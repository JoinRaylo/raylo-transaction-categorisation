"""DeBERTa-v3-small: [CLS] pooling (as pretrained) + class-weighted CE.

Does not overwrite serving dumps. Does not score locked v5/v6.

Usage:
    python src/experiment_finetune_deberta.py train
    python src/experiment_finetune_deberta.py score
    python src/experiment_finetune_deberta.py run
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

import numpy as np
import torch
import torch.nn.functional as F
from sklearn.utils.class_weight import compute_class_weight
from torch.utils.data import DataLoader
from transformers import AutoModelForSequenceClassification, AutoTokenizer, get_linear_schedule_with_warmup

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from confusion_analysis import load_taxonomy  # noqa: E402
from distillation_bakeoff import MODELS_DIR, OUT_DIR, SEED, _parse_tuning_jsonl  # noqa: E402
from eval_sets import refuse_confirmation_eval  # noqa: E402
from experiment_finetune_encoder import (  # noqa: E402
    PIPELINE_EVAL,
    TextLeafDataset,
    accs,
    collate,
    device,
    fmt,
    pct_risk,
    texts_from_gold,
    texts_from_parsed,
)
from final_evaluation import load_crosswalk, load_dictionary, load_rules  # noqa: E402
import final_evaluation as fe  # noqa: E402
from score_t5b_residual import (  # noqa: E402
    GOLD_HOLDOUT,
    GOLD_RISK,
    _promote_gambling,
    attach_waterfall,
    features_frame,
    scores_and_margin,
)

import pandas as pd

MODEL_NAME = "microsoft/deberta-v3-small"
TRAIN_JSONL = OUT_DIR / "tuning_train.jsonl"
VAL_JSONL = OUT_DIR / "tuning_val.jsonl"
HINGE_PATH = MODELS_DIR / "tfidf_linearsvm_sgd.joblib"
SAVE_DIR = MODELS_DIR / "deberta_v3_small_ft"
LABELS_PATH = SAVE_DIR / "labels.json"
REPORT = ROOT / "data" / "encoder_finetune_deberta_v3_small_report.md"

MAX_LEN = 128
BATCH = 32
EVAL_BATCH = 64
HEAD_LR = 1e-3
ENCODER_LR = 2e-5
UNFREEZE_HEAD_LR = 1e-4


def encode_texts(tokenizer, texts):
    return tokenizer(list(texts), truncation=True, padding=False, max_length=MAX_LEN)


def class_weights(y, n_labels):
    classes = np.arange(n_labels)
    w = compute_class_weight("balanced", classes=classes, y=y)
    return torch.tensor(w, dtype=torch.float32)


def weighted_loss(logits, labels, weights):
    return F.cross_entropy(logits, labels, weight=weights.to(device=logits.device, dtype=logits.dtype))


def run_epoch(model, loader, opt, sched, weights, dev, t0, label, n_steps, step0):
    model.train()
    running = 0.0
    n_seen = 0
    step = step0
    for batch in loader:
        labels = batch.pop("labels").to(dev)
        batch = {k: v.to(dev) for k, v in batch.items() if k in ("input_ids", "attention_mask")}
        logits = model(**batch).logits
        loss = weighted_loss(logits, labels, weights)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], 1.0)
        opt.step()
        if sched is not None:
            sched.step()
        running += float(loss.detach())
        n_seen += 1
        step += 1
        if step % 100 == 0:
            print(
                f"{label} step {step}/{n_steps} loss={running / n_seen:.4f} "
                f"elapsed={time.time() - t0:.0f}s",
                file=sys.stderr,
            )
            running = 0.0
            n_seen = 0
    return step


@torch.no_grad()
def val_acc(model, loader, dev):
    model.eval()
    ok = tot = 0
    for batch in loader:
        labels = batch.pop("labels").to(dev)
        batch = {k: v.to(dev) for k, v in batch.items() if k in ("input_ids", "attention_mask")}
        pred = model(**batch).logits.argmax(-1)
        ok += int((pred == labels).sum().cpu())
        tot += len(labels)
    return ok / tot if tot else 0.0


def train():
    rng = np.random.default_rng(SEED)
    print(f"Loading {TRAIN_JSONL}...", file=sys.stderr)
    df = _parse_tuning_jsonl(TRAIN_JSONL)
    df = df.iloc[rng.permutation(len(df))].reset_index(drop=True)
    leaves = sorted(df["leaf"].unique())
    label2id = {l: i for i, l in enumerate(leaves)}
    id2label = {str(i): l for l, i in label2id.items()}
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    LABELS_PATH.write_text(json.dumps({"label2id": label2id, "id2label": id2label}, indent=2))
    y = df["leaf"].map(label2id).to_numpy()
    weights_np = class_weights(y, len(leaves))
    print(
        f"{len(df)} rows, {len(leaves)} classes, {MODEL_NAME}, "
        f"weight min/median/max="
        f"{float(weights_np.min()):.2f}/{float(weights_np.median()):.2f}/{float(weights_np.max()):.2f}",
        file=sys.stderr,
    )
    tok = AutoTokenizer.from_pretrained(MODEL_NAME)
    print("Tokenising train...", file=sys.stderr)
    enc = encode_texts(tok, texts_from_parsed(df))
    pad_id = tok.pad_token_id if tok.pad_token_id is not None else 0
    loader = DataLoader(
        TextLeafDataset(enc, y.tolist()),
        batch_size=BATCH, shuffle=True,
        collate_fn=lambda b: collate(b, pad_id),
    )
    val_loader = None
    if VAL_JSONL.exists():
        val = _parse_tuning_jsonl(VAL_JSONL)
        val = val[val["leaf"].isin(label2id)].copy()
        if len(val):
            vy = val["leaf"].map(label2id).to_numpy()
            venc = encode_texts(tok, texts_from_parsed(val))
            val_loader = DataLoader(
                TextLeafDataset(venc, vy.tolist()),
                batch_size=EVAL_BATCH,
                collate_fn=lambda b: collate(b, pad_id),
            )

    dev = device()
    print(f"Device: {dev} pooling=cls weighted=balanced", file=sys.stderr)
    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME,
        num_labels=len(leaves),
        id2label={int(k): v for k, v in id2label.items()},
        label2id=label2id,
        problem_type="single_label_classification",
        attn_implementation="eager",
        ignore_mismatched_sizes=True,
        torch_dtype=torch.float32,
    )
    model.to(dev)
    weights = weights_np.to(dev)
    torch.save(weights_np, SAVE_DIR / "class_weights.pt")
    t0 = time.time()
    steps_epoch = len(loader)

    def is_head(n: str) -> bool:
        return "classifier" in n or "pooler" in n

    for name, p in model.named_parameters():
        p.requires_grad = is_head(name)
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=HEAD_LR)
    print("Phase 1: frozen encoder, weighted head", file=sys.stderr)
    run_epoch(model, loader, opt, None, weights, dev, t0, "probe", steps_epoch, 0)
    if val_loader is not None:
        print(f"probe val acc={val_acc(model, val_loader, dev):.3f}", file=sys.stderr)

    for p in model.parameters():
        p.requires_grad = True
    head = [p for n, p in model.named_parameters() if is_head(n)]
    body = [p for n, p in model.named_parameters() if not is_head(n)]
    opt = torch.optim.AdamW([
        {"params": body, "lr": ENCODER_LR},
        {"params": head, "lr": UNFREEZE_HEAD_LR},
    ])
    sched = get_linear_schedule_with_warmup(opt, int(0.06 * steps_epoch), steps_epoch)
    print("Phase 2: unfreeze encoder + head", file=sys.stderr)
    run_epoch(model, loader, opt, sched, weights, dev, t0, "unfreeze", steps_epoch, steps_epoch)
    if val_loader is not None:
        print(f"unfreeze val acc={val_acc(model, val_loader, dev):.3f}", file=sys.stderr)

    tok.save_pretrained(SAVE_DIR)
    model.save_pretrained(SAVE_DIR)
    print(f"Wrote {SAVE_DIR} in {time.time() - t0:.0f}s", file=sys.stderr)


@torch.no_grad()
def predict_deberta(texts, batch_size=EVAL_BATCH):
    blob = json.loads(LABELS_PATH.read_text())
    id2label_int = {int(k): v for k, v in blob["id2label"].items()}
    classes = np.array([id2label_int[i] for i in range(len(id2label_int))], dtype=object)
    tok = AutoTokenizer.from_pretrained(SAVE_DIR)
    model = AutoModelForSequenceClassification.from_pretrained(
        SAVE_DIR, attn_implementation="eager",
    )
    dev = device()
    model.to(dev)
    model.eval()
    scores = []
    for i in range(0, len(texts), batch_size):
        chunk = list(texts[i:i + batch_size])
        enc = tok(chunk, truncation=True, padding=True, max_length=MAX_LEN, return_tensors="pt")
        enc = {k: v.to(dev) for k, v in enc.items() if k in ("input_ids", "attention_mask")}
        logits = model(**enc).logits
        scores.append(logits.float().cpu().numpy())
    scores = np.vstack(scores)
    e = np.exp(scores - scores.max(axis=1, keepdims=True))
    proba = e / e.sum(axis=1, keepdims=True)
    pred = classes[proba.argmax(axis=1)]
    pred = _promote_gambling(pred, proba, classes)
    return pred, proba


def score():
    refuse_confirmation_eval(GOLD_HOLDOUT)
    refuse_confirmation_eval(GOLD_RISK)
    fe.SUB_MAP, fe.PRI_MAP, fe.PLAID_MAP, _ = load_crosswalk()
    fe.DICTIONARY = load_dictionary()
    fe.RULES = load_rules()
    if not (SAVE_DIR / "config.json").exists():
        sys.exit(f"missing {SAVE_DIR} — run train first")
    import joblib

    hinge = joblib.load(HINGE_PATH)
    gen_of, risk_leaves = load_taxonomy()
    holdout = attach_waterfall(pd.read_csv(GOLD_HOLDOUT))
    risk = pd.read_csv(GOLD_RISK)
    risk["provider"] = "plaid"
    risk["native_category"] = np.nan
    risk = attach_waterfall(risk)
    pipe = attach_waterfall(pd.read_csv(PIPELINE_EVAL))
    cuts = [
        ("Holdout (all, merchant-disjoint)", holdout),
        ("Holdout T6-bound", holdout[holdout["is_t6"]].copy()),
        ("Risk gold (all)", risk),
        ("Risk gold T6-bound", risk[risk["is_t6"]].copy()),
        ("Pipeline eval residual (row-disjoint)", pipe[pipe["is_t6"]].copy()),
    ]
    results = []
    print("Scoring...", file=sys.stderr)
    for name, gdf in cuts:
        feat = features_frame(gdf)
        gold = gdf["gold_leaf"].to_numpy()
        h_pred, _, _ = scores_and_margin(hinge, feat)
        e_pred, _ = predict_deberta(texts_from_gold(gdf))
        ha = accs(gold, h_pred, gen_of, risk_leaves)
        ea = accs(gold, e_pred, gen_of, risk_leaves)
        print(f"=== {name} n={len(gdf)} ===", file=sys.stderr)
        print(f"  hinge:   {fmt(ha)}", file=sys.stderr)
        print(f"  deberta: {fmt(ea)}", file=sys.stderr)
        results.append({"name": name, "n": len(gdf), "hinge": ha, "enc": ea})

    n_train = sum(1 for _ in open(TRAIN_JSONL))
    lines = [
        "# DeBERTa-v3-small vs hinge — [CLS] + class-weighted CE (2026-08-27)\n",
        f"`{MODEL_NAME}` sequence classification (`[CLS]`, as pretrained). "
        f"sklearn `balanced` class weights. Freeze encoder + weighted head "
        f"(lr={HEAD_LR}), then unfreeze (encoder {ENCODER_LR}, head {UNFREEZE_HEAD_LR}). "
        f"Batch {BATCH}, max length {MAX_LEN}. Train file `{TRAIN_JSONL.name}` "
        f"(**{n_train:,}** rows at score time). Serving hinge: "
        f"`{HINGE_PATH.relative_to(ROOT)}`. Weights: `{SAVE_DIR.relative_to(ROOT)}`. "
        f"Locked v5/v6 not scored.\n",
        "Comparators: serving hinge; mean-pool MiniLM leftover 53.0% / risk bar 68.7% "
        "(`data/encoder_finetune_minilm_meanpool_report.md`).\n",
        "| Cut | n | hinge leaf | DeBERTa leaf | Δ leaf | hinge gen | DeBERTa gen | hinge risk | Δ risk |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in results:
        h, e = r["hinge"], r["enc"]
        d_leaf = e["leaf_acc"] - h["leaf_acc"]
        d_risk = (
            f"{e['risk_acc'] - h['risk_acc']:+.1%}"
            if h["risk_acc"] is not None and e["risk_acc"] is not None
            else "n/a"
        )
        lines.append(
            f"| {r['name']} | {r['n']} | {h['leaf_acc']:.1%} | {e['leaf_acc']:.1%} | "
            f"{d_leaf:+.1%} | {h['gen_acc']:.1%} | {e['gen_acc']:.1%} | "
            f"{pct_risk(h)} | {d_risk} |"
        )
    ho = next(x for x in results if x["name"].startswith("Holdout T6"))
    rk = next(x for x in results if x["name"] == "Risk gold (all)")
    d_ho = ho["enc"]["leaf_acc"] - ho["hinge"]["leaf_acc"]
    d_bar = (rk["enc"]["risk_acc"] or 0) - (rk["hinge"]["risk_acc"] or 0)
    if d_ho > 0.01 and d_bar > -0.02:
        verdict = (
            "**DeBERTa is competitive on leftover and does not wreck the risk bar.** "
            "Keep as a candidate; leftover top-up still applies."
        )
    elif d_ho < -0.01 or d_bar < -0.05:
        verdict = (
            "**Hinge still wins leftover and/or the risk bar.** Do not serve DeBERTa. "
            "Proceed to the leftover top-up on hinge."
        )
    else:
        verdict = (
            "**Roughly tied with hinge on the money metrics.** Encoder complexity is "
            "not justified. Keep hinge."
        )
    lines += [
        "",
        "## Verdict\n",
        verdict,
        "",
        "Money metrics: **holdout T6-bound** and **risk-category bar** on full risk gold. "
        "Do not overwrite serving dumps.\n",
    ]
    REPORT.write_text("\n".join(lines) + "\n")
    print(REPORT.read_text())
    print(f"Wrote {REPORT}", file=sys.stderr)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    if cmd == "train":
        train()
    elif cmd == "score":
        score()
    elif cmd == "run":
        train()
        score()
    else:
        sys.exit(__doc__)

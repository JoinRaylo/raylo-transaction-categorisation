"""Fine-tune MiniLM as a 275-way classifier on the current tuning jsonl.

Fair A/B vs the hinge dump trained on the same file: only the model family
changes. Does not overwrite serving dumps. Does not score locked v5/v6.

Usage:
    python src/experiment_finetune_encoder.py train       # mean-pool (correct)
    python src/experiment_finetune_encoder.py score
    python src/experiment_finetune_encoder.py run
    python src/experiment_finetune_encoder.py train-cls   # original [CLS] run
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader, Dataset
import torch.nn as nn
import torch.nn.functional as F
from transformers import AutoModel, AutoModelForSequenceClassification, AutoTokenizer, get_linear_schedule_with_warmup

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from confusion_analysis import analyse, load_taxonomy  # noqa: E402
from distillation_bakeoff import MODELS_DIR, OUT_DIR, SEED, _parse_tuning_jsonl  # noqa: E402
from eval_sets import refuse_confirmation_eval  # noqa: E402
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

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
TRAIN_JSONL = OUT_DIR / "tuning_train.jsonl"
VAL_JSONL = OUT_DIR / "tuning_val.jsonl"
HINGE_PATH = MODELS_DIR / "tfidf_linearsvm_sgd.joblib"
CLS_SAVE_DIR = MODELS_DIR / "minilm_ft_jsonl"
SAVE_DIR = MODELS_DIR / "minilm_ft_meanpool"
LABELS_PATH = SAVE_DIR / "labels.json"
REPORT = ROOT / "data" / "encoder_finetune_minilm_meanpool_report.md"
HEAD_LR = 1e-3
ENCODER_LR = 2e-5
UNFREEZE_HEAD_LR = 1e-4
PIPELINE_EVAL = OUT_DIR / "gold_pipeline_eval.csv"

MAX_LEN = 128
BATCH = 64
EPOCHS = 1
LR = 2e-5
EVAL_BATCH = 128


def device():
    if torch.backends.mps.is_available():
        return torch.device("mps")
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def row_text(vendor, description, amount, is_credit):
    direction = "credit" if int(is_credit) else "debit"
    try:
        amt = f"{abs(float(amount)):.2f}"
    except (TypeError, ValueError):
        amt = "0.00"
    return f"{vendor or ''} | {description or ''} | amt={amt} | {direction}".strip().lower()


def texts_from_parsed(df):
    return [
        row_text(r.vendor, r.description, r.amount, r.is_credit)
        for r in df.itertuples(index=False)
    ]


def texts_from_gold(df):
    is_credit = (df["direction"].astype(str).str.lower() == "credit").astype(int)
    return [
        row_text(m, d, a, c)
        for m, d, a, c in zip(
            df["merchant_raw"].fillna(""),
            df["description_raw"].fillna(""),
            df["amount"],
            is_credit,
        )
    ]


class TextLeafDataset(Dataset):
    def __init__(self, encodings, labels):
        self.encodings = encodings
        self.labels = labels

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, i):
        return {
            "input_ids": self.encodings["input_ids"][i],
            "attention_mask": self.encodings["attention_mask"][i],
            "labels": self.labels[i],
        }


def collate(batch, pad_id):
    max_len = max(len(x["input_ids"]) for x in batch)
    input_ids, mask, labels = [], [], []
    for x in batch:
        n = len(x["input_ids"])
        pad = max_len - n
        input_ids.append(x["input_ids"] + [pad_id] * pad)
        mask.append(x["attention_mask"] + [0] * pad)
        labels.append(x["labels"])
    return {
        "input_ids": torch.tensor(input_ids, dtype=torch.long),
        "attention_mask": torch.tensor(mask, dtype=torch.long),
        "labels": torch.tensor(labels, dtype=torch.long),
    }


def encode_texts(tokenizer, texts):
    return tokenizer(
        list(texts),
        truncation=True,
        padding=False,
        max_length=MAX_LEN,
    )


def load_label_maps(leaves=None):
    if LABELS_PATH.exists() and leaves is None:
        blob = json.loads(LABELS_PATH.read_text())
        return blob["label2id"], blob["id2label"]
    label2id = {l: i for i, l in enumerate(leaves)}
    id2label = {str(i): l for l, i in label2id.items()}
    return label2id, id2label


class MeanPoolClassifier(nn.Module):
    """MiniLM encoder + mean pool over non-pad tokens + linear leaf head.

    sentence-transformers/all-MiniLM-L6-v2 was trained with mean pooling.
    BertForSequenceClassification uses [CLS], which this checkpoint never
    trained as a sentence vector.
    """

    def __init__(self, model_name, num_labels):
        super().__init__()
        self.encoder = AutoModel.from_pretrained(model_name, attn_implementation="eager")
        hidden = self.encoder.config.hidden_size
        self.classifier = nn.Linear(hidden, num_labels)

    def forward(self, input_ids, attention_mask, labels=None):
        last = self.encoder(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state
        mask = attention_mask.unsqueeze(-1).to(last.dtype)
        pooled = (last * mask).sum(1) / mask.sum(1).clamp(min=1e-6)
        logits = self.classifier(pooled)
        loss = None
        if labels is not None:
            loss = F.cross_entropy(logits, labels)
        return logits, loss


def _logits(model, batch):
    out = model(**batch)
    if isinstance(out, tuple):
        return out[0], out[1]
    return out.logits, out.loss


def _prepare_data():
    rng = np.random.default_rng(SEED)
    print(f"Loading {TRAIN_JSONL}...", file=sys.stderr)
    df = _parse_tuning_jsonl(TRAIN_JSONL)
    df = df.iloc[rng.permutation(len(df))].reset_index(drop=True)
    leaves = sorted(df["leaf"].unique())
    label2id, id2label = load_label_maps(leaves)
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    LABELS_PATH.write_text(json.dumps({"label2id": label2id, "id2label": id2label}, indent=2))
    y = df["leaf"].map(label2id).to_numpy()
    texts = texts_from_parsed(df)
    print(f"{len(df)} rows, {len(leaves)} classes, model={MODEL_NAME}", file=sys.stderr)
    tok = AutoTokenizer.from_pretrained(MODEL_NAME)
    print("Tokenising train...", file=sys.stderr)
    enc = encode_texts(tok, texts)
    ds = TextLeafDataset(enc, y.tolist())
    pad_id = tok.pad_token_id if tok.pad_token_id is not None else 0
    loader = DataLoader(
        ds, batch_size=BATCH, shuffle=True,
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
    return tok, loader, val_loader, len(leaves), id2label, label2id


def _run_epoch(model, loader, opt, sched, dev, t0, epoch_label, n_steps, step0):
    model.train()
    running = 0.0
    n_seen = 0
    global_step = step0
    for batch in loader:
        labels = batch.pop("labels").to(dev)
        batch = {k: v.to(dev) for k, v in batch.items()}
        logits, loss = _logits(model, {**batch, "labels": labels})
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], 1.0)
        opt.step()
        if sched is not None:
            sched.step()
        running += float(loss.detach())
        n_seen += 1
        global_step += 1
        if global_step % 100 == 0:
            print(
                f"{epoch_label} step {global_step}/{n_steps} "
                f"loss={running / n_seen:.4f} elapsed={time.time() - t0:.0f}s",
                file=sys.stderr,
            )
            running = 0.0
            n_seen = 0
    return global_step


def train():
    """Mean-pool MiniLM: freeze encoder (linear probe) then unfreeze."""
    tok, loader, val_loader, n_labels, id2label, label2id = _prepare_data()
    dev = device()
    print(f"Device: {dev} pooling=mean", file=sys.stderr)
    model = MeanPoolClassifier(MODEL_NAME, n_labels)
    model.to(dev)
    t0 = time.time()
    steps_epoch = len(loader)

    for p in model.encoder.parameters():
        p.requires_grad = False
    opt = torch.optim.AdamW(model.classifier.parameters(), lr=HEAD_LR)
    print("Phase 1: frozen encoder, train head", file=sys.stderr)
    _run_epoch(model, loader, opt, None, dev, t0, "probe", steps_epoch, 0)
    if val_loader is not None:
        print(f"probe val acc={_val_acc(model, val_loader, dev):.3f}", file=sys.stderr)

    for p in model.parameters():
        p.requires_grad = True
    opt = torch.optim.AdamW([
        {"params": model.encoder.parameters(), "lr": ENCODER_LR},
        {"params": model.classifier.parameters(), "lr": UNFREEZE_HEAD_LR},
    ])
    sched = get_linear_schedule_with_warmup(opt, int(0.06 * steps_epoch), steps_epoch)
    print("Phase 2: unfreeze encoder + head", file=sys.stderr)
    _run_epoch(model, loader, opt, sched, dev, t0, "unfreeze", steps_epoch, steps_epoch)
    if val_loader is not None:
        print(f"unfreeze val acc={_val_acc(model, val_loader, dev):.3f}", file=sys.stderr)

    tok.save_pretrained(SAVE_DIR)
    torch.save({
        "state_dict": model.state_dict(),
        "num_labels": n_labels,
        "model_name": MODEL_NAME,
        "id2label": id2label,
        "label2id": label2id,
        "pooling": "mean",
    }, SAVE_DIR / "model.pt")
    print(f"Wrote {SAVE_DIR} in {time.time() - t0:.0f}s", file=sys.stderr)


def train_cls():
    """Original (wrong pooling) CLS-head run. Kept for provenance."""
    rng = np.random.default_rng(SEED)
    print(f"Loading {TRAIN_JSONL}...", file=sys.stderr)
    df = _parse_tuning_jsonl(TRAIN_JSONL)
    df = df.iloc[rng.permutation(len(df))].reset_index(drop=True)
    leaves = sorted(df["leaf"].unique())
    CLS_SAVE_DIR.mkdir(parents=True, exist_ok=True)
    label2id = {l: i for i, l in enumerate(leaves)}
    id2label = {str(i): l for l, i in label2id.items()}
    (CLS_SAVE_DIR / "labels.json").write_text(json.dumps({"label2id": label2id, "id2label": id2label}, indent=2))
    y = df["leaf"].map(label2id).to_numpy()
    texts = texts_from_parsed(df)
    tok = AutoTokenizer.from_pretrained(MODEL_NAME)
    enc = encode_texts(tok, texts)
    ds = TextLeafDataset(enc, y.tolist())
    pad_id = tok.pad_token_id if tok.pad_token_id is not None else 0
    loader = DataLoader(ds, batch_size=BATCH, shuffle=True, collate_fn=lambda b: collate(b, pad_id))
    dev = device()
    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME, num_labels=len(leaves),
        id2label={int(k): v for k, v in id2label.items()}, label2id=label2id,
        problem_type="single_label_classification",
    )
    model.to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=LR)
    steps = EPOCHS * len(loader)
    sched = get_linear_schedule_with_warmup(opt, int(0.06 * steps), steps)
    t0 = time.time()
    _run_epoch(model, loader, opt, sched, dev, t0, "cls", steps, 0)
    model.save_pretrained(CLS_SAVE_DIR)
    tok.save_pretrained(CLS_SAVE_DIR)
    print(f"Wrote {CLS_SAVE_DIR} in {time.time() - t0:.0f}s", file=sys.stderr)


@torch.no_grad()
def _val_acc(model, loader, dev):
    model.eval()
    ok = tot = 0
    for batch in loader:
        labels = batch.pop("labels").to(dev)
        batch = {k: v.to(dev) for k, v in batch.items()}
        logits, _ = _logits(model, batch)
        pred = logits.argmax(-1)
        ok += int((pred == labels).sum().cpu())
        tot += len(labels)
    return ok / tot if tot else 0.0


@torch.no_grad()
def predict_encoder(texts, batch_size=EVAL_BATCH):
    blob = torch.load(SAVE_DIR / "model.pt", map_location="cpu", weights_only=False)
    id2label = blob["id2label"]
    id2label_int = {int(k): v for k, v in id2label.items()}
    classes = np.array([id2label_int[i] for i in range(len(id2label_int))], dtype=object)
    tok = AutoTokenizer.from_pretrained(SAVE_DIR)
    model = MeanPoolClassifier(blob["model_name"], blob["num_labels"])
    model.load_state_dict(blob["state_dict"])
    dev = device()
    model.to(dev)
    model.eval()
    scores = []
    for i in range(0, len(texts), batch_size):
        chunk = list(texts[i:i + batch_size])
        enc = tok(chunk, truncation=True, padding=True, max_length=MAX_LEN, return_tensors="pt")
        enc = {k: v.to(dev) for k, v in enc.items() if k in ("input_ids", "attention_mask")}
        logits, _ = model(**enc)
        scores.append(logits.float().cpu().numpy())
    scores = np.vstack(scores)
    e = np.exp(scores - scores.max(axis=1, keepdims=True))
    proba = e / e.sum(axis=1, keepdims=True)
    pred = classes[proba.argmax(axis=1)]
    pred = _promote_gambling(pred, proba, classes)
    return pred, proba


def accs(gold, pred, gen_of, risk_leaves):
    rows = [{"gold_leaf": g, "pred_leaf": p} for g, p in zip(gold, pred)]
    return analyse(rows, gen_of, risk_leaves)


def pct_risk(a):
    return f"{a['risk_acc']:.1%}" if a["risk_acc"] is not None else "n/a"


def fmt(a):
    return f"leaf {a['leaf_acc']:.1%} / gen {a['gen_acc']:.1%} / risk {pct_risk(a)} (n={a['risk_n']})"


def score():
    refuse_confirmation_eval(GOLD_HOLDOUT)
    refuse_confirmation_eval(GOLD_RISK)
    fe.SUB_MAP, fe.PRI_MAP, fe.PLAID_MAP, _ = load_crosswalk()
    fe.DICTIONARY = load_dictionary()
    fe.RULES = load_rules()
    if not (SAVE_DIR / "model.pt").exists():
        sys.exit(f"missing {SAVE_DIR / 'model.pt'} — run train first")
    import joblib

    hinge = joblib.load(HINGE_PATH)
    gen_of, risk_leaves = load_taxonomy()

    holdout = pd.read_csv(GOLD_HOLDOUT)
    holdout = attach_waterfall(holdout)
    risk = pd.read_csv(GOLD_RISK)
    risk["provider"] = "plaid"
    risk["native_category"] = np.nan
    risk = attach_waterfall(risk)
    pipe = pd.read_csv(PIPELINE_EVAL)
    pipe = attach_waterfall(pipe)

    cuts = [
        ("Holdout (all, merchant-disjoint)", holdout),
        ("Holdout T6-bound", holdout[holdout["is_t6"]].copy()),
        ("Risk gold (all)", risk),
        ("Risk gold T6-bound", risk[risk["is_t6"]].copy()),
        ("Pipeline eval residual (row-disjoint)", pipe[pipe["is_t6"]].copy()),
        ("Pipeline eval (all, classifier-only)", pipe),
    ]
    results = []
    print("Scoring...", file=sys.stderr)
    for name, gdf in cuts:
        feat = features_frame(gdf)
        gold = gdf["gold_leaf"].to_numpy()
        h_pred, _, _ = scores_and_margin(hinge, feat)
        e_pred, _ = predict_encoder(texts_from_gold(gdf))
        ha = accs(gold, h_pred, gen_of, risk_leaves)
        ea = accs(gold, e_pred, gen_of, risk_leaves)
        print(f"=== {name} n={len(gdf)} ===", file=sys.stderr)
        print(f"  hinge:  {fmt(ha)}", file=sys.stderr)
        print(f"  mean-pool: {fmt(ea)}", file=sys.stderr)
        results.append({"name": name, "n": len(gdf), "hinge": ha, "enc": ea})

    n_train = sum(1 for _ in open(TRAIN_JSONL))
    lines = [
        "# Mean-pool MiniLM vs hinge (pooling fix, 2026-08-27)\n",
        "The first MiniLM run used `BertForSequenceClassification` (`[CLS]` pooling). "
        f"`{MODEL_NAME}` is a **mean-pool** sentence encoder. This retry: frozen encoder "
        f"+ linear head (lr={HEAD_LR}), then unfreeze (encoder lr={ENCODER_LR}, head "
        f"lr={UNFREEZE_HEAD_LR}), one epoch each, batch {BATCH}. "
        f"Train `{TRAIN_JSONL.name}` (**{n_train:,}** rows). "
        f"Hinge is serving v5 `{HINGE_PATH.relative_to(ROOT)}`. "
        f"Weights: `{SAVE_DIR.relative_to(ROOT)}`. CLS run kept at "
        f"`{CLS_SAVE_DIR.relative_to(ROOT)}` (`data/encoder_finetune_minilm_report.md`). "
        f"Locked v5/v6 not scored.\n",
        "Frozen MiniLM + logreg (mean pool, 164k jsonl) was **27.6%** holdout leaf. "
        "CLS-pool fine-tune was **13.1%** holdout / **17.5%** leftover.\n",
        "| Cut | n | hinge leaf | mean-pool MiniLM | Δ leaf | hinge gen | MiniLM gen | hinge risk | Δ risk |",
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
    pipe_r = next(x for x in results if "Pipeline eval residual" in x["name"])
    d_ho = ho["enc"]["leaf_acc"] - ho["hinge"]["leaf_acc"]
    d_pipe = pipe_r["enc"]["leaf_acc"] - pipe_r["hinge"]["leaf_acc"]
    if d_ho > 0.01 and d_pipe > 0.005:
        verdict = (
            "**Mean-pool MiniLM beats hinge on the leftover.** Worth a candidate head; "
            "still do the leftover top-up."
        )
    elif d_ho < -0.01 or d_pipe < -0.01:
        verdict = (
            "**Hinge still wins the leftover** after the pooling fix. Char TF-IDF remains "
            "the runtime family. Do not serve MiniLM. Proceed to the leftover top-up on hinge."
        )
    else:
        verdict = (
            "**Roughly tied on the leftover.** Encoder complexity is not justified. Keep hinge."
        )
    lines += [
        "",
        "## Verdict\n",
        verdict,
        "",
        "Money metrics: holdout T6-bound and pipeline residual. Pipeline-all is "
        "classifier-only (T4 would catch most of those rows).\n",
        "Do not overwrite serving dumps with the encoder.\n",
    ]
    REPORT.write_text("\n".join(lines) + "\n")
    print(REPORT.read_text())
    print(f"Wrote {REPORT}", file=sys.stderr)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    if cmd == "train":
        train()
    elif cmd == "train-cls":
        train_cls()
    elif cmd == "score":
        score()
    elif cmd == "run":
        train()
        score()
    else:
        sys.exit(__doc__)

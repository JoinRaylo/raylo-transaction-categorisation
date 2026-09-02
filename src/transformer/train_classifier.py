"""Stage 2: leaf classifier on the domain-adapted encoder.

Head design (from the review, §5):
  * leaf head (275-way) + general head (29-way) with a hierarchy-consistency
    loss: the leaf distribution rolled up through the taxonomy must match the
    general head (DragoNet-style, cheap);
  * direction mask at the logits: `cash_flow_type` in taxonomy.csv says which
    leaves are legal for a credit / debit, so an impossible leaf can never be
    predicted (Uncapped's "direction constraints"). The mask is also applied
    in training so the loss does not spend capacity on impossible classes;
  * two passes: (a) silver — T1–T5 waterfall labels on ~1.9M distinct keys,
    one epoch, learns the head's vocabulary and the dictionary; (b) gold — the
    tuning jsonl (383k, gold-quality) with class-balanced sampling (cap head
    classes, oversample thin risk/credit leaves), 3 epochs by default.

Input text is the same sentence format as pretraining
(`[DEBIT] [AMT_x] merchant | description`), built by `build_corpus.sentence()`.

Kill criteria live in `score_transformer.py`; this script only trains. Nothing here
reads a gold eval file. Does not touch the hinge serving dumps.

Usage:
    python src/transformer/train_classifier.py silver   [--epochs 1]
    python src/transformer/train_classifier.py gold     [--epochs 3] [--from silver|mlm]
    python src/transformer/train_classifier.py all
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import pathlib
import sys
import time

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
from transformers import AutoModel, AutoTokenizer, get_linear_schedule_with_warmup

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src" / "transformer"))

from build_corpus import SILVER_PARQUET, amt_bucket_py, sentence  # noqa: E402
from distillation_bakeoff import OUT_DIR, _parse_tuning_jsonl  # noqa: E402
from pretrain_mlm import SAVE_DIR as MLM_DIR, device, log as _log  # noqa: E402

TAXONOMY = ROOT / "taxonomy" / "taxonomy.csv"
TRAIN_JSONL = OUT_DIR / "tuning_train.jsonl"
VAL_JSONL = OUT_DIR / "tuning_val.jsonl"
MODELS = ROOT / "outputs" / "distill_models"
SILVER_DIR = MODELS / "txn_classifier_silver"
GOLD_DIR = MODELS / "txn_classifier_gold"
LOG = ROOT / "outputs" / "transformer" / "train_classifier.log"

# cash_flow_type -> legal directions. `spend` is debit-only EXCEPT that a refund
# of spend is a credit, which the taxonomy models as `refund_received` (income).
CREDIT_OK = {"income", "transfer_own_accounts", "p2p_transfer", "debt_disbursement"}
DEBIT_OK = {"spend", "debt_repayment", "transfer_own_accounts", "p2p_transfer", "fee_or_penalty"}
# Leaves that legitimately appear in both directions regardless of cash_flow_type
# (provider mechanism categories, catch-alls, reversals).
BOTH_OK_LEAVES = {
    "unclassified_other", "unclassified_transfer", "unclassified_recurring",
    "unclassified_card_spend", "returned_payment", "adjustment", "cashback",
    "balance_transfer", "card_payment_unspecified", "gambling_unspecified",
    "transfer_bank_unspecified", "financial_institution_unspecified",
}


def log(msg):
    print(msg, file=sys.stderr, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as f:
        f.write(msg + "\n")


# ------------------------------------------------------------ taxonomy
EMPIRICAL_MIN_ROWS = 5


def _empirical_direction_counts():
    """(leaf, direction) -> rows in the gold jsonl. Iteration 1 showed the taxonomy-only
    mask forbids conventions the gold set uses (a cash-advance *disbursement* credit is
    labelled `cash_advance`); the mask is therefore taxonomy OR observed-in-gold."""
    if not TRAIN_JSONL.exists():
        return {}
    df = _parse_tuning_jsonl(TRAIN_JSONL)
    c = df.groupby(["leaf", df["is_credit"].astype(int)]).size()
    return {(l, int(d)): int(n) for (l, d), n in c.items()}


def load_taxonomy():
    tax = pd.read_csv(TAXONOMY)
    emp = _empirical_direction_counts()
    leaves = sorted(tax["detailed_category"].tolist()) + ["unclassified_other"] \
        if "unclassified_other" not in set(tax["detailed_category"]) else sorted(tax["detailed_category"].tolist())
    leaf_ix = {l: i for i, l in enumerate(leaves)}
    gens = sorted(tax["general_category"].unique().tolist())
    gen_ix = {g: i for i, g in enumerate(gens)}
    gen_of = dict(zip(tax["detailed_category"], tax["general_category"]))
    cft = dict(zip(tax["detailed_category"], tax["cash_flow_type"]))
    leaf_to_gen = torch.tensor([gen_ix[gen_of.get(l, gens[0])] for l in leaves])
    credit_ok = torch.tensor([
        (cft.get(l) in CREDIT_OK) or (l in BOTH_OK_LEAVES) or l.startswith("unclassified")
        or emp.get((l, 1), 0) >= EMPIRICAL_MIN_ROWS
        for l in leaves])
    debit_ok = torch.tensor([
        (cft.get(l) in DEBIT_OK) or (l in BOTH_OK_LEAVES) or l.startswith("unclassified")
        or emp.get((l, 0), 0) >= EMPIRICAL_MIN_ROWS
        for l in leaves])
    return leaves, leaf_ix, gens, gen_ix, leaf_to_gen, credit_ok, debit_ok


# ------------------------------------------------------------ model
class TxnClassifier(nn.Module):
    def __init__(self, encoder_dir, n_leaf, n_gen, leaf_to_gen, credit_ok, debit_ok, dropout=0.1):
        super().__init__()
        self.encoder = AutoModel.from_pretrained(encoder_dir)
        h = self.encoder.config.hidden_size
        self.drop = nn.Dropout(dropout)
        self.leaf_head = nn.Linear(h, n_leaf)
        self.gen_head = nn.Linear(h, n_gen)
        self.register_buffer("leaf_to_gen", leaf_to_gen)
        self.register_buffer("credit_ok", credit_ok)
        self.register_buffer("debit_ok", debit_ok)
        self.n_gen = n_gen

    def pool(self, input_ids, attention_mask):
        out = self.encoder(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state
        m = attention_mask.unsqueeze(-1).to(out.dtype)
        return (out * m).sum(1) / m.sum(1).clamp(min=1.0)  # mean pool

    def forward(self, input_ids, attention_mask, is_credit):
        z = self.drop(self.pool(input_ids, attention_mask))
        leaf = self.leaf_head(z)
        gen = self.gen_head(z)
        legal = torch.where(is_credit.unsqueeze(-1).bool(), self.credit_ok, self.debit_ok)
        leaf = leaf.masked_fill(~legal, -1e4)
        return leaf, gen

    def rolled_up(self, leaf_logits):
        p = F.softmax(leaf_logits, dim=-1)
        out = torch.zeros(p.shape[0], self.n_gen, device=p.device, dtype=p.dtype)
        return out.index_add_(1, self.leaf_to_gen, p)


def loss_fn(model, leaf_logits, gen_logits, y_leaf, y_gen, w_gen=0.3, w_cons=0.3):
    l_leaf = F.cross_entropy(leaf_logits, y_leaf)
    l_gen = F.cross_entropy(gen_logits, y_gen)
    rolled = model.rolled_up(leaf_logits).clamp(min=1e-6)
    l_cons = F.kl_div(rolled.log(), F.softmax(gen_logits, dim=-1), reduction="batchmean")
    return l_leaf + w_gen * l_gen + w_cons * l_cons, (l_leaf.item(), l_gen.item(), l_cons.item())


# ------------------------------------------------------------ data
def gold_frame():
    df = _parse_tuning_jsonl(TRAIN_JSONL)
    df["text"] = [sentence("credit" if int(c) else "debit", amt_bucket_py(a), v, d)
                  for v, d, a, c in zip(df["vendor"], df["description"], df["amount"], df["is_credit"])]
    df["is_credit"] = df["is_credit"].astype(int)
    return df[["text", "leaf", "is_credit"]]


def silver_frame():
    df = pd.read_parquet(SILVER_PARQUET, columns=["text", "leaf", "direction"])
    df["is_credit"] = (df["direction"] == "credit").astype(int)
    return df[["text", "leaf", "is_credit"]]


def balanced_order(leaves_col: pd.Series, cap: int, floor: int, rng) -> np.ndarray:
    """Indices with head classes capped at `cap` rows and thin classes repeated up to `floor`."""
    idx = []
    for leaf, grp in leaves_col.groupby(leaves_col).groups.items():
        g = np.asarray(list(grp))
        if len(g) > cap:
            g = rng.choice(g, cap, replace=False)
        elif len(g) < floor:
            g = np.concatenate([g, rng.choice(g, floor - len(g), replace=True)])
        idx.append(g)
    out = np.concatenate(idx)
    rng.shuffle(out)
    return out


# ------------------------------------------------------------ train
def run_stage(name, df, encoder_dir, out_dir, epochs, batch, lr, max_len, cap, floor, ckpt_every,
              val_df=None):
    dev = device()
    leaves, leaf_ix, gens, gen_ix, leaf_to_gen, credit_ok, debit_ok = load_taxonomy()
    tok = AutoTokenizer.from_pretrained(encoder_dir)
    model = TxnClassifier(encoder_dir, len(leaves), len(gens), leaf_to_gen, credit_ok, debit_ok).to(dev)
    if (pathlib.Path(encoder_dir) / "heads.pt").exists():
        model.load_state_dict(torch.load(pathlib.Path(encoder_dir) / "heads.pt", map_location="cpu"), strict=False)
        log(f"[{name}] loaded classifier heads from {encoder_dir}")
    gen_of_leaf = {l: gens.index(g) for l, g in zip(leaves, [gens[i] for i in leaf_to_gen.tolist()])}

    df = df[df["leaf"].isin(leaf_ix)].reset_index(drop=True)
    # Drop rows whose label is illegal for their direction under the mask. In the gold
    # jsonl this is 0.27% (direction/label noise); in silver it is 3.6% and is exactly
    # the direction-blind T4 problem (a debit-default leaf stamped on a credit) — those
    # are wrong labels, not signal. Logged so the share stays visible.
    cok = dict(zip(leaves, credit_ok.tolist())); dok = dict(zip(leaves, debit_ok.tolist()))
    legal = np.where(df["is_credit"] == 1, df["leaf"].map(cok), df["leaf"].map(dok)).astype(bool)
    log(f"[{name}] dropping {int((~legal).sum()):,} / {len(df):,} rows with a direction-illegal label "
        f"({100 * (~legal).mean():.2f}%)")
    df = df[legal].reset_index(drop=True)
    rng = np.random.default_rng(42)
    y_leaf_all = df["leaf"].map(leaf_ix).to_numpy()
    y_gen_all = df["leaf"].map(gen_of_leaf).to_numpy()
    is_credit_all = df["is_credit"].to_numpy()
    texts = df["text"].tolist()

    order = balanced_order(df["leaf"], cap, floor, rng)
    steps_per_epoch = math.ceil(len(order) / batch)
    total = steps_per_epoch * epochs
    log(f"[{name}] {len(df):,} rows -> {len(order):,} per epoch after cap={cap}/floor={floor}; "
        f"{df.leaf.nunique()} leaves; credit share {is_credit_all.mean():.1%}; {total} steps")

    enc_params = [p for n, p in model.named_parameters() if n.startswith("encoder.")]
    head_params = [p for n, p in model.named_parameters() if not n.startswith("encoder.")]
    opt = torch.optim.AdamW([{"params": enc_params, "lr": lr}, {"params": head_params, "lr": lr * 10}],
                            weight_decay=0.01)
    sched = get_linear_schedule_with_warmup(opt, int(0.05 * total), total)
    out_dir.mkdir(parents=True, exist_ok=True)
    ckpt = out_dir / "ckpt.pt"
    step = 0
    if ckpt.exists():
        ck = torch.load(ckpt, map_location="cpu")
        model.load_state_dict(ck["model"]); opt.load_state_dict(ck["opt"]); sched.load_state_dict(ck["sched"])
        step = ck["step"]; log(f"[{name}] resumed at step {step}")

    model.train()
    t0 = time.time(); run = collections.deque(maxlen=200)
    while step < total:
        ep = step // steps_per_epoch
        if step % steps_per_epoch == 0 and step > 0:
            order = balanced_order(df["leaf"], cap, floor, np.random.default_rng(42 + ep))
        i = (step % steps_per_epoch) * batch
        b = order[i:i + batch]
        if len(b) == 0:
            step += 1; continue
        enc = tok([texts[j] for j in b], truncation=True, max_length=max_len, padding="longest", return_tensors="pt")
        ids, attn = enc["input_ids"].to(dev), enc["attention_mask"].to(dev)
        y_leaf = torch.tensor(y_leaf_all[b], device=dev)
        y_gen = torch.tensor(y_gen_all[b], device=dev)
        is_credit = torch.tensor(is_credit_all[b], device=dev)
        leaf_logits, gen_logits = model(ids, attn, is_credit)
        loss, parts = loss_fn(model, leaf_logits, gen_logits, y_leaf, y_gen)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step(); sched.step(); opt.zero_grad(set_to_none=True)
        step += 1
        run.append(parts)
        if step % 200 == 0:
            a = np.mean(run, axis=0)
            el = time.time() - t0
            rate = step * batch / max(el, 1e-6)
            log(f"[{name}] step {step}/{total} leaf {a[0]:.3f} gen {a[1]:.3f} cons {a[2]:.3f} "
                f"{rate:.0f} rows/s eta {(total - step) * batch / rate / 60:.0f} min")
        if step % ckpt_every == 0 or step == total:
            torch.save({"model": model.state_dict(), "opt": opt.state_dict(), "sched": sched.state_dict(),
                        "step": step}, ckpt)
    # save encoder + tokenizer (HF format) + heads
    model.encoder.save_pretrained(out_dir)
    tok.save_pretrained(out_dir)
    torch.save({k: v for k, v in model.state_dict().items() if not k.startswith("encoder.")}, out_dir / "heads.pt")
    (out_dir / "labels.json").write_text(json.dumps({"leaves": leaves, "generals": gens}))
    (out_dir / "train_meta.json").write_text(json.dumps({
        "stage": name, "rows": len(df), "per_epoch": int(len(order)), "epochs": epochs, "batch": batch,
        "lr": lr, "max_len": max_len, "cap": cap, "floor": floor, "encoder_from": str(encoder_dir),
        "wall_s": round(time.time() - t0)}, indent=2))
    if val_df is not None:
        acc = evaluate(model, tok, val_df, leaf_ix, dev, max_len)
        log(f"[{name}] val (head-like, not the holdout) leaf acc {acc:.1%}")
    log(f"[{name}] saved {out_dir}")


@torch.no_grad()
def evaluate(model, tok, df, leaf_ix, dev, max_len, batch=256):
    model.eval()
    df = df[df["leaf"].isin(leaf_ix)]
    leaves = list(leaf_ix)
    ok = 0
    for i in range(0, len(df), batch):
        chunk = df.iloc[i:i + batch]
        enc = tok(chunk["text"].tolist(), truncation=True, max_length=max_len, padding="longest", return_tensors="pt")
        leaf_logits, _ = model(enc["input_ids"].to(dev), enc["attention_mask"].to(dev),
                               torch.tensor(chunk["is_credit"].to_numpy(), device=dev))
        pred = [leaves[j] for j in leaf_logits.argmax(-1).tolist()]
        ok += sum(p == g for p, g in zip(pred, chunk["leaf"]))
    model.train()
    return ok / max(len(df), 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["silver", "gold", "all"])
    ap.add_argument("--epochs", type=int, default=None)
    ap.add_argument("--batch", type=int, default=128)
    ap.add_argument("--lr", type=float, default=3e-5)
    ap.add_argument("--max-len", type=int, default=48)
    ap.add_argument("--from", dest="from_", choices=["mlm", "silver"], default=None)
    ap.add_argument("--max-silver", type=int, default=None)
    ap.add_argument("--ckpt-every", type=int, default=2000)
    ap.add_argument("--encoder", default=None,
                    help="Encoder dir or HF id for the silver stage (default: the MLM-adapted encoder)")
    args = ap.parse_args()
    mlm_dir = pathlib.Path(args.encoder) if args.encoder and pathlib.Path(args.encoder).exists() \
        else (args.encoder or MLM_DIR)

    val = None
    if VAL_JSONL.exists():
        v = _parse_tuning_jsonl(VAL_JSONL)
        v["text"] = [sentence("credit" if int(c) else "debit", amt_bucket_py(a), m, d)
                     for m, d, a, c in zip(v["vendor"], v["description"], v["amount"], v["is_credit"])]
        v["is_credit"] = v["is_credit"].astype(int)
        val = v[["text", "leaf", "is_credit"]]

    if args.stage in ("silver", "all"):
        df = silver_frame()
        if args.max_silver:
            df = df.sample(min(args.max_silver, len(df)), random_state=42)
        run_stage("silver", df, mlm_dir, SILVER_DIR, args.epochs or 1, args.batch, args.lr, args.max_len,
                  cap=25_000, floor=200, ckpt_every=args.ckpt_every, val_df=val)
    if args.stage in ("gold", "all"):
        src = SILVER_DIR if (args.from_ or "silver") == "silver" and SILVER_DIR.exists() else mlm_dir
        df = gold_frame()
        run_stage("gold", df, src, GOLD_DIR, args.epochs or 3, args.batch, args.lr, args.max_len,
                  cap=20_000, floor=300, ckpt_every=args.ckpt_every, val_df=val)


if __name__ == "__main__":
    main()

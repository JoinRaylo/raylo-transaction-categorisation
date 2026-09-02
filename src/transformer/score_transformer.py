"""Stage 3: score the transformer classifier against the serving hinge on the
same cuts as every encoder experiment in this repo, and apply the kill criteria.

Cuts (all row-level, never locked v5/v6):
  * holdout `gold_v2_slm_eval_holdout.csv` (1,055, merchant-disjoint) — all + T6-bound
  * risk gold `gold_transactions_risk_categories.csv` (711) — all + T6-bound (what T5b serves)
  * pipeline eval `outputs/gold_pipeline_eval.csv` — residual (T6/T7-bound) + full pipeline

Comparator is the DE-LEAKED hinge (`tfidf_linearsvm_sgd_v6_deleaked.joblib`) by default —
the v5 serving dump's risk numbers are in-sample (see data/classifier_v6_deleaked_report.md).

Kill criteria (review §5, Stage 3): holdout T6-bound leaf >= hinge +3pp; pipeline residual
leaf >= hinge +3pp; T6-bound risk-leaf accuracy no worse than hinge; credit-side bar >= hinge
+10pp; CPU throughput >= 1,000 rows/s. Miss two -> stop, keep hinge.

Usage:
    python src/transformer/score_transformer.py [--model outputs/distill_models/txn_classifier_gold]
        [--hinge outputs/distill_models/tfidf_linearsvm_sgd_v6_deleaked.joblib]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

import joblib
import numpy as np
import pandas as pd
import torch
from transformers import AutoTokenizer

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src" / "transformer"))

from build_corpus import amt_bucket_py, sentence  # noqa: E402
from confusion_analysis import CREDIT_BAR_LEAVES, analyse, load_taxonomy  # noqa: E402
from eval_sets import refuse_confirmation_eval  # noqa: E402
from score_t5b_residual import (  # noqa: E402
    GOLD_HOLDOUT, GOLD_RISK, _init_waterfall, attach_waterfall, features_frame, scores_and_margin,
)
from train_classifier import TxnClassifier, load_taxonomy as load_tax_tensors  # noqa: E402
from pretrain_mlm import device  # noqa: E402

PIPELINE_EVAL = ROOT / "outputs" / "gold_pipeline_eval.csv"
DEFAULT_MODEL = ROOT / "outputs" / "distill_models" / "txn_classifier_gold"
DEFAULT_HINGE = ROOT / "outputs" / "distill_models" / "tfidf_linearsvm_sgd_v6_deleaked.joblib"
REPORT = ROOT / "data" / "transformer_classifier_report.md"
DETERMINISTIC = ("T1_", "T2_", "T3_", "T4_", "T5_")


def load_model(model_dir: pathlib.Path, dev):
    leaves, leaf_ix, gens, gen_ix, leaf_to_gen, credit_ok, debit_ok = load_tax_tensors()
    labels = json.loads((model_dir / "labels.json").read_text())
    assert labels["leaves"] == leaves, "taxonomy changed since training"
    tok = AutoTokenizer.from_pretrained(model_dir)
    model = TxnClassifier(model_dir, len(leaves), len(gens), leaf_to_gen, credit_ok, debit_ok)
    model.load_state_dict(torch.load(model_dir / "heads.pt", map_location="cpu"), strict=False)
    model.to(dev).eval()
    return tok, model, leaves


@torch.no_grad()
def predict(tok, model, leaves, df, dev, max_len=48, batch=256):
    texts = [sentence(d, amt_bucket_py(a), m, s) for d, a, m, s in
             zip(df["direction"].astype(str).str.lower(), df["amount"].fillna(0),
                 df["merchant_raw"].fillna(""), df["description_raw"].fillna(""))]
    is_credit = (df["direction"].astype(str).str.lower() == "credit").astype(int).to_numpy()
    preds, margins, probs = [], [], []
    for i in range(0, len(texts), batch):
        enc = tok(texts[i:i + batch], truncation=True, max_length=max_len, padding="longest", return_tensors="pt")
        logits, _ = model(enc["input_ids"].to(dev), enc["attention_mask"].to(dev),
                          torch.tensor(is_credit[i:i + batch], device=dev))
        top2 = torch.topk(logits, 2, dim=-1).values
        preds.extend(leaves[j] for j in logits.argmax(-1).tolist())
        margins.extend((top2[:, 0] - top2[:, 1]).tolist())
        probs.append(torch.softmax(logits.float(), dim=-1).cpu().numpy())
    predict.last_probs = np.concatenate(probs) if probs else np.zeros((0, len(leaves)))
    return np.array(preds, dtype=object), np.array(margins)


def hybrid_predict(t_probs, leaves, hinge, feat, w_t=0.5):
    """Average transformer softmax with a softmax over the hinge decision_function
    (aligned on leaf names; hinge classes are a subset). Memorisation + generalisation."""
    from distillation_bakeoff import featurise_for
    X = featurise_for(hinge, feat)
    clf = hinge["clf"]
    scores = clf.decision_function(X)
    scores = scores - scores.max(axis=1, keepdims=True)
    h = np.exp(scores); h /= h.sum(axis=1, keepdims=True)
    h_full = np.zeros_like(t_probs)
    ix = {l: i for i, l in enumerate(leaves)}
    for j, c in enumerate(clf.classes_):
        if c in ix:
            h_full[:, ix[c]] = h[:, j]
    p = w_t * t_probs + (1 - w_t) * h_full
    return np.array([leaves[i] for i in p.argmax(axis=1)], dtype=object)


def cpu_throughput(tok, model, leaves, df, n=2000):
    cpu_model = TxnClassifier.__new__(TxnClassifier)
    cpu_model.__dict__ = model.__dict__.copy()
    model_cpu = model.to(torch.device("cpu"))
    torch.set_num_threads(max(1, (__import__("os").cpu_count() or 2)))
    sub = df.head(n)
    predict(tok, model_cpu, leaves, sub.head(256), torch.device("cpu"), batch=256)  # warm-up
    t0 = time.time()
    predict(tok, model_cpu, leaves, sub, torch.device("cpu"), batch=512)
    dt = time.time() - t0
    return len(sub) / dt


def stats(gold, pred, direction, gen_of, risk_leaves):
    rows = [{"gold_leaf": g, "pred_leaf": p, "direction": d} for g, p, d in zip(gold, pred, direction)]
    a = analyse(rows, gen_of, risk_leaves)
    bd = a.get("by_direction") or {}
    return {
        "n": a["n"], "leaf": a["leaf_acc"], "gen": a["gen_acc"],
        "risk_n": a["risk_n"], "risk": a["risk_acc"],
        "credit_n": bd.get("credit", {}).get("n", 0), "credit": bd.get("credit", {}).get("leaf_acc"),
        "cbar_n": bd.get("credit_bar_n", 0), "cbar": bd.get("credit_bar_acc"),
    }


def pct(x):
    return "n/a" if x is None else f"{x:.1%}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", type=pathlib.Path, default=DEFAULT_MODEL)
    ap.add_argument("--hinge", type=pathlib.Path, default=DEFAULT_HINGE)
    ap.add_argument("--report", type=pathlib.Path, default=REPORT)
    args = ap.parse_args()
    for p in (GOLD_HOLDOUT, GOLD_RISK, PIPELINE_EVAL):
        refuse_confirmation_eval(p)

    dev = device()
    _init_waterfall()
    gen_of, risk_leaves = load_taxonomy()
    tok, model, leaves = load_model(args.model, dev)
    hinge = joblib.load(args.hinge)

    sets = []
    hold = pd.read_csv(GOLD_HOLDOUT)
    if "native_category" not in hold.columns:
        hold["native_category"] = np.nan
    if "provider" not in hold.columns:
        hold["provider"] = "plaid"
    sets.append(("holdout", attach_waterfall(hold).reset_index(drop=True)))
    risk = pd.read_csv(GOLD_RISK); risk["provider"] = "plaid"; risk["native_category"] = np.nan
    sets.append(("risk gold", attach_waterfall(risk).reset_index(drop=True)))
    pipe = pd.read_csv(PIPELINE_EVAL)
    sets.append(("pipeline eval", attach_waterfall(pipe).reset_index(drop=True)))

    rows = []
    out = {}
    for name, df in sets:
        gold = df["gold_leaf"].astype(str).to_numpy()
        direction = df["direction"].astype(str).str.lower().to_numpy()
        tier = df["waterfall_tier"].astype(str)
        resid = ~tier.str.startswith(DETERMINISTIC).to_numpy()
        wf = df["t6_leaf"].astype(str).to_numpy()
        tp, _ = predict(tok, model, leaves, df, dev)
        hp, _, _ = scores_and_margin(hinge, features_frame(df))
        yp = hybrid_predict(predict.last_probs, leaves, hinge, features_frame(df))
        for cut, mask in (("all (classifier only)", np.ones(len(df), bool)), ("T6-bound", resid)):
            for label, pred in (("hinge", hp), ("transformer", tp), ("hybrid 50/50", yp)):
                st = stats(gold[mask], pred[mask], direction[mask], gen_of, risk_leaves)
                rows.append({"set": name, "cut": cut, "model": label, **st})
                out[(name, cut, label)] = st
        if name == "pipeline eval":
            for label, pred in (("hinge", hp), ("transformer", tp), ("hybrid 50/50", yp)):
                full = np.where(resid, pred, wf)
                st = stats(gold, full, direction, gen_of, risk_leaves)
                rows.append({"set": name, "cut": "full pipeline T1–T5 then model", "model": label, **st})
                out[(name, "full", label)] = st

    thr = cpu_throughput(tok, model, leaves, sets[2][1])

    # kill criteria
    h_hold = out[("holdout", "T6-bound", "hinge")]; t_hold = out[("holdout", "T6-bound", "transformer")]
    h_res = out[("pipeline eval", "T6-bound", "hinge")]; t_res = out[("pipeline eval", "T6-bound", "transformer")]
    h_risk = out[("risk gold", "T6-bound", "hinge")]; t_risk = out[("risk gold", "T6-bound", "transformer")]
    h_cb = out[("pipeline eval", "T6-bound", "hinge")]; t_cb = out[("pipeline eval", "T6-bound", "transformer")]
    crit = [
        ("holdout T6-bound leaf ≥ hinge +3pp", t_hold["leaf"] - h_hold["leaf"] >= 0.03,
         f"{pct(t_hold['leaf'])} vs {pct(h_hold['leaf'])} (n={t_hold['n']})"),
        ("pipeline residual leaf ≥ hinge +3pp", t_res["leaf"] - h_res["leaf"] >= 0.03,
         f"{pct(t_res['leaf'])} vs {pct(h_res['leaf'])} (n={t_res['n']})"),
        ("T6-bound risk-leaf acc ≥ hinge", (t_risk["risk"] or 0) >= (h_risk["risk"] or 0),
         f"{pct(t_risk['risk'])} vs {pct(h_risk['risk'])} (n={t_risk['risk_n']})"),
        ("credit-side bar (pipeline residual) ≥ hinge +10pp",
         (t_cb["cbar"] or 0) - (h_cb["cbar"] or 0) >= 0.10,
         f"{pct(t_cb['cbar'])} vs {pct(h_cb['cbar'])} (n={t_cb['cbar_n']})"),
        ("CPU throughput ≥ 1,000 rows/s", thr >= 1000, f"{thr:,.0f} rows/s"),
    ]
    misses = sum(1 for _, ok, _ in crit if not ok)
    verdict = "KEEP HINGE (missed %d)" % misses if misses >= 2 else "PASS — candidate to replace T5b"
    y_hold = out[("holdout", "T6-bound", "hybrid 50/50")]; y_res = out[("pipeline eval", "T6-bound", "hybrid 50/50")]
    y_risk = out[("risk gold", "T6-bound", "hybrid 50/50")]
    crit_h = [
        ("hybrid: holdout T6-bound leaf ≥ hinge +3pp", y_hold["leaf"] - h_hold["leaf"] >= 0.03,
         f"{pct(y_hold['leaf'])} vs {pct(h_hold['leaf'])}"),
        ("hybrid: pipeline residual leaf ≥ hinge +3pp", y_res["leaf"] - h_res["leaf"] >= 0.03,
         f"{pct(y_res['leaf'])} vs {pct(h_res['leaf'])}"),
        ("hybrid: T6-bound risk-leaf acc ≥ hinge", (y_risk["risk"] or 0) >= (h_risk["risk"] or 0),
         f"{pct(y_risk['risk'])} vs {pct(h_risk['risk'])}"),
        ("hybrid: credit-side bar ≥ hinge +10pp", (y_res["cbar"] or 0) - (h_res["cbar"] or 0) >= 0.10,
         f"{pct(y_res['cbar'])} vs {pct(h_res['cbar'])}"),
    ]
    misses_h = sum(1 for _, ok, _ in crit_h if not ok)

    meta = json.loads((args.model / "train_meta.json").read_text()) if (args.model / "train_meta.json").exists() else {}
    lines = [
        f"# Transformer classifier vs de-leaked hinge — {time.strftime('%Y-%m-%d')}",
        "",
        f"Model `{args.model.resolve().relative_to(ROOT)}` (stage `{meta.get('stage')}`, encoder from `{meta.get('encoder_from', '?')}`, "
        f"{meta.get('rows', '?'):,} rows, {meta.get('epochs')} epochs). Hinge `{args.hinge.name}`. "
        "Same sentence format as pretraining; direction mask at the logits. Locked v5/v6 not scored.",
        "",
        "| set | cut | model | n | leaf | general | risk-leaf acc (n) | credit leaf (n) | credit-bar (n) |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        lines.append(f"| {r['set']} | {r['cut']} | {r['model']} | {r['n']} | {pct(r['leaf'])} | {pct(r['gen'])} | "
                     f"{pct(r['risk'])} ({r['risk_n']}) | {pct(r['credit'])} ({r['credit_n']}) | {pct(r['cbar'])} ({r['cbar_n']}) |")
    lines += ["", "## Kill criteria", "", "| criterion | result | detail |", "|---|---|---|"]
    for name, ok, detail in crit:
        lines.append(f"| {name} | {'PASS' if ok else 'MISS'} | {detail} |")
    for name, ok, detail in crit_h:
        lines.append(f"| {name} | {'PASS' if ok else 'MISS'} | {detail} |")
    lines += ["", f"**Verdict (transformer alone): {verdict}.** Hybrid misses {misses_h}/4 accuracy criteria "
              f"(throughput = transformer's, {thr:,.0f} rows/s).", ""]
    args.report.write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()

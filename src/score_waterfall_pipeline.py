"""Score T1–T5 then classifier then T6/T7 on one row-disjoint eval set.

Same merchants as training are allowed. Exact (merchant, description,
amount, direction) keys that appear in `outputs/tuning_train.jsonl` are
dropped. Locked v5/v6 are never included.

Usage:
    python src/score_waterfall_pipeline.py
"""
from __future__ import annotations

import csv
import json
import pathlib
import sys

import joblib
import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from confusion_analysis import load_taxonomy  # noqa: E402
from eval_sets import refuse_confirmation_eval  # noqa: E402
from score_t5b_residual import (  # noqa: E402
    GOLD_HOLDOUT,
    GOLD_RISK,
    GOLD_V3,
    GOLD_V4,
    HINGE_PATH,
    attach_waterfall,
    features_frame,
    scores_and_margin,
)
from score_t5b_residual import _init_waterfall  # noqa: E402

GOLD_UNIFIED = ROOT / "data" / "gold_transactions.csv"
TRAIN_JSONL = ROOT / "outputs" / "tuning_train.jsonl"
REPORT = ROOT / "data" / "waterfall_pipeline_report.md"
OUT_CSV = ROOT / "outputs" / "waterfall_pipeline_rows.csv"
EVAL_CSV = ROOT / "outputs" / "gold_pipeline_eval.csv"
LEAF_CSV = ROOT / "data" / "waterfall_residual_hinge_vs_t6_leaf.csv"
GEN_CSV = ROOT / "data" / "waterfall_residual_hinge_vs_t6_general.csv"

DETERMINISTIC_PREFIXES = ("T1_", "T2_", "T3_", "T4_", "T5_")


def _stage(tier: str) -> str:
    t = str(tier)
    if t.startswith(DETERMINISTIC_PREFIXES):
        return "T1-T5"
    if t.startswith("T7"):
        return "T7"
    return "T6"


def row_key(merchant, description, amount, direction):
    try:
        amt = round(abs(float(amount)), 4)
    except (TypeError, ValueError):
        amt = 0.0
    return (
        (merchant or "").strip().lower(),
        (description or "").strip().lower(),
        amt,
        (direction or "").strip().lower(),
    )


def load_train_jsonl(path=TRAIN_JSONL):
    if not path.exists():
        sys.exit(f"Need {path} to drop training rows from pipeline eval")
    keys = set()
    leaf_n = {}
    with open(path) as f:
        for line in f:
            ex = json.loads(line)
            user = next(m["content"] for m in ex["messages"] if m["role"] == "user")
            leaf = next(m["content"] for m in ex["messages"] if m["role"] == "assistant")
            leaf_n[leaf] = leaf_n.get(leaf, 0) + 1
            fields = {}
            for part in user.split("\n"):
                k, _, v = part.partition(": ")
                fields[k] = v
            keys.add(row_key(
                fields.get("merchant"), fields.get("description"),
                fields.get("amount"), fields.get("direction"),
            ))
    return keys, leaf_n


def leak_count(path, train_keys):
    n = hit = 0
    with open(path) as f:
        for r in csv.DictReader(f):
            n += 1
            if row_key(r["merchant_raw"], r.get("description_raw"), r["amount"], r["direction"]) in train_keys:
                hit += 1
    return n, hit


def load_pipeline_eval(train_keys):
    """Unified gold iter_eval + risk gold, minus training-row keys. Deduped."""
    refuse_confirmation_eval(GOLD_UNIFIED)
    refuse_confirmation_eval(GOLD_RISK)
    rows = []
    seen = set()

    def add(r, source, provider, native):
        k = row_key(r["merchant_raw"], r.get("description_raw"), r["amount"], r["direction"])
        if k in seen or k in train_keys:
            return
        seen.add(k)
        rows.append({
            "source": source,
            "merchant_raw": r["merchant_raw"],
            "description_raw": r.get("description_raw") or "",
            "amount": r["amount"],
            "direction": (r.get("direction") or "").strip().lower(),
            "provider": (provider or "plaid").strip().lower() or "plaid",
            "native_category": native or "",
            "gold_leaf": r["gold_leaf"],
        })

    with open(GOLD_UNIFIED) as f:
        for r in csv.DictReader(f):
            if r.get("role") == "train":
                continue
            add(r, f"unified_{r.get('source') or 'gold'}", r.get("provider"), r.get("native_category"))
    with open(GOLD_RISK) as f:
        for r in csv.DictReader(f):
            add(r, "risk", "plaid", "")
    return pd.DataFrame(rows)


def summarise(name, df, ml_pred, gen_of):
    gold = df["gold_leaf"].astype(str).to_numpy()
    wf = df["t6_leaf"].astype(str).to_numpy()
    tier = df["waterfall_tier"].astype(str).to_numpy()
    stage = np.array([_stage(t) for t in tier])
    n = len(df)
    det = stage == "T1-T5"
    residual = ~det
    pipe = np.where(det, wf, ml_pred)

    def acc(pred, mask=None):
        if mask is None:
            mask = np.ones(n, dtype=bool)
        m = int(mask.sum())
        if m == 0:
            return m, None, None
        leaf = float((pred[mask] == gold[mask]).mean())
        gen = float(np.mean([
            gen_of.get(p, "") == gen_of.get(g, "")
            for p, g in zip(pred[mask], gold[mask])
        ]))
        return m, leaf, gen

    table = []
    for label, pred, mask in (
        ("T1–T5 (when that tier fired)", wf, det),
        ("classifier on residual (T6/T7-bound)", ml_pred, residual),
        ("T6/T7 backup on residual", wf, residual),
        ("full pipeline: T1–T5 then hinge", pipe, None),
        ("rules-only waterfall (T1–T7, no ML)", wf, None),
    ):
        m, leaf, gen = acc(pred, mask)
        table.append({"set": name, "slice": label, "n": m, "leaf": leaf, "general": gen})

    by_tier = []
    for t, g in df.groupby(df["waterfall_tier"].astype(str), dropna=False):
        ok = float((g["t6_leaf"].astype(str) == g["gold_leaf"].astype(str)).mean())
        by_tier.append((str(t), len(g), ok))
    by_tier.sort(key=lambda x: -x[1])
    return table, by_tier, pipe


def fmt_pct(x):
    return "n/a" if x is None else f"{100 * x:.1f}%"


def residual_by_label(gold, hinge, t6, labels, train_n_of, label_col):
    """Recall vs gold label on T6-bound rows. train_n is jsonl count for that label."""
    rows = []
    for lab in sorted(set(labels)):
        mask = labels == lab
        n = int(mask.sum())
        hinge_ok = int((hinge[mask] == gold[mask]).sum())
        t6_ok = int((t6[mask] == gold[mask]).sum())
        h_acc = hinge_ok / n
        t_acc = t6_ok / n
        rows.append({
            label_col: lab,
            "n": n,
            "hinge_correct": hinge_ok,
            "t6_correct": t6_ok,
            "hinge_acc": h_acc,
            "t6_acc": t_acc,
            "t6_minus_hinge": t_acc - h_acc,
            "train_n": int(train_n_of.get(lab, 0)),
        })
    rows.sort(key=lambda r: (-r["t6_minus_hinge"], -r["n"], r[label_col]))
    return rows


def write_metric_csv(path, rows, label_col):
    fields = [label_col, "n", "hinge_correct", "t6_correct", "hinge_acc",
              "t6_acc", "t6_minus_hinge", "train_n"]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def md_class_table(lines, title, rows, label_col, min_n=1, t6_ahead_only=False):
    subset = [r for r in rows if r["n"] >= min_n]
    if t6_ahead_only:
        subset = [r for r in subset if r["t6_minus_hinge"] > 1e-12]
    lines.append(f"### {title}\n")
    if not subset:
        lines.append("None.\n")
        return
    lines.append(
        f"| `{label_col}` | n | hinge | T6 | T6−hinge | train jsonl |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|")
    for r in subset:
        lines.append(
            f"| `{r[label_col]}` | {r['n']} | {fmt_pct(r['hinge_acc'])} "
            f"({r['hinge_correct']}/{r['n']}) | {fmt_pct(r['t6_acc'])} "
            f"({r['t6_correct']}/{r['n']}) | {r['t6_minus_hinge']:+.1%} | {r['train_n']:,} |"
        )
    lines.append("")


def append_table(lines, title, n, table, by_tier):
    lines.append(f"## {title} (n={n})\n")
    lines.append("| Slice | n | leaf | general |")
    lines.append("|---|---:|---:|---:|")
    for r in table:
        lines.append(f"| {r['slice']} | {r['n']} | {fmt_pct(r['leaf'])} | {fmt_pct(r['general'])} |")
    lines.append("\nWaterfall tier mix (rules-only leaf, including T6/T7):\n")
    lines.append("| tier | n | rules-only leaf acc |")
    lines.append("|---|---:|---:|")
    for t, count, ok in by_tier:
        lines.append(f"| `{t}` | {count} | {fmt_pct(ok)} |")
    lines.append("")


def main():
    for path in (GOLD_UNIFIED, GOLD_RISK, GOLD_HOLDOUT, GOLD_V3, GOLD_V4):
        refuse_confirmation_eval(path)
    train_keys, train_leaf_n = load_train_jsonl()
    _init_waterfall()
    gen_of, _risk = load_taxonomy()
    hinge_path = HINGE_PATH
    if not hinge_path.exists():
        hinge_path = ROOT / "outputs" / "distill_models" / "tfidf_linearsvm_sgd_v5.joblib"
    bundle = joblib.load(hinge_path)

    df = load_pipeline_eval(train_keys)
    leaks = []
    for label, path in (
        ("holdout `gold_v2_slm_eval_holdout.csv`", GOLD_HOLDOUT),
        ("v3 volume `gold_transactions_v3_volume.csv`", GOLD_V3),
        ("v4 unmatched-Plaid `gold_transactions_v4_slm_volume.csv`", GOLD_V4),
        ("risk gold `gold_transactions_risk_categories.csv`", GOLD_RISK),
        ("unified `gold_transactions.csv`", GOLD_UNIFIED),
    ):
        n, hit = leak_count(path, train_keys)
        leaks.append((label, n, hit))

    df = attach_waterfall(df).reset_index(drop=True)
    feat = features_frame(df)
    ml_pred, _top, _margin = scores_and_margin(bundle, feat)
    table, by_tier, pipe = summarise("pipeline_eval", df, ml_pred, gen_of)

    residual = ~df["waterfall_tier"].astype(str).map(_stage).eq("T1-T5").to_numpy()
    gold = df["gold_leaf"].astype(str).to_numpy()
    t6 = df["t6_leaf"].astype(str).to_numpy()
    gold_g = np.array([gen_of.get(g, "") for g in gold])
    hinge_g = np.array([gen_of.get(p, "") for p in ml_pred])
    t6_g = np.array([gen_of.get(p, "") for p in t6])
    train_gen_n = {}
    for leaf, n in train_leaf_n.items():
        train_gen_n[gen_of.get(leaf, "")] = train_gen_n.get(gen_of.get(leaf, ""), 0) + n

    leaf_rows = residual_by_label(
        gold[residual], ml_pred[residual], t6[residual], gold[residual],
        train_leaf_n, "gold_leaf")
    gen_rows = residual_by_label(
        gold_g[residual], hinge_g[residual], t6_g[residual], gold_g[residual],
        train_gen_n, "gold_general")
    write_metric_csv(LEAF_CSV, leaf_rows, "gold_leaf")
    write_metric_csv(GEN_CSV, gen_rows, "gold_general")

    EVAL_CSV.parent.mkdir(exist_ok=True)
    df.drop(columns=["t6_leaf", "waterfall_tier", "is_t6"], errors="ignore").to_csv(EVAL_CSV, index=False)

    csv_out = []
    for i in range(len(df)):
        row = df.iloc[i]
        csv_out.append({
            "source": row["source"],
            "provider": row.get("provider", ""),
            "merchant_raw": row.get("merchant_raw", ""),
            "gold_leaf": row["gold_leaf"],
            "waterfall_leaf": row["t6_leaf"],
            "waterfall_tier": row["waterfall_tier"],
            "stage": _stage(row["waterfall_tier"]),
            "ml_leaf": ml_pred[i],
            "pipeline_leaf": pipe[i],
        })
    with open(OUT_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(csv_out[0].keys()))
        w.writeheader()
        w.writerows(csv_out)

    src_counts = df["source"].value_counts().to_dict()
    lines = [
        "# Full-pipeline accuracy (T1–T5 → classifier → T6/T7)",
        "",
        "One eval set: labelled transactions whose exact row is **not** in "
        "`outputs/tuning_train.jsonl`. Same merchants as training are allowed; "
        "locked v5/v6 are not included. Hinge SVM v5 on rows that miss T1–T5.",
        "",
        f"Classifier dump: `{hinge_path.relative_to(ROOT)}`.",
        f"Eval rows written to `{EVAL_CSV.relative_to(ROOT)}` ({len(df)} after dedupe).",
        "",
        "Composition: `gold_transactions.csv` `role=iter_eval` (v2/v3/v4 rows on "
        "holdout merchants) plus risk-gold rows that are not training keys.",
        "",
        "Source mix: " + ", ".join(f"{k} {v}" for k, v in sorted(src_counts.items(), key=lambda x: -x[1])),
        "",
    ]
    append_table(lines, "Pipeline eval (row-disjoint from training)", len(df), table, by_tier)

    n_res = int(residual.sum())
    n_t6_ahead = sum(1 for r in leaf_rows if r["t6_minus_hinge"] > 1e-12)
    n_t6_ahead_n3 = sum(1 for r in leaf_rows if r["n"] >= 3 and r["t6_minus_hinge"] > 1e-12)
    lines.append("## Hinge vs T6 on the residual, by category\n")
    lines.append(
        f"Same {n_res} T6-bound rows as the headline “rest” slices. "
        "Accuracy is **recall**: of rows whose gold label is this category, "
        "what share did each head get right. `train jsonl` is how many times "
        "that label appears in `tuning_train.jsonl` (leaf or rolled-up parent). "
        f"{n_t6_ahead} leaves have T6 ahead of hinge (any n); "
        f"{n_t6_ahead_n3} of those have n≥3. Full tables: "
        f"`{LEAF_CSV.relative_to(ROOT)}`, `{GEN_CSV.relative_to(ROOT)}`.\n"
    )
    md_class_table(
        lines,
        "Leaves where T6 beats hinge (n≥3) — train-top-up candidates",
        leaf_rows, "gold_leaf", min_n=3, t6_ahead_only=True)
    md_class_table(
        lines,
        "Leaves where T6 beats hinge (n=1–2, noisy)",
        [r for r in leaf_rows if r["n"] < 3], "gold_leaf",
        min_n=1, t6_ahead_only=True)
    md_class_table(
        lines,
        "Parents where T6 beats hinge (any n)",
        gen_rows, "gold_general", min_n=1, t6_ahead_only=True)
    md_class_table(
        lines,
        "All residual leaves with n≥5 (sorted T6−hinge)",
        leaf_rows, "gold_leaf", min_n=5, t6_ahead_only=False)

    lines.append("## Why the earlier three-file readout was not valid\n")
    lines.append(
        "The first pipeline pass scored v3 and v4 as if they were held-out traffic. "
        "Those files were merged into `gold_transactions.csv` as `role=train` and "
        "copied into the 382k jsonl, so the classifier (and Tier A labels) had "
        "already seen most of those **rows**. Merchant overlap is fine; row overlap is not.\n"
    )
    lines.append("| File | n | rows also in `tuning_train.jsonl` |")
    lines.append("|---|---:|---:|")
    for label, n, hit in leaks:
        lines.append(f"| {label} | {n} | {hit} ({100 * hit / n:.1f}%) |")
    lines.append(
        "\nHoldout is clean (0%). Do not quote the leaked v3/v4 full-pipeline "
        "leaf numbers (88.7% / 92.3%) as confirmation of residual accuracy.\n"
    )

    REPORT.write_text("\n".join(lines) + "\n")
    print(REPORT.read_text())
    print(f"Wrote {REPORT}, {LEAF_CSV}, {GEN_CSV}, {EVAL_CSV}, {OUT_CSV}", file=sys.stderr)


if __name__ == "__main__":
    main()

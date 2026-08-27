"""Cheap train/serve mismatch test.

Retrain SGD hinge on jsonl rows that miss T1–T5, plus a small per-leaf
prototype from the T4-covered head, so rare classes do not vanish.

Does **not** overwrite serving dumps (`tfidf_logreg_v2.joblib`,
`tfidf_linearsvm_sgd.joblib`). Does not score locked v5/v6.

Usage:
    python src/experiment_residual_prototype.py
"""
from __future__ import annotations

import json
import pathlib
import sys
import time
from collections import Counter, defaultdict

import joblib
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix, hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import SGDClassifier

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from confusion_analysis import analyse, load_taxonomy  # noqa: E402
from distillation_bakeoff import MODELS_DIR, OUT_DIR, SEED, build_text  # noqa: E402
from eval_sets import refuse_confirmation_eval  # noqa: E402
from final_evaluation import load_crosswalk, load_dictionary, load_rules, our_leaf  # noqa: E402
import final_evaluation as fe  # noqa: E402
from score_t5b_residual import (  # noqa: E402
    GOLD_HOLDOUT,
    GOLD_RISK,
    attach_waterfall,
    features_frame,
    scores_and_margin,
)

TRAIN_JSONL = OUT_DIR / "tuning_train.jsonl"
SLICE_JSONL = OUT_DIR / "tuning_train_residual_proto.jsonl"
DUMP = MODELS_DIR / "tfidf_linearsvm_sgd_residual_proto.joblib"
BASELINE = MODELS_DIR / "tfidf_linearsvm_sgd.joblib"
PIPELINE_EVAL = OUT_DIR / "gold_pipeline_eval.csv"
REPORT = ROOT / "data" / "residual_prototype_train_report.md"

PROTO_PER_LEAF = 20
DETERMINISTIC = ("T1_", "T2_", "T3_", "T4_", "T5_")


def _init_waterfall():
    fe.SUB_MAP, fe.PRI_MAP, fe.PLAID_MAP, _ = load_crosswalk()
    fe.DICTIONARY = load_dictionary()
    fe.RULES = load_rules()


def dummy_native(*_a, **_k):
    return "unclassified_other"


def parse_jsonl(path):
    rows = []
    with open(path) as f:
        for line in f:
            ex = json.loads(line)
            user = next(m["content"] for m in ex["messages"] if m["role"] == "user")
            leaf = next(m["content"] for m in ex["messages"] if m["role"] == "assistant")
            fields = {}
            for part in user.split("\n"):
                k, _, v = part.partition(": ")
                fields[k] = v
            merch = fields.get("merchant") or ""
            desc = fields.get("description") or ""
            direction = (fields.get("direction") or "").strip().lower()
            _leaf, tier = our_leaf(merch, direction, desc, dummy_native)
            caught = str(tier).startswith(DETERMINISTIC)
            rows.append({
                "vendor": merch,
                "description": desc,
                "amount": float(fields.get("amount") or 0),
                "is_credit": 1 if direction == "credit" else 0,
                "leaf": leaf,
                "tier": tier,
                "caught": caught,
                "raw_line": line,
            })
    return pd.DataFrame(rows)


def build_slice(df, rng):
    residual = df[~df["caught"]].copy()
    head = df[df["caught"]]
    proto_idx = []
    by_leaf = defaultdict(list)
    for i, leaf in zip(head.index, head["leaf"]):
        by_leaf[leaf].append(i)
    for leaf, idxs in by_leaf.items():
        take = min(PROTO_PER_LEAF, len(idxs))
        chosen = rng.choice(np.array(idxs), size=take, replace=False)
        proto_idx.extend(int(x) for x in chosen)
    proto = df.loc[proto_idx].copy() if proto_idx else df.iloc[0:0].copy()
    proto["source"] = "head_proto"
    residual["source"] = "t6_residual"
    out = pd.concat([residual, proto], ignore_index=True)
    out = out.iloc[rng.permutation(len(out))].reset_index(drop=True)
    return residual, proto, out


def write_slice_jsonl(out):
    with open(SLICE_JSONL, "w") as f:
        for line in out["raw_line"]:
            f.write(line if line.endswith("\n") else line + "\n")


def train_hinge(df):
    y = df["leaf"].to_numpy()
    text = build_text(df)
    num = np.column_stack([
        np.log1p(np.abs(df["amount"].to_numpy(dtype=np.float32))),
        df["is_credit"].to_numpy(dtype=np.float32),
    ])
    tv = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5),
                         max_features=30_000, min_df=2)
    X_text = tv.fit_transform(text)
    X = hstack([X_text, csr_matrix(num)], format="csr")
    clf = SGDClassifier(loss="hinge", alpha=1e-6, random_state=SEED,
                        tol=None, max_iter=50)
    t0 = time.time()
    clf.fit(X, y)
    elapsed = time.time() - t0
    bundle = {"vectorizer": tv, "clf": clf, "kind": "linearsvc",
              "train": "residual_proto"}
    MODELS_DIR.mkdir(exist_ok=True)
    joblib.dump(bundle, DUMP)
    return bundle, elapsed


def accs(gold, pred, gen_of, risk_leaves):
    rows = [{"gold_leaf": g, "pred_leaf": p} for g, p in zip(gold, pred)]
    return analyse(rows, gen_of, risk_leaves)


def fmt(a):
    risk = f"{a['risk_acc']:.1%}" if a["risk_acc"] is not None else "n/a"
    return f"leaf {a['leaf_acc']:.1%} / gen {a['gen_acc']:.1%} / risk {risk} (n={a['risk_n']})"


def score_df(name, gold_df, bundles, gen_of, risk_leaves):
    feat = features_frame(gold_df)
    gold = gold_df["gold_leaf"].to_numpy()
    out = {"name": name, "n": len(gold_df)}
    for label, bundle in bundles:
        pred, _, _ = scores_and_margin(bundle, feat)
        a = accs(gold, pred, gen_of, risk_leaves)
        out[label] = a
        print(f"  {label}: {fmt(a)}", file=sys.stderr)
    return out


def main():
    refuse_confirmation_eval(GOLD_HOLDOUT)
    refuse_confirmation_eval(GOLD_RISK)
    _init_waterfall()
    rng = np.random.default_rng(SEED)

    print(f"Loading {TRAIN_JSONL}...", file=sys.stderr)
    df = parse_jsonl(TRAIN_JSONL)
    n_caught = int(df["caught"].sum())
    residual, proto, slice_df = build_slice(df, rng)
    write_slice_jsonl(slice_df)
    print(
        f"{len(df)} jsonl rows: {n_caught} T1–T5 ({n_caught / len(df):.1%}), "
        f"{len(residual)} residual, {len(proto)} head prototypes "
        f"({proto['leaf'].nunique()} leaves), train slice {len(slice_df)} "
        f"({slice_df['leaf'].nunique()} classes)",
        file=sys.stderr,
    )
    residual_leaves = set(residual["leaf"])
    proto_only = sorted(set(proto["leaf"]) - residual_leaves)
    residual_only = sorted(residual_leaves - set(proto["leaf"]))
    print(f"Training residual+proto hinge...", file=sys.stderr)
    new_b, elapsed = train_hinge(slice_df)
    print(f"Wrote {DUMP} in {elapsed:.0f}s", file=sys.stderr)
    base_b = joblib.load(BASELINE)
    bundles = [("v5 hinge (serving)", base_b), ("residual+proto hinge", new_b)]
    gen_of, risk_leaves = load_taxonomy()

    holdout = pd.read_csv(GOLD_HOLDOUT)
    holdout = attach_waterfall(holdout)
    risk = pd.read_csv(GOLD_RISK)
    risk["provider"] = "plaid"
    risk["native_category"] = np.nan
    risk = attach_waterfall(risk)
    pipe = pd.read_csv(PIPELINE_EVAL)
    pipe = attach_waterfall(pipe)

    results = []
    cuts = [
        ("Holdout (all, merchant-disjoint)", holdout),
        ("Holdout T6-bound", holdout[holdout["is_t6"]].copy()),
        ("Risk gold (all)", risk),
        ("Risk gold T6-bound", risk[risk["is_t6"]].copy()),
        ("Pipeline eval residual (row-disjoint)", pipe[pipe["is_t6"]].copy()),
        ("Pipeline eval (all)", pipe),
    ]
    print("Scoring...", file=sys.stderr)
    for name, gdf in cuts:
        print(f"=== {name} n={len(gdf)} ===", file=sys.stderr)
        results.append(score_df(name, gdf, bundles, gen_of, risk_leaves))

    def pct_risk(a):
        return f"{a['risk_acc']:.1%}" if a["risk_acc"] is not None else "n/a"

    lines = [
        "# Residual + prototype hinge — cheap train/serve test (2026-08-27)\n",
        "Question: does dropping the ~95% of `tuning_train.jsonl` that T1–T5 "
        "already resolve, and keeping a small per-leaf prototype from that head, "
        "improve the hinge on the slice the classifier actually serves?\n",
        "Same architecture as v5 hinge (char-wb TF-IDF 2–5, 30k features, "
        f"SGD `loss='hinge'`, alpha=1e-6, 50 epochs). **Fresh** vocabulary on the "
        f"slice. Prototype = up to **{PROTO_PER_LEAF}** T1–T5-caught rows per leaf "
        f"(seed {SEED}). Serving dumps were not overwritten.\n",
        "## Training mix\n",
        f"| Slice | rows | classes |",
        f"|---|---:|---:|",
        f"| Full jsonl | {len(df):,} | {df['leaf'].nunique()} |",
        f"| T1–T5 caught (dropped, except prototypes) | {n_caught:,} | — |",
        f"| T6 residual (kept) | {len(residual):,} | {residual['leaf'].nunique()} |",
        f"| Head prototypes (kept) | {len(proto):,} | {proto['leaf'].nunique()} |",
        f"| **Train (residual + proto)** | **{len(slice_df):,}** | **{slice_df['leaf'].nunique()}** |",
        "",
        f"Fit wall-clock **{elapsed:.0f}s**. Dump: `{DUMP.relative_to(ROOT)}`. "
        f"Slice jsonl: `{SLICE_JSONL.relative_to(ROOT)}` (gitignored).",
        "",
        f"Leaves only in the prototype (zero residual examples): **{len(proto_only)}**. "
        f"Leaves only in residual (no head proto): **{len(residual_only)}**.\n",
        "## Scores vs serving v5 hinge\n",
        "Both heads scored with the same `scores_and_margin` path (gambling "
        "promote). Locked v5/v6 not scored.\n",
        "| Cut | n | v5 leaf | residual+proto leaf | Δ leaf | v5 gen | residual+proto gen | v5 risk | Δ risk |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in results:
        a, b = r["v5 hinge (serving)"], r["residual+proto hinge"]
        d_leaf = b["leaf_acc"] - a["leaf_acc"]
        d_risk = (
            f"{b['risk_acc'] - a['risk_acc']:+.1%}"
            if a["risk_acc"] is not None and b["risk_acc"] is not None
            else "n/a"
        )
        lines.append(
            f"| {r['name']} | {r['n']} | {a['leaf_acc']:.1%} | {b['leaf_acc']:.1%} | "
            f"{d_leaf:+.1%} | {a['gen_acc']:.1%} | {b['gen_acc']:.1%} | "
            f"{pct_risk(a)} | {d_risk} |"
        )

    ho_t6 = next(r for r in results if r["name"].startswith("Holdout T6"))
    pipe_r = next(r for r in results if "Pipeline eval residual" in r["name"])
    d_ho = (ho_t6["residual+proto hinge"]["leaf_acc"]
            - ho_t6["v5 hinge (serving)"]["leaf_acc"])
    d_pipe = (pipe_r["residual+proto hinge"]["leaf_acc"]
              - pipe_r["v5 hinge (serving)"]["leaf_acc"])
    if d_ho > 0.005 and d_pipe > 0.005:
        verdict = (
            "**Helps** on the serving residual. Worth a residual-weighted retrain "
            "on the full jsonl (downsample T4-covered rows) before buying more labels."
        )
    elif d_ho < -0.01 or d_pipe < -0.01:
        verdict = (
            "**Hurts** the serving residual relative to the head-heavy v5 hinge. "
            "The T4-covered rows are carrying transferable signal; do not throw "
            "them away. A 100k fall-through tranche is not justified on this test."
        )
    else:
        verdict = (
            "**Mostly flat** on the serving residual. Dropping the head does not "
            "unlock a better tail model with this architecture. A large residual "
            "labelling tranche is unlikely to beat simply keeping the current mix."
        )
    lines += [
        "",
        "## Verdict\n",
        verdict,
        "",
        "Money metrics are **holdout T6-bound** (novel merchants, leakage-free) and "
        "**pipeline residual** (row-disjoint gold that misses T1–T5). Full holdout "
        "and full risk gold include T4-covered rows the classifier would not serve.\n",
        "Do not switch serving dumps on this experiment.\n",
    ]
    REPORT.write_text("\n".join(lines) + "\n")
    print(REPORT.read_text())
    print(f"Wrote {REPORT}", file=sys.stderr)


if __name__ == "__main__":
    main()

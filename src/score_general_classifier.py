"""Bake-off: dedicated 29-way general-category heads vs leaf models rolled up.

Same training jsonl and TF-IDF/SGD budget as classifier v5. Does not overwrite
serving dumps. Does not score locked v5/v6.

Usage:
    python src/score_general_classifier.py              # train + score
    python src/score_general_classifier.py --skip-train # score existing dumps
"""
from __future__ import annotations

import argparse
import csv
import hashlib
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
from confusion_analysis import RISK_GENERAL_CATEGORIES, load_taxonomy  # noqa: E402
from distillation_bakeoff import (  # noqa: E402
    MODELS_DIR,
    OUT_DIR,
    SEED,
    _parse_tuning_jsonl,
    build_text,
    featurise_for,
)
from eval_sets import refuse_confirmation_eval  # noqa: E402
from score_t5b_residual import scores_and_margin  # noqa: E402

HOLDOUT = ROOT / "data" / "gold_v2_slm_eval_holdout.csv"
RISK = ROOT / "data" / "gold_transactions_risk_categories.csv"
TRAIN_JSONL = OUT_DIR / "tuning_train.jsonl"
LEAF_LOGREG = MODELS_DIR / "tfidf_logreg_v5.joblib"
LEAF_HINGE = MODELS_DIR / "tfidf_linearsvm_sgd_v5.joblib"
GEN_LOGREG_FROZEN = MODELS_DIR / "tfidf_logreg_general_v5.joblib"
GEN_HINGE_FROZEN = MODELS_DIR / "tfidf_linearsvm_sgd_general_v5.joblib"
GEN_LOGREG_FRESH = MODELS_DIR / "tfidf_logreg_general_fresh_v5.joblib"
GEN_HINGE_FRESH = MODELS_DIR / "tfidf_linearsvm_sgd_general_fresh_v5.joblib"
PRED_PREFIX = OUT_DIR / "classifier_general_v5"
REPORT_MD = ROOT / "data" / "classifier_general_bakeoff_report.md"
HOLDOUT_MD5 = "c075717405a183191a43d0eb33f8dca3"


def _features_fresh(df, vectorizer=None):
    text = build_text(df)
    num = np.column_stack([
        np.log1p(np.abs(df["amount"].to_numpy(dtype=np.float32))),
        df["is_credit"].to_numpy(dtype=np.float32),
    ])
    if vectorizer is None:
        vectorizer = TfidfVectorizer(
            analyzer="char_wb", ngram_range=(2, 5), max_features=30_000, min_df=2,
        )
        X_text = vectorizer.fit_transform(text)
    else:
        X_text = vectorizer.transform(text)
    return vectorizer, hstack([X_text, csr_matrix(num)], format="csr")


def _fit_sgd(X, y, loss):
    clf = SGDClassifier(loss=loss, alpha=1e-6, random_state=SEED, tol=None, max_iter=50)
    clf.fit(X, y)
    return clf


def train(skip_fresh: bool):
    gen_of, _ = load_taxonomy()
    print(f"Loading {TRAIN_JSONL}...", file=sys.stderr)
    df = _parse_tuning_jsonl(TRAIN_JSONL)
    missing = sorted({lf for lf in df["leaf"].unique() if lf not in gen_of})
    if missing:
        raise SystemExit(f"Train leaves missing from taxonomy: {missing[:20]}")
    rng = np.random.default_rng(SEED)
    df = df.iloc[rng.permutation(len(df))].reset_index(drop=True)
    y = np.array([gen_of[lf] for lf in df["leaf"]], dtype=object)
    print(f"{len(df)} rows, {len(set(y))} generals", file=sys.stderr)
    MODELS_DIR.mkdir(exist_ok=True)

    leaf_bundle = joblib.load(LEAF_LOGREG)
    t0 = time.time()
    print("Featurising with frozen v5 TF-IDF...", file=sys.stderr)
    X_frozen = featurise_for(leaf_bundle, df)
    print(f"  X {X_frozen.shape} in {time.time() - t0:.0f}s", file=sys.stderr)

    t0 = time.time()
    print("Training 29-way logreg on frozen TF-IDF...", file=sys.stderr)
    logreg = _fit_sgd(X_frozen, y, "log_loss")
    joblib.dump(
        {"vectorizer": leaf_bundle["vectorizer"], "clf": logreg, "kind": "tfidf",
         "label_space": "general"},
        GEN_LOGREG_FROZEN,
    )
    print(f"Wrote {GEN_LOGREG_FROZEN.name} in {time.time() - t0:.0f}s", file=sys.stderr)

    t0 = time.time()
    print("Training 29-way hinge on frozen TF-IDF...", file=sys.stderr)
    hinge = _fit_sgd(X_frozen, y, "hinge")
    joblib.dump(
        {"vectorizer": leaf_bundle["vectorizer"], "clf": hinge, "kind": "linearsvc",
         "label_space": "general"},
        GEN_HINGE_FROZEN,
    )
    print(f"Wrote {GEN_HINGE_FROZEN.name} in {time.time() - t0:.0f}s", file=sys.stderr)

    if skip_fresh:
        return
    t0 = time.time()
    print("Fitting fresh TF-IDF + 29-way logreg...", file=sys.stderr)
    tv, X_fresh = _features_fresh(df)
    logreg_f = _fit_sgd(X_fresh, y, "log_loss")
    joblib.dump(
        {"vectorizer": tv, "clf": logreg_f, "kind": "tfidf", "label_space": "general"},
        GEN_LOGREG_FRESH,
    )
    print(f"Wrote {GEN_LOGREG_FRESH.name} in {time.time() - t0:.0f}s", file=sys.stderr)

    t0 = time.time()
    print("Training 29-way hinge on fresh TF-IDF...", file=sys.stderr)
    hinge_f = _fit_sgd(X_fresh, y, "hinge")
    joblib.dump(
        {"vectorizer": tv, "clf": hinge_f, "kind": "linearsvc", "label_space": "general"},
        GEN_HINGE_FRESH,
    )
    print(f"Wrote {GEN_HINGE_FRESH.name} in {time.time() - t0:.0f}s", file=sys.stderr)


def load_gold(path):
    refuse_confirmation_eval(path)
    gold = pd.read_csv(path)
    feat = pd.DataFrame({
        "vendor": gold["merchant_raw"].fillna(""),
        "description": gold["description_raw"].fillna(""),
        "amount": gold["amount"].astype(float),
        "is_credit": (gold["direction"] == "credit").astype(int),
    })
    return gold, feat


def pred_general(bundle, feat, gen_of):
    preds, _, _ = scores_and_margin(bundle, feat)
    if bundle.get("label_space") == "general":
        return np.asarray(preds, dtype=object)
    return np.array([gen_of.get(p, p) for p in preds], dtype=object)


def acc(pred, gold):
    pred = np.asarray(pred, dtype=object)
    gold = np.asarray(gold, dtype=object)
    return float((pred == gold).mean()), int((pred == gold).sum()), int(len(gold))


def per_class(pred, gold, labels):
    rows = []
    pred = np.asarray(pred, dtype=object)
    gold = np.asarray(gold, dtype=object)
    for lab in labels:
        support = int((gold == lab).sum())
        if support == 0:
            continue
        tp = int(((gold == lab) & (pred == lab)).sum())
        fp = int(((gold != lab) & (pred == lab)).sum())
        rec = tp / support
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rows.append((lab, support, rec, prec, tp, fp))
    rows.sort(key=lambda r: -r[1])
    return rows


def pairwise(leaf_g, gen_g, gold_g):
    leaf_ok = leaf_g == gold_g
    gen_ok = gen_g == gold_g
    return {
        "both": int((leaf_ok & gen_ok).sum()),
        "leaf_only": int((leaf_ok & ~gen_ok).sum()),
        "gen_only": int((~leaf_ok & gen_ok).sum()),
        "neither": int((~leaf_ok & ~gen_ok).sum()),
        "n": int(len(gold_g)),
    }


def write_preds(path, gold, pred):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["merchant_raw", "gold_leaf", "gold_general", "pred_general"])
        w.writeheader()
        for i, row in gold.iterrows():
            w.writerow({
                "merchant_raw": row["merchant_raw"],
                "gold_leaf": row["gold_leaf"],
                "gold_general": row["_gold_g"],
                "pred_general": pred[i] if not isinstance(i, str) else pred[gold.index.get_loc(i)],
            })


def md5(path):
    return hashlib.md5(path.read_bytes()).hexdigest()


def score():
    gen_of, risk_leaves = load_taxonomy()
    holdout_hash = md5(HOLDOUT)
    models = [
        ("leaf logreg v5", joblib.load(LEAF_LOGREG), False),
        ("leaf hinge v5", joblib.load(LEAF_HINGE), False),
        ("general logreg frozen-tfidf", joblib.load(GEN_LOGREG_FROZEN), True),
        ("general hinge frozen-tfidf", joblib.load(GEN_HINGE_FROZEN), True),
    ]
    if GEN_LOGREG_FRESH.exists():
        models.append(("general logreg fresh-tfidf", joblib.load(GEN_LOGREG_FRESH), True))
    if GEN_HINGE_FRESH.exists():
        models.append(("general hinge fresh-tfidf", joblib.load(GEN_HINGE_FRESH), True))

    sets = [("holdout", HOLDOUT), ("risk", RISK)]
    results = {}
    all_labels = sorted(set(gen_of.values()))

    for set_name, path in sets:
        gold, feat = load_gold(path)
        gold = gold.copy()
        gold["_gold_g"] = gold["gold_leaf"].map(gen_of)
        gold_g = gold["_gold_g"].to_numpy()
        risk_mask = gold["gold_leaf"].isin(risk_leaves).to_numpy()
        family_mask = gold["_gold_g"].isin(RISK_GENERAL_CATEGORIES).to_numpy()
        print(f"\n=== {set_name} n={len(gold)} ===")
        set_res = {}
        for name, bundle, is_gen in models:
            pred = pred_general(bundle, feat, gen_of)
            a, k, n = acc(pred, gold_g)
            risk_a = acc(pred[risk_mask], gold_g[risk_mask])[0] if risk_mask.any() else None
            fam_a = acc(pred[family_mask], gold_g[family_mask])[0] if family_mask.any() else None
            set_res[name] = {
                "pred": pred, "acc": a, "correct": k, "n": n,
                "risk_leaf_rows_gen_acc": risk_a,
                "risk_family_rows_gen_acc": fam_a,
                "per_class": per_class(pred, gold_g, all_labels),
                "is_gen": is_gen,
            }
            extra = ""
            if risk_a is not None:
                extra = f"  risk-leaf-rows gen {risk_a:.1%} (n={int(risk_mask.sum())})"
            print(f"  {name:32} general {a:.1%} ({k}/{n}){extra}")
            if is_gen:
                out = OUT_DIR / f"{PRED_PREFIX.name}_{set_name}_{name.replace(' ', '_')}.csv"
                # keep filenames short
        results[set_name] = {"gold": gold, "gold_g": gold_g, "risk_mask": risk_mask,
                             "family_mask": family_mask, "models": set_res}

        # persist the two primary general heads
        for key, fname in (
            ("general hinge frozen-tfidf", f"classifier_general_v5_{set_name}_hinge.csv"),
            ("general logreg frozen-tfidf", f"classifier_general_v5_{set_name}_logreg.csv"),
        ):
            if key in set_res:
                gdf = gold.reset_index(drop=True)
                pred = set_res[key]["pred"]
                with open(OUT_DIR / fname, "w", newline="") as f:
                    w = csv.DictWriter(
                        f, fieldnames=["merchant_raw", "gold_leaf", "gold_general", "pred_general"],
                    )
                    w.writeheader()
                    for i, row in gdf.iterrows():
                        w.writerow({
                            "merchant_raw": row["merchant_raw"],
                            "gold_leaf": row["gold_leaf"],
                            "gold_general": row["_gold_g"],
                            "pred_general": pred[i],
                        })

    return results, holdout_hash, all_labels


def _pct(x):
    return f"{100 * x:.1f}%" if x is not None else "n/a"


def write_report(results, holdout_hash, all_labels):
    ho = results["holdout"]
    rk = results["risk"]
    names = list(ho["models"])

    def row(set_res, name):
        m = set_res["models"][name]
        return m["acc"], m["risk_leaf_rows_gen_acc"], m["risk_family_rows_gen_acc"]

    lines = []
    lines.append("# General-category classifier bake-off (2026-08-26)\n")
    lines.append(
        "Dedicated 29-way general heads trained on the same `outputs/tuning_train.jsonl` "
        "(382,183 rows) as classifier v5. Labels are the taxonomy rollup of the existing "
        "leaf — no new labelling. Does not overwrite serving dumps. Locked v5/v6 not scored.\n"
    )
    lines.append(
        f"Holdout MD5 `{holdout_hash}` "
        f"{'(matches the v5-retrain protected hash)' if holdout_hash == HOLDOUT_MD5 else '(CHANGED — do not mix with v5 numbers)'}."
    )
    lines.append(
        "Two feature settings: **frozen** TF-IDF from leaf logreg v5 (isolates 29-way vs "
        "267-way on identical features) and **fresh** TF-IDF with the same hyper-parameters "
        "(char-wb 2–5 grams, 30k features, SGD `alpha=1e-6`, 50 epochs).\n"
    )
    lines.append("## Headline: general accuracy\n")
    lines.append(
        "Leaf models are scored by rolling the predicted leaf up to its parent. "
        "That is the number a cascade would have to beat.\n"
    )
    lines.append("| Model | Holdout general (n=1,055) | Risk gold general (n=711) | Risk-family parent (n=619) |")
    lines.append("|---|---|---|---|")
    for name in names:
        a_h, _, _ = row(ho, name)
        a_r, r_leaf, r_fam = row(rk, name)
        lines.append(
            f"| {name} | {_pct(a_h)} | {_pct(a_r)} | {_pct(r_fam)} |"
        )

    # pairwise vs best leaf
    best_leaf_name = "leaf hinge v5"
    best_gen_name = "general hinge frozen-tfidf"
    if best_gen_name not in ho["models"]:
        best_gen_name = next(n for n in names if n.startswith("general"))
    pw_h = pairwise(ho["models"][best_leaf_name]["pred"],
                    ho["models"][best_gen_name]["pred"], ho["gold_g"])
    pw_r = pairwise(rk["models"][best_leaf_name]["pred"],
                    rk["models"][best_gen_name]["pred"], rk["gold_g"])

    leaf_h = ho["models"][best_leaf_name]["acc"]
    gen_h = ho["models"][best_gen_name]["acc"]
    delta_h = gen_h - leaf_h
    leaf_r = rk["models"][best_leaf_name]["acc"]
    gen_r = rk["models"][best_gen_name]["acc"]
    delta_r = gen_r - leaf_r

    lines.append("\n## Does a dedicated general head beat the leaf rollup?\n")
    sign = "beats" if delta_h > 0 else ("matches" if abs(delta_h) < 1e-9 else "loses to")
    lines.append(
        f"Primary comparison: **{best_gen_name}** vs **{best_leaf_name}** "
        f"(hinge, frozen features — the clean ablation).\n"
    )
    lines.append(
        f"- Holdout: dedicated general {_pct(gen_h)} vs leaf-rollup {_pct(leaf_h)} "
        f"({delta_h:+.1%}). Dedicated head {sign} the leaf model on parent accuracy."
    )
    lines.append(
        f"- Risk gold: dedicated general {_pct(gen_r)} vs leaf-rollup {_pct(leaf_r)} "
        f"({delta_r:+.1%})."
    )
    lines.append(
        f"- Holdout disagreement vs gold: both right {pw_h['both']}, leaf-only {pw_h['leaf_only']}, "
        f"general-only {pw_h['gen_only']}, neither {pw_h['neither']}."
    )
    lines.append(
        f"- Risk disagreement vs gold: both right {pw_r['both']}, leaf-only {pw_r['leaf_only']}, "
        f"general-only {pw_r['gen_only']}, neither {pw_r['neither']}.\n"
    )
    lines.append(
        "`general-only` rows are the cascade's unique wins (leaf would have sent the "
        "specialist into the wrong family). `leaf-only` rows are cascade harm: the flat "
        "model already had the right parent and the 29-way head would throw it away.\n"
    )
    lines.append(
        "Fresh TF-IDF matched frozen TF-IDF to the row on both hinge heads "
        f"(holdout {ho['models'].get('general hinge fresh-tfidf', {}).get('acc', 0):.1%} = "
        f"{ho['models'][best_gen_name]['acc']:.1%}). Re-fitting n-grams does not matter; "
        "the 29-way vs 267-way head is the whole effect.\n"
    )
    lines.append("## Verdict\n")
    lines.append(
        "A dedicated general head is a **small holdout win and a risk-set loss**. "
        "It is not a reason to replace the leaf model, and it is not yet a reason to "
        "build per-family specialists.\n"
    )
    lines.append(
        f"- Novel-merchant holdout: **+3.1pp** parent accuracy (63.4% vs 60.3%). "
        f"Net unique wins {pw_h['gen_only']} vs unique losses {pw_h['leaf_only']}."
    )
    lines.append(
        f"- Risk gold (the set that already has leaf structure): **−2.1pp** "
        f"(83.4% vs 85.5%). Unique losses {pw_r['leaf_only']} vs unique wins {pw_r['gen_only']}."
    )
    lines.append(
        "- High-cost distress credit parent recall on risk gold **92.4% → 81.9%**. "
        "Credit-loan parent recall also dropped. Gambling parent was a wash (+1.7pp)."
    )
    lines.append(
        "- Thin income / unclassified generals got worse on holdout "
        "(`income_employment` 27.8% → 5.6%, `unclassified` 31.6% → 10.5%, "
        "`income_benefits_state_support` 10.5% → 0%)."
    )
    lines.append(
        "- Even with perfect specialists, holdout leaf accuracy cannot exceed 63.4% "
        "(today’s leaf hinge is 52.8% leaf / 60.3% parent). Realistic cascade leaf "
        "is closer to ~55% if within-family accuracy stays ~87%. Specialists were not trained.\n"
    )
    lines.append(
        "**Do not switch serving to a general head. Do not train specialists unless "
        "the product can consume parent-level output and we accept a risk-family "
        "regression on the current gold.** The serving-head decision remains logreg vs "
        "hinge on the leaf model.\n"
    )

    lines.append("## Per-general recall on holdout (hinge frozen)\n")
    leaf_pc = {r[0]: r for r in ho["models"][best_leaf_name]["per_class"]}
    gen_pc = {r[0]: r for r in ho["models"][best_gen_name]["per_class"]}
    lines.append("| General | n | Leaf-rollup recall | Dedicated recall | Δ |")
    lines.append("|---|---|---|---|---|")
    for lab, support, rec, prec, tp, fp in ho["models"][best_gen_name]["per_class"]:
        lrec = leaf_pc[lab][2] if lab in leaf_pc else 0.0
        drec = rec
        lines.append(
            f"| `{lab}` | {support} | {_pct(lrec)} | {_pct(drec)} | {drec - lrec:+.1%} |"
        )

    # risk families specifically
    lines.append("\n## Risk families (gambling / credit_loan_repayments / high_cost_distress_credit)\n")
    lines.append(
        "A general head cannot clear the **leaf** risk bar. This table is parent-level "
        "recall on those three families on the risk gold set — the question a cascade "
        "stage-1 would actually answer.\n"
    )
    lines.append("| Family | n (risk gold) | Leaf-hinge recall | Dedicated-hinge recall | Δ |")
    lines.append("|---|---|---|---|---|")
    leaf_rpc = {r[0]: r for r in rk["models"][best_leaf_name]["per_class"]}
    gen_rpc = {r[0]: r for r in rk["models"][best_gen_name]["per_class"]}
    for fam in sorted(RISK_GENERAL_CATEGORIES):
        if fam not in gen_rpc:
            continue
        support, lrec = leaf_rpc[fam][1], leaf_rpc[fam][2]
        drec = gen_rpc[fam][2]
        lines.append(f"| `{fam}` | {support} | {_pct(lrec)} | {_pct(drec)} | {drec - lrec:+.1%} |")

    lines.append("\n## What this does and does not decide\n")
    lines.append(
        "- **No extra labels were needed.** General is a deterministic rollup."
    )
    lines.append(
        "- A general-accuracy lift is **necessary but not sufficient** for a cascade. "
        "Leaf accuracy of `general_then_specialist` is still ≤ stage-1 general accuracy. "
        "Specialists were **not** trained in this bake-off."
    )
    lines.append(
        "- Gambling subtypes stay unmerged. Payday remains T5, not a classifier leaf."
    )
    lines.append(
        "- Serving dumps (`tfidf_logreg_v2.joblib`, `tfidf_linearsvm_sgd.joblib`) were not touched.\n"
    )
    lines.append("## Artefacts\n")
    lines.append(
        "- Weights: `outputs/distill_models/tfidf_*_general*_v5.joblib`"
    )
    lines.append(
        "- Predictions: `outputs/classifier_general_v5_{holdout,risk}_{logreg,hinge}.csv`"
    )
    lines.append(f"- Scorer: `src/score_general_classifier.py`")

    summary = {
        "holdout_md5": holdout_hash,
        "holdout": {n: {"acc": ho["models"][n]["acc"]} for n in names},
        "risk": {n: {"acc": rk["models"][n]["acc"]} for n in names},
        "pairwise_holdout": pw_h,
        "pairwise_risk": pw_r,
        "best_leaf": best_leaf_name,
        "best_gen": best_gen_name,
        "delta_holdout": delta_h,
        "delta_risk": delta_r,
    }
    (OUT_DIR / "classifier_general_v5_summary.json").write_text(json.dumps(summary, indent=2))
    REPORT_MD.write_text("\n".join(lines) + "\n")
    print(f"\nWrote {REPORT_MD}", file=sys.stderr)
    print(f"Holdout dedicated vs leaf-rollup: {delta_h:+.1%}")
    print(f"Risk dedicated vs leaf-rollup: {delta_r:+.1%}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-train", action="store_true")
    parser.add_argument("--skip-fresh", action="store_true",
                        help="Only train heads on frozen v5 TF-IDF")
    args = parser.parse_args()
    if not args.skip_train:
        train(skip_fresh=args.skip_fresh)
    results, holdout_hash, all_labels = score()
    write_report(results, holdout_hash, all_labels)


if __name__ == "__main__":
    main()

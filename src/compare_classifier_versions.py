"""Score two TF-IDF classifier dumps on the same holdout + risk gold sets.

Does not touch locked confirmation sets (v5 retired; v6 scored once at go/no-go).

Usage:
    python src/compare_classifier_versions.py \\
        --old outputs/distill_models/tfidf_logreg_v4.joblib \\
        --new outputs/distill_models/tfidf_logreg_v5.joblib
"""
from __future__ import annotations

import argparse
import csv
import pathlib
import sys

import joblib
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from confusion_analysis import analyse, load_taxonomy  # noqa: E402
from eval_sets import refuse_confirmation_eval  # noqa: E402
from final_evaluation import load_rules, _rule_matches  # noqa: E402
from gating_experiment import load_crosswalk  # noqa: E402
from score_t5b_residual import scores_and_margin  # noqa: E402

_, _, _, GEN_OF, _ = load_crosswalk()
T5_RULES = load_rules()
HOLDOUT = ROOT / "data" / "gold_v2_slm_eval_holdout.csv"
RISK = ROOT / "data" / "gold_transactions_risk_categories.csv"
OUT = ROOT / "outputs"


def t5_leaf(merchant, description, direction):
    m = "" if merchant is None or (isinstance(merchant, float) and pd.isna(merchant)) else str(merchant).strip().lower()
    d = "" if description is None or (isinstance(description, float) and pd.isna(description)) else str(description).strip().lower()
    direction = "" if direction is None or (isinstance(direction, float) and pd.isna(direction)) else str(direction)
    for rule in T5_RULES:
        if _rule_matches(rule, m, d, direction):
            return rule["detailed_category"]
    return None


def load_gold(path):
    df_gold = pd.read_csv(path)
    df = pd.DataFrame({
        "vendor": df_gold["merchant_raw"].fillna(""),
        "description": df_gold["description_raw"].fillna(""),
        "amount": df_gold["amount"].astype(float),
        "is_credit": (df_gold["direction"] == "credit").astype(int),
    })
    return df_gold, df


def apply_t5(df_gold, preds):
    n = 0
    out = preds.copy()
    for i, row in df_gold.iterrows():
        ruled = t5_leaf(row["merchant_raw"], row["description_raw"], row["direction"])
        if ruled:
            out[i] = ruled
            n += 1
    return out, n


def metrics(df_gold, preds, gen_of, risk_leaves):
    rows = [{"gold_leaf": g, "pred_leaf": p}
            for g, p in zip(df_gold["gold_leaf"].tolist(), preds.tolist())]
    return analyse(rows, gen_of, risk_leaves)


def write_preds(path, df_gold, preds, confs):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["merchant_raw", "gold_leaf", "pred_leaf", "confidence"])
        w.writeheader()
        for i, row in df_gold.iterrows():
            w.writerow({
                "merchant_raw": row["merchant_raw"],
                "gold_leaf": row["gold_leaf"],
                "pred_leaf": preds[i],
                "confidence": confs[i],
            })


def fmt(a):
    risk = f"{a['risk_acc']:.1%}" if a["risk_acc"] is not None else "n/a"
    return f"leaf {a['leaf_acc']:.1%} / gen {a['gen_acc']:.1%} / risk {risk} (n={a['risk_n']})"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--old", required=True)
    parser.add_argument("--new", required=True)
    parser.add_argument("--old-name", default="v4 (tranche 3)")
    parser.add_argument("--new-name", default="v5 (tranche 4)")
    parser.add_argument("--out-prefix", default="classifier_v5",
                        help="Filename prefix under outputs/ for the --new model's predictions")
    args = parser.parse_args()
    refuse_confirmation_eval(HOLDOUT)
    refuse_confirmation_eval(RISK)

    gen_of, risk_leaves = load_taxonomy()
    old_b = joblib.load(args.old)
    new_b = joblib.load(args.new)

    sets = [
        ("holdout", HOLDOUT, f"{args.out_prefix}_holdout_predictions.csv"),
        ("risk", RISK, f"{args.out_prefix}_risk_predictions.csv"),
    ]

    print(f"old: {args.old}")
    print(f"new: {args.new}\n")
    for set_name, path, pred_name in sets:
        gold, feat = load_gold(path)
        print(f"=== {set_name} n={len(gold)} ===")
        for label, bundle, save in (
            (args.old_name, old_b, False),
            (args.new_name, new_b, True),
        ):
            preds, confs, _margin = scores_and_margin(bundle, feat)
            a = metrics(gold, preds, gen_of, risk_leaves)
            preds_t5, n_t5 = apply_t5(gold, preds)
            a_t5 = metrics(gold, preds_t5, gen_of, risk_leaves)
            print(f"  {label:22} clf     {fmt(a)}")
            print(f"  {label:22} clf+T5  {fmt(a_t5)}  (T5 overrode {n_t5})")
            if save:
                write_preds(OUT / pred_name, gold, preds_t5, confs)
                if set_name == "risk":
                    write_preds(OUT / pred_name.replace("predictions", "clf_predictions"),
                                gold, preds, confs)
        print()


if __name__ == "__main__":
    main()

"""Score the (retrained) TF-IDF classifier against the risk-category gold set
(data/gold_transactions_risk_categories.csv) -- the fresh eval this retrain
exists to be checked against, deliberately excluded from training. Also re-scores the
untouched gold_v2_slm_eval_holdout.csv for an apples-to-apples before/after
number against the documented 32.0% baseline.

Usage: python src/score_classifier_risk_categories.py
"""
import csv
import pathlib
import sys

import joblib
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from eval_sets import refuse_confirmation_eval  # noqa: E402
from distillation_bakeoff import predict, MODELS_DIR  # noqa: E402
from gating_experiment import load_crosswalk  # noqa: E402
from final_evaluation import load_rules, _rule_matches  # noqa: E402

_, _, _, gen_of, _ = load_crosswalk()
bundle = joblib.load(MODELS_DIR / "tfidf_logreg_v2.joblib")
T5_RULES = load_rules()


def t5_leaf(merchant, description, direction):
    m = "" if merchant is None or (isinstance(merchant, float) and pd.isna(merchant)) else str(merchant).strip().lower()
    d = "" if description is None or (isinstance(description, float) and pd.isna(description)) else str(description).strip().lower()
    direction = "" if direction is None or (isinstance(direction, float) and pd.isna(direction)) else str(direction)
    for rule in T5_RULES:
        if _rule_matches(rule, m, d, direction):
            return rule["detailed_category"]
    return None


def score(name, csv_path, out_path):
    refuse_confirmation_eval(csv_path)
    df_gold = pd.read_csv(csv_path)
    df = pd.DataFrame({
        "vendor": df_gold["merchant_raw"].fillna(""), "description": df_gold["description_raw"].fillna(""),
        "amount": df_gold["amount"].astype(float),
        "is_credit": (df_gold["direction"] == "credit").astype(int),
    })
    preds, confs = predict(bundle, df)
    n_t5 = 0
    for i, row in df_gold.iterrows():
        ruled = t5_leaf(row["merchant_raw"], row["description_raw"], row["direction"])
        if ruled:
            preds[i] = ruled
            n_t5 += 1
    leaf_ok = preds == df_gold["gold_leaf"].to_numpy()
    gen_ok = pd.Series(preds).map(gen_of).to_numpy() == df_gold["gold_leaf"].map(gen_of).to_numpy()

    print(f"=== {name} (n={len(df_gold)}) ===")
    print(f"Leaf accuracy:    {leaf_ok.mean():.1%}")
    print(f"General accuracy: {gen_ok.mean():.1%}")
    print(f"T5 rules overrode classifier on {n_t5} rows", file=sys.stderr)

    out_rows = []
    for i, row in df_gold.iterrows():
        out_rows.append({
            "merchant_raw": row["merchant_raw"], "gold_leaf": row["gold_leaf"],
            "pred_leaf": preds[i], "confidence": confs[i],
        })
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["merchant_raw", "gold_leaf", "pred_leaf", "confidence"])
        w.writeheader()
        w.writerows(out_rows)
    print(f"Predictions written to {out_path}\n")


OUT_DIR = ROOT / "outputs"
score("gold_v2_slm_eval_holdout (unchanged, before/after baseline)",
      ROOT / "data" / "gold_v2_slm_eval_holdout.csv", OUT_DIR / "classifier_v4_holdout_predictions.csv")
score("risk-category gold set (fresh, held out of this retrain)",
      ROOT / "data" / "gold_transactions_risk_categories.csv", OUT_DIR / "classifier_v4_risk_predictions.csv")

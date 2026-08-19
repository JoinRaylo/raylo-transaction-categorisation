"""Four-field ML baseline categoriser (CLAUDE.md sections 6/7).

Trains a fast linear classifier on Equifax's purpose-labelled transactions
using all four agreed fields -- merchant name, raw description, amount,
direction -- and evaluates it cross-domain on the two human-verified gold
strata (data/gold_merchant_labels.csv head set, data/gold_tail_labels.csv
tail set), voting transaction-level predictions up to merchant level.

Known bias, by construction: the classifier learns Equifax's conventions, so
it should look strong on head-set rows whose gold label came from all-three-
agree consensus and weaker on rows the human adjudicated AGAINST Equifax.
`evaluate` reports the split so the bias is visible rather than hidden.

Usage:
    python src/ml_baseline.py fetch-train    # Equifax stratified sample -> outputs/ml_train.parquet
    python src/ml_baseline.py fetch-eval     # Plaid txns for gold merchants -> outputs/ml_eval_txns.parquet
    python src/ml_baseline.py train          # -> outputs/ml_baseline.joblib
    python src/ml_baseline.py evaluate       # score vs both gold strata
"""
import pathlib
import sys

import numpy as np
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from gating_experiment import ROOT, OUT_DIR, MECH_PRIMARIES, load_crosswalk  # noqa: E402

TRAIN_PARQUET = OUT_DIR / "ml_train.parquet"
EVAL_PARQUET = OUT_DIR / "ml_eval_txns.parquet"
MODEL_JOBLIB = OUT_DIR / "ml_baseline.joblib"
GOLD_HEAD = ROOT / "data" / "gold_merchant_labels.csv"
GOLD_TAIL = ROOT / "data" / "gold_tail_labels.csv"
REPORT_MD = ROOT / "data" / "ml_baseline_report.md"

CAP_PER_SUB = 12000  # per-subcategory sampling cap flattens class imbalance
SEED = 42


def bq_client():
    from google.cloud import bigquery
    return bigquery.Client(project="raylo-production")


def fetch_train():
    sub_map, _, _, _, _ = load_crosswalk()
    mech = ", ".join(f"'{p}'" for p in MECH_PRIMARIES)
    query = f"""
    SELECT Description AS description,
           IFNULL(VendorDescription, '') AS vendor,
           Amount AS amount,
           TransactionTypeId AS ttype,
           SubCategoryDescription AS sub
    FROM `raylo-production.equifax_data.open_banking_full_dump`
    WHERE SubCategoryDescription IS NOT NULL
      AND Description IS NOT NULL AND TRIM(Description) != ''
      AND PrimaryCategoryDescription NOT IN ({mech})
    QUALIFY ROW_NUMBER() OVER (PARTITION BY SubCategoryDescription ORDER BY RAND()) <= {CAP_PER_SUB}
    """
    print("Pulling stratified Equifax training sample (this downloads a few GB)...", file=sys.stderr)
    df = bq_client().query(query).result().to_dataframe()
    print(f"{len(df)} rows fetched across {df['sub'].nunique()} subcategories", file=sys.stderr)
    df["leaf"] = df["sub"].map(sub_map)
    df = df.dropna(subset=["leaf"])
    df["is_credit"] = (df["ttype"] == 1).astype(np.int8)
    df["amount"] = df["amount"].abs().astype(np.float32)
    df = df[["description", "vendor", "amount", "is_credit", "leaf"]]
    df.to_parquet(TRAIN_PARQUET, index=False)
    print(f"Wrote {TRAIN_PARQUET}: {len(df)} rows, {df['leaf'].nunique()} leaves", file=sys.stderr)


def fetch_eval():
    merchants = list(pd.read_csv(GOLD_HEAD)["merchant"]) + list(pd.read_csv(GOLD_TAIL)["merchant"])
    merchants = sorted(set(m.strip().lower() for m in merchants))
    def q(s):
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    in_list = ", ".join(q(m) for m in merchants)
    query = f"""
    SELECT LOWER(TRIM(merchant_name)) AS merchant,
           IFNULL(COALESCE(original_description, transaction_name), '') AS description,
           IFNULL(merchant_name, '') AS vendor,
           ABS(amount) AS amount,
           CAST(amount < 0 AS INT64) AS is_credit
    FROM `raylo-production.dbt_production.credit_plaid_open_banking_transactions`
    WHERE merchant_name IS NOT NULL AND TRIM(merchant_name) != ''
      AND LOWER(TRIM(merchant_name)) IN ({in_list})
    QUALIFY ROW_NUMBER() OVER (PARTITION BY LOWER(TRIM(merchant_name)) ORDER BY RAND()) <= 40
    """
    print(f"Pulling Plaid transactions for {len(merchants)} gold merchants...", file=sys.stderr)
    df = bq_client().query(query).result().to_dataframe()
    df["amount"] = df["amount"].astype(np.float32)
    df["is_credit"] = df["is_credit"].astype(np.int8)
    df.to_parquet(EVAL_PARQUET, index=False)
    print(f"Wrote {EVAL_PARQUET}: {len(df)} txns for {df['merchant'].nunique()} merchants", file=sys.stderr)


def featurise(vectorizer, df):
    from scipy.sparse import csr_matrix, hstack
    text = (df["vendor"].fillna("") + " | " + df["description"].fillna("")).str.lower()
    X_text = vectorizer.transform(text)
    num = np.column_stack([
        np.log1p(df["amount"].to_numpy(dtype=np.float32)),
        df["is_credit"].to_numpy(dtype=np.float32),
    ])
    return hstack([X_text, csr_matrix(num)], format="csr")


def train():
    import joblib
    from sklearn.feature_extraction.text import HashingVectorizer
    from sklearn.linear_model import SGDClassifier

    df = pd.read_parquet(TRAIN_PARQUET)
    rng = np.random.default_rng(SEED)
    df = df.iloc[rng.permutation(len(df))].reset_index(drop=True)
    classes = np.array(sorted(df["leaf"].unique()))
    print(f"Training on {len(df)} rows, {len(classes)} classes", file=sys.stderr)

    vectorizer = HashingVectorizer(analyzer="char_wb", ngram_range=(2, 5),
                                   n_features=2 ** 20, alternate_sign=False, norm="l2")
    clf = SGDClassifier(loss="log_loss", alpha=1e-6, random_state=SEED, tol=None)

    chunk = 200_000
    for epoch in range(2):
        for i in range(0, len(df), chunk):
            part = df.iloc[i:i + chunk]
            X = featurise(vectorizer, part)
            clf.partial_fit(X, part["leaf"].to_numpy(), classes=classes)
            print(f"  epoch {epoch + 1}: {min(i + chunk, len(df))}/{len(df)}", file=sys.stderr)

    joblib.dump({"vectorizer": vectorizer, "clf": clf}, MODEL_JOBLIB)
    print(f"Wrote {MODEL_JOBLIB}", file=sys.stderr)


def evaluate():
    import joblib
    from collections import Counter

    _, _, _, gen_of, _ = load_crosswalk()
    bundle = joblib.load(MODEL_JOBLIB)
    vectorizer, clf = bundle["vectorizer"], bundle["clf"]

    txns = pd.read_parquet(EVAL_PARQUET)
    X = featurise(vectorizer, txns)
    txns["pred"] = clf.predict(X)
    # modal transaction-level prediction per merchant string
    merchant_pred = txns.groupby("merchant")["pred"].agg(lambda s: Counter(s).most_common(1)[0][0])

    lines = ["# Four-field ML baseline -- evaluation against the gold strata\n"]
    lines.append(f"Trained on {CAP_PER_SUB}-per-subcategory Equifax sample; evaluated on Plaid "
                 f"transactions ({len(txns)} txns), modal-voted per merchant.\n")

    def score(df, label, group_col=None):
        df = df.copy()
        df["merchant"] = df["merchant"].str.strip().str.lower()
        df["pred"] = df["merchant"].map(merchant_pred)
        df = df.dropna(subset=["pred"])
        alt = df["alt_leaf"].fillna("") if "alt_leaf" in df.columns else pd.Series("", index=df.index)
        df["leaf_ok"] = (df["pred"] == df["gold_leaf"]) | ((alt != "") & (df["pred"] == alt))
        df["gen_ok"] = df["leaf_ok"] | (df["pred"].map(gen_of) == df["gold_leaf"].map(gen_of))
        lines.append(f"## {label} ({len(df)} merchants with Plaid transactions found)")
        lines.append("| group | n | leaf | general |")
        lines.append("|---|---|---|---|")
        groups = [("ALL", df)]
        if group_col:
            groups += [(g, d) for g, d in df.groupby(group_col)]
        for g, d in groups:
            lines.append(f"| {g} | {len(d)} | {d['leaf_ok'].mean():.0%} | {d['gen_ok'].mean():.0%} |")
        lines.append("")

    score(pd.read_csv(GOLD_HEAD), "Head gold set (shared merchants)", group_col="gold_source")
    score(pd.read_csv(GOLD_TAIL), "Tail gold set (unmatched population)", group_col="stratum")

    lines.append("## Reference: enriched-LLM numbers on the same sets")
    lines.append("Sonnet 5 head consensus subset: 96.1% leaf (adjudication-corrected). "
                 "Sonnet 5 tail: 76% leaf / 83% general overall, 90% leaf on top_volume.")
    report = "\n".join(lines)
    REPORT_MD.write_text(report)
    print(report)


if __name__ == "__main__":
    cmds = {"fetch-train": fetch_train, "fetch-eval": fetch_eval, "train": train, "evaluate": evaluate}
    args = sys.argv[1:]
    if not args or args[0] not in cmds:
        sys.exit(__doc__)
    cmds[args[0]]()

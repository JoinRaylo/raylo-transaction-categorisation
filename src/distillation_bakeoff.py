"""Distillation model bake-off (CLAUDE.md section 6/7 follow-on).

The ml_baseline.py experiment proved distilling from Equifax labels fails
(69% head / 30% tail, 10% on rows adjudicated against Equifax conventions).
This script re-runs the distillation from the RIGHT label source -- the
accepted production vocabulary labels (LLM-consensus + human-reviewed,
Plaid-native) -- and bakes off three candidate architectures on identical,
per-TRANSACTION training data (not merchant-level modal votes):

  A. control       -- same architecture as ml_baseline.py (hashed char
                      n-grams, SGD log-loss), only the label source changes.
                      Isolates "did fixing the label source help".
  B. tfidf_logreg  -- bounded, inspectable TF-IDF vocabulary + SGD log-loss.
                      Same optimizer as A; only the feature representation
                      changes -- isolates "does a real vocabulary beat hashing".
                      Coefficients are auditable (top n-grams per leaf).
  C. lightgbm      -- same TF-IDF features + LightGBM multiclass. Can learn
                      text x amount x direction interactions a linear model
                      can't (the McDonald's example: same text, different
                      amount -> different leaf).

Training text is merchant_name + original_description PER TRANSACTION from
Plaid directly -- not Equifax fields -- so training input matches serving
input exactly (the domain-mismatch fix identified after the baseline).

Usage:
    python src/distillation_bakeoff.py fetch-train   # accepted-label Plaid txns -> parquet
    python src/distillation_bakeoff.py train           # trains all 3 candidates
    python src/distillation_bakeoff.py evaluate        # scores all 3 on both gold sets
"""
import pathlib
import sys

import numpy as np
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from gating_experiment import ROOT, OUT_DIR, load_crosswalk  # noqa: E402
from ml_baseline import bq_client, GOLD_HEAD, GOLD_TAIL, EVAL_PARQUET  # noqa: E402

TRAIN_PARQUET = OUT_DIR / "distill_train.parquet"
MODELS_DIR = OUT_DIR / "distill_models"
REPORT_MD = ROOT / "data" / "distillation_bakeoff_report.md"

CAP_PER_MERCHANT = 150  # per-merchant cap so high-volume merchants don't dominate
SEED = 42
ACCEPTED_TIERS = {"auto_accept", "accepted", "accepted_tiebreak", "accepted_general", "human_reviewed"}

# Every closed production_labels_trancheN.csv snapshot in data/ -- always use
# the LATEST tranche file (it's a full union, not incremental).
LATEST_LABELS = sorted(
    (ROOT / "data").glob("production_labels_tranche*.csv"),
    key=lambda p: int(p.stem.rsplit("tranche", 1)[1]),
)[-1]


def fetch_train():
    labels = pd.read_csv(LATEST_LABELS)
    labels = labels[labels["tier"].isin(ACCEPTED_TIERS)]
    print(f"Using {LATEST_LABELS.name}: {len(labels)} accepted merchants across "
          f"{labels['final_leaf'].nunique()} leaves", file=sys.stderr)

    def q(s):
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    merchants = sorted(labels["merchant"].astype(str))
    client = bq_client()
    CHUNK = 2000
    frames = []
    for i in range(0, len(merchants), CHUNK):
        part = merchants[i:i + CHUNK]
        in_list = ", ".join(q(m) for m in part)
        print(f"Fetching transactions chunk {i // CHUNK + 1}/{(len(merchants) + CHUNK - 1) // CHUNK}...",
              file=sys.stderr)
        query = f"""
        SELECT LOWER(TRIM(merchant_name)) AS merchant,
               IFNULL(merchant_name, '') AS vendor,
               IFNULL(COALESCE(original_description, transaction_name), '') AS description,
               ABS(amount) AS amount,
               CAST(amount < 0 AS INT64) AS is_credit
        FROM `raylo-production.dbt_production.credit_plaid_open_banking_transactions`
        WHERE merchant_name IS NOT NULL AND TRIM(merchant_name) != ''
          AND LOWER(TRIM(merchant_name)) IN ({in_list})
        QUALIFY ROW_NUMBER() OVER (PARTITION BY LOWER(TRIM(merchant_name)) ORDER BY RAND()) <= {CAP_PER_MERCHANT}
        """
        frames.append(client.query(query).result().to_dataframe())
    df = pd.concat(frames, ignore_index=True)

    label_map = dict(zip(labels["merchant"].astype(str), labels["final_leaf"]))
    df["leaf"] = df["merchant"].map(label_map)
    df = df.dropna(subset=["leaf"])
    df["amount"] = df["amount"].astype(np.float32)
    df["is_credit"] = df["is_credit"].astype(np.int8)
    df.to_parquet(TRAIN_PARQUET, index=False)
    print(f"Wrote {TRAIN_PARQUET}: {len(df)} transaction-level rows, "
          f"{df['merchant'].nunique()} merchants, {df['leaf'].nunique()} leaves", file=sys.stderr)


def build_text(df):
    return (df["vendor"].fillna("") + " | " + df["description"].fillna("")).str.lower()


def train():
    import joblib
    from scipy.sparse import csr_matrix, hstack
    from sklearn.feature_extraction.text import HashingVectorizer, TfidfVectorizer
    from sklearn.linear_model import SGDClassifier

    MODELS_DIR.mkdir(exist_ok=True)
    df = pd.read_parquet(TRAIN_PARQUET)
    rng = np.random.default_rng(SEED)
    df = df.iloc[rng.permutation(len(df))].reset_index(drop=True)
    text = build_text(df)
    y = df["leaf"].to_numpy()
    classes = np.array(sorted(df["leaf"].unique()))
    num = np.column_stack([np.log1p(df["amount"].to_numpy(dtype=np.float32)),
                          df["is_credit"].to_numpy(dtype=np.float32)])
    print(f"Training on {len(df)} rows, {len(classes)} classes", file=sys.stderr)

    # --- A. control: hashed n-grams + SGD (same architecture as ml_baseline.py)
    print("Training A. control (hashed n-grams + SGD)...", file=sys.stderr)
    hv = HashingVectorizer(analyzer="char_wb", ngram_range=(2, 5),
                          n_features=2 ** 20, alternate_sign=False, norm="l2")
    X_hash = hstack([hv.transform(text), csr_matrix(num)], format="csr")
    clf_a = SGDClassifier(loss="log_loss", alpha=1e-6, random_state=SEED, tol=None, max_iter=50)
    clf_a.fit(X_hash, y)
    joblib.dump({"vectorizer": hv, "clf": clf_a, "kind": "hash"}, MODELS_DIR / "control.joblib")

    # --- B. tfidf_logreg: bounded vocabulary + SGD (same optimizer as A)
    print("Training B. tfidf_logreg (bounded TF-IDF + SGD)...", file=sys.stderr)
    tv = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), max_features=30_000, min_df=2)
    X_text = tv.fit_transform(text)
    X_tfidf = hstack([X_text, csr_matrix(num)], format="csr")
    clf_b = SGDClassifier(loss="log_loss", alpha=1e-6, random_state=SEED, tol=None, max_iter=50)
    clf_b.fit(X_tfidf, y)
    joblib.dump({"vectorizer": tv, "clf": clf_b, "kind": "tfidf"}, MODELS_DIR / "tfidf_logreg.joblib")

    print("A + B trained. Run `retrain-lightgbm` separately for C (needs the fix below).", file=sys.stderr)


def retrain_lightgbm():
    """C. lightgbm, attempt 3.

    Attempt 1 collapsed to ~1 predicted class (11% TRAINING accuracy) --
    unweighted multiclass loss on data where one class is 36.4% of rows.
    Attempt 2 fixed the collapse with class_weight='balanced' but that
    computes RAW inverse-frequency weights: with several classes under 10
    rows against a 188,893-row majority class, the max/min weight ratio
    exceeds 30,000x. Validation loss exploded 10x within 10 rounds (best
    iteration = 1) -- the loss surface was numerically unstable, not just
    slow to converge.

    Attempt 3 targets that specific cause: sqrt-dampened, ratio-CAPPED
    sample weights (cuts the 30,000x spread to <=100x) instead of raw
    inverse frequency, a much smaller learning rate so steps can't
    overshoot even with residual imbalance, added L1/L2 regularization,
    and early-stopping patience widened to match the slower learning rate.
    Same TF-IDF features as B (already-fitted vectorizer, no re-fit) so
    architecture remains the only variable versus B."""
    import joblib
    import lightgbm as lgb
    from collections import Counter
    from scipy.sparse import csr_matrix, hstack
    from sklearn.model_selection import train_test_split

    df = pd.read_parquet(TRAIN_PARQUET)
    rng = np.random.default_rng(SEED)
    df = df.iloc[rng.permutation(len(df))].reset_index(drop=True)
    y = df["leaf"].to_numpy()
    classes = np.array(sorted(df["leaf"].unique()))
    y_idx = np.searchsorted(classes, y)

    b_bundle = joblib.load(MODELS_DIR / "tfidf_logreg.joblib")
    tv = b_bundle["vectorizer"]
    print("Vectorizing with B's already-fitted TF-IDF (no re-fit needed)...", file=sys.stderr)
    text = build_text(df)
    X_text = tv.transform(text)
    num = np.column_stack([np.log1p(df["amount"].to_numpy(dtype=np.float32)),
                          df["is_credit"].to_numpy(dtype=np.float32)])
    X_tfidf = hstack([X_text, csr_matrix(num)], format="csr")

    counts = Counter(y_idx)
    n_total, n_classes = len(y_idx), len(classes)
    raw_w = {c: n_total / (n_classes * n) for c, n in counts.items()}
    sqrt_w = {c: w ** 0.5 for c, w in raw_w.items()}
    cap = min(sqrt_w.values()) * 100  # hard cap: at most 100x the smallest weight
    capped_w = {c: min(w, cap) for c, w in sqrt_w.items()}
    print(f"Sample weight range before cap: {min(sqrt_w.values()):.3f}-{max(sqrt_w.values()):.3f} "
          f"({max(sqrt_w.values())/min(sqrt_w.values()):.0f}x) -> after cap: "
          f"{min(capped_w.values()):.3f}-{max(capped_w.values()):.3f} "
          f"({max(capped_w.values())/min(capped_w.values()):.0f}x)", file=sys.stderr)
    sample_weight = np.array([capped_w[c] for c in y_idx])

    X_train, X_val, y_train, y_val, w_train, w_val = train_test_split(
        X_tfidf, y_idx, sample_weight, test_size=0.1, random_state=SEED)

    print(f"Training C. lightgbm attempt 3 (capped sample weights, lr=0.03, "
          f"reg, {X_train.shape[0]} train / {X_val.shape[0]} val rows)...", file=sys.stderr)
    clf_c = lgb.LGBMClassifier(
        objective="multiclass", num_class=len(classes),
        n_estimators=600, num_leaves=31, learning_rate=0.03,
        min_child_samples=5, reg_alpha=1.0, reg_lambda=1.0,
        random_state=SEED, verbosity=-1, n_jobs=-1,
    )
    clf_c.fit(
        X_train, y_train, sample_weight=w_train,
        eval_set=[(X_val, y_val)], eval_sample_weight=[w_val],
        callbacks=[lgb.early_stopping(stopping_rounds=30), lgb.log_evaluation(period=20)],
    )
    print(f"Stopped at {clf_c.best_iteration_} rounds (of 600 max)", file=sys.stderr)
    joblib.dump({"vectorizer": tv, "clf": clf_c, "classes": classes, "kind": "lgbm"},
               MODELS_DIR / "lightgbm.joblib")
    print("lightgbm retrained (attempt 3).", file=sys.stderr)


def _parse_tuning_jsonl(path):
    """Parse outputs/tuning_{train,val}.jsonl (chat format, produced by
    build_tuning_dataset.py) back into the vendor/description/amount/is_credit/leaf
    columns this script's feature pipeline expects."""
    import json
    rows = []
    with open(path) as f:
        for line in f:
            ex = json.loads(line)
            user_msg = next(m["content"] for m in ex["messages"] if m["role"] == "user")
            leaf = next(m["content"] for m in ex["messages"] if m["role"] == "assistant")
            fields = {}
            for part in user_msg.split("\n"):
                k, _, v = part.partition(": ")
                fields[k] = v
            rows.append({
                "vendor": fields.get("merchant", ""), "description": fields.get("description", ""),
                "amount": float(fields.get("amount", 0) or 0),
                "is_credit": 1 if fields.get("direction") == "credit" else 0,
                "leaf": leaf,
            })
    return pd.DataFrame(rows)


def train_v2():
    """Retrain B (tfidf_logreg, the architecture adopted from the original bake-off)
    on the new tiered training set (outputs/tuning_train.jsonl -- Tier A supersedes
    Tier B per-merchant, accepted_tiebreak/accepted_general excluded, conflicting
    merchants oversampled). Same architecture as train()'s B, only the data source
    and the resulting file name change, so this is a fair like-for-like retrain,
    not a new model family."""
    import joblib
    from scipy.sparse import csr_matrix, hstack
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import SGDClassifier

    MODELS_DIR.mkdir(exist_ok=True)
    train_path = OUT_DIR / "tuning_train.jsonl"
    print(f"Loading {train_path}...", file=sys.stderr)
    df = _parse_tuning_jsonl(train_path)
    rng = np.random.default_rng(SEED)
    df = df.iloc[rng.permutation(len(df))].reset_index(drop=True)
    text = build_text(df)
    y = df["leaf"].to_numpy()
    num = np.column_stack([np.log1p(df["amount"].to_numpy(dtype=np.float32)),
                          df["is_credit"].to_numpy(dtype=np.float32)])
    print(f"Training on {len(df)} rows, {df['leaf'].nunique()} classes", file=sys.stderr)

    tv = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), max_features=30_000, min_df=2)
    X_text = tv.fit_transform(text)
    X_tfidf = hstack([X_text, csr_matrix(num)], format="csr")
    clf = SGDClassifier(loss="log_loss", alpha=1e-6, random_state=SEED, tol=None, max_iter=50)
    clf.fit(X_tfidf, y)
    joblib.dump({"vectorizer": tv, "clf": clf, "kind": "tfidf"}, MODELS_DIR / "tfidf_logreg_v2.joblib")
    print(f"Wrote {MODELS_DIR / 'tfidf_logreg_v2.joblib'}", file=sys.stderr)


def evaluate_v2():
    """Score the v2-retrained classifier per-TRANSACTION against
    data/gold_v2_slm_eval_holdout.csv -- the exact same clean, leakage-free eval
    set the SLM fine-tune will be judged on. No merchant-level modal voting (unlike
    the original evaluate()): this is a small, mostly-one-row-per-merchant set, and
    per-transaction scoring is what actually matters at serving time."""
    import joblib

    _, _, _, gen_of, _ = load_crosswalk()
    bundle = joblib.load(MODELS_DIR / "tfidf_logreg_v2.joblib")

    holdout = pd.read_csv(ROOT / "data" / "gold_v2_slm_eval_holdout.csv")
    df = pd.DataFrame({
        "vendor": holdout["merchant_raw"], "description": holdout["description_raw"],
        "amount": holdout["amount"].astype(float),
        "is_credit": (holdout["direction"] == "credit").astype(int),
    })
    preds, confs = predict(bundle, df)

    leaf_ok = preds == holdout["gold_leaf"].to_numpy()
    gen_ok = leaf_ok | (pd.Series(preds).map(gen_of).to_numpy() == holdout["gold_leaf"].map(gen_of).to_numpy())

    with open(OUT_DIR / "tuning_train.jsonl") as f:
        n_train = sum(1 for _ in f)
    lines = ["# TF-IDF classifier v2 -- scored on the clean gold_v2 eval holdout\n",
             f"Retrained on the new tiered training set (`outputs/tuning_train.jsonl`, "
             f"{n_train} rows), scored per-transaction "
             f"against `data/gold_v2_slm_eval_holdout.csv` ({len(holdout)} real transactions, zero training "
             f"overlap) -- the same set the SLM fine-tune will be judged on, for a fair comparison.\n",
             f"**Leaf accuracy: {leaf_ok.mean():.1%}**",
             f"**General-category accuracy: {gen_ok.mean():.1%}**\n"]

    report = "\n".join(lines)
    (ROOT / "data" / "distillation_v2_holdout_report.md").write_text(report)
    print(report)
    print(f"\nWrote {ROOT / 'data' / 'distillation_v2_holdout_report.md'}", file=sys.stderr)


def featurise_for(bundle, df):
    from scipy.sparse import csr_matrix, hstack
    text = build_text(df)
    X_text = bundle["vectorizer"].transform(text)
    num = np.column_stack([np.log1p(df["amount"].to_numpy(dtype=np.float32)),
                          df["is_credit"].to_numpy(dtype=np.float32)])
    return hstack([X_text, csr_matrix(num)], format="csr")


def predict(bundle, df):
    X = featurise_for(bundle, df)
    if bundle["kind"] == "lgbm":
        proba = bundle["clf"].predict_proba(X)
        idx = proba.argmax(axis=1)
        return bundle["classes"][idx], proba.max(axis=1)
    else:
        proba = bundle["clf"].predict_proba(X)
        classes = bundle["clf"].classes_
        idx = proba.argmax(axis=1)
        return classes[idx], proba.max(axis=1)


def evaluate():
    import joblib
    from collections import Counter

    _, _, _, gen_of, _ = load_crosswalk()
    txns = pd.read_parquet(EVAL_PARQUET)
    txns["merchant"] = txns["merchant"].str.strip().str.lower()

    candidates = {
        "A_control (hashed ngrams)": MODELS_DIR / "control.joblib",
        "B_tfidf_logreg (bounded vocab)": MODELS_DIR / "tfidf_logreg.joblib",
        "C_lightgbm (tfidf + trees)": MODELS_DIR / "lightgbm.joblib",
    }

    lines = ["# Distillation model bake-off -- trained on accepted production labels\n"]
    lines.append(f"Training data: `{LATEST_LABELS.name}` accepted-tier merchants, "
                 f"per-transaction Plaid text (merchant_name + original_description), "
                 f"capped at {CAP_PER_MERCHANT}/merchant.\n")

    all_stats = {}
    for name, path in candidates.items():
        bundle = joblib.load(path)
        merchant_leaf, merchant_conf = {}, {}
        # modal-vote per merchant, using mean top-class probability as confidence
        preds, confs = predict(bundle, txns)
        tmp = pd.DataFrame({"merchant": txns["merchant"], "pred": preds, "conf": confs})
        for m, grp in tmp.groupby("merchant"):
            merchant_leaf[m] = Counter(grp["pred"]).most_common(1)[0][0]
            merchant_conf[m] = grp["conf"].mean()

        lines.append(f"## {name}")

        def score(gold_path, label, group_col=None):
            gold = pd.read_csv(gold_path)
            gold["merchant"] = gold["merchant"].str.strip().str.lower()
            gold["pred"] = gold["merchant"].map(merchant_leaf)
            gold = gold.dropna(subset=["pred"])
            alt = gold["alt_leaf"].fillna("") if "alt_leaf" in gold.columns else pd.Series("", index=gold.index)
            gold["leaf_ok"] = (gold["pred"] == gold["gold_leaf"]) | ((alt != "") & (gold["pred"] == alt))
            gold["gen_ok"] = gold["leaf_ok"] | (gold["pred"].map(gen_of) == gold["gold_leaf"].map(gen_of))
            lines.append(f"- **{label}** ({len(gold)} merchants): leaf {gold['leaf_ok'].mean():.1%}, "
                         f"general {gold['gen_ok'].mean():.1%}")
            if group_col and group_col in gold.columns:
                for g, d in gold.groupby(group_col):
                    lines.append(f"    - {g}: n={len(d)}, leaf {d['leaf_ok'].mean():.1%}")
            return gold["leaf_ok"].mean(), gold["gen_ok"].mean()

        head_leaf, head_gen = score(GOLD_HEAD, "Head gold set", group_col="gold_source")
        tail_leaf, tail_gen = score(GOLD_TAIL, "Tail gold set", group_col="stratum")
        all_stats[name] = {"head_leaf": head_leaf, "head_gen": head_gen,
                          "tail_leaf": tail_leaf, "tail_gen": tail_gen}
        lines.append("")

    lines.append("## Summary")
    lines.append("| model | head leaf | head general | tail leaf | tail general |")
    lines.append("|---|---|---|---|---|")
    for name, s in all_stats.items():
        lines.append(f"| {name} | {s['head_leaf']:.1%} | {s['head_gen']:.1%} | {s['tail_leaf']:.1%} | {s['tail_gen']:.1%} |")
    lines.append("")
    lines.append("## Reference points")
    lines.append("- Equifax-trained baseline (ml_baseline.py, wrong label source): 69% head leaf / 30% tail leaf")
    lines.append("- Enriched LLM (Sonnet 5): 96.1% head leaf (adjudicated) / 76% tail leaf")
    best = max(all_stats, key=lambda k: all_stats[k]["tail_leaf"])
    lines.append(f"\n**Best on tail (the harder, more representative population): {best}**")

    report = "\n".join(lines)
    REPORT_MD.write_text(report)
    print(report)
    print(f"\nWrote {REPORT_MD}", file=sys.stderr)


if __name__ == "__main__":
    cmds = {"fetch-train": fetch_train, "train": train, "evaluate": evaluate,
             "retrain-lightgbm": retrain_lightgbm, "train-v2": train_v2, "evaluate-v2": evaluate_v2}
    args = sys.argv[1:]
    if not args or args[0] not in cmds:
        sys.exit(__doc__)
    cmds[args[0]]()

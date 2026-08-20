"""Build the supervised fine-tuning dataset for the four-field categoriser
(CLAUDE.md sections 6/7; the SLM fine-tuning experiment agreed 2026-08-20).

Trains a small open model (via Agent Platform tuning) to categorise
transactions from merchant name + raw description + amount + direction,
distilled from our LLM-consensus + human-adjudicated production labels --
NOT from Equifax (see ml_baseline_report.md for why that biases the model
toward conventions our taxonomy deliberately rejects).

Design choices, and why:
- Source: data/production_labels_tranche2.csv only (it's a full re-gate over
  the top-20k strings, so it already supersedes tranche 1 -- no need to
  concatenate).
- Held out entirely: every merchant in data/gold_merchant_labels.csv or
  data/gold_tail_labels.csv. These are the evaluation set for this exact
  experiment; training on them would invalidate the comparison to the SGD
  baseline and the raw LLM numbers.
- Excluded: tier == context_dependent. These strings need transaction-level
  (direction/entity) rules, not a static per-merchant label -- training on
  them would teach the model a wrong lesson.
- abstain_* tiers -> target "unclassified_other" (a real, trained-for class,
  not just an accepted-tier miss). The model must learn to abstain, not
  just guess.
- Transaction cap per merchant keeps a few whale merchants (revolut-scale
  volume) from dominating the gradient.

Usage:
    python src/build_tuning_dataset.py fetch [cap_per_merchant]
    python src/build_tuning_dataset.py build   # -> outputs/tuning_{train,val}.jsonl
    python src/build_tuning_dataset.py upload gs://BUCKET/PATH
"""
import csv
import json
import pathlib
import random
import sys

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from gating_experiment import ROOT, OUT_DIR, load_crosswalk  # noqa: E402
from build_tail_eval import bq_json  # noqa: E402

LABELS_SOURCE = ROOT / "data" / "production_labels_tranche2.csv"
GOLD_FILES = [ROOT / "data" / "gold_merchant_labels.csv", ROOT / "data" / "gold_tail_labels.csv"]
TXNS_JSON = OUT_DIR / "tuning_txns.json"
TRAIN_JSONL = OUT_DIR / "tuning_train.jsonl"
VAL_JSONL = OUT_DIR / "tuning_val.jsonl"
SEED = 42
VAL_FRACTION = 0.15
DEFAULT_CAP = 10
# Agent Platform hard limit (undocumented in the bundled skill reference,
# discovered via a failed job on 2026-08-20): validation datasets over 5,000
# rows are rejected outright at job-start, regardless of train set size.
MAX_VAL_ROWS = 5000

ABSTAIN_TIERS = {"abstain_confirmed", "abstain_residual", "abstain_human"}
EXCLUDED_TIERS = {"context_dependent", "needs_review"}

SYSTEM_PROMPT_PATH = OUT_DIR / "tuning_system_prompt.txt"


def build_system_prompt(leaves):
    # Deliberately excludes the 275-leaf category list, unlike the labelling
    # prompts elsewhere in this repo. Repeating ~4.9KB of category names on
    # every training row (169k+ rows) roughly 6x'd the dataset and would have
    # inflated tuning compute cost for no real benefit: the model learns the
    # valid output vocabulary from the training completions themselves, and
    # output validity is enforced post-hoc at serving time regardless (never
    # trust a generative model's output to be in-vocabulary by construction --
    # same governance safety net whether or not the list is in-context).
    # Must be reused byte-for-byte at serving time.
    lines = [
        "You categorise a UK bank transaction into exactly one category. "
        "Respond with the category name only, nothing else.",
        "",
        "You are given: merchant (the counterparty name), description (the raw "
        "bank narrative), amount (absolute value, GBP), and direction (debit = "
        "money out / spending; credit = money in / income or refund).",
    ]
    return "\n".join(lines)


def fetch(cap_per_merchant):
    _, _, leaves, _, _ = load_crosswalk()
    excluded_merchants = set()
    for gf in GOLD_FILES:
        excluded_merchants |= {r["merchant"].strip().lower() for r in csv.DictReader(open(gf))}

    rows = list(csv.DictReader(open(LABELS_SOURCE)))
    eligible = []
    for r in rows:
        m = r["merchant"].strip().lower()
        if m in excluded_merchants or r["tier"] in EXCLUDED_TIERS:
            continue
        target = "unclassified_other" if r["tier"] in ABSTAIN_TIERS else r["final_leaf"]
        if target not in leaves and target != "unclassified_other":
            continue  # defensive: never train on an invalid leaf
        eligible.append({"merchant": m, "target": target})

    print(f"{len(rows)} labelled merchants -> {len(eligible)} eligible after "
          f"excluding {len(excluded_merchants)} gold-set merchants and context_dependent/needs_review",
          file=sys.stderr)

    def q(s):
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    CHUNK = 1500
    all_txns = []
    for i in range(0, len(eligible), CHUNK):
        part = eligible[i:i + CHUNK]
        in_list = ", ".join(q(r["merchant"]) for r in part)
        print(f"Transaction fetch chunk {i // CHUNK + 1}/{(len(eligible) + CHUNK - 1) // CHUNK}...", file=sys.stderr)
        rows_json = bq_json(f"""
SELECT LOWER(TRIM(merchant_name)) AS merchant,
       IFNULL(COALESCE(original_description, transaction_name), '') AS description,
       ROUND(ABS(amount), 2) AS amount,
       CAST(amount < 0 AS INT64) AS is_credit
FROM `raylo-production.dbt_production.credit_plaid_open_banking_transactions`
WHERE merchant_name IS NOT NULL AND TRIM(merchant_name) != ''
  AND LOWER(TRIM(merchant_name)) IN ({in_list})
QUALIFY ROW_NUMBER() OVER (PARTITION BY LOWER(TRIM(merchant_name)) ORDER BY RAND()) <= {cap_per_merchant}
""")
        all_txns += rows_json

    target_by_merchant = {r["merchant"]: r["target"] for r in eligible}
    for t in all_txns:
        t["target"] = target_by_merchant[t["merchant"]]

    TXNS_JSON.write_text(json.dumps(all_txns))
    print(f"Wrote {len(all_txns)} transaction rows -> {TXNS_JSON}", file=sys.stderr)


def build():
    _, _, leaves, _, _ = load_crosswalk()
    system_prompt = build_system_prompt(leaves)
    SYSTEM_PROMPT_PATH.write_text(system_prompt)

    txns = json.loads(TXNS_JSON.read_text())
    rng = random.Random(SEED)

    # split by MERCHANT, not by transaction, so validation genuinely tests
    # generalisation to held-out merchants rather than leaking a merchant's
    # phrasing/amount pattern across the split
    merchants = sorted({t["merchant"] for t in txns})
    rng.shuffle(merchants)
    n_val = max(1, int(len(merchants) * VAL_FRACTION))
    val_merchants = set(merchants[:n_val])

    def to_example(t):
        # BigQuery's JSON API returns INT64 fields as strings ("0"/"1"), and
        # "0" is truthy in Python -- a naive truthy check on t["is_credit"]
        # silently always takes the credit branch. Every row in the first
        # tuning attempt had direction=credit (should be ~0.5% credit).
        direction = "credit" if int(t["is_credit"]) else "debit"
        user_msg = (f"merchant: {t['merchant']}\n"
                    f"description: {t['description']}\n"
                    f"amount: {t['amount']}\n"
                    f"direction: {direction}")
        return {"messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
            {"role": "assistant", "content": t["target"]},
        ]}

    train, val = [], []
    for t in txns:
        (val if t["merchant"] in val_merchants else train).append(to_example(t))
    rng.shuffle(train)
    rng.shuffle(val)
    if len(val) > MAX_VAL_ROWS:
        val = val[:MAX_VAL_ROWS]  # platform hard cap -- see MAX_VAL_ROWS comment

    with open(TRAIN_JSONL, "w") as f:
        for ex in train:
            f.write(json.dumps(ex) + "\n")
    with open(VAL_JSONL, "w") as f:
        for ex in val:
            f.write(json.dumps(ex) + "\n")

    from collections import Counter
    target_counts = Counter(t["target"] for t in txns)
    print(f"train: {len(train)} rows ({len(merchants) - n_val} merchants)", file=sys.stderr)
    print(f"val:   {len(val)} rows ({n_val} merchants)", file=sys.stderr)
    print(f"distinct target classes: {len(target_counts)} of {len(leaves) + 1} possible", file=sys.stderr)
    print(f"unclassified_other share: {target_counts.get('unclassified_other', 0) / len(txns):.1%}", file=sys.stderr)
    print(f"rarest 5 classes: {target_counts.most_common()[-5:]}", file=sys.stderr)
    print(f"System prompt ({len(system_prompt)} chars) written to {SYSTEM_PROMPT_PATH}", file=sys.stderr)


def upload(gcs_path):
    import subprocess
    gcs_path = gcs_path.rstrip("/")
    subprocess.run(["gcloud", "storage", "cp", str(TRAIN_JSONL), f"{gcs_path}/train.jsonl"], check=True)
    subprocess.run(["gcloud", "storage", "cp", str(VAL_JSONL), f"{gcs_path}/val.jsonl"], check=True)
    print(f"Uploaded to {gcs_path}/{{train,val}}.jsonl", file=sys.stderr)


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] not in {"fetch", "build", "upload"}:
        sys.exit(__doc__)
    if args[0] == "fetch":
        fetch(int(args[1]) if len(args) > 1 else DEFAULT_CAP)
    elif args[0] == "build":
        build()
    elif args[0] == "upload":
        if len(args) < 2:
            sys.exit("usage: upload gs://BUCKET/PATH")
        upload(args[1])

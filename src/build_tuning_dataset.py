"""Build the supervised fine-tuning dataset for the four-field categoriser
(CLAUDE.md sections 6/7; the SLM fine-tuning experiment agreed 2026-08-20;
redesigned 2026-08-21 after the gold_transactions_v2/v3 leakage audit and
the tiered-trust discussion with Carlos).

Philosophy (agreed 2026-08-21, keep this in sync with any future changes):
  1. Trust labels by how they were made, not treat everything as equally
     true. Three tiers, in trust order:
       Tier A: gold_transactions_v2/v3 -- real transactions, individually
               human-reviewed from scratch. Small, zero-noise, and the ONLY
               source that teaches transaction-level discrimination (same
               merchant, different correct answer by context -- e.g.
               Admiral Insurance vs Admiral Casino).
       Tier B: production_labels_tranche3's auto_accept/accepted/
               human_reviewed tiers -- measured 82-91% accurate against the
               clean gold set. Bulk volume/breadth.
       Excluded: accepted_tiebreak (measured 66.9% -- the largest tier, but
               too weak to trust) and accepted_general (33.3%, n=3).
       Never: context_dependent, needs_review (no real per-merchant answer
               exists), abstain_* (mapped to the real unclassified_other
               class, not dropped).
  2. Split by MERCHANT, not by row, for the Tier A held-out eval slice --
     some merchants train the model, a disjoint set evaluates it. A
     merchant with genuinely conflicting labels across gold_v2/v3 (proven
     context-dependent -- e.g. revolut, monzo) is always kept in TRAINING,
     never held out: that's exactly the signal worth teaching, and there's
     no single "correct answer" to score a held-out prediction against
     anyway.
  3. Any merchant in Tier A entirely supersedes Tier B for that merchant
     (Tier A is higher-trust) -- Tier B's own copy is dropped, not merged.
  4. One source of truth: this script reads gold_transactions_v2*.csv
     directly, the same files final_evaluation.py and build_gold_v3_volume.py
     score against. No second, drifting copy of "what's correct."
  5. Known-ambiguous (conflicting) Tier A merchants are oversampled in
     training rather than left to be diluted across ~300k mostly-
     unambiguous rows.

Known gap (documented, not hidden): 65 of 275 leaves still have under 5
combined examples after a targeted top-up (data/tuning_leaf_topup.csv) --
mostly genuine data rarity (no real transactions exist at all for that
category), not a sourcing failure. The model will be weak on these; that's
an acceptable, disclosed limitation given how rare they are in real
traffic too, not something to paper over with synthetic examples.

Usage:
    python src/build_tuning_dataset.py fetch [cap_per_merchant]
    python src/build_tuning_dataset.py build   # -> outputs/tuning_{train,val}.jsonl
                                                # + data/gold_v2_slm_eval_holdout.csv
    python src/build_tuning_dataset.py upload gs://BUCKET/PATH
"""
import csv
import json
import pathlib
import random
import sys
from collections import defaultdict

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from gating_experiment import ROOT, OUT_DIR, load_crosswalk  # noqa: E402
from build_tail_eval import bq_json  # noqa: E402

LABELS_SOURCE = ROOT / "data" / "production_labels_tranche3.csv"
GOLD_V1_FILES = [ROOT / "data" / "gold_merchant_labels.csv", ROOT / "data" / "gold_tail_labels.csv"]
GOLD_V2_FILES = [ROOT / "data" / "gold_transactions_v2.csv", ROOT / "data" / "gold_transactions_v2_batch2.csv"]
# Training-only supplementary gold data (2026-08-24) -- deliberately NOT added to
# GOLD_V2_FILES/load_tier_a(), which drives the merchant-level eval-holdout carve-
# out written to SLM_EVAL_CSV (a data/ asset every model-comparison benchmark in
# CLAUDE.md sec 6a is measured against). Mixing more merchants into that pool
# would change the holdout's random split composition even at a fixed SEED, since
# the shuffle now runs over a different merchant list -- silently breaking
# comparability with every already-published number. These go straight to
# training instead, same treatment as TOPUP_FILE below. gold_transactions_
# risk_categories.csv is deliberately excluded here too -- it's reserved as a
# clean eval set for exactly this retrain (see confusion_analysis.py), and
# gold_transactions_v5_LOCKED.csv must never be touched by training OR scoring.
ADDITIONAL_TRAIN_FILES = [ROOT / "data" / "gold_transactions_v3_volume.csv",
                          ROOT / "data" / "gold_transactions_v4_slm_volume.csv"]
TOPUP_FILE = ROOT / "data" / "tuning_leaf_topup.csv"
TXNS_JSON = OUT_DIR / "tuning_txns.json"
TRAIN_JSONL = OUT_DIR / "tuning_train.jsonl"
VAL_JSONL = OUT_DIR / "tuning_val.jsonl"
SLM_EVAL_CSV = ROOT / "data" / "gold_v2_slm_eval_holdout.csv"
SPLIT_MANIFEST = OUT_DIR / "tuning_gold_v2_split_manifest.csv"
SEED = 42
VAL_FRACTION = 0.15
EVAL_HOLDOUT_FRACTION = 0.4  # Tier A is only ~1.5% of total training rows, so favouring eval size here is cheap
OVERSAMPLE_FACTOR = 3  # how many times a conflicting (context-dependent) Tier A merchant's rows are repeated
DEFAULT_CAP = 10
# Agent Platform hard limit (undocumented in the bundled skill reference,
# discovered via a failed job on 2026-08-20): validation datasets over 5,000
# rows are rejected outright at job-start, regardless of train set size.
MAX_VAL_ROWS = 5000

ALLOWED_TIERS = {"auto_accept", "accepted", "human_reviewed"}
ABSTAIN_TIERS = {"abstain_confirmed", "abstain_residual", "abstain_human"}

SYSTEM_PROMPT_PATH = OUT_DIR / "tuning_system_prompt.txt"


def _norm(s):
    return (s or "").strip().lower()


def load_tier_a():
    """merchant -> set of gold_leaf values seen (>1 means genuinely conflicting,
    i.e. proven context-dependent) + the full row list for building examples."""
    rows = []
    for f in GOLD_V2_FILES:
        if f.exists():
            rows.extend(csv.DictReader(open(f)))
    by_merchant = defaultdict(list)
    for r in rows:
        by_merchant[_norm(r["merchant_raw"])].append(r)
    return by_merchant


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
    for gf in GOLD_V1_FILES:
        excluded_merchants |= {_norm(r["merchant"]) for r in csv.DictReader(open(gf))}
    tier_a = load_tier_a()
    excluded_merchants |= set(tier_a)  # Tier A supersedes Tier B entirely for any overlapping merchant

    rows = list(csv.DictReader(open(LABELS_SOURCE)))
    eligible = []
    for r in rows:
        m = _norm(r["merchant"])
        if m in excluded_merchants:
            continue
        if r["tier"] in ABSTAIN_TIERS:
            target = "unclassified_other"
        elif r["tier"] in ALLOWED_TIERS:
            target = r["final_leaf"]
        else:
            continue  # context_dependent, needs_review, accepted_tiebreak (67%), accepted_general (33%, n=3)
        if target not in leaves and target != "unclassified_other":
            continue  # defensive: never train on an invalid leaf
        eligible.append({"merchant": m, "target": target})

    print(f"{len(rows)} labelled merchants -> {len(eligible)} eligible (Tier B) after "
          f"excluding {len(excluded_merchants)} gold-set/Tier-A merchants and "
          f"context_dependent/needs_review/accepted_tiebreak/accepted_general", file=sys.stderr)

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
    from collections import Counter

    _, _, leaves, _, _ = load_crosswalk()
    system_prompt = build_system_prompt(leaves)
    SYSTEM_PROMPT_PATH.write_text(system_prompt)

    def to_example(merchant, description, amount, direction, target):
        user_msg = (f"merchant: {merchant}\n"
                    f"description: {description}\n"
                    f"amount: {amount}\n"
                    f"direction: {direction}")
        return {"messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
            {"role": "assistant", "content": target},
        ]}

    # ---------- Tier B: production_labels, merchant-level split (unchanged mechanism) ----------
    txns = json.loads(TXNS_JSON.read_text())
    rng = random.Random(SEED)
    merchants = sorted({t["merchant"] for t in txns})
    rng.shuffle(merchants)
    n_val = max(1, int(len(merchants) * VAL_FRACTION))
    val_merchants = set(merchants[:n_val])

    def tier_b_example(t):
        # BigQuery's JSON API returns INT64 fields as strings ("0"/"1"), and
        # "0" is truthy in Python -- a naive truthy check on t["is_credit"]
        # silently always takes the credit branch. Every row in the first
        # tuning attempt had direction=credit (should be ~0.5% credit).
        direction = "credit" if int(t["is_credit"]) else "debit"
        return to_example(t["merchant"], t["description"], t["amount"], direction, t["target"])

    train, val = [], []
    for t in txns:
        (val if t["merchant"] in val_merchants else train).append(tier_b_example(t))
    tier_b_target_counts = Counter(t["target"] for t in txns)

    # ---------- Tier A: gold_transactions_v2/v3, merchant-level eval holdout ----------
    tier_a = load_tier_a()
    conflicting = {m for m, rows in tier_a.items() if len({r["gold_leaf"] for r in rows}) > 1}
    non_conflicting = [m for m in tier_a if m not in conflicting]
    rng.shuffle(non_conflicting)
    n_holdout = int(len(non_conflicting) * EVAL_HOLDOUT_FRACTION)
    holdout_merchants = set(non_conflicting[:n_holdout])
    # conflicting merchants are NEVER held out -- that's exactly the signal worth training on,
    # and there's no single "correct answer" to score a held-out prediction against anyway

    tier_a_train_examples = []
    holdout_rows = []
    for m, rows in tier_a.items():
        if m in holdout_merchants:
            holdout_rows.extend(rows)
            continue
        reps = OVERSAMPLE_FACTOR if m in conflicting else 1
        for r in rows:
            # Plaid's raw amount is signed (negative = credit) -- the system prompt promises
            # "amount (absolute value, GBP)" and direction carries the sign meaning separately.
            # 127/1500 Tier A rows had a negative amount before this fix (found 2026-08-21
            # while adapting the classifier retrain -- caught before it reached the SLM's
            # eval scoring, but it WAS already in a prior tuning_train.jsonl build).
            ex = to_example(r["merchant_raw"], r["description_raw"], abs(float(r["amount"])),
                             r["direction"], r["gold_leaf"])
            tier_a_train_examples.extend([ex] * reps)

    with open(SLM_EVAL_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["merchant_raw", "description_raw", "amount", "direction", "gold_leaf"])
        w.writeheader()
        for r in holdout_rows:
            row = {k: r[k] for k in w.fieldnames}
            row["amount"] = abs(float(r["amount"]))
            w.writerow(row)

    with open(SPLIT_MANIFEST, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["merchant", "split", "conflicting"])
        for m in tier_a:
            w.writerow([m, "eval_holdout" if m in holdout_merchants else "train", m in conflicting])

    # ---------- Top-up: thin-leaf targeted sourcing, all goes to training ----------
    topup_examples = []
    if TOPUP_FILE.exists():
        for r in csv.DictReader(open(TOPUP_FILE)):
            if _norm(r["merchant_raw"]) in holdout_merchants:
                continue  # defensive -- shouldn't happen, topup targeted different merchants entirely
            topup_examples.append(to_example(r["merchant_raw"], r["description_raw"], abs(float(r["amount"])),
                                              r["direction"], r["gold_leaf"]))

    # ---------- Additional training-only gold (v3/v4) -- never touches the holdout ----------
    additional_examples = []
    for f in ADDITIONAL_TRAIN_FILES:
        if not f.exists():
            continue
        n_before = len(additional_examples)
        for r in csv.DictReader(open(f)):
            if _norm(r["merchant_raw"]) in holdout_merchants:
                continue  # a v3/v4 merchant that happens to also be a v2 holdout merchant -- don't leak
            additional_examples.append(to_example(r["merchant_raw"], r["description_raw"], abs(float(r["amount"])),
                                                   r["direction"], r["gold_leaf"]))
        print(f"Additional training-only gold: {f.name} contributed {len(additional_examples) - n_before} rows",
              file=sys.stderr)

    train = train + tier_a_train_examples + topup_examples + additional_examples
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

    all_targets = ([t["target"] for t in txns]
                   + [r["gold_leaf"] for m, rows in tier_a.items() if m not in holdout_merchants for r in rows]
                   + ([r["gold_leaf"] for r in csv.DictReader(open(TOPUP_FILE))] if TOPUP_FILE.exists() else []))
    target_counts = Counter(all_targets)
    print(f"Tier B: {len(txns)} txns ({len(tier_b_target_counts)} classes)", file=sys.stderr)
    print(f"Tier A: {sum(len(r) for m,r in tier_a.items() if m not in holdout_merchants)} txns train "
          f"({len(tier_a) - len(holdout_merchants)} merchants, {len(conflicting)} conflicting "
          f"oversampled {OVERSAMPLE_FACTOR}x) + {len(holdout_rows)} txns held out for eval "
          f"({len(holdout_merchants)} merchants) -> {SLM_EVAL_CSV}", file=sys.stderr)
    print(f"Top-up: {len(topup_examples)} txns", file=sys.stderr)
    print(f"Additional training-only gold (v3/v4): {len(additional_examples)} txns", file=sys.stderr)
    print(f"train: {len(train)} rows total", file=sys.stderr)
    print(f"val:   {len(val)} rows ({n_val} Tier B merchants)", file=sys.stderr)
    print(f"distinct target classes across all training sources: {len(target_counts)} of {len(leaves) + 1} possible "
          f"({len(leaves) + 1 - len(target_counts)} classes with zero training examples)", file=sys.stderr)
    print(f"unclassified_other share: {target_counts.get('unclassified_other', 0) / sum(target_counts.values()):.1%}",
          file=sys.stderr)
    print(f"rarest 5 classes: {target_counts.most_common()[-5:]}", file=sys.stderr)
    print(f"System prompt ({len(system_prompt)} chars) written to {SYSTEM_PROMPT_PATH}", file=sys.stderr)
    print(f"Split manifest written to {SPLIT_MANIFEST}", file=sys.stderr)


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

"""Build the supervised fine-tuning dataset for the four-field categoriser
(CLAUDE.md sections 6/7; the SLM fine-tuning experiment agreed 2026-08-20;
redesigned 2026-08-21 after the gold_transactions_v2/v3 leakage audit and
the tiered-trust discussion with Carlos).

Philosophy (agreed 2026-08-21, keep this in sync with any future changes):
  1. Trust labels by how they were made, not treat everything as equally
     true. Three tiers, in trust order:
       Tier A: data/gold_transactions.csv (unified v2+v3+v4) rows with
               role=train — real transactions, human-reviewed. role=iter_eval
               is the frozen merchant-disjoint holdout (never trained on).
       Tier B: production_labels_tranche4's dictionary-eligible tiers
               (auto_accept / accepted / human_reviewed / agent_consensus /
               agent_tiebreak / agent_review). Tranche 4 is a full union of
               tranches 1-4, not incremental. Bulk volume/breadth.
               `human_reviewed` is Carlos only; agent_* are weak supervision.
       Excluded: accepted_tiebreak (measured 66.9% -- the largest tier, but
               too weak to trust) and accepted_general (33.3%, n=3).
       Never: context_dependent, needs_review (no real answer exists),
               abstain_* (mapped to unclassified_other, not dropped).
  2. Split by MERCHANT. The iter_eval merchant list is FROZEN in
     data/gold_v2_slm_eval_holdout.csv — this script must not reshuffle it.
     Conflicting merchants (same name, different gold_leaf) stay in TRAINING.
  3. Any merchant in Tier A entirely supersedes Tier B for that merchant.
  4. One source of truth for transaction gold: gold_transactions.csv.
     gold_transactions_v2*.csv / v3 / v4 remain provenance snapshots.
  5. Conflicting Tier A merchants are oversampled in training.
  6. gold_transactions_risk_categories.csv, gold_transactions_v5_LOCKED.csv
     (retired confirmation gold — keep in git, do not train or score), and
     gold_transactions_v6_LOCKED.csv (new locked set, same rule) are never
     training or scoring inputs.

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
from collections import defaultdict

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from gating_experiment import ROOT, OUT_DIR, load_crosswalk  # noqa: E402
from build_tail_eval import bq_json  # noqa: E402
from label_provenance import DICTIONARY_ELIGIBLE_TIERS  # noqa: E402

LABELS_SOURCE = ROOT / "data" / "production_labels_tranche4.csv"
GOLD_TXN_FILE = ROOT / "data" / "gold_transactions.csv"
GOLD_V1_FILES = [ROOT / "data" / "gold_merchant_labels.csv", ROOT / "data" / "gold_tail_labels.csv"]
TOPUP_FILE = ROOT / "data" / "tuning_leaf_topup.csv"
# Unweighted SGD ignores classes with tens of rows against 166k. Repeat
# starved-leaf top-up examples until each has at least this many effective
# training rows. Do not oversample leaves that already have hundreds of
# unique examples (bingo, debt_collection).
STARVED_TOPUP_LEAVES = {
    "cash_advance", "charge_card_repayment", "financial_services_other",
    "overdraft_unarranged", "balance_transfer",
}
MIN_STARVED_EFFECTIVE = 200
# v5b mixed T6 residual into SGD and knocked thin risk leaves (car_lease →
# carwash). Keep those residual labels; repeat *other* names in the same
# leaves until this many clean-merchant rows exist. Never cycle merchants
# that appear on the risk-gold file (that would inflate the bar by leakage).
RISK_GOLD = ROOT / "data" / "gold_transactions_risk_categories.csv"
RISK_GUARD_LEAVES = {
    "car_lease", "debt_management_plan", "revolving_credit_repayment",
}
MIN_RISK_GUARD_CLEAN = 250
TXNS_JSON = OUT_DIR / "tuning_txns.json"
TRAIN_JSONL = OUT_DIR / "tuning_train.jsonl"
VAL_JSONL = OUT_DIR / "tuning_val.jsonl"
SLM_EVAL_CSV = ROOT / "data" / "gold_v2_slm_eval_holdout.csv"
SPLIT_MANIFEST = OUT_DIR / "tuning_gold_v2_split_manifest.csv"
SEED = 42
VAL_FRACTION = 0.15
OVERSAMPLE_FACTOR = 3  # how many times a conflicting (context-dependent) Tier A merchant's rows are repeated
DEFAULT_CAP = 10
# Agent Platform hard limit (undocumented in the bundled skill reference,
# discovered via a failed job on 2026-08-20): validation datasets over 5,000
# rows are rejected outright at job-start, regardless of train set size.
MAX_VAL_ROWS = 5000

ALLOWED_TIERS = DICTIONARY_ELIGIBLE_TIERS
ABSTAIN_TIERS = {"abstain_confirmed", "abstain_residual", "abstain_human"}

SYSTEM_PROMPT_PATH = OUT_DIR / "tuning_system_prompt.txt"


def _norm(s):
    return (s or "").strip().lower()


def load_tier_a():
    """All unified gold rows, keyed by normalised merchant."""
    if not GOLD_TXN_FILE.exists():
        sys.exit(f"Missing {GOLD_TXN_FILE} — run src/build_gold_transactions_unified.py")
    by_merchant = defaultdict(list)
    for r in csv.DictReader(open(GOLD_TXN_FILE)):
        by_merchant[_norm(r["merchant_raw"])].append(r)
    return by_merchant


def frozen_holdout_merchants():
    """Merchant set from the published holdout file — never reshuffled."""
    return {_norm(r["merchant_raw"]) for r in csv.DictReader(open(SLM_EVAL_CSV))}


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
    tier_a_preview = load_tier_a()
    for t in txns:
        if t["merchant"] in tier_a_preview:
            continue  # Tier A supersedes Tier B for overlapping merchants
        (val if t["merchant"] in val_merchants else train).append(tier_b_example(t))
    tier_b_target_counts = Counter(t["target"] for t in txns if t["merchant"] not in tier_a_preview)

    # ---------- Tier A: unified gold. Holdout merchants frozen from SLM_EVAL_CSV ----------
    tier_a = load_tier_a()
    holdout_merchants = frozen_holdout_merchants()
    conflicting = {m for m, rows in tier_a.items() if len({r["gold_leaf"] for r in rows}) > 1}

    tier_a_train_examples = []
    n_iter_eval_rows = 0
    for m, rows in tier_a.items():
        if m in holdout_merchants:
            n_iter_eval_rows += len(rows)
            continue
        train_rows = [r for r in rows if r.get("role") != "iter_eval"]
        reps = OVERSAMPLE_FACTOR if m in conflicting else 1
        for r in train_rows:
            # Plaid's raw amount is signed (negative = credit) -- the system prompt promises
            # "amount (absolute value, GBP)" and direction carries the sign meaning separately.
            ex = to_example(r["merchant_raw"], r["description_raw"], abs(float(r["amount"])),
                             r["direction"], r["gold_leaf"])
            tier_a_train_examples.extend([ex] * reps)

    # Do not rewrite SLM_EVAL_CSV — that file is the frozen published holdout.
    with open(SPLIT_MANIFEST, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["merchant", "split", "conflicting"])
        for m in tier_a:
            w.writerow([m, "eval_holdout" if m in holdout_merchants else "train", m in conflicting])

    # ---------- Top-up: thin-leaf targeted sourcing, all goes to training ----------
    topup_examples = []
    starved_topup = {leaf: [] for leaf in STARVED_TOPUP_LEAVES}
    if TOPUP_FILE.exists():
        for r in csv.DictReader(open(TOPUP_FILE)):
            # Starved risk leaves are often a single live merchant (American Express
            # is the UK charge-card population AND a v2 holdout merchant). Dropping
            # those top-up rows would leave the class empty; keep them. Other
            # top-up rows still skip holdout merchants.
            if (_norm(r["merchant_raw"]) in holdout_merchants
                    and r["gold_leaf"] not in STARVED_TOPUP_LEAVES):
                continue
            ex = to_example(r["merchant_raw"], r["description_raw"], abs(float(r["amount"])),
                            r["direction"], r["gold_leaf"])
            topup_examples.append(ex)
            if r["gold_leaf"] in starved_topup:
                starved_topup[r["gold_leaf"]].append(ex)

    train = train + tier_a_train_examples + topup_examples

    def _leaf_of(ex):
        return next(m["content"] for m in ex["messages"] if m["role"] == "assistant")

    def _merchant_of(ex):
        user = next(m["content"] for m in ex["messages"] if m["role"] == "user")
        for part in user.split("\n"):
            if part.startswith("merchant: "):
                return _norm(part[len("merchant: "):])
        return ""

    leaf_counts = Counter(_leaf_of(ex) for ex in train)
    starved_extra = []
    for leaf in STARVED_TOPUP_LEAVES:
        have = leaf_counts.get(leaf, 0)
        pool = starved_topup.get(leaf) or []
        if have >= MIN_STARVED_EFFECTIVE or not pool:
            print(f"Starved oversample {leaf}: {have} already "
                  f"{'>=' if have >= MIN_STARVED_EFFECTIVE else '(no top-up pool)'} "
                  f"{MIN_STARVED_EFFECTIVE}", file=sys.stderr)
            continue
        need = MIN_STARVED_EFFECTIVE - have
        # Literal copies of the same example dicts (no description jitter).
        starved_extra.extend(pool[i % len(pool)] for i in range(need))
        print(f"Starved oversample {leaf}: {have} unique-in-train -> "
              f"{have + need} effective ({len(pool)} distinct top-up rows cycled)",
              file=sys.stderr)
    train = train + starved_extra

    risk_merchants = set()
    if RISK_GOLD.exists():
        for r in csv.DictReader(open(RISK_GOLD)):
            m = _norm(r.get("merchant_raw") or "")
            if m:
                risk_merchants.add(m)
    blocked = risk_merchants | holdout_merchants | {""}
    guard_extra = []
    for leaf in sorted(RISK_GUARD_LEAVES):
        pool = [ex for ex in train
                if _leaf_of(ex) == leaf and _merchant_of(ex) not in blocked]
        have_clean = len(pool)
        if have_clean >= MIN_RISK_GUARD_CLEAN or not pool:
            print(f"Risk-guard oversample {leaf}: {have_clean} clean-merchant "
                  f"rows already {'>=' if have_clean >= MIN_RISK_GUARD_CLEAN else '(empty pool)'} "
                  f"{MIN_RISK_GUARD_CLEAN}", file=sys.stderr)
            continue
        need = MIN_RISK_GUARD_CLEAN - have_clean
        guard_extra.extend(pool[i % len(pool)] for i in range(need))
        print(f"Risk-guard oversample {leaf}: {have_clean} clean-merchant rows -> "
              f"{have_clean + need} effective ({len({_merchant_of(ex) for ex in pool})} "
              f"merchants; risk-gold/holdout names excluded)", file=sys.stderr)
    train = train + guard_extra

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
    print(f"Tier A: {len(tier_a_train_examples)} examples after oversample "
          f"({len(tier_a) - len(holdout_merchants)} train merchants, {len(conflicting)} conflicting "
          f"oversampled {OVERSAMPLE_FACTOR}x); {n_iter_eval_rows} unified rows on frozen holdout "
          f"merchants ({len(holdout_merchants)}) — {SLM_EVAL_CSV} not rewritten", file=sys.stderr)
    print(f"Top-up: {len(topup_examples)} txns "
          f"(+{len(starved_extra)} starved-leaf oversample copies "
          f"+{len(guard_extra)} risk-guard oversample copies)", file=sys.stderr)
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

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
    python src/build_tuning_dataset.py fetch [cap_per_merchant] \
        --protected-membership /private/path/eval-membership.csv
    python src/build_tuning_dataset.py build \
        --protected-membership /private/path/eval-membership.csv
    python src/build_tuning_dataset.py upload gs://BUCKET/PATH

The fetch command now requires the reviewed unambiguous assessment -> checkout ->
user -> customer linkage and retains Plaid account/transaction IDs.  Build keeps
those identifiers out of the model JSONL and writes them to the private
``outputs/tuning_membership_lookup.csv`` instead.  Existing fetched JSON without
IDs must be re-fetched; the builder deliberately fails rather than inventing an
identity.  Legacy curated CSV rows are counted as identity-unavailable in the
coverage report, so lookup absence is not historical-completeness evidence.
"""
import argparse
import csv
import hashlib
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
from training_membership import (  # noqa: E402
    TrackedExample,
    exact_plaid_membership,
    publish_training_export,
    unavailable_membership,
    verify_training_export,
)

LABELS_SOURCE = ROOT / "data" / "production_labels_tranche4.csv"
GOLD_TXN_FILE = ROOT / "data" / "gold_transactions.csv"
GOLD_V1_FILES = [ROOT / "data" / "gold_merchant_labels.csv", ROOT / "data" / "gold_tail_labels.csv"]
TOPUP_FILE = ROOT / "data" / "tuning_leaf_topup.csv"
# Row-level credit tranche (2 Sep review, Week 2): live Plaid credits + T6-bound risk
# debits, labelled Gemini+Sonnet consensus / Opus tiebreak / Carlos. Written by
# build_credit_tranche.py apply. Merchant-disjoint from the credit eval it also writes.
CREDIT_TOPUP_FILE = ROOT / "data" / "tuning_credit_topup.csv"
RISK_TOPUP_FILE = ROOT / "data" / "tuning_risk_topup.csv"       # 3 Sep: T6-bound risk debit tranche
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
TXNS_RECEIPT = OUT_DIR / "tuning_txns_receipt.json"
TRAIN_JSONL = OUT_DIR / "tuning_train.jsonl"
VAL_JSONL = OUT_DIR / "tuning_val.jsonl"
SLM_EVAL_CSV = ROOT / "data" / "gold_v2_slm_eval_holdout.csv"
SPLIT_MANIFEST = OUT_DIR / "tuning_gold_v2_split_manifest.csv"
MEMBERSHIP_LOOKUP = OUT_DIR / "tuning_membership_lookup.csv"
MEMBERSHIP_COVERAGE = OUT_DIR / "tuning_membership_coverage.json"
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


def _file_sha256(path):
    with pathlib.Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load_eval_protection(paths):
    """Load private eval memberships that future Tier-B fetches must exclude."""

    if not paths:
        raise ValueError("at least one eval membership lookup is required")
    events = set()
    accounts = set()
    customers = set()
    account_customers = {}
    inputs = []
    for supplied in paths:
        path = pathlib.Path(supplied)
        rows = 0
        with path.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            required = {
                "provider",
                "account_id",
                "transaction_id",
                "customer_id",
                "role",
            }
            if (
                reader.fieldnames is None
                or len(reader.fieldnames) != len(set(reader.fieldnames))
                or not required <= set(reader.fieldnames)
            ):
                raise ValueError("eval membership lookup schema is incomplete")
            for row in reader:
                if None in row or any(value is None for value in row.values()):
                    raise ValueError("eval membership row width is invalid")
                identity = (
                    row["provider"],
                    row["account_id"],
                    row["transaction_id"],
                )
                customer_id = row["customer_id"]
                if (
                    identity[0] != "plaid"
                    or row["role"] != "eval"
                    or any(not value.strip() or value != value.strip() for value in identity)
                    or not customer_id.strip()
                    or customer_id != customer_id.strip()
                ):
                    raise ValueError("eval membership row is outside the protected scope")
                event = identity[1:]
                if event in events:
                    raise ValueError("eval membership contains a duplicate event")
                events.add(event)
                accounts.add(identity[1])
                customers.add(customer_id)
                previous_customer = account_customers.setdefault(identity[1], customer_id)
                if previous_customer != customer_id:
                    raise ValueError("eval membership account crosses customer groups")
                rows += 1
        if rows == 0:
            raise ValueError("eval membership lookup is empty")
        inputs.append({"sha256": _file_sha256(path), "rows": rows})
    return {
        "events": frozenset(events),
        "accounts": frozenset(accounts),
        "customers": frozenset(customers),
        "account_customers": account_customers,
        "inputs": tuple(inputs),
    }


def exclude_eval_membership(rows, protection):
    """Exclude exact events and their connected account/customer groups."""

    retained = []
    counts = {"exact_event": 0, "account_group": 0, "customer_group": 0}
    seen = set()
    fetched_account_customers = {}
    for row in rows:
        required = ("account_id", "transaction_id", "customer_id")
        if any(not isinstance(row.get(field), str) or not row[field] for field in required):
            raise ValueError("fetched Tier-B row is missing linked identity")
        event = (row["account_id"], row["transaction_id"])
        if event in seen:
            raise ValueError("fetched Tier-B rows contain a duplicate event")
        seen.add(event)
        previous_customer = fetched_account_customers.setdefault(
            row["account_id"], row["customer_id"]
        )
        if previous_customer != row["customer_id"]:
            raise ValueError("fetched Tier-B account crosses customer groups")
        protected_customer = protection["account_customers"].get(row["account_id"])
        if protected_customer is not None and protected_customer != row["customer_id"]:
            raise ValueError("fetched Tier-B account contradicts eval customer membership")
        if event in protection["events"]:
            counts["exact_event"] += 1
            continue
        if row["account_id"] in protection["accounts"]:
            counts["account_group"] += 1
            continue
        if row["customer_id"] in protection["customers"]:
            counts["customer_group"] += 1
            continue
        retained.append(row)
    return retained, counts


def write_tier_b_fetch(rows, protection, *, data_path=TXNS_JSON, receipt_path=TXNS_RECEIPT):
    """Publish fetched rows first and their protection receipt last."""

    data_path = pathlib.Path(data_path)
    receipt_path = pathlib.Path(receipt_path)
    data_path.write_text(json.dumps(rows), encoding="utf-8")
    receipt = {
        "schema_version": "tuning-tier-b-fetch-receipt-v1",
        "source_kind": "customer_linked_plaid_materialized",
        "anonymous_id_recovery": False,
        "eval_membership_inputs": list(protection["inputs"]),
        "rows": len(rows),
        "result_sha256": _file_sha256(data_path),
    }
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return receipt


def read_verified_tier_b_fetch(
    protected_memberships,
    *,
    data_path=TXNS_JSON,
    receipt_path=TXNS_RECEIPT,
):
    data_path = pathlib.Path(data_path)
    receipt_path = pathlib.Path(receipt_path)
    protection = load_eval_protection(protected_memberships)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if (
        receipt.get("schema_version") != "tuning-tier-b-fetch-receipt-v1"
        or receipt.get("source_kind") != "customer_linked_plaid_materialized"
        or receipt.get("anonymous_id_recovery") is not False
        or receipt.get("eval_membership_inputs") != list(protection["inputs"])
        or receipt.get("result_sha256") != _file_sha256(data_path)
    ):
        raise ValueError("Tier-B fetch is missing its verified eval protection")
    rows = json.loads(data_path.read_text(encoding="utf-8"))
    if type(rows) is not list or receipt.get("rows") != len(rows):
        raise ValueError("Tier-B fetch row count does not match its receipt")
    return rows


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


EVAL_ONLY_FILES = [
    ROOT / "data" / "gold_transactions_risk_categories.csv",
    ROOT / "data" / "gold_transactions_risk_t6bound.csv",   # 3 Sep: T6-bound risk gold (400)
    ROOT / "data" / "gold_credit_eval.csv",                  # 3 Sep: merchant-disjoint credit eval (2,000)
]


def load_risk_merchants():
    """Merchants in the risk-category gold sets and the credit eval — excluded from ALL
    training rows (Tier A, Tier B, top-ups). Name kept for the existing call sites."""
    out = set()
    for path in EVAL_ONLY_FILES:
        if path.exists():
            for r in csv.DictReader(open(path)):
                m = _norm(r.get("merchant_raw") or "")
                if m:
                    out.add(m)
    return out


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


def build_linked_tier_b_query(merchants, cap_per_merchant):
    """Build the Tier-B fetch from the approved customer-linked Plaid pool."""
    if type(cap_per_merchant) is not int or cap_per_merchant <= 0:
        raise ValueError("cap_per_merchant must be a positive integer")
    merchants = list(merchants)
    if not merchants or any(not isinstance(m, str) or not m.strip() for m in merchants):
        raise ValueError("at least one nonblank merchant is required")

    def q(s):
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'

    in_list = ", ".join(q(m) for m in merchants)
    return f"""
WITH source_observations AS (
  SELECT
    checkout_risk_assessment_result_id AS assessment_id,
    TRIM(account_id) AS account_id,
    TRIM(transaction_id) AS transaction_id,
    LOWER(TRIM(merchant_name)) AS merchant,
    IFNULL(COALESCE(description, transaction_name), '') AS description,
    ROUND(ABS(amount), 2) AS amount,
    CAST(amount < 0 AS INT64) AS is_credit,
    TO_HEX(SHA256(TO_JSON_STRING(STRUCT(
      LOWER(TRIM(merchant_name)) AS merchant,
      IFNULL(COALESCE(description, transaction_name), '') AS description,
      ROUND(ABS(amount), 2) AS amount,
      CAST(amount < 0 AS INT64) AS is_credit
    )))) AS payload_sha256
  FROM `raylo-production.dbt_production.intermediate_credit_plaid_transactions`
  WHERE NULLIF(TRIM(checkout_risk_assessment_result_id), '') IS NOT NULL
    AND NULLIF(TRIM(account_id), '') IS NOT NULL
    AND NULLIF(TRIM(transaction_id), '') IS NOT NULL
    AND NULLIF(TRIM(merchant_name), '') IS NOT NULL
    AND LOWER(TRIM(merchant_name)) IN ({in_list})
), assessment_links AS (
  SELECT
    checkout_risk_assessment_result_id AS assessment_id,
    COUNT(DISTINCT checkout_id) AS checkout_count,
    MIN(checkout_id) AS checkout_id
  FROM `raylo-production.dbt_production.intermediate_raylo_production__checkout_risk_assessment_results_latest`
  WHERE NULLIF(TRIM(checkout_risk_assessment_result_id), '') IS NOT NULL
    AND NULLIF(TRIM(checkout_id), '') IS NOT NULL
  GROUP BY assessment_id
), checkout_links AS (
  SELECT
    checkout_id,
    COUNT(DISTINCT NULLIF(TRIM(user_id), '')) AS user_count,
    MIN(NULLIF(TRIM(user_id), '')) AS user_id
  FROM `raylo-production.dbt_production.stg_raylo_production__checkouts`
  WHERE NULLIF(TRIM(checkout_id), '') IS NOT NULL
  GROUP BY checkout_id
), user_links AS (
  SELECT
    user_id,
    COUNT(DISTINCT NULLIF(TRIM(customer_id), '')) AS customer_count,
    MIN(NULLIF(TRIM(customer_id), '')) AS customer_id
  FROM `raylo-production.dbt_production.stg_raylo_production__users`
  WHERE NULLIF(TRIM(user_id), '') IS NOT NULL
  GROUP BY user_id
), customer_links AS (
  SELECT
    NULLIF(TRIM(customer_id), '') AS customer_id,
    COUNT(*) AS customer_record_count
  FROM `raylo-production.dbt_production.stg_raylo_production__customers`
  WHERE NULLIF(TRIM(customer_id), '') IS NOT NULL
  GROUP BY customer_id
), linked_observations AS (
  SELECT s.*, u.customer_id
  FROM source_observations s
  JOIN assessment_links a USING (assessment_id)
  JOIN checkout_links c ON a.checkout_count = 1 AND a.checkout_id = c.checkout_id
  JOIN user_links u ON c.user_count = 1 AND c.user_id = u.user_id
  JOIN customer_links cr
    ON u.customer_count = 1
    AND u.customer_id = cr.customer_id
    AND cr.customer_record_count = 1
), event_versions AS (
  SELECT
    account_id,
    transaction_id,
    ARRAY_AGG(
      STRUCT(customer_id, merchant, description, amount, is_credit, payload_sha256)
      ORDER BY assessment_id
      LIMIT 1
    )[OFFSET(0)] AS chosen
  FROM linked_observations
  GROUP BY account_id, transaction_id
  HAVING COUNT(DISTINCT payload_sha256) = 1
    AND COUNT(DISTINCT customer_id) = 1
)
SELECT
  account_id,
  transaction_id,
  chosen.customer_id AS customer_id,
  chosen.merchant AS merchant,
  chosen.description AS description,
  chosen.amount AS amount,
  chosen.is_credit AS is_credit,
  chosen.payload_sha256 AS source_payload_sha256
FROM event_versions
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY chosen.merchant
  ORDER BY TO_HEX(SHA256(CONCAT('tuning-v2:', account_id, ':', transaction_id)))
) <= {cap_per_merchant}
"""


def tier_b_role(merchant):
    """Assign a stable role that does not change when the merchant pool grows."""

    if not isinstance(merchant, str) or not merchant:
        raise ValueError("merchant is required")
    digest = hashlib.sha256(f"tuning-role-v1:{SEED}:{merchant}".encode()).digest()
    fraction = int.from_bytes(digest[:8], "big") / 2**64
    return "selection" if fraction < VAL_FRACTION else "train"


def fetch(cap_per_merchant, protected_memberships):
    protection = load_eval_protection(protected_memberships)
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

    CHUNK = 1500
    all_txns = []
    for i in range(0, len(eligible), CHUNK):
        part = eligible[i:i + CHUNK]
        print(f"Transaction fetch chunk {i // CHUNK + 1}/{(len(eligible) + CHUNK - 1) // CHUNK}...", file=sys.stderr)
        rows_json = bq_json(build_linked_tier_b_query(
            [r["merchant"] for r in part], cap_per_merchant
        ))
        all_txns += rows_json

    target_by_merchant = {r["merchant"]: r["target"] for r in eligible}
    for t in all_txns:
        t["target"] = target_by_merchant[t["merchant"]]

    all_txns, excluded = exclude_eval_membership(all_txns, protection)
    write_tier_b_fetch(all_txns, protection)
    print(
        f"Eval protection excluded {sum(excluded.values())} Tier-B rows "
        f"({excluded})",
        file=sys.stderr,
    )
    print(f"Wrote {len(all_txns)} transaction rows -> {TXNS_JSON}", file=sys.stderr)


def build(protected_memberships):
    from collections import Counter

    _, _, leaves, _, _ = load_crosswalk()
    system_prompt = build_system_prompt(leaves)
    SYSTEM_PROMPT_PATH.write_text(system_prompt)

    def to_example(merchant, description, amount, direction, target, membership):
        user_msg = (f"merchant: {merchant}\n"
                    f"description: {description}\n"
                    f"amount: {amount}\n"
                    f"direction: {direction}")
        return TrackedExample(
            messages={"messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
                {"role": "assistant", "content": target},
            ]},
            membership=membership,
        )

    # ---------- Tier B: production_labels, merchant-level split (unchanged mechanism) ----------
    txns = read_verified_tier_b_fetch(protected_memberships)
    rng = random.Random(SEED)
    merchants = sorted({t["merchant"] for t in txns})
    val_merchants = {merchant for merchant in merchants if tier_b_role(merchant) == "selection"}
    n_val = len(val_merchants)

    def tier_b_example(t):
        # BigQuery's JSON API returns INT64 fields as strings ("0"/"1"), and
        # "0" is truthy in Python -- a naive truthy check on t["is_credit"]
        # silently always takes the credit branch. Every row in the first
        # tuning attempt had direction=credit (should be ~0.5% credit).
        direction = "credit" if int(t["is_credit"]) else "debit"
        return to_example(
            t["merchant"],
            t["description"],
            t["amount"],
            direction,
            t["target"],
            exact_plaid_membership(source="tier_b_customer_linked_plaid", row=t),
        )

    train, val = [], []
    tier_a_preview = load_tier_a()
    # 2026-09-02: the risk-category gold set was described as "held out" but
    # 77.5% of its rows shared a merchant with Tier B (bookmakers/lenders are
    # tranche-4 merchants too), so the 86.1% risk bar was in-sample. Risk-gold
    # merchants are now excluded from Tier B, Tier A training rows and the
    # top-up, exactly like the frozen holdout merchants.
    risk_merchants = load_risk_merchants()
    n_risk_skipped = 0
    for t in txns:
        if t["merchant"] in tier_a_preview:
            continue  # Tier A supersedes Tier B for overlapping merchants
        if t["merchant"] in risk_merchants:
            n_risk_skipped += 1
            continue
        (val if t["merchant"] in val_merchants else train).append(tier_b_example(t))
    tier_b_target_counts = Counter(t["target"] for t in txns
                                   if t["merchant"] not in tier_a_preview
                                   and t["merchant"] not in risk_merchants)
    print(f"Tier B: skipped {n_risk_skipped} rows on {len(risk_merchants)} risk-gold merchants",
          file=sys.stderr)

    # ---------- Tier A: unified gold. Holdout merchants frozen from SLM_EVAL_CSV ----------
    tier_a = load_tier_a()
    holdout_merchants = frozen_holdout_merchants()
    conflicting = {m for m, rows in tier_a.items() if len({r["gold_leaf"] for r in rows}) > 1}

    tier_a_train_examples = []
    n_iter_eval_rows = 0
    n_risk_tier_a = 0
    for m, rows in tier_a.items():
        if m in holdout_merchants:
            n_iter_eval_rows += len(rows)
            continue
        if m in risk_merchants:
            n_risk_tier_a += len(rows)
            continue
        train_rows = [r for r in rows if r.get("role") != "iter_eval"]
        reps = OVERSAMPLE_FACTOR if m in conflicting else 1
        for r in train_rows:
            # Plaid's raw amount is signed (negative = credit) -- the system prompt promises
            # "amount (absolute value, GBP)" and direction carries the sign meaning separately.
            ex = to_example(r["merchant_raw"], r["description_raw"], abs(float(r["amount"])),
                             r["direction"], r["gold_leaf"],
                             unavailable_membership(
                                 source="tier_a_gold_transactions",
                                 row=r,
                                 provider=r.get("provider"),
                             ))
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
            if (_norm(r["merchant_raw"]) in (holdout_merchants | risk_merchants)
                    and r["gold_leaf"] not in STARVED_TOPUP_LEAVES):
                continue
            ex = to_example(r["merchant_raw"], r["description_raw"], abs(float(r["amount"])),
                            r["direction"], r["gold_leaf"],
                            unavailable_membership(
                                source="tuning_leaf_topup",
                                row=r,
                            ))
            topup_examples.append(ex)
            if r["gold_leaf"] in starved_topup:
                starved_topup[r["gold_leaf"]].append(ex)

    credit_examples = []
    for _f in (CREDIT_TOPUP_FILE, RISK_TOPUP_FILE):
      if _f.exists():
        for r in csv.DictReader(open(_f)):
            m = _norm(r.get("merchant_raw") or "")
            if m and m in (holdout_merchants | risk_merchants):
                continue
            if not r.get("gold_leaf") or r["gold_leaf"] not in leaves:
                continue
            credit_examples.append(to_example(
                r.get("merchant_raw") or "",
                r.get("description_raw") or "",
                abs(float(r["amount"])),
                r["direction"],
                r["gold_leaf"],
                unavailable_membership(
                    source=("tuning_credit_topup" if _f == CREDIT_TOPUP_FILE
                            else "tuning_risk_topup"),
                    row=r,
                    provider=r.get("provider"),
                ),
            ))
    print(f"Row-level tranche top-ups (credit + risk): {len(credit_examples)} rows", file=sys.stderr)

    train = train + tier_a_train_examples + topup_examples + credit_examples

    def _leaf_of(ex):
        return next(m["content"] for m in ex.messages["messages"] if m["role"] == "assistant")

    def _merchant_of(ex):
        user = next(m["content"] for m in ex.messages["messages"] if m["role"] == "user")
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

    membership_coverage = publish_training_export(
        train,
        val,
        train_path=TRAIN_JSONL,
        selection_path=VAL_JSONL,
        lookup_path=MEMBERSHIP_LOOKUP,
        coverage_path=MEMBERSHIP_COVERAGE,
    )

    all_targets = ([t["target"] for t in txns]
                   + [r["gold_leaf"] for m, rows in tier_a.items() if m not in holdout_merchants for r in rows]
                   + ([r["gold_leaf"] for r in csv.DictReader(open(TOPUP_FILE))] if TOPUP_FILE.exists() else [])
                   + ([r["gold_leaf"] for r in csv.DictReader(open(CREDIT_TOPUP_FILE))] if CREDIT_TOPUP_FILE.exists() else [])
                   + ([r["gold_leaf"] for r in csv.DictReader(open(RISK_TOPUP_FILE))] if RISK_TOPUP_FILE.exists() else []))
    target_counts = Counter(all_targets)
    print(f"Tier B: {len(txns)} txns ({len(tier_b_target_counts)} classes)", file=sys.stderr)
    print(f"Tier A: {n_risk_tier_a} rows on risk-gold merchants excluded", file=sys.stderr)
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
    print(f"Exact-ID membership lookup written to {MEMBERSHIP_LOOKUP} "
          f"({membership_coverage['permanent_unique_exact_transactions']} permanent unique "
          "transactions)", file=sys.stderr)
    print(f"Membership coverage written to {MEMBERSHIP_COVERAGE}", file=sys.stderr)


def upload(gcs_path):
    import subprocess
    gcs_path = gcs_path.rstrip("/")
    coverage = verify_training_export(
        train_path=TRAIN_JSONL,
        selection_path=VAL_JSONL,
        lookup_path=MEMBERSHIP_LOOKUP,
        coverage_path=MEMBERSHIP_COVERAGE,
    )
    uploads = (
        (MEMBERSHIP_LOOKUP, "membership_lookup.csv"),
        (TRAIN_JSONL, coverage["model_files"]["train"]["artifact_name"]),
        (VAL_JSONL, coverage["model_files"]["selection"]["artifact_name"]),
        # Commit marker last: consumers must verify all hashes before use.
        (MEMBERSHIP_COVERAGE, "membership_coverage.json"),
    )
    for source, destination in uploads:
        subprocess.run(
            ["gcloud", "storage", "cp", str(source), f"{gcs_path}/{destination}"],
            check=True,
        )
    print(f"Uploaded verified training export to {gcs_path}", file=sys.stderr)


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] not in {"fetch", "build", "upload"}:
        sys.exit(__doc__)
    if args[0] == "fetch":
        parser = argparse.ArgumentParser(prog="build_tuning_dataset.py fetch")
        parser.add_argument("cap_per_merchant", nargs="?", type=int, default=DEFAULT_CAP)
        parser.add_argument(
            "--protected-membership",
            action="append",
            type=pathlib.Path,
            required=True,
        )
        fetch_args = parser.parse_args(args[1:])
        fetch(fetch_args.cap_per_merchant, fetch_args.protected_membership)
    elif args[0] == "build":
        parser = argparse.ArgumentParser(prog="build_tuning_dataset.py build")
        parser.add_argument(
            "--protected-membership",
            action="append",
            type=pathlib.Path,
            required=True,
        )
        build_args = parser.parse_args(args[1:])
        build(build_args.protected_membership)
    elif args[0] == "upload":
        if len(args) < 2:
            sys.exit("usage: upload gs://BUCKET/PATH")
        upload(args[1])

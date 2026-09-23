"""Recover transaction identity for legacy TxCat-1 label files (2026-09-23).

Carlos's decision 3 for the retrain: labelled rows without provider IDs are
re-matched to BigQuery.  A row-level label that matches exactly one source
transaction keeps its label and gains that transaction's identity; anything
else is dropped.  Recovered rows then pass the canonical training-data
protection gate (B04, v2 release) and are receipted, so the retrain build can
consume them.  Outputs go to ignored ``outputs/retrain_inputs/`` only; IDs
never enter Git.

Sources:
- ``data/tuning_credit_topup.csv`` and ``data/tuning_risk_topup.csv``.  These
  are row-level labels sampled from
  ``dbt_production.credit_plaid_open_banking_transactions``, with a transaction
  date.  The match key is the raw merchant, raw description, signed amount to
  2 dp and date.
- ``data/tuning_leaf_topup.csv``.  Row-level labels with no date.  The match key
  is the raw merchant, raw description, absolute amount to 2 dp and direction.
  Rows that don't match exactly one Plaid transaction are dropped, including
  the Equifax-sourced ones.

The Plaid index resolves a row's customer in one of three ways: directly,
through checkout → user → customer, or through the approved linked chain used
by the guarded Tier-B fetch (transaction → risk assessment → checkout → user →
customer).  Each link must be unique; conflicting routes make the account
ambiguous, and it fails closed.  Rows that resolve to a protected event,
account, customer or protected user's checkout are dropped here, and the gate
then re-checks them.  When several source rows share a key, the label is kept
only if every candidate is clean and belongs to the same customer.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import pathlib
import sys
from collections import Counter, defaultdict

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src" / "transformer"))

import eval_protection  # noqa: E402
from build_corpus import PLAID, _run  # noqa: E402
from build_pretrain_guarded import CHECKOUTS, PROTECTED_TABLE, USERS, verify_protected_table  # noqa: E402

OUT = ROOT / "outputs" / "retrain_inputs"
CONSUMER = "recover_training_identity"
PURPOSE = "supervised_training"
SOURCES = {
    "tuning_credit_topup": ROOT / "data" / "tuning_credit_topup.csv",
    "tuning_risk_topup": ROOT / "data" / "tuning_risk_topup.csv",
    "tuning_leaf_topup": ROOT / "data" / "tuning_leaf_topup.csv",
}

PLAID_INDEX = f"""
WITH p AS (SELECT * FROM {PROTECTED_TABLE}),
c AS (SELECT TRIM(checkout_id) AS checkout_id, ANY_VALUE(TRIM(user_id)) AS user_id,
             COUNT(DISTINCT TRIM(user_id)) AS nu
      FROM {CHECKOUTS} WHERE NULLIF(TRIM(checkout_id), '') IS NOT NULL GROUP BY 1),
u AS (SELECT TRIM(user_id) AS user_id, ANY_VALUE(TRIM(customer_id)) AS customer_id,
             COUNT(DISTINCT TRIM(customer_id)) AS nc
      FROM {USERS} WHERE NULLIF(TRIM(user_id), '') IS NOT NULL GROUP BY 1),
protected_checkouts AS (
  SELECT checkout_id FROM c WHERE user_id IN (SELECT user_id FROM p WHERE user_id != '')
  UNION DISTINCT SELECT checkout_id FROM p WHERE checkout_id != ''),
-- The approved customer-linked chain used by the guarded Tier-B fetch:
-- transaction -> risk assessment -> checkout -> user -> customer, each unique.
chain AS (
  SELECT TRIM(i.account_id) AS account_id, TRIM(i.transaction_id) AS transaction_id,
         ANY_VALUE(u2.customer_id) AS customer_id, COUNT(DISTINCT u2.customer_id) AS nchain
  FROM `raylo-production.dbt_production.intermediate_credit_plaid_transactions` i
  JOIN (SELECT checkout_risk_assessment_result_id AS assessment_id,
               COUNT(DISTINCT checkout_id) AS nck, ANY_VALUE(TRIM(checkout_id)) AS checkout_id
        FROM `raylo-production.dbt_production.intermediate_raylo_production__checkout_risk_assessment_results_latest`
        WHERE NULLIF(TRIM(checkout_id), '') IS NOT NULL GROUP BY 1) a
    ON i.checkout_risk_assessment_result_id = a.assessment_id AND a.nck = 1
  JOIN c c2 ON a.checkout_id = c2.checkout_id AND c2.nu = 1
  JOIN u u2 ON c2.user_id = u2.user_id AND u2.nc = 1
  WHERE NULLIF(TRIM(i.account_id), '') IS NOT NULL AND NULLIF(TRIM(i.transaction_id), '') IS NOT NULL
  GROUP BY 1, 2),
r AS (
  SELECT TRIM(t.account_id) AS account_id, TRIM(t.transaction_id) AS transaction_id,
         COALESCE(NULLIF(TRIM(t.customer_id), ''),
                  IF(c.nu = 1 AND u.nc = 1, NULLIF(u.customer_id, ''), NULL),
                  IF(ch.nchain = 1, NULLIF(ch.customer_id, ''), NULL)) AS customer_id,
         NULLIF(TRIM(t.checkout_id), '') AS checkout_id,
         IFNULL(t.merchant_name, '') AS merchant_raw,
         IFNULL(COALESCE(t.original_description, t.transaction_name), '') AS description_raw,
         ROUND(t.amount, 2) AS amount, CAST(t.transaction_date AS STRING) AS transaction_date
  FROM {PLAID} t
  LEFT JOIN c ON TRIM(t.checkout_id) = c.checkout_id
  LEFT JOIN u ON c.user_id = u.user_id
  LEFT JOIN chain ch ON TRIM(t.account_id) = ch.account_id
                    AND TRIM(t.transaction_id) = ch.transaction_id),
acct AS (SELECT account_id, COUNT(DISTINCT customer_id) AS ncust FROM r
         WHERE customer_id IS NOT NULL GROUP BY 1)
SELECT r.account_id, r.transaction_id, r.customer_id, r.merchant_raw, r.description_raw,
       r.amount, r.transaction_date,
       CASE
         WHEN r.customer_id IS NULL THEN 'unlinked_customer'
         WHEN acct.ncust > 1 THEN 'ambiguous_account'
         WHEN TO_HEX(SHA256(CONCAT('plaid:', r.account_id, ':', r.transaction_id)))
              IN (SELECT event_key FROM p) THEN 'protected_event'
         WHEN r.account_id IN (SELECT account_id FROM p) THEN 'protected_account'
         WHEN r.customer_id IN (SELECT customer_id FROM p) THEN 'protected_customer'
         WHEN r.checkout_id IN (SELECT checkout_id FROM protected_checkouts)
           THEN 'protected_user_checkout'
         ELSE NULL END AS drop_reason
FROM r LEFT JOIN acct USING (account_id)
"""


def _money(value) -> str:
    return f"{round(float(value), 2):.2f}"


def load_index() -> pd.DataFrame:
    df = _run(PLAID_INDEX, "recover/plaid-index")
    df["amount_2dp"] = [_money(a) for a in df["amount"]]
    df["abs_2dp"] = [_money(abs(float(a))) for a in df["amount"]]
    df["direction"] = ["credit" if float(a) < 0 else "debit" for a in df["amount"]]
    return df


def recover(name: str, path: pathlib.Path, index: pd.DataFrame):
    dated = name != "tuning_leaf_topup"
    if dated:
        keys = zip(index.merchant_raw, index.description_raw, index.amount_2dp, index.transaction_date)
    else:
        keys = zip(index.merchant_raw, index.description_raw, index.abs_2dp, index.direction)
    lookup: dict[tuple, list[int]] = defaultdict(list)
    for position, key in enumerate(keys):
        lookup[key].append(position)
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    outcomes: Counter = Counter()
    recovered = []
    seen_events = set()
    for row in rows:
        if dated:
            key = (
                row["merchant_raw"] or "",
                row["description_raw"] or "",
                _money(row["amount"]),
                (row.get("transaction_date") or "")[:10],
            )
        else:
            key = (
                row["merchant_raw"] or "",
                row["description_raw"] or "",
                _money(abs(float(row["amount"]))),
                row["direction"],
            )
        hits = lookup.get(key, [])
        if not hits:
            outcomes["unmatched"] += 1
            continue
        candidates = index.iloc[hits]
        flagged = candidates.drop_reason.notna()
        if len(hits) > 1:
            # Several source rows with the same key: accept only when every
            # candidate is clean and they all belong to one customer (the same
            # transaction repeated across reports or that customer's accounts).
            if flagged.any() or candidates.customer_id.nunique() != 1:
                outcomes["ambiguous_match"] += 1
                continue
            outcomes["recovered_repeated_same_customer"] += 1
            match = candidates.sort_values(["account_id", "transaction_id"]).iloc[0]
        else:
            match = candidates.iloc[0]
            if flagged.iloc[0]:
                outcomes[f"dropped_{match.drop_reason}"] += 1
                continue
        event = (match.account_id, match.transaction_id)
        if event in seen_events:
            outcomes["duplicate_event"] += 1
            continue
        seen_events.add(event)
        outcomes["recovered"] += 1
        recovered.append(
            {
                **row,
                "provider": "plaid",
                "account_id": match.account_id,
                "transaction_id": match.transaction_id,
                "customer_id": match.customer_id,
                "source_row_sha256": hashlib.sha256(
                    json.dumps(row, sort_keys=True, ensure_ascii=False).encode()
                ).hexdigest(),
            }
        )
    return recovered, outcomes, len(rows)


CONSENSUS = ROOT / "data" / "distillation_labels_consensus.parquet"


def recover_consensus(index: pd.DataFrame, args, out: pathlib.Path) -> dict:
    """Text-level consensus labels (stage 1): keep a text only with a clean witness.

    These labels belong to a distinct (merchant, description, direction) text,
    not to one transaction.  A text is kept when at least one clean,
    customer-linked, unprotected transaction carries it.  That transaction
    becomes its representative identity, chosen deterministically, for the
    gate.  Texts equal to any protected transaction's text are dropped.
    """

    from build_pretrain_guarded import protected_texts  # noqa: PLC0415

    blocked = protected_texts()
    clean = index[index.drop_reason.isna()]
    witness = {}
    for m, d, direction, account, txn, customer in sorted(
        zip(
            clean.merchant_raw.str.strip().str.lower(),
            clean.description_raw.str.strip().str.lower(),
            clean.direction,
            clean.account_id,
            clean.transaction_id,
            clean.customer_id,
        ),
        key=lambda t: (t[0], t[1], t[2], t[3], t[4]),
    ):
        witness.setdefault((direction, m, d), (account, txn, customer))
    labels = pd.read_parquet(CONSENSUS)
    outcomes: Counter = Counter()
    kept = []
    for row in labels.to_dict("records"):
        key = (row["direction"], row["merchant"], row["description"])
        if key in blocked:
            outcomes["dropped_protected_text"] += 1
            continue
        hit = witness.get(key)
        if hit is None:
            outcomes["dropped_no_clean_transaction"] += 1
            continue
        outcomes["kept"] += 1
        kept.append(
            {
                **row,
                "provider": "plaid",
                "account_id": hit[0],
                "transaction_id": hit[1],
                "customer_id": hit[2],
            }
        )
    # Decision 2 and the shared conventions: these are LLM consensus labels, so
    # where the staging bundle's T1-T5 rules decide a text, the rule's leaf wins.
    from build_tuning_dataset_retrain import label  # noqa: PLC0415
    from raylo_txncat import label_conventions  # noqa: PLC0415

    rules = label(
        [
            {
                "merchant": r["merchant_raw"] or r["merchant"],
                "description": r["description_raw"] or r["description"],
                "is_credit": 1 if r["direction"] == "credit" else 0,
                "native_category": r.get("native_category"),
            }
            for r in kept
        ],
        args.rules_root,
    )
    for row, lab in zip(kept, rules, strict=True):
        row["original_final_leaf"] = row["final_leaf"]
        if lab["leaf"] and lab["leaf"] != row["final_leaf"]:
            outcomes["rule_override"] += 1
            row["final_leaf"] = lab["leaf"]
        hit = label_conventions.general_rule(
            row["merchant_raw"], row["description_raw"], row["direction"], "labelled",
            row["final_leaf"],
        )
        if hit and hit[2] and hit[2] != row["final_leaf"]:
            outcomes[f"convention_{hit[0]}"] += 1
            row["final_leaf"] = hit[2]
    guarded = eval_protection.apply(kept, args, purpose="distillation")
    if len(guarded) != len(kept):
        raise RuntimeError("consensus: the gate excluded rows the index kept; stopping")
    target = out / "distillation_labels_consensus.parquet"
    pd.DataFrame(list(guarded)).to_parquet(target, index=False)
    os.chmod(target, 0o600)
    receipt = eval_protection.write_artifact_receipt(
        target, consumer=CONSUMER, purpose="distillation", guard=guarded.guard
    )
    print(f"consensus: {len(guarded):,}/{len(labels):,} kept {dict(outcomes)}", file=sys.stderr)
    return {
        "source_file_sha256": hashlib.sha256(CONSENSUS.read_bytes()).hexdigest(),
        "source_rows": len(labels),
        "outcomes": dict(outcomes),
        "recovered_rows": len(guarded),
        "output": target.name,
        "output_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "receipt": receipt.name,
    }


def main() -> None:
    parser = eval_protection.add_args(argparse.ArgumentParser(description=__doc__))
    parser.add_argument("--output", type=pathlib.Path, default=OUT)
    parser.add_argument(
        "--rules-root",
        type=pathlib.Path,
        help="Staging bundle's research checkout, for the consensus rule override",
    )
    parser.add_argument(
        "--consensus-only",
        action="store_true",
        help="Recover only the stage-1 consensus labels into an existing output directory",
    )
    args = parser.parse_args()
    if args.consensus_only:
        if args.rules_root is None:
            raise SystemExit("--rules-root is required for the consensus rule override")
        protection, _publication = eval_protection.load_release(args)
        verify_protected_table(protection)
        report_path = args.output / "RECOVERY.json"
        report = json.loads(report_path.read_text())
        report["sources"]["distillation_labels_consensus"] = recover_consensus(
            load_index(), args, args.output
        )
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        return
    protection, _publication = eval_protection.load_release(args)
    table_check = verify_protected_table(protection)
    index = load_index()
    out = args.output
    out.mkdir(parents=True, exist_ok=False)
    os.chmod(out, 0o700)
    report = {
        "schema_version": "training-identity-recovery-v1",
        "protected_release": eval_protection.PINNED_BINDING,
        "protected_table_check": table_check,
        "plaid_index_rows": len(index),
        "plaid_index_drop_reasons": {
            str(k): int(v) for k, v in index.drop_reason.fillna("kept").value_counts().items()
        },
        "sources": {},
        "authorizes_consumption": False,
    }
    for name, path in SOURCES.items():
        recovered, outcomes, total = recover(name, path, index)
        guarded = eval_protection.apply(recovered, args, purpose=PURPOSE)
        if len(guarded) != len(recovered):
            raise RuntimeError(f"{name}: the gate excluded rows the index kept; stopping")
        target = out / f"{name}.csv"
        with target.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(recovered[0].keys()))
            writer.writeheader()
            writer.writerows(guarded)
        os.chmod(target, 0o600)
        receipt = eval_protection.write_artifact_receipt(
            target, consumer=CONSUMER, purpose=PURPOSE, guard=guarded.guard
        )
        report["sources"][name] = {
            "source_file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "source_rows": total,
            "outcomes": dict(outcomes),
            "recovered_rows": len(guarded),
            "output": target.name,
            "output_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            "receipt": receipt.name,
        }
        print(f"{name}: {len(guarded):,}/{total:,} recovered {dict(outcomes)}", file=sys.stderr)
    (out / "RECOVERY.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report["sources"], indent=1))


if __name__ == "__main__":
    main()

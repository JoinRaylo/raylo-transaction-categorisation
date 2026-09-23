"""Recover legacy label identity against the 39M-row customer-linked Plaid source.

Second pass of ``recover_training_identity.py`` (2026-09-23).  The first pass
matched against ``credit_plaid_open_banking_transactions`` (4.28M rows, 43%
without a customer link) and dropped already-paid labels as unlinked.  This
pass matches against ``intermediate_credit_plaid_transactions``, where every
row resolves to a customer through the approved linked chain used by the
guarded Tier-B fetch (transaction → risk assessment → checkout → user →
customer, each link unique).

No narrative text leaves the machine.  Only SHA-256 hashes of each label row's
match key are uploaded, to a private table that expires after one day.
BigQuery hashes the linked rows the same way, trying both the ``description``
and ``transaction_name`` narratives.  It applies the protected-release
exclusions and returns per-key summaries.

The acceptance rules are unchanged:
- **Row-level top-ups.**  Exactly one customer, and no protected or ambiguous
  candidate.
- **Text-level consensus labels.**  At least one clean witness.

Recovered rows keep their first-pass identity when they have one.  They then
go through the canonical gate and are receipted, as in the first pass.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import tempfile
from collections import Counter

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src" / "transformer"))

import eval_protection  # noqa: E402
import recover_training_identity as first  # noqa: E402
from build_corpus import _run  # noqa: E402
from build_pretrain_guarded import CHECKOUTS, PROTECTED_TABLE, USERS, verify_protected_table  # noqa: E402

DATASET = "raylo-production:txncat_eval_protected"
KEY_TABLE = "retrain_label_key_hashes_20260923"
SEP = "\x1f"


def _h(*parts: str) -> str:
    return hashlib.sha256(SEP.join(parts).encode("utf-8")).hexdigest()


def row_key(row: dict) -> str:
    return _h(
        row["merchant_raw"] or "",
        row["description_raw"] or "",
        first._money(row["amount"]),
        (row.get("transaction_date") or "")[:10],
    )


def text_key(direction: str, merchant: str, description: str) -> str:
    return _h(direction, (merchant or "").strip().lower(), (description or "").strip().lower())


MATCH_SQL = f"""
WITH k AS (SELECT kind, key_hash FROM `raylo-production.txncat_eval_protected.{KEY_TABLE}`),
p AS (SELECT * FROM {PROTECTED_TABLE}),
c AS (SELECT TRIM(checkout_id) AS checkout_id, ANY_VALUE(TRIM(user_id)) AS user_id,
             COUNT(DISTINCT TRIM(user_id)) AS nu
      FROM {CHECKOUTS} WHERE NULLIF(TRIM(checkout_id), '') IS NOT NULL GROUP BY 1),
u AS (SELECT TRIM(user_id) AS user_id, ANY_VALUE(TRIM(customer_id)) AS customer_id,
             COUNT(DISTINCT TRIM(customer_id)) AS nc
      FROM {USERS} WHERE NULLIF(TRIM(user_id), '') IS NOT NULL GROUP BY 1),
a AS (SELECT checkout_risk_assessment_result_id AS assessment_id,
             COUNT(DISTINCT checkout_id) AS nck, ANY_VALUE(TRIM(checkout_id)) AS checkout_id
      FROM `raylo-production.dbt_production.intermediate_raylo_production__checkout_risk_assessment_results_latest`
      WHERE NULLIF(TRIM(checkout_id), '') IS NOT NULL GROUP BY 1),
protected_checkouts AS (
  SELECT checkout_id FROM c WHERE user_id IN (SELECT user_id FROM p WHERE user_id != '')
  UNION DISTINCT SELECT checkout_id FROM p WHERE checkout_id != ''),
r AS (
  SELECT TRIM(i.account_id) AS account_id, TRIM(i.transaction_id) AS transaction_id,
         IF(a.nck = 1 AND c.nu = 1 AND u.nc = 1, NULLIF(u.customer_id, ''), NULL) AS customer_id,
         a.checkout_id,
         IFNULL(i.merchant_name, '') AS merchant_raw, IFNULL(i.description, '') AS d1,
         IFNULL(i.transaction_name, '') AS d2, ROUND(i.amount, 2) AS amount,
         CAST(i.transaction_date AS STRING) AS transaction_date,
         IF(i.amount < 0, 'credit', 'debit') AS direction
  FROM `raylo-production.dbt_production.intermediate_credit_plaid_transactions` i
  LEFT JOIN a ON i.checkout_risk_assessment_result_id = a.assessment_id
  LEFT JOIN c ON a.checkout_id = c.checkout_id
  LEFT JOIN u ON c.user_id = u.user_id
  WHERE NULLIF(TRIM(i.account_id), '') IS NOT NULL AND NULLIF(TRIM(i.transaction_id), '') IS NOT NULL),
acct AS (SELECT account_id, COUNT(DISTINCT customer_id) AS ncust FROM r
         WHERE customer_id IS NOT NULL GROUP BY 1),
flagged AS (
  SELECT r.*, CASE
    WHEN r.customer_id IS NULL THEN 'unlinked_customer'
    WHEN acct.ncust > 1 THEN 'ambiguous_account'
    WHEN TO_HEX(SHA256(CONCAT('plaid:', r.account_id, ':', r.transaction_id)))
         IN (SELECT event_key FROM p) THEN 'protected_event'
    WHEN r.account_id IN (SELECT account_id FROM p) THEN 'protected_account'
    WHEN r.customer_id IN (SELECT customer_id FROM p) THEN 'protected_customer'
    WHEN r.checkout_id IN (SELECT checkout_id FROM protected_checkouts) THEN 'protected_user_checkout'
    ELSE NULL END AS drop_reason
  FROM r LEFT JOIN acct USING (account_id)),
hashed AS (
  SELECT f.*, 'row' AS kind, h AS key_hash FROM flagged f,
    UNNEST([
      TO_HEX(SHA256(CONCAT(merchant_raw, '{SEP}', d1, '{SEP}', FORMAT('%.2f', amount), '{SEP}',
                           transaction_date))),
      TO_HEX(SHA256(CONCAT(merchant_raw, '{SEP}', d2, '{SEP}', FORMAT('%.2f', amount), '{SEP}',
                           transaction_date)))]) AS h
  UNION ALL
  SELECT f.*, 'text' AS kind, h AS key_hash FROM flagged f,
    UNNEST([
      TO_HEX(SHA256(CONCAT(direction, '{SEP}', LOWER(TRIM(merchant_raw)), '{SEP}', LOWER(TRIM(d1))))),
      TO_HEX(SHA256(CONCAT(direction, '{SEP}', LOWER(TRIM(merchant_raw)), '{SEP}', LOWER(TRIM(d2)))))
    ]) AS h),
m AS (SELECT DISTINCT hashed.* EXCEPT (d1, d2) FROM hashed JOIN k USING (kind, key_hash))
SELECT kind, key_hash,
       COUNT(DISTINCT CONCAT(account_id, ':', transaction_id)) AS candidates,
       COUNT(DISTINCT customer_id) AS customers,
       COUNTIF(drop_reason IS NOT NULL) AS flagged,
       ARRAY_AGG(IF(drop_reason IS NULL, STRUCT(account_id, transaction_id, customer_id), NULL)
                 IGNORE NULLS ORDER BY account_id, transaction_id LIMIT 1) AS clean,
       ARRAY_AGG(DISTINCT IFNULL(drop_reason, 'clean')) AS reasons
FROM m GROUP BY kind, key_hash
"""


def upload_keys(keys: list[tuple[str, str]]) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as stream:
        writer = csv.writer(stream)
        writer.writerow(["kind", "key_hash"])
        writer.writerows(sorted(set(keys)))
        path = stream.name
    try:
        subprocess.run(
            ["bq", "--location=EU", "load", "--replace", "--source_format=CSV",
             "--skip_leading_rows=1", f"{DATASET}.{KEY_TABLE}", path,
             "kind:STRING,key_hash:STRING"],
            check=True, capture_output=True, text=True,
        )
        subprocess.run(
            ["bq", "update", "--expiration", "86400",
             "--set_label", "contains_pii:hashed", "--set_label", "purpose:retrain-identity-recovery",
             "--description", "SHA-256 hashes of TxCat-1 retrain label match keys (no text); "
             "expires after one day.", f"{DATASET}.{KEY_TABLE}"],
            check=True, capture_output=True, text=True,
        )
    finally:
        os.unlink(path)


def main() -> None:
    parser = eval_protection.add_args(argparse.ArgumentParser(description=__doc__))
    parser.add_argument("--rules-root", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path, default=first.OUT.parent / "retrain_inputs_v2")
    args = parser.parse_args()
    protection, _publication = eval_protection.load_release(args)
    table_check = verify_protected_table(protection)

    sources = {name: list(csv.DictReader(open(path, newline="", encoding="utf-8")))
               for name, path in first.SOURCES.items() if name != "tuning_leaf_topup"}
    consensus = pd.read_parquet(first.CONSENSUS).to_dict("records")
    keys = [("row", row_key(r)) for rows in sources.values() for r in rows]
    keys += [("text", text_key(r["direction"], r["merchant"], r["description"])) for r in consensus]
    upload_keys(keys)
    matches = _run(MATCH_SQL, "recover-linked/match")
    by = {(m.kind, m.key_hash): m for m in matches.itertuples()}

    out = args.output
    out.mkdir(parents=True, exist_ok=False)
    os.chmod(out, 0o700)
    report = {"schema_version": "training-identity-recovery-linked-v1",
              "protected_release": eval_protection.PINNED_BINDING,
              "protected_table_check": table_check, "key_table": f"{DATASET}.{KEY_TABLE}",
              "sources": {}, "authorizes_consumption": False}

    # Row-level top-ups: first-pass identity if any, else exactly one clean customer.
    previous = {}
    for name in sources:
        path = first.OUT / f"{name}.csv"
        if path.exists():
            for r in csv.DictReader(open(path, newline="", encoding="utf-8")):
                previous[(name, r["source_row_sha256"])] = r
    for name, rows in sources.items():
        outcomes, kept, seen = Counter(), [], set()
        for row in rows:
            digest = hashlib.sha256(json.dumps(row, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            prior = previous.get((name, digest))
            if prior is not None:
                ident = (prior["account_id"], prior["transaction_id"], prior["customer_id"])
                outcomes["first_pass"] += 1
            else:
                m = by.get(("row", row_key(row)))
                if m is None:
                    outcomes["unmatched"] += 1
                    continue
                if m.flagged or m.customers != 1 or m.clean is None or len(m.clean) == 0:
                    outcomes["ambiguous_or_flagged"] += 1
                    continue
                c = m.clean[0]
                ident = (c["account_id"], c["transaction_id"], c["customer_id"])
                outcomes["linked_pass"] += 1
            if ident[:2] in seen:
                outcomes["duplicate_event"] += 1
                continue
            seen.add(ident[:2])
            kept.append({**row, "provider": "plaid", "account_id": ident[0],
                         "transaction_id": ident[1], "customer_id": ident[2],
                         "source_row_sha256": digest})
        guarded = eval_protection.apply(kept, args, purpose=first.PURPOSE)
        if len(guarded) != len(kept):
            raise RuntimeError(f"{name}: the gate excluded rows the index kept; stopping")
        target = out / f"{name}.csv"
        with target.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(kept[0].keys()))
            writer.writeheader()
            writer.writerows(guarded)
        os.chmod(target, 0o600)
        receipt = eval_protection.write_artifact_receipt(
            target, consumer=first.CONSUMER, purpose=first.PURPOSE, guard=guarded.guard
        )
        report["sources"][name] = {"source_rows": len(rows), "recovered_rows": len(guarded),
                                   "outcomes": dict(outcomes), "receipt": receipt.name}
        print(f"{name}: {len(guarded):,}/{len(rows):,} {dict(outcomes)}", file=sys.stderr)

    # The leaf top-up has no date; carry its first-pass file forward unchanged.
    leaf = first.OUT / "tuning_leaf_topup.csv"
    rows = list(csv.DictReader(open(leaf, newline="", encoding="utf-8")))
    guarded = eval_protection.apply(rows, args, purpose=first.PURPOSE)
    target = out / "tuning_leaf_topup.csv"
    with target.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(guarded)
    os.chmod(target, 0o600)
    receipt = eval_protection.write_artifact_receipt(
        target, consumer=first.CONSUMER, purpose=first.PURPOSE, guard=guarded.guard
    )
    report["sources"]["tuning_leaf_topup"] = {"recovered_rows": len(guarded),
                                              "outcomes": {"first_pass_carried": len(guarded)},
                                              "receipt": receipt.name}

    # Text-level consensus: a clean witness from either pass.
    from build_pretrain_guarded import protected_texts  # noqa: PLC0415
    from build_tuning_dataset_retrain import label  # noqa: PLC0415
    from raylo_txncat import label_conventions  # noqa: PLC0415

    blocked = protected_texts()
    prior = {(r["direction"], r["merchant"], r["description"]): r
             for r in pd.read_parquet(first.OUT / "distillation_labels_consensus.parquet")
             .to_dict("records")}
    outcomes, kept = Counter(), []
    for row in consensus:
        key = (row["direction"], row["merchant"], row["description"])
        if key in blocked:
            outcomes["dropped_protected_text"] += 1
            continue
        if key in prior:
            kept.append(prior[key])
            outcomes["first_pass"] += 1
            continue
        m = by.get(("text", text_key(*key)))
        if m is None or m.clean is None or len(m.clean) == 0:
            outcomes["dropped_no_clean_transaction"] += 1
            continue
        c = m.clean[0]
        new = {**row, "provider": "plaid", "account_id": c["account_id"],
               "transaction_id": c["transaction_id"], "customer_id": c["customer_id"],
               "original_final_leaf": row["final_leaf"]}
        kept.append(new)
        outcomes["linked_pass"] += 1
    fresh = [r for r in kept if r.get("original_final_leaf") == r["final_leaf"]
             and (r["direction"], r["merchant"], r["description"]) not in prior]
    rules = label([{"merchant": r["merchant_raw"] or r["merchant"],
                    "description": r["description_raw"] or r["description"],
                    "is_credit": 1 if r["direction"] == "credit" else 0,
                    "native_category": r.get("native_category")} for r in fresh], args.rules_root)
    for row, lab in zip(fresh, rules, strict=True):
        if lab["leaf"] and lab["leaf"] != row["final_leaf"]:
            outcomes["rule_override"] += 1
            row["final_leaf"] = lab["leaf"]
        hit = label_conventions.general_rule(row["merchant_raw"], row["description_raw"],
                                             row["direction"], "labelled", row["final_leaf"])
        if hit and hit[2] and hit[2] != row["final_leaf"]:
            outcomes[f"convention_{hit[0]}"] += 1
            row["final_leaf"] = hit[2]
    seen, unique = set(), []
    for r in kept:
        event = (r["account_id"], r["transaction_id"])
        if event in seen:
            outcomes["duplicate_witness_dropped"] += 1
            continue
        seen.add(event)
        unique.append(r)
    guarded = eval_protection.apply(unique, args, purpose="distillation")
    if len(guarded) != len(unique):
        raise RuntimeError("consensus: the gate excluded rows the index kept; stopping")
    target = out / "distillation_labels_consensus.parquet"
    pd.DataFrame(list(guarded)).to_parquet(target, index=False)
    os.chmod(target, 0o600)
    receipt = eval_protection.write_artifact_receipt(
        target, consumer=first.CONSUMER, purpose="distillation", guard=guarded.guard
    )
    report["sources"]["distillation_labels_consensus"] = {
        "source_rows": len(consensus), "recovered_rows": len(guarded),
        "outcomes": dict(outcomes), "receipt": receipt.name}
    print(f"consensus: {len(guarded):,}/{len(consensus):,} {dict(outcomes)}", file=sys.stderr)
    (out / "RECOVERY.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()

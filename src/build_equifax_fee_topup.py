"""Append Equifax fee/distress narratives to data/tuning_leaf_topup.csv.

Training only — never gold eval. Plaid does not emit these mechanism/fee
subcategories, so T5b can only learn them from Equifax Description text
that looks like a live bank narrative.

Pulls:
  cash_advance_fee      SubCategory = Cash Advance Fees, debit, non-empty narrative
  overdraft_unarranged  SubCategory = Unarranged Overdraft, debit, non-empty narrative
  balance_transfer      Primary = Balance Transfers, debit, narrative must say
                        'balance transfer' (drops empty/GB and unrelated strings)

Does NOT pull loan_repayment_dd (lender-side 'THANK YOU' credits).

Usage:
    python src/build_equifax_fee_topup.py
"""
from __future__ import annotations

import csv
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from ml_baseline import bq_client  # noqa: E402

FINAL_CSV = ROOT / "data" / "tuning_leaf_topup.csv"
BT_PAT = re.compile(r"balance\s*transfer", re.I)
FIELDNAMES = ["merchant_raw", "description_raw", "amount", "direction",
              "native_category", "gold_leaf", "target_leaf"]


def _norm(s):
    return (s or "").strip().lower()


def _amt_key(v):
    try:
        return f"{round(float(v), 2):.2f}"
    except (TypeError, ValueError):
        return str(v or "")


def _fp(r):
    return (_norm(r["merchant_raw"]), _norm(r["description_raw"]),
            _amt_key(r.get("amount")), (r.get("direction") or "").lower(), r["gold_leaf"])


QUERY = r"""
SELECT
  IFNULL(VendorDescription, '') AS merchant_raw,
  Description AS description_raw,
  Amount AS amount,
  IF(TransactionTypeId = 1, 'credit', 'debit') AS direction,
  CONCAT(IFNULL(PrimaryCategoryDescription, ''), ' | ', IFNULL(SubCategoryDescription, '')) AS native_category,
  CASE
    WHEN SubCategoryDescription = 'Cash Advance Fees' THEN 'cash_advance_fee'
    WHEN SubCategoryDescription = 'Unarranged Overdraft' THEN 'overdraft_unarranged'
    WHEN PrimaryCategoryDescription = 'Balance Transfers' THEN 'balance_transfer'
  END AS gold_leaf
FROM `raylo-production.equifax_data.open_banking_full_dump`
WHERE TransactionTypeId = 2
  AND Description IS NOT NULL
  AND TRIM(Description) NOT IN ('', 'GB')
  AND (
    SubCategoryDescription IN ('Cash Advance Fees', 'Unarranged Overdraft')
    OR (
      PrimaryCategoryDescription = 'Balance Transfers'
      AND REGEXP_CONTAINS(Description, r'(?i)balance\s*transfer')
    )
  )
"""


def main():
    print("Fetching Equifax fee/distress rows...", file=sys.stderr)
    df = bq_client().query(QUERY).result().to_dataframe()
    rows = []
    for r in df.to_dict("records"):
        leaf = r["gold_leaf"]
        if not leaf:
            continue
        desc = r["description_raw"] or ""
        if leaf == "balance_transfer" and not BT_PAT.search(desc):
            continue
        rows.append({
            "merchant_raw": r["merchant_raw"] or "",
            "description_raw": desc,
            "amount": abs(float(r["amount"] or 0)),
            "direction": "debit",
            "native_category": r["native_category"],
            "gold_leaf": leaf,
            "target_leaf": leaf,
        })

    existing = list(csv.DictReader(open(FINAL_CSV))) if FINAL_CSV.exists() else []
    seen = {_fp(r) for r in existing}
    added = []
    for r in rows:
        fp = _fp(r)
        if fp in seen:
            continue
        seen.add(fp)
        added.append(r)

    with open(FINAL_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        w.writeheader()
        w.writerows(existing)
        w.writerows(added)

    from collections import Counter
    by_leaf = Counter(r["gold_leaf"] for r in added)
    print(f"Fetched {len(rows)} usable Equifax rows; appended {len(added)} new "
          f"(skipped {len(rows) - len(added)} already in top-up)", file=sys.stderr)
    for leaf, n in sorted(by_leaf.items()):
        print(f"  +{n} {leaf}", file=sys.stderr)
    print(f"Top-up file now {len(existing) + len(added)} rows -> {FINAL_CSV}", file=sys.stderr)


if __name__ == "__main__":
    main()

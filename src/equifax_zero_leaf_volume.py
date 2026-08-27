"""Equifax dump volume for taxonomy leaves that currently have 0 training rows."""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from ml_baseline import bq_client  # noqa: E402

SUBS = [
    "Account Misuse", "Cash Advance Fees", "Unarranged Overdraft", "Money Management",
    "Direct Debit Repayments", "Balance Transfer Fees", "Credit Card Fees",
    "Money Transfer Fees", "Cheques", "Audio Equipment", "Camping Equipment",
    "Emergency Services", "Housing Benefits", "Interest Charge",
    "Office Equipment", "Office Electricals", "Bank Interest Accrual",
    "Prepaid Cards", "Money Transfers",
]
PRIS = [
    "Balance Transfers", "Adjustments", "Bank Charges and Returns",
    "Rent and Mortgage", "Interest Payments", "Interest",
    "Interests and Dividends", "Misc Regular Payments", "Transfers / Other",
]


def sql_list(vals):
    return ", ".join("'" + v.replace("'", "\\'") + "'" for v in vals)


query = f"""
SELECT
  SubCategoryDescription AS sub,
  PrimaryCategoryDescription AS pri,
  IF(TransactionTypeId=1,'credit','debit') AS direction,
  COUNT(*) AS n,
  COUNTIF(Description IS NOT NULL AND TRIM(Description) NOT IN ('','GB')) AS n_narrative
FROM `raylo-production.equifax_data.open_banking_full_dump`
WHERE SubCategoryDescription IN ({sql_list(SUBS)})
   OR PrimaryCategoryDescription IN ({sql_list(PRIS)})
GROUP BY 1, 2, 3
ORDER BY n DESC
"""

print("Querying Equifax dump...", file=sys.stderr)
df = bq_client().query(query).result().to_dataframe()
print(df.to_string(index=False))
out = ROOT / "outputs" / "equifax_zero_leaf_volume.csv"
df.to_csv(out, index=False)
print(f"\nWrote {out}", file=sys.stderr)

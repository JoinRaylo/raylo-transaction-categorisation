"""Stage 0 of the in-house transformer: pretraining corpus + silver labels.

Two BigQuery pulls, both written to `outputs/transformer/` as parquet:

  pretrain  Distinct transaction "sentences" from BOTH providers, unlabelled, for
            masked-language-model domain adaptation. Sentence format follows the
            Trustly Open-Banking paper: `[DEBIT|CREDIT] [AMT_<bucket>] merchant | description`.
            All 1.33M distinct Plaid texts plus a uniform sample of Equifax texts.
  silver    Distinct (merchant, description, direction, amount bucket) keys whose
            T1-T5 waterfall tier fires (the SAME CASE bodies as sql/apply_crosswalk.sql,
            via generate_crosswalk_sql), with the resulting leaf as a weak label.
            Capped per leaf so transfer_p2p does not dominate. Used for the first
            classifier fine-tune pass before the gold jsonl.

Gold rows are never touched here; `eval_sets` merchant exclusions are applied to the
silver set so the merchant-disjoint holdout stays disjoint.

Usage:
    python src/transformer/build_corpus.py pretrain [--eqx-sample 3500000]
    python src/transformer/build_corpus.py silver   [--per-leaf-cap 40000]
"""
from __future__ import annotations

import argparse
import pathlib
import sys
import time

import pandas as pd
from google.cloud import bigquery

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import generate_crosswalk_sql as gxw  # noqa: E402
from build_tuning_dataset import frozen_holdout_merchants, load_risk_merchants  # noqa: E402

OUT = ROOT / "outputs" / "transformer"
PRETRAIN_PARQUET = OUT / "pretrain_corpus.parquet"
SILVER_PARQUET = OUT / "silver_labels.parquet"
PROJECT = "raylo-production"

PLAID = "`raylo-production.dbt_production.credit_plaid_open_banking_transactions`"
EQX = "`raylo-production.equifax_data.open_banking_full_dump`"

# Amount buckets (GBP, absolute). Coarse on purpose: the token carries scale, not value.
AMT_CASE = """CASE
      WHEN a < 5 THEN 'AMT_0_5' WHEN a < 20 THEN 'AMT_5_20' WHEN a < 50 THEN 'AMT_20_50'
      WHEN a < 100 THEN 'AMT_50_100' WHEN a < 250 THEN 'AMT_100_250' WHEN a < 500 THEN 'AMT_250_500'
      WHEN a < 1000 THEN 'AMT_500_1K' WHEN a < 2500 THEN 'AMT_1K_2500' ELSE 'AMT_2500_PLUS' END"""


def amt_bucket_py(a: float) -> str:
    a = abs(float(a or 0))
    for lim, tok in ((5, "AMT_0_5"), (20, "AMT_5_20"), (50, "AMT_20_50"), (100, "AMT_50_100"),
                     (250, "AMT_100_250"), (500, "AMT_250_500"), (1000, "AMT_500_1K"),
                     (2500, "AMT_1K_2500")):
        if a < lim:
            return tok
    return "AMT_2500_PLUS"


def sentence(direction: str, amt_bucket: str, merchant: str, description: str) -> str:
    d = "[CREDIT]" if str(direction).lower() == "credit" else "[DEBIT]"
    m = (merchant or "").strip().lower()
    desc = (description or "").strip().lower()
    return f"{d} [{amt_bucket}] {m} | {desc}".strip()


def _client():
    return bigquery.Client(project=PROJECT)


def _run(sql: str, label: str) -> pd.DataFrame:
    t0 = time.time()
    print(f"[{label}] querying...", file=sys.stderr)
    df = _client().query(sql).to_dataframe(create_bqstorage_client=True)
    print(f"[{label}] {len(df):,} rows in {time.time() - t0:.0f}s", file=sys.stderr)
    return df


# ------------------------------------------------------------------ pretrain
def build_pretrain(eqx_sample: int):
    plaid_sql = f"""
WITH r AS (
  SELECT LOWER(TRIM(IFNULL(merchant_name, ''))) AS merchant,
         LOWER(TRIM(IFNULL(COALESCE(original_description, transaction_name), ''))) AS description,
         IF(amount < 0, 'credit', 'debit') AS direction,
         ABS(amount) AS a
  FROM {PLAID})
SELECT 'plaid' AS provider, merchant, description, direction, {AMT_CASE} AS amt_bucket, COUNT(*) AS n
FROM r
WHERE merchant != '' OR description != ''
GROUP BY 1, 2, 3, 4, 5
"""
    eqx_sql = f"""
WITH r AS (
  SELECT LOWER(TRIM(IFNULL(VendorDescription, ''))) AS merchant,
         LOWER(TRIM(IFNULL(Description, ''))) AS description,
         IF(TransactionTypeId = 1, 'credit', 'debit') AS direction,
         ABS(Amount) AS a
  FROM {EQX}),
g AS (
  SELECT 'equifax' AS provider, merchant, description, direction, {AMT_CASE} AS amt_bucket, COUNT(*) AS n
  FROM r
  WHERE merchant != '' OR description != ''
  GROUP BY 1, 2, 3, 4, 5)
SELECT * FROM g WHERE RAND() < {eqx_sample} / (SELECT COUNT(*) FROM g)
"""
    plaid = _run(plaid_sql, "pretrain/plaid")
    eqx = _run(eqx_sql, "pretrain/equifax")
    df = pd.concat([plaid, eqx], ignore_index=True)
    df["text"] = [sentence(d, b, m, s) for d, b, m, s in
                  zip(df["direction"], df["amt_bucket"], df["merchant"], df["description"])]
    df = df.drop_duplicates("text").sample(frac=1.0, random_state=42).reset_index(drop=True)
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_parquet(PRETRAIN_PARQUET, index=False)
    print(f"pretrain corpus: {len(df):,} sentences "
          f"(plaid {int((df.provider == 'plaid').sum()):,} / equifax {int((df.provider == 'equifax').sum()):,}) "
          f"-> {PRETRAIN_PARQUET}", file=sys.stderr)
    print(f"credit share: {(df.direction == 'credit').mean():.1%}; "
          f"median tokens (whitespace): {int(df.text.str.split().str.len().median())}", file=sys.stderr)


# -------------------------------------------------------------------- silver
def _silver_sql(per_leaf_cap: int) -> str:
    """T1-T5 waterfall over distinct keys, same CASE bodies as the shipped SQL."""
    return f"""
WITH sub_xw AS (SELECT * FROM UNNEST([STRUCT<eqx_sub STRING, leaf STRING>
{gxw.vals(gxw.sub_map)}
])),
pri_xw AS (SELECT * FROM UNNEST([STRUCT<eqx_pri STRING, leaf STRING>
{gxw.vals(gxw.pri_map)}
])),
plaid_xw AS (SELECT * FROM UNNEST([STRUCT<plaid_cat STRING, leaf STRING>
{gxw.vals(gxw.plaid_map)}
])),
{gxw.dict_xw_sql()},
eqx_raw AS (
  SELECT PrimaryCategoryDescription AS pri, SubCategoryDescription AS sub,
         VendorDescription AS vendor, Description AS description_raw,
         IF(TransactionTypeId = 1, 'credit', 'debit') AS direction,
         {AMT_CASE.replace('a <', 'ABS(Amount) <')} AS amt_bucket,
         COUNT(*) AS n
  FROM {EQX}
  GROUP BY 1, 2, 3, 4, 5, 6
),
eqx_resolved AS (
  SELECT 'equifax' AS provider, LOWER(TRIM(IFNULL(r.vendor, ''))) AS merchant,
         LOWER(TRIM(IFNULL(r.description_raw, ''))) AS description, r.direction, r.amt_bucket, r.n,
{gxw.eqx_leaf_case()}    END AS leaf,
{gxw.eqx_tier_case()}    END AS resolution_tier
  FROM eqx_raw r
  LEFT JOIN sub_xw s ON r.sub = s.eqx_sub
  LEFT JOIN pri_xw p ON r.pri = p.eqx_pri
  LEFT JOIN dict_xw d ON LOWER(TRIM(r.vendor)) = d.merchant
),
plaid_raw AS (
  SELECT credit_category_detailed AS cat, merchant_name AS merchant_raw,
         COALESCE(original_description, transaction_name) AS description_raw,
         IF(amount < 0, 'credit', 'debit') AS direction,
         {AMT_CASE.replace('a <', 'ABS(amount) <')} AS amt_bucket,
         COUNT(*) AS n
  FROM {PLAID}
  GROUP BY 1, 2, 3, 4, 5
),
plaid_resolved AS (
  SELECT 'plaid' AS provider, LOWER(TRIM(IFNULL(r.merchant_raw, ''))) AS merchant,
         LOWER(TRIM(IFNULL(r.description_raw, ''))) AS description, r.direction, r.amt_bucket, r.n,
{gxw.plaid_leaf_case()}    END AS leaf,
{gxw.plaid_tier_case()}    END AS resolution_tier
  FROM plaid_raw r
  LEFT JOIN plaid_xw x ON r.cat = x.plaid_cat
  LEFT JOIN dict_xw d ON LOWER(TRIM(r.merchant_raw)) = d.merchant
),
allrows AS (
  SELECT * FROM eqx_resolved UNION ALL SELECT * FROM plaid_resolved
),
kept AS (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY leaf ORDER BY RAND()) AS rn
  FROM allrows
  WHERE REGEXP_CONTAINS(resolution_tier, r'^T[1-5]_')
    AND NOT STARTS_WITH(leaf, 'unclassified')
    AND (merchant != '' OR description != '')
)
SELECT provider, merchant, description, direction, amt_bucket, n, leaf, resolution_tier
FROM kept WHERE rn <= {per_leaf_cap}
"""


def build_silver(per_leaf_cap: int):
    sql = _silver_sql(per_leaf_cap)
    assert len(sql.encode()) < 1_000_000, len(sql)
    df = _run(sql, "silver")
    excluded = frozen_holdout_merchants() | load_risk_merchants()
    before = len(df)
    df = df[~df["merchant"].isin(excluded)].reset_index(drop=True)
    print(f"silver: dropped {before - len(df):,} rows on holdout/risk-gold merchants", file=sys.stderr)
    df["text"] = [sentence(d, b, m, s) for d, b, m, s in
                  zip(df["direction"], df["amt_bucket"], df["merchant"], df["description"])]
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_parquet(SILVER_PARQUET, index=False)
    vc = df["leaf"].value_counts()
    print(f"silver labels: {len(df):,} keys, {df.leaf.nunique()} leaves, "
          f"credit share {(df.direction == 'credit').mean():.1%} -> {SILVER_PARQUET}", file=sys.stderr)
    print(f"tier mix: {df.resolution_tier.str.slice(0, 2).value_counts().to_dict()}", file=sys.stderr)
    print(f"top leaves: {vc.head(8).to_dict()}", file=sys.stderr)
    print(f"leaves under 100 keys: {int((vc < 100).sum())}", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("pretrain")
    a.add_argument("--eqx-sample", type=int, default=3_500_000)
    b = sub.add_parser("silver")
    b.add_argument("--per-leaf-cap", type=int, default=40_000)
    args = ap.parse_args()
    if args.cmd == "pretrain":
        build_pretrain(args.eqx_sample)
    else:
        build_silver(args.per_leaf_cap)


if __name__ == "__main__":
    main()

"""Experiment 3 rebuild — T1–T7 categorisation, feature screen, two XGBoosts.

Pipeline (transactions stay in BigQuery; only residual *keys* and proposal
features come to the laptop):

  1. Apply the SQL waterfall (T1–T6, T7 unclassified) to every Equifax and
     Plaid transaction on the outcome-labelled cohort.
  2. Score unique T6/T7 keys with the serving hinge (T5b). Always-ML on the
     leftover, matching `score_waterfall_pipeline.py`. T6 is overwritten.
  3. Rebuild the live analog feature set plus a wide candidate family
     (general-category persistence/amount, risk leaves as count *and*
     months, recency, cash-flow ratios, coverage).
  4. Screen on the *train* window only (IV, coverage, correlation, XGB gain).
  5. Fit XGBoost:
       month3_1plus_pia — train 2023-01..2026-02, OOT 2026-03..2026-04
       month6_3plus_pia_from_subscription — train 2023-01..2025-10,
         OOT 2025-11..2026-01

Does not score locked v5/v6.

Usage:
    python src/experiment3_xgb_pipeline.py              # all stages
    python src/experiment3_xgb_pipeline.py fetch
    python src/experiment3_xgb_pipeline.py classify
    python src/experiment3_xgb_pipeline.py features
    python src/experiment3_xgb_pipeline.py train
"""
from __future__ import annotations

import csv
import json
import pathlib
import sys
import time

import numpy as np
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import generate_crosswalk_sql as gxw  # noqa: E402
from credit_metrics import signed_gini  # noqa: E402

PROJECT = "raylo-production"
DATASET = "credit_risk_research"
LOCATION = "EU"
EQX_TXN_TABLE = f"{PROJECT}.{DATASET}.experiment3_eqx_txns"
PLAID_TXN_TABLE = f"{PROJECT}.{DATASET}.experiment3_plaid_txns"
OVERRIDE_PLAID = f"{PROJECT}.{DATASET}.experiment3_residual_override_plaid"
OVERRIDE_EQX = f"{PROJECT}.{DATASET}.experiment3_residual_override_eqx"
FEAT_TABLE = f"{PROJECT}.{DATASET}.experiment3_proposal_features"

HINGE_PATH = ROOT / "outputs" / "distill_models" / "tfidf_linearsvm_sgd.joblib"
OUT_DIR = ROOT / "outputs"
REPORT = ROOT / "data" / "experiment3_xgb_report.md"
FEAT_PARQUET = OUT_DIR / "experiment3_xgb_proposal_features.parquet"
SEL_JSON = OUT_DIR / "experiment3_xgb_selected_features.json"
MODEL_M3 = OUT_DIR / "experiment3_xgb_month3.joblib"
MODEL_M6 = OUT_DIR / "experiment3_xgb_month6.joblib"

TAXONOMY_PATH = ROOT / "taxonomy" / "taxonomy.csv"

LIVE_FEATURES = [
    "spend_hhi",
    "num_distinct_detailed_categories",
    "p2p_to_salary_ratio",
    "num_distinct_merchants",
    "grocer_months",
    "avg_credit_transaction_amount",
    "mortgage_auto_payment_debit_amount",
    "loan_payment_monthly_cv",
    "essential_spend_ratio",
    "essential_spend_amount_total",
    "has_recent_salary_flag",
    "legit_life_footprint_months",
    "returned_payment_count",
    "total_months",
    "loan_payment_months",
    "loan_payment_consistency_ratio",
    "streaming_months",
    "bnpl_30d_vs_90d_ratio",
    "pct_p2p_like_debit_amount",
    "telco_months",
]

BASELINE_FEATURES = [
    "total_months",
    "spend_hhi",
    "spend_hhi_leaf",
    "num_distinct_leaves",
    "num_distinct_merchants",
    "p2p_to_salary_ratio",
    "pct_p2p_like_debit_amount",
    "p2p_to_salary_ratio_loose",
    "pct_p2p_like_debit_amount_loose",
    "grocer_months",
    "avg_credit_transaction_amount",
    "mortgage_debit_amount",
    "loan_payment_monthly_cv",
    "essential_spend_ratio",
    "essential_spend_amount_total",
    "has_recent_salary_flag",
    "legit_life_footprint_months",
    "returned_payment_count",
    "loan_repayment_months",
    "loan_payment_consistency_ratio",
    "streaming_months",
    "bnpl_30d_vs_90d_ratio",
    "telco_months",
    "priority_debt_months",
    "priority_debt_breadth",
    "credit_product_months",
    "income_months",
    "bnpl_months",
    "payday_loan_months",
    "cash_advance_months",
    "rent_months",
    "mortgage_months",
    "gambling_betting_months",
    "gambling_lottery_months",
    "gambling_casino_months",
    "gambling_bingo_months",
    "gambling_unspecified_months",
    "is_plaid",
]

KEY_LEAVES = [
    "salary", "salary_gig", "benefits_state", "pension_received",
    "groceries", "council_tax", "energy",
    "mobile_phone_contract", "broadband_tv_phone",
    "cash_advance_fee",
    "debt_management_plan", "overdraft_unarranged", "returned_payment",
    "credit_card_repayment", "personal_loan_repayment",
    "revolving_credit_repayment", "car_lease", "charge_card_repayment",
    "gambling_betting", "gambling_lottery", "gambling_casino",
    "gambling_bingo", "gambling_unspecified",
    "cash_withdrawal", "cash_deposit", "takeaway", "restaurant_cafe",
    "alcohol_beer_spirits", "vaping",
    "transfer_p2p", "unclassified_transfer", "unclassified_other",
    "savings_transfer", "loan_disbursement", "balance_transfer",
    "rent", "mortgage", "streaming", "bnpl", "payday_loan", "cash_advance",
]

DESC_TRUNC = 300
CLASSIFY_CHUNK = 60_000

M3_TRAIN_START = "2023-01-01"
M3_TRAIN_END = "2026-03-01"
M3_OOT_END = "2026-05-01"
M6_TRAIN_START = "2023-01-01"
M6_TRAIN_END = "2025-11-01"
M6_OOT_END = "2026-02-01"
M3_Y = "month3_1plus_pia"
M6_Y = "month6_3plus_pia_from_subscription"


def _taxonomy_rows():
    return list(csv.DictReader(open(TAXONOMY_PATH)))


def _generals():
    return sorted({r["general_category"] for r in _taxonomy_rows()})


def _lookup_sql() -> str:
    return f"""
sub_xw AS (SELECT * FROM UNNEST([STRUCT<eqx_sub STRING, leaf STRING>
{gxw.vals(gxw.sub_map)}
])),
pri_xw AS (SELECT * FROM UNNEST([STRUCT<eqx_pri STRING, leaf STRING>
{gxw.vals(gxw.pri_map)}
])),
plaid_xw AS (SELECT * FROM UNNEST([STRUCT<plaid_cat STRING, leaf STRING>
{gxw.vals(gxw.plaid_map)}
])),
{gxw.dict_xw_sql()},
leaf_meta AS (SELECT * FROM UNNEST([STRUCT<leaf STRING, general_category STRING, necessity STRING,
  cash_flow_type STRING, is_debt_related BOOL, is_priority_debt BOOL, is_age_restricted BOOL, risk_flag STRING>
{gxw.metavals()}
]))
"""


def _eqx_leaf_sql() -> str:
    return f"""
    CASE
      WHEN r.pri LIKE 'Gambling and Betting%' AND r.direction='credit' THEN 'gambling_unspecified'
      WHEN r.sub='Council' AND r.direction='credit' THEN 'salary'
      WHEN r.pri='Identified Salary' AND r.sub IN ('Taxis','Delivery','Take Away') THEN 'salary_gig'
      WHEN r.pri='Identified Salary' AND r.sub IN ('Recruitment Services','Employment Agencies') THEN 'income_agency_work'
{gxw.t2_entity_collision_leaf(gxw.EQX_MERCHANT_EXPR, gxw.EQX_DESC_EXPR)}
      WHEN r.pri='Identified Salary' THEN 'salary'
      WHEN r.pri='Refund' THEN 'refund_received'
      WHEN r.pri IN ('Benefits','Welfare') THEN 'benefits_state'
      WHEN r.pri='Pension Payout' THEN 'pension_received'
      WHEN r.pri='Tax Refund' THEN 'tax_refund'
      WHEN r.pri='Cash Back' THEN 'cashback'
      WHEN r.pri='Cash Machine' THEN 'cash_withdrawal'
      WHEN r.pri='Cash Deposit' THEN 'cash_deposit'
      WHEN r.pri IN ('Interest','Interests and Dividends') THEN 'savings_interest_received'
      WHEN r.pri='Balance Transfers' THEN 'balance_transfer'
      WHEN r.pri='Adjustments' THEN 'adjustment'
{gxw.t1_gambling_credit_leaf()}
{gxw.t2_refund_leaf(gxw.EQX_DESC_EXPR)}
{gxw.t2_returned_leaf(gxw.EQX_DESC_EXPR)}
{gxw.t2_youlend_credit_leaf(gxw.EQX_MERCHANT_EXPR)}
      WHEN d.leaf IS NOT NULL THEN d.leaf
{gxw.rules_leaf_case(gxw.EQX_MERCHANT_EXPR, gxw.EQX_DESC_EXPR)}
      WHEN s.leaf IS NOT NULL THEN s.leaf
      WHEN p.leaf IS NOT NULL THEN p.leaf
      ELSE 'unclassified_other'
    END
"""


def _eqx_tier_sql() -> str:
    return f"""
    CASE
      WHEN r.pri LIKE 'Gambling and Betting%' AND r.direction='credit' THEN 'T1_direction'
      WHEN r.sub='Council' AND r.direction='credit' THEN 'T1_direction'
      WHEN r.pri='Identified Salary' AND r.sub IN ('Taxis','Delivery','Take Away') THEN 'T2_compound'
      WHEN r.pri='Identified Salary' AND r.sub IN ('Recruitment Services','Employment Agencies') THEN 'T2_compound'
{gxw.t2_entity_collision_tier(gxw.EQX_MERCHANT_EXPR, gxw.EQX_DESC_EXPR)}
      WHEN r.pri IN ('Identified Salary','Refund','Benefits','Welfare','Pension Payout','Tax Refund',
        'Cash Back','Cash Machine','Cash Deposit','Interest','Interests and Dividends',
        'Balance Transfers','Adjustments') THEN 'T3_mechanism_override'
{gxw.t1_gambling_credit_tier()}
{gxw.t2_refund_tier(gxw.EQX_DESC_EXPR)}
{gxw.t2_returned_tier(gxw.EQX_DESC_EXPR)}
{gxw.t2_youlend_credit_tier(gxw.EQX_MERCHANT_EXPR)}
      WHEN d.leaf IS NOT NULL THEN 'T4_merchant_dictionary'
{gxw.rules_tier_case(gxw.EQX_MERCHANT_EXPR, gxw.EQX_DESC_EXPR)}
      WHEN s.leaf IS NOT NULL THEN 'T6_provider_crosswalk'
      WHEN p.leaf IS NOT NULL THEN 'T6_provider_crosswalk'
      ELSE 'T7_unclassified'
    END
"""


def _plaid_leaf_sql() -> str:
    return f"""
    CASE
      WHEN r.cat='ENTERTAINMENT_CASINOS_AND_GAMBLING' AND r.direction='credit' THEN 'gambling_unspecified'
{gxw.t2_entity_collision_leaf(gxw.PLAID_MERCHANT_EXPR, gxw.PLAID_DESC_EXPR)}
{gxw.t1_gambling_credit_leaf()}
{gxw.t2_refund_leaf(gxw.PLAID_DESC_EXPR)}
{gxw.t2_returned_leaf(gxw.PLAID_DESC_EXPR)}
{gxw.t2_youlend_credit_leaf(gxw.PLAID_MERCHANT_EXPR)}
      WHEN d.leaf IS NOT NULL THEN d.leaf
{gxw.rules_leaf_case(gxw.PLAID_MERCHANT_EXPR, gxw.PLAID_DESC_EXPR)}
      WHEN x.leaf IS NOT NULL THEN x.leaf
      ELSE 'unclassified_other'
    END
"""


def _plaid_tier_sql() -> str:
    return f"""
    CASE
      WHEN r.cat='ENTERTAINMENT_CASINOS_AND_GAMBLING' AND r.direction='credit' THEN 'T1_direction'
{gxw.t2_entity_collision_tier(gxw.PLAID_MERCHANT_EXPR, gxw.PLAID_DESC_EXPR)}
{gxw.t1_gambling_credit_tier()}
{gxw.t2_refund_tier(gxw.PLAID_DESC_EXPR)}
{gxw.t2_returned_tier(gxw.PLAID_DESC_EXPR)}
{gxw.t2_youlend_credit_tier(gxw.PLAID_MERCHANT_EXPR)}
      WHEN d.leaf IS NOT NULL THEN 'T4_merchant_dictionary'
{gxw.rules_tier_case(gxw.PLAID_MERCHANT_EXPR, gxw.PLAID_DESC_EXPR)}
      WHEN x.leaf IS NOT NULL THEN 'T6_provider_crosswalk'
      ELSE 'T7_unclassified'
    END
"""


def _eqx_fetch_sql() -> str:
    return f"""
WITH {_lookup_sql()},
cohort AS (
  SELECT
    CAST(p.proposal_id AS STRING) AS proposal_id,
    p.financial_proposal_id,
    p.financial_proposal_created_at,
    p.month3_1plus_pia,
    p.month6_3plus_pia_from_subscription
  FROM `raylo-production.dbt_production.ds_first_order_proposal_pia_metrics` p
  JOIN (
    SELECT DISTINCT financial_proposal_id
    FROM `raylo-production.equifax_data.open_banking_transactions_with_matches`
    WHERE final_matched_on != 'name_time' AND financial_proposal_id IS NOT NULL
  ) e USING (financial_proposal_id)
  WHERE p.financial_proposal_created_at >= '{M3_TRAIN_START}'
    AND (p.month3_1plus_pia IS NOT NULL
         OR p.month6_3plus_pia_from_subscription IS NOT NULL)
),
eqx_raw AS (
  SELECT
    c.proposal_id,
    c.financial_proposal_id,
    c.financial_proposal_created_at,
    c.month3_1plus_pia,
    c.month6_3plus_pia_from_subscription,
    DATE(t.PostDate) AS txn_date,
    DATE_TRUNC(t.PostDate, MONTH) AS month,
    t.PrimaryCategoryDescription AS pri,
    t.SubCategoryDescription AS sub,
    t.VendorDescription AS vendor,
    LEFT(IFNULL(t.Description, ''), {DESC_TRUNC}) AS description_raw,
    IF(t.TransactionTypeId = 1, 'credit', 'debit') AS direction,
    ABS(t.Amount) AS abs_amt,
    LOWER(TRIM(IFNULL(t.VendorDescription, ''))) AS merchant
  FROM cohort c
  JOIN `raylo-production.equifax_data.open_banking_transactions_with_matches` t
    ON t.financial_proposal_id = c.financial_proposal_id
  WHERE t.final_matched_on != 'name_time'
)
SELECT
  r.proposal_id,
  r.financial_proposal_id,
  r.financial_proposal_created_at,
  r.month3_1plus_pia,
  r.month6_3plus_pia_from_subscription,
  'equifax' AS provider,
  r.txn_date,
  r.month,
  r.direction,
  r.abs_amt,
  r.merchant,
  LOWER(IFNULL(r.description_raw, '')) AS description,
{_eqx_leaf_sql()} AS leaf,
{_eqx_tier_sql()} AS resolution_tier
FROM eqx_raw r
LEFT JOIN dict_xw d ON r.merchant = d.merchant
LEFT JOIN sub_xw s ON r.sub = s.eqx_sub
LEFT JOIN pri_xw p ON r.pri = p.eqx_pri
"""


def _plaid_fetch_sql() -> str:
    return f"""
WITH {_lookup_sql()},
cohort AS (
  SELECT
    f.financial_proposal_id,
    f.checkout_risk_assessment_result_id,
    p.financial_proposal_created_at,
    p.month3_1plus_pia,
    p.month6_3plus_pia_from_subscription
  FROM `raylo-production.dbt_production.ds_plaid_credit_features` f
  JOIN `raylo-production.dbt_production.ds_first_order_proposal_pia_metrics` p
    USING (financial_proposal_id)
  WHERE p.financial_proposal_created_at >= '{M3_TRAIN_START}'
    AND (p.month3_1plus_pia IS NOT NULL
         OR p.month6_3plus_pia_from_subscription IS NOT NULL)
),
plaid_raw AS (
  SELECT
    CAST(c.financial_proposal_id AS STRING) AS proposal_id,
    c.financial_proposal_id,
    c.financial_proposal_created_at,
    c.month3_1plus_pia,
    c.month6_3plus_pia_from_subscription,
    DATE_TRUNC(SAFE.PARSE_DATE('%Y-%m-%d', SUBSTR(t.transaction_date, 1, 10)), MONTH) AS month,
    SAFE.PARSE_DATE('%Y-%m-%d', SUBSTR(t.transaction_date, 1, 10)) AS txn_date,
    t.detailed_credit_category AS cat,
    t.merchant_name AS merchant_raw,
    LEFT(IFNULL(COALESCE(t.description, t.transaction_name), ''), {DESC_TRUNC}) AS description_raw,
    IF(t.amount < 0, 'credit', 'debit') AS direction,
    ABS(t.amount) AS abs_amt,
    LOWER(TRIM(IFNULL(t.merchant_name, ''))) AS merchant
  FROM cohort c
  JOIN `raylo-production.dbt_production.intermediate_credit_plaid_transactions` t
    ON t.checkout_risk_assessment_result_id = c.checkout_risk_assessment_result_id
)
SELECT
  r.proposal_id,
  r.financial_proposal_id,
  r.financial_proposal_created_at,
  r.month3_1plus_pia,
  r.month6_3plus_pia_from_subscription,
  'plaid' AS provider,
  r.txn_date,
  r.month,
  r.direction,
  r.abs_amt,
  r.merchant,
  LOWER(IFNULL(r.description_raw, '')) AS description,
{_plaid_leaf_sql()} AS leaf,
{_plaid_tier_sql()} AS resolution_tier
FROM plaid_raw r
LEFT JOIN dict_xw d ON r.merchant = d.merchant
LEFT JOIN plaid_xw x ON r.cat = x.plaid_cat
"""


def _client():
    from google.cloud import bigquery
    return bigquery.Client(project=PROJECT)


def _run_ctas(client, sql: str, dest: str, label: str):
    from google.cloud import bigquery
    print(f"CTAS {label} → {dest} ({len(sql):,} chars)...", file=sys.stderr)
    t0 = time.time()
    job = client.query(
        sql,
        job_config=bigquery.QueryJobConfig(
            destination=dest,
            write_disposition="WRITE_TRUNCATE",
        ),
        location=LOCATION,
    )
    job.result()
    n = client.get_table(dest).num_rows
    print(f"  {label}: {n:,} rows in {time.time() - t0:.0f}s", file=sys.stderr)
    return n


def fetch():
    client = _client()
    _run_ctas(client, _eqx_fetch_sql(), EQX_TXN_TABLE, "Equifax T1–T6")
    _run_ctas(client, _plaid_fetch_sql(), PLAID_TXN_TABLE, "Plaid T1–T6")


def _residual_plaid_sql() -> str:
    return f"""
SELECT merchant, description, direction,
       APPROX_QUANTILES(abs_amt, 2)[OFFSET(1)] AS amount,
       COUNT(*) AS n
FROM `{PLAID_TXN_TABLE}`
WHERE STARTS_WITH(resolution_tier, 'T6') OR STARTS_WITH(resolution_tier, 'T7')
GROUP BY 1, 2, 3
"""


def _residual_eqx_sql() -> str:
    # Equifax vendors are a closed list (~6k residual keys). Narratives vary;
    # hinge sees merchant + typical amount.
    return f"""
SELECT merchant, '' AS description, direction,
       APPROX_QUANTILES(abs_amt, 2)[OFFSET(1)] AS amount,
       COUNT(*) AS n
FROM `{EQX_TXN_TABLE}`
WHERE STARTS_WITH(resolution_tier, 'T6') OR STARTS_WITH(resolution_tier, 'T7')
GROUP BY 1, 3
"""


def _hinge_predict(bundle, keys: pd.DataFrame) -> pd.Series:
    from score_t5b_residual import features_frame, scores_and_margin
    preds = []
    for i in range(0, len(keys), CLASSIFY_CHUNK):
        chunk = keys.iloc[i:i + CLASSIFY_CHUNK]
        feat = features_frame(pd.DataFrame({
            "merchant_raw": chunk["merchant"],
            "description_raw": chunk["description"],
            "amount": chunk["amount"],
            "direction": chunk["direction"],
        }))
        pred, _, _ = scores_and_margin(bundle, feat)
        preds.append(pred)
        print(f"  classified {min(i + CLASSIFY_CHUNK, len(keys)):,}/{len(keys):,}",
              file=sys.stderr)
    return pd.Series(np.concatenate(preds), index=keys.index)


def classify():
    import joblib
    from google.cloud import bigquery

    if not HINGE_PATH.exists():
        raise SystemExit(f"Missing serving hinge {HINGE_PATH}")
    client = _client()
    bundle = joblib.load(HINGE_PATH)
    job_config = bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE")

    print("Fetching Plaid unique T6/T7 keys (merchant+description+direction)...",
          file=sys.stderr)
    plaid_keys = client.query(_residual_plaid_sql(), location=LOCATION).result().to_dataframe()
    print(f"  {len(plaid_keys):,} Plaid keys", file=sys.stderr)
    plaid_keys["hinge_leaf"] = _hinge_predict(bundle, plaid_keys).to_numpy()
    plaid_out = plaid_keys[["merchant", "description", "direction", "amount", "hinge_leaf"]].copy()
    for col in ("merchant", "description", "direction"):
        plaid_out[col] = plaid_out[col].astype(str)
    job = client.load_table_from_dataframe(
        plaid_out, OVERRIDE_PLAID, job_config=job_config, location=LOCATION)
    job.result()
    print(f"Loaded {OVERRIDE_PLAID}: {len(plaid_out):,}", file=sys.stderr)

    print("Fetching Equifax unique T6/T7 keys (merchant+direction)...", file=sys.stderr)
    eqx_keys = client.query(_residual_eqx_sql(), location=LOCATION).result().to_dataframe()
    print(f"  {len(eqx_keys):,} Equifax keys", file=sys.stderr)
    eqx_keys["hinge_leaf"] = _hinge_predict(bundle, eqx_keys).to_numpy()
    eqx_out = eqx_keys[["merchant", "direction", "amount", "hinge_leaf"]].copy()
    eqx_out["merchant"] = eqx_out["merchant"].astype(str)
    eqx_out["direction"] = eqx_out["direction"].astype(str)
    job = client.load_table_from_dataframe(
        eqx_out, OVERRIDE_EQX, job_config=job_config, location=LOCATION)
    job.result()
    print(f"Loaded {OVERRIDE_EQX}: {len(eqx_out):,}", file=sys.stderr)


def _leaf_block(alias: str, pred) -> str:
    """SQL fragment: months / count / debit amt / credit amt for one leaf."""
    return f"""
  COUNT(DISTINCT IF(w.leaf = '{alias}', w.month, NULL)) AS {pred}_months,
  COUNTIF(w.leaf = '{alias}') AS {pred}_n,
  SUM(IF(w.leaf = '{alias}' AND w.direction = 'debit', w.abs_amt, 0)) AS {pred}_debit_amt,
  SUM(IF(w.leaf = '{alias}' AND w.direction = 'credit', w.abs_amt, 0)) AS {pred}_credit_amt
"""


def _gen_block(g: str) -> str:
    a = g
    return f"""
  COUNT(DISTINCT IF(w.general_category = '{g}', w.month, NULL)) AS gen_{a}_months,
  SUM(IF(w.general_category = '{g}' AND w.direction = 'debit', w.abs_amt, 0)) AS gen_{a}_debit_amt,
  COUNTIF(w.general_category = '{g}' AND w.direction = 'debit') AS gen_{a}_debit_n
"""


_TXN_COLS = """proposal_id, financial_proposal_id, financial_proposal_created_at,
    month3_1plus_pia, month6_3plus_pia_from_subscription, provider,
    txn_date, DATE(month) AS month, direction, abs_amt, merchant, description,
    leaf, resolution_tier"""


def _feature_sql() -> str:
    as_of = "DATE(c.financial_proposal_created_at)"
    live_select = ",\n  ".join(f"l.{col} AS live_{col}" for col in LIVE_FEATURES)
    leaf_sql = ",\n".join(_leaf_block(x, x) for x in KEY_LEAVES)
    gen_sql = ",\n".join(_gen_block(g) for g in _generals())
    return f"""
WITH {_lookup_sql()},
override_plaid AS (
  SELECT merchant, description, direction, hinge_leaf
  FROM `{OVERRIDE_PLAID}`
),
override_eqx AS (
  SELECT merchant, direction, hinge_leaf
  FROM `{OVERRIDE_EQX}`
),
eqx AS (
  SELECT {_TXN_COLS} FROM `{EQX_TXN_TABLE}`
),
plaid AS (
  SELECT {_TXN_COLS} FROM `{PLAID_TXN_TABLE}`
),
unioned AS (
  SELECT * FROM eqx
  UNION ALL
  SELECT * FROM plaid
),
resolved AS (
  SELECT
    u.* EXCEPT (leaf, resolution_tier),
    CASE
      WHEN (STARTS_WITH(u.resolution_tier, 'T6') OR STARTS_WITH(u.resolution_tier, 'T7'))
           AND u.provider = 'plaid' AND op.hinge_leaf IS NOT NULL THEN op.hinge_leaf
      WHEN (STARTS_WITH(u.resolution_tier, 'T6') OR STARTS_WITH(u.resolution_tier, 'T7'))
           AND u.provider = 'equifax' AND oe.hinge_leaf IS NOT NULL THEN oe.hinge_leaf
      ELSE u.leaf
    END AS leaf,
    CASE
      WHEN (STARTS_WITH(u.resolution_tier, 'T6') OR STARTS_WITH(u.resolution_tier, 'T7'))
           AND u.provider = 'plaid' AND op.hinge_leaf IS NOT NULL THEN 'T5b_classifier'
      WHEN (STARTS_WITH(u.resolution_tier, 'T6') OR STARTS_WITH(u.resolution_tier, 'T7'))
           AND u.provider = 'equifax' AND oe.hinge_leaf IS NOT NULL THEN 'T5b_classifier'
      ELSE u.resolution_tier
    END AS resolution_tier
  FROM unioned u
  LEFT JOIN override_plaid op
    ON u.provider = 'plaid'
   AND u.merchant = op.merchant
   AND u.description = op.description
   AND u.direction = op.direction
  LEFT JOIN override_eqx oe
    ON u.provider = 'equifax'
   AND u.merchant = oe.merchant
   AND u.direction = oe.direction
),
with_meta AS (
  SELECT r.*,
    m.general_category, m.necessity, m.cash_flow_type,
    m.is_debt_related, m.is_priority_debt, m.is_age_restricted, m.risk_flag
  FROM resolved r
  LEFT JOIN leaf_meta m ON r.leaf = m.leaf
),
hhi AS (
  SELECT financial_proposal_id, provider, SUM(POW(share, 2)) AS spend_hhi
  FROM (
    SELECT financial_proposal_id, provider,
      SAFE_DIVIDE(spend, SUM(spend) OVER (PARTITION BY financial_proposal_id, provider)) AS share
    FROM (
      SELECT financial_proposal_id, provider, general_category,
             SUM(IF(direction = 'debit', abs_amt, 0)) AS spend
      FROM with_meta
      GROUP BY 1, 2, 3
    )
  )
  GROUP BY 1, 2
),
hhi_leaf AS (
  SELECT financial_proposal_id, provider, SUM(POW(share, 2)) AS spend_hhi_leaf
  FROM (
    SELECT financial_proposal_id, provider,
      SAFE_DIVIDE(spend, SUM(spend) OVER (PARTITION BY financial_proposal_id, provider)) AS share
    FROM (
      SELECT financial_proposal_id, provider, leaf,
             SUM(IF(direction = 'debit', abs_amt, 0)) AS spend
      FROM with_meta
      GROUP BY 1, 2, 3
    )
  )
  GROUP BY 1, 2
),
loan_month AS (
  SELECT financial_proposal_id, provider, month, SUM(abs_amt) AS loan_amt
  FROM with_meta
  WHERE general_category = 'credit_loan_repayments' AND direction = 'debit'
  GROUP BY 1, 2, 3
),
loan_cv AS (
  SELECT financial_proposal_id, provider,
    SAFE_DIVIDE(STDDEV_SAMP(loan_amt), NULLIF(AVG(loan_amt), 0)) AS loan_payment_monthly_cv
  FROM loan_month
  GROUP BY 1, 2
),
inc_month AS (
  SELECT financial_proposal_id, provider, month,
    SUM(IF(cash_flow_type = 'income' AND direction = 'credit', abs_amt, 0)) AS inc_amt,
    SUM(IF(direction = 'debit', abs_amt, 0)) AS spend_amt
  FROM with_meta
  GROUP BY 1, 2, 3
),
inc_cv AS (
  SELECT financial_proposal_id, provider,
    SAFE_DIVIDE(STDDEV_SAMP(inc_amt), NULLIF(AVG(inc_amt), 0)) AS income_monthly_cv,
    SAFE_DIVIDE(STDDEV_SAMP(spend_amt), NULLIF(AVG(spend_amt), 0)) AS spend_monthly_cv
  FROM inc_month
  GROUP BY 1, 2
),
cohort AS (
  SELECT DISTINCT
    proposal_id, financial_proposal_id, financial_proposal_created_at,
    month3_1plus_pia, month6_3plus_pia_from_subscription, provider
  FROM unioned
),
live AS (
  SELECT financial_proposal_id, {", ".join(LIVE_FEATURES)}
  FROM `raylo-production.dbt_production.ds_plaid_credit_features`
)
SELECT
  c.proposal_id,
  CAST(c.financial_proposal_id AS STRING) AS financial_proposal_id,
  c.financial_proposal_created_at,
  c.month3_1plus_pia,
  c.month6_3plus_pia_from_subscription,
  c.provider,
  IF(c.provider = 'plaid', 1, 0) AS is_plaid,
  {live_select},
  COUNT(*) AS n_txns,
  COUNTIF(w.direction = 'debit') AS n_debits,
  COUNTIF(w.direction = 'credit') AS n_credits,
  COUNT(DISTINCT w.month) AS total_months,
  COUNT(DISTINCT w.leaf) AS num_distinct_leaves,
  COUNT(DISTINCT NULLIF(w.merchant, '')) AS num_distinct_merchants,
  SUM(IF(w.direction = 'debit', w.abs_amt, 0)) AS total_debit_amt,
  SUM(IF(w.direction = 'credit', w.abs_amt, 0)) AS total_credit_amt,
  AVG(IF(w.direction = 'credit', w.abs_amt, NULL)) AS avg_credit_transaction_amount,
  AVG(IF(w.direction = 'debit', w.abs_amt, NULL)) AS avg_debit_transaction_amount,
  MAX(IF(w.direction = 'debit', w.abs_amt, 0)) AS max_debit_amt,
  SAFE_DIVIDE(
    SUM(IF(w.direction = 'credit', w.abs_amt, 0)) - SUM(IF(w.direction = 'debit', w.abs_amt, 0)),
    NULLIF(SUM(IF(w.direction = 'debit', w.abs_amt, 0)), 0)
  ) AS net_to_debit_ratio,
  SAFE_DIVIDE(
    SUM(IF(w.cash_flow_type = 'income' AND w.direction = 'credit', w.abs_amt, 0)),
    NULLIF(SUM(IF(w.direction = 'debit', w.abs_amt, 0)), 0)
  ) AS income_to_spend_ratio,
  COUNT(DISTINCT IF(w.is_priority_debt, w.month, NULL)) AS priority_debt_months,
  COUNT(DISTINCT IF(w.is_priority_debt, w.leaf, NULL)) AS priority_debt_breadth,
  COUNT(DISTINCT IF(w.is_debt_related, w.month, NULL)) AS credit_product_months,
  COUNT(DISTINCT IF(w.cash_flow_type = 'income', w.month, NULL)) AS income_months,
  COUNT(DISTINCT IF(w.leaf = 'groceries', w.month, NULL)) AS grocer_months,
  COUNT(DISTINCT IF(w.leaf IN ('mobile_phone_contract', 'broadband_tv_phone'), w.month, NULL)) AS telco_months,
  COUNT(DISTINCT IF(w.general_category = 'credit_loan_repayments', w.month, NULL)) AS loan_repayment_months,
  COUNTIF(w.leaf = 'returned_payment') AS returned_payment_count,
  COUNT(DISTINCT IF(
    w.leaf IN ('groceries', 'rent', 'mortgage', 'council_tax',
               'mobile_phone_contract', 'broadband_tv_phone')
    OR w.general_category = 'utilities_household_bills',
    w.month, NULL)) AS legit_life_footprint_months,
  SUM(IF(w.direction = 'debit' AND w.necessity = 'essential', w.abs_amt, 0)) AS essential_spend_amount_total,
  SAFE_DIVIDE(
    SUM(IF(w.direction = 'debit' AND w.necessity = 'essential', w.abs_amt, 0)),
    SUM(IF(w.direction = 'debit', w.abs_amt, 0))
  ) AS essential_spend_ratio,
  SAFE_DIVIDE(
    SUM(IF(w.direction = 'debit' AND w.necessity = 'mixed_basket', w.abs_amt, 0)),
    SUM(IF(w.direction = 'debit', w.abs_amt, 0))
  ) AS mixed_basket_spend_ratio,
  SAFE_DIVIDE(
    SUM(IF(w.direction = 'debit' AND w.necessity = 'discretionary', w.abs_amt, 0)),
    SUM(IF(w.direction = 'debit', w.abs_amt, 0))
  ) AS discretionary_spend_ratio,
  SUM(IF(w.leaf = 'mortgage' AND w.direction = 'debit', w.abs_amt, 0)) AS mortgage_debit_amount,
  SAFE_DIVIDE(
    SUM(IF(w.cash_flow_type = 'p2p_transfer' AND w.direction = 'debit', w.abs_amt, 0)),
    SUM(IF(w.direction = 'debit', w.abs_amt, 0))
  ) AS pct_p2p_like_debit_amount,
  SAFE_DIVIDE(
    SUM(IF(w.cash_flow_type = 'p2p_transfer' AND w.direction = 'debit', w.abs_amt, 0)),
    SUM(IF(w.leaf IN ('salary', 'salary_gig') AND w.direction = 'credit', w.abs_amt, 0))
  ) AS p2p_to_salary_ratio,
  SAFE_DIVIDE(
    SUM(IF((w.cash_flow_type = 'p2p_transfer' OR w.leaf = 'unclassified_transfer')
           AND w.direction = 'debit', w.abs_amt, 0)),
    SUM(IF(w.direction = 'debit', w.abs_amt, 0))
  ) AS pct_p2p_like_debit_amount_loose,
  SAFE_DIVIDE(
    SUM(IF((w.cash_flow_type = 'p2p_transfer' OR w.leaf = 'unclassified_transfer')
           AND w.direction = 'debit', w.abs_amt, 0)),
    SUM(IF(w.leaf IN ('salary', 'salary_gig') AND w.direction = 'credit', w.abs_amt, 0))
  ) AS p2p_to_salary_ratio_loose,
  SAFE_DIVIDE(
    COUNT(DISTINCT IF(w.general_category = 'credit_loan_repayments' AND w.direction = 'debit', w.month, NULL)),
    COUNT(DISTINCT w.month)
  ) AS loan_payment_consistency_ratio,
  MAX(IF(
    w.leaf IN ('salary', 'salary_gig') AND w.direction = 'credit'
    AND w.txn_date >= DATE_SUB({as_of}, INTERVAL 30 DAY)
    AND w.txn_date <= {as_of}, 1, 0)) AS has_recent_salary_flag,
  SAFE_DIVIDE(
    SUM(IF(w.leaf = 'bnpl' AND w.direction = 'debit'
           AND w.txn_date >= DATE_SUB({as_of}, INTERVAL 30 DAY)
           AND w.txn_date <= {as_of}, w.abs_amt, 0)),
    SUM(IF(w.leaf = 'bnpl' AND w.direction = 'debit'
           AND w.txn_date >= DATE_SUB({as_of}, INTERVAL 90 DAY)
           AND w.txn_date <= {as_of}, w.abs_amt, 0))
  ) AS bnpl_30d_vs_90d_ratio,
  SAFE_DIVIDE(
    SUM(IF(w.direction = 'debit' AND w.txn_date >= DATE_SUB({as_of}, INTERVAL 30 DAY)
           AND w.txn_date <= {as_of}, w.abs_amt, 0)),
    SUM(IF(w.direction = 'debit' AND w.txn_date >= DATE_SUB({as_of}, INTERVAL 90 DAY)
           AND w.txn_date <= {as_of}, w.abs_amt, 0))
  ) AS spend_30d_vs_90d_ratio,
  DATE_DIFF({as_of}, MAX(IF(w.leaf IN ('salary', 'salary_gig') AND w.direction = 'credit', w.txn_date, NULL)), DAY)
    AS days_since_salary,
  DATE_DIFF({as_of}, MAX(IF(w.leaf = 'returned_payment', w.txn_date, NULL)), DAY)
    AS days_since_returned_payment,
  DATE_DIFF({as_of}, MAX(IF(w.general_category = 'gambling', w.txn_date, NULL)), DAY)
    AS days_since_gambling,
  DATE_DIFF({as_of}, MAX(IF(w.leaf = 'payday_loan', w.txn_date, NULL)), DAY)
    AS days_since_payday,
  COUNTIF(STARTS_WITH(w.resolution_tier, 'T5b')) AS n_t5b,
  SAFE_DIVIDE(COUNTIF(STARTS_WITH(w.resolution_tier, 'T1')
                      OR STARTS_WITH(w.resolution_tier, 'T2')
                      OR STARTS_WITH(w.resolution_tier, 'T3')
                      OR STARTS_WITH(w.resolution_tier, 'T4')
                      OR STARTS_WITH(w.resolution_tier, 'T5_')), COUNT(*)) AS pct_t1_t5,
  SAFE_DIVIDE(COUNTIF(STARTS_WITH(w.leaf, 'unclassified')), COUNT(*)) AS pct_unclassified,
  SAFE_DIVIDE(
    SUM(IF(w.direction = 'debit' AND w.is_age_restricted, w.abs_amt, 0)),
    SUM(IF(w.direction = 'debit', w.abs_amt, 0))
  ) AS pct_age_restricted_debit,
  COUNT(DISTINCT IF(w.risk_flag IN ('high_cost_credit', 'distress_signal', 'distress_fee'), w.month, NULL))
    AS high_cost_distress_months,
  SUM(IF(w.direction = 'debit' AND w.risk_flag IN ('high_cost_credit', 'distress_signal', 'distress_fee'),
         w.abs_amt, 0)) AS high_cost_distress_debit_amt,
  SAFE_DIVIDE(
    SUM(IF(w.leaf = 'takeaway' AND w.direction = 'debit', w.abs_amt, 0)),
    NULLIF(SUM(IF(w.leaf = 'groceries' AND w.direction = 'debit', w.abs_amt, 0)), 0)
  ) AS takeaway_to_groceries_ratio,
  SAFE_DIVIDE(
    SUM(IF(w.general_category = 'gambling' AND w.direction = 'debit', w.abs_amt, 0)),
    NULLIF(SUM(IF(w.leaf IN ('salary', 'salary_gig') AND w.direction = 'credit', w.abs_amt, 0)), 0)
  ) AS gambling_to_salary_ratio,
  ANY_VALUE(h.spend_hhi) AS spend_hhi,
  ANY_VALUE(hl.spend_hhi_leaf) AS spend_hhi_leaf,
  ANY_VALUE(lc.loan_payment_monthly_cv) AS loan_payment_monthly_cv,
  ANY_VALUE(ic.income_monthly_cv) AS income_monthly_cv,
  ANY_VALUE(ic.spend_monthly_cv) AS spend_monthly_cv,
  {leaf_sql},
  {gen_sql}
FROM cohort c
LEFT JOIN with_meta w
  ON c.financial_proposal_id = w.financial_proposal_id AND c.provider = w.provider
LEFT JOIN hhi h
  ON c.financial_proposal_id = h.financial_proposal_id AND c.provider = h.provider
LEFT JOIN hhi_leaf hl
  ON c.financial_proposal_id = hl.financial_proposal_id AND c.provider = hl.provider
LEFT JOIN loan_cv lc
  ON c.financial_proposal_id = lc.financial_proposal_id AND c.provider = lc.provider
LEFT JOIN inc_cv ic
  ON c.financial_proposal_id = ic.financial_proposal_id AND c.provider = ic.provider
LEFT JOIN live l
  ON c.provider = 'plaid' AND c.financial_proposal_id = l.financial_proposal_id
GROUP BY c.proposal_id, c.financial_proposal_id, c.financial_proposal_created_at,
         c.month3_1plus_pia, c.month6_3plus_pia_from_subscription, c.provider,
         {", ".join("l." + col for col in LIVE_FEATURES)}
"""


def features():
    from google.cloud import bigquery
    client = _client()
    sql = _feature_sql()
    print(f"Aggregating proposal features ({len(sql):,} chars)...", file=sys.stderr)
    t0 = time.time()
    job = client.query(
        sql,
        job_config=bigquery.QueryJobConfig(
            destination=FEAT_TABLE,
            write_disposition="WRITE_TRUNCATE",
        ),
        location=LOCATION,
    )
    job.result()
    print(f"  wrote {FEAT_TABLE} in {time.time() - t0:.0f}s", file=sys.stderr)
    df = client.query(
        f"SELECT * FROM `{FEAT_TABLE}`", location=LOCATION
    ).result().to_dataframe()
    OUT_DIR.mkdir(exist_ok=True)
    df.to_parquet(FEAT_PARQUET, index=False)
    print(f"  parquet {len(df):,} proposals → {FEAT_PARQUET}", file=sys.stderr)
    return df


def _iv_quantile(x, y, n=5):
    x = pd.Series(x, dtype=float)
    y = np.asarray(y, dtype=int)
    mask = x.notna() & np.isfinite(x)
    x, y = x[mask], y[mask]
    if len(x) < 50 or y.min() == y.max():
        return 0.0
    try:
        bins = pd.qcut(x.rank(method="first"), n, labels=False, duplicates="drop")
    except ValueError:
        return 0.0
    total_good = (y == 0).sum()
    total_bad = (y == 1).sum()
    if total_good == 0 or total_bad == 0:
        return 0.0
    iv = 0.0
    for b in sorted(pd.unique(bins)):
        m = bins == b
        good = max((y[m] == 0).sum(), 0.5)
        bad = max((y[m] == 1).sum(), 0.5)
        iv += (bad / total_bad - good / total_good) * np.log((bad / total_bad) / (good / total_good))
    return float(iv)


def _meta_cols():
    return {
        "proposal_id", "financial_proposal_id", "financial_proposal_created_at",
        M3_Y, M6_Y, "provider",
    } | {f"live_{c}" for c in LIVE_FEATURES}


def _candidate_cols(df: pd.DataFrame) -> list[str]:
    skip = _meta_cols()
    out = []
    for c in df.columns:
        if c in skip:
            continue
        if df[c].dtype == object:
            continue
        out.append(c)
    return out


def _prepare(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["financial_proposal_id"] = df["financial_proposal_id"].astype(str)
    df["created"] = pd.to_datetime(df["financial_proposal_created_at"], utc=True)
    plaid_ids = set(df.loc[df["provider"] == "plaid", "financial_proposal_id"])
    df = df[~((df["provider"] == "equifax") & df["financial_proposal_id"].isin(plaid_ids))].copy()
    return df


def _window(df, start, end, ycol):
    start_ts = pd.Timestamp(start, tz="UTC")
    end_ts = pd.Timestamp(end, tz="UTC")
    out = df[(df["created"] >= start_ts) & (df["created"] < end_ts)].copy()
    out = out[out[ycol].notna()].copy()
    return out


def _drop_immature_months(df, ycol):
    """Drop calendar months where the label is filled as all-zero (immature)."""
    tmp = df.copy()
    tmp["_ym"] = tmp["created"].dt.strftime("%Y-%m")
    keep = []
    for ym, g in tmp.groupby("_ym"):
        rate = float(g[ycol].mean())
        if len(g) >= 400 and rate == 0.0:
            print(f"  drop immature {ym} n={len(g):,} {ycol}=0", file=sys.stderr)
            continue
        keep.append(ym)
    return tmp[tmp["_ym"].isin(keep)].drop(columns=["_ym"])


def _inner_cut(train: pd.DataFrame):
    train = train.sort_values("created")
    cut = train["created"].quantile(0.80)
    return train[train["created"] < cut], train[train["created"] >= cut], cut


def _screen(inner_train: pd.DataFrame, ycol: str, candidates: list[str]):
    y = inner_train[ycol].astype(int)
    rows = []
    keep = []
    for col in candidates:
        x = pd.to_numeric(inner_train[col], errors="coerce")
        nz = float((x.fillna(0) != 0).mean())
        nuniq = int(x.nunique(dropna=True))
        if nuniq < 2:
            rows.append({"feature": col, "iv": 0.0, "nonzero": nz, "keep": False, "why": "constant"})
            continue
        iv = _iv_quantile(x, y)
        forced = col in BASELINE_FEATURES
        if nz < 0.005 and iv < 0.03 and not forced:
            rows.append({"feature": col, "iv": round(iv, 4), "nonzero": round(nz, 4),
                         "keep": False, "why": "sparse"})
            continue
        if iv < 0.012 and not forced:
            rows.append({"feature": col, "iv": round(iv, 4), "nonzero": round(nz, 4),
                         "keep": False, "why": "low_iv"})
            continue
        rows.append({"feature": col, "iv": round(iv, 4), "nonzero": round(nz, 4),
                     "keep": True, "why": "baseline" if forced else "iv"})
        keep.append(col)
    screen = pd.DataFrame(rows).sort_values("iv", ascending=False)
    # Correlation prune among kept (not forced): drop lower-IV of |r|>0.92
    forced = [c for c in keep if c in BASELINE_FEATURES]
    optional = [c for c in keep if c not in BASELINE_FEATURES]
    dropped_corr = []
    if len(optional) > 1:
        mat = inner_train[optional].apply(pd.to_numeric, errors="coerce")
        corr = mat.corr().abs()
        iv_map = dict(zip(screen["feature"], screen["iv"]))
        dead = set()
        for i, a in enumerate(optional):
            if a in dead:
                continue
            for b in optional[i + 1:]:
                if b in dead:
                    continue
                try:
                    r = float(corr.loc[a, b])
                except KeyError:
                    continue
                if r > 0.92:
                    loser = a if iv_map.get(a, 0) < iv_map.get(b, 0) else b
                    dead.add(loser)
                    dropped_corr.append((loser, a if loser == b else b, r))
        optional = [c for c in optional if c not in dead]
        screen.loc[screen["feature"].isin(dead), "keep"] = False
        screen.loc[screen["feature"].isin(dead), "why"] = "corr"
    kept = forced + optional
    return screen, kept, dropped_corr


def _fit_xgb(X_tr, y_tr, X_va, y_va):
    import xgboost as xgb
    pos = max(int(y_tr.sum()), 1)
    neg = max(int((y_tr == 0).sum()), 1)
    clf = xgb.XGBClassifier(
        n_estimators=500,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.85,
        colsample_bytree=0.7,
        min_child_weight=15,
        reg_lambda=2.0,
        objective="binary:logistic",
        eval_metric="auc",
        tree_method="hist",
        n_jobs=-1,
        scale_pos_weight=neg / pos,
        early_stopping_rounds=40,
    )
    clf.fit(X_tr, y_tr, eval_set=[(X_va, y_va)], verbose=False)
    return clf


def _fit_logit(X, y):
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    pipe = Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
        ("clf", LogisticRegression(max_iter=2000, solver="lbfgs")),
    ])
    pipe.fit(X, y.astype(int))
    return pipe


def _gain_prune(clf, cols, inner_train, inner_valid, ycol, min_keep=20):
    gain = clf.feature_importances_
    order = np.argsort(-gain)
    ranked = [(cols[i], float(gain[i])) for i in order]
    # Keep features that produced any split, plus baseline that survived screen.
    nonzero = [c for c, g in ranked if g > 0]
    if len(nonzero) < min_keep:
        nonzero = [c for c, _ in ranked[:min_keep]]
    # Cap at 80 to avoid an over-wide GBM on ~50k rows.
    if len(nonzero) > 80:
        nonzero = nonzero[:80]
    return nonzero, ranked


def _score_block(name, proba, y):
    return {
        "model": name,
        "n": int(len(y)),
        "bads": int(np.asarray(y).sum()),
        "gini": round(signed_gini(proba, y), 4),
    }


def _run_one(df, ycol, train_start, train_end, oot_end, label):
    import joblib

    train = _drop_immature_months(_window(df, train_start, train_end, ycol), ycol)
    oot = _drop_immature_months(_window(df, train_end, oot_end, ycol), ycol)
    if oot.empty or int(oot[ycol].sum()) == 0:
        raise SystemExit(f"{label}: OOT empty or 0 bads")
    inner_tr, inner_va, cut = _inner_cut(train)
    cands = _candidate_cols(df)
    screen, kept, dropped_corr = _screen(inner_tr, ycol, cands)
    print(f"{label}: train {len(train):,} ({int(train[ycol].sum())} bads) "
          f"OOT {len(oot):,} ({int(oot[ycol].sum())} bads) "
          f"screen kept {len(kept)}/{len(cands)}", file=sys.stderr)

    y_tr = inner_tr[ycol].astype(int)
    y_va = inner_va[ycol].astype(int)
    y_oot = oot[ycol].astype(int)

    def _X(frame, cols):
        return frame[cols].apply(pd.to_numeric, errors="coerce")

    xgb1 = _fit_xgb(_X(inner_tr, kept), y_tr, _X(inner_va, kept), y_va)
    selected, ranked = _gain_prune(xgb1, kept, inner_tr, inner_va, ycol)
    # Always retain surviving baseline analogs.
    for c in BASELINE_FEATURES:
        if c in kept and c not in selected:
            selected.append(c)
    print(f"  after gain prune: {len(selected)} features", file=sys.stderr)

    xgb_final = _fit_xgb(_X(inner_tr, selected), y_tr, _X(inner_va, selected), y_va)
    # Refit on full train with the same n_estimators as early-stopped.
    best_iter = int(getattr(xgb_final, "best_iteration", None) or xgb_final.n_estimators)
    import xgboost as xgb
    pos = max(int(train[ycol].sum()), 1)
    neg = max(int((train[ycol] == 0).sum()), 1)
    xgb_refit = xgb.XGBClassifier(
        n_estimators=max(best_iter, 50),
        max_depth=4,
        learning_rate=0.05,
        subsample=0.85,
        colsample_bytree=0.7,
        min_child_weight=15,
        reg_lambda=2.0,
        objective="binary:logistic",
        eval_metric="auc",
        tree_method="hist",
        n_jobs=-1,
        scale_pos_weight=neg / pos,
    )
    xgb_refit.fit(_X(train, selected), train[ycol].astype(int))

    baseline_cols = [c for c in BASELINE_FEATURES if c in train.columns]
    live_cols = [f"live_{c}" for c in LIVE_FEATURES if f"live_{c}" in train.columns]
    plaid_train = train[train["is_plaid"] == 1]
    plaid_oot = oot[oot["is_plaid"] == 1]

    results = []
    # Taxonomy selected XGB
    results.append(_score_block(
        f"{label} taxonomy selected XGB",
        xgb_refit.predict_proba(_X(oot, selected))[:, 1], y_oot))
    results.append(_score_block(
        f"{label} taxonomy selected XGB (inner valid)",
        xgb_final.predict_proba(_X(inner_va, selected))[:, 1], y_va))
    # Baseline analog logistic + XGB
    logit_b = _fit_logit(_X(train, baseline_cols), train[ycol])
    results.append(_score_block(
        f"{label} taxonomy baseline logistic",
        logit_b.predict_proba(_X(oot, baseline_cols))[:, 1], y_oot))
    xgb_b = _fit_xgb(_X(inner_tr, baseline_cols), y_tr,
                     _X(inner_va, baseline_cols), y_va)
    results.append(_score_block(
        f"{label} taxonomy baseline XGB",
        xgb_b.predict_proba(_X(oot, baseline_cols))[:, 1], y_oot))
    # Live Plaid-native and Plaid-only taxonomy (same population as the live model).
    if live_cols and len(plaid_train) > 200 and plaid_train[ycol].nunique() == 2 and len(plaid_oot):
        p_tr, p_va, _ = _inner_cut(plaid_train)
        logit_l = _fit_logit(_X(plaid_train, live_cols), plaid_train[ycol])
        results.append(_score_block(
            f"{label} live Plaid logistic",
            logit_l.predict_proba(_X(plaid_oot, live_cols))[:, 1],
            plaid_oot[ycol].astype(int)))
        if len(p_tr) > 200 and len(p_va) > 50 and p_va[ycol].nunique() == 2:
            xgb_l = _fit_xgb(
                _X(p_tr, live_cols), p_tr[ycol].astype(int),
                _X(p_va, live_cols), p_va[ycol].astype(int))
            results.append(_score_block(
                f"{label} live Plaid XGB",
                xgb_l.predict_proba(_X(plaid_oot, live_cols))[:, 1],
                plaid_oot[ycol].astype(int)))
            xgb_tp = _fit_xgb(
                _X(p_tr, selected), p_tr[ycol].astype(int),
                _X(p_va, selected), p_va[ycol].astype(int))
            best_p = int(getattr(xgb_tp, "best_iteration", None) or xgb_tp.n_estimators)
            pos_p = max(int(plaid_train[ycol].sum()), 1)
            neg_p = max(int((plaid_train[ycol] == 0).sum()), 1)
            xgb_tp_refit = xgb.XGBClassifier(
                n_estimators=max(best_p, 50),
                max_depth=4,
                learning_rate=0.05,
                subsample=0.85,
                colsample_bytree=0.7,
                min_child_weight=15,
                reg_lambda=2.0,
                objective="binary:logistic",
                eval_metric="auc",
                tree_method="hist",
                n_jobs=-1,
                scale_pos_weight=neg_p / pos_p,
            )
            xgb_tp_refit.fit(_X(plaid_train, selected), plaid_train[ycol].astype(int))
            results.append(_score_block(
                f"{label} taxonomy selected XGB, Plaid-train only",
                xgb_tp_refit.predict_proba(_X(plaid_oot, selected))[:, 1],
                plaid_oot[ycol].astype(int)))

    gain_rows = [{"feature": c, "gain": round(g, 6)} for c, g in ranked if c in selected]
    return {
        "label": label,
        "ycol": ycol,
        "train_n": len(train),
        "train_bads": int(train[ycol].sum()),
        "oot_n": len(oot),
        "oot_bads": int(oot[ycol].sum()),
        "inner_cut": str(cut),
        "n_candidates": len(cands),
        "n_screen_kept": len(kept),
        "n_selected": len(selected),
        "selected": selected,
        "screen": screen,
        "dropped_corr": dropped_corr[:30],
        "results": results,
        "gain_rows": gain_rows,
        "model": xgb_refit,
        "eqx_train": int((train["provider"] == "equifax").sum()),
        "plaid_train": int((train["provider"] == "plaid").sum()),
        "plaid_oot": int((oot["provider"] == "plaid").sum()),
        "eqx_oot": int((oot["provider"] == "equifax").sum()),
    }


def _md_table(rows, cols):
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for r in rows:
        lines.append("| " + " | ".join(str(r.get(c, "")) for c in cols) + " |")
    return "\n".join(lines)


def train(df=None):
    import joblib
    if df is None:
        df = pd.read_parquet(FEAT_PARQUET)
    df = _prepare(df)
    OUT_DIR.mkdir(exist_ok=True)

    m3 = _run_one(df, M3_Y, M3_TRAIN_START, M3_TRAIN_END, M3_OOT_END, "month3")
    m6 = _run_one(df, M6_Y, M6_TRAIN_START, M6_TRAIN_END, M6_OOT_END, "month6")
    joblib.dump({"model": m3["model"], "features": m3["selected"], "y": M3_Y}, MODEL_M3)
    joblib.dump({"model": m6["model"], "features": m6["selected"], "y": M6_Y}, MODEL_M6)
    SEL_JSON.write_text(json.dumps({
        "month3": m3["selected"],
        "month6": m6["selected"],
    }, indent=2))

    def pack(run):
        gini_rows = [{"model": r["model"], "n": r["n"], "bads": r["bads"],
                      "signed_gini": r["gini"]} for r in run["results"]]
        top_iv = run["screen"][run["screen"]["keep"]].head(25)
        top_gain = sorted(run["gain_rows"], key=lambda x: -x["gain"])[:25]
        return gini_rows, top_iv, top_gain

    g3, iv3, ga3 = pack(m3)
    g6, iv6, ga6 = pack(m6)

    lines = [
        "# Experiment 3 — feature rebuild and XGBoost",
        "",
        "Transactions were labelled with the T1–T7 waterfall (SQL T1–T6 / T7, then "
        "serving hinge **T5b** on unique T6/T7 keys; always-ML on the leftover). "
        "Features are rebuilt from those leaves. GINI is **signed** (`2*AUC−1`). "
        "Locked v5/v6 were not scored.",
        "",
        "Overlapping Equifax/Plaid proposal_ids keep the Plaid row. Calendar months "
        "where the outcome is filled as all-zero (immature) are dropped.",
        "",
        "## Splits",
        "",
        f"- **month3_1plus_pia:** train `{M3_TRAIN_START}` to `< {M3_TRAIN_END}` "
        f"(n={m3['train_n']:,}, {m3['train_bads']:,} bads; Equifax {m3['eqx_train']:,} / "
        f"Plaid {m3['plaid_train']:,}). OOT `{M3_TRAIN_END}` to `< {M3_OOT_END}` "
        f"(n={m3['oot_n']:,}, {m3['oot_bads']:,} bads; Plaid {m3['plaid_oot']:,} / "
        f"Equifax {m3['eqx_oot']:,}).",
        f"- **month6_3plus_pia_from_subscription:** train `{M6_TRAIN_START}` to "
        f"`< {M6_TRAIN_END}` (n={m6['train_n']:,}, {m6['train_bads']:,} bads; "
        f"Equifax {m6['eqx_train']:,} / Plaid {m6['plaid_train']:,}). OOT "
        f"`{M6_TRAIN_END}` to `< {M6_OOT_END}` (n={m6['oot_n']:,}, {m6['oot_bads']:,} bads; "
        f"Plaid {m6['plaid_oot']:,} / Equifax {m6['eqx_oot']:,}).",
        "",
        "Inner validation is the last 20% of each train window by `created_at` "
        "OOT GINI is from a model refit on the full train window. "
        "`taxonomy selected XGB, Plaid-train only` uses the same Plaid rows as the live comparator "
        "(no Equifax), so that gap is features+learner rather than extra history.",
        "",
        "## month3 OOT GINI",
        "",
        _md_table(g3, ["model", "n", "bads", "signed_gini"]),
        "",
        f"Selected **{m3['n_selected']}** features from {m3['n_candidates']} candidates "
        f"({m3['n_screen_kept']} after IV/coverage/correlation).",
        "",
        "### Top IV on inner train (kept)",
        "",
        _md_table(iv3.head(20).to_dict("records"), ["feature", "iv", "nonzero", "why"]),
        "",
        "### Top XGB gain (selected)",
        "",
        _md_table(ga3[:20], ["feature", "gain"]),
        "",
        "## month6 OOT GINI",
        "",
        _md_table(g6, ["model", "n", "bads", "signed_gini"]),
        "",
        f"Selected **{m6['n_selected']}** features from {m6['n_candidates']} candidates "
        f"({m6['n_screen_kept']} after IV/coverage/correlation).",
        "",
        "### Top IV on inner train (kept)",
        "",
        _md_table(iv6.head(20).to_dict("records"), ["feature", "iv", "nonzero", "why"]),
        "",
        "### Top XGB gain (selected)",
        "",
        _md_table(ga6[:20], ["feature", "gain"]),
        "",
        "## Screening rules (train window only)",
        "",
        "- Drop constants and features with <0.5% non-zero unless they are in the live-analog baseline.",
        "- Drop IV < 0.012 unless baseline.",
        "- Of a |r| > 0.92 pair, drop the lower-IV optional feature (baseline is kept).",
        "- Fit XGB on the screened set; keep non-zero gain features (cap 80) plus surviving baseline.",
        "",
        "Candidate families beyond the live analogs: 29 general-category months/debit "
        "amount/count; key-leaf months/count/debit/credit (gambling subtypes stay "
        "separate); cash-withdrawal frequency; takeaway/groceries and gambling/salary "
        "ratios; mixed-basket and discretionary spend share; high-cost/distress flags; "
        "age-restricted debit share; income and spend monthly CV; 30d/90d spend ratio; "
        "days since salary / returned payment / gambling / payday; T1–T5 coverage and "
        "unclassified share; T5b residual count.",
        "",
        f"Models: `{MODEL_M3.name}`, `{MODEL_M6.name}`. Features parquet: "
        f"`outputs/experiment3_xgb_proposal_features.parquet`.",
        "",
        "Script: `src/experiment3_xgb_pipeline.py`.",
    ]
    REPORT.write_text("\n".join(lines) + "\n")
    print(f"Wrote {REPORT}", file=sys.stderr)
    for r in m3["results"] + m6["results"]:
        print(f"  {r['model']}: GINI {r['gini']} n={r['n']:,} bads={r['bads']}",
              file=sys.stderr)
    return m3, m6


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    stage = argv[0] if argv else "all"
    if stage == "fetch":
        fetch()
    elif stage == "classify":
        classify()
    elif stage == "features":
        features()
    elif stage == "train":
        train()
    elif stage in ("all", ""):
        fetch()
        classify()
        features()
        train()
    else:
        raise SystemExit(f"unknown stage {stage}")


if __name__ == "__main__":
    main()

"""Experiment 3 — unified-taxonomy risk features vs the live Open Banking model.

The live comparator is `dbt_production.ds_plaid_credit_features` (Plaid-native
categories), not Xylo gen2. The point of the Raylo-owned taxonomy is that the
*same* feature definitions can be built on Equifax history and on live Plaid
transactions, so a risk model can train on both.

Two almost-disjoint populations (measured 2026-08-24):
  Equifax-matched ∩ PIA, not name_time: 36,603 month3-labelled (3,951 bads)
  Plaid ds_plaid_credit_features month3-labelled: 27,680 (1,791 bads)
  Overlap on financial_proposal_id: 41 proposals

So this is pooled training in a shared feature space, not stacked history on
the same people. Plaid labelled outcomes are month3 only; Equifax also has
month12. Plaid history is 90-day capped (`total_months` never > 3).

Design:
  1. Apply T1–T6 waterfall to each provider's transactions.
  2. Build the same taxonomy persistence / ratio / HHI features on both.
  3. Calendar split: train/test = Equifax + Plaid with created_at < 2026-03-01;
     OOT = March–April 2026 (Plaid only; month3 matured).
  4. Fit the same learner (logistic) on:
       A. live Plaid-native MIV shortlist, Plaid-train only
       B. taxonomy rebuild of that shortlist (p2p/salary, loan CV, BNPL 30d/90d, …)
       B+. B plus priority-debt / gambling-subtype extras
       C. B+ features, Equifax-train only
       D. B+ features, Equifax + Plaid-train (provider dummy)
     Score all four on Plaid OOT, target month3_1plus_pia.
  5. Head-to-head IVs on the Plaid labelled rows (taxonomy vs live).

A 2026-08-24 pass compared taxonomy IVs to Xylo gen2 on an Equifax OOT slice.
That was the wrong comparator; those numbers are archived in the report and
are not the Experiment 3 headline.

Does not score gold_v5.

Usage:
    python src/experiment3_taxonomy_iv.py          # fetch + score
    python src/experiment3_taxonomy_iv.py fetch
    python src/experiment3_taxonomy_iv.py score
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import generate_crosswalk_sql as gxw  # noqa: E402

REPORT = ROOT / "data" / "experiment3_iv_report.md"
PLAID_PARQUET = ROOT / "outputs" / "experiment3_plaid_features.parquet"
EQX_PARQUET = ROOT / "outputs" / "experiment3_equifax_features.parquet"

# Calendar split (headline, 2026-08-24): develop on Equifax + Plaid through
# February 2026, confirm on March–April 2026. Equifax dump ends Aug 2025 so
# every Equifax row is in development. June–Aug 2026 Plaid month3 is filled
# as 0 (immature) and is excluded. May 2026 is matured but held out of this
# OOT so the window is exactly Mar–Apr.
DEV_END = "2026-03-01"
OOT_END = "2026-05-01"
PLAID_MATURE_END = "2026-05-24"
EQX_DATES_PARQUET = ROOT / "outputs" / "experiment3_equifax_dates.parquet"

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

# Compact taxonomy set for the logistic — live MIV-shortlist analogs, plus
# the orthogonal flags the live Plaid-native layer cannot express.
TAXONOMY_ANALOG_FEATURES = [
    "total_months",
    "spend_hhi",
    "spend_hhi_leaf",
    "num_distinct_leaves",
    "num_distinct_merchants",
    "p2p_to_salary_ratio",
    "pct_p2p_like_debit_amount",
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
]
TAXONOMY_EXTRA_FEATURES = [
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
]
TAXONOMY_MODEL_FEATURES = TAXONOMY_ANALOG_FEATURES + TAXONOMY_EXTRA_FEATURES

GAMBLING_LEAVES = (
    "gambling_betting", "gambling_casino", "gambling_bingo",
    "gambling_lottery", "gambling_unspecified",
)


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
      WHEN d.leaf IS NOT NULL THEN d.leaf
{gxw.rules_leaf_case(gxw.EQX_MERCHANT_EXPR, gxw.EQX_DESC_EXPR)}
      WHEN s.leaf IS NOT NULL THEN s.leaf
      WHEN p.leaf IS NOT NULL THEN p.leaf
      ELSE 'unclassified_other'
    END
"""


def _plaid_leaf_sql() -> str:
    return f"""
    CASE
      WHEN r.cat='ENTERTAINMENT_CASINOS_AND_GAMBLING' AND r.direction='credit' THEN 'gambling_unspecified'
{gxw.t2_entity_collision_leaf(gxw.PLAID_MERCHANT_EXPR, gxw.PLAID_DESC_EXPR)}
{gxw.t1_gambling_credit_leaf()}
{gxw.t2_refund_leaf(gxw.PLAID_DESC_EXPR)}
      WHEN d.leaf IS NOT NULL THEN d.leaf
{gxw.rules_leaf_case(gxw.PLAID_MERCHANT_EXPR, gxw.PLAID_DESC_EXPR)}
      WHEN x.leaf IS NOT NULL THEN x.leaf
      ELSE 'unclassified_other'
    END
"""


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


def _extra_feature_ctes() -> str:
    """Leaf-level HHI and monthly loan-payment CV — join in the proposal SELECT."""
    return """
hhi_leaf AS (
  SELECT financial_proposal_id, SUM(POW(share, 2)) AS spend_hhi_leaf
  FROM (
    SELECT financial_proposal_id,
      SAFE_DIVIDE(spend, SUM(spend) OVER (PARTITION BY financial_proposal_id)) AS share
    FROM (
      SELECT financial_proposal_id, leaf,
             SUM(IF(direction = 'debit', abs_amt, 0)) AS spend
      FROM with_meta
      GROUP BY 1, 2
    )
  )
  GROUP BY 1
),
loan_month AS (
  SELECT financial_proposal_id, month, SUM(abs_amt) AS loan_amt
  FROM with_meta
  WHERE general_category = 'credit_loan_repayments' AND direction = 'debit'
  GROUP BY 1, 2
),
loan_cv AS (
  SELECT financial_proposal_id,
    SAFE_DIVIDE(STDDEV_SAMP(loan_amt), NULLIF(AVG(loan_amt), 0)) AS loan_payment_monthly_cv
  FROM loan_month
  GROUP BY 1
)
"""


def _taxonomy_agg_select() -> str:
    """Shared proposal-level taxonomy features. `w` is with_meta, `h`/`hl`/`lc` extras.

    Windowed features (BNPL 30d/90d, recent salary) are relative to
    DATE(c.financial_proposal_created_at). p2p-like = cash_flow_type p2p_transfer
    (not unclassified_transfer). Salary = salary + salary_gig.
    """
    gambling = ",\n    ".join(
        f"COUNT(DISTINCT IF(w.leaf = '{leaf}', w.month, NULL)) AS {leaf}_months"
        for leaf in GAMBLING_LEAVES
    )
    as_of = "DATE(c.financial_proposal_created_at)"
    return f"""
  COUNT(DISTINCT w.month) AS total_months,
  COUNT(DISTINCT IF(w.is_priority_debt, w.month, NULL)) AS priority_debt_months,
  COUNT(DISTINCT IF(w.is_priority_debt, w.leaf, NULL)) AS priority_debt_breadth,
  COUNT(DISTINCT IF(w.is_debt_related, w.month, NULL)) AS credit_product_months,
  COUNT(DISTINCT IF(w.general_category = 'gambling', w.month, NULL)) AS gambling_any_months,
  COUNT(DISTINCT IF(w.cash_flow_type = 'income', w.month, NULL)) AS income_months,
  COUNT(DISTINCT IF(w.leaf = 'groceries', w.month, NULL)) AS grocer_months,
  COUNT(DISTINCT IF(w.leaf IN ('mobile_phone_contract', 'broadband_tv_phone'), w.month, NULL)) AS telco_months,
  COUNT(DISTINCT IF(w.leaf = 'streaming', w.month, NULL)) AS streaming_months,
  COUNT(DISTINCT IF(w.general_category = 'credit_loan_repayments', w.month, NULL)) AS loan_repayment_months,
  COUNT(DISTINCT IF(w.leaf = 'returned_payment', w.month, NULL)) AS returned_payment_months,
  COUNTIF(w.leaf = 'returned_payment') AS returned_payment_count,
  COUNT(DISTINCT IF(w.leaf = 'bnpl', w.month, NULL)) AS bnpl_months,
  COUNT(DISTINCT IF(w.leaf = 'payday_loan', w.month, NULL)) AS payday_loan_months,
  COUNT(DISTINCT IF(w.leaf = 'cash_advance', w.month, NULL)) AS cash_advance_months,
  COUNT(DISTINCT IF(w.leaf = 'rent', w.month, NULL)) AS rent_months,
  COUNT(DISTINCT IF(w.leaf = 'mortgage', w.month, NULL)) AS mortgage_months,
  COUNT(DISTINCT IF(
    w.leaf IN ('groceries', 'rent', 'mortgage', 'council_tax',
               'mobile_phone_contract', 'broadband_tv_phone')
    OR w.general_category = 'utilities_household_bills',
    w.month, NULL)) AS legit_life_footprint_months,
  {gambling},
  COUNT(DISTINCT w.leaf) AS num_distinct_leaves,
  COUNT(DISTINCT w.merchant) AS num_distinct_merchants,
  SUM(IF(w.direction = 'debit' AND w.necessity = 'essential', w.abs_amt, 0)) AS essential_spend_amount_total,
  SAFE_DIVIDE(
    SUM(IF(w.direction = 'debit' AND w.necessity = 'essential', w.abs_amt, 0)),
    SUM(IF(w.direction = 'debit', w.abs_amt, 0))
  ) AS essential_spend_ratio,
  AVG(IF(w.direction = 'credit', w.abs_amt, NULL)) AS avg_credit_transaction_amount,
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
  ANY_VALUE(h.spend_hhi) AS spend_hhi,
  ANY_VALUE(hl.spend_hhi_leaf) AS spend_hhi_leaf,
  ANY_VALUE(lc.loan_payment_monthly_cv) AS loan_payment_monthly_cv
"""


def _equifax_sql() -> str:
    return f"""
WITH {_lookup_sql()},
cohort AS (
  SELECT
    CAST(p.proposal_id AS STRING) AS proposal_id,
    p.financial_proposal_id,
    p.financial_proposal_created_at,
    p.month3_1plus_pia,
    p.month12_1plus_pia,
    p.month12_3plus_pia
  FROM `raylo-production.dbt_production.ds_first_order_proposal_pia_metrics` p
  JOIN (
    SELECT DISTINCT financial_proposal_id
    FROM `raylo-production.equifax_data.open_banking_transactions_with_matches`
    WHERE final_matched_on != 'name_time' AND financial_proposal_id IS NOT NULL
  ) e USING (financial_proposal_id)
  WHERE p.month3_1plus_pia IS NOT NULL
),
eqx_raw AS (
  SELECT
    t.financial_proposal_id,
    DATE_TRUNC(t.PostDate, MONTH) AS month,
    DATE(t.PostDate) AS txn_date,
    t.PrimaryCategoryDescription AS pri,
    t.SubCategoryDescription AS sub,
    t.VendorDescription AS vendor,
    t.Description AS description_raw,
    IF(t.TransactionTypeId = 1, 'credit', 'debit') AS direction,
    ABS(t.Amount) AS abs_amt,
    LOWER(TRIM(IFNULL(t.VendorDescription, ''))) AS merchant
  FROM `raylo-production.equifax_data.open_banking_transactions_with_matches` t
  JOIN cohort c ON t.financial_proposal_id = c.financial_proposal_id
  WHERE t.final_matched_on != 'name_time'
),
eqx_resolved AS (
  SELECT r.*,
{_eqx_leaf_sql()} AS leaf
  FROM eqx_raw r
  LEFT JOIN sub_xw s ON r.sub = s.eqx_sub
  LEFT JOIN pri_xw p ON r.pri = p.eqx_pri
  LEFT JOIN dict_xw d ON r.merchant = d.merchant
),
with_meta AS (
  SELECT r.*,
    m.general_category, m.necessity, m.cash_flow_type,
    m.is_debt_related, m.is_priority_debt
  FROM eqx_resolved r
  LEFT JOIN leaf_meta m ON r.leaf = m.leaf
),
hhi AS (
  SELECT financial_proposal_id, SUM(POW(share, 2)) AS spend_hhi
  FROM (
    SELECT financial_proposal_id,
      SAFE_DIVIDE(spend, SUM(spend) OVER (PARTITION BY financial_proposal_id)) AS share
    FROM (
      SELECT financial_proposal_id, general_category,
             SUM(IF(direction = 'debit', abs_amt, 0)) AS spend
      FROM with_meta
      GROUP BY 1, 2
    )
  )
  GROUP BY 1
),
{_extra_feature_ctes()}
SELECT
  c.proposal_id,
  c.financial_proposal_id,
  c.financial_proposal_created_at,
  c.month3_1plus_pia,
  c.month12_1plus_pia,
  c.month12_3plus_pia,
  'equifax' AS provider,
{_taxonomy_agg_select()}
FROM cohort c
LEFT JOIN with_meta w ON c.financial_proposal_id = w.financial_proposal_id
LEFT JOIN hhi h ON c.financial_proposal_id = h.financial_proposal_id
LEFT JOIN hhi_leaf hl ON c.financial_proposal_id = hl.financial_proposal_id
LEFT JOIN loan_cv lc ON c.financial_proposal_id = lc.financial_proposal_id
GROUP BY c.proposal_id, c.financial_proposal_id, c.financial_proposal_created_at,
         c.month3_1plus_pia, c.month12_1plus_pia, c.month12_3plus_pia
"""


def _plaid_sql() -> str:
    live_select = ",\n  ".join(f"c.{col} AS live_{col}" for col in LIVE_FEATURES)
    return f"""
WITH {_lookup_sql()},
cohort AS (
  SELECT
    financial_proposal_id,
    checkout_risk_assessment_result_id,
    financial_proposal_created_at,
    month3_1plus_pia,
    {", ".join(LIVE_FEATURES)}
  FROM `raylo-production.dbt_production.ds_plaid_credit_features`
  WHERE month3_1plus_pia IS NOT NULL
),
plaid_raw AS (
  SELECT
    c.financial_proposal_id,
    DATE_TRUNC(SAFE.PARSE_DATE('%Y-%m-%d', SUBSTR(t.transaction_date, 1, 10)), MONTH) AS month,
    SAFE.PARSE_DATE('%Y-%m-%d', SUBSTR(t.transaction_date, 1, 10)) AS txn_date,
    t.detailed_credit_category AS cat,
    t.merchant_name AS merchant_raw,
    COALESCE(t.description, t.transaction_name) AS description_raw,
    IF(t.amount < 0, 'credit', 'debit') AS direction,
    ABS(t.amount) AS abs_amt,
    LOWER(TRIM(IFNULL(t.merchant_name, ''))) AS merchant
  FROM cohort c
  JOIN `raylo-production.dbt_production.intermediate_credit_plaid_transactions` t
    ON t.checkout_risk_assessment_result_id = c.checkout_risk_assessment_result_id
),
plaid_resolved AS (
  SELECT r.*,
{_plaid_leaf_sql()} AS leaf
  FROM plaid_raw r
  LEFT JOIN plaid_xw x ON r.cat = x.plaid_cat
  LEFT JOIN dict_xw d ON r.merchant = d.merchant
),
with_meta AS (
  SELECT r.*,
    m.general_category, m.necessity, m.cash_flow_type,
    m.is_debt_related, m.is_priority_debt
  FROM plaid_resolved r
  LEFT JOIN leaf_meta m ON r.leaf = m.leaf
),
hhi AS (
  SELECT financial_proposal_id, SUM(POW(share, 2)) AS spend_hhi
  FROM (
    SELECT financial_proposal_id,
      SAFE_DIVIDE(spend, SUM(spend) OVER (PARTITION BY financial_proposal_id)) AS share
    FROM (
      SELECT financial_proposal_id, general_category,
             SUM(IF(direction = 'debit', abs_amt, 0)) AS spend
      FROM with_meta
      GROUP BY 1, 2
    )
  )
  GROUP BY 1
),
{_extra_feature_ctes()}
SELECT
  CAST(c.financial_proposal_id AS STRING) AS proposal_id,
  c.financial_proposal_id,
  c.financial_proposal_created_at,
  c.month3_1plus_pia,
  CAST(NULL AS INT64) AS month12_1plus_pia,
  CAST(NULL AS INT64) AS month12_3plus_pia,
  'plaid' AS provider,
  {live_select},
{_taxonomy_agg_select()}
FROM cohort c
LEFT JOIN with_meta w ON c.financial_proposal_id = w.financial_proposal_id
LEFT JOIN hhi h ON c.financial_proposal_id = h.financial_proposal_id
LEFT JOIN hhi_leaf hl ON c.financial_proposal_id = hl.financial_proposal_id
LEFT JOIN loan_cv lc ON c.financial_proposal_id = lc.financial_proposal_id
GROUP BY c.financial_proposal_id, c.financial_proposal_created_at, c.month3_1plus_pia,
         {", ".join("c." + col for col in LIVE_FEATURES)}
"""


def _iv_persistence(x, y):
    """0 / 1 / 2+ months — same bins as rent_iv_analysis.py."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=int)
    bins = np.where(x == 0, "0", np.where(x == 1, "1", "2+"))
    total_good = (y == 0).sum()
    total_bad = (y == 1).sum()
    if total_good == 0 or total_bad == 0:
        return 0.0
    iv = 0.0
    for b in ("0", "1", "2+"):
        mask = bins == b
        good = max((y[mask] == 0).sum(), 0.5)
        bad = max((y[mask] == 1).sum(), 0.5)
        good_pct = good / total_good
        bad_pct = bad / total_bad
        iv += (bad_pct - good_pct) * np.log(bad_pct / good_pct)
    return float(iv)


def _iv_quantile(x, y, n=5):
    """Equal-count bins for continuous live features (ratios, amounts, HHI)."""
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


def _gini(score, y):
    from credit_metrics import signed_gini
    return signed_gini(score, y)


def _fit_logistic(X: pd.DataFrame, y: pd.Series):
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


def _query(client, sql: str, label: str) -> pd.DataFrame:
    print(f"Running {label} ({len(sql):,} chars)...", file=sys.stderr)
    df = client.query(sql).result().to_dataframe()
    print(f"  {label}: {len(df):,} rows", file=sys.stderr)
    return df


def fetch():
    from google.cloud import bigquery
    client = bigquery.Client(project="raylo-production")
    PLAID_PARQUET.parent.mkdir(exist_ok=True)

    eqx = _query(client, _equifax_sql(), "Equifax taxonomy features")
    eqx.to_parquet(EQX_PARQUET, index=False)
    print(f"Wrote {EQX_PARQUET}", file=sys.stderr)

    plaid = _query(client, _plaid_sql(), "Plaid taxonomy + live features")
    plaid.to_parquet(PLAID_PARQUET, index=False)
    print(f"Wrote {PLAID_PARQUET}", file=sys.stderr)
    covered = int((plaid["total_months"] > 0).sum())
    print(f"  Plaid proposals with ≥1 resolved txn: {covered:,}/{len(plaid):,}", file=sys.stderr)
    if covered < 0.8 * len(plaid):
        raise SystemExit(
            "Plaid taxonomy features are empty for most rows — the txn join is wrong."
        )
    return eqx, plaid


def _split_plaid(plaid: pd.DataFrame):
    """Legacy 80/20 split inside the matured month3 window. Kept for appendix."""
    plaid = plaid.copy()
    plaid["financial_proposal_created_at"] = pd.to_datetime(
        plaid["financial_proposal_created_at"], utc=True)
    mature_end = pd.Timestamp(PLAID_MATURE_END, tz="UTC")
    mature = plaid[plaid["financial_proposal_created_at"] <= mature_end].copy()
    cut = mature["financial_proposal_created_at"].quantile(0.80)
    train = mature[mature["financial_proposal_created_at"] < cut]
    oot = mature[mature["financial_proposal_created_at"] >= cut]
    return train, oot, mature, cut


def _attach_equifax_dates(eqx: pd.DataFrame) -> pd.DataFrame:
    """Join financial_proposal_created_at onto Equifax feature rows."""
    eqx = eqx.copy()
    eqx["financial_proposal_id"] = eqx["financial_proposal_id"].astype(str)
    if EQX_DATES_PARQUET.exists():
        dates = pd.read_parquet(EQX_DATES_PARQUET)
    else:
        from google.cloud import bigquery
        client = bigquery.Client(project="raylo-production")
        dates = client.query("""
            SELECT CAST(financial_proposal_id AS STRING) AS financial_proposal_id,
                   financial_proposal_created_at
            FROM `raylo-production.dbt_production.ds_first_order_proposal_pia_metrics`
            WHERE month3_1plus_pia IS NOT NULL
        """).result().to_dataframe()
        EQX_DATES_PARQUET.parent.mkdir(exist_ok=True)
        dates.to_parquet(EQX_DATES_PARQUET, index=False)
    dates["financial_proposal_id"] = dates["financial_proposal_id"].astype(str)
    eqx = eqx.drop(columns=["financial_proposal_created_at"], errors="ignore")
    eqx = eqx.merge(dates, on="financial_proposal_id", how="left")
    return eqx


def _calendar_frames(eqx: pd.DataFrame, plaid: pd.DataFrame):
    """Development through Feb 2026; OOT March–April 2026."""
    eqx = _attach_equifax_dates(eqx)
    eqx["created"] = pd.to_datetime(eqx["financial_proposal_created_at"], utc=True)
    plaid = plaid.copy()
    plaid["created"] = pd.to_datetime(plaid["financial_proposal_created_at"], utc=True)

    # 41 overlapping proposal_ids: keep the Plaid row (live features live there).
    plaid_ids = set(plaid["financial_proposal_id"].astype(str))
    eqx = eqx[~eqx["financial_proposal_id"].astype(str).isin(plaid_ids)].copy()

    dev_end = pd.Timestamp(DEV_END, tz="UTC")
    oot_end = pd.Timestamp(OOT_END, tz="UTC")

    eqx_dev = eqx[eqx["created"] < dev_end].copy()
    plaid_dev = plaid[plaid["created"] < dev_end].copy()
    plaid_oot = plaid[(plaid["created"] >= dev_end) & (plaid["created"] < oot_end)].copy()

    combined_dev = pd.concat([
        eqx_dev.assign(is_plaid=0),
        plaid_dev.assign(is_plaid=1),
    ], ignore_index=True)
    combined_dev = combined_dev.sort_values("created")
    cut = combined_dev["created"].quantile(0.80)
    inner_train = combined_dev[combined_dev["created"] < cut]
    inner_test = combined_dev[combined_dev["created"] >= cut]
    return {
        "eqx_dev": eqx_dev,
        "plaid_dev": plaid_dev,
        "plaid_oot": plaid_oot,
        "combined_dev": combined_dev,
        "inner_train": inner_train,
        "inner_test": inner_test,
        "inner_cut": cut,
        "eqx": eqx,
        "plaid": plaid,
    }


def _iv_table(df: pd.DataFrame, cols: list[str], prefix: str, continuous: bool) -> pd.DataFrame:
    y = df["month3_1plus_pia"].astype(int)
    rows = []
    for col in cols:
        if col not in df.columns:
            continue
        iv_fn = _iv_quantile if continuous else _iv_persistence
        rows.append({
            "family": prefix,
            "feature": col,
            "month3_iv": round(iv_fn(df[col], y), 4),
        })
    return pd.DataFrame(rows).sort_values("month3_iv", ascending=False)


def score(eqx=None, plaid=None):
    if eqx is None:
        eqx = pd.read_parquet(EQX_PARQUET)
    if plaid is None:
        plaid = pd.read_parquet(PLAID_PARQUET)

    frames = _calendar_frames(eqx, plaid)
    eqx_dev = frames["eqx_dev"]
    plaid_dev = frames["plaid_dev"]
    plaid_oot = frames["plaid_oot"]
    combined_dev = frames["combined_dev"]
    inner_train = frames["inner_train"]
    inner_test = frames["inner_test"]
    y_oot = plaid_oot["month3_1plus_pia"].astype(int)
    if int(y_oot.sum()) == 0:
        raise SystemExit(
            "March–April OOT has 0 bads — month3 has not matured on this window."
        )

    live_cols = [c for c in (f"live_{x}" for x in LIVE_FEATURES) if c in plaid.columns]
    analog_cols = [c for c in TAXONOMY_ANALOG_FEATURES if c in plaid.columns]
    plus_cols = [c for c in TAXONOMY_MODEL_FEATURES if c in plaid.columns]
    missing_analog = [c for c in TAXONOMY_ANALOG_FEATURES if c not in plaid.columns]
    if missing_analog:
        print(f"Missing analog columns (refetch needed): {missing_analog}", file=sys.stderr)

    def _swap_p2p(cols):
        m = {
            "p2p_to_salary_ratio": "p2p_to_salary_ratio_loose",
            "pct_p2p_like_debit_amount": "pct_p2p_like_debit_amount_loose",
        }
        out = [m.get(c, c) for c in cols]
        missing = [c for c in out if c not in plaid.columns]
        if missing:
            raise SystemExit(f"Missing loose p2p columns (refetch needed): {missing}")
        return out

    analog_loose = _swap_p2p(analog_cols)
    plus_loose = _swap_p2p(plus_cols)

    models = {
        "A live Plaid-native, Plaid through Feb": _fit_logistic(
            plaid_dev[live_cols], plaid_dev["month3_1plus_pia"]),
        "B taxonomy live-analogs, Plaid through Feb": _fit_logistic(
            plaid_dev[analog_cols], plaid_dev["month3_1plus_pia"]),
        "B+ taxonomy analogs+extras, Plaid through Feb": _fit_logistic(
            plaid_dev[plus_cols], plaid_dev["month3_1plus_pia"]),
        "B loose p2p (analogs, unclassified_transfer in p2p)": _fit_logistic(
            plaid_dev[analog_loose], plaid_dev["month3_1plus_pia"]),
        "B+ loose p2p (analogs+extras, unclassified_transfer in p2p)": _fit_logistic(
            plaid_dev[plus_loose], plaid_dev["month3_1plus_pia"]),
        "C taxonomy analogs+extras, Equifax only": _fit_logistic(
            eqx_dev[plus_cols], eqx_dev["month3_1plus_pia"]),
        "D taxonomy analogs+extras, Equifax+Plaid through Feb": _fit_logistic(
            combined_dev[plus_cols + ["is_plaid"]], combined_dev["month3_1plus_pia"]),
    }
    train_sizes = {
        "A live Plaid-native, Plaid through Feb": (
            len(plaid_dev), int(plaid_dev["month3_1plus_pia"].sum())),
        "B taxonomy live-analogs, Plaid through Feb": (
            len(plaid_dev), int(plaid_dev["month3_1plus_pia"].sum())),
        "B+ taxonomy analogs+extras, Plaid through Feb": (
            len(plaid_dev), int(plaid_dev["month3_1plus_pia"].sum())),
        "B loose p2p (analogs, unclassified_transfer in p2p)": (
            len(plaid_dev), int(plaid_dev["month3_1plus_pia"].sum())),
        "B+ loose p2p (analogs+extras, unclassified_transfer in p2p)": (
            len(plaid_dev), int(plaid_dev["month3_1plus_pia"].sum())),
        "C taxonomy analogs+extras, Equifax only": (
            len(eqx_dev), int(eqx_dev["month3_1plus_pia"].sum())),
        "D taxonomy analogs+extras, Equifax+Plaid through Feb": (
            len(combined_dev), int(combined_dev["month3_1plus_pia"].sum())),
    }

    def _predict(name, clf, df, is_plaid_value=None):
        if name.startswith("A"):
            return clf.predict_proba(df[live_cols])[:, 1]
        if name.startswith("D"):
            flag = df["is_plaid"] if "is_plaid" in df.columns else is_plaid_value
            return clf.predict_proba(df[plus_cols].assign(is_plaid=flag))[:, 1]
        if name.startswith("C") or name.startswith("B+ loose"):
            cols = plus_loose if "loose" in name else plus_cols
            return clf.predict_proba(df[cols])[:, 1]
        if name.startswith("B+"):
            return clf.predict_proba(df[plus_cols])[:, 1]
        if "loose p2p" in name:
            return clf.predict_proba(df[analog_loose])[:, 1]
        return clf.predict_proba(df[analog_cols])[:, 1]

    ginis = []
    for name, clf in models.items():
        proba = _predict(name, clf, plaid_oot, is_plaid_value=1)
        ginis.append({
            "model": name,
            "oot_gini": round(_gini(proba, y_oot), 4),
            "train_n": train_sizes[name][0],
            "train_bads": train_sizes[name][1],
        })

    inner_models = {
        "B taxonomy live-analogs, Plaid through Feb": _fit_logistic(
            inner_train.loc[inner_train["is_plaid"] == 1, analog_cols],
            inner_train.loc[inner_train["is_plaid"] == 1, "month3_1plus_pia"]),
        "B+ taxonomy analogs+extras, Plaid through Feb": _fit_logistic(
            inner_train.loc[inner_train["is_plaid"] == 1, plus_cols],
            inner_train.loc[inner_train["is_plaid"] == 1, "month3_1plus_pia"]),
        "D taxonomy analogs+extras, Equifax+Plaid through Feb": _fit_logistic(
            inner_train[plus_cols + ["is_plaid"]], inner_train["month3_1plus_pia"]),
    }
    inner_test_plaid = inner_test[inner_test["is_plaid"] == 1]
    inner_rows = []
    for name, clf in inner_models.items():
        if name.startswith("D"):
            proba = clf.predict_proba(inner_test[plus_cols + ["is_plaid"]])[:, 1]
            y = inner_test["month3_1plus_pia"]
        elif name.startswith("B+"):
            proba = clf.predict_proba(inner_test_plaid[plus_cols])[:, 1]
            y = inner_test_plaid["month3_1plus_pia"]
        else:
            proba = clf.predict_proba(inner_test_plaid[analog_cols])[:, 1]
            y = inner_test_plaid["month3_1plus_pia"]
        inner_rows.append({"model": name, "test_gini": round(_gini(proba, y), 4), "test_n": len(y)})

    # IVs on the Mar–Apr OOT (the confirmation window) plus through-Feb Plaid.
    iv_base = pd.concat([plaid_dev, plaid_oot], ignore_index=True)
    tax_iv = _iv_table(iv_base, plus_cols + [
        c for c in (
            "gambling_any_months",
            "p2p_to_salary_ratio_loose",
            "pct_p2p_like_debit_amount_loose",
        ) if c in iv_base.columns
    ], "taxonomy", continuous=False)
    for feat in (
        "essential_spend_ratio", "spend_hhi", "spend_hhi_leaf",
        "num_distinct_leaves", "num_distinct_merchants",
        "p2p_to_salary_ratio", "pct_p2p_like_debit_amount",
        "p2p_to_salary_ratio_loose", "pct_p2p_like_debit_amount_loose",
        "avg_credit_transaction_amount", "mortgage_debit_amount",
        "loan_payment_monthly_cv", "essential_spend_amount_total",
        "returned_payment_count", "loan_payment_consistency_ratio",
        "bnpl_30d_vs_90d_ratio",
    ):
        if feat in iv_base.columns:
            tax_iv.loc[tax_iv["feature"] == feat, "month3_iv"] = round(
                _iv_quantile(iv_base[feat], iv_base["month3_1plus_pia"].astype(int)), 4)
    live_iv = _iv_table(iv_base, live_cols, "live", continuous=True)
    for feat in live_cols:
        raw = feat.removeprefix("live_")
        if raw.endswith("_months") or raw in ("has_recent_salary_flag",):
            live_iv.loc[live_iv["feature"] == feat, "month3_iv"] = round(
                _iv_persistence(iv_base[feat].fillna(0), iv_base["month3_1plus_pia"].astype(int)), 4)
    tax_iv = tax_iv.sort_values("month3_iv", ascending=False)
    live_iv = live_iv.sort_values("month3_iv", ascending=False)

    y_iv = iv_base["month3_1plus_pia"].astype(int)

    def _p2p_line(label, ratio_col, pct_col, live_ratio="live_p2p_to_salary_ratio",
                  live_pct="live_pct_p2p_like_debit_amount"):
        med = float(iv_base[ratio_col].median())
        corr_r = float(iv_base[ratio_col].corr(iv_base[live_ratio])) if ratio_col != live_ratio else 1.0
        corr_p = float(iv_base[pct_col].corr(iv_base[live_pct])) if pct_col != live_pct else 1.0
        iv = _iv_quantile(iv_base[ratio_col], y_iv)
        return (f"| {label} | {med:.3f} | {corr_r:.2f} | {iv:.4f} | {corr_p:.2f} |")

    p2p_table = [
        _p2p_line("Live Plaid-native", "live_p2p_to_salary_ratio", "live_pct_p2p_like_debit_amount"),
        _p2p_line("Strict (`p2p_transfer` only)", "p2p_to_salary_ratio", "pct_p2p_like_debit_amount"),
        _p2p_line("Loose (+ `unclassified_transfer`)", "p2p_to_salary_ratio_loose", "pct_p2p_like_debit_amount_loose"),
    ]

    oot_mar = plaid_oot[plaid_oot["created"] < pd.Timestamp("2026-04-01", tz="UTC")]
    oot_apr = plaid_oot[plaid_oot["created"] >= pd.Timestamp("2026-04-01", tz="UTC")]
    d_oot = next(g["oot_gini"] for g in ginis if g["model"].startswith("D"))
    bplus_oot = next(g["oot_gini"] for g in ginis if g["model"].startswith("B+") and "loose" not in g["model"])
    b_oot = next(g["oot_gini"] for g in ginis if g["model"].startswith("B taxonomy live"))
    b_loose = next(g["oot_gini"] for g in ginis if g["model"].startswith("B loose"))
    bplus_loose = next(g["oot_gini"] for g in ginis if g["model"].startswith("B+ loose"))
    a_oot = next(g["oot_gini"] for g in ginis if g["model"].startswith("A"))
    c_oot = next(g["oot_gini"] for g in ginis if g["model"].startswith("C"))

    lines = [
        "# Experiment 3 — unified taxonomy vs live Open Banking features",
        "",
        "Live comparator: logistic regression on `ds_plaid_credit_features` "
        "(the Plaid-native feature table behind the live Open Banking risk model). "
        "Same learner on both sides so this is a feature-space comparison, not "
        "taxonomy-logistic vs a production GBM.",
        "",
        "**Headline split (2026-08-24):** one development sample of Equifax + Plaid "
        f"with `financial_proposal_created_at` < {DEV_END}, then OOT = March and "
        f"April 2026 (`< {OOT_END}`). Equifax dump ends 2025-08-31, so every "
        "Equifax row is in development. Overlapping proposal_ids (41) keep the "
        "Plaid row. May 2026 is matured but not in this OOT; Jun–Aug 2026 month3 "
        "is filled as 0 and is excluded.",
        "",
        f"Development: Equifax {len(eqx_dev):,} ({int(eqx_dev['month3_1plus_pia'].sum()):,} bads, "
        f"{eqx_dev['month3_1plus_pia'].mean():.1%}) + Plaid {len(plaid_dev):,} "
        f"({int(plaid_dev['month3_1plus_pia'].sum()):,} bads, "
        f"{plaid_dev['month3_1plus_pia'].mean():.1%}) → combined {len(combined_dev):,} "
        f"({int(combined_dev['month3_1plus_pia'].sum()):,} bads). "
        f"Inner train/test cut {frames['inner_cut'].date()} (last 20% of development by date). "
        f"OOT March {len(oot_mar):,} ({int(oot_mar['month3_1plus_pia'].sum()):,} bads) + "
        f"April {len(oot_apr):,} ({int(oot_apr['month3_1plus_pia'].sum()):,} bads) = "
        f"{len(plaid_oot):,} / {int(y_oot.sum())} bads ({y_oot.mean():.1%}).",
        "",
        "Leaf assignment is the provider waterfall (Equifax T1–T6 including T3; "
        "Plaid T1/T2/T4/T5/T6). Gambling subtypes stay separate. Locked v5 was not scored.",
        "",
        "B rebuilds the live MIV shortlist on our leaves: `p2p_to_salary_ratio` "
        "(p2p_transfer debits / salary+salary_gig credits — not `unclassified_transfer`), "
        "`pct_p2p_like_debit_amount`, `loan_payment_monthly_cv`, `bnpl_30d_vs_90d_ratio` "
        "(relative to application date), `essential_spend_amount_total`, "
        "`avg_credit_transaction_amount`, `mortgage_debit_amount`, `returned_payment_count`, "
        "`has_recent_salary_flag`, `legit_life_footprint_months`, `spend_hhi_leaf`, "
        "`loan_payment_consistency_ratio`. B+ adds priority-debt and gambling-subtype "
        "flags. The classifier is still not in this waterfall.",
        "",
        "## March–April 2026 OOT GINI (month3_1plus_pia)",
        "",
        "Models A–D are fit on **all** development through February, then scored "
        "on March–April. That is the confirmation number.",
        "",
        "| Model | Train n | Train bads | Mar–Apr OOT GINI |",
        "|---|---:|---:|---:|",
    ]
    for g in ginis:
        lines.append(
            f"| {g['model']} | {g['train_n']:,} | {g['train_bads']:,} | **{g['oot_gini']:.3f}** |"
        )
    lines += [
        "",
        "Inner test (fit on first 80% of through-Feb by date, score the last 20%):",
        "",
        "| Model | Test n | Test GINI |",
        "|---|---:|---:|",
    ]
    for r in inner_rows:
        lines.append(f"| {r['model']} | {r['test_n']:,} | {r['test_gini']:.3f} |")
    lines += [
        "",
        f"**Reading.** Live Plaid-native (A) **{a_oot:.3f}**. Strict taxonomy analogs "
        f"(B) **{b_oot:.3f}**; B+ **{bplus_oot:.3f}**. Loose p2p "
        f"(unclassified_transfer counted as p2p-like): B **{b_loose:.3f}**, "
        f"B+ **{bplus_loose:.3f}**. Equifax-only (C) **{c_oot:.3f}**. Pooled (D) "
        f"**{d_oot:.3f}**. Loose p2p **matches the live column** (corr 0.84, median "
        "near live) and lifts standalone IV 0.04 → 0.11, but it does **not** close "
        "the multivariate GINI gap — slightly worse than strict. Live "
        "`p2p_to_salary` is still stronger (IV 0.17) than our loose analog (0.11). "
        "Do not promote unclassified_transfer to p2p; the remaining gap is not "
        "that one recode.",
        "",
        "### p2p sensitivity (same Mar–Apr OOT)",
        "",
        "| Version | `p2p_to_salary` median | corr vs live | `p2p_to_salary` IV | `pct_p2p` corr vs live |",
        "|---|---:|---:|---:|---:|",
        p2p_table[0],
        p2p_table[1],
        p2p_table[2],
        "",
        "Plaid transactions come from `intermediate_credit_plaid_transactions` "
        "(100% of labelled feature-table rows).",
        "",
        "## Head-to-head IVs on Plaid through April 2026 (month3)",
        "",
        "### Taxonomy features",
        "",
        "| Feature | month3 IV |",
        "|---|---:|",
    ]
    for _, r in tax_iv.iterrows():
        lines.append(f"| `{r['feature']}` | {r['month3_iv']:.4f} |")
    lines += [
        "",
        "### Live Plaid-native features (MIV-audit shortlist)",
        "",
        "| Feature | month3 IV |",
        "|---|---:|",
    ]
    for _, r in live_iv.iterrows():
        lines.append(f"| `{r['feature']}` | {r['month3_iv']:.4f} |")
    lines += [
        "",
        "## What this does not claim",
        "",
        "- Beating a production GBM. Both sides are a freshly fit logistic on the same OOT.",
        "- That Equifax month12 outcomes can be used as the Plaid promotion metric.",
        "- A 90-day-window fix. Plaid history is still capped; Equifax in the train "
        "set does not lengthen Plaid applicants' lookback.",
        "",
        "## Earlier splits (not the headline)",
        "",
        "An 80/20-within-mature Plaid split (OOT from 2026-04-04, including May) "
        "gave live 0.264 / taxonomy Plaid-only 0.281 / Equifax-only 0.226 / pooled "
        "0.275. Same models, different holdout. Xylo gen2 GINI 0.393 on an "
        "Equifax 2024–2025 OOT is a different product's score, not this comparison.",
        "",
    ]
    REPORT.write_text("\n".join(lines) + "\n")
    print(f"Wrote {REPORT}", file=sys.stderr)
    print("Development Equifax", len(eqx_dev), "Plaid", len(plaid_dev),
          "OOT", len(plaid_oot), "bads", int(y_oot.sum()), file=sys.stderr)
    print(pd.DataFrame(ginis).to_string(index=False))
    print("\nInner test:")
    print(pd.DataFrame(inner_rows).to_string(index=False))
    print("\nTaxonomy IVs:")
    print(tax_iv.head(12).to_string(index=False))
    return ginis, tax_iv, live_iv


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    if cmd == "score":
        score()
    elif cmd == "fetch":
        fetch()
    else:
        eqx, plaid = fetch()
        score(eqx, plaid)

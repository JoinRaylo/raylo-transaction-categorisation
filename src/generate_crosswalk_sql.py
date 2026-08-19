import csv
rows=list(csv.DictReader(open('../taxonomy/taxonomy.csv')))

sub_map={}; pri_map={}; plaid_map={}; meta={}
for r in rows:
    meta[r['detailed_category']]=(r['general_category'],r['necessity'],r['cash_flow_type'],
        r['is_debt_related'],r['is_priority_debt'],r['is_age_restricted'],r['risk_flag'])
    for s in [x.strip() for x in r['equifax_source'].split(';') if x.strip()]:
        if '+' in s or '|' in s: continue          # compound rules handled separately
        if s.startswith('primary:'):
            v=s[8:].strip()
            if v not in ('(null)',): pri_map[v]=r['detailed_category']
        else:
            sub_map[s]=r['detailed_category']
    for p in [x.strip() for x in r['plaid_source'].split(';') if x.strip()]:
        plaid_map[p]=r['detailed_category']

def esc(s): return s.replace("'","\\'")
def vals(d): return ",\n".join(f"    ('{esc(k)}','{v}')" for k,v in sorted(d.items()))
def metavals():
    return ",\n".join(
      f"    ('{k}','{v[0]}','{v[1]}','{v[2]}',{v[3]},{v[4]},{v[5]},'{v[6]}')"
      for k,v in sorted(meta.items()))

sql = f"""
-- ============ RAYLO UNIFIED TAXONOMY - crosswalk application (sample test) ============
WITH sub_xw AS (SELECT * FROM UNNEST([STRUCT<eqx_sub STRING, leaf STRING>
{vals(sub_map)}
])),
pri_xw AS (SELECT * FROM UNNEST([STRUCT<eqx_pri STRING, leaf STRING>
{vals(pri_map)}
])),
plaid_xw AS (SELECT * FROM UNNEST([STRUCT<plaid_cat STRING, leaf STRING>
{vals(plaid_map)}
])),
leaf_meta AS (SELECT * FROM UNNEST([STRUCT<leaf STRING, general_category STRING, necessity STRING,
  cash_flow_type STRING, is_debt_related BOOL, is_priority_debt BOOL, is_age_restricted BOOL, risk_flag STRING>
{metavals()}
])),

-- ---------- EQUIFAX ----------
eqx_raw AS (
  SELECT
    PrimaryCategoryDescription AS pri,
    SubCategoryDescription AS sub,
    IF(TransactionTypeId=1,'credit','debit') AS direction,
    Amount
  FROM `raylo-production.equifax_data.open_banking_full_dump`
  TABLESAMPLE SYSTEM (2 PERCENT)
),
eqx_resolved AS (
  SELECT r.*,
    CASE
      -- T1: direction-dependent overrides
      WHEN r.pri LIKE 'Gambling and Betting%' AND r.direction='credit' THEN 'gambling_winnings'
      WHEN r.sub='Council' AND r.direction='credit' THEN 'salary'
      -- T2: compound rule - gig income
      WHEN r.pri='Identified Salary' AND r.sub IN ('Taxis','Delivery','Take Away') THEN 'salary_gig'
      WHEN r.pri='Identified Salary' AND r.sub IN ('Recruitment Services','Employment Agencies') THEN 'income_agency_work'
      -- T3: MECHANISM-OVERRIDE primaries (mechanism determines leaf regardless of merchant)
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
      -- T4: sub (WHAT) match
      WHEN s.leaf IS NOT NULL THEN s.leaf
      -- T5: primary fallback
      WHEN p.leaf IS NOT NULL THEN p.leaf
      ELSE 'unclassified_other'
    END AS leaf,
    CASE
      WHEN r.pri LIKE 'Gambling and Betting%' AND r.direction='credit' THEN 'T1_direction'
      WHEN r.sub='Council' AND r.direction='credit' THEN 'T1_direction'
      WHEN r.pri='Identified Salary' AND r.sub IN ('Taxis','Delivery','Take Away') THEN 'T2_compound'
      WHEN r.pri='Identified Salary' AND r.sub IN ('Recruitment Services','Employment Agencies') THEN 'T2_compound'
      WHEN r.pri IN ('Identified Salary','Refund','Benefits','Welfare','Pension Payout','Tax Refund',
        'Cash Back','Cash Machine','Cash Deposit','Interest','Interests and Dividends',
        'Balance Transfers','Adjustments') THEN 'T3_mechanism_override'
      WHEN s.leaf IS NOT NULL THEN 'T4_sub_match'
      WHEN p.leaf IS NOT NULL THEN 'T5_primary_fallback'
      ELSE 'T6_unresolved'
    END AS resolution_tier
  FROM eqx_raw r
  LEFT JOIN sub_xw s ON r.sub = s.eqx_sub
  LEFT JOIN pri_xw p ON r.pri = p.eqx_pri
),

-- ---------- PLAID ----------
plaid_raw AS (
  SELECT credit_category_detailed AS cat,
         IF(amount < 0,'credit','debit') AS direction, amount AS Amount
  FROM `raylo-production.dbt_production.credit_plaid_open_banking_transactions`
  TABLESAMPLE SYSTEM (20 PERCENT)
),
plaid_resolved AS (
  SELECT r.*,
    CASE
      WHEN r.cat='ENTERTAINMENT_CASINOS_AND_GAMBLING' AND r.direction='credit' THEN 'gambling_winnings'
      WHEN x.leaf IS NOT NULL THEN x.leaf
      ELSE 'unclassified_other'
    END AS leaf,
    CASE
      WHEN r.cat='ENTERTAINMENT_CASINOS_AND_GAMBLING' AND r.direction='credit' THEN 'T1_direction'
      WHEN x.leaf IS NOT NULL THEN 'T4_provider_crosswalk'
      ELSE 'T6_unresolved'
    END AS resolution_tier
  FROM plaid_raw r LEFT JOIN plaid_xw x ON r.cat = x.plaid_cat
),

combined AS (
  SELECT 'equifax' AS provider, leaf, resolution_tier FROM eqx_resolved
  UNION ALL
  SELECT 'plaid', leaf, resolution_tier FROM plaid_resolved
)
SELECT
  c.provider, c.resolution_tier,
  COUNT(*) AS n,
  ROUND(100*COUNT(*)/SUM(COUNT(*)) OVER (PARTITION BY c.provider),2) AS pct_of_provider,
  COUNT(DISTINCT c.leaf) AS distinct_leaves,
  COUNTIF(m.leaf IS NULL) AS leaves_missing_metadata
FROM combined c
LEFT JOIN leaf_meta m ON c.leaf = m.leaf
GROUP BY 1,2 ORDER BY 1, n DESC
"""
open('apply.sql','w').write(sql)
print("SQL generated:", len(sql), "chars")
print("mapping rows: sub",len(sub_map),"| primary",len(pri_map),"| plaid",len(plaid_map),"| meta",len(meta))

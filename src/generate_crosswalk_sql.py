import csv
import pathlib
_ROOT = pathlib.Path(__file__).resolve().parents[1]
rows = list(csv.DictReader(open(_ROOT / "taxonomy" / "taxonomy.csv")))

sub_map = {}; pri_map = {}; plaid_map = {}; meta = {}
for r in rows:
    meta[r['detailed_category']] = (r['general_category'], r['necessity'], r['cash_flow_type'],
        r['is_debt_related'], r['is_priority_debt'], r['is_age_restricted'], r['risk_flag'])
    for s in [x.strip() for x in r['equifax_source'].split(';') if x.strip()]:
        if '+' in s or '|' in s: continue          # compound rules handled separately
        if s.startswith('primary:'):
            v = s[8:].strip()
            if v not in ('(null)',): pri_map[v] = r['detailed_category']
        else:
            sub_map[s] = r['detailed_category']
    for p in [x.strip() for x in r['plaid_source'].split(';') if x.strip()]:
        plaid_map[p] = r['detailed_category']

dict_map = {r['normalised_merchant']: r['detailed_category']
            for r in csv.DictReader(open(_ROOT / "taxonomy" / "merchant_dictionary.csv"))}

_rules_raw = list(csv.DictReader(open(_ROOT / "taxonomy" / "rules" / "deterministic_rules.csv")))
rules = sorted((r for r in _rules_raw if r['enabled'].strip().lower() == 'true'),
               key=lambda r: (int(r['priority']), r['rule_id']))

def esc(s): return s.replace("\\", "\\\\").replace("'", "\\'")
def vals(d): return ",\n".join(f"    ('{esc(k)}','{v}')" for k, v in sorted(d.items()))
def metavals():
    return ",\n".join(
      f"    ('{k}','{v[0]}','{v[1]}','{v[2]}',{v[3]},{v[4]},{v[5]},'{v[6]}')"
      for k, v in sorted(meta.items()))

# T5 rules are provider-independent (defined once against a `merchant_name` / `description`
# field), applied identically to both providers via their respective raw-text columns.
def _rule_condition(rule, merchant_expr, desc_expr):
    field_expr = merchant_expr if rule['field'] == 'merchant_name' else desc_expr
    pat = esc(rule['pattern'])
    if rule['pattern_type'] == 'regex':
        pattern_sql = f"'{pat}'"
    else:  # exact_set -- plain string(s), auto-wrapped as a word-boundary alternation
        pattern_sql = f"CONCAT(r'\\b(', '{pat}', r')\\b')"
    cond = f"REGEXP_CONTAINS({field_expr}, {pattern_sql})"
    exclude = rule.get('exclude_pattern', '').strip()
    if exclude:
        cond = f"({cond} AND NOT REGEXP_CONTAINS({field_expr}, '{esc(exclude)}'))"
    if rule['direction'] != 'any':
        cond = f"({cond} AND r.direction = '{rule['direction']}')"
    return cond

def rules_leaf_case(merchant_expr, desc_expr):
    return "\n".join(
        f"      WHEN {_rule_condition(r, merchant_expr, desc_expr)} THEN '{r['detailed_category']}'"
        for r in rules)

def rules_tier_case(merchant_expr, desc_expr):
    return "\n".join(
        f"      WHEN {_rule_condition(r, merchant_expr, desc_expr)} THEN 'T5_rule_{r['rule_id']}'"
        for r in rules)

EQX_MERCHANT_EXPR = "LOWER(TRIM(r.vendor))"
EQX_DESC_EXPR = "LOWER(COALESCE(r.description_raw, ''))"
PLAID_MERCHANT_EXPR = "LOWER(TRIM(r.merchant_raw))"
PLAID_DESC_EXPR = "LOWER(COALESCE(r.description_raw, ''))"

sql = f"""
-- ============ RAYLO UNIFIED TAXONOMY - crosswalk application (sample test) ============
-- Precedence waterfall (CLAUDE.md section 4): T1 direction overrides -> T2 compound rules ->
-- T3 mechanism-override primaries -> T4 merchant dictionary -> T5 deterministic rules ->
-- T6 provider crosswalk (fallback) -> T7 unclassified.
WITH sub_xw AS (SELECT * FROM UNNEST([STRUCT<eqx_sub STRING, leaf STRING>
{vals(sub_map)}
])),
pri_xw AS (SELECT * FROM UNNEST([STRUCT<eqx_pri STRING, leaf STRING>
{vals(pri_map)}
])),
plaid_xw AS (SELECT * FROM UNNEST([STRUCT<plaid_cat STRING, leaf STRING>
{vals(plaid_map)}
])),
dict_xw AS (SELECT * FROM UNNEST([STRUCT<merchant STRING, leaf STRING>
{vals(dict_map)}
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
    VendorDescription AS vendor,
    Description AS description_raw,
    IF(TransactionTypeId=1,'credit','debit') AS direction,
    Amount
  FROM `raylo-production.equifax_data.open_banking_full_dump`
  TABLESAMPLE SYSTEM (2 PERCENT)
),
eqx_resolved AS (
  SELECT r.*,
    CASE
      -- T1: direction-dependent overrides
      WHEN r.pri LIKE 'Gambling and Betting%' AND r.direction='credit' THEN 'gambling_unspecified'
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
      -- T4: merchant dictionary (provider-independent, overrides both providers' own categories)
      WHEN d.leaf IS NOT NULL THEN d.leaf
      -- T5: deterministic rules
{rules_leaf_case(EQX_MERCHANT_EXPR, EQX_DESC_EXPR)}
      -- T6: provider crosswalk fallback (sub = WHAT, primary = mechanism fallback)
      WHEN s.leaf IS NOT NULL THEN s.leaf
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
      WHEN d.leaf IS NOT NULL THEN 'T4_merchant_dictionary'
{rules_tier_case(EQX_MERCHANT_EXPR, EQX_DESC_EXPR)}
      WHEN s.leaf IS NOT NULL THEN 'T6_provider_crosswalk'
      WHEN p.leaf IS NOT NULL THEN 'T6_provider_crosswalk'
      ELSE 'T7_unclassified'
    END AS resolution_tier
  FROM eqx_raw r
  LEFT JOIN sub_xw s ON r.sub = s.eqx_sub
  LEFT JOIN pri_xw p ON r.pri = p.eqx_pri
  LEFT JOIN dict_xw d ON LOWER(TRIM(r.vendor)) = d.merchant
),

-- ---------- PLAID ----------
plaid_raw AS (
  SELECT credit_category_detailed AS cat,
         merchant_name AS merchant_raw,
         COALESCE(original_description, transaction_name) AS description_raw,
         IF(amount < 0,'credit','debit') AS direction, amount AS Amount
  FROM `raylo-production.dbt_production.credit_plaid_open_banking_transactions`
  TABLESAMPLE SYSTEM (20 PERCENT)
),
plaid_resolved AS (
  SELECT r.*,
    CASE
      -- T1: direction-dependent overrides
      WHEN r.cat='ENTERTAINMENT_CASINOS_AND_GAMBLING' AND r.direction='credit' THEN 'gambling_unspecified'
      -- T4: merchant dictionary (provider-independent, overrides both providers' own categories)
      WHEN d.leaf IS NOT NULL THEN d.leaf
      -- T5: deterministic rules
{rules_leaf_case(PLAID_MERCHANT_EXPR, PLAID_DESC_EXPR)}
      -- T6: provider crosswalk fallback
      WHEN x.leaf IS NOT NULL THEN x.leaf
      ELSE 'unclassified_other'
    END AS leaf,
    CASE
      WHEN r.cat='ENTERTAINMENT_CASINOS_AND_GAMBLING' AND r.direction='credit' THEN 'T1_direction'
      WHEN d.leaf IS NOT NULL THEN 'T4_merchant_dictionary'
{rules_tier_case(PLAID_MERCHANT_EXPR, PLAID_DESC_EXPR)}
      WHEN x.leaf IS NOT NULL THEN 'T6_provider_crosswalk'
      ELSE 'T7_unclassified'
    END AS resolution_tier
  FROM plaid_raw r
  LEFT JOIN plaid_xw x ON r.cat = x.plaid_cat
  LEFT JOIN dict_xw d ON LOWER(TRIM(r.merchant_raw)) = d.merchant
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
(_ROOT / "sql" / "apply_crosswalk.sql").write_text(sql)
print("SQL generated:", len(sql), "chars")
print("mapping rows: sub", len(sub_map), "| primary", len(pri_map), "| plaid", len(plaid_map),
      "| dictionary", len(dict_map), "| rules (enabled)", len(rules), "| meta", len(meta))

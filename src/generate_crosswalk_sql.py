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

# T2 provider-entity collisions: Plaid (and occasionally Equifax) collapses two
# legal entities onto the same merchant string, so T4's exact-key match cannot
# disambiguate. Narrative check MUST fire before T4. Owned here -- not as a
# hand-patch on apply_crosswalk.sql -- because regenerating this file dropped
# the 2026-08-23 Tesco Bank fix (and the 2026-08-24 petrol / phone-insurance
# extensions) on 2026-08-24.
# (pattern, leaf, resolution_tier)
T2_TESCO_COLLISIONS = [
    (r"\btesco bank\b", "financial_institution_unspecified", "T2_compound_tesco_bank"),
    (r"tescophoneins", "insurance_other", "T2_compound_tesco_phoneins"),
    (r"caf[eé]", "restaurant_cafe", "T2_compound_tesco_cafe"),
    (r"petrol|\bpfs\b|\bfuel\b", "fuel", "T2_compound_tesco_petrol"),
]

# HMRC is the same shape: T4's `hmrc` / `hm revenue and customs` -> tax_payment
# is the right debit default (Self Assessment, Shipley, Cumbernauld) but Plaid
# also dumps Child Benefit, tax credits, and SA refunds onto those strings.
# Credits only -- an HMRC SA *debit* must still reach T4 as tax_payment.
# (pattern, leaf, resolution_tier)
T2_HMRC_MERCHANTS = ("hmrc", "hm revenue and customs")
T2_HMRC_COLLISIONS = [
    (r"child\s+benefits?", "benefits_state", "T2_compound_hmrc_child_benefit"),
    (r"work(?:ing)?\s+and\s+child\s+(?:tax\s+)?credits?|work(?:ing)?\s+and\s+child\s+tc\b|"
     r"child\s+tax\s+credits?|working\s+tax\s+credits?",
     "benefits_state", "T2_compound_hmrc_tax_credit"),
    (r"\bhmrc\s+sa\b|\bgov\.uk\s+sa\b|\bself[\s-]*assess",
     "tax_refund", "T2_compound_hmrc_sa_refund"),
]


def t2_tesco_leaf(merchant_expr, desc_expr):
    return "\n".join(
        f"      WHEN {merchant_expr}='tesco' AND REGEXP_CONTAINS({desc_expr}, r'{pat}') THEN '{leaf}'"
        for pat, leaf, _tier in T2_TESCO_COLLISIONS)


def t2_tesco_tier(merchant_expr, desc_expr):
    return "\n".join(
        f"      WHEN {merchant_expr}='tesco' AND REGEXP_CONTAINS({desc_expr}, r'{pat}') THEN '{tier}'"
        for pat, _leaf, tier in T2_TESCO_COLLISIONS)


def _hmrc_merchant_pred(merchant_expr):
    inner = ", ".join(f"'{m}'" for m in T2_HMRC_MERCHANTS)
    return f"{merchant_expr} IN ({inner})"


def t2_hmrc_leaf(merchant_expr, desc_expr):
    pred = _hmrc_merchant_pred(merchant_expr)
    return "\n".join(
        f"      WHEN {pred} AND r.direction='credit' AND REGEXP_CONTAINS({desc_expr}, r'{pat}') THEN '{leaf}'"
        for pat, leaf, _tier in T2_HMRC_COLLISIONS)


def t2_hmrc_tier(merchant_expr, desc_expr):
    pred = _hmrc_merchant_pred(merchant_expr)
    return "\n".join(
        f"      WHEN {pred} AND r.direction='credit' AND REGEXP_CONTAINS({desc_expr}, r'{pat}') THEN '{tier}'"
        for pat, _leaf, tier in T2_HMRC_COLLISIONS)


GAMBLING_SUBTYPE_LEAVES = (
    "gambling_betting", "gambling_casino", "gambling_bingo", "gambling_lottery",
)

T2_ATM_MERCHANTS = (
    "tesco", "one stop", "post office", "u.s. post office", "asda", "sainsbury's", "co-op",
)
T2_ATM_DEBIT_PAT = r"\batm\b|\blnk\b|cash\s+at\b|cash\s+withdrawal"
T2_ATM_CREDIT_PAT = r"\batm\b|cash\s+deposit"

T2_GROCER_PETROL_MERCHANTS = ("co-op", "sainsbury's", "asda")
T2_GROCER_PETROL_PAT = r"petrol|\bpfs\b|\bfuel\b"

T2_KFC_PAT = r"\bkfc\b"


def _in_merchants(merchant_expr, merchants):
    inner = ", ".join(f"'{esc(m)}'" for m in merchants)
    return f"{merchant_expr} IN ({inner})"


def t2_atm_leaf(merchant_expr, desc_expr):
    pred = _in_merchants(merchant_expr, T2_ATM_MERCHANTS)
    return "\n".join((
        f"      WHEN {pred} AND r.direction='debit' AND REGEXP_CONTAINS({desc_expr}, r'{T2_ATM_DEBIT_PAT}') THEN 'cash_withdrawal'",
        f"      WHEN {pred} AND r.direction='credit' AND REGEXP_CONTAINS({desc_expr}, r'{T2_ATM_CREDIT_PAT}') THEN 'cash_deposit'",
    ))


def t2_atm_tier(merchant_expr, desc_expr):
    pred = _in_merchants(merchant_expr, T2_ATM_MERCHANTS)
    return "\n".join((
        f"      WHEN {pred} AND r.direction='debit' AND REGEXP_CONTAINS({desc_expr}, r'{T2_ATM_DEBIT_PAT}') THEN 'T2_compound_instore_atm'",
        f"      WHEN {pred} AND r.direction='credit' AND REGEXP_CONTAINS({desc_expr}, r'{T2_ATM_CREDIT_PAT}') THEN 'T2_compound_instore_atm_deposit'",
    ))


def t2_grocer_petrol_leaf(merchant_expr, desc_expr):
    pred = _in_merchants(merchant_expr, T2_GROCER_PETROL_MERCHANTS)
    return (f"      WHEN {pred} AND REGEXP_CONTAINS({desc_expr}, r'{T2_GROCER_PETROL_PAT}') "
            f"THEN 'fuel'")


def t2_grocer_petrol_tier(merchant_expr, desc_expr):
    pred = _in_merchants(merchant_expr, T2_GROCER_PETROL_MERCHANTS)
    return (f"      WHEN {pred} AND REGEXP_CONTAINS({desc_expr}, r'{T2_GROCER_PETROL_PAT}') "
            f"THEN 'T2_compound_grocer_petrol'")


def t2_kfc_leaf(merchant_expr, desc_expr):
    hit = (f"(REGEXP_CONTAINS({merchant_expr}, r'{T2_KFC_PAT}') OR "
           f"REGEXP_CONTAINS({desc_expr}, r'{T2_KFC_PAT}'))")
    return f"      WHEN r.direction='debit' AND {hit} THEN 'takeaway'"


def t2_kfc_tier(merchant_expr, desc_expr):
    hit = (f"(REGEXP_CONTAINS({merchant_expr}, r'{T2_KFC_PAT}') OR "
           f"REGEXP_CONTAINS({desc_expr}, r'{T2_KFC_PAT}'))")
    return f"      WHEN r.direction='debit' AND {hit} THEN 'T2_compound_kfc'"


def t2_misc_leaf(merchant_expr, desc_expr):
    return "\n".join((
        f"      WHEN {merchant_expr}='tiktok' AND r.direction='debit' AND REGEXP_CONTAINS({desc_expr}, r'tiktok\\s*shop|\\bshop\\s*seller') THEN 'marketplace_general'",
        f"      WHEN {merchant_expr}='tiktok' AND r.direction='credit' AND REGEXP_CONTAINS({desc_expr}, r'shop\\s*seller') THEN 'income_other_unspecified'",
        f"      WHEN {merchant_expr}='sky' AND REGEXP_CONTAINS({desc_expr}, r'sky\\s*protect|\\bdgi\\b.*protect|protect.*\\bdgi\\b') THEN 'insurance_other'",
        f"      WHEN {merchant_expr}='child benefits' AND r.direction='credit' AND REGEXP_CONTAINS({desc_expr}, r'dwp\\s*cms|dwpcms|cmsgb2012|child\\s+maintenance') THEN 'income_other_unspecified'",
        f"      WHEN {merchant_expr}='asda' AND REGEXP_CONTAINS({desc_expr}, r'asda\\s*mobile') THEN 'mobile_phone_contract'",
        f"      WHEN {merchant_expr}='asda' AND REGEXP_CONTAINS({desc_expr}, r'asda\\s*living') THEN 'home_accessories'",
        f"      WHEN {merchant_expr}='vodafone' AND r.direction='debit' AND REGEXP_CONTAINS({desc_expr}, r'device') THEN 'mobile_handset'",
        f"      WHEN {merchant_expr}='amazon' AND r.direction='debit' AND REGEXP_CONTAINS({desc_expr}, r'prime\\s*video') THEN 'streaming'",
        f"      WHEN {merchant_expr}='bolt' AND REGEXP_CONTAINS({desc_expr}, r'stackblitz') THEN 'software'",
    ))


def t2_misc_tier(merchant_expr, desc_expr):
    return "\n".join((
        f"      WHEN {merchant_expr}='tiktok' AND r.direction='debit' AND REGEXP_CONTAINS({desc_expr}, r'tiktok\\s*shop|\\bshop\\s*seller') THEN 'T2_compound_tiktok_shop'",
        f"      WHEN {merchant_expr}='tiktok' AND r.direction='credit' AND REGEXP_CONTAINS({desc_expr}, r'shop\\s*seller') THEN 'T2_compound_tiktok_shop_seller'",
        f"      WHEN {merchant_expr}='sky' AND REGEXP_CONTAINS({desc_expr}, r'sky\\s*protect|\\bdgi\\b.*protect|protect.*\\bdgi\\b') THEN 'T2_compound_sky_protect'",
        f"      WHEN {merchant_expr}='child benefits' AND r.direction='credit' AND REGEXP_CONTAINS({desc_expr}, r'dwp\\s*cms|dwpcms|cmsgb2012|child\\s+maintenance') THEN 'T2_compound_cms_not_child_benefit'",
        f"      WHEN {merchant_expr}='asda' AND REGEXP_CONTAINS({desc_expr}, r'asda\\s*mobile') THEN 'T2_compound_asda_mobile'",
        f"      WHEN {merchant_expr}='asda' AND REGEXP_CONTAINS({desc_expr}, r'asda\\s*living') THEN 'T2_compound_asda_living'",
        f"      WHEN {merchant_expr}='vodafone' AND r.direction='debit' AND REGEXP_CONTAINS({desc_expr}, r'device') THEN 'T2_compound_vodafone_device'",
        f"      WHEN {merchant_expr}='amazon' AND r.direction='debit' AND REGEXP_CONTAINS({desc_expr}, r'prime\\s*video') THEN 'T2_compound_amazon_prime_video'",
        f"      WHEN {merchant_expr}='bolt' AND REGEXP_CONTAINS({desc_expr}, r'stackblitz') THEN 'T2_compound_bolt_stackblitz'",
    ))


def t1_gambling_credit_leaf():
    inner = ", ".join(f"'{x}'" for x in GAMBLING_SUBTYPE_LEAVES)
    return f"      WHEN r.direction='credit' AND d.leaf IN ({inner}) THEN 'gambling_unspecified'"


def t1_gambling_credit_tier():
    inner = ", ".join(f"'{x}'" for x in GAMBLING_SUBTYPE_LEAVES)
    return f"      WHEN r.direction='credit' AND d.leaf IN ({inner}) THEN 'T1_direction_gambling_credit'"


def t2_refund_leaf(desc_expr):
    # After T1 gambling so bookmaker credits stay gambling_unspecified even
    # when the narrative says REFUND. Before T4 so Iceland/Amazon/Tesco
    # credits with \brefund\b are not labelled as spend.
    inner = ", ".join(f"'{x}'" for x in GAMBLING_SUBTYPE_LEAVES)
    return (f"      WHEN r.direction='credit' AND REGEXP_CONTAINS({desc_expr}, r'\\brefund\\b') "
            f"AND (d.leaf IS NULL OR d.leaf NOT IN ({inner})) THEN 'refund_received'")


def t2_refund_tier(desc_expr):
    inner = ", ".join(f"'{x}'" for x in GAMBLING_SUBTYPE_LEAVES)
    return (f"      WHEN r.direction='credit' AND REGEXP_CONTAINS({desc_expr}, r'\\brefund\\b') "
            f"AND (d.leaf IS NULL OR d.leaf NOT IN ({inner})) THEN 'T2_compound_refund'")


def t2_entity_collision_leaf(merchant_expr, desc_expr):
    # Order is load-bearing: Tesco Bank / PhoneIns before ATM before petrol;
    # KFC narrative before T4 so Klarna*KFC / Burton+KFC are takeaway.
    tesco_bank_phone = "\n".join(
        f"      WHEN {merchant_expr}='tesco' AND REGEXP_CONTAINS({desc_expr}, r'{pat}') THEN '{leaf}'"
        for pat, leaf, _tier in T2_TESCO_COLLISIONS if "petrol" not in pat and "fuel" not in pat)
    tesco_petrol = "\n".join(
        f"      WHEN {merchant_expr}='tesco' AND REGEXP_CONTAINS({desc_expr}, r'{pat}') THEN '{leaf}'"
        for pat, leaf, _tier in T2_TESCO_COLLISIONS if "petrol" in pat or "fuel" in pat)
    return "\n".join((
        tesco_bank_phone,
        t2_atm_leaf(merchant_expr, desc_expr),
        tesco_petrol,
        t2_grocer_petrol_leaf(merchant_expr, desc_expr),
        t2_hmrc_leaf(merchant_expr, desc_expr),
        t2_kfc_leaf(merchant_expr, desc_expr),
        t2_misc_leaf(merchant_expr, desc_expr),
    ))


def t2_entity_collision_tier(merchant_expr, desc_expr):
    tesco_bank_phone = "\n".join(
        f"      WHEN {merchant_expr}='tesco' AND REGEXP_CONTAINS({desc_expr}, r'{pat}') THEN '{tier}'"
        for pat, _leaf, tier in T2_TESCO_COLLISIONS if "petrol" not in pat and "fuel" not in pat)
    tesco_petrol = "\n".join(
        f"      WHEN {merchant_expr}='tesco' AND REGEXP_CONTAINS({desc_expr}, r'{pat}') THEN '{tier}'"
        for pat, _leaf, tier in T2_TESCO_COLLISIONS if "petrol" in pat or "fuel" in pat)
    return "\n".join((
        tesco_bank_phone,
        t2_atm_tier(merchant_expr, desc_expr),
        tesco_petrol,
        t2_grocer_petrol_tier(merchant_expr, desc_expr),
        t2_hmrc_tier(merchant_expr, desc_expr),
        t2_kfc_tier(merchant_expr, desc_expr),
        t2_misc_tier(merchant_expr, desc_expr),
    ))


def match_t2(merchant, direction, description):
    """Python mirror of t2_entity_collision_leaf. Used by the eval harness."""
    import re
    m = (merchant or "").strip().lower()
    desc = description or ""
    direction = (direction or "").strip().lower()

    if m == "tesco":
        for pat, leaf, tier in T2_TESCO_COLLISIONS:
            if "petrol" in pat:
                continue
            if re.search(pat, desc, flags=re.IGNORECASE):
                return leaf, tier
    if m in T2_ATM_MERCHANTS:
        if direction == "debit" and re.search(T2_ATM_DEBIT_PAT, desc, flags=re.IGNORECASE):
            return "cash_withdrawal", "T2_compound_instore_atm"
        if direction == "credit" and re.search(T2_ATM_CREDIT_PAT, desc, flags=re.IGNORECASE):
            return "cash_deposit", "T2_compound_instore_atm_deposit"
    if m == "tesco":
        for pat, leaf, tier in T2_TESCO_COLLISIONS:
            if "petrol" in pat and re.search(pat, desc, flags=re.IGNORECASE):
                return leaf, tier
    if m in T2_GROCER_PETROL_MERCHANTS and re.search(T2_GROCER_PETROL_PAT, desc, flags=re.IGNORECASE):
        return "fuel", "T2_compound_grocer_petrol"
    if m in T2_HMRC_MERCHANTS and direction == "credit":
        for pat, leaf, tier in T2_HMRC_COLLISIONS:
            if re.search(pat, desc, flags=re.IGNORECASE):
                return leaf, tier
    if direction == "debit" and (
            re.search(T2_KFC_PAT, m, flags=re.IGNORECASE)
            or re.search(T2_KFC_PAT, desc, flags=re.IGNORECASE)):
        return "takeaway", "T2_compound_kfc"
    if m == "tiktok":
        if direction == "debit" and re.search(r"tiktok\s*shop|\bshop\s*seller", desc, flags=re.IGNORECASE):
            return "marketplace_general", "T2_compound_tiktok_shop"
        if direction == "credit" and re.search(r"shop\s*seller", desc, flags=re.IGNORECASE):
            return "income_other_unspecified", "T2_compound_tiktok_shop_seller"
    if m == "sky" and re.search(r"sky\s*protect|\bdgi\b.*protect|protect.*\bdgi\b", desc, flags=re.IGNORECASE):
        return "insurance_other", "T2_compound_sky_protect"
    if m == "child benefits" and direction == "credit" and re.search(
            r"dwp\s*cms|dwpcms|cmsgb2012|child\s+maintenance", desc, flags=re.IGNORECASE):
        return "income_other_unspecified", "T2_compound_cms_not_child_benefit"
    if m == "asda" and re.search(r"asda\s*mobile", desc, flags=re.IGNORECASE):
        return "mobile_phone_contract", "T2_compound_asda_mobile"
    if m == "asda" and re.search(r"asda\s*living", desc, flags=re.IGNORECASE):
        return "home_accessories", "T2_compound_asda_living"
    if m == "vodafone" and direction == "debit" and re.search(r"device", desc, flags=re.IGNORECASE):
        return "mobile_handset", "T2_compound_vodafone_device"
    if m == "amazon" and direction == "debit" and re.search(r"prime\s*video", desc, flags=re.IGNORECASE):
        return "streaming", "T2_compound_amazon_prime_video"
    if m == "bolt" and re.search(r"stackblitz", desc, flags=re.IGNORECASE):
        return "software", "T2_compound_bolt_stackblitz"
    return None

def generate():
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
      -- T2: provider-entity collisions (Tesco Bank/Petrol/PhoneIns; HMRC
      -- Child Benefit / tax credits / SA refunds). Must precede T4.
{t2_entity_collision_leaf(EQX_MERCHANT_EXPR, EQX_DESC_EXPR)}
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
      -- T1 (dict-informed): bookmaker credits stay unspecified even when T4
      -- would assign a debit subtype. Plaid native T1 only sees Plaid's
      -- gambling category, so salary-mislabeled Sky Bet credits used to lose to T4.
{t1_gambling_credit_leaf()}
{t2_refund_leaf(EQX_DESC_EXPR)}
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
{t2_entity_collision_tier(EQX_MERCHANT_EXPR, EQX_DESC_EXPR)}
      WHEN r.pri IN ('Identified Salary','Refund','Benefits','Welfare','Pension Payout','Tax Refund',
        'Cash Back','Cash Machine','Cash Deposit','Interest','Interests and Dividends',
        'Balance Transfers','Adjustments') THEN 'T3_mechanism_override'
{t1_gambling_credit_tier()}
{t2_refund_tier(EQX_DESC_EXPR)}
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
      -- T2: provider-entity collisions -- see eqx_resolved
{t2_entity_collision_leaf(PLAID_MERCHANT_EXPR, PLAID_DESC_EXPR)}
{t1_gambling_credit_leaf()}
{t2_refund_leaf(PLAID_DESC_EXPR)}
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
{t2_entity_collision_tier(PLAID_MERCHANT_EXPR, PLAID_DESC_EXPR)}
{t1_gambling_credit_tier()}
{t2_refund_tier(PLAID_DESC_EXPR)}
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
    return sql


if __name__ == "__main__":
    generate()

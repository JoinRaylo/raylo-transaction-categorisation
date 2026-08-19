"""Measure cross-provider leaf disagreement.

Finding (2025-08): for the 2,307 merchants both providers cover, applying the two
crosswalks independently yields DIFFERENT leaves for 72.2% of merchants / 45.2% of
Plaid volume. 925 are genuine conflicts between two specific leaves. This is why the
merchant dictionary must OVERRIDE provider categories rather than supplement them.

Usage: run QUERY below in BigQuery, save the JSON result to
       outputs/shared_merchants.json, then run this script.
"""
import json, csv, pathlib, sys

QUERY = r"""
WITH eqx AS (
  SELECT LOWER(TRIM(VendorDescription)) AS merchant,
         PrimaryCategoryDescription AS pri, SubCategoryDescription AS sub, COUNT(*) AS n
  FROM `raylo-production.equifax_data.open_banking_full_dump`
  WHERE VendorDescription IS NOT NULL AND TRIM(VendorDescription)!='' AND TransactionTypeId = 2
  GROUP BY 1,2,3
),
eqx_modal AS (SELECT merchant, pri, sub, n AS eqx_n FROM eqx
  QUALIFY ROW_NUMBER() OVER (PARTITION BY merchant ORDER BY n DESC) = 1),
plaid AS (
  SELECT LOWER(TRIM(merchant_name)) AS merchant, credit_category_detailed AS cat, COUNT(*) AS n
  FROM `raylo-production.dbt_production.credit_plaid_open_banking_transactions`
  WHERE merchant_name IS NOT NULL AND TRIM(merchant_name)!='' AND amount > 0
  GROUP BY 1,2),
plaid_modal AS (SELECT merchant, cat, n AS plaid_n FROM plaid
  QUALIFY ROW_NUMBER() OVER (PARTITION BY merchant ORDER BY n DESC) = 1)
SELECT e.merchant, e.pri, e.sub, e.eqx_n, p.cat AS plaid_cat, p.plaid_n
FROM eqx_modal e JOIN plaid_modal p USING (merchant) ORDER BY p.plaid_n DESC
"""

RESULT = pathlib.Path(__file__).resolve().parents[1] / "outputs" / "shared_merchants.json"
if not RESULT.exists():
    sys.exit(f"Run QUERY in BigQuery and save the result JSON to {RESULT}")
d = json.loads(RESULT.read_text())

rows=[[f['v'] for f in r['f']] for r in d['rows']]
print("shared merchants (debit-only, modal):", len(rows))

# rebuild crosswalk from the seed
tax=list(csv.DictReader(open(str(pathlib.Path(__file__).resolve().parents[1] / "taxonomy" / "taxonomy.csv"))))
sub_map={}; pri_map={}; plaid_map={}; gen={}
for r in tax:
    gen[r['detailed_category']]=r['general_category']
    for s in [x.strip() for x in r['equifax_source'].split(';') if x.strip()]:
        if '+' in s or '|' in s: continue
        if s.startswith('primary:'):
            v=s[8:].strip()
            if v!='(null)': pri_map[v]=r['detailed_category']
        else: sub_map[s]=r['detailed_category']
    for p in [x.strip() for x in r['plaid_source'].split(';') if x.strip()]:
        plaid_map[p]=r['detailed_category']

MECH={'Identified Salary','Refund','Benefits','Welfare','Pension Payout','Tax Refund','Cash Back',
      'Cash Machine','Cash Deposit','Interest','Interests and Dividends','Balance Transfers','Adjustments'}
MECH_LEAF={'Identified Salary':'salary','Refund':'refund_received','Benefits':'benefits_state',
 'Welfare':'benefits_state','Pension Payout':'pension_received','Tax Refund':'tax_refund',
 'Cash Back':'cashback','Cash Machine':'cash_withdrawal','Cash Deposit':'cash_deposit',
 'Interest':'savings_interest_received','Interests and Dividends':'savings_interest_received',
 'Balance Transfers':'balance_transfer','Adjustments':'adjustment'}

def eqx_leaf(pri,sub):
    if pri in MECH: return MECH_LEAF[pri]
    if sub and sub in sub_map: return sub_map[sub]
    if pri and pri in pri_map: return pri_map[pri]
    return 'unclassified_other'

COARSE={'unclassified_transfer','unclassified_card_spend','unclassified_other','retail_other',
 'transport_other','entertainment_other','business_services','services_unspecified',
 'financial_services_other','gambling_unspecified','travel_other','general_merchandise_other',
 'eating_out_other','health_other','housing_other','pet_other','utility_other','loan_repayment_other',
 'income_other_unspecified','transfer_bank_unspecified','card_payment_unspecified','financial_institution_unspecified'}

agree=disagree=0; agree_v=disagree_v=0
examples=[]; coarse_only=0
for merchant,pri,sub,eqx_n,plaid_cat,plaid_n in rows:
    el=eqx_leaf(pri, sub if sub!=None else None)
    pl=plaid_map.get(plaid_cat,'unclassified_other')
    v=int(plaid_n)
    if el==pl:
        agree+=1; agree_v+=v
    else:
        disagree+=1; disagree_v+=v
        # is the disagreement only because one side is coarse?
        if el in COARSE or pl in COARSE: coarse_only+=1
        else: examples.append((v,merchant,f"{pri} | {sub}",el,plaid_cat,pl))

tot=agree+disagree
print(f"\nLEAF-LEVEL AGREEMENT across the two crosswalks:")
print(f"  agree:    {agree:>5} merchants ({100*agree/tot:.1f}%)")
print(f"  DISAGREE: {disagree:>5} merchants ({100*disagree/tot:.1f}%)")
print(f"\nWeighted by Plaid transaction volume:")
print(f"  agree:    {agree_v:>9,} ({100*agree_v/(agree_v+disagree_v):.1f}%)")
print(f"  DISAGREE: {disagree_v:>9,} ({100*disagree_v/(agree_v+disagree_v):.1f}%)")
print(f"\n  of disagreements, {coarse_only} ({100*coarse_only/disagree:.0f}%) involve a coarse/catch-all leaf on one side")
print(f"  {len(examples)} are GENUINE conflicts between two specific leaves\n")
print("--- top genuine conflicts by Plaid volume ---")
for v,m,eq,el,pc,pl in sorted(examples, reverse=True)[:20]:
    print(f"  {v:>6,}  {m[:26]:26} EQX[{eq[:38]:38}]->{el:24} PLAID[{pc[:34]:34}]->{pl}")

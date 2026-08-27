"""Second T6 residual fetch — keyword/entity nets, not Plaid natives.

Previewed in BQ 27 Aug before this pull. Rejects the first pack's failure
modes (INCOME_SALARY → p2p, OTHER_UTILITIES → waste, cashback, personal LOAN).

Does not label or append tuning_leaf_topup.csv.

Usage:
    python src/fetch_t6_residual_topup2.py
"""
from __future__ import annotations

import csv
import pathlib
import re
import sys
from collections import Counter

from dotenv import load_dotenv

load_dotenv()

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "outputs"
sys.path.insert(0, str(ROOT / "src"))

from generate_crosswalk_sql import BQ_DICT_TABLE  # noqa: E402
from final_evaluation import (  # noqa: E402
    load_crosswalk,
    load_dictionary,
    load_rules,
    our_leaf,
    plaid_native_leaf,
)
import final_evaluation as fe  # noqa: E402

SAMPLE_CSV = OUT_DIR / "t6_residual_topup2_sample.csv"
COUNTS_MD = ROOT / "data" / "t6_residual_topup2_fetch.md"
PLAID_TABLE = "`raylo-production.dbt_production.credit_plaid_open_banking_transactions`"

# (leaf, direction, include_re, exclude_re, fetch_n, keep_n)
NETS = [
    (
        "salary", "credit",
        r"\b(salary|payroll)\b",
        r"dwp|adyen|stripe|square|faire",
        200, 40,
    ),
    (
        "salary_gig", "credit",
        r"roofoods limited|stuart delivery",
        r"uber\s*eats|pending\.uber|refund",
        200, 40,
    ),
    (
        "refund_received", "credit",
        r"rebate|credit\s*note|goods\s+returned|overpayment",
        r"cash.?back",
        200, 40,
    ),
    (
        "loan_disbursement", "credit",
        r"moneyboat|lending\s*stream|salad money|creditspring\s+advan|natwest boxed loan|loan disbursement",
        r"savings\s+withdrawal|\bunp\b",
        200, 40,
    ),
    (
        "utility_other", "debit",
        r"homebox|leep\s+networks|glide student|heat network|district heat|communal (heat|energy)|metered heat",
        r"waste|refuse|recycl|ourtaap",
        80, 40,
    ),
    (
        "account_charge", "debit",
        r"tide fee|service charges?|total charges",
        r"unpaid|n-s trn|non-gbp|notemachine|cashback|reservation",
        150, 40,
    ),
]

ENTITY_CAP = {
    "roofoods": 12,
    "stuart delivery": 12,
    "moneyboat": 10,
    "lending stream": 10,
    "salad": 8,
    "creditspring": 8,
    "tide fee": 10,
    "service charges": 12,
}


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def _blob(r: dict) -> str:
    return f"{r.get('merchant') or ''} {r.get('description_raw') or ''}".lower()


def _entity(text: str) -> str:
    t = text.lower()
    for key in ENTITY_CAP:
        if key in t:
            return key
    return ""


def _sql_quote_regex(pat: str) -> str:
    # GoogleSQL r'...' already treats \b / \s as regex. Doubling backslashes
    # makes word-boundary patterns match nothing (measured on salary/payroll).
    return pat.replace("'", "\\'")


def _eat(path, merchants, fingerprints, merchant_key, desc_key="description_raw", merchants_out=True):
    if not path.exists():
        return
    for r in csv.DictReader(open(path)):
        m = _norm(r.get(merchant_key) or r.get("merchant") or "")
        d = _norm(r.get(desc_key) or r.get("description") or "")
        fingerprints.add((m, d))
        if merchants_out and m:
            merchants.add(m)


def load_exclusions():
    merchants, fingerprints = set(), set()
    data = ROOT / "data"
    # Merchant-level skip: eval sets + pack 1 (do not put holdout names in training).
    _eat(data / "gold_v2_slm_eval_holdout.csv", merchants, fingerprints, "merchant_raw")
    _eat(data / "gold_transactions_risk_categories.csv", merchants, fingerprints, "merchant_raw")
    _eat(data / "gold_transactions_v5_LOCKED.csv", merchants, fingerprints, "merchant_raw")
    _eat(data / "tuning_leaf_topup.csv", merchants, fingerprints, "merchant_raw")
    _eat(OUT_DIR / "gold_v6_locked_sample.csv", merchants, fingerprints, "merchant_raw")
    _eat(OUT_DIR / "gold_pipeline_eval.csv", merchants, fingerprints, "merchant")
    _eat(OUT_DIR / "t6_residual_topup_sample.csv", merchants, fingerprints, "merchant")
    _eat(OUT_DIR / "t6_residual_topup_sample_reviewed.csv", merchants, fingerprints, "merchant")
    # Fingerprint-only: already-labelled volume gold (avoid exact dupes, keep scarce entities).
    for path, key in (
        (data / "gold_transactions_v2.csv", "merchant_raw"),
        (data / "gold_transactions_v3_volume.csv", "merchant_raw"),
        (data / "gold_transactions_v4_slm_volume.csv", "merchant_raw"),
        (OUT_DIR / "gold_v2_sample.csv", "merchant_raw"),
    ):
        _eat(path, merchants, fingerprints, key, merchants_out=False)
    merchants.discard("")
    return merchants, fingerprints


def _init_waterfall():
    fe.SUB_MAP, fe.PRI_MAP, fe.PLAID_MAP, _ = load_crosswalk()
    fe.DICTIONARY = load_dictionary()
    fe.RULES = load_rules()


def accept_row(leaf: str, r: dict) -> str | None:
    """Return None to keep, or a drop reason."""
    text = _blob(r)
    amt = abs(float(r.get("amount") or 0))
    if leaf == "salary":
        if "salary finance" in text or "sf advance" in text:
            return "salary_finance_loan"
        if re.search(r"payroll\s+advance|salary\s+advance", text):
            return "salary_advance_product"
        if re.search(r"\bno salary\b", text):
            return "no_salary_memo"
        if "expenses" in text:
            return "salary_expenses"
        if amt < 50:
            return "tiny_salary_adjustment"
        if not re.search(r"\b(salary|payroll)\b", text):
            return "no_salary_token"
    if leaf == "salary_gig":
        if amt < 15:
            return "tiny_gig_credit"
        if not re.search(r"roofoods|stuart delivery", text):
            return "not_gig_platform"
    if leaf == "refund_received":
        if re.search(r"\btax\b.*rebate|rebate.*\btax\b", text):
            return "tax_rebate"
        if re.search(r"\bunp\b", text):
            return "unpaid_marker"
        if re.search(r"slack rebate|\bvrate\b|business savings", text):
            return "fx_savings_rebate"
        if "overpayment" in text and not re.search(r"credit\s*note|invoice", text):
            return "personal_overpayment"
        if re.search(r"payment from [a-z][a-z]+ [a-z]", text) and "overpayment" in text:
            return "personal_overpayment"
        if re.search(r"debt overpayment", text):
            return "personal_debt_memo"
    if leaf == "loan_disbursement":
        if "savings withdrawal" in text:
            return "wagestream_savings"
    if leaf == "utility_other":
        if "ourtaap" in text or "virgin pure" in text:
            return "water_filter_not_utility"
        if re.search(r"waste|refuse|recycl", text):
            return "waste"
    if leaf == "account_charge":
        if re.search(r"unpaid|n-s trn|non-gbp", text):
            return "not_isolated_fee"
    return None


def fetch_net(client, leaf, direction, include_re, exclude_re, fetch_n, exclude_merchants):
    from google.cloud import bigquery

    dir_sql = "t.amount < 0" if direction == "credit" else "t.amount > 0"
    sql = f"""
    SELECT merchant, merchant_raw, description_raw, amount, direction, native_category
    FROM (
      SELECT LOWER(TRIM(IFNULL(t.merchant_name, ''))) AS merchant,
             IFNULL(t.merchant_name, '') AS merchant_raw,
             IFNULL(COALESCE(t.original_description, t.transaction_name), '') AS description_raw,
             t.amount,
             IF(t.amount < 0, 'credit', 'debit') AS direction,
             t.credit_category_detailed AS native_category
      FROM {PLAID_TABLE} t
      LEFT JOIN (
        SELECT normalised_merchant
        FROM {BQ_DICT_TABLE}
        WHERE review_status = 'approved'
          AND NOT STARTS_WITH(detailed_category, 'unclassified')
      ) d
      ON LOWER(TRIM(IFNULL(t.merchant_name, ''))) = d.normalised_merchant
        AND TRIM(IFNULL(t.merchant_name, '')) != ''
      WHERE {dir_sql}
        AND d.normalised_merchant IS NULL
        AND LOWER(TRIM(IFNULL(t.merchant_name, ''))) NOT IN UNNEST(@excluded)
        AND REGEXP_CONTAINS(
          LOWER(CONCAT(IFNULL(t.merchant_name, ''), ' ',
            IFNULL(COALESCE(t.original_description, t.transaction_name), ''))),
          r'{_sql_quote_regex(include_re)}')
        AND NOT REGEXP_CONTAINS(
          LOWER(CONCAT(IFNULL(t.merchant_name, ''), ' ',
            IFNULL(COALESCE(t.original_description, t.transaction_name), ''))),
          r'{_sql_quote_regex(exclude_re)}')
      QUALIFY ROW_NUMBER() OVER (
        PARTITION BY IF(
          TRIM(IFNULL(t.merchant_name, '')) = '',
          LOWER(TRIM(IFNULL(COALESCE(t.original_description, t.transaction_name), ''))),
          LOWER(TRIM(t.merchant_name))
        )
        ORDER BY RAND()
      ) = 1
    )
    ORDER BY RAND()
    LIMIT {int(fetch_n)}
    """
    params = [bigquery.ArrayQueryParameter("excluded", "STRING", exclude_merchants or [""])]
    job_config = bigquery.QueryJobConfig(query_parameters=params)
    rows = [dict(r) for r in client.query(sql, job_config=job_config).result()]
    print(f"  [{leaf}] BQ {len(rows)} keyword T4-miss", file=sys.stderr)
    return rows


def keep_rows(leaf, keep_n, rows, fingerprints, seen_merchants, entity_counts):
    kept = []
    dropped = Counter()
    for r in rows:
        m = _norm(r.get("merchant") or "")
        d = _norm(r.get("description_raw") or "")
        if (m, d) in fingerprints:
            dropped["fingerprint"] += 1
            continue
        if m and m in seen_merchants:
            dropped["merchant_cap"] += 1
            continue
        reason = accept_row(leaf, r)
        if reason:
            dropped[reason] += 1
            continue
        ent = _entity(_blob(r))
        if ent and entity_counts[ent] >= ENTITY_CAP.get(ent, 99):
            dropped[f"entity_{ent}"] += 1
            continue
        direction = r.get("direction") or "debit"
        cat = r.get("native_category") or ""
        _leaf, tier = our_leaf(
            r.get("merchant") or "", direction, r.get("description_raw") or "",
            plaid_native_leaf, cat, direction,
        )
        if not str(tier).startswith("T6"):
            dropped[str(tier)] += 1
            continue
        kept.append({**r, "waterfall_tier": tier, "t6_native_leaf": _leaf})
        if m:
            seen_merchants.add(m)
        fingerprints.add((m, d))
        if ent:
            entity_counts[ent] += 1
        if len(kept) >= keep_n:
            break
    print(f"    kept {len(kept)}; dropped {dict(dropped)}", file=sys.stderr)
    return kept


def main():
    from google.cloud import bigquery

    _init_waterfall()
    exclude_m, fingerprints = load_exclusions()
    print(f"Exclusions: {len(exclude_m)} merchants, {len(fingerprints)} fingerprints",
          file=sys.stderr)
    client = bigquery.Client(project="raylo-production")
    all_rows = []
    seen_merchants = set(exclude_m)
    entity_counts = Counter()
    row_id = 0
    by_leaf = {}
    for leaf, direction, inc, exc, fetch_n, keep_n in NETS:
        raw = fetch_net(client, leaf, direction, inc, exc, fetch_n, sorted(exclude_m) or [""])
        kept = keep_rows(leaf, keep_n, raw, fingerprints, seen_merchants, entity_counts)
        by_leaf[leaf] = len(kept)
        for r in kept:
            all_rows.append({
                "row_id": row_id,
                "target_leaf": leaf,
                "provider": "plaid",
                "merchant": r.get("merchant") or "",
                "merchant_raw": r.get("merchant_raw") or "",
                "description_raw": r.get("description_raw") or "",
                "amount": r.get("amount"),
                "direction": r.get("direction") or "",
                "native_category": r.get("native_category") or "",
                "waterfall_tier": r.get("waterfall_tier") or "",
                "t6_native_leaf": r.get("t6_native_leaf") or "",
            })
            row_id += 1

    OUT_DIR.mkdir(exist_ok=True)
    fieldnames = [
        "row_id", "target_leaf", "provider", "merchant", "merchant_raw",
        "description_raw", "amount", "direction", "native_category",
        "waterfall_tier", "t6_native_leaf",
    ]
    with open(SAMPLE_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(all_rows)

    lines = [
        "# T6 residual top-up fetch 2 (2026-08-27)\n",
        "Keyword/entity nets only (no Plaid native). Previewed then filtered. "
        "Not labelled. Not appended to `tuning_leaf_topup.csv`.\n",
        f"Wrote `{SAMPLE_CSV.relative_to(ROOT)}` — **{len(all_rows)}** rows.\n",
        "| target_leaf | n | source |",
        "|---|---:|---|",
        "| salary | {0} | salary/payroll credits; drop Salary Finance advances |".format(by_leaf.get("salary", 0)),
        "| salary_gig | {0} | Roofoods Limited / Stuart Delivery credits ≥ £15 |".format(by_leaf.get("salary_gig", 0)),
        "| refund_received | {0} | rebate/credit note/overpayment; drop tax + personal FPS |".format(by_leaf.get("refund_received", 0)),
        "| loan_disbursement | {0} | Moneyboat / Lending Stream / Salad / Creditspring advance |".format(by_leaf.get("loan_disbursement", 0)),
        "| utility_other | {0} | Homebox / Leep / Glide / heat network; not Ourtaap/waste |".format(by_leaf.get("utility_other", 0)),
        "| account_charge | {0} | Tide fee / service charges / total charges |".format(by_leaf.get("account_charge", 0)),
    ]
    COUNTS_MD.write_text("\n".join(lines) + "\n")
    print(f"\nWrote {SAMPLE_CSV}: {len(all_rows)} rows", file=sys.stderr)


if __name__ == "__main__":
    main()

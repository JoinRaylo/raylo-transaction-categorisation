"""Fetch Plaid T6-bound examples for a short list of weak residual leaves.

Training top-up, not eval. Does **not** label, does **not** append
`tuning_leaf_topup.csv`, does **not** retrain.

Sourcing is the serving residual: miss T4 (BQ dictionary join) and miss
T1/T2/T5 in Python (`our_leaf`). Native Plaid category is a recall net,
not the gold leaf — labelling comes later.

Excludes holdout / risk gold / locked v5 / v6 sample / existing top-up
fingerprints. Does not exclude the 100k tranche merchants by name: those
are already T4 and drop out of the join.

Usage:
    python src/fetch_t6_residual_topup.py
"""
from __future__ import annotations

import csv
import pathlib
import sys
from collections import Counter

from dotenv import load_dotenv

load_dotenv()

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "outputs"
sys.path.insert(0, str(ROOT / "src"))

from generate_crosswalk_sql import BQ_DICT_TABLE, plaid_map  # noqa: E402
from final_evaluation import (  # noqa: E402
    load_crosswalk,
    load_dictionary,
    load_rules,
    our_leaf,
    plaid_native_leaf,
)
import final_evaluation as fe  # noqa: E402

SAMPLE_CSV = OUT_DIR / "t6_residual_topup_sample.csv"
COUNTS_MD = ROOT / "data" / "t6_residual_topup_fetch.md"

# Residual leaves where T6 still beats hinge, both fail, or the class is
# thin in jsonl. Skip high-volume jsonl dumps (days_out, transfer_p2p).
TARGET_LEAVES = [
    "salary",
    "benefits_state",
    "refund_received",
    "loan_disbursement",
    "utility_other",
    "investment_trading",
    "gambling_bingo",
    "account_charge",
]

# Oversample in BQ; Python T6 filter + merchant cap shrinks this.
FETCH_N = 250
KEEP_N = 60

# refund(ed) is T2 — do not use it here or the rows never stay T6-bound.
KEYWORD_FALLBACK = {
    "refund_received": r"rebate|credit note|goods returned|overpayment|cash.?back",
    "investment_trading": (
        r"\btrading\b|etoro|plus500|freetrade|trading.?212|ig markets|"
        r"degiro|interactive brokers|\bsaxo\b|hargreaves lansdown"
    ),
    "gambling_bingo": r"\bbingo\b",
    "salary": r"\bwages\b|\bsalary\b|\bpayroll\b",
}

PLAID_TABLE = "`raylo-production.dbt_production.credit_plaid_open_banking_transactions`"


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def _natives_for(leaf: str) -> list[str]:
    return sorted({cat for cat, mapped in plaid_map.items() if mapped == leaf})


def _eat(path, merchants, fingerprints, merchant_key, desc_key="description_raw"):
    if not path.exists():
        return
    for r in csv.DictReader(open(path)):
        m = _norm(r.get(merchant_key) or r.get("merchant") or "")
        d = _norm(r.get(desc_key) or r.get("description") or "")
        fingerprints.add((m, d))
        if m:
            merchants.add(m)


def load_exclusions():
    merchants, fingerprints = set(), set()
    data = ROOT / "data"
    _eat(data / "gold_v2_slm_eval_holdout.csv", merchants, fingerprints, "merchant_raw")
    _eat(data / "gold_transactions_risk_categories.csv", merchants, fingerprints, "merchant_raw")
    _eat(data / "gold_transactions_v5_LOCKED.csv", merchants, fingerprints, "merchant_raw")
    _eat(data / "tuning_leaf_topup.csv", merchants, fingerprints, "merchant_raw")
    _eat(OUT_DIR / "gold_v6_locked_sample.csv", merchants, fingerprints, "merchant_raw")
    _eat(OUT_DIR / "gold_pipeline_eval.csv", merchants, fingerprints, "merchant")
    merchants.discard("")
    return merchants, fingerprints


def _sql_quote_regex(pat: str) -> str:
    return pat.replace("\\", "\\\\").replace("'", "\\'")


def _init_waterfall():
    fe.SUB_MAP, fe.PRI_MAP, fe.PLAID_MAP, _ = load_crosswalk()
    fe.DICTIONARY = load_dictionary()
    fe.RULES = load_rules()


def fetch_leaf(client, leaf: str, exclude_merchants: list[str]) -> list[dict]:
    from google.cloud import bigquery

    natives = _natives_for(leaf)
    pat = KEYWORD_FALLBACK.get(leaf)
    clauses = []
    params = [
        bigquery.ArrayQueryParameter(
            "excluded", "STRING", exclude_merchants or [""]
        ),
    ]
    if natives:
        params.append(bigquery.ArrayQueryParameter("natives", "STRING", natives))
        clauses.append("credit_category_detailed IN UNNEST(@natives)")
    if pat:
        clauses.append(
            "REGEXP_CONTAINS("
            "LOWER(CONCAT(IFNULL(merchant_name, ''), ' ', "
            "IFNULL(COALESCE(original_description, transaction_name), ''))), "
            f"r'{_sql_quote_regex(pat)}')"
        )
    if not clauses:
        print(f"  [{leaf}] no native/keyword source — SKIPPED", file=sys.stderr)
        return []

    where = " OR ".join(f"({c})" for c in clauses)
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
      WHERE ({where})
        AND d.normalised_merchant IS NULL
        AND LOWER(TRIM(IFNULL(t.merchant_name, ''))) NOT IN UNNEST(@excluded)
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
    LIMIT {int(FETCH_N)}
    """
    job_config = bigquery.QueryJobConfig(query_parameters=params)
    rows = [dict(r) for r in client.query(sql, job_config=job_config).result()]
    print(f"  [{leaf}] BQ {len(rows)} T4-miss rows "
          f"(natives={natives or 'none'})", file=sys.stderr)
    return rows


def keep_t6(rows: list[dict], fingerprints: set, seen_merchants: set) -> list[dict]:
    kept = []
    dropped = Counter()
    for r in rows:
        m = _norm(r.get("merchant") or "")
        d = _norm(r.get("description_raw") or "")
        if (m, d) in fingerprints:
            dropped["eval_fingerprint"] += 1
            continue
        if m and m in seen_merchants:
            dropped["merchant_already_kept"] += 1
            continue
        direction = r.get("direction") or "debit"
        cat = r.get("native_category") or ""
        _leaf, tier = our_leaf(
            r.get("merchant") or "", direction, r.get("description_raw") or "",
            plaid_native_leaf, cat, direction,
        )
        if not str(tier).startswith("T6"):
            dropped[tier] += 1
            continue
        kept.append({**r, "waterfall_tier": tier, "t6_native_leaf": _leaf})
        if m:
            seen_merchants.add(m)
        fingerprints.add((m, d))
        if len(kept) >= KEEP_N:
            break
    if dropped:
        print(f"    dropped (not T6 / overlap): {dict(dropped)}", file=sys.stderr)
    return kept


def main():
    from google.cloud import bigquery

    _init_waterfall()
    exclude_m, fingerprints = load_exclusions()
    print(f"Exclusions: {len(exclude_m)} merchants, "
          f"{len(fingerprints)} fingerprints", file=sys.stderr)

    client = bigquery.Client(project="raylo-production")
    all_rows = []
    seen_merchants = set(exclude_m)
    row_id = 0
    by_leaf = {}
    for leaf in TARGET_LEAVES:
        raw = fetch_leaf(client, leaf, sorted(exclude_m) or [""])
        kept = keep_t6(raw, fingerprints, seen_merchants)
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
        print(f"  [{leaf}] kept {len(kept)} T6-bound", file=sys.stderr)

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
        "# T6 residual top-up fetch (2026-08-27)\n",
        "Plaid rows that miss T1–T5 (`our_leaf` tier starts with T6). "
        "Not labelled. Not appended to `tuning_leaf_topup.csv`. "
        "Not scored against locked v5/v6.\n",
        f"Wrote `{SAMPLE_CSV.relative_to(ROOT)}` — **{len(all_rows)}** rows.\n",
        "| target_leaf | n |",
        "|---|---:|",
    ]
    for leaf in TARGET_LEAVES:
        lines.append(f"| {leaf} | {by_leaf.get(leaf, 0)} |")
    COUNTS_MD.write_text("\n".join(lines) + "\n")
    print(f"\nWrote {SAMPLE_CSV}: {len(all_rows)} rows", file=sys.stderr)
    print(f"Wrote {COUNTS_MD}", file=sys.stderr)


if __name__ == "__main__":
    main()

"""Compare Plaid legacy `category` / `category_path` vs PFC `credit_category_detailed` as T6.

Maps every distinct live `category_path` in taxonomy/plaid_legacy_category_map.csv.
Does not score locked v5/v6. Does not change serving SQL.

Usage:
    python src/score_plaid_legacy_category.py
"""
from __future__ import annotations

import csv
import hashlib
import json
import pathlib
import sys
from collections import Counter

from dotenv import load_dotenv

load_dotenv()

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from eval_sets import refuse_confirmation_eval  # noqa: E402
from final_evaluation import (  # noqa: E402
    load_crosswalk,
    load_dictionary,
    load_rules,
    our_leaf,
    plaid_native_leaf,
)
import final_evaluation as fe  # noqa: E402

MAP_CSV = ROOT / "taxonomy" / "plaid_legacy_category_map.csv"
TAX = ROOT / "taxonomy" / "taxonomy.csv"
REPORT = ROOT / "data" / "plaid_legacy_category_t6_report.md"
PLAID_TABLE = "`raylo-production.dbt_production.credit_plaid_open_banking_transactions`"

GOLD = [
    ("holdout", ROOT / "data" / "gold_v2_slm_eval_holdout.csv"),
    ("pipeline", ROOT / "outputs" / "gold_pipeline_eval.csv"),
    ("risk", ROOT / "data" / "gold_transactions_risk_categories.csv"),
    ("v3", ROOT / "data" / "gold_transactions_v3_volume.csv"),
    ("v4", ROOT / "data" / "gold_transactions_v4_slm_volume.csv"),
]


def _norm(s):
    return (s or "").strip().lower()


def _amt(v):
    try:
        return round(abs(float(v)), 2)
    except (TypeError, ValueError):
        return None


def load_map():
    leaves = {r["detailed_category"] for r in csv.DictReader(open(TAX))}
    out = {}
    for r in csv.DictReader(open(MAP_CSV)):
        path = (r.get("category_path") or "").strip()
        leaf = (r.get("leaf") or "").strip()
        if leaf not in leaves:
            sys.exit(f"{MAP_CSV}: unknown leaf {leaf!r} for {path!r}")
        out[path] = leaf
    return out


def path_to_leaf(path, direction, mapping):
    path = (path or "").strip()
    leaf = mapping.get(path, "unclassified_other")
    if path and path not in mapping:
        leaf = "unclassified_other"
    if leaf.startswith("gambling") and direction == "credit":
        return "gambling_unspecified"
    return leaf


def json_to_path(cat_json):
    if cat_json is None or cat_json == "null":
        return ""
    if isinstance(cat_json, list):
        return " - ".join(str(x) for x in cat_json)
    try:
        arr = json.loads(cat_json)
        if arr is None:
            return ""
        return " - ".join(str(x) for x in arr)
    except (TypeError, json.JSONDecodeError):
        return str(cat_json)


def load_gold_rows():
    rows = []
    for name, path in GOLD:
        if not path.exists():
            continue
        if "LOCKED" in path.name:
            refuse_confirmation_eval(path)
        for r in csv.DictReader(open(path)):
            provider = (r.get("provider") or "").strip().lower()
            if provider and provider != "plaid":
                continue
            leaf = (r.get("gold_leaf") or "").strip()
            if not leaf:
                continue
            rows.append({
                "set": name,
                "merchant": r.get("merchant_raw") or "",
                "description": r.get("description_raw") or "",
                "amount": _amt(r.get("amount")),
                "direction": (r.get("direction") or "").strip().lower(),
                "native_category": r.get("native_category") or "",
                "gold_leaf": leaf,
            })
    return rows


def fp(r):
    return (_norm(r["merchant"]), _norm(r["description"]), r["amount"], r["direction"])


def fetch_plaid_paths(client, gold_rows):
    from google.cloud import bigquery

    merchants = sorted({_norm(r["merchant"]) for r in gold_rows if _norm(r["merchant"])})
    # blank-merchant gold: also pull by description hash would be huge; include blanks via
    # a second query on amount+direction is worse. Pull all blank-merchant rows that
    # match any gold description prefix? Simpler: UNNEST descriptions for blank merchants.
    blank_descs = sorted({_norm(r["description"])[:80] for r in gold_rows if not _norm(r["merchant"])})
    sql = f"""
    SELECT LOWER(TRIM(IFNULL(merchant_name, ''))) AS merchant,
           LOWER(TRIM(IFNULL(COALESCE(original_description, transaction_name), ''))) AS description,
           ROUND(ABS(amount), 2) AS amount,
           IF(amount < 0, 'credit', 'debit') AS direction,
           credit_category_detailed AS detailed,
           category_path
    FROM {PLAID_TABLE}
    WHERE LOWER(TRIM(IFNULL(merchant_name, ''))) IN UNNEST(@merchants)
       OR (
         TRIM(IFNULL(merchant_name, '')) = ''
         AND LOWER(SUBSTR(IFNULL(COALESCE(original_description, transaction_name), ''), 1, 80))
             IN UNNEST(@blank_descs)
       )
    """
    params = [
        bigquery.ArrayQueryParameter("merchants", "STRING", merchants or [""]),
        bigquery.ArrayQueryParameter("blank_descs", "STRING", blank_descs or [""]),
    ]
    job = client.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params))
    by_fp = {}
    n = 0
    for row in job.result():
        n += 1
        key = (row.merchant, row.description, float(row.amount) if row.amount is not None else None,
               row.direction)
        by_fp[key] = {"detailed": row.detailed or "", "category_path": row.category_path or ""}
    print(f"BQ pulled {n} candidate Plaid rows; {len(by_fp)} fingerprints", file=sys.stderr)
    return by_fp


def attach(gold_rows, by_fp):
    out = []
    miss = 0
    for r in gold_rows:
        key = fp(r)
        hit = by_fp.get(key)
        if not hit and r["native_category"]:
            # still score PFC from the gold file even if path join missed
            hit = {"detailed": r["native_category"], "category_path": None}
            r = {**r, "path_missing": True, **hit}
            miss += 1
        elif not hit:
            miss += 1
            continue
        else:
            r = {**r, "path_missing": hit["category_path"] in (None, ""), **hit}
            if not r["detailed"] and r["native_category"]:
                r["detailed"] = r["native_category"]
        out.append(r)
    print(f"gold {len(gold_rows)} -> joined {len(out)}; path-missing or unmatched {miss}",
          file=sys.stderr)
    return out


def acc(pairs):
    n = len(pairs)
    if not n:
        return None, 0
    return sum(1 for a, b in pairs if a == b) / n, n


def gen_acc(pairs, gen_of):
    n = len(pairs)
    if not n:
        return None, 0
    return sum(1 for a, b in pairs if gen_of.get(a) == gen_of.get(b)) / n, n


def fmt(p):
    return "n/a" if p is None else f"{p:.1%}"


def main():
    from google.cloud import bigquery

    mapping = load_map()
    gold = load_gold_rows()
    print(f"{len(gold)} Plaid-eligible gold rows", file=sys.stderr)
    client = bigquery.Client(project="raylo-production")
    by_fp = fetch_plaid_paths(client, gold)
    rows = attach(gold, by_fp)

    fe.SUB_MAP, fe.PRI_MAP, fe.PLAID_MAP, gen_of = load_crosswalk()
    fe.DICTIONARY = load_dictionary()
    fe.RULES = load_rules()

    scored = []
    for r in rows:
        detailed = r.get("detailed") or r.get("native_category") or ""
        path = r.get("category_path")
        if path is None:
            path = ""
        pfc = plaid_native_leaf(detailed, r["direction"])
        legacy = path_to_leaf(path, r["direction"], mapping)
        _, tier = our_leaf(
            r["merchant"], r["direction"], r["description"],
            plaid_native_leaf, detailed, r["direction"],
        )
        scored.append({**r, "pfc_leaf": pfc, "legacy_leaf": legacy, "tier": str(tier)})

    with_path = [r for r in scored if not r.get("path_missing") and r.get("category_path") not in (None, "")]
    t6 = [r for r in with_path if str(r["tier"]).startswith("T6")]

    def block(title, subset):
        golds = [r["gold_leaf"] for r in subset]
        pfc = [(r["gold_leaf"], r["pfc_leaf"]) for r in subset]
        leg = [(r["gold_leaf"], r["legacy_leaf"]) for r in subset]
        a, n = acc(pfc)
        b, _ = acc(leg)
        ga, _ = gen_acc(pfc, gen_of)
        gb, _ = gen_acc(leg, gen_of)
        agree = sum(1 for r in subset if r["pfc_leaf"] == r["legacy_leaf"]) / n if n else 0
        return {
            "title": title, "n": n,
            "pfc_leaf": a, "legacy_leaf": b,
            "pfc_gen": ga, "legacy_gen": gb,
            "agree": agree,
        }

    sections = [
        block("All joined Plaid gold with a category_path", with_path),
        block("T6-bound (miss T1–T5) with a category_path", t6),
    ]
    for set_name in ("holdout", "pipeline", "risk", "v3", "v4"):
        sub = [r for r in with_path if r["set"] == set_name]
        if sub:
            sections.append(block(f"{set_name} (with path)", sub))
        sub6 = [r for r in t6 if r["set"] == set_name]
        if sub6:
            sections.append(block(f"{set_name} T6-bound", sub6))

    # unmapped live paths check
    live_unmapped = []
    sql = f"""
    SELECT category_path, COUNT(*) n
    FROM {PLAID_TABLE}
    GROUP BY 1
    """
    mapped_keys = set(mapping)
    for row in client.query(sql).result():
        p = row.category_path or ""
        if p not in mapped_keys:
            live_unmapped.append((row.n, p))

    lines = [
        "# Plaid legacy `category` vs PFC detailed as T6 (2026-08-27)\n",
        "Plaid Asset Reports carry two category systems: the older list field "
        "(`category` / live `category_path`, e.g. `[\"Recreation\",\"Arts and Entertainment\","
        "\"Casinos and Gaming\"]`) and PFC v2 (`credit_category_detailed`), which is "
        "what T6 uses today. Every distinct live `category_path` is mapped in "
        f"`taxonomy/plaid_legacy_category_map.csv` ({len(mapping)} keys). "
        "Locked v5/v6 not scored. Serving SQL not changed.\n",
        "Join: gold Plaid rows to `credit_plaid_open_banking_transactions` on "
        "normalised merchant + description + abs(amount) + direction. "
        "T6-bound = `our_leaf` tier starts with T6 (dictionary and rules already lost).\n",
        "| set | n | PFC leaf | legacy leaf | PFC general | legacy general | PFC=legacy |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for s in sections:
        lines.append(
            f"| {s['title']} | {s['n']} | {fmt(s['pfc_leaf'])} | {fmt(s['legacy_leaf'])} | "
            f"{fmt(s['pfc_gen'])} | {fmt(s['legacy_gen'])} | {fmt(s['agree'])} |"
        )
    winner = sections[1] if len(sections) > 1 else sections[0]
    if winner["legacy_leaf"] is not None and winner["pfc_leaf"] is not None:
        delta = winner["legacy_leaf"] - winner["pfc_leaf"]
        lines.append(
            f"\n**T6-bound headline:** legacy path {fmt(winner['legacy_leaf'])} vs "
            f"PFC detailed {fmt(winner['pfc_leaf'])} ({delta:+.1%} leaf). "
            + ("Legacy is the better fallback on this set." if delta > 0.005
               else "PFC detailed remains the better fallback on this set." if delta < -0.005
               else "The two fallbacks are within 0.5pp.")
        )
    if live_unmapped:
        lines.append("\nUnmapped live `category_path` values (should be empty):\n")
        for n, p in sorted(live_unmapped, reverse=True)[:20]:
            lines.append(f"- {n:,} `{p}`")
    else:
        lines.append("\nAll live `category_path` values are in the map (blank → `unclassified_other`).")
    REPORT.write_text("\n".join(lines) + "\n")
    print(REPORT.read_text())
    print(f"Wrote {REPORT}", file=sys.stderr)


if __name__ == "__main__":
    main()

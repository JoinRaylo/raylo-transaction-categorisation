"""Targeted TRAINING top-up for risk-category leaves the classifier fails.

This is training data, not eval. The risk-category gold set
(data/gold_transactions_risk_categories.csv) stays held out. Sourced from
Plaid (serving input), labelled Gemini 3.7 Flash + Sonnet 5 (Option 1),
accepted on exact-leaf consensus, appended to data/tuning_leaf_topup.csv.

Do NOT use src/build_tuning_leaf_topup.py for this: that script sources
Equifax only and still labels with Haiku. cash_advance has an empty
equifax_source, so that fetch would skip it.

Usage:
    python src/build_risk_leaf_topup.py fetch
    python src/build_risk_leaf_topup.py label gemini
    python src/build_risk_leaf_topup.py label sonnet
    python src/build_risk_leaf_topup.py resolve   # appends to tuning_leaf_topup.csv
    python src/build_risk_leaf_topup.py gap_fill  # only if a starved leaf has <15 accepted
    python src/build_risk_leaf_topup.py promote_starved  # Amex/charge-card override + tight cash-advance/FSO fetch
"""
import csv
import json
import pathlib
import sys
from collections import Counter

from dotenv import load_dotenv

load_dotenv()

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "outputs"
sys.path.insert(0, str(ROOT / "src"))
from gating_experiment import (  # noqa: E402
    build_system_prompt, build_tool_schema, load_example_merchants, load_example_notes,
    build_notes_addendum, load_crosswalk,
)
from build_final_gold_v2 import TXN_ADDENDUM  # noqa: E402

SAMPLE_CSV = OUT_DIR / "risk_leaf_topup_sample.csv"
MODELS = {
    "gemini": {"backend": "gemini", "id": "gemini-3.7-flash", "extra": {}},
    "sonnet": {"backend": "anthropic", "id": "claude-sonnet-5", "max_tokens": 16000, "extra": {}},
}
PREDICTIONS = {k: OUT_DIR / f"risk_leaf_topup_predictions_{k}.csv" for k in MODELS}
FINAL_CSV = ROOT / "data" / "tuning_leaf_topup.csv"

STARVED = ["cash_advance", "charge_card_repayment", "financial_services_other"]
MEDIUM = ["gambling_unspecified", "payday_loan", "revolving_credit_repayment"]
RICH = ["gambling_bingo", "debt_collection"]
TARGET_LEAVES = STARVED + MEDIUM + RICH
FETCH_N = {**{l: 80 for l in STARVED}, **{l: 50 for l in MEDIUM}, **{l: 40 for l in RICH}}
MIN_ACCEPTED_STARVED = 15
GAP_FILL_N = 150

GAMBLING_SUBTYPES = [
    "gambling_betting", "gambling_casino", "gambling_bingo",
    "gambling_lottery", "prize_competitions",
]

# Permissive recall-over-precision. Consensus labelling is the filter, not these.
KEYWORD_FALLBACK = {
    "cash_advance": r"cash advance",
    "charge_card_repayment": r"charge card|\bamex\b|american express",
    "financial_services_other": r"financial services",
    "gambling_bingo": r"bingo|mecca bingo|gala bingo|tombola",
    "payday_loan": r"payday loan|wonga|quickquid|sunny loans",
    "revolving_credit_repayment": r"loqbox|newpay|credit builder|revolving credit|revolving line",
    "debt_collection": r"debt collection|debt collector|\bdca\b|credit collection",
}
RELAXED_KEYWORDS = {
    "cash_advance": r"cash advance|cashadv|cash-advance",
    "charge_card_repayment": r"charge card|amex|american express",
    "financial_services_other": r"financial services|accountancy|bookkeeping",
}
PLAID_NATIVE = {
    "cash_advance": ["LOAN_PAYMENTS_CASH_ADVANCES", "LOAN_DISBURSEMENTS_CASH_ADVANCES"],
    "financial_services_other": ["GENERAL_SERVICES_ACCOUNTING_AND_FINANCIAL_SERVICES"],
    "gambling_unspecified": ["ENTERTAINMENT_CASINOS_AND_GAMBLING"],
}

_, _, ALL_LEAVES, gen_of_all, _ = load_crosswalk()
for leaf in TARGET_LEAVES:
    assert leaf in gen_of_all, f"{leaf} not in taxonomy"


def _norm(s):
    return (s or "").strip().lower()


def _dict_merchants_for(leaf):
    return [r["normalised_merchant"] for r in csv.DictReader(open(ROOT / "taxonomy" / "merchant_dictionary.csv"))
            if r["detailed_category"] == leaf and _norm(r["normalised_merchant"])]


def _load_exclusion_files():
    """Merchant-level exclusions, blank-merchant descriptions, and exact
    (merchant, description) fingerprints of eval/locked/holdout/existing-topup rows.

    Starved leaves (cash_advance, charge_card) are often one live merchant
    (American Express) or blank-merchant narratives. Merchant-level exclusion
    would leave the class empty; those leaves drop only exact eval fingerprints.
    """
    merchants, blank_descs, fingerprints = set(), set(), set()

    def eat(path, merchant_key, desc_key="description_raw"):
        if not path.exists():
            return
        for r in csv.DictReader(open(path)):
            m = _norm(r.get(merchant_key, ""))
            d = _norm(r.get(desc_key, ""))
            fingerprints.add((m, d))
            if m:
                merchants.add(m)
            elif d:
                blank_descs.add(d)

    eat(ROOT / "data" / "gold_transactions_risk_categories.csv", "merchant_raw")
    eat(ROOT / "data" / "gold_transactions_v5_LOCKED.csv", "merchant_raw")
    eat(ROOT / "data" / "gold_v2_slm_eval_holdout.csv", "merchant_raw")
    eat(FINAL_CSV, "merchant_raw")
    return merchants, blank_descs, fingerprints


def _sql_quote_regex(pat):
    return pat.replace("\\", "\\\\").replace("'", "\\'")


def _fetch_leaf(client, leaf, n, exclude_merchants, exclude_descs, keyword_pat=None,
                extra_not_in=None, merchant_level_exclude=True, partition_by_description=False):
    from google.cloud import bigquery

    merchants = _dict_merchants_for(leaf)
    clauses = []
    params = [
        bigquery.ArrayQueryParameter("excluded", "STRING", sorted(exclude_merchants) or [""]),
        bigquery.ArrayQueryParameter("excluded_descs", "STRING", sorted(exclude_descs) or [""]),
    ]
    merchant_filter = ""
    if merchant_level_exclude:
        merchant_filter = "AND LOWER(TRIM(IFNULL(merchant_name, ''))) NOT IN UNNEST(@excluded)"
    partition = (
        "LOWER(TRIM(IFNULL(COALESCE(original_description, transaction_name), '')))"
        if partition_by_description else
        """IF(
          TRIM(IFNULL(merchant_name, '')) = '',
          LOWER(TRIM(IFNULL(COALESCE(original_description, transaction_name), ''))),
          LOWER(TRIM(merchant_name))
        )"""
    )
    if merchants:
        params.append(bigquery.ArrayQueryParameter("merchants", "STRING", merchants))
        clauses.append("LOWER(TRIM(IFNULL(merchant_name, ''))) IN UNNEST(@merchants)")
    pat = keyword_pat if keyword_pat is not None else KEYWORD_FALLBACK.get(leaf)
    if pat:
        clauses.append(
            f"REGEXP_CONTAINS(LOWER(COALESCE(original_description, transaction_name, '')), r'{_sql_quote_regex(pat)}')")
    natives = PLAID_NATIVE.get(leaf, [])
    if natives:
        params.append(bigquery.ArrayQueryParameter("natives", "STRING", natives))
        native_clause = "credit_category_detailed IN UNNEST(@natives)"
        if extra_not_in:
            params.append(bigquery.ArrayQueryParameter("not_merchants", "STRING", extra_not_in))
            native_clause = (f"({native_clause} AND LOWER(TRIM(IFNULL(merchant_name, ''))) "
                             f"NOT IN UNNEST(@not_merchants))")
        clauses.append(native_clause)
    if not clauses:
        print(f"  [{leaf}] no dictionary / keyword / native source -- SKIPPED", file=sys.stderr)
        return []

    where = " OR ".join(f"({c})" for c in clauses)
    sql = f"""
    SELECT merchant, merchant_raw, description_raw, amount, direction, native_category
    FROM (
      SELECT LOWER(TRIM(IFNULL(merchant_name, ''))) AS merchant,
             IFNULL(merchant_name, '') AS merchant_raw,
             IFNULL(COALESCE(original_description, transaction_name), '') AS description_raw,
             amount,
             IF(amount < 0, 'credit', 'debit') AS direction,
             credit_category_detailed AS native_category
      FROM `raylo-production.dbt_production.credit_plaid_open_banking_transactions`
      WHERE ({where})
        {merchant_filter}
        AND NOT (
          TRIM(IFNULL(merchant_name, '')) = ''
          AND LOWER(TRIM(IFNULL(COALESCE(original_description, transaction_name), '')))
              IN UNNEST(@excluded_descs)
        )
      QUALIFY ROW_NUMBER() OVER (
        PARTITION BY {partition}
        ORDER BY RAND()
      ) = 1
    )
    ORDER BY RAND()
    LIMIT {int(n)}
    """
    job_config = bigquery.QueryJobConfig(query_parameters=params)
    try:
        rows = [dict(r) for r in client.query(sql, job_config=job_config).result()]
    except Exception as e:
        print(f"  [{leaf}] query failed: {e}", file=sys.stderr)
        return []
    print(f"  [{leaf}] sourced {len(rows)} rows "
          f"(dict={len(merchants)}, keyword={'yes' if pat else 'no'}, "
          f"native={natives or 'none'})", file=sys.stderr)
    return rows


def fetch():
    from google.cloud import bigquery
    client = bigquery.Client(project="raylo-production")
    exclude_m, exclude_d, fingerprints = _load_exclusion_files()
    print(f"Exclusions: {len(exclude_m)} merchants, {len(exclude_d)} blank-merchant descriptions, "
          f"{len(fingerprints)} exact fingerprints", file=sys.stderr)

    subtype_merchants = []
    for sub in GAMBLING_SUBTYPES:
        subtype_merchants.extend(_dict_merchants_for(sub))
    subtype_merchants = sorted(set(subtype_merchants))

    all_rows = []
    row_id = 0
    seen_keys = set()
    for leaf in TARGET_LEAVES:
        extra_not = subtype_merchants if leaf == "gambling_unspecified" else None
        starved = leaf in STARVED
        rows = _fetch_leaf(
            client, leaf, FETCH_N[leaf], exclude_m, exclude_d, extra_not_in=extra_not,
            merchant_level_exclude=not starved, partition_by_description=starved,
        )
        for r in rows:
            fp = (_norm(r["merchant"]), _norm(r["description_raw"]))
            if fp in fingerprints:
                continue
            key = (*fp, leaf)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            fingerprints.add(fp)
            if not starved:
                if _norm(r["merchant"]):
                    exclude_m.add(_norm(r["merchant"]))
                elif _norm(r["description_raw"]):
                    exclude_d.add(_norm(r["description_raw"]))
            all_rows.append({"row_id": row_id, "target_leaf": leaf, "provider": "plaid", **r})
            row_id += 1

    OUT_DIR.mkdir(exist_ok=True)
    fieldnames = ["row_id", "target_leaf", "merchant", "merchant_raw", "description_raw",
                  "amount", "direction", "native_category", "provider"]
    with open(SAMPLE_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(all_rows)
    by_leaf = Counter(r["target_leaf"] for r in all_rows)
    print(f"\nWrote {SAMPLE_CSV}: {len(all_rows)} rows", file=sys.stderr)
    for leaf in TARGET_LEAVES:
        print(f"  {leaf}: {by_leaf.get(leaf, 0)}", file=sys.stderr)


def gap_fill():
    """Second pass for starved leaves that landed under MIN_ACCEPTED_STARVED after resolve.

    Relaxes keywords and re-fetches; appends to SAMPLE_CSV so label/resolve can
    be re-run (resolve is append-only and skips already-accepted fingerprints).
    """
    from google.cloud import bigquery

    if not FINAL_CSV.exists():
        sys.exit("gap_fill requires an existing resolve -- run resolve first")
    accepted = list(csv.DictReader(open(FINAL_CSV)))
    counts = Counter(r["gold_leaf"] for r in accepted)
    need = [l for l in STARVED if counts.get(l, 0) < MIN_ACCEPTED_STARVED]
    if not need:
        print(f"All starved leaves have >= {MIN_ACCEPTED_STARVED} accepted rows -- nothing to gap-fill",
              file=sys.stderr)
        return

    client = bigquery.Client(project="raylo-production")
    exclude_m, exclude_d, fingerprints = _load_exclusion_files()
    existing = list(csv.DictReader(open(SAMPLE_CSV))) if SAMPLE_CSV.exists() else []
    next_id = max((int(r["row_id"]) for r in existing), default=-1) + 1
    seen = {(_norm(r["merchant"]), _norm(r["description_raw"]), r["target_leaf"]) for r in existing}

    new_rows = []
    for leaf in need:
        print(f"  gap-fill {leaf}: currently {counts.get(leaf, 0)} accepted", file=sys.stderr)
        rows = _fetch_leaf(
            client, leaf, GAP_FILL_N, exclude_m, exclude_d,
            keyword_pat=RELAXED_KEYWORDS.get(leaf),
            merchant_level_exclude=False, partition_by_description=True,
        )
        for r in rows:
            fp = (_norm(r["merchant"]), _norm(r["description_raw"]))
            if fp in fingerprints:
                continue
            key = (*fp, leaf)
            if key in seen:
                continue
            seen.add(key)
            fingerprints.add(fp)
            new_rows.append({"row_id": next_id, "target_leaf": leaf, "provider": "plaid", **r})
            next_id += 1

    all_rows = existing + new_rows
    fieldnames = ["row_id", "target_leaf", "merchant", "merchant_raw", "description_raw",
                  "amount", "direction", "native_category", "provider"]
    with open(SAMPLE_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(all_rows)
    print(f"Gap-fill added {len(new_rows)} rows -> {SAMPLE_CSV} now {len(all_rows)}", file=sys.stderr)


def label(model_key):
    cfg = MODELS[model_key]
    _, _, leaves, gen_of, notes_of = load_crosswalk()
    system_prompt = (build_system_prompt(leaves, gen_of, notes_of, load_example_merchants())
                      + TXN_ADDENDUM + build_notes_addendum(load_example_notes()))

    rows = list(csv.DictReader(open(SAMPLE_CSV)))
    out_path = PREDICTIONS[model_key]
    predictions = {}
    if out_path.exists():
        predictions = {r["row_id"]: r for r in csv.DictReader(open(out_path)) if r["llm_leaf"]}
        print(f"Resuming: {len(predictions)} already labelled", file=sys.stderr)
    todo = [r for r in rows if r["row_id"] not in predictions]
    BATCH = 20

    def render(i, r):
        return (f"{i}. merchant: {r['merchant_raw']}\n"
                f"   description: {r['description_raw']}\n"
                f"   amount_gbp: {r['amount']} | direction: {r['direction']}\n"
                f"   native_category: {r['native_category']}")

    def flush():
        with open(out_path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["row_id", "merchant", "target_leaf", "llm_leaf", "llm_confidence"])
            w.writeheader()
            for p in predictions.values():
                w.writerow(p)

    if cfg["backend"] == "anthropic":
        import anthropic
        client = anthropic.Anthropic()
        tool = build_tool_schema(leaves)

        def classify_batch(batch, tag, attempt=0):
            user_msg = ("Classify each of these real transactions:\n\n"
                        + "\n".join(render(j + 1, r) for j, r in enumerate(batch)))
            try:
                resp = client.messages.create(
                    model=cfg["id"], max_tokens=cfg.get("max_tokens", 8000),
                    system=system_prompt, tools=[tool],
                    tool_choice={"type": "tool", "name": "submit_classifications"},
                    messages=[{"role": "user", "content": user_msg}], timeout=90.0,
                    **cfg.get("extra", {}),
                )
            except Exception as e:
                if attempt < 2:
                    print(f"  [{tag}] error ({e}), retrying...", file=sys.stderr)
                    import time
                    time.sleep(2 ** attempt)
                    return classify_batch(batch, tag, attempt + 1)
                print(f"  [{tag}] FAILED after retries: {e}", file=sys.stderr)
                return {}
            tool_use = next((b for b in resp.content if b.type == "tool_use"), None)
            if not tool_use:
                return {}
            by_idx = {j + 1: r for j, r in enumerate(batch)}
            out = {}
            for res in tool_use.input.get("results", []):
                r = by_idx.get(res.get("index"))
                if not r:
                    continue
                out[r["row_id"]] = {"row_id": r["row_id"], "merchant": r["merchant"],
                                    "target_leaf": r["target_leaf"],
                                    "llm_leaf": res.get("detailed_category"),
                                    "llm_confidence": res.get("confidence")}
            return out

    elif cfg["backend"] == "gemini":
        import os
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"], vertexai=False)
        leaf_list = sorted(leaves)
        index_addendum = "\n\n## Category index (output this number, not the name)\n" + "\n".join(
            f"{i + 1}. {leaf}" for i, leaf in enumerate(leaf_list))
        gemini_system = system_prompt + index_addendum
        schema = {
            "type": "object",
            "properties": {
                "results": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "index": {"type": "integer"},
                            "merchant": {"type": "string"},
                            "category_index": {"type": "integer", "minimum": 1, "maximum": len(leaf_list)},
                            "confidence": {"type": "number"},
                        },
                        "required": ["index", "merchant", "category_index", "confidence"],
                    },
                }
            },
            "required": ["results"],
        }

        def classify_batch(batch, tag, attempt=0):
            user_msg = ("Classify each of these real transactions:\n\n"
                        + "\n".join(render(j + 1, r) for j, r in enumerate(batch)))
            try:
                resp = client.models.generate_content(
                    model=cfg["id"], contents=user_msg,
                    config=types.GenerateContentConfig(
                        system_instruction=gemini_system,
                        response_mime_type="application/json", response_schema=schema,
                        temperature=0.0,
                    ),
                )
                data = json.loads(resp.text)
            except Exception as e:
                if attempt < 2:
                    print(f"  [{tag}] error ({e}), retrying...", file=sys.stderr)
                    import time
                    time.sleep(2 ** attempt)
                    return classify_batch(batch, tag, attempt + 1)
                print(f"  [{tag}] FAILED after retries: {e}", file=sys.stderr)
                return {}
            by_idx = {j + 1: r for j, r in enumerate(batch)}
            out = {}
            for res in data.get("results", []):
                cat_idx = res.get("category_index")
                r = by_idx.get(res.get("index"))
                if not r or not (isinstance(cat_idx, int) and 1 <= cat_idx <= len(leaf_list)):
                    continue
                out[r["row_id"]] = {"row_id": r["row_id"], "merchant": r["merchant"],
                                    "target_leaf": r["target_leaf"],
                                    "llm_leaf": leaf_list[cat_idx - 1],
                                    "llm_confidence": res.get("confidence")}
            return out
    else:
        sys.exit(f"unknown backend {cfg['backend']!r}")

    n_batches = (len(todo) + BATCH - 1) // BATCH
    for i in range(0, len(todo), BATCH):
        batch = todo[i:i + BATCH]
        num = i // BATCH + 1
        print(f"[{model_key}] batch {num}/{n_batches}", file=sys.stderr)
        predictions.update(classify_batch(batch, f"b{num:03d}"))
        for attempt in (1, 2):
            missing = [r for r in batch if r["row_id"] not in predictions]
            if not missing:
                break
            predictions.update(classify_batch(missing, f"b{num:03d}_r{attempt}"))
        if num % 5 == 0:
            flush()
    flush()
    missing = sum(1 for r in todo if r["row_id"] not in predictions)
    print(f"Wrote {out_path}: {len(predictions)} labelled, {missing} missing", file=sys.stderr)


def _blob(r):
    return f"{r.get('merchant_raw', '')} {r.get('description_raw', '')}".lower()


def _is_amex(r):
    blob = _blob(r)
    return "american express" in blob or "amex" in blob


def _is_unp_or_reversal(r):
    d = (r.get("description_raw") or "").lower()
    return " unp" in f" {d}" or "unp " in d or "revers" in d


def _apply_starved_override(r, consensus_leaf):
    """Taxonomy convention the production prompt will not emit.

    American Express is a charge card (Equifax source = Charge Card). Gemini and
    Sonnet both map it to credit_card_repayment. Without this override the
    charge_card_repayment class stays empty.
    """
    if (
        r.get("target_leaf") == "charge_card_repayment"
        and (r.get("direction") or "").lower() == "debit"
        and _is_amex(r)
        and not _is_unp_or_reversal(r)
        and consensus_leaf in {"credit_card_repayment", "charge_card_repayment"}
    ):
        return "charge_card_repayment"
    return consensus_leaf


def _eval_amount_fps():
    """(merchant, description, amount, direction) of protected eval/locked/holdout rows."""
    fps = set()
    specs = [
        (ROOT / "data" / "gold_transactions_risk_categories.csv", "merchant_raw"),
        (ROOT / "data" / "gold_transactions_v5_LOCKED.csv", "merchant_raw"),
        (ROOT / "data" / "gold_v2_slm_eval_holdout.csv", "merchant_raw"),
    ]
    for path, mkey in specs:
        if not path.exists():
            continue
        for r in csv.DictReader(open(path)):
            try:
                amt = round(abs(float(r["amount"])), 2)
            except (TypeError, ValueError):
                continue
            fps.add((_norm(r.get(mkey, "")), _norm(r.get("description_raw", "")),
                     amt, (r.get("direction") or "").lower()))
    return fps


def _amt_key(v):
    try:
        return f"{round(float(v), 2):.2f}"
    except (TypeError, ValueError):
        return str(v or "")


def _append_topup_rows(new_rows):
    existing = list(csv.DictReader(open(FINAL_CSV))) if FINAL_CSV.exists() else []
    existing_fp = {
        (_norm(r["merchant_raw"]), _norm(r["description_raw"]),
         _amt_key(r.get("amount")), (r.get("direction") or "").lower(), r["gold_leaf"])
        for r in existing
    }
    fieldnames = ["merchant_raw", "description_raw", "amount", "direction",
                  "native_category", "gold_leaf", "target_leaf"]
    added = []
    for r in new_rows:
        fp = (_norm(r["merchant_raw"]), _norm(r["description_raw"]),
              _amt_key(r.get("amount")), (r.get("direction") or "").lower(), r["gold_leaf"])
        if fp in existing_fp:
            continue
        existing_fp.add(fp)
        added.append({k: r.get(k, "") for k in fieldnames})
    with open(FINAL_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(existing)
        w.writerows(added)
    return existing, added


def promote_starved():
    """Fill the three starved leaves without trusting Plaid's coarse native buckets.

    charge_card_repayment: Amex debit payments already in the top-up file (LLM
        said credit_card_repayment; taxonomy says charge card).
    cash_advance: bank-product narrative 'Cash Advance' (amount-disjoint from
        eval) plus genuine LOAN_PAYMENTS_CASH_ADVANCES merchants (YouLend/Bizlend).
        Does NOT take LOAN_DISBURSEMENTS_CASH_ADVANCES — that bucket is P2P/BNPL/gambling.
    financial_services_other: T4 dictionary merchants (Curve subscription, Elfin,
        FE Fundinfo) with eval fingerprints dropped — not the coarse Plaid
        GENERAL_SERVICES_ACCOUNTING_AND_FINANCIAL_SERVICES bucket.
    """
    from google.cloud import bigquery

    existing = list(csv.DictReader(open(FINAL_CSV))) if FINAL_CSV.exists() else []
    n_relabel = 0
    for r in existing:
        if (
            r.get("gold_leaf") == "credit_card_repayment"
            and (r.get("target_leaf") == "charge_card_repayment"
                 or _is_amex(r))
            and (r.get("direction") or "").lower() == "debit"
            and _is_amex(r)
            and not _is_unp_or_reversal(r)
        ):
            r["gold_leaf"] = "charge_card_repayment"
            n_relabel += 1
    fieldnames = ["merchant_raw", "description_raw", "amount", "direction",
                  "native_category", "gold_leaf", "target_leaf"]
    with open(FINAL_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(existing)
    print(f"Relabelled {n_relabel} Amex debit rows -> charge_card_repayment", file=sys.stderr)

    _, _, fingerprints = _load_exclusion_files()
    amount_fps = _eval_amount_fps()
    client = bigquery.Client(project="raylo-production")

    cash_sql = r"""
    SELECT IFNULL(merchant_name, '') AS merchant_raw,
           IFNULL(COALESCE(original_description, transaction_name), '') AS description_raw,
           ABS(amount) AS amount,
           IF(amount < 0, 'credit', 'debit') AS direction,
           credit_category_detailed AS native_category
    FROM `raylo-production.dbt_production.credit_plaid_open_banking_transactions`
    WHERE (
        LOWER(TRIM(IFNULL(COALESCE(original_description, transaction_name), ''))) = 'cash advance'
        OR (
          credit_category_detailed = 'LOAN_PAYMENTS_CASH_ADVANCES'
          AND LOWER(TRIM(IFNULL(merchant_name, ''))) IN ('youlend', 'bizlend ltd', 'bizlend')
        )
    )
    QUALIFY ROW_NUMBER() OVER (
      PARTITION BY LOWER(TRIM(IFNULL(merchant_name, ''))),
                   LOWER(TRIM(IFNULL(COALESCE(original_description, transaction_name), ''))),
                   ABS(amount),
                   IF(amount < 0, 'credit', 'debit')
      ORDER BY RAND()
    ) = 1
    """
    cash_rows = []
    for r in client.query(cash_sql).result():
        row = dict(r)
        merch, desc = _norm(row["merchant_raw"]), _norm(row["description_raw"])
        amt = round(float(row["amount"]), 2)
        direction = row["direction"]
        if (merch, desc, amt, direction) in amount_fps:
            continue
        if (merch, desc) in fingerprints and desc != "cash advance":
            # Identical product string as eval is unavoidable for this leaf;
            # amount-disjoint rows of 'Cash Advance' are kept. Other merchants
            # still drop on (merchant, description) overlap.
            continue
        cash_rows.append({
            "merchant_raw": row["merchant_raw"],
            "description_raw": row["description_raw"],
            "amount": row["amount"],
            "direction": direction,
            "native_category": row["native_category"],
            "gold_leaf": "cash_advance",
            "target_leaf": "cash_advance",
        })
    print(f"cash_advance candidates after eval exclusion: {len(cash_rows)}", file=sys.stderr)

    fso_sql = r"""
    SELECT IFNULL(merchant_name, '') AS merchant_raw,
           IFNULL(COALESCE(original_description, transaction_name), '') AS description_raw,
           ABS(amount) AS amount,
           IF(amount < 0, 'credit', 'debit') AS direction,
           credit_category_detailed AS native_category
    FROM `raylo-production.dbt_production.credit_plaid_open_banking_transactions`
    WHERE LOWER(TRIM(IFNULL(merchant_name, ''))) IN ('curve', 'elfin market', 'fe fundinfo')
      AND IF(amount < 0, 'credit', 'debit') = 'debit'
      AND (
        LOWER(TRIM(IFNULL(merchant_name, ''))) IN ('elfin market', 'fe fundinfo')
        OR REGEXP_CONTAINS(LOWER(COALESCE(original_description, transaction_name, '')),
                           r'curve subscription|crv\*curve')
      )
    QUALIFY ROW_NUMBER() OVER (
      PARTITION BY LOWER(TRIM(IFNULL(COALESCE(original_description, transaction_name), '')))
      ORDER BY RAND()
    ) = 1
    """
    fso_rows = []
    for r in client.query(fso_sql).result():
        row = dict(r)
        merch, desc = _norm(row["merchant_raw"]), _norm(row["description_raw"])
        if (merch, desc) in fingerprints:
            continue
        fso_rows.append({
            "merchant_raw": row["merchant_raw"],
            "description_raw": row["description_raw"],
            "amount": row["amount"],
            "direction": row["direction"],
            "native_category": row["native_category"],
            "gold_leaf": "financial_services_other",
            "target_leaf": "financial_services_other",
        })
    print(f"financial_services_other candidates after eval exclusion: {len(fso_rows)}",
          file=sys.stderr)

    _, added = _append_topup_rows(cash_rows + fso_rows)
    all_rows = list(csv.DictReader(open(FINAL_CSV)))
    counts = Counter(r["gold_leaf"] for r in all_rows)
    print(f"Appended {len(added)} starved-leaf rows; file now {len(all_rows)}", file=sys.stderr)
    print("Starved-leaf totals in file:", {l: counts.get(l, 0) for l in STARVED}, file=sys.stderr)
    short = [l for l in STARVED if counts.get(l, 0) < MIN_ACCEPTED_STARVED]
    if short:
        print(f"WARNING: starved leaves still under {MIN_ACCEPTED_STARVED}: {short}",
              file=sys.stderr)


def resolve():
    rows = list(csv.DictReader(open(SAMPLE_CSV)))
    gemini = {r["row_id"]: r for r in csv.DictReader(open(PREDICTIONS["gemini"]))}
    sonnet = {r["row_id"]: r for r in csv.DictReader(open(PREDICTIONS["sonnet"]))}

    existing = list(csv.DictReader(open(FINAL_CSV))) if FINAL_CSV.exists() else []
    existing_fp = {
        (_norm(r["merchant_raw"]), _norm(r["description_raw"]), r["gold_leaf"])
        for r in existing
    }

    accepted, dropped_disagree, dropped_dup, off_target = [], 0, 0, 0
    for r in rows:
        g, s = gemini.get(r["row_id"]), sonnet.get(r["row_id"])
        if not g or not s or not g.get("llm_leaf") or not s.get("llm_leaf"):
            continue
        if g["llm_leaf"] != s["llm_leaf"]:
            dropped_disagree += 1
            continue
        leaf = _apply_starved_override(r, g["llm_leaf"])
        fp = (_norm(r["merchant_raw"]), _norm(r["description_raw"]), leaf)
        if fp in existing_fp:
            dropped_dup += 1
            continue
        existing_fp.add(fp)
        out = {
            "merchant_raw": r["merchant_raw"],
            "description_raw": r["description_raw"],
            "amount": r["amount"],
            "direction": r["direction"],
            "native_category": r["native_category"],
            "gold_leaf": leaf,
            "target_leaf": r["target_leaf"],
        }
        accepted.append(out)
        if leaf != r["target_leaf"]:
            off_target += 1

    fieldnames = ["merchant_raw", "description_raw", "amount", "direction",
                  "native_category", "gold_leaf", "target_leaf"]
    with open(FINAL_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(existing)
        w.writerows(accepted)

    new_counts = Counter(r["gold_leaf"] for r in accepted)
    all_counts = Counter(r["gold_leaf"] for r in existing + accepted)
    print(f"Accepted this pass: {len(accepted)} / {len(rows)}", file=sys.stderr)
    print(f"Dropped (models disagreed): {dropped_disagree}", file=sys.stderr)
    print(f"Dropped (already in top-up file): {dropped_dup}", file=sys.stderr)
    print(f"Landed on a different leaf than targeted (kept): {off_target}", file=sys.stderr)
    print(f"File now {len(existing) + len(accepted)} rows (was {len(existing)})", file=sys.stderr)
    print("Accepted this pass by gold_leaf:", dict(new_counts), file=sys.stderr)
    print("Starved-leaf totals in file:",
          {l: all_counts.get(l, 0) for l in STARVED}, file=sys.stderr)
    short = [l for l in STARVED if all_counts.get(l, 0) < MIN_ACCEPTED_STARVED]
    if short:
        print(f"WARNING: starved leaves still under {MIN_ACCEPTED_STARVED}: {short} "
              f"-- run gap_fill then label + resolve again", file=sys.stderr)
    print(f"Wrote {FINAL_CSV}", file=sys.stderr)


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] not in {"fetch", "label", "resolve", "gap_fill", "promote_starved"}:
        sys.exit(__doc__)
    if args[0] == "fetch":
        fetch()
    elif args[0] == "gap_fill":
        gap_fill()
    elif args[0] == "label":
        if len(sys.argv) < 3 or sys.argv[2] not in MODELS:
            sys.exit(f"Usage: label [{'|'.join(MODELS)}]")
        label(sys.argv[2])
    elif args[0] == "resolve":
        resolve()
    elif args[0] == "promote_starved":
        promote_starved()

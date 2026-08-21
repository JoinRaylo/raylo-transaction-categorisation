"""Targeted top-up for the 76 taxonomy leaves that have <5 combined examples
across gold_transactions_v2/v3 and production_labels_tranche3 (22 with zero).

Unlike gold_v2/v3, this is TRAINING data, not an eval set -- per the agreed
philosophy, bulk training volume doesn't need full individual human review,
just the same LLM-consensus trust model already used for production_labels
(two models agree -> accept; disagree -> drop rather than guess, since we
only need a handful of good examples per class, not every row).

Sources real transactions from the Equifax subcategory/primary that maps to
each target leaf (Plaid's categories are too coarse to reach most of these --
same finding as batch 2), excludes every merchant already in Tier A (gold_v2)
or Tier B (production_labels) so this adds genuinely new coverage.

Usage:
    python src/build_tuning_leaf_topup.py fetch
    python src/build_tuning_leaf_topup.py label haiku
    python src/build_tuning_leaf_topup.py label sonnet
    python src/build_tuning_leaf_topup.py resolve   # -> data/tuning_leaf_topup.csv
"""
import csv
import pathlib
import sys

from dotenv import load_dotenv

load_dotenv()

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "outputs"
sys.path.insert(0, str(ROOT / "src"))
from gating_experiment import (MODELS, build_system_prompt, build_tool_schema,  # noqa: E402
                                load_example_merchants, load_example_notes, build_notes_addendum, load_crosswalk)
from build_final_gold_v2 import TXN_ADDENDUM  # noqa: E402
from build_final_gold_v2_batch2 import _leaf_equifax_queries  # noqa: E402

SAMPLE_CSV = OUT_DIR / "tuning_topup_sample.csv"
PREDICTIONS = {k: OUT_DIR / f"tuning_topup_predictions_{k}.csv" for k in MODELS}
FINAL_CSV = ROOT / "data" / "tuning_leaf_topup.csv"
N_PER_LEAF = 8


def _norm(s):
    return (s or "").strip().lower()


def _target_leaves():
    tier_a = []
    for f in ["gold_transactions_v2.csv", "gold_transactions_v2_batch2.csv"]:
        p = ROOT / "data" / f
        if p.exists():
            tier_a.extend(csv.DictReader(open(p)))
    from collections import Counter
    tier_a_counts = Counter(r["gold_leaf"] for r in tier_a)

    GOOD_TIERS = {"auto_accept", "accepted", "human_reviewed"}
    prod = list(csv.DictReader(open(ROOT / "data" / "production_labels_tranche3.csv")))
    tier_b_counts = Counter(r["final_leaf"] for r in prod if r["tier"] in GOOD_TIERS)

    _, _, leaves, _, _ = load_crosswalk()
    thin = [l for l in leaves if tier_a_counts.get(l, 0) + tier_b_counts.get(l, 0) < 5]
    return thin, tier_a_counts, tier_b_counts


def _existing_merchant_exclusions():
    excluded = set()
    for f in ["gold_transactions_v2.csv", "gold_transactions_v2_batch2.csv"]:
        p = ROOT / "data" / f
        if p.exists():
            excluded |= {_norm(r["merchant_raw"]) for r in csv.DictReader(open(p))}
    for r in csv.DictReader(open(ROOT / "data" / "production_labels_tranche3.csv")):
        excluded.add(_norm(r["merchant"]))
    return excluded


def fetch():
    from google.cloud import bigquery
    client = bigquery.Client(project="raylo-production")

    target_leaves, tier_a_counts, tier_b_counts = _target_leaves()
    print(f"{len(target_leaves)} target leaves (< 5 combined examples)", file=sys.stderr)
    exclude = _existing_merchant_exclusions()
    print(f"{len(exclude)} merchants already covered -- excluded from sourcing", file=sys.stderr)

    tax_rows = {r["detailed_category"]: r for r in csv.DictReader(open(ROOT / "taxonomy" / "taxonomy.csv"))}
    rows = []
    no_data = []
    for leaf in target_leaves:
        row = tax_rows.get(leaf)
        if not row or not row["equifax_source"]:
            no_data.append(leaf)
            continue
        found_any = False
        for pri, sub in _leaf_equifax_queries(leaf, row):
            conditions = ["TRUE"]
            params = []
            if pri:
                conditions.append("PrimaryCategoryDescription = @pri")
                params.append(bigquery.ScalarQueryParameter("pri", "STRING", pri))
            if sub:
                conditions.append("SubCategoryDescription IN UNNEST(@sub)")
                params.append(bigquery.ArrayQueryParameter("sub", "STRING", sub))
            params.append(bigquery.ArrayQueryParameter("excluded", "STRING", sorted(exclude)))
            sql = f"""
            SELECT LOWER(TRIM(VendorDescription)) AS merchant, VendorDescription AS merchant_raw,
                   Description AS description_raw, Amount AS amount,
                   IF(TransactionTypeId=1,'credit','debit') AS direction,
                   CONCAT(PrimaryCategoryDescription, ' | ', SubCategoryDescription) AS native_category
            FROM `raylo-production.equifax_data.open_banking_full_dump`
            TABLESAMPLE SYSTEM (10 PERCENT)
            WHERE {' AND '.join(conditions)}
              AND VendorDescription IS NOT NULL AND TRIM(VendorDescription) != ''
              AND LOWER(TRIM(VendorDescription)) NOT IN UNNEST(@excluded)
            ORDER BY RAND()
            LIMIT {N_PER_LEAF}
            """
            job_config = bigquery.QueryJobConfig(query_parameters=params)
            try:
                hits = list(client.query(sql, job_config=job_config).result())
            except Exception as e:
                print(f"  [{leaf}] query failed: {e}", file=sys.stderr)
                continue
            for r in hits:
                m = r["merchant"]
                if m in exclude:
                    continue
                exclude.add(m)
                found_any = True
                rows.append({
                    "target_leaf": leaf, "merchant": m, "merchant_raw": r["merchant_raw"],
                    "description_raw": r["description_raw"] or "", "amount": r["amount"],
                    "direction": r["direction"], "native_category": r["native_category"],
                })
        if not found_any:
            no_data.append(leaf)

    for i, r in enumerate(rows):
        r["row_id"] = i
    print(f"Sourced {len(rows)} real transactions for {len(target_leaves) - len(no_data)} of "
          f"{len(target_leaves)} target leaves", file=sys.stderr)
    print(f"Genuinely no Equifax data found for {len(no_data)} leaves: {no_data}", file=sys.stderr)

    OUT_DIR.mkdir(exist_ok=True)
    fieldnames = ["row_id"] + [k for k in rows[0].keys() if k != "row_id"]
    with open(SAMPLE_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader(); w.writerows(rows)
    print(f"Wrote {SAMPLE_CSV}", file=sys.stderr)


def label(model_key):
    import anthropic

    cfg = MODELS[model_key]
    _, _, leaves, gen_of, notes_of = load_crosswalk()
    system_prompt = (build_system_prompt(leaves, gen_of, notes_of, load_example_merchants())
                      + TXN_ADDENDUM + build_notes_addendum(load_example_notes()))
    tool = build_tool_schema(leaves)

    rows = list(csv.DictReader(open(SAMPLE_CSV)))
    out_path = PREDICTIONS[model_key]
    predictions = {}
    if out_path.exists():
        predictions = {r["row_id"]: r for r in csv.DictReader(open(out_path)) if r["llm_leaf"]}
        print(f"Resuming: {len(predictions)} already labelled", file=sys.stderr)

    def row_key(r):
        return r["row_id"]

    todo = [r for r in rows if row_key(r) not in predictions]
    client = anthropic.Anthropic()
    BATCH = 20
    n_batches = (len(todo) + BATCH - 1) // BATCH

    def render(i, r):
        return (f"{i}. merchant: {r['merchant_raw']}\n"
                f"   description: {r['description_raw']}\n"
                f"   amount_gbp: {r['amount']} | direction: {r['direction']}\n"
                f"   native_category: {r['native_category']}")

    def flush():
        with open(out_path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["row_id", "merchant", "llm_leaf", "llm_confidence"])
            w.writeheader()
            for k, p in predictions.items():
                w.writerow({"row_id": p["row_id"], "merchant": p["merchant"],
                            "llm_leaf": p["llm_leaf"], "llm_confidence": p["llm_confidence"]})

    def classify_batch(batch, tag, attempt=0):
        user_msg = ("Classify each of these real transactions:\n\n"
                    + "\n".join(render(j + 1, r) for j, r in enumerate(batch)))
        try:
            resp = client.messages.create(
                model=cfg["id"], max_tokens=cfg.get("max_tokens", 8000),
                system=system_prompt, tools=[tool],
                tool_choice={"type": "tool", "name": "submit_classifications"},
                messages=[{"role": "user", "content": user_msg}],
                timeout=90.0,
                **cfg.get("extra", {}),
            )
        except Exception as e:
            if attempt < 2:
                print(f"  [{tag}] error ({e}), retrying...", file=sys.stderr)
                import time; time.sleep(2 ** attempt)
                return classify_batch(batch, tag, attempt + 1)
            print(f"  [{tag}] FAILED after retries: {e}", file=sys.stderr)
            return {}
        tool_use = next((b for b in resp.content if b.type == "tool_use"), None)
        if not tool_use:
            return {}
        by_idx = {j + 1: r for j, r in enumerate(batch)}
        out = {}
        for res in tool_use.input.get("results", []):
            idx = res.get("index")
            r = by_idx.get(idx)
            if not r:
                continue
            out[row_key(r)] = {"row_id": r["row_id"], "merchant": r["merchant"],
                                "llm_leaf": res.get("detailed_category"), "llm_confidence": res.get("confidence")}
        return out

    for i in range(0, len(todo), BATCH):
        batch = todo[i:i + BATCH]
        num = i // BATCH + 1
        print(f"[{model_key}] batch {num}/{n_batches}", file=sys.stderr)
        predictions.update(classify_batch(batch, f"b{num:04d}"))
        for attempt in (1, 2):
            missing = [r for r in batch if row_key(r) not in predictions]
            if not missing:
                break
            predictions.update(classify_batch(missing, f"b{num:04d}_r{attempt}"))
        flush()
    missing = sum(1 for r in todo if row_key(r) not in predictions)
    print(f"Wrote {out_path}: {len(predictions)} labelled, {missing} missing", file=sys.stderr)


def resolve():
    """Agreement-based trust, same model as production_labels: both models agree ->
    accept as a training example. Disagree -> drop (we only need a handful of good
    examples per class, not every sampled row)."""
    rows = list(csv.DictReader(open(SAMPLE_CSV)))
    haiku = {r["row_id"]: r for r in csv.DictReader(open(PREDICTIONS["haiku"]))}
    sonnet = {r["row_id"]: r for r in csv.DictReader(open(PREDICTIONS["sonnet"]))}

    accepted, dropped_disagree, dropped_offtarget = [], 0, 0
    for r in rows:
        h, s = haiku.get(r["row_id"]), sonnet.get(r["row_id"])
        if not h or not s:
            continue
        if h["llm_leaf"] != s["llm_leaf"]:
            dropped_disagree += 1
            continue
        leaf = h["llm_leaf"]
        r["gold_leaf"] = leaf
        accepted.append(r)
        if leaf != r["target_leaf"]:
            dropped_offtarget += 1  # still a valid, useful example -- just not for the leaf we were targeting

    from collections import Counter
    target_leaves, tier_a_counts, tier_b_counts = _target_leaves()
    new_counts = Counter(r["gold_leaf"] for r in accepted)
    still_zero = [l for l in target_leaves
                  if tier_a_counts.get(l, 0) + tier_b_counts.get(l, 0) + new_counts.get(l, 0) < 5]

    with open(FINAL_CSV, "w", newline="") as f:
        fieldnames = ["merchant_raw", "description_raw", "amount", "direction", "native_category", "gold_leaf", "target_leaf"]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in accepted:
            w.writerow({k: r[k] for k in fieldnames if k in r} | {"gold_leaf": r["gold_leaf"]})

    print(f"Accepted (models agreed): {len(accepted)} / {len(rows)}", file=sys.stderr)
    print(f"Dropped (models disagreed): {dropped_disagree}", file=sys.stderr)
    print(f"Landed on a different leaf than targeted (still a valid example): {dropped_offtarget}", file=sys.stderr)
    print(f"Of the {len(target_leaves)} target leaves, still under 5 combined examples after top-up: "
          f"{len(still_zero)}: {still_zero}", file=sys.stderr)
    print(f"Wrote {FINAL_CSV}", file=sys.stderr)


def fetch_gap_fill(gap_leaves):
    """Second pass for leaves that got zero new examples with the exclusion on --
    those categories have so few real Equifax merchants that the exclusion (skip
    anything already in Tier A/B) leaves nothing. Relaxes the exclusion: still
    skips merchants already claimed by THIS run, but allows reusing a merchant
    that's in Tier A/B for a different leaf, since the native category match
    itself is direct evidence, not a guess -- worth a human/LLM double-check
    rather than silently having zero examples for the class."""
    from google.cloud import bigquery
    client = bigquery.Client(project="raylo-production")

    tax_rows = {r["detailed_category"]: r for r in csv.DictReader(open(ROOT / "taxonomy" / "taxonomy.csv"))}
    existing = list(csv.DictReader(open(SAMPLE_CSV))) if SAMPLE_CSV.exists() else []
    seen = {r["merchant"] for r in existing}
    next_id = max((int(r["row_id"]) for r in existing), default=-1) + 1

    rows = []
    still_no_data = []
    for leaf in gap_leaves:
        row = tax_rows.get(leaf)
        if not row or not row["equifax_source"]:
            still_no_data.append(leaf)
            continue
        found_any = False
        for pri, sub in _leaf_equifax_queries(leaf, row):
            conditions = ["TRUE"]
            params = []
            if pri:
                conditions.append("PrimaryCategoryDescription = @pri")
                params.append(bigquery.ScalarQueryParameter("pri", "STRING", pri))
            if sub:
                conditions.append("SubCategoryDescription IN UNNEST(@sub)")
                params.append(bigquery.ArrayQueryParameter("sub", "STRING", sub))
            sql = f"""
            SELECT LOWER(TRIM(VendorDescription)) AS merchant, VendorDescription AS merchant_raw,
                   Description AS description_raw, Amount AS amount,
                   IF(TransactionTypeId=1,'credit','debit') AS direction,
                   CONCAT(PrimaryCategoryDescription, ' | ', SubCategoryDescription) AS native_category
            FROM `raylo-production.equifax_data.open_banking_full_dump`
            WHERE {' AND '.join(conditions)}
              AND VendorDescription IS NOT NULL AND TRIM(VendorDescription) != ''
            ORDER BY RAND()
            LIMIT {N_PER_LEAF}
            """
            job_config = bigquery.QueryJobConfig(query_parameters=params) if params else None
            try:
                hits = list(client.query(sql, job_config=job_config).result())
            except Exception as e:
                print(f"  [{leaf}] query failed: {e}", file=sys.stderr)
                continue
            for r in hits:
                m = r["merchant"]
                if m in seen:
                    continue
                seen.add(m)
                found_any = True
                rows.append({
                    "target_leaf": leaf, "merchant": m, "merchant_raw": r["merchant_raw"],
                    "description_raw": r["description_raw"] or "", "amount": r["amount"],
                    "direction": r["direction"], "native_category": r["native_category"],
                })
        if not found_any:
            still_no_data.append(leaf)

    for r in rows:
        r["row_id"] = next_id
        next_id += 1

    print(f"Gap-fill pass: sourced {len(rows)} more transactions for "
          f"{len(gap_leaves) - len(still_no_data)} of {len(gap_leaves)} leaves", file=sys.stderr)
    print(f"Still genuinely zero Equifax data at all for {len(still_no_data)} leaves: {still_no_data}", file=sys.stderr)

    all_rows = existing + rows
    fieldnames = ["row_id"] + [k for k in all_rows[0].keys() if k != "row_id"]
    with open(SAMPLE_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader(); w.writerows(all_rows)
    print(f"Wrote {SAMPLE_CSV}: {len(all_rows)} total rows", file=sys.stderr)


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] not in {"fetch", "gap_fill", "label", "resolve"}:
        sys.exit(__doc__)
    if args[0] == "fetch":
        fetch()
    elif args[0] == "gap_fill":
        gap_leaves = sys.argv[2].split(",")
        fetch_gap_fill(gap_leaves)
    elif args[0] == "label":
        if len(sys.argv) < 3 or sys.argv[2] not in MODELS:
            sys.exit(f"Usage: label [{'|'.join(MODELS)}]")
        label(sys.argv[2])
    elif args[0] == "resolve":
        resolve()

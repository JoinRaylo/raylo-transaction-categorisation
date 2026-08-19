"""Production vocabulary labelling (the LLM route, post-gating GREEN LIGHT).

Labels the unmatched Plaid merchant vocabulary with the context-enriched
two-model pipeline and gates every string into a quality tier. Accepted
labels become T4 lookup data; nothing enters the dictionary silently.

Tiers (thresholds from measured calibration -- CLAUDE.md section 6):
    auto_accept        models agree AND sonnet confidence >= 0.9
    accepted           models agree AND sonnet confidence >= 0.7
    abstain_confirmed  both models say unclassified_other
    needs_review       everything else (disagreement / low confidence)

Usage:
    python src/production_labelling.py fetch [N]     # top-N unmatched strings + evidence
    python src/production_labelling.py label [haiku|sonnet]
    python src/production_labelling.py gate           # -> outputs/production_labels.csv + stats
"""
import csv
import json
import pathlib
import sys

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from gating_experiment import (  # noqa: E402
    MODELS, ROOT, OUT_DIR, build_system_prompt, build_tool_schema,
    load_crosswalk, load_example_merchants,
)
from build_tail_eval import TAIL_ADDENDUM, POPULATION_QUERY, bq_json  # noqa: E402

STRINGS_CSV = OUT_DIR / "production_strings.csv"
EVIDENCE_JSON = OUT_DIR / "production_evidence.json"
PREDICTIONS = {k: OUT_DIR / f"production_predictions_{k}.csv" for k in MODELS}
OPUS_PREDICTIONS = OUT_DIR / "production_predictions_opus.csv"
LABELS_CSV = OUT_DIR / "production_labels.csv"
BATCH = 20
DEFAULT_N = 5000

# Tiebreaker for needs_review strings: a third, stronger model breaks 2-of-3
# majorities. Local config (not in gating MODELS -- the two-model experiments
# stay two-model). Opus 5: no sampling params; thinking suppressed under
# forced tool_choice, same as Sonnet 5.
TIEBREAK_CFG = {"id": "claude-opus-5", "max_tokens": 16000, "extra": {}}

# strings already gold-labelled by human adjudication are excluded here --
# their labels come from data/, not from this pipeline
GOLD_FILES = [ROOT / "data" / "gold_merchant_labels.csv", ROOT / "data" / "gold_tail_labels.csv"]


def fetch(n):
    print("Querying unmatched Plaid merchant population...", file=sys.stderr)
    pop = sorted(((r["m"], int(r["n"])) for r in bq_json(POPULATION_QUERY)), key=lambda x: -x[1])
    already_gold = set()
    for gf in GOLD_FILES:
        if gf.exists():
            already_gold |= {r["merchant"].strip().lower() for r in csv.DictReader(open(gf))}
    total_vol = sum(v for _, v in pop)
    chosen = [(m, v) for m, v in pop if m not in already_gold][:n]
    print(f"Selected top {len(chosen)} strings covering "
          f"{sum(v for _, v in chosen) / total_vol:.1%} of unmatched volume "
          f"({len(already_gold & {m for m, _ in pop})} gold-labelled strings excluded)", file=sys.stderr)

    with open(STRINGS_CSV, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["merchant", "plaid_n"])
        w.writerows(chosen)

    def q(s):
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    evidence = []
    CHUNK = 2000  # keep each IN-list query a sane size
    for i in range(0, len(chosen), CHUNK):
        part = chosen[i:i + CHUNK]
        in_list = ", ".join(q(m) for m, _ in part)
        print(f"Evidence chunk {i // CHUNK + 1}/{(len(chosen) + CHUNK - 1) // CHUNK}...", file=sys.stderr)
        evidence += bq_json(f"""
SELECT LOWER(TRIM(merchant_name)) AS m,
       ROUND(COUNTIF(amount < 0) / COUNT(*), 2) AS pct_credit,
       ROUND(APPROX_QUANTILES(ABS(amount), 2)[OFFSET(1)], 2) AS median_amount,
       APPROX_TOP_COUNT(credit_category_detailed, 2) AS cats,
       APPROX_TOP_COUNT(COALESCE(original_description, transaction_name), 3) AS descs
FROM `raylo-production.dbt_production.credit_plaid_open_banking_transactions`
WHERE merchant_name IS NOT NULL AND TRIM(merchant_name) != ''
  AND LOWER(TRIM(merchant_name)) IN ({in_list})
GROUP BY 1
""")
    EVIDENCE_JSON.write_text(json.dumps(evidence))
    print(f"Wrote {STRINGS_CSV} and {EVIDENCE_JSON}", file=sys.stderr)


def load_evidence():
    ev = {}
    for r in json.loads(EVIDENCE_JSON.read_text()):
        ev[r["m"]] = {
            "pct_credit": float(r["pct_credit"]),
            "median_amount": float(r["median_amount"]),
            "cats": " · ".join(f"{c['value']} {int(c['count'])}x" for c in r["cats"][:2]),
            "descs": " | ".join(f"\"{d['value'].strip()[:70]}\"" for d in r["descs"][:3]),
        }
    return ev


def run_labelling(cfg, rows, out_path):
    import anthropic

    _, _, leaves, gen_of, notes_of = load_crosswalk()
    system_prompt = build_system_prompt(leaves, gen_of, notes_of, load_example_merchants()) + TAIL_ADDENDUM
    tool = build_tool_schema(leaves)
    ev = load_evidence()

    # resumable: skip strings already predicted (rerun-safe after interruption)
    predictions = {}
    if out_path.exists():
        predictions = {r["merchant"]: {"leaf": r["llm_leaf"], "conf": r["llm_confidence"]}
                       for r in csv.DictReader(open(out_path)) if r["llm_leaf"]}
        print(f"Resuming: {len(predictions)} already labelled", file=sys.stderr)
    todo = [r for r in rows if r["merchant"] not in predictions]

    client = anthropic.Anthropic()
    n_batches = (len(todo) + BATCH - 1) // BATCH

    def render(i, r):
        e = ev.get(r["merchant"], {})
        return (f"{i}. merchant: {r['merchant']}\n"
                f"   plaid_native_categories: {e.get('cats', 'n/a')}\n"
                f"   pct_credit: {e.get('pct_credit', 'n/a')} | median_amount_gbp: {e.get('median_amount', 'n/a')}\n"
                f"   top_raw_narratives: {e.get('descs', 'n/a')}")

    def flush():
        with open(out_path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["merchant", "llm_leaf", "llm_confidence"])
            w.writeheader()
            for r in rows:
                p = predictions.get(r["merchant"])
                w.writerow({"merchant": r["merchant"],
                            "llm_leaf": p["leaf"] if p else "",
                            "llm_confidence": p["conf"] if p else ""})

    def classify_batch(batch, tag):
        user_msg = "Classify each of these merchant strings using the evidence provided:\n\n" + \
            "\n".join(render(j + 1, r) for j, r in enumerate(batch))
        response = client.messages.create(
            model=cfg["id"], max_tokens=cfg["max_tokens"],
            system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral", "ttl": "1h"}}],
            tools=[tool], tool_choice={"type": "tool", "name": "submit_classifications"},
            messages=[{"role": "user", "content": user_msg}], **cfg["extra"],
        )
        if response.stop_reason == "max_tokens":
            print(f"  WARNING: [{tag}] truncated", file=sys.stderr)
        tool_use = next((b for b in response.content if b.type == "tool_use"), None)
        if tool_use is None:
            return {}
        by_string = {r["merchant"].strip().lower(): r["merchant"] for r in batch}
        got = {}
        for res in tool_use.input.get("results", []):
            idx = res.get("index")
            echoed = (res.get("merchant") or "").strip().lower()
            merchant = None
            if isinstance(idx, int) and 1 <= idx <= len(batch):
                candidate = batch[idx - 1]["merchant"]
                if candidate.strip().lower() == echoed or echoed not in by_string:
                    merchant = candidate
            if merchant is None and echoed in by_string:
                merchant = by_string[echoed]
            if merchant is not None:
                got[merchant] = {"leaf": res.get("detailed_category"), "conf": res.get("confidence")}
        return got

    for i in range(0, len(todo), BATCH):
        batch = todo[i:i + BATCH]
        num = i // BATCH + 1
        if num % 10 == 1:
            print(f"[{cfg['id']}] batch {num}/{n_batches}", file=sys.stderr)
        predictions.update(classify_batch(batch, f"b{num:03d}"))
        for attempt in (1, 2):
            missing = [r for r in batch if r["merchant"] not in predictions]
            if not missing:
                break
            predictions.update(classify_batch(missing, f"b{num:03d}_r{attempt}"))
        if num % 25 == 0:
            flush()  # checkpoint

    flush()
    missing = sum(1 for r in rows if r["merchant"] not in predictions)
    print(f"Wrote {out_path} ({len(predictions)} labelled, {missing} missing)", file=sys.stderr)


def label(model_key):
    rows = list(csv.DictReader(open(STRINGS_CSV)))
    run_labelling(MODELS[model_key], rows, PREDICTIONS[model_key])


def tiebreak():
    """Run the tiebreaker model over the needs_review strings only."""
    labels = list(csv.DictReader(open(LABELS_CSV)))
    rows = [{"merchant": r["merchant"], "plaid_n": r["plaid_n"]}
            for r in labels if r["tier"] == "needs_review"]
    print(f"Tiebreaking {len(rows)} needs_review strings with {TIEBREAK_CFG['id']}", file=sys.stderr)
    run_labelling(TIEBREAK_CFG, rows, OPUS_PREDICTIONS)


def gate():
    _, _, _, gen_of, _ = load_crosswalk()
    rows = list(csv.DictReader(open(STRINGS_CSV)))
    preds = {k: {r["merchant"]: r for r in csv.DictReader(open(PREDICTIONS[k]))} for k in MODELS}

    opus = {}
    if OPUS_PREDICTIONS.exists():
        opus = {r["merchant"]: r for r in csv.DictReader(open(OPUS_PREDICTIONS))}
        print(f"Applying {TIEBREAK_CFG['id']} tiebreak over {len(opus)} strings", file=sys.stderr)

    out, stats = [], {}
    vol = {r["merchant"]: int(r["plaid_n"]) for r in rows}
    for r in rows:
        m = r["merchant"]
        h, s = preds["haiku"].get(m, {}), preds["sonnet"].get(m, {})
        hl, sl = h.get("llm_leaf", ""), s.get("llm_leaf", "")
        sc = float(s["llm_confidence"]) if s.get("llm_confidence") else 0.0
        agree = bool(hl) and hl == sl
        if agree and hl == "unclassified_other":
            tier, leaf = "abstain_confirmed", "unclassified_other"
        elif agree and sc >= 0.9:
            tier, leaf = "auto_accept", sl
        elif agree and sc >= 0.7:
            tier, leaf = "accepted", sl
        else:
            tier, leaf = "needs_review", sl or hl
            # 2-of-3 majority with the tiebreaker model resolves the queue;
            # the tiebreaker must be IN the majority (it never rescues a
            # low-confidence haiku+sonnet pair it disagrees with)
            ol = opus.get(m, {}).get("llm_leaf", "")
            if ol and (ol == sl or ol == hl):
                if ol == "unclassified_other":
                    tier, leaf = "abstain_confirmed", "unclassified_other"
                else:
                    tier, leaf = "accepted_tiebreak", ol
        out.append({"merchant": m, "final_leaf": leaf, "tier": tier,
                    "haiku_leaf": hl, "sonnet_leaf": sl, "sonnet_conf": sc,
                    "opus_leaf": opus.get(m, {}).get("llm_leaf", ""),
                    "general_category": gen_of.get(leaf, ""), "plaid_n": vol[m]})
        stats.setdefault(tier, [0, 0])
        stats[tier][0] += 1
        stats[tier][1] += vol[m]

    with open(LABELS_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(sorted(out, key=lambda x: -x["plaid_n"]))

    total_n = len(out)
    total_v = sum(vol.values())
    print(f"Gated {total_n} strings ({total_v} txns of volume):")
    for tier in ("auto_accept", "accepted", "accepted_tiebreak", "abstain_confirmed", "needs_review"):
        n, v = stats.get(tier, (0, 0))
        print(f"  {tier:18s} {n:6d} strings ({n / total_n:5.1%})   {v:8d} txns ({v / total_v:5.1%} of volume)")
    print(f"Wrote {LABELS_CSV}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] not in {"fetch", "label", "tiebreak", "gate"}:
        sys.exit(__doc__)
    if args[0] == "fetch":
        fetch(int(args[1]) if len(args) > 1 else DEFAULT_N)
    elif args[0] == "label":
        model_key = args[1] if len(args) > 1 else "haiku"
        if model_key not in MODELS:
            sys.exit(f"Unknown model '{model_key}'")
        label(model_key)
    elif args[0] == "tiebreak":
        tiebreak()
    elif args[0] == "gate":
        gate()

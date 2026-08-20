"""Gemini 3.7 Flash as an alternative tiebreaker -- speed/accuracy/cost
comparison against the Opus 5 tiebreak already used in production_labelling.py.

Runs over the SAME needs_review queue Opus is tiebreaking (does not touch
opus's output file or the live gate/apply-review pipeline -- this is purely
a side-by-side comparison experiment).

Usage:
    python src/gemini_tiebreak_experiment.py label     # Gemini over current needs_review queue
    python src/gemini_tiebreak_experiment.py compare   # vs production_predictions_opus.csv
"""
import csv
import json
import pathlib
import sys
import time

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from gating_experiment import ROOT, OUT_DIR, load_crosswalk, build_system_prompt, load_example_merchants  # noqa: E402
from build_tail_eval import TAIL_ADDENDUM  # noqa: E402

GEMINI_MODEL = "gemini-3.7-flash"
GEMINI_PREDICTIONS = OUT_DIR / "production_predictions_gemini_tiebreak.csv"
TIMING_JSON = OUT_DIR / "gemini_vs_opus_timing.json"
BATCH = 20


def get_needs_review():
    rows = list(csv.DictReader(open(OUT_DIR / "production_labels.csv")))
    return [r for r in rows if r["tier"] == "needs_review"]


# KNOWN PLATFORM LIMIT (measured 2026-08-20): Gemini's response_json_schema
# rejects string enums above ~100-150 values with an uninformative 400
# INVALID_ARGUMENT -- bisected: n=100 OK, n=150 FAILED, for this exact
# taxonomy. Claude's tool-use schema enforces the full 275-value enum with
# no issue (used throughout this project). Workaround: number the taxonomy
# in the prompt and constrain the response to a bounded INTEGER (no enum
# keyword, no size cap), then map the index back to a leaf name locally.
# This trades grammar-enforced exact-string validity for a bounds check +
# the model's own adherence to the numbered list -- a real, worth-noting
# reliability difference between the two providers for closed-set tasks
# this large, not a code bug.
def build_leaf_index(leaves):
    return sorted(leaves)


def build_index_addendum(leaf_index):
    lines = ["\n## Taxonomy index (for this request only)",
             "Output `detailed_category_index`, the number below matching your chosen leaf -- NOT the leaf name."]
    lines += [f"{i+1}. {leaf}" for i, leaf in enumerate(leaf_index)]
    return "\n".join(lines)


def build_response_schema(leaf_index):
    return {
        "type": "object",
        "properties": {
            "results": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "index": {"type": "integer"},
                        "merchant": {"type": "string"},
                        "detailed_category_index": {"type": "integer", "minimum": 1, "maximum": len(leaf_index)},
                        "confidence": {"type": "number"},
                    },
                    "required": ["index", "merchant", "detailed_category_index", "confidence"],
                },
            }
        },
        "required": ["results"],
    }


def label():
    from google import genai
    from google.genai import types

    _, _, leaves, gen_of, notes_of = load_crosswalk()
    leaf_index = build_leaf_index(leaves)
    system_prompt = (build_system_prompt(leaves, gen_of, notes_of, load_example_merchants())
                    + TAIL_ADDENDUM + build_index_addendum(leaf_index))
    schema = build_response_schema(leaf_index)

    rows = get_needs_review()
    ev = {}
    evidence_path = OUT_DIR / "production_evidence.json"
    if evidence_path.exists():
        for r in json.loads(evidence_path.read_text()):
            ev[r["m"]] = {
                "pct_credit": r.get("pct_credit"), "median_amount": r.get("median_amount"),
                "cats": " · ".join(f"{c['value']} {int(c['count'])}x" for c in r.get("cats", [])[:2]),
                "descs": " | ".join(f"\"{d['value'].strip()[:70]}\"" for d in r.get("descs", [])[:3]),
            }

    predictions = {}
    if GEMINI_PREDICTIONS.exists():
        predictions = {r["merchant"]: {"leaf": r["llm_leaf"], "conf": r["llm_confidence"]}
                       for r in csv.DictReader(open(GEMINI_PREDICTIONS)) if r["llm_leaf"]}
        print(f"Resuming: {len(predictions)} already labelled", file=sys.stderr)
    todo = [r for r in rows if r["merchant"] not in predictions]

    client = genai.Client()
    n_batches = (len(todo) + BATCH - 1) // BATCH

    def render(i, r):
        e = ev.get(r["merchant"], {})
        return (f"{i}. merchant: {r['merchant']}\n"
                f"   plaid_native_categories: {e.get('cats', 'n/a')}\n"
                f"   pct_credit: {e.get('pct_credit', 'n/a')} | median_amount_gbp: {e.get('median_amount', 'n/a')}\n"
                f"   top_raw_narratives: {e.get('descs', 'n/a')}")

    def flush():
        with open(GEMINI_PREDICTIONS, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["merchant", "llm_leaf", "llm_confidence"])
            w.writeheader()
            seen = set()
            for r in rows:
                seen.add(r["merchant"])
                p = predictions.get(r["merchant"])
                w.writerow({"merchant": r["merchant"],
                            "llm_leaf": p["leaf"] if p else "",
                            "llm_confidence": p["conf"] if p else ""})
            for m, p in predictions.items():
                if m not in seen:
                    w.writerow({"merchant": m, "llm_leaf": p["leaf"], "llm_confidence": p["conf"]})

    def classify_batch(batch, tag, attempt=0):
        user_msg = "Classify each of these merchant strings using the evidence provided:\n\n" + \
            "\n".join(render(j + 1, r) for j, r in enumerate(batch))
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=system_prompt + "\n\n" + user_msg,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_json_schema=schema,
                ),
            )
        except Exception as e:
            if attempt < 2:
                print(f"  [{tag}] error ({e}), retrying...", file=sys.stderr)
                time.sleep(2 ** attempt)
                return classify_batch(batch, tag, attempt + 1)
            print(f"  [{tag}] FAILED after retries: {e}", file=sys.stderr)
            return {}
        try:
            parsed = json.loads(response.text)
        except (json.JSONDecodeError, TypeError):
            print(f"  [{tag}] WARNING: non-JSON response, skipping batch", file=sys.stderr)
            return {}
        by_string = {r["merchant"].strip().lower(): r["merchant"] for r in batch}
        out = {}
        for res in parsed.get("results", []):
            idx = res.get("index")
            echoed = (res.get("merchant") or "").strip().lower()
            merchant = None
            if isinstance(idx, int) and 1 <= idx <= len(batch):
                candidate = batch[idx - 1]["merchant"]
                if candidate.strip().lower() == echoed or echoed not in by_string:
                    merchant = candidate
            if merchant is None and echoed in by_string:
                merchant = by_string[echoed]
            if merchant is None:
                continue
            leaf_idx = res.get("detailed_category_index")
            if not (isinstance(leaf_idx, int) and 1 <= leaf_idx <= len(leaf_index)):
                continue  # out-of-range index -- drop, gets retried like a missing merchant
            out[merchant] = {"leaf": leaf_index[leaf_idx - 1], "conf": res.get("confidence")}
        return out

    t0 = time.monotonic()
    for i in range(0, len(todo), BATCH):
        batch = todo[i:i + BATCH]
        num = i // BATCH + 1
        if num % 20 == 1:
            print(f"[{GEMINI_MODEL}] batch {num}/{n_batches}", file=sys.stderr)
        predictions.update(classify_batch(batch, f"b{num:04d}"))
        for attempt in (1, 2):
            missing = [r for r in batch if r["merchant"] not in predictions]
            if not missing:
                break
            predictions.update(classify_batch(missing, f"b{num:04d}_r{attempt}"))
        if num % 25 == 0:
            flush()
    elapsed = time.monotonic() - t0

    flush()
    missing = sum(1 for r in rows if r["merchant"] not in predictions)
    print(f"Wrote {GEMINI_PREDICTIONS} ({len(predictions)} labelled, {missing} missing) "
          f"in {elapsed:.0f}s ({len(todo) / elapsed:.1f} strings/sec)", file=sys.stderr)

    timing = {}
    if TIMING_JSON.exists():
        timing = json.loads(TIMING_JSON.read_text())
    timing["gemini"] = {"strings": len(todo), "elapsed_sec": elapsed,
                        "strings_per_sec": len(todo) / elapsed if elapsed else 0}
    TIMING_JSON.write_text(json.dumps(timing, indent=2))


def compare():
    _, _, _, gen_of, _ = load_crosswalk()
    nr = {r["merchant"] for r in get_needs_review()}
    opus = {r["merchant"]: r["llm_leaf"] for r in csv.DictReader(open(OUT_DIR / "production_predictions_opus.csv"))
            if r["merchant"] in nr and r["llm_leaf"]}
    gemini = {r["merchant"]: r["llm_leaf"] for r in csv.DictReader(open(GEMINI_PREDICTIONS))
              if r["merchant"] in nr and r["llm_leaf"]}
    both = sorted(set(opus) & set(gemini))
    print(f"Both models labelled: {len(both)} / {len(nr)} needs_review strings")

    agree = [m for m in both if opus[m] == gemini[m]]
    print(f"Leaf agreement: {len(agree)}/{len(both)} ({len(agree)/len(both):.1%})")
    gen_agree = [m for m in both if gen_of.get(opus[m]) == gen_of.get(gemini[m])]
    print(f"General-category agreement: {len(gen_agree)}/{len(both)} ({len(gen_agree)/len(both):.1%})")

    disagree = [m for m in both if m not in agree]
    print(f"\nSample disagreements (up to 15):")
    for m in disagree[:15]:
        print(f"  {m}: opus={opus[m]}  gemini={gemini[m]}")

    if TIMING_JSON.exists():
        timing = json.loads(TIMING_JSON.read_text())
        print(f"\nTiming: {json.dumps(timing, indent=2)}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] not in {"label", "compare"}:
        sys.exit(__doc__)
    if args[0] == "label":
        label()
    elif args[0] == "compare":
        compare()

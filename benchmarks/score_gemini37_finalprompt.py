"""Re-score Gemini 3.7 Flash (untuned) with the FINALIZED standard prompt
(taxonomy + loan-keyword bugfix + full 375 worked examples) -- the original
score_llm_taxonomy.py run used a simpler standalone prompt (taxonomy + a
generic task block only, no examples) built BEFORE today's prompt work, so
Gemini 3.7 Flash never got the same test Haiku/Sonnet/Opus did. Same
enum-index-workaround as before (Gemini's response_schema rejects string
enums above ~100-150 values) and same 1,055-row gold set.
"""
import csv
import pathlib
import sys
import time

from dotenv import load_dotenv

load_dotenv()

ROOT = pathlib.Path("/Users/carlosnoblejesus/Repos/raylo-transaction-categorisation")
sys.path.insert(0, str(ROOT / "src"))
from gating_experiment import load_crosswalk, load_example_merchants, load_example_notes, build_system_prompt, build_notes_addendum  # noqa: E402
from build_tail_eval import TAIL_ADDENDUM  # noqa: E402

GOLD_CSV = ROOT / "data/gold_v2_slm_eval_holdout.csv"
MODEL_ID = "gemini-3.7-flash"
BATCH = 25
MAX_RETRIES = 3
OUT_CSV = ROOT / "outputs/mlx_full_run/gemini37_finalprompt_predictions.csv"

_, _, leaves, gen_of, notes_of = load_crosswalk()
leaf_to_general = dict(gen_of)
leaf_list = sorted(leaves) + ["unclassified_other"]

SYSTEM_PROMPT = (build_system_prompt(leaves, gen_of, notes_of, load_example_merchants())
                  + TAIL_ADDENDUM + build_notes_addendum(load_example_notes()))
print(f"[gemini3.7][finalprompt] system prompt: {len(SYSTEM_PROMPT)} chars", file=sys.stderr)

rows = list(csv.DictReader(open(GOLD_CSV)))


def txn_text(i, r):
    merchant = r["merchant_raw"].strip().lower()
    return (f"{i}. merchant: {merchant} | description: {r['description_raw']} | "
            f"amount: {r['amount']} | direction: {r['direction'].strip().lower()}")


import os

from google import genai
from google.genai import types
# Explicit api_key + vertexai=False forces the direct Gemini Developer API --
# a bare genai.Client() still resolved to Vertex mode here (ADC quota-project
# config from earlier this session apparently outranks GOOGLE_API_KEY), and
# Gemini 3.7 Flash isn't available via Vertex AI in this project/region.
client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"], vertexai=False)


def score_batch(batch, tag):
    schema = {
        "type": "object",
        "properties": {
            "results": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "index": {"type": "integer"},
                        "category_index": {"type": "integer", "minimum": 1, "maximum": len(leaf_list)},
                    },
                    "required": ["index", "category_index"],
                },
            }
        },
        "required": ["results"],
    }
    index_addendum = "\n\n## Category index (output this number, not the name)\n" + "\n".join(
        f"{i+1}. {leaf}" for i, leaf in enumerate(leaf_list))
    user_msg = "Classify each transaction:\n" + "\n".join(txn_text(i + 1, r) for i, r in enumerate(batch))
    resp = client.models.generate_content(
        model=MODEL_ID, contents=user_msg,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT + index_addendum,
            response_mime_type="application/json", response_schema=schema, temperature=0.0,
        ),
    )
    import json
    try:
        data = json.loads(resp.text)
    except Exception as e:
        print(f"[gemini3.7] [{tag}] JSON parse failed: {e}", file=sys.stderr)
        return {}
    out = {}
    for r in data.get("results", []):
        idx, cat_idx = r.get("index"), r.get("category_index")
        if isinstance(idx, int) and isinstance(cat_idx, int) and 1 <= cat_idx <= len(leaf_list):
            out[idx] = leaf_list[cat_idx - 1]
    return out


predictions = {}
start = time.monotonic()
n_batches = (len(rows) + BATCH - 1) // BATCH
for b in range(n_batches):
    batch = rows[b * BATCH:(b + 1) * BATCH]
    to_do = list(range(len(batch)))
    got = {}
    for attempt in range(MAX_RETRIES):
        sub_batch = [batch[i] for i in to_do]
        try:
            result = score_batch(sub_batch, f"batch{b}try{attempt}")
        except Exception as e:
            print(f"[gemini3.7] batch {b} attempt {attempt} exception: {e}", file=sys.stderr)
            time.sleep(2 * (attempt + 1))
            continue
        for local_idx, leaf in result.items():
            orig_idx = to_do[local_idx - 1] if 1 <= local_idx <= len(to_do) else None
            if orig_idx is not None:
                got[orig_idx] = leaf
        to_do = [i for i in to_do if i not in got]
        if not to_do:
            break
    for i in to_do:
        got[i] = "unclassified_other"
    for local_i, leaf in got.items():
        predictions[b * BATCH + local_i] = leaf
    done = min((b + 1) * BATCH, len(rows))
    if done % 100 < BATCH or b == n_batches - 1:
        elapsed = time.monotonic() - start
        print(f"[gemini3.7] {done}/{len(rows)} done in {elapsed:.0f}s ({done/elapsed:.2f} rows/sec)", file=sys.stderr)

total_elapsed = time.monotonic() - start
results = []
for i, r in enumerate(rows):
    pred = predictions.get(i, "unclassified_other")
    gold_leaf = r["gold_leaf"].strip()
    leaf_correct = pred == gold_leaf
    pred_general = leaf_to_general.get(pred)
    gold_general = leaf_to_general.get(gold_leaf)
    general_correct = pred_general is not None and pred_general == gold_general
    results.append({**r, "pred_leaf": pred, "leaf_correct": leaf_correct,
                     "pred_general": pred_general, "gold_general": gold_general,
                     "general_correct": general_correct})

n = len(results)
leaf_acc = sum(r["leaf_correct"] for r in results) / n
general_acc = sum(r["general_correct"] for r in results) / n

print(f"\n[gemini3.7][finalprompt] === RESULTS ({n} rows) ===")
print(f"[gemini3.7][finalprompt] Leaf accuracy:    {leaf_acc:.1%}")
print(f"[gemini3.7][finalprompt] General accuracy: {general_acc:.1%}")
print(f"[gemini3.7][finalprompt] Total time: {total_elapsed:.0f}s ({total_elapsed/60:.1f} min) = {n/total_elapsed:.2f} rows/sec")

with open(OUT_CSV, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
    w.writeheader()
    w.writerows(results)
print(f"[gemini3.7][finalprompt] Per-row predictions written to {OUT_CSV}")

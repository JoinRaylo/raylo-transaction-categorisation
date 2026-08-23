"""Score a frontier LLM against data/gold_transactions_v4_slm_volume.csv --
the 900-row volume-weighted gold set over the unmatched-Plaid population
(what the LLM tier actually sees in production). Identical harness to the
v2-holdout benchmark: the finalized standard prompt (taxonomy + loan-keyword
bugfix + full 375 worked examples), batch-of-25, forced structured output.

Also reports a leakage split: rows whose merchant string appears verbatim in
the prompt's worked examples (example merchants or dictionary notes) vs not,
since v4 is a random population sample, NOT merchant-disjoint from the prompt
the way gold_v2_slm_eval_holdout was constructed to be.

Usage: python score_v4.py {haiku,sonnet,opus,gemini}
"""
import csv
import pathlib
import sys
import time

from dotenv import load_dotenv

load_dotenv()

ROOT = pathlib.Path("/Users/carlosnoblejesus/Repos/raylo-transaction-categorisation")
sys.path.insert(0, str(ROOT / "src"))
from gating_experiment import (  # noqa: E402
    load_crosswalk, load_example_merchants, load_example_notes,
    build_system_prompt, build_notes_addendum,
)
from build_tail_eval import TAIL_ADDENDUM  # noqa: E402

GOLD_CSV = ROOT / "data/gold_transactions_v4_slm_volume.csv"
MODEL_IDS = {
    "haiku": "claude-haiku-4-5",
    "sonnet": "claude-sonnet-5",
    "opus": "claude-opus-5",
    "gemini": "gemini-3.7-flash",
}
BATCH = 25
MAX_RETRIES = 3

backend = sys.argv[1] if len(sys.argv) > 1 else sys.exit(f"usage: {sys.argv[0]} {{{','.join(MODEL_IDS)}}}")
if backend not in MODEL_IDS:
    sys.exit(f"unknown backend {backend!r}")
OUT_CSV = ROOT / f"outputs/mlx_full_run/v4_{backend}_predictions.csv"
LOG = f"[v4:{backend}]"

_, _, leaves, gen_of, notes_of = load_crosswalk()
examples_of = load_example_merchants()
example_notes = load_example_notes()
leaf_to_general = dict(gen_of)
leaf_list = sorted(leaves) + ["unclassified_other"]

SYSTEM_PROMPT = (build_system_prompt(leaves, gen_of, notes_of, examples_of)
                 + TAIL_ADDENDUM + build_notes_addendum(example_notes))
print(f"{LOG} system prompt: {len(SYSTEM_PROMPT)} chars", file=sys.stderr)

# Merchants the prompt itself mentions verbatim (for the leakage split).
prompt_merchants = {m.strip().lower() for ms in examples_of.values() for m in ms}
prompt_merchants |= {m.strip().lower() for m, _, _ in example_notes}

rows = list(csv.DictReader(open(GOLD_CSV)))


def txn_text(i, r):
    merchant = r["merchant_raw"].strip().lower()
    return (f"{i}. merchant: {merchant} | description: {r['description_raw']} | "
            f"amount: {r['amount']} | direction: {r['direction'].strip().lower()}")


def score_batch_anthropic(client, batch, tag):
    tool = {
        "name": "submit_classifications",
        "description": "Submit categories for a batch of transactions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "results": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "index": {"type": "integer"},
                            "detailed_category": {"type": "string", "enum": leaf_list},
                        },
                        "required": ["index", "detailed_category"],
                    },
                }
            },
            "required": ["results"],
        },
    }
    user_msg = "Classify each transaction:\n" + "\n".join(txn_text(i + 1, r) for i, r in enumerate(batch))
    resp = client.messages.create(
        model=MODEL_IDS[backend], max_tokens=4000, system=SYSTEM_PROMPT,
        tools=[tool], tool_choice={"type": "tool", "name": "submit_classifications"},
        messages=[{"role": "user", "content": user_msg}],
        timeout=120.0,
    )
    tool_use = next((b for b in resp.content if b.type == "tool_use"), None)
    if tool_use is None:
        print(f"{LOG} [{tag}] no tool_use, stop_reason={resp.stop_reason}", file=sys.stderr)
        return {}
    return {r["index"]: r["detailed_category"] for r in tool_use.input.get("results", [])
            if isinstance(r.get("index"), int)}


def score_batch_gemini(client, batch, tag):
    import json

    from google.genai import types
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
        model=MODEL_IDS[backend], contents=user_msg,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT + index_addendum,
            response_mime_type="application/json", response_schema=schema, temperature=0.0,
        ),
    )
    try:
        data = json.loads(resp.text)
    except Exception as e:
        print(f"{LOG} [{tag}] JSON parse failed: {e}", file=sys.stderr)
        return {}
    out = {}
    for r in data.get("results", []):
        idx, cat_idx = r.get("index"), r.get("category_index")
        if isinstance(idx, int) and isinstance(cat_idx, int) and 1 <= cat_idx <= len(leaf_list):
            out[idx] = leaf_list[cat_idx - 1]
    return out


if backend == "gemini":
    import os

    from google import genai
    # Explicit api_key + vertexai=False: Gemini 3.7 Flash is Developer-API-only
    # in this project/region (see score_gemini37_finalprompt.py).
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"], vertexai=False)
    score_batch = score_batch_gemini
else:
    import anthropic
    client = anthropic.Anthropic()
    score_batch = score_batch_anthropic

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
            result = score_batch(client, sub_batch, f"batch{b}try{attempt}")
        except Exception as e:
            print(f"{LOG} batch {b} attempt {attempt} exception: {e}", file=sys.stderr)
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
    elapsed = time.monotonic() - start
    if done % 100 < BATCH or b == n_batches - 1:
        print(f"{LOG} {done}/{len(rows)} done in {elapsed:.0f}s ({done/elapsed:.2f} rows/sec)", file=sys.stderr)

total_elapsed = time.monotonic() - start
results = []
for i, r in enumerate(rows):
    pred = predictions.get(i, "unclassified_other")
    gold_leaf = r["gold_leaf"].strip()
    leaf_correct = pred == gold_leaf
    pred_general = leaf_to_general.get(pred)
    gold_general = leaf_to_general.get(gold_leaf)
    general_correct = pred_general is not None and pred_general == gold_general
    in_prompt = r["merchant_raw"].strip().lower() in prompt_merchants
    results.append({**r, "pred_leaf": pred, "leaf_correct": leaf_correct,
                    "pred_general": pred_general, "gold_general": gold_general,
                    "general_correct": general_correct, "merchant_in_prompt": in_prompt})


def acc(subset):
    n = len(subset)
    if n == 0:
        return "n=0"
    la = sum(r["leaf_correct"] for r in subset) / n
    ga = sum(r["general_correct"] for r in subset) / n
    return f"leaf {la:.1%} / general {ga:.1%} (n={n})"


leaked = [r for r in results if r["merchant_in_prompt"]]
clean = [r for r in results if not r["merchant_in_prompt"]]

print(f"\n{LOG} === RESULTS gold_v4 (900-row volume-weighted, unmatched-Plaid) ===")
print(f"{LOG} Overall:                 {acc(results)}")
print(f"{LOG} Merchant-in-prompt rows: {acc(leaked)}")
print(f"{LOG} Prompt-clean rows:       {acc(clean)}")
print(f"{LOG} Total time: {total_elapsed:.0f}s ({total_elapsed/60:.1f} min) = {len(results)/total_elapsed:.2f} rows/sec")

with open(OUT_CSV, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
    w.writeheader()
    w.writerows(results)
print(f"{LOG} Per-row predictions written to {OUT_CSV}")

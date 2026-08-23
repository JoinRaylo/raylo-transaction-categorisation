"""Score a frontier LLM against the 1,055-row gold_v2_slm_eval_holdout.csv,
this time giving the model the REAL taxonomy (all 275 leaves + descriptions/
examples) and enforcing output to exactly one valid leaf -- matching how
this project uses LLMs everywhere else (gating_experiment.py,
production_labelling.py). A first pass with a bare/format-hint-only prompt
scored near-zero across every model because none of them knew our specific
275-leaf vocabulary; this is the real, representative comparison.

Anthropic models: forced tool-call, enum-constrained to the real leaf set.
Gemini: enum constraints above ~100-150 values are rejected by the API
(known platform limit, see src/gemini_tiebreak_experiment.py) -- uses the
documented workaround instead: a numbered taxonomy index in the prompt +
a bounded-integer response field, mapped back to the leaf name locally.

Usage: python score_llm_taxonomy.py {haiku,sonnet,opus,gemini}
"""
import csv
import pathlib
import sys
import time
from collections import defaultdict

from dotenv import load_dotenv

load_dotenv()

ROOT = pathlib.Path("/Users/carlosnoblejesus/Repos/raylo-transaction-categorisation")
sys.path.insert(0, str(ROOT / "src"))
from gating_experiment import load_crosswalk, load_example_merchants  # noqa: E402

GOLD_CSV = ROOT / "data/gold_v2_slm_eval_holdout.csv"
MODEL_IDS = {
    "haiku": "claude-haiku-4-5",
    "sonnet": "claude-sonnet-5",
    "opus": "claude-opus-5",
    "gemini": "gemini-3.7-flash",
    "sonnet46": "claude-sonnet-4-6",
    "opus48": "claude-opus-4-8",
}
BATCH = 25
MAX_RETRIES = 3

backend = sys.argv[1] if len(sys.argv) > 1 else sys.exit(f"usage: {sys.argv[0]} {{{','.join(MODEL_IDS)}}} [temperature] [run_tag]")
if backend not in MODEL_IDS:
    sys.exit(f"unknown backend {backend!r}")
# Anthropic's API default temperature is 1.0 (real sampling) unless set
# explicitly; pass a temperature arg (e.g. 0) for a deterministic run.
TEMPERATURE = float(sys.argv[2]) if len(sys.argv) > 2 else None
RUN_TAG = sys.argv[3] if len(sys.argv) > 3 else ""
OUT_CSV = ROOT / f"outputs/mlx_full_run/llm_taxonomy_{backend}{RUN_TAG}_predictions.csv"
LOG = f"[{backend}]" + (f"[temp={TEMPERATURE}]" if TEMPERATURE is not None else "[temp=default]")

_, _, leaves, gen_of, notes_of = load_crosswalk()
examples_of = load_example_merchants()
leaf_list = sorted(leaves) + ["unclassified_other"]


def build_taxonomy_block():
    by_gen = defaultdict(list)
    for leaf in leaves:
        by_gen[gen_of[leaf]].append(leaf)
    lines = ["## Taxonomy (the complete, closed set of valid categories)",
             "Format per line: `leaf_name` -- [note] (e.g. example merchants)"]
    for gen in sorted(by_gen):
        lines.append(f"\n### {gen}")
        for leaf in sorted(by_gen[gen]):
            note = notes_of.get(leaf, "")
            examples = examples_of.get(leaf, [])
            extra = []
            if note:
                extra.append(note)
            if examples:
                extra.append("e.g. " + ", ".join(examples[:4]))
            suffix = f" -- {'; '.join(extra)}" if extra else ""
            lines.append(f"- `{leaf}`{suffix}")
    lines.append(
        "\n- `unclassified_other` -- use when genuinely ambiguous or unidentifiable; "
        "abstaining is preferred over a low-confidence guess."
    )
    return "\n".join(lines)


TAXONOMY_BLOCK = build_taxonomy_block()
TASK_BLOCK = """
## Task
You categorise UK bank transactions for a consumer credit lender. For each transaction you are
given: merchant (counterparty name), description (raw bank narrative), amount (absolute value,
GBP), and direction (debit = money out / spending; credit = money in / income or refund). Choose
exactly one category from the taxonomy above -- never invent a category outside this list.
Some categories look similar but are deliberately kept separate because they carry different
credit-risk signal -- most importantly the gambling subtypes, which must never be merged.
Return EXACTLY one result per input transaction, in the same order, echoing the input's number
as `index`.
"""
SYSTEM_PROMPT = TAXONOMY_BLOCK + "\n" + TASK_BLOCK

rows = list(csv.DictReader(open(GOLD_CSV)))
leaf_to_general = dict(gen_of)


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
    extra = {"temperature": TEMPERATURE} if TEMPERATURE is not None else {}
    resp = client.messages.create(
        model=MODEL_IDS[backend], max_tokens=4000, system=SYSTEM_PROMPT,
        tools=[tool], tool_choice={"type": "tool", "name": "submit_classifications"},
        messages=[{"role": "user", "content": user_msg}],
        **extra,
    )
    tool_use = next((b for b in resp.content if b.type == "tool_use"), None)
    if tool_use is None:
        print(f"{LOG} [{tag}] no tool_use, stop_reason={resp.stop_reason}", file=sys.stderr)
        return {}
    return {r["index"]: r["detailed_category"] for r in tool_use.input.get("results", [])
            if isinstance(r.get("index"), int)}


def score_batch_gemini(client, batch, tag):
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
    import json
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
    from google import genai
    client = genai.Client()
    score_batch = score_batch_gemini
else:
    import anthropic
    client = anthropic.Anthropic()
    score_batch = score_batch_anthropic

predictions = {}  # row-index (0-based) -> leaf
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
        # result keys are 1-based positions WITHIN sub_batch
        for local_idx, leaf in result.items():
            orig_idx = to_do[local_idx - 1] if 1 <= local_idx <= len(to_do) else None
            if orig_idx is not None:
                got[orig_idx] = leaf
        to_do = [i for i in to_do if i not in got]
        if not to_do:
            break
    for i in to_do:
        got[i] = "unclassified_other"  # exhausted retries -- treat as abstain, not silent drop
    for local_i, leaf in got.items():
        predictions[b * BATCH + local_i] = leaf
    done = min((b + 1) * BATCH, len(rows))
    if done % 100 < BATCH or b == n_batches - 1:
        elapsed = time.monotonic() - start
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
    results.append({**r, "pred_leaf": pred, "leaf_correct": leaf_correct,
                     "pred_general": pred_general, "gold_general": gold_general,
                     "general_correct": general_correct})

n = len(results)
leaf_acc = sum(r["leaf_correct"] for r in results) / n
general_acc = sum(r["general_correct"] for r in results) / n

print(f"\n{LOG} === RESULTS ({n} rows, full taxonomy + enforced output) ===")
print(f"{LOG} Leaf accuracy:    {leaf_acc:.1%}")
print(f"{LOG} General accuracy: {general_acc:.1%}")
print(f"{LOG} Total time: {total_elapsed:.0f}s ({total_elapsed/60:.1f} min) = {n/total_elapsed:.2f} rows/sec")

with open(OUT_CSV, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
    w.writeheader()
    w.writerows(results)
print(f"{LOG} Per-row predictions written to {OUT_CSV}")

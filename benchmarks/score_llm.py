"""Score a frontier LLM against the SAME 1,055-row gold_v2_slm_eval_holdout.csv,
using the EXACT same system prompt + user-message format as the local SLM eval
(benchmarks/tuning_system_prompt.txt, no taxonomy list, no schema/tool-call) --
plain free-text generation, exact-string-matched -- so the comparison to the
vanilla and fine-tuned local model is genuinely apples-to-apples, not helped
along by giving the LLM more grounding than the SLM had.

Usage: python score_llm.py {haiku,sonnet,opus,gemini}
"""
import csv
import pathlib
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv

load_dotenv()

ROOT = pathlib.Path("/Users/carlosnoblejesus/Repos/raylo-transaction-categorisation")
# NOTE: uses the format-hint variant, not the SLM's bare training prompt --
# a first pass (all 4 models) scored 0.0% because every model, given zero
# hint about our lowercase_snake_case leaf naming convention, answered in
# natural Title Case ("Groceries", not "groceries"). The fine-tuned SLM
# never needed this hint because it learned the convention from training
# data; these frontier/vanilla models were never shown it at all. This one
# extra line levels that specific gap without leaking any taxonomy content
# beyond two example leaf names.
SYSTEM_PROMPT = (ROOT / "benchmarks" / "system_prompt_llm_compare.txt").read_text()
GOLD_CSV = ROOT / "data/gold_v2_slm_eval_holdout.csv"
TAXONOMY_CSV = ROOT / "taxonomy/taxonomy.csv"

MODEL_IDS = {
    "haiku": "claude-haiku-4-5",
    "sonnet": "claude-sonnet-5",
    "opus": "claude-opus-5",
    "gemini": "gemini-3.7-flash",
}
CONCURRENCY = 8
MAX_RETRIES = 3

backend = sys.argv[1] if len(sys.argv) > 1 else sys.exit(f"usage: {sys.argv[0]} {{{','.join(MODEL_IDS)}}}")
if backend not in MODEL_IDS:
    sys.exit(f"unknown backend {backend!r}, choose one of {list(MODEL_IDS)}")

OUT_CSV = ROOT / f"outputs/mlx_full_run/llm_{backend}_predictions.csv"
LOG_TAG = f"[{backend}]"

leaf_to_general = {}
with open(TAXONOMY_CSV) as f:
    for row in csv.DictReader(f):
        leaf_to_general[row["detailed_category"]] = row["general_category"]

rows = list(csv.DictReader(open(GOLD_CSV)))


def user_msg_for(r):
    merchant = r["merchant_raw"].strip().lower()
    return (f"merchant: {merchant}\n"
            f"description: {r['description_raw']}\n"
            f"amount: {r['amount']}\n"
            f"direction: {r['direction'].strip().lower()}")


if backend == "gemini":
    from google import genai
    from google.genai import types
    client = genai.Client()

    def call(user_msg):
        resp = client.models.generate_content(
            model=MODEL_IDS[backend],
            contents=user_msg,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT, max_output_tokens=20, temperature=0.0,
            ),
        )
        return (resp.text or "").strip()
else:
    import anthropic
    client = anthropic.Anthropic()

    def call(user_msg):
        resp = client.messages.create(
            model=MODEL_IDS[backend],
            max_tokens=20,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        return "".join(b.text for b in resp.content if b.type == "text").strip()


def score_row(i, r):
    user_msg = user_msg_for(r)
    pred = ""
    for attempt in range(MAX_RETRIES):
        try:
            pred = call(user_msg).split("\n")[0].strip()
            break
        except Exception as e:
            print(f"{LOG_TAG} row {i} attempt {attempt+1} failed: {e}", file=sys.stderr)
            time.sleep(2 * (attempt + 1))
    gold_leaf = r["gold_leaf"].strip()
    leaf_correct = pred == gold_leaf
    pred_general = leaf_to_general.get(pred)
    gold_general = leaf_to_general.get(gold_leaf)
    general_correct = pred_general is not None and pred_general == gold_general
    return {**r, "pred_leaf": pred, "leaf_correct": leaf_correct,
            "pred_general": pred_general, "gold_general": gold_general,
            "general_correct": general_correct}


print(f"{LOG_TAG} scoring {len(rows)} rows with {CONCURRENCY} concurrent workers...", file=sys.stderr)
start = time.monotonic()
results = [None] * len(rows)
done = 0
with ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
    futures = {ex.submit(score_row, i, r): i for i, r in enumerate(rows)}
    for fut in as_completed(futures):
        i = futures[fut]
        results[i] = fut.result()
        done += 1
        if done % 100 == 0:
            elapsed = time.monotonic() - start
            acc_so_far = sum(r["leaf_correct"] for r in results if r) / done
            print(f"{LOG_TAG} {done}/{len(rows)} done in {elapsed:.0f}s "
                  f"({done/elapsed:.2f} rows/sec), running leaf accuracy {acc_so_far:.1%}", file=sys.stderr)

total_elapsed = time.monotonic() - start
n = len(results)
leaf_acc = sum(r["leaf_correct"] for r in results) / n
general_acc = sum(r["general_correct"] for r in results) / n
in_vocab = sum(1 for r in results if r["pred_leaf"] in leaf_to_general or r["pred_leaf"] == "unclassified_other") / n

print(f"\n{LOG_TAG} === RESULTS ({n} rows) ===")
print(f"{LOG_TAG} Leaf accuracy:    {leaf_acc:.1%}")
print(f"{LOG_TAG} General accuracy: {general_acc:.1%}")
print(f"{LOG_TAG} In-taxonomy-vocab output rate: {in_vocab:.1%}")
print(f"{LOG_TAG} Total time: {total_elapsed:.0f}s ({total_elapsed/60:.1f} min) for {n} rows "
      f"= {n/total_elapsed:.2f} rows/sec (with {CONCURRENCY}x concurrency)")

with open(OUT_CSV, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
    w.writeheader()
    w.writerows(results)
print(f"{LOG_TAG} Per-row predictions written to {OUT_CSV}")

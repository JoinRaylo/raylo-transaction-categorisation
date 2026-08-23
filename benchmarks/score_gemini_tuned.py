"""Score the fully-tuned Gemini 2.5 Flash endpoint against the standard
1,055-row gold_v2_slm_eval_holdout.csv, same methodology as every other
model this session (plain-text generation, exact-match scoring). No
response_schema -- per Google's own documented caveat, applying controlled
generation at inference on a tuned model can degrade quality; thinking is
disabled (thinking_budget=0) since it burns the output budget on a task
this simple, confirmed empirically during the smoke test.
"""
import csv
import pathlib
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from google import genai
from google.genai import types

ROOT = pathlib.Path("/Users/carlosnoblejesus/Repos/raylo-transaction-categorisation")
ENDPOINT = "projects/601576302267/locations/europe-west4/endpoints/2220430746944798720"
SYSTEM_PROMPT = (ROOT / "benchmarks" / "tuning_system_prompt.txt").read_text()
GOLD_CSV = ROOT / "data/gold_v2_slm_eval_holdout.csv"
TAXONOMY_CSV = ROOT / "taxonomy/taxonomy.csv"
OUT_CSV = ROOT / "outputs/mlx_full_run/gemini_tuned_predictions.csv"
CONCURRENCY = 8
MAX_RETRIES = 3

leaf_to_general = {}
with open(TAXONOMY_CSV) as f:
    for row in csv.DictReader(f):
        leaf_to_general[row["detailed_category"]] = row["general_category"]

rows = list(csv.DictReader(open(GOLD_CSV)))
client = genai.Client(vertexai=True, project="raylo-production", location="europe-west4")


def call(user_msg):
    resp = client.models.generate_content(
        model=ENDPOINT, contents=user_msg,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT, max_output_tokens=50, temperature=0.0,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    return (resp.text or "").strip()


def score_row(i, r):
    merchant = r["merchant_raw"].strip().lower()
    user_msg = (f"merchant: {merchant}\n"
                f"description: {r['description_raw']}\n"
                f"amount: {r['amount']}\n"
                f"direction: {r['direction'].strip().lower()}")
    pred = ""
    for attempt in range(MAX_RETRIES):
        try:
            pred = call(user_msg).split("\n")[0].strip()
            break
        except Exception as e:
            print(f"row {i} attempt {attempt+1} failed: {e}", file=sys.stderr)
            time.sleep(2 * (attempt + 1))
    gold_leaf = r["gold_leaf"].strip()
    leaf_correct = pred == gold_leaf
    pred_general = leaf_to_general.get(pred)
    gold_general = leaf_to_general.get(gold_leaf)
    general_correct = pred_general is not None and pred_general == gold_general
    return {**r, "pred_leaf": pred, "leaf_correct": leaf_correct,
            "pred_general": pred_general, "gold_general": gold_general,
            "general_correct": general_correct}


print(f"Scoring {len(rows)} rows against the tuned Gemini endpoint, {CONCURRENCY}x concurrency...", file=sys.stderr)
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
            print(f"{done}/{len(rows)} done in {elapsed:.0f}s ({done/elapsed:.2f} rows/sec), "
                  f"running leaf accuracy {acc_so_far:.1%}", file=sys.stderr)

total_elapsed = time.monotonic() - start
n = len(results)
leaf_acc = sum(r["leaf_correct"] for r in results) / n
general_acc = sum(r["general_correct"] for r in results) / n
in_vocab = sum(1 for r in results if r["pred_leaf"] in leaf_to_general or r["pred_leaf"] == "unclassified_other") / n

print(f"\n=== TUNED GEMINI 2.5 FLASH RESULTS ({n} rows) ===")
print(f"Leaf accuracy:    {leaf_acc:.1%}")
print(f"General accuracy: {general_acc:.1%}")
print(f"In-taxonomy-vocab output rate: {in_vocab:.1%}")
print(f"Total time: {total_elapsed:.0f}s ({total_elapsed/60:.1f} min) = {n/total_elapsed:.2f} rows/sec")

with open(OUT_CSV, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
    w.writeheader()
    w.writerows(results)
print(f"Per-row predictions written to {OUT_CSV}")

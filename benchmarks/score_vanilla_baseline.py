"""Score the VANILLA (no LoRA adapter) Gemma 3 4B text-only model against
the same 1,055-row gold_v2_slm_eval_holdout.csv, to measure fine-tuning
uplift. Also times the full pass to report real inference throughput.
"""
import csv
import pathlib
import sys
import time

from mlx_lm import load, generate

ROOT = pathlib.Path("/Users/carlosnoblejesus/Repos/raylo-transaction-categorisation")
MODEL = "mlx-community/gemma-3-text-4b-it-4bit"
# format-hint variant (see score_llm.py's comment) -- the original bare
# prompt scored a guaranteed 0.0% because vanilla Gemma was never shown our
# lowercase_snake_case leaf naming convention, so this reruns with the same
# one-line hint given to the LLM comparison runs, for a fair baseline.
SYSTEM_PROMPT = (ROOT / "benchmarks" / "system_prompt_llm_compare.txt").read_text()
GOLD_CSV = ROOT / "data/gold_v2_slm_eval_holdout.csv"
TAXONOMY_CSV = ROOT / "taxonomy/taxonomy.csv"
OUT_CSV = ROOT / "outputs/mlx_full_run/vanilla_baseline_hint_predictions.csv"

leaf_to_general = {}
with open(TAXONOMY_CSV) as f:
    for row in csv.DictReader(f):
        leaf_to_general[row["detailed_category"]] = row["general_category"]

print("Loading VANILLA model (no adapter)...", file=sys.stderr)
model, tokenizer = load(MODEL)  # no adapter_path

rows = list(csv.DictReader(open(GOLD_CSV)))
print(f"Scoring {len(rows)} gold rows...", file=sys.stderr)

results = []
start = time.monotonic()
for i, r in enumerate(rows):
    merchant = r["merchant_raw"].strip().lower()
    description = r["description_raw"]
    amount = r["amount"]
    direction = r["direction"].strip().lower()
    user_msg = (f"merchant: {merchant}\n"
                f"description: {description}\n"
                f"amount: {amount}\n"
                f"direction: {direction}")
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]
    prompt = tokenizer.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
    pred_raw = generate(model, tokenizer, prompt, max_tokens=15, verbose=False)
    pred = pred_raw.strip().split("\n")[0].strip()

    gold_leaf = r["gold_leaf"].strip()
    leaf_correct = pred == gold_leaf
    pred_general = leaf_to_general.get(pred)
    gold_general = leaf_to_general.get(gold_leaf)
    general_correct = pred_general is not None and pred_general == gold_general

    results.append({**r, "pred_leaf": pred, "leaf_correct": leaf_correct,
                     "pred_general": pred_general, "gold_general": gold_general,
                     "general_correct": general_correct})
    if (i + 1) % 100 == 0:
        elapsed = time.monotonic() - start
        acc_so_far = sum(x["leaf_correct"] for x in results) / len(results)
        rate = (i + 1) / elapsed
        print(f"  {i+1}/{len(rows)} done in {elapsed:.0f}s ({rate:.2f} rows/sec), "
              f"running leaf accuracy {acc_so_far:.1%}", file=sys.stderr)

total_elapsed = time.monotonic() - start
n = len(results)
leaf_acc = sum(r["leaf_correct"] for r in results) / n
general_acc = sum(r["general_correct"] for r in results) / n
in_vocab = sum(1 for r in results if r["pred_leaf"] in leaf_to_general or r["pred_leaf"] == "unclassified_other") / n

print(f"\n=== VANILLA (no fine-tuning) RESULTS ({n} rows) ===")
print(f"Leaf accuracy:    {leaf_acc:.1%}")
print(f"General accuracy: {general_acc:.1%}")
print(f"In-taxonomy-vocab output rate: {in_vocab:.1%}")
print(f"Total inference time: {total_elapsed:.0f}s ({total_elapsed/60:.1f} min) "
      f"for {n} rows = {n/total_elapsed:.2f} rows/sec, {total_elapsed/n:.2f} sec/row")

with open(OUT_CSV, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
    w.writeheader()
    w.writerows(results)
print(f"\nPer-row predictions written to {OUT_CSV}")

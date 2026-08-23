"""Score the locally fine-tuned Gemma 3 4B LoRA adapter against the
held-out gold_v2_slm_eval_holdout.csv (CLAUDE.md / runbook step 5).

Never trains or early-stops on this file -- it is scored once, here, after
training is fully finished.
"""
import csv
import pathlib
import sys

from mlx_lm import load, generate

ROOT = pathlib.Path("/Users/carlosnoblejesus/Repos/raylo-transaction-categorisation")
MODEL = "mlx-community/gemma-3-text-4b-it-4bit"
ADAPTER = str(ROOT / "outputs/mlx_full_run/adapters")
SYSTEM_PROMPT = (ROOT / "benchmarks" / "tuning_system_prompt.txt").read_text()
GOLD_CSV = ROOT / "data/gold_v2_slm_eval_holdout.csv"
TAXONOMY_CSV = ROOT / "taxonomy/taxonomy.csv"
OUT_CSV = ROOT / "outputs/mlx_full_run/gold_eval_predictions.csv"

leaf_to_general = {}
with open(TAXONOMY_CSV) as f:
    for row in csv.DictReader(f):
        leaf_to_general[row["detailed_category"]] = row["general_category"]

print(f"Loading model + adapter...", file=sys.stderr)
model, tokenizer = load(MODEL, adapter_path=ADAPTER)

rows = list(csv.DictReader(open(GOLD_CSV)))
print(f"Scoring {len(rows)} gold rows...", file=sys.stderr)

results = []
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
        acc_so_far = sum(x["leaf_correct"] for x in results) / len(results)
        print(f"  {i+1}/{len(rows)} done, running leaf accuracy {acc_so_far:.1%}", file=sys.stderr)

n = len(results)
leaf_acc = sum(r["leaf_correct"] for r in results) / n
general_acc = sum(r["general_correct"] for r in results) / n
in_vocab = sum(1 for r in results if r["pred_leaf"] in leaf_to_general or r["pred_leaf"] == "unclassified_other") / n

print(f"\n=== RESULTS ({n} rows) ===")
print(f"Leaf accuracy:    {leaf_acc:.1%}")
print(f"General accuracy: {general_acc:.1%}")
print(f"In-taxonomy-vocab output rate: {in_vocab:.1%}")

with open(OUT_CSV, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
    w.writeheader()
    w.writerows(results)
print(f"\nPer-row predictions written to {OUT_CSV}")

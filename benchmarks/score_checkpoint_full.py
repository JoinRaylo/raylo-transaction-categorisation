"""Full 1,055-row confirmation score for one specific numbered checkpoint
(the coarse 200-row scan is noisy; this confirms the top candidates).
Usage: python score_checkpoint_full.py 28000
"""
import csv
import pathlib
import shutil
import sys

from mlx_lm import load, generate

ROOT = pathlib.Path("/Users/carlosnoblejesus/Repos/raylo-transaction-categorisation")
MODEL = "mlx-community/gemma-3-text-4b-it-4bit"
ADAPTER_DIR = ROOT / "outputs/mlx_full_run/adapters"
SYSTEM_PROMPT = (ROOT / "benchmarks" / "tuning_system_prompt.txt").read_text()
GOLD_CSV = ROOT / "data/gold_v2_slm_eval_holdout.csv"
TAXONOMY_CSV = ROOT / "taxonomy/taxonomy.csv"

iters = sys.argv[1] if len(sys.argv) > 1 else sys.exit("usage: score_checkpoint_full.py <iters>")
ckpt_file = ADAPTER_DIR / f"{int(iters):07d}_adapters.safetensors"
if not ckpt_file.exists():
    sys.exit(f"no such checkpoint: {ckpt_file}")
OUT_CSV = ROOT / f"outputs/mlx_full_run/gold_eval_predictions_ckpt{iters}.csv"

TMP_DIR = ROOT / f"outputs/mlx_full_run/_ckpt_full_tmp_{iters}"
TMP_DIR.mkdir(exist_ok=True)
shutil.copy(ADAPTER_DIR / "adapter_config.json", TMP_DIR / "adapter_config.json")
link = TMP_DIR / "adapters.safetensors"
if link.exists() or link.is_symlink():
    link.unlink()
link.symlink_to(ckpt_file.resolve())

leaf_to_general = {}
with open(TAXONOMY_CSV) as f:
    for row in csv.DictReader(f):
        leaf_to_general[row["detailed_category"]] = row["general_category"]

print(f"Loading checkpoint {iters}...", file=sys.stderr)
model, tokenizer = load(MODEL, adapter_path=str(TMP_DIR))

rows = list(csv.DictReader(open(GOLD_CSV)))
print(f"Scoring {len(rows)} gold rows against checkpoint {iters}...", file=sys.stderr)

results = []
for i, r in enumerate(rows):
    merchant = r["merchant_raw"].strip().lower()
    user_msg = (f"merchant: {merchant}\n"
                f"description: {r['description_raw']}\n"
                f"amount: {r['amount']}\n"
                f"direction: {r['direction'].strip().lower()}")
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_msg}]
    prompt = tokenizer.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
    pred = generate(model, tokenizer, prompt, max_tokens=15, verbose=False).strip().split("\n")[0].strip()

    gold_leaf = r["gold_leaf"].strip()
    leaf_correct = pred == gold_leaf
    pred_general = leaf_to_general.get(pred)
    gold_general = leaf_to_general.get(gold_leaf)
    general_correct = pred_general is not None and pred_general == gold_general
    results.append({**r, "pred_leaf": pred, "leaf_correct": leaf_correct,
                     "pred_general": pred_general, "gold_general": gold_general,
                     "general_correct": general_correct})
    if (i + 1) % 200 == 0:
        acc_so_far = sum(x["leaf_correct"] for x in results) / len(results)
        print(f"  {i+1}/{len(rows)} done, running leaf accuracy {acc_so_far:.1%}", file=sys.stderr)

n = len(results)
leaf_acc = sum(r["leaf_correct"] for r in results) / n
general_acc = sum(r["general_correct"] for r in results) / n

print(f"\n=== CHECKPOINT {iters} RESULTS ({n} rows) ===")
print(f"Leaf accuracy:    {leaf_acc:.1%}")
print(f"General accuracy: {general_acc:.1%}")

with open(OUT_CSV, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
    w.writeheader()
    w.writerows(results)
print(f"Per-row predictions written to {OUT_CSV}")

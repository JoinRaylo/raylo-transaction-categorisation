"""Coarse scan across saved LoRA checkpoints to find the best-generalizing
iteration count, using a fixed random subset of the gold eval set (full
1,055-row scoring takes ~11 min per checkpoint x 21 checkpoints = too slow
for a first pass). The final checkpoint's subset score is included so we
can sanity-check subset noise against its already-known full-set score
(47.6% leaf / 56.2% general).
"""
import csv
import os
import pathlib
import random
import shutil
import sys

from mlx_lm import load, generate

ROOT = pathlib.Path("/Users/carlosnoblejesus/Repos/raylo-transaction-categorisation")
MODEL = "mlx-community/gemma-3-text-4b-it-4bit"
ADAPTER_DIR = ROOT / "outputs/mlx_full_run/adapters"
SYSTEM_PROMPT = (ROOT / "benchmarks" / "tuning_system_prompt.txt").read_text()
GOLD_CSV = ROOT / "data/gold_v2_slm_eval_holdout.csv"
TAXONOMY_CSV = ROOT / "taxonomy/taxonomy.csv"
OUT_CSV = ROOT / "outputs/mlx_full_run/checkpoint_scan_results.csv"
SUBSET_N = 200
SEED = 42

CHECKPOINT_FILES = [ADAPTER_DIR / f"{i:07d}_adapters.safetensors" for i in range(2000, 41000, 2000)]
CHECKPOINT_FILES.append(ADAPTER_DIR / "adapters.safetensors")  # final, iter 41112

# mlx_lm's load_adapters() requires a directory containing literally-named
# adapter_config.json + adapters.safetensors -- it can't take a direct path
# to one of the numbered checkpoint files. Stage each checkpoint into a
# scratch dir via a swapped symlink instead of copying the 28MB file each time.
TMP_ADAPTER_DIR = ROOT / "outputs/mlx_full_run/_ckpt_scan_tmp"
TMP_ADAPTER_DIR.mkdir(exist_ok=True)
shutil.copy(ADAPTER_DIR / "adapter_config.json", TMP_ADAPTER_DIR / "adapter_config.json")
TMP_WEIGHTS_LINK = TMP_ADAPTER_DIR / "adapters.safetensors"

leaf_to_general = {}
with open(TAXONOMY_CSV) as f:
    for row in csv.DictReader(f):
        leaf_to_general[row["detailed_category"]] = row["general_category"]

all_rows = list(csv.DictReader(open(GOLD_CSV)))
rng = random.Random(SEED)
subset = rng.sample(all_rows, SUBSET_N)
print(f"Scanning {len(CHECKPOINT_FILES)} checkpoints on a fixed {SUBSET_N}-row subset...", file=sys.stderr)


def build_prompt(tokenizer, r):
    merchant = r["merchant_raw"].strip().lower()
    user_msg = (f"merchant: {merchant}\n"
                f"description: {r['description_raw']}\n"
                f"amount: {r['amount']}\n"
                f"direction: {r['direction'].strip().lower()}")
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]
    return tokenizer.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)


def score(model, tokenizer, rows):
    leaf_correct = 0
    general_correct = 0
    for r in rows:
        prompt = build_prompt(tokenizer, r)
        pred = generate(model, tokenizer, prompt, max_tokens=15, verbose=False).strip().split("\n")[0].strip()
        gold_leaf = r["gold_leaf"].strip()
        if pred == gold_leaf:
            leaf_correct += 1
        pred_g = leaf_to_general.get(pred)
        gold_g = leaf_to_general.get(gold_leaf)
        if pred_g is not None and pred_g == gold_g:
            general_correct += 1
    n = len(rows)
    return leaf_correct / n, general_correct / n


results = []
for ckpt_file in CHECKPOINT_FILES:
    ckpt_name = ckpt_file.stem
    print(f"Loading checkpoint {ckpt_name}...", file=sys.stderr)
    if TMP_WEIGHTS_LINK.exists() or TMP_WEIGHTS_LINK.is_symlink():
        TMP_WEIGHTS_LINK.unlink()
    TMP_WEIGHTS_LINK.symlink_to(ckpt_file.resolve())
    model, tokenizer = load(MODEL, adapter_path=str(TMP_ADAPTER_DIR))
    leaf_acc, general_acc = score(model, tokenizer, subset)
    print(f"  {ckpt_name}: leaf {leaf_acc:.1%}, general {general_acc:.1%}", file=sys.stderr)
    results.append({"checkpoint": ckpt_name, "leaf_acc": leaf_acc, "general_acc": general_acc})

with open(OUT_CSV, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["checkpoint", "leaf_acc", "general_acc"])
    w.writeheader()
    w.writerows(results)

print("\n=== SCAN SUMMARY (subset, n={}) ===".format(SUBSET_N))
for r in results:
    print(f"{r['checkpoint']}: leaf {r['leaf_acc']:.1%}, general {r['general_acc']:.1%}")
best = max(results, key=lambda r: r["leaf_acc"])
print(f"\nBest on subset: {best['checkpoint']} (leaf {best['leaf_acc']:.1%})")
print(f"Reference: final checkpoint scored 47.6% leaf / 56.2% general on the FULL 1055-row set (for subset-noise calibration).")

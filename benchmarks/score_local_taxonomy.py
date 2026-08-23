"""Score a local MLX model (vanilla Gemma 3 4B or the fine-tuned SLM) with
the REAL taxonomy in-context and TRUE constrained decoding enforcing a
valid leaf every time (via constrained_decode.py's token trie) -- the
local-model equivalent of the frontier LLMs' enum-constrained tool call.

The taxonomy block is ~7,177 tokens -- reprocessing it from scratch for
every one of 1,055 rows would take ~23 hours (measured). Instead we prime
the model's KV cache ONCE on the fixed shared prefix (system prompt +
taxonomy, identical for every row) and deep-copy that primed cache per row,
feeding only the small per-row suffix (user message + generation marker).
Correctness of the prefix/suffix token split is verified per row (not
assumed) against a fresh full-string tokenization, since BPE boundary
effects could in principle shift tokens across the split point.

Usage: python score_local_taxonomy.py {vanilla,finetuned}
"""
import copy
import csv
import pathlib
import sys
import time
from collections import defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))
import mlx.core as mx
from mlx_lm import load, generate
from mlx_lm.models import cache as mlx_cache
from constrained_decode import generate_constrained
from gating_experiment import load_crosswalk, load_example_merchants

ROOT = pathlib.Path("/Users/carlosnoblejesus/Repos/raylo-transaction-categorisation")
MODEL = "mlx-community/gemma-3-text-4b-it-4bit"
BEST_CHECKPOINT = ROOT / "outputs/mlx_full_run/adapters/0038000_adapters.safetensors"
GOLD_CSV = ROOT / "data/gold_v2_slm_eval_holdout.csv"

variant = sys.argv[1] if len(sys.argv) > 1 else sys.exit("usage: score_local_taxonomy.py {vanilla,finetuned}")
if variant not in ("vanilla", "finetuned"):
    sys.exit("variant must be 'vanilla' or 'finetuned'")
LOG = f"[local-{variant}]"
OUT_CSV = ROOT / f"outputs/mlx_full_run/local_{variant}_taxonomy_predictions.csv"

_, _, leaves, gen_of, notes_of = load_crosswalk()
examples_of = load_example_merchants()
candidates = sorted(leaves) + ["unclassified_other"]


def build_taxonomy_block():
    by_gen = defaultdict(list)
    for leaf in leaves:
        by_gen[gen_of[leaf]].append(leaf)
    lines = ["## Taxonomy (the complete, closed set of valid categories)"]
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
    lines.append("\n- `unclassified_other` -- use when genuinely ambiguous or unidentifiable.")
    return "\n".join(lines)


SYSTEM_PROMPT = (
    "You categorise a UK bank transaction into exactly one category. Respond with the "
    "category name only, nothing else.\n\n"
    "You are given: merchant (the counterparty name), description (the raw bank narrative), "
    "amount (absolute value, GBP), and direction (debit = money out / spending; credit = "
    "money in / income or refund).\n\n"
    + build_taxonomy_block()
)

leaf_to_general = dict(gen_of)
rows = list(csv.DictReader(open(GOLD_CSV)))

print(f"{LOG} loading model (adapter={'none' if variant == 'vanilla' else BEST_CHECKPOINT.name})...",
      file=sys.stderr)
if variant == "finetuned":
    import shutil
    tmp_dir = ROOT / "outputs/mlx_full_run/_ckpt_besttax_tmp"
    tmp_dir.mkdir(exist_ok=True)
    shutil.copy(ROOT / "outputs/mlx_full_run/adapters/adapter_config.json", tmp_dir / "adapter_config.json")
    link = tmp_dir / "adapters.safetensors"
    if link.exists() or link.is_symlink():
        link.unlink()
    link.symlink_to(BEST_CHECKPOINT.resolve())
    model, tokenizer = load(MODEL, adapter_path=str(tmp_dir))
else:
    model, tokenizer = load(MODEL)

# Render the template ONCE with a placeholder standing in for the per-row
# user content, so we can split the rendered string into a fixed prefix
# (system + taxonomy, identical every row) and a fixed suffix template
# (whatever the chat template puts after the user turn -- end-of-turn +
# generation marker), with the real user message sandwiched between them.
PLACEHOLDER = "@@@USERMSG@@@"
rendered = tokenizer.apply_chat_template(
    [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": PLACEHOLDER}],
    add_generation_prompt=True, tokenize=False,
)
prefix_str, suffix_template = rendered.split(PLACEHOLDER)

add_special_tokens = tokenizer.bos_token is None or not prefix_str.startswith(tokenizer.bos_token)
prefix_ids = tokenizer.encode(prefix_str, add_special_tokens=add_special_tokens)
print(f"{LOG} shared prefix: {len(prefix_ids)} tokens -- priming cache once...", file=sys.stderr)

t0 = time.monotonic()
base_cache = mlx_cache.make_prompt_cache(model)
model(mx.array(prefix_ids)[None], cache=base_cache)
mx.eval([c.state for c in base_cache])
print(f"{LOG} cache primed in {time.monotonic()-t0:.1f}s", file=sys.stderr)

print(f"{LOG} scoring {len(rows)} gold rows with full taxonomy + constrained decoding (cached prefix)...",
      file=sys.stderr)
results = []
mismatches = 0
start = time.monotonic()
for i, r in enumerate(rows):
    merchant = r["merchant_raw"].strip().lower()
    user_msg = (f"merchant: {merchant}\n"
                f"description: {r['description_raw']}\n"
                f"amount: {r['amount']}\n"
                f"direction: {r['direction'].strip().lower()}")
    full_str = prefix_str + user_msg + suffix_template
    full_ids = tokenizer.encode(full_str, add_special_tokens=add_special_tokens)

    if full_ids[:len(prefix_ids)] == prefix_ids:
        suffix_ids = full_ids[len(prefix_ids):]
        row_cache = copy.deepcopy(base_cache)
        pred = generate_constrained(model, tokenizer, suffix_ids, candidates, generate, prompt_cache=row_cache)
    else:
        mismatches += 1  # BPE boundary shifted tokens -- fall back to a full, uncached pass
        pred = generate_constrained(model, tokenizer, full_str, candidates, generate)

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
        print(f"{LOG} {i+1}/{len(rows)} done in {elapsed:.0f}s ({(i+1)/elapsed:.2f} rows/sec), "
              f"running leaf accuracy {acc_so_far:.1%}, {mismatches} prefix mismatches so far",
              file=sys.stderr)

total_elapsed = time.monotonic() - start
n = len(results)
leaf_acc = sum(r["leaf_correct"] for r in results) / n
general_acc = sum(r["general_correct"] for r in results) / n

print(f"\n{LOG} === RESULTS ({n} rows, full taxonomy + constrained decoding, cached prefix) ===")
print(f"{LOG} Leaf accuracy:    {leaf_acc:.1%}")
print(f"{LOG} General accuracy: {general_acc:.1%}")
print(f"{LOG} Prefix mismatches (uncached fallback): {mismatches}/{n}")
print(f"{LOG} Total time: {total_elapsed:.0f}s ({total_elapsed/60:.1f} min) = {n/total_elapsed:.2f} rows/sec, "
      f"{total_elapsed/n:.2f} sec/row")

with open(OUT_CSV, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
    w.writeheader()
    w.writerows(results)
print(f"{LOG} Per-row predictions written to {OUT_CSV}")

"""Score a Qwen3 MLX LoRA adapter on a gold CSV.

Closed-vocab direct generation — same system prompt and user-message shape as
training. Never scores locked confirmation sets (v5 retired; v6 at go/no-go).

Usage:
    .venv/bin/python benchmarks/score_qwen_eval.py \\
        --model mlx-community/Qwen3-4B-Instruct-2507-4bit \\
        --adapter outputs/qwen3_4b_adapters \\
        --gold data/gold_v2_slm_eval_holdout.csv \\
        --out outputs/qwen3_4b_holdout_predictions.csv

    # v4 post-T4 residual only (exact LOWER(TRIM(merchant)) dictionary membership)
    .venv/bin/python benchmarks/score_qwen_eval.py ... \\
        --gold data/gold_transactions_v4_slm_volume.csv \\
        --residual-t4 \\
        --out outputs/qwen3_4b_v4_residual_predictions.csv
"""
from __future__ import annotations

import argparse
import csv
import pathlib
import sys

from mlx_lm import load, generate

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from eval_sets import refuse_confirmation_eval  # noqa: E402

SYSTEM_PROMPT = (ROOT / "outputs" / "tuning_system_prompt.txt").read_text()
TAXONOMY_CSV = ROOT / "taxonomy" / "taxonomy.csv"
DICT_CSV = ROOT / "taxonomy" / "merchant_dictionary.csv"


def load_taxonomy():
    leaf_to_general = {}
    with open(TAXONOMY_CSV) as f:
        for row in csv.DictReader(f):
            leaf_to_general[row["detailed_category"]] = row["general_category"]
    return leaf_to_general


def load_t4_keys():
    keys = set()
    with open(DICT_CSV) as f:
        for row in csv.DictReader(f):
            keys.add(row["normalised_merchant"].strip().lower())
    return keys


def clean_pred(raw: str, vocab: set[str]) -> str:
    text = raw
    if "</think>" in text:
        text = text.split("</think>")[-1]
    line = text.strip().split("\n")[0].strip().strip("`").strip('"').strip("'")
    if line in vocab or line == "unclassified_other":
        return line
    for tok in line.replace(",", " ").split():
        t = tok.strip(".:;")
        if t in vocab or t == "unclassified_other":
            return t
    return line


def build_prompt(tokenizer, row: dict) -> str:
    merchant = row["merchant_raw"].strip().lower()
    description = row["description_raw"]
    amount = row["amount"]
    direction = row["direction"].strip().lower()
    user_msg = (
        f"merchant: {merchant}\n"
        f"description: {description}\n"
        f"amount: {amount}\n"
        f"direction: {direction}"
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]
    kwargs = dict(add_generation_prompt=True, tokenize=False)
    try:
        return tokenizer.apply_chat_template(
            messages, enable_thinking=False, **kwargs
        )
    except TypeError:
        return tokenizer.apply_chat_template(messages, **kwargs)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", required=True)
    p.add_argument("--adapter", required=True)
    p.add_argument("--gold", required=True, type=pathlib.Path)
    p.add_argument("--out", required=True, type=pathlib.Path)
    p.add_argument(
        "--residual-t4",
        action="store_true",
        help="Keep only rows whose merchant is NOT an exact T4 dictionary key",
    )
    p.add_argument("--max-tokens", type=int, default=16)
    args = p.parse_args()

    gold_path = args.gold.resolve()
    refuse_confirmation_eval(gold_path)

    leaf_to_general = load_taxonomy()
    vocab = set(leaf_to_general) | {"unclassified_other"}

    rows = list(csv.DictReader(open(args.gold)))
    if args.residual_t4:
        t4 = load_t4_keys()
        before = len(rows)
        rows = [
            r for r in rows
            if r["merchant_raw"].strip().lower() not in t4
        ]
        print(f"T4 residual: {len(rows)}/{before} rows", file=sys.stderr)

    print(f"Loading {args.model} + {args.adapter}...", file=sys.stderr)
    model, tokenizer = load(args.model, adapter_path=args.adapter)

    print(f"Scoring {len(rows)} gold rows from {args.gold}...", file=sys.stderr)
    results = []
    for i, r in enumerate(rows):
        prompt = build_prompt(tokenizer, r)
        pred_raw = generate(
            model, tokenizer, prompt, max_tokens=args.max_tokens, verbose=False
        )
        pred = clean_pred(pred_raw, vocab)
        gold_leaf = r["gold_leaf"].strip()
        pred_general = leaf_to_general.get(pred)
        gold_general = leaf_to_general.get(gold_leaf)
        results.append({
            **r,
            "gold_leaf": gold_leaf,
            "gold_leaf": gold_leaf,
            "pred_leaf": pred,
            "pred_raw": pred_raw.strip().replace("\n", " | "),
            "leaf_correct": pred == gold_leaf,
            "pred_general": pred_general,
            "gold_general": gold_general,
            "general_correct": pred_general is not None and pred_general == gold_general,
        })
        if (i + 1) % 50 == 0:
            acc = sum(x["leaf_correct"] for x in results) / len(results)
            print(f"  {i+1}/{len(rows)} leaf {acc:.1%}", file=sys.stderr)

    n = len(results)
    leaf_acc = sum(r["leaf_correct"] for r in results) / n if n else 0.0
    general_acc = sum(r["general_correct"] for r in results) / n if n else 0.0
    in_vocab = sum(1 for r in results if r["pred_leaf"] in vocab) / n if n else 0.0

    print(f"\n=== RESULTS ({n} rows) ===")
    print(f"Leaf accuracy:    {leaf_acc:.1%}")
    print(f"General accuracy: {general_acc:.1%}")
    print(f"In-taxonomy-vocab: {in_vocab:.1%}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        w.writeheader()
        w.writerows(results)
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()

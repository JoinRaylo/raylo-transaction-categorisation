"""Variant selection for the TxCat-1 retrain (acceptance plan, amendment 7).

This re-scores every stage-2 seed of A, B and B2 on the same 5,000 validation
rows, with the training-time evaluation (``train_classifier.evaluate``'s text,
masks and argmax), and keeps per-row correctness so the comparison is paired.

For each variant, a row's accuracy is the mean over its three seeds.  The
B − B2 difference and the winner − A difference get 95% paired bootstrap
intervals (10,000 row resamples, fixed seed).  The amendment-7 rule is then
applied:
- B2 is the default;
- B replaces B2 only if B leads by more than 0.5 pp *and* the lower bound of
  the interval is above zero;
- if B2 trails B by more than 1.0 pp, selection pauses;
- the winner is then compared with A, and A is chosen only if within 0.1 pp;
- within the chosen variant, the median seed is used.

Validation only; the benchmark is never read.  Prints aggregates and writes
``outputs/variant_selection.json``.

    TXNCAT_TUNING_DIR=outputs/retrain_export_v2 python src/transformer/compare_variants.py
"""

from __future__ import annotations

import json
import os
import pathlib
import sys

import numpy as np
import torch

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src" / "transformer"))

import train_classifier as tc  # noqa: E402
from build_corpus import sentence  # noqa: E402
from transformers import AutoTokenizer  # noqa: E402

MODELS = ROOT / "outputs" / "distill_models"
VARIANTS = ("A", "B", "B2")
SEEDS = (42, 7, 123)
RESAMPLES, BOOT_SEED = 10_000, 20260925


@torch.no_grad()
def row_correct(model_dir: pathlib.Path, val, leaves, leaf_ix, masks, dev) -> np.ndarray:
    leaf_to_gen, credit_ok, debit_ok = masks
    tok = AutoTokenizer.from_pretrained(model_dir)
    labels = json.loads((model_dir / "labels.json").read_text())
    if labels["leaves"] != leaves:
        raise RuntimeError(f"{model_dir.name}: label order differs from the taxonomy")
    model = tc.TxnClassifier(model_dir, len(leaves), leaf_to_gen.max().item() + 1,
                             leaf_to_gen, credit_ok, debit_ok).to(dev)
    model.load_state_dict(tc.load_heads(model_dir / "heads.pt"), strict=False)
    model.eval()
    out = []
    for i in range(0, len(val), 256):
        chunk = val.iloc[i:i + 256]
        enc = tok(chunk["text"].tolist(), truncation=True, max_length=48, padding="longest",
                  return_tensors="pt")
        logits, _ = model(enc["input_ids"].to(dev), enc["attention_mask"].to(dev),
                          torch.tensor(chunk["is_credit"].to_numpy(), device=dev))
        pred = [leaves[j] for j in logits.argmax(-1).tolist()]
        out.extend(p == g for p, g in zip(pred, chunk["leaf"]))
    return np.asarray(out, dtype=float)


def paired(a: np.ndarray, b: np.ndarray, rng) -> dict:
    d = a - b
    idx = rng.integers(0, len(d), size=(RESAMPLES, len(d)))
    boots = d[idx].mean(axis=1)
    return {"diff_pp": round(100 * d.mean(), 3),
            "ci95_pp": [round(100 * np.percentile(boots, 2.5), 3),
                        round(100 * np.percentile(boots, 97.5), 3)]}


def main() -> None:
    if not os.environ.get("TXNCAT_TUNING_DIR"):
        raise SystemExit("set TXNCAT_TUNING_DIR to the retrain export")
    dev = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    leaves, leaf_ix, _gens, _gen_ix, leaf_to_gen, credit_ok, debit_ok = tc.load_taxonomy()
    v = tc._parse_tuning_jsonl(tc.VAL_JSONL)
    v["text"] = [sentence("credit" if int(c) else "debit", tc.amt_bucket_py(a), m, d)
                 for m, d, a, c in zip(v["vendor"], v["description"], v["amount"], v["is_credit"])]
    v["is_credit"] = v["is_credit"].astype(int)
    val = v[v["leaf"].isin(leaf_ix)].reset_index(drop=True)[["text", "leaf", "is_credit"]]
    per_model, recorded = {}, {}
    for variant in VARIANTS:
        for seed in SEEDS:
            name = f"txn_classifier_gold_distilled_{variant}_s{seed}"
            meta = json.loads((MODELS / name / "train_meta.json").read_text())
            if meta.get("placeholder") or meta.get("seed") != seed:
                raise RuntimeError(f"{name}: not a real seed-{seed} model")
            per_model[(variant, seed)] = row_correct(
                MODELS / name, val, leaves, leaf_ix, (leaf_to_gen, credit_ok, debit_ok), dev)
            recorded[(variant, seed)] = meta["best_val"]
    rng = np.random.default_rng(BOOT_SEED)
    rows = {var: np.mean([per_model[(var, s)] for s in SEEDS], axis=0) for var in VARIANTS}
    b_vs_b2 = paired(rows["B"], rows["B2"], rng)
    if b_vs_b2["diff_pp"] > 1.0:
        decision, winner = "pause: B2 trails B by more than 1.0 pp; investigate B2's run", None
    elif b_vs_b2["diff_pp"] > 0.5 and b_vs_b2["ci95_pp"][0] > 0:
        decision, winner = "B replaces B2 (lead > 0.5 pp and lower bound > 0)", "B"
    else:
        decision, winner = "B2 kept (B's lead is not > 0.5 pp with lower bound > 0)", "B2"
    result = {
        "schema_version": "txncat1-variant-selection-v1",
        "validation_rows": len(val),
        "seed_accuracy_pp": {f"{var}_s{s}": {"rescored": round(100 * per_model[(var, s)].mean(), 2),
                                            "recorded_best_val": round(100 * recorded[(var, s)], 2)}
                             for var in VARIANTS for s in SEEDS},
        "variant_mean_pp": {var: round(100 * rows[var].mean(), 3) for var in VARIANTS},
        "B_minus_B2": b_vs_b2,
        "step2": decision,
    }
    if winner:
        vs_a = paired(rows[winner], rows["A"], rng)
        result[f"{winner}_minus_A"] = vs_a
        chosen = "A" if vs_a["diff_pp"] <= 0.1 else winner
        accs = sorted((per_model[(chosen, s)].mean(), s) for s in SEEDS)
        result["chosen_variant"] = chosen
        result["chosen_seed"] = accs[1][1]
        result["step3"] = (f"A chosen ({winner} within 0.1 pp)" if chosen == "A"
                           else f"{winner} kept over A (lead {vs_a['diff_pp']} pp > 0.1 pp)")
    out = ROOT / "outputs" / "variant_selection.json"
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()

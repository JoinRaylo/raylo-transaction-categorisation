"""Make the stage-1 labels merchant-disjoint from the stage-2 validation set.

Retrain amendment 5 (Carlos, 2026-09-24).  ``build_stage1_labels.py`` kept
stage 1 away from the benchmark and gold sets, but not from the 5,000-row
validation set in ``retrain_export_v2/tuning_val.jsonl``.  Half the validation
texts were in stage 1, which inflated validation and biased best-epoch choice.

This script:
1. verifies the current stage-1 receipt;
2. drops every row whose merchant (normalised, raw or cleaned) is a validation
   merchant, or whose text matches a validation text;
3. moves the old parquet and its receipt to ``superseded-val-overlap/``;
4. re-runs the canonical gate and writes a fresh receipt at the same path.

The stage-2 export already excludes validation merchants, so after this no
training stage has seen a validation merchant.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import sys
from collections import Counter

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src" / "transformer"))

import eval_protection  # noqa: E402
from build_stage1_labels import CONSUMER, INPUTS, PURPOSE  # noqa: E402

USER = re.compile(
    r"\Amerchant: (?P<merchant>.*?)\ndescription: (?P<description>.*)\n"
    r"amount: (?P<amount>[^\n]*)\ndirection: (?P<direction>[^\n]*)\Z",
    re.DOTALL,
)


def norm(value) -> str:
    return " ".join(str(value or "").lower().split())


def main() -> None:
    parser = eval_protection.add_args(argparse.ArgumentParser(description=__doc__))
    parser.add_argument("--validation", type=pathlib.Path,
                        default=ROOT / "outputs/retrain_export_v2/tuning_val.jsonl")
    args = parser.parse_args()
    protection, _publication = eval_protection.load_release(args)
    path = INPUTS / "stage1_labels.parquet"
    eval_protection.verify_artifact(path, expected_consumer=CONSUMER, expected_purpose=PURPOSE,
                                    protection=protection)
    before_sha = hashlib.sha256(path.read_bytes()).hexdigest()
    merchants, texts = set(), set()
    for line in open(args.validation, encoding="utf-8"):
        f = USER.match(json.loads(line)["messages"][1]["content"]).groupdict()
        if norm(f["merchant"]):
            merchants.add(norm(f["merchant"]))
        texts.add((f["direction"], norm(f["merchant"]), norm(f["description"])))
    df = pd.read_parquet(path)
    m1, m2 = df.merchant.map(norm), df.merchant_raw.map(norm)
    d1, d2 = df.description.map(norm), df.description_raw.map(norm)
    hit_merchant = (m1.isin(merchants) & (m1 != "")) | (m2.isin(merchants) & (m2 != ""))
    hit_text = pd.Series([(a, b, c) in texts or (a, d, e) in texts
                          for a, b, c, d, e in zip(df.direction, m1, d1, m2, d2)], index=df.index)
    drop = hit_merchant | hit_text
    kept = df[~drop]
    outcomes = {
        "rows_before": len(df),
        "dropped_validation_merchant": int(hit_merchant.sum()),
        "dropped_validation_text_only": int((hit_text & ~hit_merchant).sum()),
        "dropped_by_label_source": dict(Counter(df.label_source[drop])),
        "rows_after": len(kept),
        "validation_merchants": len(merchants),
    }
    old = INPUTS / "superseded-val-overlap"
    old.mkdir(mode=0o700, exist_ok=False)
    receipt_old = path.with_name(path.name + ".b04-receipt.json")
    shutil.move(str(path), old / path.name)
    shutil.move(str(receipt_old), old / receipt_old.name)
    guarded = eval_protection.apply(kept.to_dict("records"), args, purpose=PURPOSE)
    if len(guarded) != len(kept):
        raise RuntimeError("the gate excluded rows of an already-guarded stage-1 set; stopping")
    pd.DataFrame(list(guarded)).to_parquet(path, index=False)
    os.chmod(path, 0o600)
    receipt = eval_protection.write_artifact_receipt(path, consumer=CONSUMER, purpose=PURPOSE,
                                                     guard=guarded.guard)
    summary_path = INPUTS / "stage1_labels_summary.json"
    summary = json.loads(summary_path.read_text())
    summary["amendment_5_validation_exclusion"] = {
        **outcomes,
        "superseded_sha256": before_sha,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "validation_sha256": hashlib.sha256(args.validation.read_bytes()).hexdigest(),
    }
    summary["rows"] = len(kept)
    summary["by_label_source"] = kept.label_source.value_counts().to_dict()
    summary["receipt"] = receipt.name
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary["amendment_5_validation_exclusion"], indent=1))


if __name__ == "__main__":
    main()

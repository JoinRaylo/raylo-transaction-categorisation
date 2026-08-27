"""Append labelled T6 residual packs to data/tuning_leaf_topup.csv.

Training only. Reads Carlos-reviewed files in outputs/, writes gold_leaf =
correct_category. Skips holdout merchants (non-starved) and exact fingerprints
already in the top-up file.

Does not retrain the classifier. Rebuild jsonl with:

    python src/build_tuning_dataset.py build

Usage:
    python src/append_t6_residual_topup.py
"""
from __future__ import annotations

import csv
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs"
FINAL = ROOT / "data" / "tuning_leaf_topup.csv"
HOLDOUT = ROOT / "data" / "gold_v2_slm_eval_holdout.csv"
STARVED = {
    "cash_advance", "charge_card_repayment", "financial_services_other",
    "overdraft_unarranged", "balance_transfer",
}
REVIEWED = [
    OUT / "t6_residual_topup_sample_reviewed.csv",
    OUT / "t6_residual_topup2_sample_reviewed.csv",
]
FIELDS = ["merchant_raw", "description_raw", "amount", "direction",
          "native_category", "gold_leaf", "target_leaf"]


def _norm(s):
    return (s or "").strip().lower()


def _amt_key(v):
    try:
        return f"{round(abs(float(v)), 2):.2f}"
    except (TypeError, ValueError):
        return str(v or "")


def _fp(r):
    return (_norm(r.get("merchant_raw") or ""), _norm(r.get("description_raw") or ""),
            _amt_key(r.get("amount")), _norm(r.get("direction") or ""), r["gold_leaf"])


def main():
    holdout = {_norm(r["merchant_raw"]) for r in csv.DictReader(open(HOLDOUT))}
    holdout.discard("")
    existing = list(csv.DictReader(open(FINAL))) if FINAL.exists() else []
    seen = {_fp(r) for r in existing}
    added, skipped = [], {"holdout": 0, "dup": 0, "blank": 0}
    for path in REVIEWED:
        if not path.exists():
            sys.exit(f"missing {path}")
        for r in csv.DictReader(open(path)):
            leaf = (r.get("correct_category") or "").strip()
            if not leaf:
                skipped["blank"] += 1
                continue
            merch = r.get("merchant_raw") or r.get("merchant") or ""
            if _norm(merch) in holdout and leaf not in STARVED:
                skipped["holdout"] += 1
                continue
            row = {
                "merchant_raw": merch,
                "description_raw": r.get("description_raw") or "",
                "amount": _amt_key(r.get("amount")),
                "direction": (r.get("direction") or "").lower(),
                "native_category": r.get("native_category") or "",
                "gold_leaf": leaf,
                "target_leaf": (r.get("target_leaf") or "").strip(),
            }
            fp = _fp(row)
            if fp in seen:
                skipped["dup"] += 1
                continue
            seen.add(fp)
            added.append(row)

    with open(FINAL, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(existing)
        w.writerows(added)
    print(f"was {len(existing)}; added {len(added)}; now {len(existing) + len(added)}; "
          f"skipped {skipped}", file=sys.stderr)


if __name__ == "__main__":
    main()

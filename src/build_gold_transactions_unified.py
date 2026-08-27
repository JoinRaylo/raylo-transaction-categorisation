"""Build the append-only unified transaction gold file.

Concatenates human-reviewed v2, v2 batch 2, v3, and v4. Does not include
risk gold or locked v5.

Role:
  iter_eval — merchant appears in data/gold_v2_slm_eval_holdout.csv
  train     — everyone else

The holdout CSV itself is not rewritten here (published §6a numbers).

Usage:
    python src/build_gold_transactions_unified.py
"""
from __future__ import annotations

import csv
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "gold_transactions.csv"
HOLDOUT = ROOT / "data" / "gold_v2_slm_eval_holdout.csv"
V4_EYE = ROOT / "data" / "gold_v4_eyeball.csv"
FIELDNAMES = [
    "source", "role", "merchant_raw", "description_raw", "amount", "direction",
    "provider", "native_category", "gold_leaf", "notes",
]


def _norm(s):
    return (s or "").strip().lower()


def _key(r):
    try:
        amt = f"{abs(float(r['amount'])):.4f}"
    except (TypeError, ValueError):
        amt = "0.0000"
    return (
        _norm(r.get("merchant_raw", "")),
        (r.get("description_raw") or "").strip(),
        amt,
        _norm(r.get("direction", "")),
    )


def holdout_merchants():
    return {_norm(r["merchant_raw"]) for r in csv.DictReader(open(HOLDOUT))}


def v4_native_map():
    eye = list(csv.DictReader(open(V4_EYE)))
    by_key = {}
    for r in eye:
        by_key[_key(r)] = r.get("native_category_raw") or ""
    notes = {}
    for r in eye:
        notes[_key(r)] = r.get("review_notes") or ""
    return by_key, notes


def row_out(source, r, holdout_m, native, notes=""):
    m = _norm(r["merchant_raw"])
    return {
        "source": source,
        "role": "iter_eval" if m in holdout_m else "train",
        "merchant_raw": r["merchant_raw"],
        "description_raw": r.get("description_raw") or "",
        "amount": r["amount"],
        "direction": (r.get("direction") or "").strip().lower(),
        "provider": (r.get("provider") or "").strip().lower(),
        "native_category": native or "",
        "gold_leaf": r["gold_leaf"],
        "notes": notes or r.get("notes") or "",
    }


def main():
    holdout_m = holdout_merchants()
    v4_native, v4_notes = v4_native_map()
    out = []
    seen = set()

    def add(source, r, native, notes=""):
        k = (*_key(r), source)
        if k in seen:
            return
        seen.add(k)
        if not r.get("gold_leaf"):
            return
        out.append(row_out(source, r, holdout_m, native, notes))

    for path, source in [
        (ROOT / "data" / "gold_transactions_v2.csv", "v2"),
        (ROOT / "data" / "gold_transactions_v2_batch2.csv", "v2_batch2"),
    ]:
        for r in csv.DictReader(open(path)):
            add(source, r, r.get("native_category") or "", r.get("notes") or "")

    for r in csv.DictReader(open(ROOT / "data" / "gold_transactions_v3_volume.csv")):
        add("v3", r, r.get("native_category") or "", r.get("notes") or "")

    for r in csv.DictReader(open(ROOT / "data" / "gold_transactions_v4_slm_volume.csv")):
        k = _key(r)
        r = {**r, "provider": "plaid"}
        add("v4", r, v4_native.get(k, ""), v4_notes.get(k, ""))

    n_eval = sum(1 for r in out if r["role"] == "iter_eval")
    n_train = len(out) - n_eval
    missing_v4 = sum(1 for r in out if r["source"] == "v4" and not r["native_category"])
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        w.writeheader()
        w.writerows(out)
    print(f"Wrote {OUT}: {len(out)} rows ({n_train} train, {n_eval} iter_eval); "
          f"{len(holdout_m)} holdout merchants; v4 missing native={missing_v4}",
          file=sys.stderr)


if __name__ == "__main__":
    main()

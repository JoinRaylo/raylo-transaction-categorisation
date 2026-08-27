"""Evaluation-set roles and scoring guards.

v5 was built as a locked confirmation set of novel merchants. Tranche 4 and
the doubled dictionary later covered hundreds of those merchants, so it is
retired as confirmation gold. The rows stay in git as reviewed labels.

v6 is the replacement locked set. It is scored once, at go/no-go, then
retired. Do not point a benchmark at either file during development.
"""
from __future__ import annotations

import csv
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

V5_LOCKED = ROOT / "data" / "gold_transactions_v5_LOCKED.csv"
V6_LOCKED = ROOT / "data" / "gold_transactions_v6_LOCKED.csv"

# Filenames that must never be scored during development.
CONFIRMATION_SET_NAMES = frozenset({
    "gold_transactions_v5_LOCKED.csv",
    "gold_transactions_v6_LOCKED.csv",
})

# Iteration suite — these may be scored while we work.
DEVELOPMENT_EVAL_FILES = (
    "gold_v2_slm_eval_holdout.csv",
    "gold_transactions_risk_categories.csv",
    "gold_transactions_v3_volume.csv",
    "gold_transactions_v4_slm_volume.csv",
    "gold_transactions.csv",
)

_V6_GOLD_FILES = (
    "gold_transactions.csv",
    "gold_transactions_v2.csv",
    "gold_transactions_v2_batch2.csv",
    "gold_transactions_v3_volume.csv",
    "gold_transactions_v4_slm_volume.csv",
    "gold_transactions_v5_LOCKED.csv",
    "gold_merchant_labels.csv",
    "gold_tail_labels.csv",
    "gold_v2_slm_eval_holdout.csv",
    "gold_transactions_risk_categories.csv",
    "gold_v3_eyeball.csv",
    "gold_v4_eyeball.csv",
    "tuning_leaf_topup.csv",
)
_V6_TRANCHE_FILES = (
    "production_labels_tranche1.csv",
    "production_labels_tranche2.csv",
    "production_labels_tranche3.csv",
    "production_labels_tranche4.csv",
)


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def refuse_confirmation_eval(path) -> None:
    """Exit if `path` is a locked confirmation set. Call from every scorer."""
    name = pathlib.Path(path).name
    if name in CONFIRMATION_SET_NAMES:
        sys.exit(
            f"Refusing to score {name}. "
            "v5 is retired (tranche-4 novelty leak). "
            "v6 is the locked confirmation set and is scored once at go/no-go."
        )


def v6_excluded_merchants() -> set[str]:
    """Every merchant this project has labelled, dictionaried, or held out."""
    seen: set[str] = set()
    data = ROOT / "data"
    for fname in _V6_GOLD_FILES:
        path = data / fname
        if not path.exists():
            continue
        for r in csv.DictReader(open(path)):
            seen.add(_norm(r.get("merchant_raw") or r.get("merchant") or ""))
    for fname in _V6_TRANCHE_FILES:
        path = data / fname
        if not path.exists():
            continue
        for r in csv.DictReader(open(path)):
            seen.add(_norm(r.get("merchant") or r.get("merchant_raw") or ""))
    dict_path = ROOT / "taxonomy" / "merchant_dictionary.csv"
    if dict_path.exists():
        for r in csv.DictReader(open(dict_path)):
            seen.add(_norm(r.get("normalised_merchant") or ""))
    seen.discard("")
    return seen

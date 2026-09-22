"""Append labelled T6 residual packs to data/tuning_leaf_topup.csv.

Training only. Reads Carlos-reviewed files in outputs/, writes gold_leaf =
correct_category. Skips holdout merchants (non-starved) and exact fingerprints
already in the top-up file.

B04: every appended row is joined back to its guarded raw fetch row — the
reviewed file alone cannot prove which linked event it came from — and the
output manifest propagates that row's exact identity and source digest.
Existing rows carry their prior manifest entry forward; rows that cannot
resolve to an exact identity fail issuance, so a top-up file whose rows
predate guarded fetches stays gated until an identity-preserving rebuild.

Does not retrain the classifier. Rebuild jsonl with:

    python src/build_tuning_dataset.py build

Usage:
    python src/append_t6_residual_topup.py
"""
from __future__ import annotations

import csv
import json
import pathlib
import sys

import eval_protection  # noqa: E402

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


def _fetch_fp(r):
    """Content fingerprint joining a reviewed row to its raw fetch row."""

    return (
        _norm(r.get("merchant_raw") or r.get("merchant") or ""),
        _norm(r.get("description_raw") or ""),
        _amt_key(r.get("amount")),
        _norm(r.get("direction") or ""),
    )


def _prior_manifest(path):
    """The prior artifact's bound row manifest: row_sha256 -> entry."""

    manifest_path = path.with_name(path.name + ".b04-manifest.json")
    if not manifest_path.exists():
        return {}
    document = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {
        entry["row_sha256"]: entry for entry in document.get("rows") or []
    }


def _join_raw(reviewed, raw_rows):
    """Deterministically join one reviewed row to its guarded raw fetch row.

    ``row_id`` is the primary key; the content fingerprint must then agree.
    Without ``row_id`` the fingerprint must match exactly one raw row.
    Anything else fails closed — an unjoined reviewed row cannot claim an
    identity.
    """

    row_id = (reviewed.get("row_id") or "").strip()
    fingerprint = _fetch_fp(reviewed)
    if row_id:
        matches = [r for r in raw_rows if str(r.get("row_id")) == row_id]
        if len(matches) != 1:
            sys.exit(f"B04: row_id {row_id!r} matches {len(matches)} raw rows")
        raw = matches[0]
        if _fetch_fp(raw) != fingerprint:
            sys.exit(
                f"B04: reviewed row_id {row_id!r} content does not match its "
                "raw fetch row"
            )
        return raw
    matches = [r for r in raw_rows if _fetch_fp(r) == fingerprint]
    if len(matches) != 1:
        sys.exit(
            f"B04: reviewed row matches {len(matches)} raw rows by fingerprint "
            f"({fingerprint!r}); cannot establish its source event"
        )
    return matches[0]


def main():
    # B04: the reviewed files descend from guarded fetches — each must have a
    # sibling raw fetch artifact whose bound receipt still verifies, and an
    # existing output file must match its own merge receipt.  Reviewed files
    # predating the guard fail closed until the raw fetch is rerun under it.
    input_receipts = []
    raw_rows = []
    for path in REVIEWED:
        raw = path.with_name(path.name.replace("_reviewed", ""))
        if raw == path or not raw.exists():
            sys.exit(f"B04: no raw fetch artifact for reviewed file {path.name}")
        input_receipts.append(eval_protection.verify_artifact(raw))
        for raw_row in csv.DictReader(open(raw)):
            raw_rows.append((raw.name, raw_row))
    prior_manifest = {}
    if FINAL.exists():
        # The prior file is overwritten below, so its receipt cannot join the
        # new input chain — verification re-reads the path.  Carry its
        # verified inputs forward instead: existing rows keep their original
        # manifest provenance, which resolves through the grandparent chain.
        prior_receipt = eval_protection.verify_artifact(FINAL)
        input_receipts.extend(prior_receipt.get("input_receipts") or [])
        prior_manifest = _prior_manifest(FINAL)
    holdout = {_norm(r["merchant_raw"]) for r in csv.DictReader(open(HOLDOUT))}
    holdout.discard("")
    existing = list(csv.DictReader(open(FINAL))) if FINAL.exists() else []
    seen = {_fp(r) for r in existing}
    added, added_manifest = [], []
    skipped = {"holdout": 0, "dup": 0, "blank": 0}
    for path in REVIEWED:
        if not path.exists():
            sys.exit(f"missing {path}")
        raw_name = path.name.replace("_reviewed", "")
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
            source_rows = [row_ for name, row_ in raw_rows if name == raw_name]
            raw_row = _join_raw(r, source_rows)
            added.append(row)
            added_manifest.append(
                {
                    "identity": eval_protection.row_identity(raw_row),
                    "provenance": {
                        "source": raw_name,
                        "source_row_sha256": eval_protection.row_content_sha256(
                            raw_row
                        ),
                    },
                }
            )

    existing_manifest = []
    for r in existing:
        prior = prior_manifest.get(eval_protection.row_content_sha256(r))
        if prior is not None:
            # Verbatim copy: the row keeps the exact identity and the
            # source-row provenance it was issued with.
            existing_manifest.append(
                {"identity": prior["identity"], "provenance": prior["provenance"]}
            )
        else:
            # No bound manifest predates this row — it cannot prove which
            # guarded event produced it, so it stays unresolved and blocks
            # issuance until an identity-preserving rebuild.
            existing_manifest.append({"identity": None, "provenance": None})

    with open(FINAL, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(existing)
        w.writerows(added)
    eval_protection.write_artifact_receipt(
        FINAL, consumer="append_t6_residual_topup",
        purpose="supervised_training", input_receipts=input_receipts,
        manifest_identities=existing_manifest + added_manifest,
    )
    print(f"was {len(existing)}; added {len(added)}; now {len(existing) + len(added)}; "
          f"skipped {skipped}", file=sys.stderr)


if __name__ == "__main__":
    main()

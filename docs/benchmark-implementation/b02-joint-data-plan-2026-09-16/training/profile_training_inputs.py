#!/usr/bin/env python3
"""Build aggregate-only profiles of the current categoriser training inputs.

The script emits counts only: label, direction, blank-merchant status, provider,
and available provenance/quality fields. It never prints row values and refuses
the protected v5/v6 assets.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

RESEARCH = Path("/Users/carlosnoblejesus/Repos/raylo-transaction-categorisation")
OUT = Path("/private/tmp/txncat-training-augmentation-20260916")
PROTECTED_MARKERS = ("gold_transactions_v5_locked", "gold_transactions_v6_locked", "signing_key")


def guard(path: Path) -> None:
    lowered = str(path).lower().replace("-", "_")
    if any(marker in lowered for marker in PROTECTED_MARKERS):
        raise RuntimeError(f"protected path refused: {path.name}")


def inc_profile(
    profile: dict,
    label: str,
    direction: str,
    merchant: str,
    logical_input: str | None = None,
    **fields,
) -> None:
    label = label or "<missing_label>"
    direction = direction or "<missing_direction>"
    missing = "missing" if not (merchant or "").strip() else "present"
    profile["rows"] += 1
    profile["label"][label] += 1
    profile["direction"][direction] += 1
    profile["merchant_presence"][missing] += 1
    profile["label_direction"][f"{label}\t{direction}"] += 1
    profile["label_direction_missing"][f"{label}\t{direction}\t{missing}"] += 1
    if logical_input is not None:
        profile.setdefault("_input_labels", defaultdict(set))[logical_input].add(label)
        profile.setdefault("_label_inputs", defaultdict(set))[label].add(logical_input)
    for name, value in fields.items():
        if value is not None and value != "":
            profile.setdefault(name, Counter())[str(value)] += 1


def empty_profile() -> dict:
    return {
        "rows": 0,
        "label": Counter(),
        "direction": Counter(),
        "label_direction": Counter(),
        "label_direction_missing": Counter(),
        "merchant_presence": Counter(),
    }


def jsonl_profile(path: Path) -> dict:
    guard(path)
    profile = empty_profile()
    with path.open() as stream:
        for line in stream:
            record = json.loads(line)
            messages = record["messages"]
            user = next(m["content"] for m in messages if m["role"] == "user")
            label = next(m["content"] for m in messages if m["role"] == "assistant")
            fields = dict(line.split(": ", 1) for line in user.splitlines() if ": " in line)
            inc_profile(
                profile,
                label,
                fields.get("direction", ""),
                fields.get("merchant", ""),
                logical_input=user,
            )
    return profile


def csv_profile(path: Path) -> dict:
    guard(path)
    profile = empty_profile()
    with path.open(newline="") as stream:
        for row in csv.DictReader(stream):
            label = next(
                (
                    row.get(k, "")
                    for k in ("gold_leaf", "final_leaf", "target_leaf", "target")
                    if row.get(k)
                ),
                "",
            )
            direction = row.get("direction", "")
            merchant = next(
                (row.get(k, "") for k in ("merchant_raw", "merchant") if row.get(k) is not None),
                "",
            )
            resolution_source = (row.get("resolution_source") or "").lower()
            if not resolution_source:
                resolution_source_class = None
            elif "agent" in resolution_source or "consensus" in resolution_source:
                resolution_source_class = "agent_or_consensus"
            elif "human" in resolution_source:
                resolution_source_class = "human"
            elif "review" in resolution_source:
                resolution_source_class = "review_unspecified"
            else:
                resolution_source_class = "other"
            inc_profile(
                profile,
                label,
                direction,
                merchant,
                logical_input="\x1f".join(
                    str(row.get(k, ""))
                    for k in (
                        "merchant_raw",
                        "merchant",
                        "description_raw",
                        "description",
                        "amount",
                        "direction",
                    )
                ),
                source=row.get("source"),
                role=row.get("role"),
                tier=row.get("tier"),
                resolution_tier=row.get("resolution_tier"),
                resolution_source_class=resolution_source_class,
                provider=row.get("provider"),
            )
    return profile


def parquet_profile(path: Path) -> dict:
    guard(path)
    import pyarrow.parquet as pq

    profile = empty_profile()
    parquet = pq.ParquetFile(path)
    fields = set(parquet.schema_arrow.names)
    for batch in parquet.iter_batches(batch_size=65536):
        for row in batch.to_pylist():
            label = row.get("leaf", row.get("final_leaf", ""))
            direction = row.get("direction") or ("credit" if row.get("is_credit") else "debit")
            merchant = row.get("merchant", row.get("merchant_raw", ""))
            inc_profile(
                profile,
                str(label or ""),
                str(direction or ""),
                str(merchant or ""),
                logical_input=str(row.get("text", ""))
                if "text" in fields
                else "\x1f".join(
                    str(row.get(k, ""))
                    for k in (
                        "merchant",
                        "merchant_raw",
                        "description",
                        "description_raw",
                        "amount",
                        "direction",
                    )
                ),
                provider=row.get("provider"),
                tier=row.get("tier"),
                resolution_tier=row.get("resolution_tier"),
                stratum=row.get("stratum"),
            )
    return profile


def parquet_meta(path: Path) -> dict:
    guard(path)
    import pyarrow.parquet as pq

    parquet = pq.ParquetFile(path)
    return {
        "file": str(path),
        "rows": parquet.metadata.num_rows,
        "columns": parquet.schema_arrow.names,
        "fingerprint": source_fingerprint(path),
    }


def clean(value):
    if isinstance(value, Counter):
        return dict(sorted(value.items()))
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    return value


def finalize_profile(profile: dict) -> dict:
    input_labels = profile.pop("_input_labels", {})
    label_inputs = profile.pop("_label_inputs", {})
    profile["unique_logical_inputs"] = len(input_labels)
    profile["unique_input_label_pairs"] = sum(len(labels) for labels in input_labels.values())
    profile["conflicting_input_groups"] = sum(
        1 for labels in input_labels.values() if len(labels) > 1
    )
    profile["duplicate_rows_above_unique_input_label"] = (
        profile["rows"] - profile["unique_input_label_pairs"]
    )
    profile["unique_inputs_by_label"] = {
        label: len(inputs) for label, inputs in sorted(label_inputs.items())
    }
    return profile


def source_fingerprint(path: Path) -> dict:
    guard(path)
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return {"bytes": path.stat().st_size, "sha256": h.hexdigest()}


def main() -> None:
    global RESEARCH, OUT
    parser = argparse.ArgumentParser()
    parser.add_argument("--research", type=Path, default=RESEARCH)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    RESEARCH, OUT = args.research, args.output
    files = {
        "tuning_train": RESEARCH / "outputs/tuning_train.jsonl",
        "tuning_val": RESEARCH / "outputs/tuning_val.jsonl",
        "distillation_consensus": RESEARCH / "data/distillation_labels_consensus.parquet",
        "tier_a_gold": RESEARCH / "data/gold_transactions.csv",
        "tier_b_labels": RESEARCH / "data/production_labels_tranche4.csv",
        "leaf_topup": RESEARCH / "data/tuning_leaf_topup.csv",
        "credit_topup": RESEARCH / "data/tuning_credit_topup.csv",
        "risk_topup": RESEARCH / "data/tuning_risk_topup.csv",
    }
    profiles = {}
    for name, path in files.items():
        if not path.exists():
            profiles[name] = {"missing": True}
            continue
        print(f"profiling {name}", flush=True)
        before = source_fingerprint(path)
        if path.suffix == ".jsonl":
            profile = jsonl_profile(path)
        elif path.suffix == ".csv":
            profile = csv_profile(path)
        else:
            profile = parquet_profile(path)
        profile = finalize_profile(profile)
        profile["file"] = str(path)
        profile["fingerprint_before"] = before
        profile["fingerprint_after"] = source_fingerprint(path)
        if before != profile["fingerprint_after"]:
            raise RuntimeError(f"source changed while profiling: {path.name}")
        profiles[name] = clean(profile)
    artifact_paths = {
        "silver_labels": RESEARCH / "outputs/transformer/silver_labels.parquet",
        "distill_train_legacy": RESEARCH / "outputs/distill_train.parquet",
    }
    artifacts = {}
    for name, path in artifact_paths.items():
        if path.exists():
            artifacts[name] = parquet_meta(path)
    profiles["artifact_metadata"] = artifacts
    train_meta = {}
    for path in sorted(
        (RESEARCH / "outputs/distill_models").glob("txn_classifier_*/train_meta.json")
    ):
        try:
            train_meta[str(path.relative_to(RESEARCH))] = json.loads(path.read_text())
        except json.JSONDecodeError:
            train_meta[str(path.relative_to(RESEARCH))] = {"invalid_json": True}
    profiles["classifier_train_meta"] = train_meta
    profiles["profile_script"] = {
        "file": str(Path(__file__).resolve()),
        "sha256": source_fingerprint(Path(__file__))["sha256"],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "aggregate_profile.json").write_text(
        json.dumps(profiles, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps({name: p.get("rows", 0) for name, p in profiles.items()}, sort_keys=True))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Aggregate cached exposure screens for the identified engineering sample only."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path("/Users/carlosnoblejesus/.local/share/raylo-txncat/benchmark-engineering/2026-09-16")
OUT = Path("/private/tmp/txncat-linked-sample-exposure-20260916/aggregate.json")
EXPECTED = {
    "identity/identity-sidecar.jsonl": (
        "548fe996dae828558007d4842a8a77be4dc26bf38fb1d8c1fa3387d8e48f0426"
    ),
    "effective/event-exposure.jsonl": (
        "e8a4ad705a16473ddc3d81f40ee7f50ef9f667c0aabd8284a0cc9443966737b1"
    ),
    "merchants/merchant-exposure.jsonl": (
        "d5602554a8fa560d2a073ce6d77e3aa6d5f5152d7ca559aa01eb4fc111a3c89f"
    ),
}
SOURCE_SHA = "038006cdc28cebd2103b40316480eddf4a8229f3150a95715ca82dea5153d8f2"


def read(path: Path):
    with path.open() as fh:
        return [json.loads(line) for line in fh if line.strip()]


def main(archive: Path = BASE, output: Path = OUT) -> None:
    # Check 1: supplied artifact hashes and summary source hashes.
    for rel, expected in EXPECTED.items():
        h = hashlib.sha256((archive / rel).read_bytes()).hexdigest()
        if h != expected:
            raise ValueError(f"hash mismatch: {rel}")
        summary = json.loads((archive / (rel.split("/")[0] + "/summary.json")).read_text())
        if (
            summary.get("source_sha256") != SOURCE_SHA
            or summary.get("authorizes_consumption") is not False
        ):
            raise ValueError(f"invalid summary: {rel}")

    before = {rel: hashlib.sha256((archive / rel).read_bytes()).hexdigest() for rel in EXPECTED}
    identity = read(archive / "identity/identity-sidecar.jsonl")
    effective = read(archive / "effective/event-exposure.jsonl")
    merchants = read(archive / "merchants/merchant-exposure.jsonl")
    after = {rel: hashlib.sha256((archive / rel).read_bytes()).hexdigest() for rel in EXPECTED}
    if before != after:
        raise ValueError("artifact changed during read")

    # Check 2: exposure views are unique; identity is observation-level and may
    # repeat an event, but repeated identity evidence must not conflict.
    def pairs(rows):
        return [(r["event"], r["key_id"]) for r in rows]

    identity_statuses = defaultdict(set)
    identity_rows = defaultdict(list)
    for r in identity:
        identity_statuses[(r["event"], r["key_id"])].add(r["status"])
        identity_rows[(r["event"], r["key_id"])].append(r)
    if not all(len(statuses) == 1 for statuses in identity_statuses.values()):
        raise ValueError("mixed identity status evidence")
    if len(set(pairs(effective))) != len(effective) or len(set(pairs(merchants))) != len(merchants):
        raise ValueError("duplicate exposure evidence")
    if set(identity_statuses) != set(pairs(effective)) or set(identity_statuses) != set(
        pairs(merchants)
    ):
        raise ValueError("key coverage mismatch")
    if len({r.get("key_id") for rows in (identity, effective, merchants) for r in rows}) != 1:
        raise ValueError("mixed key_id evidence")
    if any(
        r.get("authorizes_consumption") is not False
        for rows in (identity, effective, merchants)
        for r in rows
    ):
        raise ValueError("consumption-authorizing artifact")

    # Check 3: linked identity evidence is exactly the two permitted statuses.
    linked_statuses = {"direct_customer_link", "recovered_current_checkout_link"}
    linked = [
        k for k, statuses in identity_statuses.items() if next(iter(statuses)) in linked_statuses
    ]
    for k in linked:
        rows = identity_rows[k]
        customers = {r["direct_customer"] for r in rows}
        if len(customers) != 1 or not next(iter(customers)):
            raise ValueError("missing/conflicting linked customer")
        if any(set(r["blocking_customers"]) - customers for r in rows):
            raise ValueError("blocking customer conflict")

    eff_by = {(r["event"], r["key_id"]): r["matches"] for r in effective}
    mer_by = {(r["event"], r["key_id"]): r for r in merchants}
    keys = linked
    projections = ("token48", "hinge_sparse", "surface_fold")
    known_input = {p: set() for p in projections}
    union_input = set()
    for k in keys:
        matches = eff_by[k]
        for p in projections:
            if matches.get(p):
                known_input[p].add(k)
                union_input.add(k)
    # Check 4: all linked-only screen keys stay inside the shared event universe.
    if not union_input <= set(keys):
        raise ValueError("input coverage escaped linked scope")
    merchant_counts = Counter()
    cross = defaultdict(Counter)
    for k in keys:
        row = mer_by[k]
        if not row["merchant_present"]:
            category = "blank"
        elif row["known_name_sources"]:
            category = "known_name"
        else:
            category = "unmatched_name"
        merchant_counts[category] += 1
        cross["known_input_union" if k in union_input else "no_known_input"][category] += 1
    # Check 5: aggregate partitions reconcile to linked population.
    if sum(merchant_counts.values()) != len(linked) or sum(
        sum(v.values()) for v in cross.values()
    ) != len(linked):
        raise ValueError("aggregate partition mismatch")
    output.write_text(
        json.dumps(
            {
                "scope": "identified_portion_of_private_100_request_engineering_sample",
                "authorizes_consumption": False,
                "adapter_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "source_sha256": SOURCE_SHA,
                "artifact_sha256": EXPECTED,
                "source_observations": len(identity),
                "source_distinct_events": len(identity_statuses),
                "linked_observations": sum(len(identity_rows[k]) for k in linked),
                "linked_distinct_events": len(linked),
                "linked_status_counts": dict(
                    Counter(next(iter(identity_statuses[k])) for k in linked)
                ),
                "known_input_projection_counts": {p: len(v) for p, v in known_input.items()},
                "known_input_union_count": len(union_input),
                "merchant_counts": dict(merchant_counts),
                "known_input_vs_merchant": {k: dict(v) for k, v in cross.items()},
                "limitations": [
                    "100-request sample; not a population estimate or admission decision",
                    "unmatched is not proven unseen",
                    "no IDs or contact strings exported",
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, default=BASE)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    main(args.archive, args.output)

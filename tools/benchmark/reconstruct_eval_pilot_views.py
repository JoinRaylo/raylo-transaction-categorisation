"""Reconstruct per-row primary views for the recovered 500-row eval pilot.

The approved 2026-09-18 pilot's per-row ``primary_view``/``views`` assignments
were lost with ``/private/tmp``.  They are deterministic: the profiler's opaque
eligibility flags (``input_sources``, merchant evidence) plus
``build_eval_pilot.allocate_pilot`` (seed ``eval-pilot-v1``, budgets
250/150/100, whole-customer blocks) reproduce the assignment when run over the
same 500 candidate rows in the original draw order.

This script reuses the production helpers rather than reimplementing them:
``benchmark_profile_candidates._load_artifacts``/``_candidate_keys``/
``_screen_inputs``/``_screen_merchants`` for the exposure screens, and
``build_eval_pilot.PilotCandidate``/``allocate_pilot``/``_payload`` for the
allocation and payload shape.  ``source_snapshot_sha256`` is pinned to the
original draw's result hash (``PINNED_CANDIDATE_RESULT_SHA256``) so pilot IDs,
opaque candidate IDs and row digests match the original artifacts.

The original draw order is recovered by re-sorting on the pinned extract's
``ORDER BY TO_HEX(SHA256(@seed || ':' || account_id || ':' || transaction_id))``
with seed ``b05-pilot-source-v1``.  No provider call, no BigQuery, no label;
nothing here authorizes consumption.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from collections import Counter
from pathlib import Path

import build_eval_pilot
from benchmark_build_index import private_key
from benchmark_profile_candidates import (
    _candidate_keys,
    _load_artifacts,
    _screen_inputs,
    _screen_merchants,
)
from raylo_txncat.benchmark_exposure import ExposureIndex, file_sha256
from raylo_txncat.dictionary import normalise_merchant
from raylo_txncat.hashing import canonical_json, strict_json_loads
from recover_eval_pilot_membership import (
    PINNED_CANDIDATE_RESULT_SHA256,
    canonical_pilot_id,
)

DRAW_SEED = "b05-pilot-source-v1"
DRAW_LIMIT = 5000
BUDGETS = {"representative": 250, "unseen_input": 150, "unfamiliar_merchant": 100}
ALLOC_SEED = "eval-pilot-v1"

EXPECTED = {
    "primary_views": {"representative": 250, "unseen_input": 150, "unfamiliar_merchant": 100},
    "pilot_customers": 464,
    "view_tags": {"representative": 500, "unseen_input": 389, "unfamiliar_merchant": 156},
    "primary_view_historical_input_overlap": {
        "representative": 111,
        "unseen_input": 0,
        "unfamiliar_merchant": 0,
    },
}


def _draw_order(row: dict) -> tuple:
    """Original extract ORDER BY key (benchmark_candidate_extract.sql tail)."""
    digest = hashlib.sha256(
        f"{DRAW_SEED}:{row['account_id']}:{row['transaction_id']}".encode()
    ).hexdigest()
    return digest, row["account_id"], row["transaction_id"]


def _load_recovered(candidates_dir: Path) -> list[dict]:
    receipt = strict_json_loads((candidates_dir / "receipt.json").read_bytes())
    if (
        receipt.get("schema_version") != "benchmark-eval-pilot-recovery-v1"
        or receipt.get("executed") is not True
        or receipt.get("pinned_candidate_result_sha256") != PINNED_CANDIDATE_RESULT_SHA256
        or receipt.get("missing_pilot_ids") != 0
        or receipt.get("authorizes_consumption") is not False
    ):
        raise ValueError("recovery receipt is outside the pinned pilot contract")
    rows = [
        strict_json_loads(line)
        for line in (candidates_dir / "candidates.jsonl").read_bytes().splitlines()
    ]
    if len(rows) != 500 or receipt["result_rows"] != 500:
        raise ValueError("recovered candidate count is incomplete")
    events = set()
    for row in rows:
        required = (
            "account_id",
            "transaction_id",
            "customer_id",
            "assessment_id",
            "checkout_id",
            "user_id",
        )
        if any(type(row.get(field)) is not str or not row[field] for field in required):
            raise ValueError("recovered row is missing linked identity")
        link_counts = (
            "assessment_checkout_count",
            "checkout_user_count",
            "user_customer_count",
            "customer_record_count",
        )
        if any(type(row.get(field)) is not int or row[field] != 1 for field in link_counts):
            raise ValueError("recovered row is not backed by unique current links")
        event = (row["account_id"], row["transaction_id"])
        if event in events:
            raise ValueError("recovered draw contains duplicate events")
        events.add(event)
        if canonical_pilot_id(
            row["account_id"], row["transaction_id"], PINNED_CANDIDATE_RESULT_SHA256
        ) != row.get("pilot_id"):
            raise ValueError("recovered pilot_id does not match the pinned derivation")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "candidates",
        "research",
        "inventory",
        "index",
        "key-file",
        "legacy",
        "comparison",
        "output",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)

    rows = _load_recovered(args.candidates)
    rows.sort(key=_draw_order)
    inventory = strict_json_loads(args.inventory.read_bytes())["files"]
    index_receipt = strict_json_loads((args.index / "receipt.json").read_bytes())
    key = private_key(args.key_file, index_receipt["key_id"])
    index = ExposureIndex(
        args.index / "inputs.sqlite",
        expected_sha256=index_receipt["database_sha256"],
        key=key,
    )
    try:
        tokenizer, vectorizer = _load_artifacts(args.research, inventory)
        heads, events, projections, values = _candidate_keys(rows, key, tokenizer, vectorizer)
        input_hits, input_source_rows = _screen_inputs(
            args.research, inventory, values, tokenizer, vectorizer
        )
        merchant_hits, merchant_source_rows = _screen_merchants(
            args.research, inventory, args.legacy, rows
        )
        pool = []
        for index_number, row in enumerate(rows):
            input_sources = set()
            for projection in projections[index_number]:
                input_sources.update(index.lookup(projection)["sources"])
            for name in ("token48", "surface_fold", "hinge_sparse"):
                for source, found in input_hits[name].items():
                    if index_number in found:
                        input_sources.add(source)
            merchant = normalise_merchant(row.get("merchant_name"))
            opaque = {
                "candidate_id": hashlib.sha256(
                    canonical_json(
                        {
                            "source": PINNED_CANDIDATE_RESULT_SHA256,
                            "event": events[index_number],
                        }
                    )
                ).hexdigest(),
                "source_snapshot_sha256": PINNED_CANDIDATE_RESULT_SHA256,
                "observation": events[index_number],
                "event_aliases": (),
                "account": key.token(
                    "account", {"namespace": "plaid", "account": row["account_id"]}
                ),
                "customer": key.token(
                    "customer", {"namespace": "raylo", "customer": row["customer_id"]}
                ),
                "assignment_block": key.token(
                    "customer",
                    {
                        "namespace": "raylo",
                        "customer": row["customer_id"],
                        "policy": "customer-block-v1",
                    },
                ),
                "input_sources": sorted(input_sources),
                "merchant_present": bool(merchant),
                "merchant_known_sources": sorted(merchant_hits[index_number]),
                "source_stratum": row.get("source_stratum", "unknown"),
                "authorizes_consumption": False,
            }
            pool.append(build_eval_pilot.PilotCandidate(index=index_number, row=row, opaque=opaque))
    finally:
        index.close()

    build_eval_pilot._validate_customer_token_mapping(pool)
    assignments = build_eval_pilot.allocate_pilot(pool, budgets=BUDGETS, seed=ALLOC_SEED)
    by_index = {candidate.index: candidate for candidate in pool}

    args.output.mkdir(mode=0o700, parents=False, exist_ok=False)
    annotations, memberships, view_rows = [], [], []
    for index, primary in sorted(assignments.items()):
        candidate = by_index[index]
        annotation, membership = build_eval_pilot._payload(
            candidate, primary, PINNED_CANDIDATE_RESULT_SHA256
        )
        annotations.append(annotation)
        memberships.append(membership)
        view_rows.append(
            {
                "pilot_id": annotation["pilot_id"],
                "primary_view": primary,
                "views": annotation["views"],
                "unseen": candidate.unseen,
                "unfamiliar": candidate.unfamiliar,
                "known_input_match": not candidate.unseen,
            }
        )

    views_path = args.output / "views.jsonl"
    build_eval_pilot._write_private(
        views_path,
        b"".join(build_eval_pilot._canonical(row) + b"\n" for row in view_rows),
    )
    pilot_path = args.output / "pilot.jsonl"
    build_eval_pilot._write_private(
        pilot_path,
        b"".join(build_eval_pilot._canonical(row) + b"\n" for row in annotations),
    )
    membership_path = args.output / "membership.csv"
    with membership_path.open("x", newline="", encoding="utf-8") as stream:
        os.fchmod(stream.fileno(), 0o600)
        writer = csv.DictWriter(
            stream, fieldnames=build_eval_pilot.MEMBERSHIP_FIELDS, lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(memberships)
        stream.flush()
        os.fsync(stream.fileno())

    customer_counts = Counter(row["customer_id"] for row in memberships)
    primary_counts = Counter(row["primary_view"] for row in annotations)
    tag_counts = Counter(v for row in annotations for v in row["views"])
    overlap = Counter(
        primary for index, primary in assignments.items() if not by_index[index].unseen
    )
    strata = Counter(row["source_stratum"] for row in annotations)
    fingerprint = {
        "primary_views": dict(sorted(primary_counts.items())),
        "pilot_customers": len(customer_counts),
        "max_rows_per_customer": max(customer_counts.values()),
        "view_tags": dict(sorted(tag_counts.items())),
        "unfamiliar_subset_of_unseen": all(
            candidate.unseen for candidate in pool if candidate.unfamiliar
        ),
        "primary_view_historical_input_overlap": {
            view: overlap[view] for view in build_eval_pilot.VIEW_ORDER
        },
        "pilot_sha256": file_sha256(pilot_path),
        "membership_sha256": file_sha256(membership_path),
        "source_strata": dict(sorted(strata.items())),
    }
    summary = {
        "schema_version": "benchmark-eval-pilot-view-reconstruction-v1",
        "purpose": "re_identify_existing_v2_eval_pilot_view_assignment",
        "authorizes_consumption": False,
        "source_snapshot_sha256": PINNED_CANDIDATE_RESULT_SHA256,
        "draw_seed": DRAW_SEED,
        "allocation_seed": ALLOC_SEED,
        "budgets": BUDGETS,
        "candidate_rows": len(rows),
        "fingerprint": fingerprint,
        "expected_fingerprint": EXPECTED,
        "input_source_rows": input_source_rows,
        "merchant_source_rows": merchant_source_rows,
    }
    summary_path = args.output / "summary.json"
    build_eval_pilot._write_private(
        summary_path, json.dumps(summary, indent=2, sort_keys=True).encode() + b"\n"
    )

    receipt = {
        "schema_version": "benchmark-eval-pilot-view-reconstruction-receipt-v1",
        "authorizes_consumption": False,
        "narratives_printed": False,
        "candidates_sha256": file_sha256(args.candidates / "candidates.jsonl"),
        "recovery_receipt_sha256": file_sha256(args.candidates / "receipt.json"),
        "index_receipt_sha256": file_sha256(args.index / "receipt.json"),
        "index_database_sha256": index_receipt["database_sha256"],
        "inventory_sha256": file_sha256(args.inventory),
        "legacy_summary_sha256": file_sha256(args.legacy / "summary.json"),
        "comparison_sha256": file_sha256(args.comparison),
        "reconstructor_sha256": file_sha256(Path(__file__)),
        "views_sha256": file_sha256(views_path),
        "pilot_sha256": fingerprint["pilot_sha256"],
        "membership_sha256": fingerprint["membership_sha256"],
        "summary_sha256": file_sha256(summary_path),
    }
    build_eval_pilot._write_private(
        args.output / "receipt.json",
        json.dumps(receipt, indent=2, sort_keys=True).encode() + b"\n",
    )
    print(json.dumps(fingerprint, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

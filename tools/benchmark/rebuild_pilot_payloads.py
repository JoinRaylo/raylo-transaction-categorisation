"""Rebuild identifier-free annotation payloads for the recovered 500-row pilot.

Reads the recovered candidate rows (which carry source identifiers) and emits
the annotation payload ``build_eval_pilot._payload`` produces, minus
``primary_view``/``views`` (Task B has not established them yet).  The field
logic is extracted verbatim from ``build_eval_pilot.py`` lines 459-498 because
``_payload`` needs a ``PilotCandidate`` object that requires context not
present in the recovery files.  ``pilot_id`` is recomputed with the pinned
candidate snapshot via ``canonical_pilot_id`` and asserted equal to the row's
``pilot_id``.

The output contains no source identifiers; the script verifies that no
``account_id``/``transaction_id``/``customer_id``/``assessment_id`` value from
the candidate rows appears anywhere in the payload bytes.  Nothing here
authorizes consumption.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path

from recover_eval_pilot_membership import (
    PINNED_CANDIDATE_RESULT_SHA256,
    canonical_pilot_id,
)

IDENTIFIER_FIELDS = ("account_id", "transaction_id", "customer_id", "assessment_id")


def _annotation(row: dict) -> dict:
    """Field logic verbatim from build_eval_pilot.py:459-498 (`_payload`),
    excluding primary_view/views which Task B has not established."""
    amount = row.get("amount")
    try:
        absolute_amount = abs(float(amount))
    except (TypeError, ValueError):
        raise ValueError("candidate amount is invalid") from None
    if not math.isfinite(absolute_amount):
        raise ValueError("candidate amount is non-finite")
    direction = row.get("direction")
    if direction not in {"credit", "debit"}:
        raise ValueError("candidate direction is invalid")
    description = row.get("description")
    if description is None:
        description = row.get("transaction_name")
    if description is None:
        description = ""
    if type(description) is not str:
        raise ValueError("candidate description is invalid")
    merchant = row.get("merchant_name") or ""
    if type(merchant) is not str:
        raise ValueError("candidate merchant is invalid")
    pilot_id = canonical_pilot_id(
        row["account_id"], row["transaction_id"], PINNED_CANDIDATE_RESULT_SHA256
    )
    if pilot_id != row.get("pilot_id"):
        raise ValueError("recovered pilot_id does not match the pinned derivation")
    return {
        "schema_version": "txncat-private-eval-pilot-item-v1",
        "pilot_id": pilot_id,
        "merchant": merchant,
        "description": description,
        "amount": absolute_amount,
        "direction": direction,
        "source_stratum": row.get("source_stratum", "unknown"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)

    rows = [json.loads(line) for line in args.candidates.read_text().splitlines()]
    if len(rows) != 500:
        raise ValueError(f"expected 500 candidate rows, found {len(rows)}")

    identifier_values: set[str] = set()
    for row in rows:
        for field in IDENTIFIER_FIELDS:
            value = row.get(field)
            if value is not None:
                identifier_values.add(str(value))

    items = [_annotation(row) for row in rows]
    if len({item["pilot_id"] for item in items}) != 500:
        raise ValueError("duplicate pilot_id in recovered candidates")

    args.output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(args.output.parent, 0o700)
    with args.output.open("x") as stream:
        for item in sorted(items, key=lambda i: i["pilot_id"]):
            stream.write(json.dumps(item, sort_keys=True) + "\n")
    os.chmod(args.output, 0o600)

    payload_bytes = args.output.read_bytes()
    leaked = sum(1 for v in identifier_values if v.encode() in payload_bytes)
    field_leaks = [f for f in IDENTIFIER_FIELDS if f.encode() in payload_bytes]
    directions = {}
    for item in items:
        directions[item["direction"]] = directions.get(item["direction"], 0) + 1
    report = {
        "schema_version": "benchmark-pilot-payload-rebuild-v1",
        "authorizes_consumption": False,
        "rows": len(items),
        "direction_counts": directions,
        "blank_merchant": sum(1 for i in items if not i["merchant"]),
        "empty_description": sum(1 for i in items if not i["description"]),
        "payload_sha256": hashlib.sha256(payload_bytes).hexdigest(),
        "identifier_field_names_present": field_leaks,
        "identifier_values_present_in_payload": leaked,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    if leaked or field_leaks:
        raise ValueError("identifier material detected in payload bytes")


if __name__ == "__main__":
    main()

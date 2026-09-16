"""Aggregate private source readiness and indexed input presence; no admission.

Every request observation remains in the immutable extract. The event view below
chooses the latest recorded report/request observation only for engineering counts;
provider pending/reconnection aliases and conflicting events still need governance.
"""

import argparse
import os
from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from benchmark_build_index import private_key
from raylo_txncat.benchmark import observation_key, project_head
from raylo_txncat.benchmark_exposure import ExposureIndex, file_sha256
from raylo_txncat.classifier_types import ClassifierInput
from raylo_txncat.hashing import canonical_json, strict_json_loads

REQUIRED_FIELDS = (
    "external_request_id",
    "source_row_id",
    "source_ingested_at",
    "request_created_at",
    "request_updated_at",
    "assessment_id",
    "report_id",
    "report_generated_at",
    "item_id",
    "institution_id",
    "account_id",
    "transaction_id",
    "transaction_date",
    "amount",
    "account_currency",
    "transaction_currency",
    "pending",
    "pending_json_type",
    "pending_transaction_id",
    "pending_alias_json_type",
    "customer_id",
    "user_id",
)
CONTENT_FIELDS = (
    "transaction_date",
    "date_transacted",
    "amount",
    "transaction_currency",
    "pending",
    "pending_transaction_id",
    "merchant_name",
    "transaction_name",
    "description",
    "primary_credit_category",
    "detailed_credit_category",
    "legacy_categories",
)


def head_for_row(row):
    """Serving-equivalent heads; missing API context is *not* filled to build a wire row."""
    raw = row["amount"]
    if not isinstance(raw, str) or not raw:
        raise ValueError("missing decimal amount")
    amount = Decimal(raw)
    if not amount.is_finite():
        raise ValueError("invalid decimal amount")
    for field in ("merchant_name", "description", "transaction_name"):
        if row[field] is not None and not isinstance(row[field], str):
            raise ValueError("invalid source text")
    return ClassifierInput.from_research(
        {
            "merchant_raw": row["merchant_name"],
            "description_raw": row["description"]
            if row["description"] is not None
            else row["transaction_name"],
            "amount": raw,
            "direction": "credit" if amount < 0 else "debit",
        }
    )


def timestamp(value):
    parsed = datetime.fromisoformat(value)
    # Request DATETIME fields are source UTC, as in the existing exporter.
    from datetime import UTC

    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def profile(rows, key, index=None):
    observations = 0
    missing, presence, direction = Counter(), Counter(), Counter()
    requests, reports, accounts, users, customers, days = set(), set(), set(), set(), set(), set()
    selected, signatures = {}, defaultdict(set)
    account_customers, account_users = defaultdict(set), defaultdict(set)
    unidentified = 0
    for row in rows:
        observations += 1
        if not set(REQUIRED_FIELDS) <= set(row):
            raise ValueError("incomplete source schema")
        missing.update(f for f in REQUIRED_FIELDS if row[f] is None or row[f] == "")
        for field, values in (
            ("external_request_id", requests),
            ("report_id", reports),
            ("account_id", accounts),
            ("user_id", users),
            ("customer_id", customers),
        ):
            if row[field]:
                values.add(row[field])
        if row["transaction_date"]:
            days.add(date.fromisoformat(row["transaction_date"]))
        presence["pending_true"] += (
            row["pending"] == "true" and row["pending_json_type"] == "boolean"
        )
        presence["pending_false"] += (
            row["pending"] == "false" and row["pending_json_type"] == "boolean"
        )
        presence["pending_invalid_type"] += row["pending_json_type"] not in {
            None,
            "null",
            "boolean",
        }
        presence["pending_alias_field_present"] += row["pending_alias_json_type"] is not None
        presence["pending_alias_nonnull"] += bool(row["pending_transaction_id"])
        presence["linked_user_and_customer"] += bool(row["user_id"] and row["customer_id"])
        presence["business_checkout"] += row["is_business_checkout"] is True
        presence["unknown_business_scope"] += row["is_business_checkout"] is None
        presence["blank_merchant"] += not (row["merchant_name"] or "").strip()
        presence["currency_mismatch"] += bool(
            row["transaction_currency"]
            and row["account_currency"]
            and row["transaction_currency"] != row["account_currency"]
        )
        if not row["account_id"] or not row["transaction_id"]:
            unidentified += 1
            continue
        for field, groups in (("customer_id", account_customers), ("user_id", account_users)):
            if row[field]:
                groups[row["account_id"]].add(row[field])
        event = observation_key(
            key,
            namespace="plaid",
            account_id=row["account_id"],
            transaction_id=row["transaction_id"],
        )
        # Source IDs are retained privately only as deterministic tie breakers.
        rank = (
            timestamp(row["report_generated_at"] or row["request_created_at"]),
            timestamp(row["request_updated_at"] or row["request_created_at"]),
            timestamp(row["source_ingested_at"]),
            row["external_request_id"],
            row["source_row_id"],
            *(
                int(row[f])
                for f in ("node_offset", "item_offset", "account_offset", "transaction_offset")
            ),
        )
        signatures[event].add(
            key.token("input", {"source_event_content": {f: row[f] for f in CONTENT_FIELDS}})
        )
        if event not in selected or rank > selected[event][0]:
            selected[event] = (rank, row)
    exposure, head_errors, selected_presence = Counter(), 0, Counter()
    matched_events = set()
    for event, (_, row) in selected.items():
        selected_presence["content_conflict"] += len(signatures[event]) > 1
        selected_presence["linked_user_and_customer"] += bool(row["user_id"] and row["customer_id"])
        selected_presence["blank_merchant"] += not (row["merchant_name"] or "").strip()
        try:
            head = head_for_row(row)
            direction["credit" if head.is_credit else "debit"] += 1
            projections = project_head(head, key)
        except (ValueError, TypeError, ArithmeticError):
            head_errors += 1
            continue
        if index:
            for projection in projections:
                hit = index.lookup(projection)
                exposure[f"{projection.version}:{hit['status']}"] += 1
                for source in hit["sources"]:
                    exposure[f"{projection.version}:{source}"] += 1
                if hit["status"] == "known_presence":
                    matched_events.add(event)
    return {
        "schema_version": "benchmark-source-profile-v1",
        "purpose": "engineering_source_readiness_not_benchmark_sample",
        "observation_rows": observations,
        "distinct_requests": len(requests),
        "distinct_reports": len(reports),
        "distinct_accounts": len(accounts),
        "distinct_users": len(users),
        "distinct_customers": len(customers),
        "transaction_date_min": str(min(days)) if days else None,
        "transaction_date_max": str(max(days)) if days else None,
        "observation_missing_fields": {f: missing[f] for f in REQUIRED_FIELDS},
        "observation_presence": dict(sorted(presence.items())),
        "observations_missing_event_key": unidentified,
        "distinct_account_transaction_events": len(selected),
        "repeat_observations": observations - unidentified - len(selected),
        "accounts_multiple_customers": sum(len(v) > 1 for v in account_customers.values()),
        "accounts_multiple_users": sum(len(v) > 1 for v in account_users.values()),
        "selected_event_presence": dict(sorted(selected_presence.items())),
        "selected_event_direction": dict(sorted(direction.items())),
        "head_projection_errors": head_errors,
        "indexed_input_presence": dict(sorted(exposure.items())),
        "events_with_any_known_indexed_input": len(matched_events) if index else None,
        "admission": {
            "assessed": False,
            "certified_benchmark_rows": None,
            "authorizes_consumption": False,
            "blockers": [
                "historical_event_customer_identity_incomplete",
                "pending_reconnection_aliases_unverified",
                "effective_token_sparse_near_duplicate_coverage_incomplete",
                "merchant_family_history_incomplete",
                "legacy_protected_memberships_unmigrated",
                "durable_reservation_and_consumer_gates_pending",
            ],
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--key-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    source_receipt = strict_json_loads((args.source / "receipt.json").read_bytes())
    index_receipt = strict_json_loads((args.index / "receipt.json").read_bytes())
    path = args.source / "observations.jsonl"
    if not source_receipt["executed"] or file_sha256(path) != source_receipt["result_sha256"]:
        raise ValueError("incomplete or changed source extract")
    key = private_key(args.key_file, index_receipt["key_id"])
    index = ExposureIndex(
        args.index / "inputs.sqlite", expected_sha256=index_receipt["database_sha256"], key=key
    )
    try:
        with path.open("rb") as stream:
            result = profile((strict_json_loads(line) for line in stream), key, index)
        if (
            result["observation_rows"] != source_receipt["result_rows"]
            or file_sha256(path) != source_receipt["result_sha256"]
        ):
            raise ValueError("incomplete or changing source observations")
        result.update(
            source_sha256=source_receipt["result_sha256"],
            database_sha256=index_receipt["database_sha256"],
            source_receipt_sha256=file_sha256(args.source / "receipt.json"),
            index_receipt_sha256=file_sha256(args.index / "receipt.json"),
            adapter_sha256=file_sha256(Path(__file__)),
        )
        with args.output.open("xb") as stream:
            stream.write(canonical_json(result) + b"\n")
        print(f"Profiled {result['observation_rows']:,} observations; admission remains blocked.")
    finally:
        index.close()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("Source profiling failed; no eligibility claim may be made.") from None

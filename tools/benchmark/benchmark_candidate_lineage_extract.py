"""Extract private account/report lineage for a candidate admission draw.

This is evidence collection only. It never reserves, labels, authorizes or
exports a benchmark set. It deliberately records when the available source
tables cannot prove pending/reconnect aliases or reviewed merchant families.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from benchmark_extract import MAX_BYTES, encode, metadata

PROJECT = "raylo-production"
LOCATION = "EU"
MAX_LINEAGE_ROWS = 500_000
LINEAGE_SQL_NAME = "benchmark_candidate_lineage.sql"
LINEAGE_SCHEMA = (
    "source_kind",
    "observation_at",
    "assessment_id",
    "account_id",
    "transaction_id",
    "transaction_date",
    "date_transacted",
    "amount",
    "merchant_name",
    "transaction_name",
    "description",
    "asset_report_id",
    "report_date_generated",
    "client_report_id",
    "is_pending",
    "pending_transaction_id",
    "source_customer_id",
    "linked_customer_id",
    "checkout_count",
    "user_count",
    "customer_count",
    "customer_record_count",
)
EXPECTED_HISTORY_FLAGS = frozenset(
    {
        "event_aliases_verified",
        "family_history_complete",
        "identity_history_complete",
        "input_history_complete",
        "legacy_index_complete",
    }
)
ACCEPTED_CANDIDATE_SCHEMAS = frozenset(
    {"benchmark-candidate-extract-v1", "benchmark-candidate-frame-extract-v1"}
)
ACCEPTED_PROFILE_SCHEMAS = frozenset(
    {"benchmark-admission-profile-v1", "benchmark-admission-profile-v2"}
)


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"{path} is not a JSON object")
    return value


def _load_candidates(directory: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    receipt = _load_json(directory / "receipt.json")
    candidate_path = directory / "candidates.jsonl"
    if (
        receipt.get("schema_version") not in ACCEPTED_CANDIDATE_SCHEMAS
        or receipt.get("project") != PROJECT
        or receipt.get("location") != LOCATION
        or receipt.get("statement_type") != "SELECT"
        or receipt.get("source_kind") != "customer_linked_plaid_materialized"
        or receipt.get("executed") is not True
        or receipt.get("authorizes_consumption") is not False
        or digest(candidate_path) != receipt.get("result_sha256")
    ):
        raise ValueError(
            "candidate draw is incomplete or outside the linked-only contract"
        )
    rows: list[dict[str, Any]] = []
    events: set[tuple[str, str]] = set()
    with candidate_path.open() as stream:
        for line in stream:
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError("candidate row is not an object")
            required = ("account_id", "transaction_id", "customer_id")
            if any(
                type(row.get(field)) is not str or not row[field] for field in required
            ):
                raise ValueError("candidate row is missing an identity field")
            event = (row["account_id"], row["transaction_id"])
            if event in events:
                raise ValueError("candidate draw contains a duplicate event")
            events.add(event)
            rows.append(row)
    if len(rows) != receipt.get("result_rows") or not rows:
        raise ValueError("candidate row count does not match its receipt")
    return receipt, rows


def _validate_profile(profile_path: Path, candidate_receipt: dict[str, Any]) -> str:
    profile = _load_json(profile_path)
    history_flags = profile.get("history_flags")
    if (
        profile.get("schema_version") not in ACCEPTED_PROFILE_SCHEMAS
        or profile.get("source_snapshot_sha256")
        != candidate_receipt.get("result_sha256")
        or profile.get("authorizes_consumption") is not False
        or type(profile.get("rows_reserved_or_labelled")) is not int
        or profile.get("rows_reserved_or_labelled") != 0
        or type(history_flags) is not dict
        or set(history_flags) != EXPECTED_HISTORY_FLAGS
        or any(
            type(value) is not bool or value is not False
            for value in history_flags.values()
        )
    ):
        raise ValueError("candidate profile is not bound to this non-authorizing draw")
    return digest(profile_path)


def _validate_lineage(row: dict[str, Any]) -> None:
    if set(row) != set(LINEAGE_SCHEMA):
        raise ValueError("lineage row schema changed")
    for field in ("source_kind", "account_id", "transaction_id"):
        if not isinstance(row[field], str) or not row[field]:
            raise ValueError("lineage identity field is incomplete")
    if row["source_kind"] not in {"current_materialized", "plaid_materialized_history"}:
        raise ValueError("unexpected lineage source")
    if row["is_pending"] is not None and type(row["is_pending"]) is not bool:
        raise ValueError("lineage pending state is not a boolean or null")
    if row["pending_transaction_id"] is not None:
        raise ValueError("unexpected pending alias data was returned")
    if row["source_kind"] == "current_materialized" and (
        type(row["linked_customer_id"]) is not str or not row["linked_customer_id"]
    ):
        raise ValueError("current lineage row is missing its uniquely linked customer")


def _content_signature(row: dict[str, Any]) -> str:
    content = {
        field: row[field]
        for field in (
            "transaction_date",
            "amount",
            "merchant_name",
            "transaction_name",
            "description",
        )
    }
    return hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()


def _source_metadata_signature(row: dict[str, Any]) -> str:
    metadata_fields = {
        field: row[field]
        for field in (
            "source_kind",
            "date_transacted",
            "is_pending",
            "asset_report_id",
            "report_date_generated",
            "client_report_id",
            "assessment_id",
        )
    }
    return hashlib.sha256(
        json.dumps(metadata_fields, sort_keys=True).encode()
    ).hexdigest()


def _validate_candidate_lineage(
    candidates: list[dict[str, Any]], lineage: list[dict[str, Any]]
) -> None:
    candidate_customers = {
        (row["account_id"], row["transaction_id"]): row["customer_id"]
        for row in candidates
    }
    lineage_events = {(row["account_id"], row["transaction_id"]) for row in lineage}
    unexpected_events = lineage_events - set(candidate_customers)
    if unexpected_events:
        raise ValueError("lineage contains an unexpected candidate event pair")
    current_events = {
        (row["account_id"], row["transaction_id"])
        for row in lineage
        if row["source_kind"] == "current_materialized"
    }
    if current_events != set(candidate_customers):
        raise ValueError(
            "current lineage does not cover the exact candidate event pairs"
        )
    for row in lineage:
        if row["source_kind"] == "current_materialized":
            event = (row["account_id"], row["transaction_id"])
            if row["linked_customer_id"] != candidate_customers[event]:
                raise ValueError(
                    "current lineage customer does not match the candidate"
                )


def summarise(
    candidates: list[dict[str, Any]], lineage: list[dict[str, Any]], profile_sha256: str
) -> dict[str, Any]:
    candidate_events = {
        (row["account_id"], row["transaction_id"]): row for row in candidates
    }
    by_account: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in lineage:
        _validate_lineage(row)
        by_account[row["account_id"]].append(row)
    _validate_candidate_lineage(candidates, lineage)

    account_customer_sets: dict[str, set[str]] = {}
    event_observations: dict[tuple[str, str], list[dict[str, Any]]] = {}
    source_counts = Counter(row["source_kind"] for row in lineage)
    pending_counts = Counter()
    duplicate_events = 0
    content_variant_events = 0
    source_metadata_variant_events = 0
    pending_posted_pairs = 0
    accounts_with_customer_conflict = 0
    candidate_events_with_history = 0
    candidate_events_with_multiple_reports = 0
    candidate_events_with_pending_state = 0
    account_history_rows = Counter()
    customer_accounts: defaultdict[str, set[str]] = defaultdict(set)

    for account, rows in by_account.items():
        customers = {
            value
            for row in rows
            for value in (row.get("linked_customer_id"), row.get("source_customer_id"))
            if isinstance(value, str) and value
        }
        account_customer_sets[account] = customers
        if len(customers) > 1:
            accounts_with_customer_conflict += 1
        for customer in customers:
            customer_accounts[customer].add(account)
        account_history_rows[account] = len(rows)
        for row in rows:
            event_observations.setdefault((account, row["transaction_id"]), []).append(
                row
            )
            if row["is_pending"] is True:
                pending_counts["true"] += 1
            elif row["is_pending"] is False:
                pending_counts["false"] += 1
            else:
                pending_counts["unknown"] += 1

    for _event, rows in event_observations.items():
        if len(rows) > 1:
            duplicate_events += 1
        if len({_content_signature(row) for row in rows}) > 1:
            content_variant_events += 1
        if len({_source_metadata_signature(row) for row in rows}) > 1:
            source_metadata_variant_events += 1
        states = {row["is_pending"] for row in rows}
        if True in states and False in states:
            pending_posted_pairs += 1

    for event in candidate_events:
        rows = event_observations.get(event, [])
        if rows:
            candidate_events_with_history += 1
        if (
            len(
                {
                    row.get("asset_report_id")
                    for row in rows
                    if row.get("asset_report_id")
                }
            )
            > 1
        ):
            candidate_events_with_multiple_reports += 1
        if any(row["is_pending"] is True for row in rows):
            candidate_events_with_pending_state += 1

    account_sizes = Counter(row["account_id"] for row in candidates)
    customer_sizes = Counter(row["customer_id"] for row in candidates)
    assignment_sizes = Counter(row["customer_id"] for row in candidates)
    return {
        "schema_version": "benchmark-candidate-lineage-profile-v1",
        "purpose": "candidate_admission_evidence_not_authority",
        "candidate_rows": len(candidates),
        "candidate_accounts": len(account_sizes),
        "candidate_customers": len(customer_sizes),
        "candidate_profile_sha256": profile_sha256,
        "lineage_rows": len(lineage),
        "lineage_source_rows": dict(sorted(source_counts.items())),
        "lineage_accounts": len(by_account),
        "lineage_events": len(event_observations),
        "candidate_event_lineage_rows_per_account": {
            "min": min(account_history_rows.values(), default=0),
            "max": max(account_history_rows.values(), default=0),
            "accounts_with_lineage": sum(
                value > 0 for value in account_history_rows.values()
            ),
        },
        "alias_signals": {
            "pending_transaction_id_available": False,
            "pending_transaction_id_nonnull": 0,
            "events_with_multiple_source_observations": duplicate_events,
            "events_with_content_variants": content_variant_events,
            "events_with_source_metadata_variants": source_metadata_variant_events,
            "events_with_pending_and_posted_states": pending_posted_pairs,
            "candidate_events_with_history": candidate_events_with_history,
            "candidate_events_with_multiple_reports": candidate_events_with_multiple_reports,
            "candidate_events_with_pending_state": candidate_events_with_pending_state,
        },
        "identity_signals": {
            "accounts_with_multiple_customer_ids_in_selected_lineage": (
                accounts_with_customer_conflict
            ),
            "customers_with_multiple_candidate_accounts": sum(
                len(accounts) > 1 for accounts in customer_accounts.values()
            ),
            "all_selected_account_history_identity_complete": False,
        },
        "candidate_blocks": {
            "account_groups": len(account_sizes),
            "account_max_rows": max(account_sizes.values(), default=0),
            "customer_groups": len(customer_sizes),
            "customer_max_rows": max(customer_sizes.values(), default=0),
            "assignment_groups": len(assignment_sizes),
            "assignment_max_rows": max(assignment_sizes.values(), default=0),
        },
        "family_evidence": {
            "reviewed_family_index_present": False,
            "family_absence_certified": False,
            "exact_name_absence_is_family_absence": False,
        },
        "admission": {
            "eligible_rows": 0,
            "authorizes_consumption": False,
            "rows_reserved_or_labelled": 0,
            "blockers": [
                "pending_reconnection_aliases_unverified",
                "historical_identity_completeness_not_certified",
                "effective_input_history_profile_is_non_authorizing",
                "reviewed_merchant_family_index_missing",
                "legacy_protected_membership_migration_missing",
                "managed_reservation_and_consumer_gate_not_authorizing",
            ],
        },
    }


def main() -> None:
    from google.cloud import bigquery

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--candidate-profile", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    os.umask(0o077)
    candidate_receipt, candidates = _load_candidates(args.candidates)
    profile_sha256 = _validate_profile(args.candidate_profile, candidate_receipt)
    args.output.mkdir(mode=0o700, parents=False, exist_ok=False)
    sql_path = Path(__file__).with_name(LINEAGE_SQL_NAME)
    sql = sql_path.read_text()
    account_ids = sorted({row["account_id"] for row in candidates})
    transaction_ids = sorted({row["transaction_id"] for row in candidates})
    candidate_pairs = [
        bigquery.StructQueryParameter(
            None,
            bigquery.ScalarQueryParameter("account_id", "STRING", row["account_id"]),
            bigquery.ScalarQueryParameter(
                "transaction_id", "STRING", row["transaction_id"]
            ),
        )
        for row in candidates
    ]
    candidate_pair_type = bigquery.StructQueryParameterType(
        bigquery.ScalarQueryParameterType("STRING", name="account_id"),
        bigquery.ScalarQueryParameterType("STRING", name="transaction_id"),
    )
    client = bigquery.Client(project=PROJECT, location=LOCATION)
    table_names = sorted(
        set(re.findall(r"`(raylo-production\.[a-zA-Z0-9_]+\.[a-zA-Z0-9_]+)`", sql))
    )
    metadata_before = [metadata(client.get_table(name)) for name in table_names]
    config = bigquery.QueryJobConfig(
        dry_run=True,
        use_query_cache=False,
        maximum_bytes_billed=MAX_BYTES,
        query_parameters=[
            bigquery.ArrayQueryParameter(
                "candidate_pairs", candidate_pair_type, candidate_pairs
            ),
        ],
    )
    dry = client.query(sql, job_config=config, location=LOCATION)
    if dry.statement_type != "SELECT" or dry.total_bytes_processed > MAX_BYTES:
        raise ValueError("lineage query is outside the bounded read-only scope")
    receipt = {
        "schema_version": "benchmark-candidate-lineage-extract-v1",
        "purpose": "private_customer_linked_candidate_lineage_evidence",
        "authorizes_consumption": False,
        "project": PROJECT,
        "location": LOCATION,
        "statement_type": "SELECT",
        "candidate_result_sha256": candidate_receipt["result_sha256"],
        "candidate_profile_sha256": profile_sha256,
        "candidate_rows": len(candidates),
        "account_parameter_count": len(account_ids),
        "transaction_parameter_count": len(transaction_ids),
        "maximum_bytes_billed": MAX_BYTES,
        "dry_run_bytes": dry.total_bytes_processed,
        "sql_sha256": digest(sql_path),
        "runner_sha256": digest(Path(__file__)),
        "source_tables": table_names,
        "source_metadata_before": metadata_before,
        "pending_transaction_id_available": False,
        "executed": False,
    }
    print(
        f"Validated lineage SELECT: {dry.total_bytes_processed:,} estimated bytes",
        flush=True,
    )
    lineage_path = args.output / "lineage.jsonl"
    if args.execute:
        config.dry_run = False
        job = client.query(
            sql, job_config=config, location=LOCATION, job_id_prefix="txncat_lineage_"
        )
        rows = job.result(page_size=1000)
        if rows.total_rows > MAX_LINEAGE_ROWS:
            raise ValueError("unexpected lineage size")
        lineage: list[dict[str, Any]] = []
        for row in rows:
            value = dict(row)
            _validate_lineage(value)
            lineage.append(value)
        if len(lineage) != rows.total_rows:
            raise ValueError("lineage result is incomplete")
        _validate_candidate_lineage(candidates, lineage)
        with lineage_path.open("x") as stream:
            for value in lineage:
                stream.write(encode(value))
        receipt.update(
            executed=True,
            job_id=job.job_id,
            started_at=job.started,
            ended_at=job.ended,
            bytes_processed=job.total_bytes_processed,
            bytes_billed=job.total_bytes_billed,
            result_rows=len(lineage),
            result_sha256=digest(lineage_path),
            source_metadata_after=[
                metadata(client.get_table(name)) for name in table_names
            ],
        )
        (args.output / "summary.json").write_bytes(
            (
                json.dumps(
                    summarise(candidates, lineage, profile_sha256), sort_keys=True
                )
                + "\n"
            ).encode()
        )
        os.chmod(args.output / "summary.json", 0o600)
        print(
            f"Private lineage extract complete: {len(lineage):,} rows; no admission authorized."
        )
    (args.output / "receipt.json").write_bytes(encode(receipt).encode())
    os.chmod(args.output / "receipt.json", 0o600)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit(
            "Candidate lineage extraction failed; no admission claim is valid."
        ) from None

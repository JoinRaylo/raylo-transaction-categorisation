"""Extract bounded per-account evidence for the G3 admission design.

Runs three aggregate SELECTs over the candidate account set: per-account
retained-history coverage (pending observations, resolved customers, account
attributes, date bounds), pending-resolution outcomes, and transaction-id
collisions across candidate accounts.  This is evidence collection only; it
reserves nothing, labels nothing and cannot authorize consumption.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any

from benchmark_extract import encode, metadata

PROJECT = "raylo-production"
LOCATION = "EU"
MAX_RESULT_ROWS = 2_000_000
ACCOUNT_MAX_BYTES = 40_000_000_000
DETAIL_MAX_BYTES = 20_000_000_000
ACCOUNT_SQL_NAME = "benchmark_account_evidence_account.sql"
PENDING_SQL_NAME = "benchmark_account_evidence_pending.sql"
COLLISION_SQL_NAME = "benchmark_account_evidence_collisions.sql"
ACCOUNT_SCHEMA = "benchmark-account-evidence-extract-v1"
FRAME_SCHEMA = "benchmark-candidate-frame-extract-v1"
FRAME_PURPOSE = "g2_candidate_frame_read_not_admission"
SOURCE_TABLE = (
    "raylo-production.dbt_production.intermediate_credit_plaid_transactions"
)
ACCOUNT_FIELDS = (
    "source_table",
    "account_id",
    "observation_rows",
    "distinct_transactions",
    "pending_rows",
    "pending_transaction_ids",
    "pending_state_unknown_rows",
    "distinct_customers",
    "customer_ids",
    "unresolved_link_rows",
    "first_observation_date",
    "last_observation_date",
    "account_masks",
    "account_names",
    "account_subtypes",
)
PENDING_FIELDS = (
    "account_id",
    "transaction_id",
    "posted_history_rows",
    "current_materialized_rows",
)
COLLISION_FIELDS = (
    "transaction_id",
    "observation_rows",
    "account_ids",
    "distinct_accounts",
)
SOURCE_KINDS = frozenset({"current_materialized", "plaid_materialized_history"})


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"{path} is not a JSON object")
    return value


DERIVED_SCHEMA = "benchmark-derived-pool-v1"
DERIVED_PURPOSE = "g3_roster_hit_evidence_scope_not_admission"


def _load_candidates(
    directory: Path, purpose: str = FRAME_PURPOSE, derived: bool = False
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    receipt = _load_json(directory / "receipt.json")
    candidate_path = directory / "candidates.jsonl"
    if derived:
        if (
            receipt.get("schema_version") != DERIVED_SCHEMA
            or receipt.get("purpose") != DERIVED_PURPOSE
            or receipt.get("authorizes_consumption") is not False
            or digest(candidate_path) != receipt.get("result_sha256")
        ):
            raise ValueError(
                "derived pool is incomplete or outside the approved contract"
            )
    elif (
        receipt.get("schema_version") != FRAME_SCHEMA
        or receipt.get("purpose") != purpose
        or receipt.get("project") != PROJECT
        or receipt.get("location") != LOCATION
        or receipt.get("statement_type") != "SELECT"
        or receipt.get("source_table") != SOURCE_TABLE
        or receipt.get("executed") is not True
        or receipt.get("authorizes_consumption") is not False
        or digest(candidate_path) != receipt.get("result_sha256")
    ):
        raise ValueError(
            "candidate frame is incomplete or outside the approved contract"
        )
    rows: list[dict[str, Any]] = []
    events: set[tuple[str, str]] = set()
    with candidate_path.open() as stream:
        for line in stream:
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError("candidate frame row is not an object")
            for field in ("account_id", "transaction_id", "customer_id"):
                if type(row.get(field)) is not str or not row[field]:
                    raise ValueError("candidate frame identity field is incomplete")
            event = (row["account_id"], row["transaction_id"])
            if event in events:
                raise ValueError("candidate frame contains a duplicate event")
            events.add(event)
            rows.append(row)
    expected_rows = (
        receipt.get("roster_hit_rows") if derived else receipt.get("result_rows")
    )
    if len(rows) != expected_rows:
        raise ValueError("candidate frame row count does not match its receipt")
    return receipt, rows


def _validate_account_row(row: dict[str, Any]) -> None:
    if set(row) != set(ACCOUNT_FIELDS):
        raise ValueError("account evidence row schema changed")
    if row["source_table"] not in SOURCE_KINDS:
        raise ValueError("unexpected account evidence source")
    if type(row["account_id"]) is not str or not row["account_id"]:
        raise ValueError("account evidence row lacks its account id")
    for field in (
        "observation_rows",
        "distinct_transactions",
        "pending_rows",
        "pending_state_unknown_rows",
        "distinct_customers",
        "unresolved_link_rows",
    ):
        if type(row[field]) is not int or row[field] < 0:
            raise ValueError("account evidence count field is invalid")
    for field in (
        "pending_transaction_ids",
        "customer_ids",
        "account_masks",
        "account_names",
        "account_subtypes",
    ):
        if not isinstance(row[field], list):
            raise ValueError("account evidence array field is invalid")


def _validate_pending_row(row: dict[str, Any]) -> None:
    if set(row) != set(PENDING_FIELDS):
        raise ValueError("pending evidence row schema changed")
    for field in ("account_id", "transaction_id"):
        if type(row[field]) is not str or not row[field]:
            raise ValueError("pending evidence row lacks its identity")
    for field in ("posted_history_rows", "current_materialized_rows"):
        if type(row[field]) is not int or row[field] < 0:
            raise ValueError("pending evidence count is invalid")


def _validate_collision_row(row: dict[str, Any]) -> None:
    if set(row) != set(COLLISION_FIELDS):
        raise ValueError("collision row schema changed")
    if type(row["transaction_id"]) is not str or not row["transaction_id"]:
        raise ValueError("collision row lacks its transaction id")
    if type(row["observation_rows"]) is not int or row["observation_rows"] < 2:
        raise ValueError("collision row count is invalid")
    if (
        type(row["distinct_accounts"]) is not int
        or row["distinct_accounts"] < 2
        or row["distinct_accounts"] != len(row["account_ids"])
        or not all(type(a) is str and a for a in row["account_ids"])
    ):
        raise ValueError("collision account set is invalid")


def _run_query(
    client,
    sql: str,
    sql_path: Path,
    account_ids: list[str],
    *,
    max_bytes: int,
    job_prefix: str,
    execute: bool,
):
    from google.cloud import bigquery  # noqa: PLC0415

    config = bigquery.QueryJobConfig(
        dry_run=True,
        use_query_cache=False,
        maximum_bytes_billed=max_bytes,
        query_parameters=[
            bigquery.ArrayQueryParameter("account_ids", "STRING", account_ids)
        ],
    )
    dry = client.query(sql, job_config=config, location=LOCATION)
    if dry.statement_type != "SELECT" or dry.total_bytes_processed > max_bytes:
        raise ValueError("account evidence query is outside the bounded scope")
    result = {
        "dry_run_bytes": dry.total_bytes_processed,
        "sql_sha256": digest(sql_path),
        "rows": None,
    }
    if not execute:
        return result
    config.dry_run = False
    job = client.query(
        sql, job_config=config, location=LOCATION, job_id_prefix=job_prefix
    )
    rows = [dict(row) for row in job.result(page_size=1000)]
    result.update(
        job_id=job.job_id,
        started_at=job.started,
        ended_at=job.ended,
        bytes_processed=job.total_bytes_processed,
        bytes_billed=job.total_bytes_billed,
        rows=rows,
    )
    return result


def main() -> None:
    from google.cloud import bigquery

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--purpose", default=FRAME_PURPOSE)
    parser.add_argument("--derived", action="store_true")
    args = parser.parse_args()
    os.umask(0o077)
    candidate_receipt, candidates = _load_candidates(
        args.candidates, purpose=args.purpose, derived=args.derived
    )
    args.output.mkdir(mode=0o700, parents=False, exist_ok=False)
    query_specs = (
        (
            "account_summary",
            Path(__file__).with_name(ACCOUNT_SQL_NAME),
            ACCOUNT_MAX_BYTES,
            "txncat_acct_evidence_",
            _validate_account_row,
            "account-summary.jsonl",
        ),
        (
            "pending_resolution",
            Path(__file__).with_name(PENDING_SQL_NAME),
            DETAIL_MAX_BYTES,
            "txncat_acct_pending_",
            _validate_pending_row,
            "pending-resolution.jsonl",
        ),
        (
            "txid_collisions",
            Path(__file__).with_name(COLLISION_SQL_NAME),
            DETAIL_MAX_BYTES,
            "txncat_acct_collisions_",
            _validate_collision_row,
            "txid-collisions.jsonl",
        ),
    )
    account_ids = sorted({row["account_id"] for row in candidates})
    client = bigquery.Client(project=PROJECT, location=LOCATION)
    table_names = sorted(
        set(
            re.findall(
                r"`(raylo-production\.[a-zA-Z0-9_]+\.[a-zA-Z0-9_]+)`",
                "".join(path.read_text() for _, path, *_ in query_specs),
            )
        )
    )
    metadata_before = [metadata(client.get_table(name)) for name in table_names]
    receipt = {
        "schema_version": ACCOUNT_SCHEMA,
        "purpose": "g3_account_evidence_read_not_admission",
        "authorizes_consumption": False,
        "project": PROJECT,
        "location": LOCATION,
        "candidate_result_sha256": candidate_receipt["result_sha256"],
        "candidate_rows": len(candidates),
        "account_parameter_count": len(account_ids),
        "derived_pool_sha256": (
            candidate_receipt.get("pool_result_sha256")
            if args.derived
            else None
        ),
        "maximum_bytes_billed": {
            name: bound for name, _, bound, *_rest in query_specs
        },
        "runner_sha256": digest(Path(__file__)),
        "source_tables": table_names,
        "source_metadata_before": metadata_before,
        "executed": False,
    }
    runs = {}
    for name, sql_path, bound, prefix, _validator, _out in query_specs:
        runs[name] = _run_query(
            client,
            sql_path.read_text(),
            sql_path,
            account_ids,
            max_bytes=bound,
            job_prefix=prefix,
            execute=args.execute,
        )
        print(
            f"Validated {name} SELECT: "
            f"{runs[name]['dry_run_bytes']:,} estimated bytes",
            flush=True,
        )
    if not args.execute:
        receipt["queries"] = {
            name: {k: v for k, v in run.items() if k != "rows"}
            for name, run in runs.items()
        }
        (args.output / "receipt.json").write_bytes(encode(receipt).encode())
        os.chmod(args.output / "receipt.json", 0o600)
        return
    written = {}
    for name, _sql_path, _bound, _prefix, validator, out_name in query_specs:
        rows = runs[name]["rows"]
        if len(rows) > MAX_RESULT_ROWS:
            raise ValueError("unexpected account evidence size")
        for row in rows:
            validator(row)
        path = args.output / out_name
        with path.open("x") as stream:
            for row in rows:
                stream.write(encode(row))
        os.chmod(path, 0o600)
        written[name] = path
    account_rows = runs["account_summary"]["rows"]
    pending_rows = runs["pending_resolution"]["rows"]
    collision_rows = runs["txid_collisions"]["rows"]
    covered = {row["account_id"] for row in account_rows}
    missing = set(account_ids) - covered
    customers_by_account: dict[str, set[str]] = {}
    unresolved_by_account: dict[str, int] = {}
    pending_by_account: dict[str, set[str]] = {}
    for row in account_rows:
        customers_by_account.setdefault(row["account_id"], set()).update(
            row["customer_ids"]
        )
        unresolved_by_account[row["account_id"]] = (
            unresolved_by_account.get(row["account_id"], 0)
            + row["unresolved_link_rows"]
        )
        pending_by_account.setdefault(row["account_id"], set()).update(
            row["pending_transaction_ids"]
        )
    unresolved_pending = sum(
        row["posted_history_rows"] == 0 and row["current_materialized_rows"] == 0
        for row in pending_rows
    )
    summary = {
        "schema_version": "benchmark-account-evidence-summary-v1",
        "purpose": "g3_admission_evidence_not_authority",
        "authorizes_consumption": False,
        "candidate_result_sha256": candidate_receipt["result_sha256"],
        "candidate_accounts": len(account_ids),
        "accounts_with_retained_rows": len(covered),
        "accounts_without_retained_rows": len(missing),
        "account_rows": len(account_rows),
        "pending_pairs": len(pending_rows),
        "unresolved_pending_pairs": unresolved_pending,
        "collision_rows": len(collision_rows),
        "colliding_transaction_ids": len(collision_rows),
        "accounts_with_pending_observations": sum(
            row["pending_rows"] > 0 for row in account_rows
        ),
        "accounts_with_identity_churn": sum(
            len(customers) > 1 for customers in customers_by_account.values()
        ),
        "accounts_with_unresolved_links": sum(
            count > 0 for count in unresolved_by_account.values()
        ),
        "source_rows": dict(
            sorted(Counter(row["source_table"] for row in account_rows).items())
        ),
        "candidate_events_ever_pending": sum(
            row["transaction_id"]
            in pending_by_account.get(row["account_id"], set())
            for row in candidates
        ),
        "pending_resolution_note": (
            "every pending transaction id later materialized non-pending under "
            "the same key; pending state is a same-key transition in the "
            "retained record, not an enumerable alias pair"
        ),
    }
    (args.output / "summary.json").write_bytes(encode(summary).encode())
    receipt.update(
        executed=True,
        queries={
            name: {k: v for k, v in run.items() if k != "rows"}
            for name, run in runs.items()
        },
        result_sha256={
            name: digest(path) for name, path in written.items()
        },
        result_rows={
            name: len(runs[name]["rows"]) for name, _, *_ in query_specs
        },
        source_metadata_after=[
            metadata(client.get_table(name)) for name in table_names
        ],
    )
    (args.output / "receipt.json").write_bytes(encode(receipt).encode())
    os.chmod(args.output / "summary.json", 0o600)
    os.chmod(args.output / "receipt.json", 0o600)
    print(
        f"Account evidence extract complete: {len(account_rows):,} account rows, "
        f"{len(pending_rows):,} pending pairs, {len(collision_rows):,} "
        "collisions; no admission authorized."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit(
            "Account evidence extraction failed; no admission claim is valid."
        ) from None

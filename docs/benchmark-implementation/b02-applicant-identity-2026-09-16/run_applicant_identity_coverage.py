#!/usr/bin/env python3
"""Run the bounded aggregate probe without exporting cohort identifiers."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from google.cloud import bigquery

BASE = Path(__file__).resolve().parent
DEFAULT_LINKS_BASE = Path(
    "/Users/carlosnoblejesus/.local/share/raylo-txncat/benchmark-engineering/2026-09-16"
)
SQL_PATH = BASE / "applicant_identity_coverage.sql"
PROJECT = "raylo-production"
LOCATION = "EU"
MAXIMUM_BYTES_BILLED = 20_000_000_000
EXPECTED_ROWS = 99
EXPECTED_MISSING_USER_ROWS = 49
EXPECTED_LINKS_ROWS_SHA256 = (
    "f90ea0244f9248a0fad1dbe71cc53920626c934262187819d54362d038447f5d"
)

TABLES = [
    f"{PROJECT}.airbyte_raylo_prod.checkouts",
    f"{PROJECT}.airbyte_raylo_prod.checkout_customer_infos",
    f"{PROJECT}.airbyte_raylo_prod.users",
    f"{PROJECT}.airbyte_raylo_prod.customers",
]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def read_and_validate_cohort(
    links_base: Path,
) -> tuple[list[str], dict[str, object], str]:
    links_receipt = links_base / "links" / "receipt.json"
    links_rows = links_base / "links" / "rows.jsonl"
    receipt_bytes = links_receipt.read_bytes()
    rows_bytes = links_rows.read_bytes()
    receipt = json.loads(receipt_bytes)
    rows = [json.loads(line) for line in rows_bytes.decode().splitlines()]
    rows_sha256 = hashlib.sha256(rows_bytes).hexdigest()

    if receipt.get("project") != PROJECT or receipt.get("location") != LOCATION:
        raise RuntimeError("retained links receipt is not raylo-production/EU")
    if str(receipt.get("statement_type", "")).upper() != "SELECT":
        raise RuntimeError("retained links receipt is not a SELECT")
    if receipt.get("result_rows") != EXPECTED_ROWS:
        raise RuntimeError("retained links receipt row count changed")
    if receipt.get("result_sha256") != EXPECTED_LINKS_ROWS_SHA256:
        raise RuntimeError("retained links result SHA changed")
    if rows_sha256 != EXPECTED_LINKS_ROWS_SHA256:
        raise RuntimeError("retained links rows SHA changed")
    if len(rows) != EXPECTED_ROWS:
        raise RuntimeError("retained links rows changed")
    for row in rows:
        if not isinstance(row.get("checkout_id"), str):
            raise RuntimeError("retained checkout ID is not a string")
        if not isinstance(row.get("assessment_id"), str):
            raise RuntimeError("retained assessment ID is not a string")
        if not row["checkout_id"].strip() or not row["assessment_id"].strip():
            raise RuntimeError("retained checkout/assessment ID is blank")
    checkout_ids = [row["checkout_id"] for row in rows if (row.get("user_count") or 0) == 0]
    if len(checkout_ids) != EXPECTED_MISSING_USER_ROWS:
        raise RuntimeError("retained missing-user cohort count changed")
    if len(set(checkout_ids)) != EXPECTED_MISSING_USER_ROWS:
        raise RuntimeError("retained missing-user checkout IDs are not unique")
    if len({row["checkout_id"] for row in rows}) != EXPECTED_ROWS:
        raise RuntimeError("retained links checkout IDs are not unique")
    if len({row["assessment_id"] for row in rows}) != EXPECTED_ROWS:
        raise RuntimeError("retained links assessment IDs are not unique")
    if any(
        (row.get("user_count") or 0) == 0
        and row.get("user_customer_count") is not None
        for row in rows
    ):
        raise RuntimeError("missing-user rows unexpectedly have customer linkage")
    if any(
        (row.get("user_count") or 0) > 0
        and (row.get("user_customer_count") or 0) == 0
        for row in rows
    ):
        raise RuntimeError("referenced users unexpectedly lack customer linkage")

    # Only receipt metadata and hashes are persisted; no cohort IDs are saved.
    pin = {
        "links_receipt_sha256": hashlib.sha256(receipt_bytes).hexdigest(),
        "links_rows_sha256": rows_sha256,
        "links_result_sha256": receipt.get("result_sha256"),
        "links_sql_sha256": receipt.get("sql_sha256"),
        "links_runner_sha256": receipt.get("runner_sha256"),
        "links_result_rows": receipt.get("result_rows"),
        "links_source_day": receipt.get("source_day"),
        "links_statement_type": receipt.get("statement_type"),
    }
    return checkout_ids, pin, hashlib.sha256(receipt_bytes).hexdigest()


def table_metadata(client: bigquery.Client) -> list[dict[str, object]]:
    metadata: list[dict[str, object]] = []
    for name in TABLES:
        table = client.get_table(name)
        metadata.append(
            {
                "table": name,
                "etag": table.etag,
                "created": table.created.isoformat() if table.created else None,
                "modified": table.modified.isoformat() if table.modified else None,
                "num_rows": table.num_rows,
                "num_bytes": table.num_bytes,
                "schema": [
                    {"name": field.name, "type": field.field_type, "mode": field.mode}
                    for field in table.schema
                ],
            }
        )
    return metadata


def run(execute: bool, links_base: Path, output_dir: Path) -> Path:
    checkout_ids, links_pin, links_receipt_sha256 = read_and_validate_cohort(
        links_base
    )
    sql = SQL_PATH.read_text()
    runner_hash = sha256_file(Path(__file__))
    sql_hash = hashlib.sha256(sql.encode()).hexdigest()
    client = bigquery.Client(project=PROJECT)
    metadata_before = table_metadata(client)

    dry_run_config = bigquery.QueryJobConfig(
        dry_run=True,
        use_query_cache=False,
        maximum_bytes_billed=MAXIMUM_BYTES_BILLED,
        query_parameters=[
            bigquery.ArrayQueryParameter("checkout_ids", "STRING", checkout_ids)
        ],
        labels={"purpose": "txncat_applicant_identity_coverage"},
    )
    started_at = utc_now()
    dry_run_job = client.query(sql, location=LOCATION, job_config=dry_run_config)
    dry_run_bytes = dry_run_job.total_bytes_processed
    if dry_run_bytes is None or dry_run_bytes > MAXIMUM_BYTES_BILLED:
        raise RuntimeError("dry-run estimate exceeds maximum_bytes_billed")
    if dry_run_job.statement_type != "SELECT":
        raise RuntimeError("identity probe dry-run is not a SELECT")

    job = dry_run_job
    result: dict[str, object] | None = None
    if execute:
        execute_config = bigquery.QueryJobConfig(
            dry_run=False,
            use_query_cache=False,
            maximum_bytes_billed=MAXIMUM_BYTES_BILLED,
            query_parameters=dry_run_config.query_parameters,
            labels={"purpose": "txncat_applicant_identity_coverage"},
        )
        job = client.query(sql, location=LOCATION, job_config=execute_config)
        rows = list(job.result())
        if len(rows) != 1:
            raise RuntimeError("aggregate probe did not return exactly one row")
        result = {key: int(value) for key, value in dict(rows[0]).items()}
        if result.get("cohort_rows") != EXPECTED_MISSING_USER_ROWS:
            raise RuntimeError("aggregate cohort row count did not reconcile")
        if result.get("cohort_unique_checkouts") != EXPECTED_MISSING_USER_ROWS:
            raise RuntimeError("aggregate cohort uniqueness did not reconcile")
    metadata_after = table_metadata(client)
    receipt = {
        "schema_version": "txncat-applicant-identity-v1",
        "executed": execute,
        "project": PROJECT,
        "location": LOCATION,
        "maximum_bytes_billed": MAXIMUM_BYTES_BILLED,
        "started_at": started_at,
        "ended_at": utc_now(),
        "job_id": job.job_id,
        "statement_type": job.statement_type,
        "dry_run_bytes": dry_run_bytes,
        "total_bytes_billed": job.total_bytes_billed,
        "bytes_processed": job.total_bytes_processed if execute else 0,
        "sql_sha256": sql_hash,
        "runner_sha256": runner_hash,
        "links_receipt_sha256": links_receipt_sha256,
        "links_pin": links_pin,
        "cohort_rows_validated_privately": EXPECTED_ROWS,
        "missing_user_rows_validated_privately": EXPECTED_MISSING_USER_ROWS,
        "metadata_before": metadata_before,
        "metadata_after": metadata_after,
        "result_columns": sorted(result) if result is not None else [],
        "aggregate_result": result,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / (
        "executed_receipt.json" if execute else "dry_run_receipt.json"
    )
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"receipt": str(output), "dry_run_bytes": job.total_bytes_processed}))
    if result is not None:
        print(json.dumps({"aggregate_result": result}, sort_keys=True))
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--links-dir", type=Path, default=DEFAULT_LINKS_BASE)
    parser.add_argument("--output-dir", type=Path, default=BASE)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="execute the aggregate after review; default is dry-run",
    )
    args = parser.parse_args()
    run(args.execute, args.links_dir, args.output_dir)

"""Bounded private G2 candidate-frame draw from the customer-linked Plaid pool.

This is the Phase-2 candidate frame read for the 1,500-row expansion: one
deterministic hash-ranked SELECT that keeps source and identity fields private
and adds the provider category and content-revision columns the frame contract
requires.  It is a source draw for admission engineering, not a benchmark
reservation or label export.  A later admission step must still verify aliases,
exposure, families, blocks and authority state.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
from pathlib import Path

from benchmark_extract import MAX_BYTES, encode, metadata
from raylo_txncat.hashing import canonical_json

MAX_ROWS = 10_000
PROJECT = "raylo-production"
LOCATION = "EU"
SOURCE_TABLE = "raylo-production.dbt_production.intermediate_credit_plaid_transactions"
SCOPE_CONTRACT = {
    "source_kind": "customer_linked_plaid_materialized",
    "source_table": SOURCE_TABLE,
    "link_rule": "assessment_to_one_checkout_to_one_user_to_one_customer_record",
    "anonymous_id_recovery": False,
}
SCOPE_CONTRACT_SHA256 = hashlib.sha256(canonical_json(SCOPE_CONTRACT)).hexdigest()
SCHEMA_VERSION = "benchmark-candidate-frame-extract-v1"
SQL_NAME = "benchmark_candidate_frame_extract.sql"
CONTENT_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _validate_row(value: dict) -> None:
    required = (
        "account_id",
        "transaction_id",
        "customer_id",
        "assessment_id",
        "checkout_id",
        "user_id",
    )
    if any(not isinstance(value.get(field), str) or not value[field] for field in required):
        raise ValueError("candidate row is missing a linked source field")
    link_counts = (
        "assessment_checkout_count",
        "checkout_user_count",
        "user_customer_count",
        "customer_record_count",
    )
    if any(type(value.get(field)) is not int or value[field] != 1 for field in link_counts):
        raise ValueError("candidate row is not backed by unique current links")
    content = value.get("content_sha256")
    if not isinstance(content, str) or not CONTENT_SHA256_PATTERN.fullmatch(content):
        raise ValueError("candidate row is missing its content revision digest")
    if not isinstance(value.get("category"), list):
        raise ValueError("candidate row provider category is not an array")


def main() -> None:
    from google.cloud import bigquery

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-limit", type=int, default=10_000)
    parser.add_argument("--seed", default="g2-candidate-frame-2026-09-22-v1")
    parser.add_argument("--output", type=Path, required=True, help="New private directory")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.candidate_limit <= MAX_ROWS:
        raise ValueError("candidate limit outside bounded engineering scope")
    if type(args.seed) is not str or not args.seed.strip() or len(args.seed) > 128:
        raise ValueError("invalid deterministic candidate seed")
    os.umask(0o077)
    args.output.mkdir(mode=0o700, parents=False, exist_ok=False)
    sql_path = Path(__file__).with_name(SQL_NAME)
    sql = sql_path.read_text()
    client = bigquery.Client(project=PROJECT, location=LOCATION)
    tables = sorted(set(re.findall(r"`(raylo-production\.[a-zA-Z0-9_]+\.[a-zA-Z0-9_]+)`", sql)))
    before = [metadata(client.get_table(table)) for table in tables]
    config = bigquery.QueryJobConfig(
        dry_run=True,
        use_query_cache=False,
        maximum_bytes_billed=MAX_BYTES,
        query_parameters=[
            bigquery.ScalarQueryParameter("candidate_limit", "INT64", args.candidate_limit),
            bigquery.ScalarQueryParameter("seed", "STRING", args.seed),
        ],
    )
    dry = client.query(sql, job_config=config, location=LOCATION)
    if dry.statement_type != "SELECT" or dry.total_bytes_processed > MAX_BYTES:
        raise ValueError("candidate query outside read-only budget")
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "purpose": "g2_candidate_frame_read_not_admission",
        "authorizes_consumption": False,
        "project": PROJECT,
        "location": LOCATION,
        "statement_type": "SELECT",
        "source_table": SOURCE_TABLE,
        "source_kind": SCOPE_CONTRACT["source_kind"],
        "scope_contract": SCOPE_CONTRACT,
        "scope_contract_sha256": SCOPE_CONTRACT_SHA256,
        "anonymous_id_recovery": False,
        "seed": args.seed,
        "candidate_limit": args.candidate_limit,
        "maximum_bytes_billed": MAX_BYTES,
        "dry_run_bytes": dry.total_bytes_processed,
        "sql_sha256": digest(sql_path),
        "runner_sha256": digest(Path(__file__)),
        "source_metadata_before": before,
        "executed": False,
    }
    print(f"Validated candidate SELECT: {dry.total_bytes_processed:,} estimated bytes", flush=True)
    if args.execute:
        config.dry_run = False
        job = client.query(
            sql, job_config=config, location=LOCATION, job_id_prefix="txncat_frame_"
        )
        rows = job.result(page_size=1000)
        path = args.output / "candidates.jsonl"
        seen = set()
        count = 0
        with path.open("x") as stream:
            for row in rows:
                value = dict(row)
                _validate_row(value)
                event = (value["account_id"], value["transaction_id"])
                if event in seen:
                    raise ValueError("candidate draw contains a duplicate event")
                seen.add(event)
                stream.write(encode(value))
                count += 1
        if not 0 < count <= args.candidate_limit or count != rows.total_rows:
            raise ValueError("candidate draw size is incomplete or unexpected")
        receipt.update(
            executed=True,
            job_id=job.job_id,
            started_at=job.started,
            ended_at=job.ended,
            bytes_processed=job.total_bytes_processed,
            bytes_billed=job.total_bytes_billed,
            result_rows=count,
            result_sha256=digest(path),
            source_metadata_after=[metadata(client.get_table(table)) for table in tables],
        )
        print(f"Private candidate frame complete: {count:,} rows; no admission authorized.")
    with (args.output / "receipt.json").open("x") as stream:
        stream.write(encode(receipt))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit(
            "Candidate frame extraction failed; private output is incomplete and "
            "not admissible."
        ) from None

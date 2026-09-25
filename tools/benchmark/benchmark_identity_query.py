"""Bounded SELECT investigation of existing source IDs; private rows, public receipts."""

import argparse
import json
import os
import re
from datetime import date
from pathlib import Path

from benchmark_extract import MAX_BYTES, encode, metadata


def main():
    from google.cloud import bigquery

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--sql", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    import hashlib

    def digest(path):
        with path.open("rb") as stream:
            return hashlib.file_digest(stream, "sha256").hexdigest()

    source_receipt = json.loads((args.source / "receipt.json").read_text())
    source_path = args.source / "observations.jsonl"
    if not source_receipt["executed"] or digest(source_path) != source_receipt["result_sha256"]:
        raise ValueError("source snapshot changed")
    params = {
        k: set()
        for k in ("assessment_id", "external_request_id", "source_row_id", "account_id", "item_id")
    }
    with source_path.open() as stream:
        for line in stream:
            row = json.loads(line)
            for k in params:
                if row[k]:
                    params[k].add(row[k])
    os.umask(0o077)
    args.output.mkdir(mode=0o700, exist_ok=False)
    sql = args.sql.read_text()
    client = bigquery.Client(project="raylo-production", location="EU")
    tables = sorted(set(re.findall(r"`(raylo-production\.[a-zA-Z0-9_]+\.[a-zA-Z0-9_]+)`", sql)))
    before = [metadata(client.get_table(t)) for t in tables]
    parameters = [
        bigquery.ArrayQueryParameter(k + "s", "STRING", sorted(v)) for k, v in params.items()
    ]
    parameters.append(
        bigquery.ScalarQueryParameter(
            "source_day", "DATE", date.fromisoformat(source_receipt["source_day"])
        )
    )
    config = bigquery.QueryJobConfig(
        dry_run=True,
        use_query_cache=False,
        maximum_bytes_billed=MAX_BYTES,
        query_parameters=parameters,
    )
    dry = client.query(sql, job_config=config, location="EU")
    if dry.statement_type != "SELECT" or dry.total_bytes_processed > MAX_BYTES:
        raise ValueError("query exceeds read-only scope")
    print(f"Validated SELECT: {dry.total_bytes_processed:,} estimated bytes", flush=True)
    config.dry_run = False
    job = client.query(sql, job_config=config, location="EU", job_id_prefix="txncat_identity_")
    rows = job.result(page_size=1000)
    if rows.total_rows > 500_000:
        raise ValueError("unexpected investigation size")
    path = args.output / "rows.jsonl"
    with path.open("x") as stream:
        count = 0
        for row in rows:
            stream.write(encode(dict(row)))
            count += 1
    if count != rows.total_rows:
        raise ValueError("incomplete query result")
    receipt = {
        "schema_version": "benchmark-identity-investigation-v1",
        "authorizes_consumption": False,
        "sql_sha256": digest(args.sql),
        "source_sha256": digest(source_path),
        "result_sha256": digest(path),
        "runner_sha256": digest(Path(__file__)),
        "job_id": job.job_id,
        "result_rows": count,
        "project": "raylo-production",
        "location": "EU",
        "statement_type": "SELECT",
        "maximum_bytes_billed": MAX_BYTES,
        "dry_run_bytes": dry.total_bytes_processed,
        "bytes_processed": job.total_bytes_processed,
        "started_at": job.started,
        "ended_at": job.ended,
        "parameter_counts": {k: len(v) for k, v in params.items()},
        "source_day": source_receipt["source_day"],
        "metadata_before": before,
        "metadata_after": [metadata(client.get_table(t)) for t in tables],
    }
    with (args.output / "receipt.json").open("x") as stream:
        stream.write(encode(receipt))
    print(f"Completed identity investigation: {count:,} private result rows", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit(
            "Identity query failed; no link may be certified from incomplete output."
        ) from None

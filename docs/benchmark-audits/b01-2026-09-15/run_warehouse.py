"""Dry-run and optionally execute the fixed, aggregate-only B01 SELECT queries.

Uses existing bq authentication; no table writes, credentials or raw examples.
The job may create BigQuery's ordinary temporary query-result table.
"""

import argparse
import hashlib
import json
import subprocess
import uuid
from pathlib import Path

NAMES = [
    "legacy_identity",
    "current_profile",
    "customer_linkage",
    "repeated_observations",
    "historical_input_proxy",
    "direct_user_linkage",
    "account_report_completeness",
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--only", choices=NAMES, nargs="+")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    prefix = ["bq", "--project_id=raylo-production", "--location=EU", "--format=prettyjson"]
    limit = 20_000_000_000
    for name in args.only or NAMES:
        sql = (Path(__file__).parent / "sql" / (name + ".sql")).read_text()
        sha = hashlib.sha256(sql.encode()).hexdigest()
        options = ["query", "--use_legacy_sql=false", f"--maximum_bytes_billed={limit}"]
        dry = subprocess.run(
            prefix + options + ["--dry_run"], input=sql, text=True, capture_output=True, check=True
        )
        metadata = json.loads(dry.stdout)
        stats = metadata["statistics"]["query"]
        assert stats["statementType"] == "SELECT", "Only read-only SELECT queries permitted"
        assert int(stats["totalBytesProcessed"]) <= limit
        record = {
            "query_name": name,
            "sql_sha256": sha,
            "dry_run_bytes": int(stats["totalBytesProcessed"]),
            "maximum_bytes_billed": limit,
            "statement_type": "SELECT",
            "executed": False,
        }
        print(f"Validated {name}: {record['dry_run_bytes']:,} bytes", flush=True)
        if args.execute:
            job_id = "txncat_b01_" + name + "_" + uuid.uuid4().hex[:12]
            actual = subprocess.run(
                prefix + options + [f"--job_id={job_id}", "--max_rows=1000"],
                input=sql,
                text=True,
                capture_output=True,
                check=True,
            )
            result = json.loads(actual.stdout)
            path = args.output / (name + ".json")
            path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
            job = json.loads(
                subprocess.check_output(prefix + ["show", "--job=true", job_id], text=True)
            )
            actual_stats = job["statistics"]
            assert job["status"]["state"] == "DONE" and not job["status"].get("errorResult")
            record.update(
                executed=True,
                job_id=job_id,
                job_reference=job["jobReference"],
                query_statistics=actual_stats.get("query"),
                started_at_unix_ms=actual_stats.get("startTime"),
                ended_at_unix_ms=actual_stats.get("endTime"),
                result_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                result_rows=len(result),
            )
            print(f"Completed {name}: {len(result)} aggregate rows", flush=True)
        (args.output / (name + "_receipt.json")).write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n"
        )


if __name__ == "__main__":
    main()

"""Extract reconnect/sibling evidence for the G3 admission design.

First runs a bounded discovery SELECT mapping every candidate customer to all
account_ids attributed to that customer in retained materialized history, then
re-runs the account-evidence queries over the sibling accounts that are not
already covered by the candidate-account extract.  Evidence collection only:
nothing here reserves, labels or authorizes consumption.
"""

from __future__ import annotations

import argparse
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any

from benchmark_account_evidence_extract import (
    ACCOUNT_MAX_BYTES,
    ACCOUNT_SQL_NAME,
    FRAME_PURPOSE,
    COLLISION_SQL_NAME,
    DETAIL_MAX_BYTES,
    LOCATION,
    PENDING_SQL_NAME,
    PROJECT,
    _load_candidates,
    _validate_account_row,
    _validate_collision_row,
    _validate_pending_row,
    digest,
)
from benchmark_extract import encode, metadata

DISCOVERY_SQL_NAME = "benchmark_account_evidence_customer_accounts.sql"
DISCOVERY_MAX_BYTES = 20_000_000_000
DISCOVERY_FIELDS = (
    "customer_id",
    "account_id",
    "observation_rows",
    "distinct_transactions",
    "pending_rows",
    "first_observation_date",
    "last_observation_date",
)


def _validate_discovery_row(row: dict[str, Any]) -> None:
    if set(row) != set(DISCOVERY_FIELDS):
        raise ValueError("customer-account evidence row schema changed")
    for field in ("customer_id", "account_id"):
        if type(row[field]) is not str or not row[field]:
            raise ValueError("customer-account evidence row lacks its identity")
    for field in ("observation_rows", "distinct_transactions", "pending_rows"):
        if type(row[field]) is not int or row[field] < 0:
            raise ValueError("customer-account evidence count is invalid")


def _run_query(client, sql, sql_path, param_name, values, *, max_bytes, prefix, execute):
    from google.cloud import bigquery  # noqa: PLC0415

    config = bigquery.QueryJobConfig(
        dry_run=True,
        use_query_cache=False,
        maximum_bytes_billed=max_bytes,
        query_parameters=[
            bigquery.ArrayQueryParameter(param_name, "STRING", values)
        ],
    )
    dry = client.query(sql, job_config=config, location=LOCATION)
    if dry.statement_type != "SELECT" or dry.total_bytes_processed > max_bytes:
        raise ValueError("sibling evidence query is outside the bounded scope")
    result = {
        "dry_run_bytes": dry.total_bytes_processed,
        "sql_sha256": digest(sql_path),
        "rows": None,
    }
    if not execute:
        return result
    config.dry_run = False
    job = client.query(
        sql, job_config=config, location=LOCATION, job_id_prefix=prefix
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
    client = bigquery.Client(project=PROJECT, location=LOCATION)
    sibling_specs = (
        (
            "account_summary",
            Path(__file__).with_name(ACCOUNT_SQL_NAME),
            ACCOUNT_MAX_BYTES,
            "txncat_sib_evidence_",
            _validate_account_row,
            "account-summary.jsonl",
        ),
        (
            "pending_resolution",
            Path(__file__).with_name(PENDING_SQL_NAME),
            DETAIL_MAX_BYTES,
            "txncat_sib_pending_",
            _validate_pending_row,
            "pending-resolution.jsonl",
        ),
        (
            "txid_collisions",
            Path(__file__).with_name(COLLISION_SQL_NAME),
            DETAIL_MAX_BYTES,
            "txncat_sib_collisions_",
            _validate_collision_row,
            "txid-collisions.jsonl",
        ),
    )
    customer_ids = sorted({row["customer_id"] for row in candidates})
    candidate_accounts = {row["account_id"] for row in candidates}
    table_names = sorted(
        set(
            re.findall(
                r"`(raylo-production\.[a-zA-Z0-9_]+\.[a-zA-Z0-9_]+)`",
                Path(__file__)
                .with_name(DISCOVERY_SQL_NAME)
                .read_text()
                + "".join(path.read_text() for _, path, *_ in sibling_specs),
            )
        )
    )
    metadata_before = [metadata(client.get_table(name)) for name in table_names]
    receipt = {
        "schema_version": "benchmark-sibling-evidence-extract-v1",
        "purpose": "g3_reconnect_evidence_read_not_admission",
        "authorizes_consumption": False,
        "project": PROJECT,
        "location": LOCATION,
        "candidate_result_sha256": candidate_receipt["result_sha256"],
        "candidate_rows": len(candidates),
        "derived_pool_sha256": (
            candidate_receipt.get("pool_result_sha256")
            if args.derived
            else None
        ),
        "customer_parameter_count": len(customer_ids),
        "runner_sha256": digest(Path(__file__)),
        "source_tables": table_names,
        "source_metadata_before": metadata_before,
        "executed": False,
    }
    discovery_path = Path(__file__).with_name(DISCOVERY_SQL_NAME)
    discovery = _run_query(
        client,
        discovery_path.read_text(),
        discovery_path,
        "customer_ids",
        customer_ids,
        max_bytes=DISCOVERY_MAX_BYTES,
        prefix="txncat_sib_discovery_",
        execute=args.execute,
    )
    print(
        "Validated customer-account discovery SELECT: "
        f"{discovery['dry_run_bytes']:,} estimated bytes",
        flush=True,
    )
    receipt["queries"] = {
        "customer_accounts": {
            k: v for k, v in discovery.items() if k != "rows"
        }
    }
    if not args.execute:
        (args.output / "receipt.json").write_bytes(encode(receipt).encode())
        os.chmod(args.output / "receipt.json", 0o600)
        return
    discovery_rows = discovery["rows"]
    for row in discovery_rows:
        _validate_discovery_row(row)
    sibling_accounts = sorted(
        {row["account_id"] for row in discovery_rows} - candidate_accounts
    )
    runs = {"customer_accounts": discovery}
    for name, sql_path, bound, prefix, _validator, _out in sibling_specs:
        runs[name] = _run_query(
            client,
            sql_path.read_text(),
            sql_path,
            "account_ids",
            sibling_accounts,
            max_bytes=bound,
            prefix=prefix,
            execute=True,
        )
        print(
            f"Validated sibling {name} SELECT: "
            f"{runs[name]['dry_run_bytes']:,} estimated bytes, "
            f"{len(runs[name]['rows']):,} rows",
            flush=True,
        )
        receipt["queries"][name] = {
            k: v for k, v in runs[name].items() if k != "rows"
        }
    written = {}
    outputs = (
        ("customer_accounts", discovery_rows, _validate_discovery_row,
         "customer-accounts.jsonl"),
        *((name, runs[name]["rows"], validator, out)
          for name, _p, _b, _x, validator, out in sibling_specs),
    )
    for name, rows, validator, out_name in outputs:
        if len(rows) > 2_000_000:
            raise ValueError("unexpected sibling evidence size")
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
    summary = {
        "schema_version": "benchmark-sibling-evidence-summary-v1",
        "purpose": "g3_reconnect_evidence_not_authority",
        "authorizes_consumption": False,
        "candidate_result_sha256": candidate_receipt["result_sha256"],
        "candidate_customers": len(customer_ids),
        "customer_account_pairs": len(discovery_rows),
        "distinct_accounts_for_candidate_customers": len(
            {row["account_id"] for row in discovery_rows}
        ),
        "candidate_accounts": len(candidate_accounts),
        "sibling_accounts": len(sibling_accounts),
        "sibling_account_rows": len(account_rows),
        "sibling_pending_pairs": len(pending_rows),
        "sibling_unresolved_pending_pairs": sum(
            row["posted_history_rows"] == 0
            and row["current_materialized_rows"] == 0
            for row in pending_rows
        ),
        "sibling_collision_rows": len(runs["txid_collisions"]["rows"]),
        "sibling_accounts_with_identity_churn": sum(
            len(set(row["customer_ids"])) > 1 for row in account_rows
        ),
        "sibling_accounts_with_unresolved_links": sum(
            row["unresolved_link_rows"] > 0 for row in account_rows
        ),
        "source_rows": dict(
            sorted(Counter(row["source_table"] for row in account_rows).items())
        ),
    }
    (args.output / "summary.json").write_bytes(encode(summary).encode())
    receipt.update(
        executed=True,
        result_sha256={name: digest(path) for name, path in written.items()},
        result_rows={
            "customer_accounts": len(discovery_rows),
            **{name: len(runs[name]["rows"]) for name, _p, _b, _x, _v, _o in sibling_specs},
        },
        source_metadata_after=[
            metadata(client.get_table(name)) for name in table_names
        ],
    )
    (args.output / "receipt.json").write_bytes(encode(receipt).encode())
    os.chmod(args.output / "receipt.json", 0o600)
    print(
        f"Sibling evidence complete: {len(discovery_rows)} customer-account "
        f"pairs, {len(sibling_accounts)} sibling accounts, "
        f"{summary['sibling_unresolved_pending_pairs']} unresolved pending "
        f"pairs; no admission authorized."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit(
            "Sibling evidence extract failed; no admission claim is valid."
        ) from None

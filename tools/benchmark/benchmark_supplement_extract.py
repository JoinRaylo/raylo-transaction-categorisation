"""Proxy-targeted G3 rare-leaf supplement pool draw.

Builds the frozen roster's per-leaf predicates from the pinned research
artifacts — dictionary merchants, approved merchant lexicon, historical label
merchants, provider natives and rule patterns — then runs two bounded SELECTs:
a per-leaf capped targeted draw and a uniform tail draw so the
``baseline_prediction`` proxy can reach roster leaves with no lexicon signal.
The merged pool is a private candidate extract, not a reservation.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

from benchmark_candidate_frame_extract import (
    LOCATION,
    MAX_BYTES,
    PROJECT,
    SCOPE_CONTRACT,
    SCOPE_CONTRACT_SHA256,
    SCHEMA_VERSION,
    _validate_row,
    digest,
)
from benchmark_extract import encode, metadata
from benchmark_profile_candidate_frame import (
    _historical_label_map,
    _init_waterfall,
    _merchant_label_map,
)
from raylo_txncat.dictionary import normalise_merchant
from raylo_txncat.hashing import canonical_json, strict_json_loads

PURPOSE = "g3_supplement_pool_read_not_admission"
TARGETED_SQL_NAME = "benchmark_supplement_extract.sql"
TAIL_SQL_NAME = "benchmark_supplement_tail_extract.sql"
SPEC_SCHEMA = "benchmark-rare-leaf-spec-v1"
LEAF_CAP = 80
TAIL_LIMIT = 40_000
TARGETED_SEED = "g3-rare-leaf-targeted-2026-09-22-v1"
TAIL_SEED = "g3-rare-leaf-tail-2026-09-22-v1"
TAIL_MAX_BYTES = 20_000_000_000


def _build_leaf_specs(research: Path, roster: list[str]) -> list[dict[str, Any]]:
    """Per-leaf retrieval predicates; over-inclusion is verified downstream."""
    fe = _init_waterfall(research)
    lexicon = _merchant_label_map(research)
    historical = _historical_label_map(research)
    natives_by_leaf: dict[str, set[str]] = {}
    for native, leaf in fe.PLAID_MAP.items():
        natives_by_leaf.setdefault(leaf, set()).add(native)
    merchants_by_leaf: dict[str, set[str]] = {leaf: set() for leaf in roster}
    for mapping in (fe.DICTIONARY, lexicon, historical):
        for merchant, leaf in mapping.items():
            if leaf in merchants_by_leaf:
                merchants_by_leaf[leaf].add(normalise_merchant(merchant))
    merchant_patterns: dict[str, list[str]] = {leaf: [] for leaf in roster}
    description_patterns: dict[str, list[str]] = {leaf: [] for leaf in roster}
    for rule in fe.RULES:
        leaf = rule.get("detailed_category")
        if leaf not in merchant_patterns or rule.get("enabled") != "true":
            continue
        pattern = rule["pattern"]
        if rule["pattern_type"] != "regex":
            pattern = r"\b(" + pattern + r")\b"
        target = (
            merchant_patterns
            if rule["field"] == "merchant_name"
            else description_patterns
        )
        target[leaf].append(pattern)
    return [
        {
            "leaf": leaf,
            "merchants": sorted(merchants_by_leaf[leaf]),
            "natives": sorted(natives_by_leaf.get(leaf, ())),
            "merchant_patterns": merchant_patterns[leaf],
            "description_patterns": description_patterns[leaf],
        }
        for leaf in roster
    ]


def _run(client, sql, sql_path, params, *, max_bytes, prefix, execute):
    from google.cloud import bigquery  # noqa: PLC0415

    config = bigquery.QueryJobConfig(
        dry_run=True,
        use_query_cache=False,
        maximum_bytes_billed=max_bytes,
        query_parameters=params,
    )
    dry = client.query(sql, job_config=config, location=LOCATION)
    if dry.statement_type != "SELECT" or dry.total_bytes_processed > max_bytes:
        raise ValueError("supplement query is outside the bounded scope")
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
    parser.add_argument("--research", type=Path, required=True)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--private-predicates", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    os.umask(0o077)
    args.output.mkdir(mode=0o700, parents=False, exist_ok=False)
    spec = strict_json_loads(args.spec.read_bytes())
    if spec.get("schema_version") != SPEC_SCHEMA or spec.get("total") != 500:
        raise ValueError("rare-leaf specification is not the frozen artifact")
    roster = [entry["leaf"] for entry in spec["roster"]]
    if len(roster) != 25 or len(set(roster)) != 25:
        raise ValueError("rare-leaf roster is invalid")
    leaf_specs = _build_leaf_specs(args.research, roster)
    predicates = {
        "schema_version": "benchmark-leaf-predicates-v1",
        "authorizes_consumption": False,
        "spec_sha256": digest(args.spec),
        "leaf_cap": LEAF_CAP,
        "tail_limit": TAIL_LIMIT,
        "leaves": leaf_specs,
    }
    predicates_path = args.private_predicates
    predicates_path.write_bytes(canonical_json(predicates) + b"\n")
    os.chmod(predicates_path, 0o600)
    client = bigquery.Client(project=PROJECT, location=LOCATION)
    targeted_path = Path(__file__).with_name(TARGETED_SQL_NAME)
    tail_path = Path(__file__).with_name(TAIL_SQL_NAME)
    tables = sorted(
        set(
            re.findall(
                r"`(raylo-production\.[a-zA-Z0-9_]+\.[a-zA-Z0-9_]+)`",
                targeted_path.read_text() + tail_path.read_text(),
            )
        )
    )
    before = [metadata(client.get_table(table)) for table in tables]
    leaf_param = bigquery.ScalarQueryParameter(
        "leaf_specs_json", "STRING", json.dumps(leaf_specs)
    )
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "purpose": PURPOSE,
        "authorizes_consumption": False,
        "project": PROJECT,
        "location": LOCATION,
        "statement_type": "SELECT",
        "source_table": SCOPE_CONTRACT["source_table"],
        "source_kind": SCOPE_CONTRACT["source_kind"],
        "scope_contract": SCOPE_CONTRACT,
        "scope_contract_sha256": SCOPE_CONTRACT_SHA256,
        "anonymous_id_recovery": False,
        "spec_sha256": digest(args.spec),
        "leaf_predicates_sha256": digest(predicates_path),
        "seed": TARGETED_SEED,
        "tail_seed": TAIL_SEED,
        "leaf_cap": LEAF_CAP,
        "candidate_limit": LEAF_CAP * len(roster) + TAIL_LIMIT,
        "maximum_bytes_billed": MAX_BYTES,
        "sql_sha256": digest(targeted_path),
        "runner_sha256": digest(Path(__file__)),
        "source_metadata_before": before,
        "executed": False,
    }
    targeted = _run(
        client,
        targeted_path.read_text(),
        targeted_path,
        [
            leaf_param,
            bigquery.ScalarQueryParameter("leaf_cap", "INT64", LEAF_CAP),
            bigquery.ScalarQueryParameter("seed", "STRING", TARGETED_SEED),
        ],
        max_bytes=MAX_BYTES,
        prefix="txncat_supplement_",
        execute=args.execute,
    )
    print(
        "Validated supplement targeted SELECT: "
        f"{targeted['dry_run_bytes']:,} estimated bytes",
        flush=True,
    )
    tail = _run(
        client,
        tail_path.read_text(),
        tail_path,
        [
            bigquery.ScalarQueryParameter("tail_limit", "INT64", TAIL_LIMIT),
            bigquery.ScalarQueryParameter("seed", "STRING", TAIL_SEED),
        ],
        max_bytes=TAIL_MAX_BYTES,
        prefix="txncat_suptail_",
        execute=args.execute,
    )
    print(
        "Validated supplement tail SELECT: "
        f"{tail['dry_run_bytes']:,} estimated bytes",
        flush=True,
    )
    receipt["queries"] = {
        "targeted": {k: v for k, v in targeted.items() if k != "rows"},
        "tail": {k: v for k, v in tail.items() if k != "rows"},
    }
    if not args.execute:
        (args.output / "receipt.json").write_bytes(encode(receipt).encode())
        os.chmod(args.output / "receipt.json", 0o600)
        return
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for name, rows in (("targeted", targeted["rows"]), ("tail", tail["rows"])):
        for row in rows:
            row.pop("order_hash", None)
            hits = row.pop("leaf_hits") or []
            _validate_row(row)
            event = (row["account_id"], row["transaction_id"])
            if event in merged:
                merged[event]["leaf_hits"] = sorted(
                    set(merged[event]["leaf_hits"]) | set(hits)
                )
                continue
            row["leaf_hits"] = sorted(set(hits))
            row["supplement_source"] = name
            merged[event] = row
    ordered = sorted(
        merged.values(), key=lambda row: (row["account_id"], row["transaction_id"])
    )
    path = args.output / "candidates.jsonl"
    with path.open("x") as stream:
        for row in ordered:
            stream.write(encode(row))
    os.chmod(path, 0o600)
    receipt.update(
        executed=True,
        result_rows=len(ordered),
        result_sha256=digest(path),
        source_metadata_after=[
            metadata(client.get_table(table)) for table in tables
        ],
    )
    (args.output / "receipt.json").write_bytes(encode(receipt).encode())
    os.chmod(args.output / "receipt.json", 0o600)
    print(
        f"Supplement pool complete: {len(ordered):,} rows "
        f"({len(targeted['rows']):,} targeted, {len(tail['rows']):,} tail); "
        "no admission authorized."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit(
            "Supplement extract failed; no admission claim is valid."
        ) from None

"""Re-identify the approved v2 eval pilot rows from recovered opaque pilot IDs.

The 2026-09-18 private pilot artifact was lost with ``/private/tmp``.  Its 500
opaque item IDs survive in the provider batch results, and each ID is a
deterministic digest of the pinned candidate snapshot hash plus the Plaid
``account_id``/``transaction_id``.  This runner recomputes that digest inside a
bounded read-only SELECT over the same customer-linked link chain as the pinned
candidate draw and returns only rows whose digest is in the recovered ID set.

It is a recovery of an existing reservation, not a new draw: no ranking, no
seed, no limit.  Rows that cannot be re-identified are reported as missing, never
substituted.  Output is private (0600) and carries ``authorizes_consumption=false``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path

from benchmark_extract import MAX_BYTES, encode, metadata

PROJECT = "raylo-production"
LOCATION = "EU"
SOURCE_TABLE = "raylo-production.dbt_production.intermediate_credit_plaid_transactions"
PINNED_CANDIDATE_RESULT_SHA256 = "f9c549ee7a8a6bbfaec8999d3edaf2dca22f0d4f4fa463a486dcc3fd5a8f32ef"
PINNED_DRAW_SQL_SHA256 = "4b457cf50800416d9db25391f179e30559b0303b4bc7e3d4e9a9b5d9d5b853da"
PILOT_ID = re.compile(r"^pilot-v1-[0-9a-f]{64}$")
SAFE_ID = re.compile(r"^[A-Za-z0-9]+$")

# The link chain is the pinned draw's CTEs verbatim; only the final selection differs.
SQL = """
WITH source_observations AS (
  SELECT
    checkout_risk_assessment_result_id AS assessment_id,
    external_request_created_at,
    account_id,
    transaction_id,
    transaction_date,
    date_transacted,
    CAST(amount AS STRING) AS amount,
    CAST(NULL AS STRING) AS transaction_currency,
    transaction_name,
    merchant_name,
    description,
    reference_number,
    payment_method
  FROM `raylo-production.dbt_production.intermediate_credit_plaid_transactions`
  WHERE NULLIF(TRIM(checkout_risk_assessment_result_id), '') IS NOT NULL
    AND NULLIF(TRIM(account_id), '') IS NOT NULL
    AND NULLIF(TRIM(transaction_id), '') IS NOT NULL
), assessment_links AS (
  SELECT
    checkout_risk_assessment_result_id AS assessment_id,
    COUNT(DISTINCT checkout_id) AS checkout_count,
    MIN(checkout_id) AS checkout_id
  FROM `raylo-production.dbt_production.intermediate_raylo_production__checkout_risk_assessment_results_latest`
  WHERE NULLIF(TRIM(checkout_risk_assessment_result_id), '') IS NOT NULL
    AND NULLIF(TRIM(checkout_id), '') IS NOT NULL
  GROUP BY assessment_id
), checkout_links AS (
  SELECT
    checkout_id,
    COUNT(DISTINCT NULLIF(TRIM(user_id), '')) AS user_count,
    MIN(NULLIF(TRIM(user_id), '')) AS user_id,
    LOGICAL_OR(is_business_checkout) AS is_business_checkout,
    ARRAY_AGG(DISTINCT state IGNORE NULLS ORDER BY state) AS checkout_states
  FROM `raylo-production.dbt_production.stg_raylo_production__checkouts`
  WHERE NULLIF(TRIM(checkout_id), '') IS NOT NULL
  GROUP BY checkout_id
), user_links AS (
  SELECT
    user_id,
    COUNT(DISTINCT NULLIF(TRIM(customer_id), '')) AS customer_count,
    MIN(NULLIF(TRIM(customer_id), '')) AS customer_id
  FROM `raylo-production.dbt_production.stg_raylo_production__users`
  WHERE NULLIF(TRIM(user_id), '') IS NOT NULL
  GROUP BY user_id
), customer_links AS (
  SELECT
    NULLIF(TRIM(customer_id), '') AS customer_id,
    COUNT(*) AS customer_record_count
  FROM `raylo-production.dbt_production.stg_raylo_production__customers`
  WHERE NULLIF(TRIM(customer_id), '') IS NOT NULL
  GROUP BY customer_id
), linked AS (
  SELECT
    s.*,
    a.checkout_count,
    a.checkout_id,
    c.user_count,
    c.user_id,
    c.is_business_checkout,
    c.checkout_states,
    u.customer_count,
    u.customer_id,
    cr.customer_record_count
  FROM source_observations s
  JOIN assessment_links a USING (assessment_id)
  JOIN checkout_links c ON a.checkout_count = 1 AND a.checkout_id = c.checkout_id
  JOIN user_links u ON c.user_count = 1 AND c.user_id = u.user_id
  JOIN customer_links cr
    ON u.customer_count = 1
    AND u.customer_id = cr.customer_id
    AND cr.customer_record_count = 1
), ranked AS (
  SELECT
    linked.*,
    CASE
      WHEN SAFE_CAST(amount AS FLOAT64) < 0 THEN 'credit'
      WHEN SAFE_CAST(amount AS FLOAT64) > 0 THEN 'debit'
      ELSE 'zero'
    END AS direction,
    IF(NULLIF(TRIM(merchant_name), '') IS NULL, 'blank', 'present') AS merchant_presence,
    CASE
      WHEN is_business_checkout THEN 'business'
      WHEN is_business_checkout = FALSE THEN 'consumer'
      ELSE 'unknown'
    END AS checkout_scope
  FROM linked
), identified AS (
  SELECT
    ranked.*,
    CONCAT(
      'pilot-v1-',
      TO_HEX(SHA256(CONCAT(
        '{"account_id":"', account_id,
        '","source_snapshot_sha256":"', @snapshot,
        '","transaction_id":"', transaction_id, '"}'
      )))
    ) AS pilot_id
  FROM ranked
  WHERE REGEXP_CONTAINS(account_id, r'^[A-Za-z0-9]+$')
    AND REGEXP_CONTAINS(transaction_id, r'^[A-Za-z0-9]+$')
)
SELECT
  assessment_id,
  checkout_count AS assessment_checkout_count,
  external_request_created_at,
  account_id,
  transaction_id,
  transaction_date,
  date_transacted,
  amount,
  transaction_currency,
  transaction_name,
  merchant_name,
  description,
  reference_number,
  payment_method,
  checkout_id,
  user_count AS checkout_user_count,
  user_id,
  customer_count AS user_customer_count,
  customer_id,
  customer_record_count,
  is_business_checkout,
  checkout_states,
  direction,
  merchant_presence,
  checkout_scope,
  CONCAT(direction, '/', merchant_presence, '/', checkout_scope) AS source_stratum,
  pilot_id
FROM identified
WHERE pilot_id IN UNNEST(@pilot_ids)
ORDER BY pilot_id
"""


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def canonical_pilot_id(account_id: str, transaction_id: str, snapshot: str) -> str:
    body = json.dumps(
        {
            "account_id": account_id,
            "source_snapshot_sha256": snapshot,
            "transaction_id": transaction_id,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return "pilot-v1-" + hashlib.sha256(body).hexdigest()


def anthropic_custom_id(pilot_id: str) -> str:
    return "pilot-v1-" + hashlib.sha256(pilot_id.encode("utf-8")).hexdigest()[:48]


def load_gemini_item_ids(path: Path) -> set[str]:
    payload = json.loads(path.read_text())
    responses = payload["response"]["inlinedResponses"]["inlinedResponses"]
    ids = [entry["metadata"]["item_id"] for entry in responses]
    if len(ids) != len(set(ids)) or any(not PILOT_ID.fullmatch(item) for item in ids):
        raise ValueError(f"{path.name}: duplicate or malformed pilot IDs")
    return set(ids)


def load_anthropic_custom_ids(path: Path) -> set[str]:
    ids = [json.loads(line)["custom_id"] for line in path.read_text().splitlines() if line]
    if len(ids) != len(set(ids)):
        raise ValueError(f"{path.name}: duplicate custom IDs")
    return set(ids)


def main() -> None:
    from google.cloud import bigquery

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gemini-batch", type=Path, action="append", required=True)
    parser.add_argument("--anthropic-results", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="New private directory")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    os.umask(0o077)

    id_sets = [load_gemini_item_ids(path) for path in args.gemini_batch]
    pilot_ids = id_sets[0]
    if any(other != pilot_ids for other in id_sets[1:]):
        raise ValueError("recovered Gemini batches disagree on the pilot ID set")
    if len(pilot_ids) != 500:
        raise ValueError(f"expected 500 recovered pilot IDs, found {len(pilot_ids)}")
    anthropic_ids = load_anthropic_custom_ids(args.anthropic_results)
    if {anthropic_custom_id(item) for item in pilot_ids} != anthropic_ids:
        raise ValueError("Anthropic custom IDs do not match the recovered Gemini pilot IDs")
    ordered_ids = sorted(pilot_ids)
    id_set_sha256 = hashlib.sha256("\n".join(ordered_ids).encode()).hexdigest()

    sql_path = Path(__file__).with_name("benchmark_candidate_extract.sql")
    if digest(sql_path) != PINNED_DRAW_SQL_SHA256:
        raise ValueError("pinned candidate draw SQL has changed; refusing to reuse its link chain")

    args.output.mkdir(mode=0o700, parents=False, exist_ok=False)
    client = bigquery.Client(project=PROJECT, location=LOCATION)
    before = metadata(client.get_table(SOURCE_TABLE))
    parameters = [
        bigquery.ScalarQueryParameter("snapshot", "STRING", PINNED_CANDIDATE_RESULT_SHA256),
        bigquery.ArrayQueryParameter("pilot_ids", "STRING", ordered_ids),
    ]
    config = bigquery.QueryJobConfig(
        dry_run=True,
        use_query_cache=False,
        maximum_bytes_billed=MAX_BYTES,
        query_parameters=parameters,
    )
    dry = client.query(SQL, job_config=config, location=LOCATION)
    if dry.statement_type != "SELECT" or dry.total_bytes_processed > MAX_BYTES:
        raise ValueError("recovery query outside read-only budget")
    receipt = {
        "schema_version": "benchmark-eval-pilot-recovery-v1",
        "purpose": "re_identify_existing_v2_eval_pilot_reservation",
        "authorizes_consumption": False,
        "new_draw": False,
        "project": PROJECT,
        "location": LOCATION,
        "statement_type": "SELECT",
        "source_table": SOURCE_TABLE,
        "pinned_candidate_result_sha256": PINNED_CANDIDATE_RESULT_SHA256,
        "pinned_draw_sql_sha256": PINNED_DRAW_SQL_SHA256,
        "recovery_sql_sha256": hashlib.sha256(SQL.encode()).hexdigest(),
        "runner_sha256": digest(Path(__file__)),
        "pilot_id_count": len(ordered_ids),
        "pilot_id_set_sha256": id_set_sha256,
        "gemini_batch_files_sha256": {str(p): digest(p) for p in args.gemini_batch},
        "anthropic_results_sha256": digest(args.anthropic_results),
        "maximum_bytes_billed": MAX_BYTES,
        "dry_run_bytes": dry.total_bytes_processed,
        "source_metadata_before": before,
        "executed": False,
    }
    print(f"Validated recovery SELECT: {dry.total_bytes_processed:,} estimated bytes", flush=True)
    if args.execute:
        config.dry_run = False
        job = client.query(
            SQL, job_config=config, location=LOCATION, job_id_prefix="txncat_pilot_recover_"
        )
        rows = job.result(page_size=1000)
        found: dict[str, dict] = {}
        path = args.output / "candidates.jsonl"
        with path.open("x") as stream:
            for row in rows:
                value = dict(row)
                pilot_id = value["pilot_id"]
                if pilot_id in found:
                    raise ValueError("recovery returned a duplicate pilot ID")
                if not SAFE_ID.fullmatch(value["account_id"]) or not SAFE_ID.fullmatch(
                    value["transaction_id"]
                ):
                    raise ValueError("recovered row has an unsafe identifier")
                if (
                    canonical_pilot_id(
                        value["account_id"],
                        value["transaction_id"],
                        PINNED_CANDIDATE_RESULT_SHA256,
                    )
                    != pilot_id
                ):
                    raise ValueError("SQL pilot digest disagrees with the Python canonical digest")
                if pilot_id not in pilot_ids:
                    raise ValueError("recovery returned a pilot ID outside the recovered set")
                link_counts = (
                    "assessment_checkout_count",
                    "checkout_user_count",
                    "user_customer_count",
                    "customer_record_count",
                )
                if any(
                    type(value.get(field)) is not int or value[field] != 1 for field in link_counts
                ):
                    raise ValueError("recovered row is not backed by unique current links")
                found[pilot_id] = value
                stream.write(encode(value))
        os.chmod(path, 0o600)
        missing = sorted(pilot_ids - set(found))
        (args.output / "missing-pilot-ids.json").write_text(json.dumps(missing, indent=2) + "\n")
        os.chmod(args.output / "missing-pilot-ids.json", 0o600)
        receipt.update(
            executed=True,
            job_id=job.job_id,
            started_at=job.started,
            ended_at=job.ended,
            bytes_processed=job.total_bytes_processed,
            bytes_billed=job.total_bytes_billed,
            result_rows=len(found),
            result_sha256=digest(path),
            missing_pilot_ids=len(missing),
            distinct_accounts=len({v["account_id"] for v in found.values()}),
            distinct_customers=len({v["customer_id"] for v in found.values()}),
            source_metadata_after=metadata(client.get_table(SOURCE_TABLE)),
            captured_at=datetime.now(UTC).isoformat(),
        )
        print(
            f"Recovered {len(found)}/500 pilot rows; missing {len(missing)}; "
            f"accounts {receipt['distinct_accounts']}, customers {receipt['distinct_customers']}",
            flush=True,
        )
    receipt_path = args.output / "receipt.json"
    with receipt_path.open("x") as stream:
        stream.write(json.dumps(receipt, indent=2, sort_keys=True, default=str) + "\n")
    os.chmod(receipt_path, 0o600)


if __name__ == "__main__":
    main()

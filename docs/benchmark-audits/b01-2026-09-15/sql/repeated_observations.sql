-- Bounded raw-ingestion window; these counts do not cover all historical repeats.
WITH observations AS (
  SELECT external_request_id, transaction_id, account_id,
    checkout_risk_assessment_result_id, COUNT(*) AS ingested_versions,
    COUNT(DISTINCT TO_JSON_STRING(STRUCT(amount, merchant_name, description, transaction_name,
      transaction_date, detailed_credit_category))) AS distinct_payload_versions
  FROM `raylo-production.landing_external_requests.external_requests_taktile_plaid_transactions`
  WHERE external_request_created_at >= TIMESTAMP '2026-08-16 00:00:00+00'
    AND external_request_created_at < TIMESTAMP '2026-09-16 00:00:00+00'
  GROUP BY external_request_id, transaction_id, account_id, checkout_risk_assessment_result_id
), events AS (
  SELECT transaction_id, COUNT(*) AS observations,
    COUNT(DISTINCT external_request_id) AS requests,
    COUNT(DISTINCT account_id) AS accounts,
    COUNT(DISTINCT checkout_risk_assessment_result_id) AS assessments
  FROM observations GROUP BY transaction_id
)
SELECT
  (SELECT SUM(ingested_versions) FROM observations) AS raw_ingested_rows,
  (SELECT COUNT(*) FROM observations) AS distinct_observation_groups,
  (SELECT COUNTIF(ingested_versions > 1) FROM observations) AS repeated_ingestion_groups,
  (SELECT COUNTIF(distinct_payload_versions > 1) FROM observations) AS changed_payload_groups,
  COUNT(*) AS transaction_id_groups,
  COUNTIF(requests > 1) AS transaction_ids_multiple_requests,
  COUNTIF(accounts > 1) AS transaction_ids_multiple_accounts,
  COUNTIF(assessments > 1) AS transaction_ids_multiple_assessments
FROM events

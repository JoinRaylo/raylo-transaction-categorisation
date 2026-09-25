-- Full account/report tables; the transaction join is limited to the same raw window.
WITH accounts AS (
  SELECT external_request_id, account_id, COUNT(*) AS versions,
    COUNT(DISTINCT account_currency_code) AS currencies,
    COUNT(DISTINCT account_subtype) AS subtypes
  FROM `raylo-production.landing_external_requests.external_requests_taktile_plaid_accounts`
  GROUP BY external_request_id, account_id
), tx_keys AS (
  SELECT DISTINCT external_request_id, account_id
  FROM `raylo-production.landing_external_requests.external_requests_taktile_plaid_transactions`
  WHERE external_request_created_at >= TIMESTAMP '2026-08-16 00:00:00+00'
    AND external_request_created_at < TIMESTAMP '2026-09-16 00:00:00+00'
), reports AS (
  SELECT * FROM `raylo-production.landing_external_requests.external_requests_taktile_plaid_asset_reports`
)
SELECT
  (SELECT COUNT(*) FROM reports) AS report_rows,
  (SELECT COUNTIF(NULLIF(TRIM(asset_report_id), '') IS NULL) FROM reports) AS missing_asset_report_id,
  (SELECT COUNTIF(NULLIF(TRIM(client_report_id), '') IS NULL) FROM reports) AS missing_client_report_id,
  (SELECT COUNTIF(NULLIF(TRIM(report_date_generated), '') IS NULL) FROM reports) AS missing_report_date_generated,
  (SELECT COUNTIF(SAFE_CAST(days_requested AS INT64) IS NULL) FROM reports) AS missing_or_invalid_days_requested,
  (SELECT MIN(SAFE_CAST(report_date_generated AS TIMESTAMP)) FROM reports) AS min_report_generated_at,
  (SELECT MAX(SAFE_CAST(report_date_generated AS TIMESTAMP)) FROM reports) AS max_report_generated_at,
  COUNT(*) AS recent_transaction_request_account_pairs,
  COUNTIF(a.versions IS NULL) AS recent_pairs_missing_account_record,
  COUNTIF(a.currencies = 0) AS recent_pairs_missing_account_currency,
  COUNTIF(a.currencies > 1) AS recent_pairs_ambiguous_account_currency,
  COUNTIF(a.subtypes = 0) AS recent_pairs_missing_account_subtype,
  COUNTIF(a.subtypes > 1) AS recent_pairs_ambiguous_account_subtype
FROM tx_keys t LEFT JOIN accounts a USING (external_request_id, account_id)

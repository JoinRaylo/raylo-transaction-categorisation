-- Aggregate-only historical source audit. No row identifiers or narratives returned.
WITH base AS (
  SELECT * FROM `raylo-production.dbt_production.credit_plaid_open_banking_transactions`
), event_groups AS (
  SELECT transaction_id, COUNT(*) AS n,
    COUNT(DISTINCT account_id) AS accounts,
    COUNT(DISTINCT customer_id) AS customers,
    COUNT(DISTINCT asset_report_id) AS reports
  FROM base GROUP BY transaction_id
), account_groups AS (
  SELECT account_id, COUNT(DISTINCT customer_id) AS customers
  FROM base WHERE NULLIF(TRIM(account_id), '') IS NOT NULL GROUP BY account_id
)
SELECT
  COUNT(*) AS row_count,
  COUNT(DISTINCT transaction_id) AS distinct_transaction_ids,
  COUNT(DISTINCT account_id) AS distinct_account_ids,
  COUNT(DISTINCT customer_id) AS distinct_customer_ids,
  COUNT(DISTINCT asset_report_id) AS distinct_asset_report_ids,
  COUNT(DISTINCT pk) AS distinct_row_pks,
  COUNTIF(NULLIF(TRIM(transaction_id), '') IS NULL) AS missing_transaction_id,
  COUNTIF(NULLIF(TRIM(account_id), '') IS NULL) AS missing_account_id,
  COUNTIF(NULLIF(TRIM(customer_id), '') IS NULL) AS missing_customer_id,
  COUNTIF(NULLIF(TRIM(asset_report_id), '') IS NULL) AS missing_report_id,
  COUNTIF(amount < 0) AS credits, COUNTIF(amount > 0) AS positive_debits,
  COUNTIF(amount = 0) AS zero_amounts, COUNTIF(amount IS NULL) AS missing_amount,
  COUNTIF(NULLIF(TRIM(merchant_name), '') IS NULL) AS blank_merchant,
  COUNTIF(NULLIF(TRIM(COALESCE(original_description, transaction_name)), '') IS NULL) AS blank_effective_description,
  COUNTIF(iso_currency_code = 'GBP') AS gbp_rows,
  COUNTIF(iso_currency_code IS NULL) AS missing_currency,
  COUNTIF(is_pending) AS pending_rows, COUNTIF(is_pending IS NULL) AS missing_pending,
  MIN(transaction_date) AS min_transaction_date, MAX(transaction_date) AS max_transaction_date,
  MIN(created_at) AS min_source_created_at, MAX(created_at) AS max_source_created_at,
  MAX(updated_at) AS max_source_updated_at,
  (SELECT COUNTIF(n > 1) FROM event_groups) AS repeated_transaction_id_groups,
  (SELECT COUNTIF(accounts > 1) FROM event_groups) AS transaction_ids_multiple_accounts,
  (SELECT COUNTIF(customers > 1) FROM event_groups) AS transaction_ids_multiple_customers,
  (SELECT COUNTIF(reports > 1) FROM event_groups) AS transaction_ids_multiple_reports,
  (SELECT COUNTIF(customers > 1) FROM account_groups) AS accounts_multiple_customers
FROM base

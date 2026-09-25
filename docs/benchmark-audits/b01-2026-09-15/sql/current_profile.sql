-- Current materialized table: already deduplicated globally by transaction_id.
SELECT
  FORMAT_DATE('%Y-%m', SAFE_CAST(transaction_date AS DATE)) AS transaction_month,
  COUNT(*) AS row_count,
  COUNT(DISTINCT transaction_id) AS distinct_transaction_ids,
  COUNT(DISTINCT account_id) AS distinct_account_ids,
  COUNT(DISTINCT checkout_risk_assessment_result_id) AS distinct_assessment_ids,
  COUNTIF(NULLIF(TRIM(transaction_id), '') IS NULL) AS missing_transaction_id,
  COUNTIF(NULLIF(TRIM(account_id), '') IS NULL) AS missing_account_id,
  COUNTIF(NULLIF(TRIM(checkout_risk_assessment_result_id), '') IS NULL) AS missing_assessment_id,
  COUNTIF(amount < 0) AS credits, COUNTIF(amount > 0) AS positive_debits,
  COUNTIF(amount = 0) AS zero_amounts, COUNTIF(amount IS NULL) AS missing_amount,
  COUNTIF(IS_NAN(amount) OR IS_INF(amount)) AS nonfinite_amounts,
  COUNTIF(NULLIF(TRIM(merchant_name), '') IS NULL) AS blank_merchant,
  COUNTIF(amount < 0 AND NULLIF(TRIM(merchant_name), '') IS NULL) AS blank_merchant_credits,
  COUNTIF(NULLIF(TRIM(COALESCE(description, transaction_name)), '') IS NULL) AS blank_effective_description,
  COUNTIF(NULLIF(TRIM(detailed_credit_category), '') IS NULL) AS missing_provider_detailed_category,
  COUNTIF(transaction_date IS NOT NULL AND SAFE_CAST(transaction_date AS DATE) IS NULL) AS invalid_transaction_dates,
  COUNTIF(SAFE_CAST(transaction_date AS DATE) > DATE '2026-09-15') AS future_transaction_dates,
  MIN(SAFE_CAST(transaction_date AS DATE)) AS min_transaction_date,
  MAX(SAFE_CAST(transaction_date AS DATE)) AS max_transaction_date,
  MIN(external_request_created_at) AS min_observed_request_at,
  MAX(external_request_created_at) AS max_observed_request_at
FROM `raylo-production.dbt_production.intermediate_credit_plaid_transactions`
GROUP BY transaction_month ORDER BY transaction_month

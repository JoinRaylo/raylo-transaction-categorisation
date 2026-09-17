-- Reduce the checkout-item-grain bridge before joining; measure ambiguous links.
-- The 7 Sep cutoff is a screening scenario, not a clean-benchmark certificate.
WITH links AS (
  SELECT checkout_risk_assessment_result_id,
    COUNT(*) AS bridge_rows,
    COUNT(DISTINCT customer_id) AS customer_count,
    MIN(customer_id) AS single_customer_id,
    MIN(customer_created_at) AS earliest_customer_created_at
  FROM `raylo-production.dbt_production.intermediate_core_aggregated_identities`
  WHERE NULLIF(TRIM(checkout_risk_assessment_result_id), '') IS NOT NULL
  GROUP BY checkout_risk_assessment_result_id
), old_customers AS (
  SELECT DISTINCT customer_id
  FROM `raylo-production.dbt_production.credit_plaid_open_banking_transactions`
  WHERE NULLIF(TRIM(customer_id), '') IS NOT NULL
), joined AS (
  SELECT t.transaction_id, t.account_id, t.checkout_risk_assessment_result_id,
    l.bridge_rows, l.customer_count,
    IF(l.customer_count = 1, l.single_customer_id, NULL) AS customer_id,
    l.earliest_customer_created_at,
    old.customer_id IS NOT NULL AS in_legacy_customer_population,
    SAFE_CAST(t.transaction_date AS DATE) AS transaction_date
  FROM `raylo-production.dbt_production.intermediate_credit_plaid_transactions` t
  LEFT JOIN links l USING (checkout_risk_assessment_result_id)
  LEFT JOIN old_customers old ON l.customer_count = 1 AND l.single_customer_id = old.customer_id
), accounts AS (
  SELECT account_id, COUNT(DISTINCT customer_id) AS customers
  FROM joined WHERE NULLIF(TRIM(account_id), '') IS NOT NULL GROUP BY account_id
)
SELECT COUNT(*) AS row_count,
  COUNTIF(bridge_rows IS NULL) AS rows_without_bridge,
  COUNTIF(customer_count = 0) AS rows_bridge_without_customer,
  COUNTIF(customer_count > 1) AS rows_ambiguous_customer,
  COUNTIF(customer_count = 1) AS rows_unique_customer,
  COUNTIF(bridge_rows > 1) AS rows_with_multirow_bridge,
  COUNT(DISTINCT IF(customer_count = 1, customer_id, NULL)) AS unique_linked_customers,
  COUNTIF(in_legacy_customer_population) AS rows_in_legacy_customer_population,
  COUNTIF(customer_count = 1 AND NOT in_legacy_customer_population) AS rows_customer_absent_from_legacy,
  COUNTIF(customer_count = 1 AND earliest_customer_created_at >= TIMESTAMP '2026-09-07 00:00:00+00') AS rows_new_customer_since_sep7,
  COUNT(DISTINCT IF(customer_count = 1 AND earliest_customer_created_at >= TIMESTAMP '2026-09-07 00:00:00+00', customer_id, NULL)) AS new_customers_since_sep7,
  COUNTIF(customer_count = 1 AND earliest_customer_created_at >= TIMESTAMP '2026-09-07 00:00:00+00'
    AND transaction_date >= DATE '2026-09-07') AS rows_both_event_and_customer_since_sep7,
  (SELECT COUNTIF(customers > 1) FROM accounts) AS accounts_multiple_linked_customers,
  (SELECT COUNTIF(customers = 0) FROM accounts) AS accounts_without_linked_customer
FROM joined

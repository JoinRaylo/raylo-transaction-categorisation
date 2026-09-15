-- Authoritative ID joins only. No matching on email/name/phone/account masks.
-- User identity is an application identity, not proof of a unique natural person.
WITH checkout_links AS (
  SELECT checkout_id, COUNT(DISTINCT user_id) AS user_count, MIN(user_id) AS user_id,
    COUNTIF(is_business_checkout) > 0 AS is_business_checkout
  FROM `raylo-production.dbt_production.stg_raylo_production__checkouts` GROUP BY checkout_id
), user_links AS (
  SELECT user_id, COUNT(DISTINCT customer_id) AS customer_count,
    MIN(customer_id) AS customer_id, MIN(created_at) AS user_created_at
  FROM `raylo-production.dbt_production.stg_raylo_production__users` GROUP BY user_id
), assessment_links AS (
  SELECT checkout_risk_assessment_result_id, COUNT(DISTINCT checkout_id) AS checkout_count,
    MIN(checkout_id) AS checkout_id
  FROM `raylo-production.dbt_production.intermediate_raylo_production__checkout_risk_assessment_results_latest`
  GROUP BY checkout_risk_assessment_result_id
), observations AS (
  SELECT 'current' AS scope, transaction_id, account_id, checkout_risk_assessment_result_id,
    SAFE_CAST(transaction_date AS DATE) AS transaction_date
  FROM `raylo-production.dbt_production.intermediate_credit_plaid_transactions`
  UNION ALL
  SELECT 'historical', transaction_id, account_id, checkout_risk_assessment_result_id, transaction_date
  FROM `raylo-production.dbt_production.credit_plaid_open_banking_transactions`
), linked AS (
  SELECT o.*, a.checkout_count, c.user_count,
    IF(c.user_count = 1 AND a.checkout_count = 1, c.user_id, NULL) AS user_id,
    u.user_created_at, u.customer_count,
    IF(u.customer_count = 1 AND c.user_count = 1 AND a.checkout_count = 1, u.customer_id, NULL) AS customer_id,
    c.is_business_checkout
  FROM observations o
  LEFT JOIN assessment_links a USING (checkout_risk_assessment_result_id)
  LEFT JOIN checkout_links c ON a.checkout_count = 1 AND a.checkout_id = c.checkout_id
  LEFT JOIN user_links u ON c.user_count = 1 AND c.user_id = u.user_id
), historical_users AS (
  SELECT DISTINCT user_id FROM linked WHERE scope = 'historical' AND user_id IS NOT NULL
), account_links AS (
  SELECT scope, account_id, COUNT(DISTINCT user_id) AS users, COUNT(DISTINCT customer_id) AS customers
  FROM linked GROUP BY scope, account_id
)
SELECT l.scope, COUNT(*) AS row_count,
  COUNTIF(l.checkout_count IS NULL) AS rows_missing_assessment_link,
  COUNTIF(l.checkout_count > 1) AS rows_ambiguous_checkout,
  COUNTIF(l.user_count > 1) AS rows_ambiguous_user,
  COUNTIF(l.user_id IS NOT NULL) AS rows_with_unique_user,
  COUNTIF(l.user_created_at IS NULL) AS rows_missing_user_record_or_created_at,
  COUNT(DISTINCT l.user_id) AS distinct_linked_users,
  COUNTIF(l.customer_count > 1) AS rows_ambiguous_customer,
  COUNTIF(l.customer_id IS NOT NULL) AS rows_with_unique_customer,
  COUNT(DISTINCT l.customer_id) AS distinct_linked_customers,
  COUNTIF(l.is_business_checkout) AS business_checkout_rows,
  COUNTIF(l.is_business_checkout IS NULL) AS rows_unknown_business_scope,
  COUNTIF(h.user_id IS NOT NULL) AS rows_user_present_in_historical_population,
  COUNTIF(l.user_id IS NOT NULL AND h.user_id IS NULL) AS rows_user_absent_from_historical_population,
  COUNTIF(l.user_id IS NOT NULL AND l.user_created_at >= TIMESTAMP '2026-09-07 00:00:00+00') AS rows_user_created_since_sep7,
  COUNT(DISTINCT IF(l.user_created_at >= TIMESTAMP '2026-09-07 00:00:00+00', l.user_id, NULL)) AS users_created_since_sep7,
  COUNTIF(l.user_created_at >= TIMESTAMP '2026-09-07 00:00:00+00' AND transaction_date >= DATE '2026-09-07') AS rows_both_user_and_event_since_sep7,
  (SELECT COUNTIF(users > 1) FROM account_links a WHERE a.scope = l.scope) AS accounts_multiple_users,
  (SELECT COUNTIF(customers > 1) FROM account_links a WHERE a.scope = l.scope) AS accounts_multiple_customers
FROM linked l LEFT JOIN historical_users h ON l.user_id = h.user_id
GROUP BY scope ORDER BY scope

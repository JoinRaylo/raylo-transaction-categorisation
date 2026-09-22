-- Bounded per-account evidence for the G3 admission design.
-- SELECT-only aggregate over the candidate account set: observation counts,
-- pending-state coverage, resolved customer identity and account attributes.
-- Pending/reconnect alias certification uses only retained materialized
-- history; no raw payloads are read and no content similarity is inferred.
WITH candidate_accounts AS (
  SELECT account_id
  FROM UNNEST(@account_ids) AS account_id
), assessment_links AS (
  SELECT
    checkout_risk_assessment_result_id AS assessment_id,
    COUNT(DISTINCT checkout_id) AS checkout_count,
    MIN(checkout_id) AS checkout_id
  FROM `raylo-production.dbt_production.intermediate_raylo_production__checkout_risk_assessment_results_latest`
  GROUP BY assessment_id
), checkout_links AS (
  SELECT
    checkout_id,
    COUNT(DISTINCT NULLIF(TRIM(user_id), '')) AS user_count,
    MIN(NULLIF(TRIM(user_id), '')) AS user_id
  FROM `raylo-production.dbt_production.stg_raylo_production__checkouts`
  GROUP BY checkout_id
), user_links AS (
  SELECT
    user_id,
    COUNT(DISTINCT NULLIF(TRIM(customer_id), '')) AS customer_count,
    MIN(NULLIF(TRIM(customer_id), '')) AS customer_id
  FROM `raylo-production.dbt_production.stg_raylo_production__users`
  GROUP BY user_id
), customer_records AS (
  SELECT
    NULLIF(TRIM(customer_id), '') AS customer_id,
    COUNT(*) AS customer_record_count
  FROM `raylo-production.dbt_production.stg_raylo_production__customers`
  WHERE NULLIF(TRIM(customer_id), '') IS NOT NULL
  GROUP BY customer_id
), observations AS (
  SELECT
    'current_materialized' AS source_table,
    t.account_id,
    t.transaction_id,
    CAST(NULL AS BOOL) AS is_pending,
    IF(
      a.checkout_count = 1
      AND c.user_count = 1
      AND u.customer_count = 1
      AND cr.customer_record_count = 1,
      u.customer_id,
      NULL
    ) AS resolved_customer_id,
    CAST(t.transaction_date AS STRING) AS transaction_date,
    CAST(NULL AS STRING) AS account_mask,
    CAST(NULL AS STRING) AS account_name,
    CAST(NULL AS STRING) AS account_subtype,
    CAST(NULL AS STRING) AS institution_hint
  FROM `raylo-production.dbt_production.intermediate_credit_plaid_transactions` t
  JOIN candidate_accounts ca
    ON t.account_id = ca.account_id
  LEFT JOIN assessment_links a
    ON t.checkout_risk_assessment_result_id = a.assessment_id
  LEFT JOIN checkout_links c
    ON a.checkout_count = 1 AND a.checkout_id = c.checkout_id
  LEFT JOIN user_links u
    ON c.user_count = 1 AND c.user_id = u.user_id
  LEFT JOIN customer_records cr
    ON u.customer_count = 1 AND u.customer_id = cr.customer_id
  UNION ALL
  SELECT
    'plaid_materialized_history' AS source_table,
    h.account_id,
    h.transaction_id,
    h.is_pending,
    NULLIF(TRIM(h.customer_id), '') AS resolved_customer_id,
    CAST(h.transaction_date AS STRING) AS transaction_date,
    CAST(h.account_mask AS STRING) AS account_mask,
    CAST(h.account_name AS STRING) AS account_name,
    CAST(h.account_subtype AS STRING) AS account_subtype,
    CAST(NULL AS STRING) AS institution_hint
  FROM `raylo-production.dbt_production.credit_plaid_open_banking_transactions` h
  JOIN candidate_accounts ca
    ON h.account_id = ca.account_id
)
SELECT
  source_table,
  account_id,
  COUNT(*) AS observation_rows,
  COUNT(DISTINCT transaction_id) AS distinct_transactions,
  COUNTIF(is_pending IS TRUE) AS pending_rows,
  ARRAY_AGG(
    DISTINCT IF(is_pending IS TRUE, transaction_id, NULL) IGNORE NULLS
    LIMIT 1000
  ) AS pending_transaction_ids,
  COUNTIF(is_pending IS NULL) AS pending_state_unknown_rows,
  COUNT(DISTINCT resolved_customer_id) AS distinct_customers,
  ARRAY_AGG(DISTINCT resolved_customer_id IGNORE NULLS LIMIT 20) AS customer_ids,
  COUNTIF(resolved_customer_id IS NULL) AS unresolved_link_rows,
  MIN(transaction_date) AS first_observation_date,
  MAX(transaction_date) AS last_observation_date,
  ARRAY_AGG(DISTINCT account_mask IGNORE NULLS LIMIT 20) AS account_masks,
  ARRAY_AGG(DISTINCT account_name IGNORE NULLS LIMIT 20) AS account_names,
  ARRAY_AGG(DISTINCT account_subtype IGNORE NULLS LIMIT 20) AS account_subtypes
FROM observations
GROUP BY source_table, account_id

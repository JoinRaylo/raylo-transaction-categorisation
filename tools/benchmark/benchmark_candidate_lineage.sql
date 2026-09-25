-- Bounded lineage evidence for one private customer-linked candidate draw.
-- The query is SELECT-only and returns private rows for exact candidate pairs.
-- The older materialized Plaid table has pending state/report history but does
-- not expose pending_transaction_id; the local summariser must not infer an
-- alias certificate from repeated transaction IDs alone.
WITH candidate_events AS (
  SELECT account_id, transaction_id
  FROM UNNEST(@candidate_pairs)
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
), current_materialized AS (
  SELECT
    'current_materialized' AS source_kind,
    CAST(t.external_request_created_at AS STRING) AS observation_at,
    t.checkout_risk_assessment_result_id AS assessment_id,
    t.account_id,
    t.transaction_id,
    CAST(t.transaction_date AS STRING) AS transaction_date,
    CAST(t.date_transacted AS STRING) AS date_transacted,
    CAST(t.amount AS STRING) AS amount,
    t.merchant_name,
    t.transaction_name,
    t.description,
    CAST(NULL AS STRING) AS asset_report_id,
    CAST(NULL AS STRING) AS report_date_generated,
    CAST(NULL AS STRING) AS client_report_id,
    CAST(NULL AS BOOL) AS is_pending,
    CAST(NULL AS STRING) AS pending_transaction_id,
    CAST(NULL AS STRING) AS source_customer_id,
    IF(
      a.checkout_count = 1
      AND c.user_count = 1
      AND u.customer_count = 1
      AND cr.customer_record_count = 1,
      u.customer_id,
      NULL
    ) AS linked_customer_id,
    a.checkout_count,
    c.user_count,
    u.customer_count,
    cr.customer_record_count
  FROM `raylo-production.dbt_production.intermediate_credit_plaid_transactions` t
  JOIN candidate_events e
    ON t.account_id = e.account_id AND t.transaction_id = e.transaction_id
  LEFT JOIN assessment_links a
    ON t.checkout_risk_assessment_result_id = a.assessment_id
  LEFT JOIN checkout_links c
    ON a.checkout_count = 1 AND a.checkout_id = c.checkout_id
  LEFT JOIN user_links u
    ON c.user_count = 1 AND c.user_id = u.user_id
  LEFT JOIN customer_records cr
    ON u.customer_count = 1 AND u.customer_id = cr.customer_id
), plaid_history AS (
  SELECT
    'plaid_materialized_history' AS source_kind,
    CAST(h.updated_at AS STRING) AS observation_at,
    h.checkout_risk_assessment_result_id AS assessment_id,
    h.account_id,
    h.transaction_id,
    CAST(h.transaction_date AS STRING) AS transaction_date,
    CAST(NULL AS STRING) AS date_transacted,
    CAST(h.amount AS STRING) AS amount,
    h.merchant_name,
    h.transaction_name,
    h.original_description AS description,
    h.asset_report_id,
    h.report_date_generated,
    h.client_report_id,
    h.is_pending,
    CAST(NULL AS STRING) AS pending_transaction_id,
    h.customer_id AS source_customer_id,
    CAST(NULL AS STRING) AS linked_customer_id,
    CAST(NULL AS INT64) AS checkout_count,
    CAST(NULL AS INT64) AS user_count,
    CAST(NULL AS INT64) AS customer_count,
    CAST(NULL AS INT64) AS customer_record_count
  FROM `raylo-production.dbt_production.credit_plaid_open_banking_transactions` h
  JOIN candidate_events e
    ON h.account_id = e.account_id AND h.transaction_id = e.transaction_id
)
SELECT * FROM current_materialized
UNION ALL
SELECT * FROM plaid_history
ORDER BY account_id, transaction_id, source_kind, observation_at, assessment_id

-- Bounded reconnect-discovery evidence for the G3 admission design.
-- SELECT-only aggregate: for each candidate customer, every distinct
-- account_id attributed to that customer in retained materialized history
-- plus every account whose current-materialized rows resolve to that
-- customer through the unambiguous assessment -> checkout -> user ->
-- customer chain.  This extends reconnect/sibling coverage beyond the
-- candidate account set: a customer's other linked accounts are the only
-- places a pending or reconnect duplicate of a candidate event could
-- materialize.
WITH candidate_customers AS (
  SELECT customer_id
  FROM UNNEST(@customer_ids) AS customer_id
), history_pairs AS (
  SELECT
    h.customer_id AS customer_id,
    h.account_id AS account_id,
    COUNT(*) AS observation_rows,
    COUNT(DISTINCT h.transaction_id) AS distinct_transactions,
    COUNTIF(h.is_pending IS TRUE) AS pending_rows,
    MIN(CAST(h.transaction_date AS STRING)) AS first_observation_date,
    MAX(CAST(h.transaction_date AS STRING)) AS last_observation_date
  FROM `raylo-production.dbt_production.credit_plaid_open_banking_transactions` h
  JOIN candidate_customers cc
    ON h.customer_id = cc.customer_id
  GROUP BY customer_id, account_id
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
), current_pairs AS (
  SELECT
    u.customer_id AS customer_id,
    t.account_id AS account_id,
    COUNT(*) AS observation_rows,
    COUNT(DISTINCT t.transaction_id) AS distinct_transactions,
    0 AS pending_rows,
    MIN(CAST(t.transaction_date AS STRING)) AS first_observation_date,
    MAX(CAST(t.transaction_date AS STRING)) AS last_observation_date
  FROM `raylo-production.dbt_production.intermediate_credit_plaid_transactions` t
  JOIN assessment_links a
    ON t.checkout_risk_assessment_result_id = a.assessment_id
    AND a.checkout_count = 1
  JOIN checkout_links c
    ON a.checkout_id = c.checkout_id
    AND c.user_count = 1
  JOIN user_links u
    ON c.user_id = u.user_id
    AND u.customer_count = 1
  JOIN customer_records cr
    ON u.customer_id = cr.customer_id
    AND cr.customer_record_count = 1
  JOIN candidate_customers cc
    ON u.customer_id = cc.customer_id
  GROUP BY customer_id, account_id
), pairs AS (
  SELECT
    customer_id,
    account_id,
    SUM(observation_rows) AS observation_rows,
    SUM(distinct_transactions) AS distinct_transactions,
    SUM(pending_rows) AS pending_rows,
    MIN(first_observation_date) AS first_observation_date,
    MAX(last_observation_date) AS last_observation_date
  FROM (
    SELECT * FROM history_pairs
    UNION ALL
    SELECT * FROM current_pairs
  )
  GROUP BY customer_id, account_id
)
SELECT * FROM pairs

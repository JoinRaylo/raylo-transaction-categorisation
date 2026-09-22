-- Uniform G3 supplement tail draw.  Same linked spine as the candidate frame
-- with an empty leaf_hits array; the tail exists so the baseline_prediction
-- proxy can reach roster leaves with no dictionary/lexicon/provider signal.
-- Source draw for admission engineering, not a benchmark reservation.
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
    payment_method,
    category,
    primary_credit_category,
    detailed_credit_category
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
  category,
  primary_credit_category,
  detailed_credit_category,
  TO_HEX(SHA256(TO_JSON_STRING(STRUCT(
    transaction_date,
    date_transacted,
    amount,
    transaction_name,
    merchant_name,
    description,
    reference_number,
    payment_method,
    category,
    primary_credit_category,
    detailed_credit_category
  )))) AS content_sha256,
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
  CONCAT(direction, '/', merchant_presence, '/', checkout_scope) AS source_stratum
  , ARRAY<STRING>[] AS leaf_hits
FROM ranked
ORDER BY
  TO_HEX(SHA256(CONCAT(@seed, ':', account_id, ':', transaction_id))),
  account_id,
  transaction_id
LIMIT @tail_limit

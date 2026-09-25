-- Full-range aggregate profile of the current materialized Plaid pool.
-- The materialized relation is already one row per transaction_id (B01 source
-- semantics); this query does not claim to measure repeats in the raw CDC feed.
-- One output row; no raw IDs, contacts, narratives, or source rows are returned.
-- Identity admission is existing assessment -> checkout -> user -> customer
-- linkage only. No natural-key matching or anonymous recovery is performed.
WITH
source_observations AS (
  SELECT
    'plaid' AS provider,
    checkout_risk_assessment_result_id AS assessment_id,
    account_id,
    transaction_id,
    SAFE_CAST(transaction_date AS DATE) AS transaction_date,
    SAFE_CAST(amount AS FLOAT64) AS amount,
    transaction_name,
    merchant_name,
    description,
    reference_number,
    payment_method,
    category,
    primary_credit_category,
    detailed_credit_category,
    FARM_FINGERPRINT(TO_JSON_STRING(STRUCT(
      transaction_date,
      amount,
      transaction_name,
      merchant_name,
      description,
      reference_number,
      payment_method,
      category,
      primary_credit_category,
      detailed_credit_category
    ))) AS content_signature
  FROM `raylo-production.dbt_production.intermediate_credit_plaid_transactions`
),
assessment_links AS (
  SELECT
    checkout_risk_assessment_result_id AS assessment_id,
    COUNT(DISTINCT checkout_id) AS checkout_count,
    MIN(checkout_id) AS checkout_id
  FROM `raylo-production.dbt_production.intermediate_raylo_production__checkout_risk_assessment_results_latest`
  WHERE NULLIF(TRIM(checkout_risk_assessment_result_id), '') IS NOT NULL
    AND NULLIF(TRIM(checkout_id), '') IS NOT NULL
  GROUP BY assessment_id
),
checkout_links AS (
  SELECT
    checkout_id,
    COUNT(DISTINCT NULLIF(TRIM(user_id), '')) AS user_count,
    MIN(NULLIF(TRIM(user_id), '')) AS user_id,
    LOGICAL_OR(is_business_checkout) AS is_business_checkout
  FROM `raylo-production.dbt_production.stg_raylo_production__checkouts`
  WHERE NULLIF(TRIM(checkout_id), '') IS NOT NULL
  GROUP BY checkout_id
),
user_links AS (
  SELECT
    user_id,
    COUNT(DISTINCT NULLIF(TRIM(customer_id), '')) AS customer_count,
    MIN(NULLIF(TRIM(customer_id), '')) AS customer_id
  FROM `raylo-production.dbt_production.stg_raylo_production__users`
  WHERE NULLIF(TRIM(user_id), '') IS NOT NULL
  GROUP BY user_id
),
customer_links AS (
  SELECT
    NULLIF(TRIM(customer_id), '') AS customer_id,
    COUNT(*) AS customer_record_count
  FROM `raylo-production.dbt_production.stg_raylo_production__customers`
  WHERE NULLIF(TRIM(customer_id), '') IS NOT NULL
  GROUP BY customer_id
),
observations_with_identity AS (
  SELECT
    s.*,
    a.checkout_count,
    c.user_count,
    c.is_business_checkout,
    u.customer_count,
    cr.customer_record_count,
    IF(a.checkout_count = 1, a.checkout_id, NULL) AS linked_checkout_id,
    IF(a.checkout_count = 1 AND c.user_count = 1, c.user_id, NULL) AS linked_user_id,
    IF(a.checkout_count = 1 AND c.user_count = 1 AND u.customer_count = 1,
       u.customer_id, NULL) AS linked_customer_id,
    (
      a.checkout_count = 1
      AND c.user_count = 1
      AND u.customer_count = 1
      AND NULLIF(TRIM(u.customer_id), '') IS NOT NULL
      AND cr.customer_record_count = 1
    ) AS is_unambiguous_customer_link
  FROM source_observations s
  LEFT JOIN assessment_links a USING (assessment_id)
  LEFT JOIN checkout_links c ON a.checkout_count = 1 AND a.checkout_id = c.checkout_id
  LEFT JOIN user_links u ON c.user_count = 1 AND c.user_id = u.user_id
  LEFT JOIN customer_links cr ON u.customer_count = 1 AND u.customer_id = cr.customer_id
),
linked_observations AS (
  SELECT * FROM observations_with_identity
  WHERE is_unambiguous_customer_link
),
event_key_stats AS (
  SELECT
    provider,
    account_id,
    transaction_id,
    COUNT(*) AS observation_count,
    COUNT(DISTINCT content_signature) AS content_variant_count
  FROM linked_observations
  WHERE NULLIF(TRIM(account_id), '') IS NOT NULL
    AND NULLIF(TRIM(transaction_id), '') IS NOT NULL
  GROUP BY provider, account_id, transaction_id
),
account_customer_pairs AS (
  SELECT
    account_id,
    linked_customer_id AS customer_id,
    COUNT(*) AS observation_count
  FROM linked_observations
  WHERE NULLIF(TRIM(account_id), '') IS NOT NULL
  GROUP BY account_id, customer_id
),
account_breadth AS (
  SELECT account_id, COUNT(DISTINCT customer_id) AS linked_customer_count
  FROM account_customer_pairs
  GROUP BY account_id
),
customer_breadth AS (
  SELECT customer_id, COUNT(DISTINCT account_id) AS linked_account_count
  FROM account_customer_pairs
  GROUP BY customer_id
),
direction_strata AS (
  SELECT
    CASE
      WHEN amount IS NULL OR IS_NAN(amount) OR IS_INF(amount) THEN 'invalid_or_blank'
      WHEN amount < 0 THEN 'credit_negative'
      WHEN amount > 0 THEN 'debit_positive'
      ELSE 'zero'
    END AS direction,
    COUNT(*) AS observations
  FROM linked_observations
  GROUP BY direction
),
magnitude_strata AS (
  SELECT
    CASE
      WHEN amount IS NULL OR IS_NAN(amount) OR IS_INF(amount) THEN 'invalid_or_blank'
      WHEN ABS(amount) = 0 THEN 'zero'
      WHEN ABS(amount) < 10 THEN 'under_10'
      WHEN ABS(amount) < 50 THEN '10_to_under_50'
      WHEN ABS(amount) < 100 THEN '50_to_under_100'
      WHEN ABS(amount) < 500 THEN '100_to_under_500'
      WHEN ABS(amount) < 1000 THEN '500_to_under_1000'
      ELSE '1000_or_more'
    END AS magnitude_bucket,
    COUNT(*) AS observations
  FROM linked_observations
  GROUP BY magnitude_bucket
),
merchant_strata AS (
  SELECT
    IF(NULLIF(TRIM(merchant_name), '') IS NULL, 'blank', 'present') AS merchant_presence,
    COUNT(*) AS observations
  FROM linked_observations
  GROUP BY merchant_presence
),
direction_merchant_strata AS (
  SELECT
    CASE
      WHEN amount IS NULL OR IS_NAN(amount) OR IS_INF(amount) THEN 'invalid_or_blank'
      WHEN amount < 0 THEN 'credit_negative'
      WHEN amount > 0 THEN 'debit_positive'
      ELSE 'zero'
    END AS direction,
    IF(NULLIF(TRIM(merchant_name), '') IS NULL, 'blank', 'present') AS merchant_presence,
    COUNT(*) AS observations
  FROM linked_observations
  GROUP BY direction, merchant_presence
),
business_strata AS (
  SELECT
    CASE WHEN is_business_checkout THEN 'business'
         WHEN is_business_checkout = FALSE THEN 'consumer'
         ELSE 'unknown'
    END AS checkout_scope,
    COUNT(*) AS observations
  FROM linked_observations
  GROUP BY checkout_scope
),
proxy_category_strata AS (
  SELECT 'legacy_category_array_PROXY' AS category_source,
         IF(category IS NULL OR ARRAY_LENGTH(category) = 0, 'missing', 'present') AS availability,
         COUNT(*) AS observations
  FROM linked_observations
  GROUP BY 2
  UNION ALL
  SELECT 'primary_credit_category_PROXY',
         IF(NULLIF(TRIM(primary_credit_category), '') IS NULL, 'missing', 'present'),
         COUNT(*)
  FROM linked_observations
  GROUP BY 2
  UNION ALL
  SELECT 'detailed_credit_category_PROXY',
         IF(NULLIF(TRIM(detailed_credit_category), '') IS NULL, 'missing', 'present'),
         COUNT(*)
  FROM linked_observations
  GROUP BY 2
),
month_strata AS (
  SELECT FORMAT_DATE('%Y-%m', transaction_date) AS transaction_month,
         COUNT(*) AS observations
  FROM linked_observations
  WHERE transaction_date IS NOT NULL
  GROUP BY transaction_month
),
customer_breadth_strata AS (
  SELECT
    CASE
      WHEN linked_account_count = 0 THEN 'zero_accounts'
      WHEN linked_account_count = 1 THEN 'one_account'
      WHEN linked_account_count BETWEEN 2 AND 5 THEN 'two_to_five_accounts'
      WHEN linked_account_count BETWEEN 6 AND 10 THEN 'six_to_ten_accounts'
      ELSE 'over_ten_accounts'
    END AS account_breadth_bucket,
    COUNT(*) AS customers
  FROM customer_breadth
  GROUP BY account_breadth_bucket
)
SELECT
  COUNT(*) AS source_materialized_observation_rows,
  COUNT(DISTINCT NULLIF(TRIM(assessment_id), '')) AS source_distinct_assessments,
  COUNT(DISTINCT NULLIF(TRIM(account_id), '')) AS source_distinct_accounts,
  COUNT(DISTINCT NULLIF(TRIM(transaction_id), '')) AS source_distinct_transaction_ids,
  COUNTIF(NULLIF(TRIM(assessment_id), '') IS NULL) AS source_rows_missing_assessment_id,
  COUNTIF(NULLIF(TRIM(account_id), '') IS NULL) AS source_rows_missing_account_id,
  COUNTIF(NULLIF(TRIM(transaction_id), '') IS NULL) AS source_rows_missing_transaction_id,
  COUNTIF(NULLIF(TRIM(assessment_id), '') IS NOT NULL AND checkout_count IS NULL) AS rows_missing_assessment_checkout_link,
  COUNTIF(checkout_count > 1) AS rows_ambiguous_assessment_checkout_link,
  COUNTIF(checkout_count = 1 AND COALESCE(user_count, 0) = 0) AS rows_missing_checkout_user_link,
  COUNTIF(checkout_count = 1 AND user_count > 1) AS rows_ambiguous_checkout_user_link,
  COUNTIF(checkout_count = 1 AND user_count = 1 AND COALESCE(customer_count, 0) = 0) AS rows_missing_user_customer_link,
  COUNTIF(checkout_count = 1 AND user_count = 1 AND customer_count > 1) AS rows_ambiguous_user_customer_link,
  COUNTIF(checkout_count = 1 AND user_count = 1 AND customer_count = 1 AND customer_record_count IS NULL) AS rows_missing_customer_record,
  COUNTIF(checkout_count = 1 AND user_count = 1 AND customer_count = 1 AND customer_record_count > 1) AS rows_ambiguous_customer_record,
  COUNTIF(is_unambiguous_customer_link) AS unambiguous_customer_linked_observations,
  COUNT(DISTINCT IF(is_unambiguous_customer_link, linked_checkout_id, NULL)) AS unambiguous_linked_checkouts,
  COUNT(DISTINCT IF(is_unambiguous_customer_link, linked_user_id, NULL)) AS unambiguous_linked_users,
  COUNT(DISTINCT IF(is_unambiguous_customer_link, linked_customer_id, NULL)) AS unambiguous_linked_customers,
  COUNT(*) - COUNTIF(is_unambiguous_customer_link) AS identity_missing_or_conflicting_observations_excluded,
  COUNTIF(is_unambiguous_customer_link AND NULLIF(TRIM(account_id), '') IS NOT NULL) AS linked_rows_with_usable_account_id,
  COUNTIF(is_unambiguous_customer_link AND NULLIF(TRIM(transaction_id), '') IS NOT NULL) AS linked_rows_with_usable_transaction_id,
  COUNTIF(is_unambiguous_customer_link AND NULLIF(TRIM(account_id), '') IS NOT NULL AND NULLIF(TRIM(transaction_id), '') IS NOT NULL) AS linked_rows_with_usable_event_key,
  (SELECT COUNT(*) FROM event_key_stats) AS linked_distinct_provider_account_transaction_keys,
  (SELECT COUNTIF(observation_count > 1) FROM event_key_stats) AS linked_repeated_event_key_count,
  (SELECT COALESCE(SUM(observation_count - 1), 0) FROM event_key_stats) AS linked_repeated_event_observations,
  (SELECT COUNTIF(content_variant_count > 1) FROM event_key_stats) AS linked_changed_content_variant_event_key_count,
  (SELECT COALESCE(SUM(IF(content_variant_count > 1, observation_count, 0)), 0) FROM event_key_stats) AS linked_changed_content_variant_observations,
  (SELECT COUNT(*) FROM account_customer_pairs) AS linked_distinct_account_customer_pairs,
  (SELECT COUNT(*) FROM account_breadth) AS linked_accounts_with_customer,
  (SELECT COUNTIF(linked_customer_count > 1) FROM account_breadth) AS linked_accounts_with_multiple_customers,
  (SELECT COUNT(*) FROM customer_breadth) AS linked_customers_with_account,
  (SELECT COALESCE(SUM(linked_account_count), 0) FROM customer_breadth) AS linked_customer_account_pair_count_check,
  MIN(IF(is_unambiguous_customer_link, transaction_date, NULL)) AS linked_min_transaction_date,
  MAX(IF(is_unambiguous_customer_link, transaction_date, NULL)) AS linked_max_transaction_date,
  COUNTIF(is_unambiguous_customer_link AND transaction_date IS NULL) AS linked_invalid_or_blank_transaction_date_observations,
  COUNT(DISTINCT IF(is_unambiguous_customer_link AND transaction_date IS NOT NULL, FORMAT_DATE('%Y-%m', transaction_date), NULL)) AS linked_distinct_transaction_months,
  ARRAY(SELECT AS STRUCT direction, observations FROM direction_strata ORDER BY direction) AS linked_direction_strata,
  ARRAY(SELECT AS STRUCT magnitude_bucket, observations FROM magnitude_strata ORDER BY magnitude_bucket) AS linked_magnitude_strata,
  ARRAY(SELECT AS STRUCT merchant_presence, observations FROM merchant_strata ORDER BY merchant_presence) AS linked_merchant_presence_strata,
  ARRAY(SELECT AS STRUCT direction, merchant_presence, observations FROM direction_merchant_strata ORDER BY direction, merchant_presence) AS linked_direction_merchant_strata,
  ARRAY(SELECT AS STRUCT category_source, availability, observations FROM proxy_category_strata ORDER BY category_source, availability) AS linked_provider_category_availability_PROXY_strata,
  ARRAY(SELECT AS STRUCT transaction_month, observations FROM month_strata ORDER BY transaction_month) AS linked_transaction_month_strata,
  ARRAY(SELECT AS STRUCT account_breadth_bucket, customers FROM customer_breadth_strata ORDER BY account_breadth_bucket) AS linked_customer_account_breadth_strata,
  ARRAY(SELECT AS STRUCT checkout_scope, observations FROM business_strata ORDER BY checkout_scope) AS linked_checkout_scope_strata
FROM observations_with_identity;

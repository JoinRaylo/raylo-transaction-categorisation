-- Source-level proxy, not an exact local-corpus or model-consumption membership test.
-- Counts only Plaid historical sentence projections; excludes Equifax/other learning
-- and does not account for tokenizer truncation, customer isolation or label quality.
WITH both_sources AS (
  SELECT 'historical' AS scope, amount,
    LOWER(TRIM(IFNULL(merchant_name, ''))) AS merchant,
    LOWER(TRIM(IFNULL(COALESCE(original_description, transaction_name), ''))) AS description,
    transaction_date
  FROM `raylo-production.dbt_production.credit_plaid_open_banking_transactions`
  UNION ALL
  SELECT 'current', amount,
    LOWER(TRIM(IFNULL(merchant_name, ''))),
    LOWER(TRIM(IFNULL(COALESCE(description, transaction_name), ''))),
    SAFE_CAST(transaction_date AS DATE)
  FROM `raylo-production.dbt_production.intermediate_credit_plaid_transactions`
), projected AS (
  SELECT scope, transaction_date, merchant, amount < 0 AS is_credit,
    TO_JSON_STRING(STRUCT(
      IF(amount < 0, 'credit', 'debit') AS direction,
      CASE WHEN ABS(amount) < 5 THEN 'AMT_0_5' WHEN ABS(amount) < 20 THEN 'AMT_5_20'
        WHEN ABS(amount) < 50 THEN 'AMT_20_50' WHEN ABS(amount) < 100 THEN 'AMT_50_100'
        WHEN ABS(amount) < 250 THEN 'AMT_100_250' WHEN ABS(amount) < 500 THEN 'AMT_250_500'
        WHEN ABS(amount) < 1000 THEN 'AMT_500_1K' WHEN ABS(amount) < 2500 THEN 'AMT_1K_2500'
        ELSE 'AMT_2500_PLUS' END AS amount_band,
      merchant AS merchant, description AS description)) AS sentence_key
  FROM both_sources
), historical AS (
  SELECT DISTINCT sentence_key FROM projected
  WHERE scope = 'historical'
)
SELECT FORMAT_DATE('%Y-%m', transaction_date) AS transaction_month,
  p.is_credit, p.merchant = '' AS blank_merchant,
  COUNT(*) AS current_rows,
  COUNTIF(h.sentence_key IS NOT NULL) AS matches_historical_plaid_sentence,
  COUNTIF(h.sentence_key IS NULL) AS no_match_to_historical_plaid_sentence,
  (SELECT COUNT(*) FROM historical) AS historical_distinct_sentence_keys
FROM projected p LEFT JOIN historical h USING (sentence_key)
WHERE p.scope = 'current'
GROUP BY transaction_month, is_credit, blank_merchant
ORDER BY transaction_month, is_credit, blank_merchant

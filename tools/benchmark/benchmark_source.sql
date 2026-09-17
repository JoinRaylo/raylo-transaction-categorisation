-- Engineering sample only: hash-ranked requests in one ingestion/request day.
-- Project Plaid fields in BigQuery; never export whole applicant/credit payloads.
-- Source partition and request bounds are both explicit. Latest is within this
-- bounded snapshot, not a claim of the latest version across all history.
WITH requests AS (
  SELECT id, resource_id, created_at, updated_at, _airbyte_raw_id,
    _airbyte_extracted_at, response
  FROM `raylo-production.airbyte_raylo_prod_no_cdc.external_requests`
  WHERE _airbyte_extracted_at >= TIMESTAMP(@source_day)
    AND _airbyte_extracted_at < TIMESTAMP(DATE_ADD(@source_day, INTERVAL 1 DAY))
    AND created_at >= DATETIME(@source_day)
    AND created_at < DATETIME(DATE_ADD(@source_day, INTERVAL 1 DAY))
    AND provider = 'Taktile' AND resource_type = 'CheckoutRiskAssessmentResult'
    AND description = 'Get decision status' AND id IS NOT NULL
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY id ORDER BY updated_at DESC, _airbyte_extracted_at DESC, _airbyte_raw_id DESC
  ) = 1
), reports AS (
  SELECT r.* EXCEPT(response), node_offset,
    SAFE.PARSE_JSON(COALESCE(JSON_VALUE(node, '$.raw_response'),
                            JSON_QUERY(node, '$.raw_response'))) AS raw_report
  FROM requests r, UNNEST(JSON_QUERY_ARRAY(response, '$.body.raw_provider_responses')) node
    WITH OFFSET node_offset
  WHERE JSON_VALUE(node, '$.resource') = 'asset_report'
), sampled_requests AS (
  SELECT id FROM reports WHERE JSON_TYPE(JSON_QUERY(raw_report, '$.report')) = 'object'
  GROUP BY id ORDER BY TO_HEX(SHA256(CONCAT('b02-source-engineering-v1:', id))), id
  LIMIT @request_limit
), assessment_links AS (
  SELECT checkout_risk_assessment_result_id, COUNT(DISTINCT checkout_id) AS checkout_count,
    MIN(checkout_id) AS checkout_id
  FROM `raylo-production.dbt_production.intermediate_raylo_production__checkout_risk_assessment_results_latest`
  GROUP BY checkout_risk_assessment_result_id
), checkout_links AS (
  SELECT checkout_id, COUNT(DISTINCT user_id) AS user_count, MIN(user_id) AS user_id,
    LOGICAL_OR(is_business_checkout) AS is_business_checkout
  FROM `raylo-production.dbt_production.stg_raylo_production__checkouts` GROUP BY checkout_id
), user_links AS (
  SELECT user_id, COUNT(DISTINCT customer_id) AS customer_count,
    MIN(customer_id) AS customer_id, MIN(created_at) AS user_created_at
  FROM `raylo-production.dbt_production.stg_raylo_production__users` GROUP BY user_id
)
SELECT r.id AS external_request_id, r.resource_id AS assessment_id,
  r.created_at AS request_created_at, r.updated_at AS request_updated_at,
  r._airbyte_raw_id AS source_row_id, r._airbyte_extracted_at AS source_ingested_at,
  r.node_offset, item_offset, account_offset, transaction_offset,
  JSON_VALUE(raw_report, '$.report.asset_report_id') AS report_id,
  JSON_VALUE(raw_report, '$.report.date_generated') AS report_generated_at,
  JSON_VALUE(raw_report, '$.report.days_requested') AS days_requested,
  JSON_VALUE(item, '$.item_id') AS item_id,
  JSON_VALUE(item, '$.institution_id') AS institution_id,
  JSON_VALUE(item, '$.date_last_updated') AS item_updated_at,
  JSON_VALUE(account, '$.account_id') AS account_id,
  JSON_VALUE(account, '$.subtype') AS account_subtype,
  JSON_VALUE(account, '$.balances.iso_currency_code') AS account_currency,
  JSON_VALUE(tx, '$.transaction_id') AS transaction_id,
  JSON_VALUE(tx, '$.date') AS transaction_date,
  JSON_VALUE(tx, '$.date_transacted') AS date_transacted,
  JSON_VALUE(tx, '$.amount') AS amount,
  JSON_VALUE(tx, '$.iso_currency_code') AS transaction_currency,
  JSON_VALUE(tx, '$.unofficial_currency_code') AS transaction_unofficial_currency,
  JSON_TYPE(JSON_QUERY(tx, '$.pending')) AS pending_json_type,
  JSON_VALUE(tx, '$.pending') AS pending,
  JSON_VALUE(tx, '$.pending_transaction_id') AS pending_transaction_id,
  JSON_TYPE(JSON_QUERY(tx, '$.pending_transaction_id')) AS pending_alias_json_type,
  JSON_VALUE(tx, '$.merchant_name') AS merchant_name,
  JSON_VALUE(tx, '$.name') AS transaction_name,
  JSON_VALUE(tx, '$.original_description') AS description,
  JSON_VALUE(tx, '$.credit_category.primary') AS primary_credit_category,
  JSON_VALUE(tx, '$.credit_category.detailed') AS detailed_credit_category,
  JSON_VALUE(tx, '$.credit_category.confidence_level') AS credit_category_confidence,
  JSON_VALUE(tx, '$.personal_finance_category.primary') AS primary_personal_finance_category,
  JSON_VALUE(tx, '$.personal_finance_category.detailed') AS detailed_personal_finance_category,
  JSON_VALUE(tx, '$.personal_finance_category.confidence_level') AS personal_finance_confidence,
  JSON_VALUE_ARRAY(tx, '$.category') AS legacy_categories,
  JSON_VALUE(tx, '$.payment_meta.reference_number') AS reference_number,
  JSON_VALUE(tx, '$.payment_meta.payment_method') AS payment_method,
  a.checkout_count, c.user_count, u.customer_count,
  IF(a.checkout_count = 1 AND c.user_count = 1, c.user_id, NULL) AS user_id,
  IF(a.checkout_count = 1 AND c.user_count = 1 AND u.customer_count = 1,
     u.customer_id, NULL) AS customer_id,
  u.user_created_at, c.is_business_checkout
FROM reports r JOIN sampled_requests s USING(id)
CROSS JOIN UNNEST(JSON_QUERY_ARRAY(raw_report, '$.report.items')) item WITH OFFSET item_offset
CROSS JOIN UNNEST(JSON_QUERY_ARRAY(item, '$.accounts')) account WITH OFFSET account_offset
CROSS JOIN UNNEST(JSON_QUERY_ARRAY(account, '$.transactions')) tx WITH OFFSET transaction_offset
LEFT JOIN assessment_links a ON r.resource_id = a.checkout_risk_assessment_result_id
LEFT JOIN checkout_links c ON a.checkout_count = 1 AND a.checkout_id = c.checkout_id
LEFT JOIN user_links u ON c.user_count = 1 AND c.user_id = u.user_id
ORDER BY external_request_id, node_offset, item_offset, account_offset, transaction_offset

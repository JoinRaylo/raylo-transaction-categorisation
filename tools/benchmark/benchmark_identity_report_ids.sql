-- Read the same source records as the immutable engineering extract. Project only IDs.
WITH reports AS (
 SELECT id AS external_request_id, resource_id AS assessment_id,
   SAFE.PARSE_JSON(COALESCE(JSON_VALUE(node,'$.raw_response'),JSON_QUERY(node,'$.raw_response'))) AS payload
 FROM `raylo-production.airbyte_raylo_prod_no_cdc.external_requests`,
   UNNEST(JSON_QUERY_ARRAY(response,'$.body.raw_provider_responses')) node
 WHERE _airbyte_extracted_at >= TIMESTAMP(@source_day)
   AND _airbyte_extracted_at < TIMESTAMP(DATE_ADD(@source_day, INTERVAL 1 DAY))
   AND _airbyte_raw_id IN UNNEST(@source_row_ids)
   AND JSON_VALUE(node,'$.resource')='asset_report'
)
SELECT external_request_id, assessment_id,
 JSON_VALUE(payload,'$.report.asset_report_id') AS report_id,
 JSON_VALUE(payload,'$.report.client_report_id') AS client_report_id,
 JSON_VALUE(payload,'$.report.user.client_user_id') AS client_user_id,
 JSON_VALUE(item,'$.item_id') AS item_id,
 JSON_VALUE(account,'$.account_id') AS account_id,
 JSON_VALUE(account,'$.persistent_account_id') AS persistent_account_id
FROM reports, UNNEST(JSON_QUERY_ARRAY(payload,'$.report.items')) item,
 UNNEST(JSON_QUERY_ARRAY(item,'$.accounts')) account
ORDER BY external_request_id,item_id,account_id

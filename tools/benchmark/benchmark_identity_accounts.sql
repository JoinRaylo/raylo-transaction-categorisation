-- Conservative group evidence from the same provider account across assessments.
-- This does not assert a unique natural person or resolve reconnected account IDs.
WITH observations AS (
 SELECT DISTINCT account_id, checkout_risk_assessment_result_id
 FROM `raylo-production.dbt_production.intermediate_credit_plaid_transactions`
 WHERE account_id IN UNNEST(@account_ids)
 UNION DISTINCT
 SELECT DISTINCT account_id, checkout_risk_assessment_result_id
 FROM `raylo-production.dbt_production.credit_plaid_open_banking_transactions`
 WHERE account_id IN UNNEST(@account_ids)
), assessments AS (
 SELECT checkout_risk_assessment_result_id, COUNT(DISTINCT checkout_id) AS checkout_count,
 MIN(checkout_id) AS checkout_id
 FROM `raylo-production.dbt_production.intermediate_raylo_production__checkout_risk_assessment_results_latest`
 GROUP BY 1
), checkouts AS (
 SELECT checkout_id, COUNT(DISTINCT user_id) AS user_count, MIN(user_id) AS user_id
 FROM `raylo-production.dbt_production.stg_raylo_production__checkouts` GROUP BY 1
), users AS (
 SELECT user_id, COUNT(DISTINCT customer_id) AS customer_count, MIN(customer_id) AS customer_id
 FROM `raylo-production.dbt_production.stg_raylo_production__users` GROUP BY 1
)
SELECT o.account_id, COUNT(DISTINCT o.checkout_risk_assessment_result_id) AS assessments,
 COUNT(DISTINCT IF(a.checkout_count=1 AND c.user_count=1,c.user_id,NULL)) AS users,
 COUNT(DISTINCT IF(a.checkout_count=1 AND c.user_count=1 AND u.customer_count=1,u.customer_id,NULL)) AS customers,
 ARRAY_AGG(DISTINCT IF(a.checkout_count=1 AND c.user_count=1,c.user_id,NULL) IGNORE NULLS) AS user_ids,
 ARRAY_AGG(DISTINCT IF(a.checkout_count=1 AND c.user_count=1 AND u.customer_count=1,u.customer_id,NULL) IGNORE NULLS) AS customer_ids,
 COUNTIF(a.checkout_count>1 OR c.user_count>1 OR u.customer_count>1) AS ambiguous_link_rows
FROM observations o
LEFT JOIN assessments a USING(checkout_risk_assessment_result_id)
LEFT JOIN checkouts c ON a.checkout_count=1 AND a.checkout_id=c.checkout_id
LEFT JOIN users u ON c.user_count=1 AND c.user_id=u.user_id
GROUP BY account_id ORDER BY account_id

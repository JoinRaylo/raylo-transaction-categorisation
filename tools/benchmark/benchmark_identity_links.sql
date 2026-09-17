-- Existing relational identifiers only. No fuzzy or contact-field identity matching.
WITH assessments AS (
 SELECT checkout_risk_assessment_result_id AS assessment_id,
   COUNT(DISTINCT checkout_id) AS checkout_count, MIN(checkout_id) AS checkout_id
 FROM `raylo-production.dbt_production.intermediate_raylo_production__checkout_risk_assessment_results_latest`
 WHERE checkout_risk_assessment_result_id IN UNNEST(@assessment_ids) GROUP BY 1
), checkouts AS (
 SELECT checkout_id, COUNT(DISTINCT user_id) AS user_count, MIN(user_id) AS user_id,
   ARRAY_AGG(DISTINCT state IGNORE NULLS) AS states,
   LOGICAL_OR(is_business_checkout) AS is_business_checkout
 FROM `raylo-production.dbt_production.stg_raylo_production__checkouts` GROUP BY 1
), users AS (
 SELECT user_id, COUNT(DISTINCT customer_id) AS customer_count, MIN(customer_id) AS customer_id
 FROM `raylo-production.dbt_production.stg_raylo_production__users` GROUP BY 1
), orders AS (
 SELECT checkout_id, COUNT(*) AS order_rows, COUNT(DISTINCT customer_id) AS customer_count,
   MIN(customer_id) AS customer_id
 FROM `raylo-production.dbt_production.stg_raylo_production__orders` GROUP BY 1
), infos AS (
 SELECT checkout_id, COUNT(DISTINCT checkout_customer_info_id) AS info_count
 FROM `raylo-production.dbt_production.stg_raylo_production__checkout_customer_infos` GROUP BY 1
)
SELECT a.*, c.user_count, IF(c.user_count=1, c.user_id, NULL) AS user_id,
 c.states AS checkout_states, c.is_business_checkout, u.customer_count AS user_customer_count,
 IF(c.user_count=1 AND u.customer_count=1,u.customer_id,NULL) AS user_customer_id,
 o.order_rows, o.customer_count AS order_customer_count,
 IF(o.customer_count=1,o.customer_id,NULL) AS order_customer_id,
 i.info_count AS checkout_customer_info_count
FROM assessments a
LEFT JOIN checkouts c ON a.checkout_count=1 AND a.checkout_id=c.checkout_id
LEFT JOIN users u ON c.user_count=1 AND c.user_id=u.user_id
LEFT JOIN orders o ON a.checkout_count=1 AND a.checkout_id=o.checkout_id
LEFT JOIN infos i ON a.checkout_count=1 AND a.checkout_id=i.checkout_id
ORDER BY assessment_id

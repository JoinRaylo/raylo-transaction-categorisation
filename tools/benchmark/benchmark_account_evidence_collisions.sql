-- Bounded collision scan for the G3 admission design.
-- A provider transaction_id observed under more than one candidate account is
-- a direct account-scope violation; this emits only the colliding ids.
WITH candidate_accounts AS (
  SELECT account_id
  FROM UNNEST(@account_ids) AS account_id
), observations AS (
  SELECT account_id, transaction_id
  FROM `raylo-production.dbt_production.intermediate_credit_plaid_transactions`
  WHERE account_id IN (SELECT account_id FROM candidate_accounts)
  UNION ALL
  SELECT account_id, transaction_id
  FROM `raylo-production.dbt_production.credit_plaid_open_banking_transactions`
  WHERE account_id IN (SELECT account_id FROM candidate_accounts)
)
SELECT
  transaction_id,
  COUNT(*) AS observation_rows,
  ARRAY_AGG(DISTINCT account_id LIMIT 100) AS account_ids,
  COUNT(DISTINCT account_id) AS distinct_accounts
FROM observations
GROUP BY transaction_id
HAVING COUNT(DISTINCT account_id) > 1

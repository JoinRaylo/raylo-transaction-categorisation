-- Bounded pending-resolution evidence for the G3 admission design.
-- A pending observation that later materialized posted under the same
-- transaction_id is a same-key state transition, not an alias pair.  This
-- emits every pending candidate-account transaction with its resolution so
-- the resolver can certify or quarantine without inferring content matches.
WITH candidate_accounts AS (
  SELECT account_id
  FROM UNNEST(@account_ids) AS account_id
), pending_pairs AS (
  SELECT DISTINCT account_id, transaction_id
  FROM `raylo-production.dbt_production.credit_plaid_open_banking_transactions`
  WHERE account_id IN (SELECT account_id FROM candidate_accounts)
    AND is_pending IS TRUE
)
SELECT
  p.account_id,
  p.transaction_id,
  COUNTIF(h.is_pending IS FALSE) AS posted_history_rows,
  COUNT(c.account_id) AS current_materialized_rows
FROM pending_pairs p
LEFT JOIN `raylo-production.dbt_production.credit_plaid_open_banking_transactions` h
  ON h.account_id = p.account_id
  AND h.transaction_id = p.transaction_id
  AND h.is_pending IS FALSE
LEFT JOIN `raylo-production.dbt_production.intermediate_credit_plaid_transactions` c
  ON c.account_id = p.account_id
  AND c.transaction_id = p.transaction_id
GROUP BY p.account_id, p.transaction_id

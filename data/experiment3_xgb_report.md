# Experiment 3 — feature rebuild and XGBoost

Transactions were labelled with the T1–T7 waterfall (SQL T1–T6 / T7, then serving hinge **T5b** on leftover keys; always-ML on the leftover). Plaid leftover keys are unique `(merchant, description, direction)` (**1,805,727**); Equifax leftover keys are unique `(merchant, direction)` (**6,259** — closed vendor list). Features are rebuilt from the resulting leaves. GINI is **signed** (`2*AUC−1`). Locked v5/v6 were not scored.

Overlapping Equifax/Plaid proposal_ids keep the Plaid row. Calendar months where the outcome is filled as all-zero (immature) are dropped.

## Splits

- **month3_1plus_pia:** train `2023-01-01` to `< 2026-03-01` (n=48,940, 5,074 bads; Equifax 36,126 / Plaid 12,814). OOT `2026-03-01` to `< 2026-05-01` (n=4,855, 465 bads; Plaid 4,855 / Equifax 0).
- **month6_3plus_pia_from_subscription:** train `2023-01-01` to `< 2025-11-01` (n=39,961, 3,362 bads; Equifax 36,126 / Plaid 3,835). OOT `2025-11-01` to `< 2026-02-01` (n=6,652, 410 bads; Plaid 6,652 / Equifax 0).

Inner validation is the last 20% of each train window by `created_at` OOT GINI is from a model refit on the full train window. `taxonomy selected XGB, Plaid-train only` uses the same Plaid rows as the live comparator (no Equifax), so that gap is features+learner rather than extra history.

## month3 OOT GINI

| model | n | bads | signed_gini |
|---|---|---|---|
| month3 taxonomy selected XGB | 4855 | 465 | 0.4781 |
| month3 taxonomy selected XGB (inner valid) | 9788 | 866 | 0.5009 |
| month3 taxonomy baseline logistic | 4855 | 465 | 0.2946 |
| month3 taxonomy baseline XGB | 4855 | 465 | 0.3667 |
| month3 live Plaid logistic | 4855 | 465 | 0.3275 |
| month3 live Plaid XGB | 4855 | 465 | 0.403 |
| month3 taxonomy selected XGB, Plaid-train only | 4855 | 465 | 0.4669 |

Selected **102** features from 305 candidates (231 after IV/coverage/correlation).

### Top IV on inner train (kept)

| feature | iv | nonzero | why |
|---|---|---|---|
| essential_spend_amount_total | 0.1858 | 0.9881 | baseline |
| essential_spend_ratio | 0.1806 | 0.9881 | baseline |
| avg_credit_transaction_amount | 0.1758 | 0.9988 | baseline |
| gen_general_retail_marketplaces_months | 0.1679 | 0.9057 | iv |
| gen_general_retail_marketplaces_debit_n | 0.1671 | 0.8984 | iv |
| gen_general_retail_marketplaces_debit_amt | 0.1433 | 0.898 | iv |
| salary_credit_amt | 0.1376 | 0.5741 | iv |
| pct_unclassified | 0.1351 | 0.991 | iv |
| priority_debt_breadth | 0.1306 | 0.5917 | baseline |
| num_distinct_leaves | 0.1294 | 1.0 | baseline |
| gen_credit_loan_repayments_months | 0.1264 | 0.7503 | iv |
| loan_repayment_months | 0.1264 | 0.7503 | baseline |
| gen_credit_loan_repayments_debit_amt | 0.1258 | 0.7345 | iv |
| loan_payment_consistency_ratio | 0.1248 | 0.7362 | baseline |
| credit_product_months | 0.1211 | 0.7889 | baseline |
| streaming_months | 0.1211 | 0.6251 | baseline |
| gen_insurance_months | 0.1197 | 0.4192 | iv |
| salary_months | 0.1161 | 0.5742 | iv |
| pct_t1_t5 | 0.1148 | 0.9969 | iv |
| streaming_n | 0.1148 | 0.6251 | iv |

### Top XGB gain (selected)

| feature | gain |
|---|---|
| streaming_months | 0.030971 |
| gen_general_retail_marketplaces_months | 0.025267 |
| loan_payment_consistency_ratio | 0.019696 |
| avg_credit_transaction_amount | 0.016084 |
| essential_spend_amount_total | 0.013353 |
| gen_insurance_months | 0.013287 |
| gen_insurance_debit_n | 0.013153 |
| priority_debt_breadth | 0.012892 |
| essential_spend_ratio | 0.012873 |
| gen_general_retail_marketplaces_debit_n | 0.010904 |
| loan_repayment_months | 0.010359 |
| gen_credit_loan_repayments_months | 0.009857 |
| salary_months | 0.009157 |
| gen_home_garden_debit_amt | 0.008983 |
| pct_unclassified | 0.00872 |
| gen_digital_subscriptions_services_debit_amt | 0.008574 |
| priority_debt_months | 0.00842 |
| salary_credit_amt | 0.008239 |
| days_since_salary | 0.008009 |
| cash_withdrawal_debit_amt | 0.007899 |

## month6 OOT GINI

| model | n | bads | signed_gini |
|---|---|---|---|
| month6 taxonomy selected XGB | 6652 | 410 | 0.5601 |
| month6 taxonomy selected XGB (inner valid) | 7993 | 525 | 0.5175 |
| month6 taxonomy baseline logistic | 6652 | 410 | 0.4311 |
| month6 taxonomy baseline XGB | 6652 | 410 | 0.4557 |
| month6 live Plaid logistic | 6652 | 410 | 0.4045 |
| month6 live Plaid XGB | 6652 | 410 | 0.3861 |
| month6 taxonomy selected XGB, Plaid-train only | 6652 | 410 | 0.5316 |

Selected **96** features from 305 candidates (169 after IV/coverage/correlation).

### Top IV on inner train (kept)

| feature | iv | nonzero | why |
|---|---|---|---|
| streaming_debit_amt | 0.2291 | 0.6234 | iv |
| streaming_months | 0.2277 | 0.6281 | baseline |
| gen_general_retail_marketplaces_months | 0.2266 | 0.9075 | iv |
| essential_spend_amount_total | 0.2264 | 0.9879 | baseline |
| gen_general_retail_marketplaces_debit_n | 0.2238 | 0.9007 | iv |
| streaming_n | 0.2162 | 0.6281 | iv |
| num_distinct_leaves | 0.2098 | 1.0 | baseline |
| gen_digital_subscriptions_services_debit_amt | 0.2051 | 0.8228 | iv |
| essential_spend_ratio | 0.1996 | 0.9879 | baseline |
| gen_digital_subscriptions_services_months | 0.1992 | 0.8284 | iv |
| gen_general_retail_marketplaces_debit_amt | 0.1934 | 0.9002 | iv |
| salary_credit_amt | 0.1828 | 0.5866 | iv |
| num_distinct_merchants | 0.1827 | 0.9946 | baseline |
| salary_months | 0.172 | 0.5867 | iv |
| credit_product_months | 0.1682 | 0.7827 | baseline |
| loan_repayment_months | 0.157 | 0.7439 | baseline |
| gen_credit_loan_repayments_months | 0.157 | 0.7439 | iv |
| loan_payment_consistency_ratio | 0.1518 | 0.7302 | baseline |
| gen_digital_subscriptions_services_debit_n | 0.142 | 0.826 | iv |
| priority_debt_breadth | 0.1379 | 0.5887 | baseline |

### Top XGB gain (selected)

| feature | gain |
|---|---|
| streaming_months | 0.077409 |
| gen_digital_subscriptions_services_months | 0.036422 |
| salary_months | 0.024318 |
| gen_general_retail_marketplaces_months | 0.022994 |
| streaming_n | 0.020846 |
| credit_product_months | 0.01823 |
| gen_credit_loan_repayments_months | 0.015452 |
| priority_debt_months | 0.012379 |
| avg_credit_transaction_amount | 0.012104 |
| priority_debt_breadth | 0.010775 |
| loan_payment_consistency_ratio | 0.010315 |
| salary_credit_amt | 0.010057 |
| revolving_credit_repayment_months | 0.010046 |
| cash_withdrawal_n | 0.009257 |
| gen_insurance_months | 0.009199 |
| gen_general_retail_marketplaces_debit_amt | 0.00912 |
| essential_spend_ratio | 0.008949 |
| cash_withdrawal_debit_amt | 0.008737 |
| gen_general_retail_marketplaces_debit_n | 0.008532 |
| cash_deposit_credit_amt | 0.007955 |

## Screening rules (train window only)

- Drop constants and features with <0.5% non-zero unless they are in the live-analog baseline.
- Drop IV < 0.012 unless baseline.
- Of a |r| > 0.92 pair, drop the lower-IV optional feature (baseline is kept).
- Fit XGB on the screened set; keep non-zero gain features (cap 80) plus surviving baseline.

Candidate families beyond the live analogs: 29 general-category months/debit amount/count; key-leaf months/count/debit/credit (gambling subtypes stay separate); cash-withdrawal frequency; takeaway/groceries and gambling/salary ratios; mixed-basket and discretionary spend share; high-cost/distress flags; age-restricted debit share; income and spend monthly CV; 30d/90d spend ratio; days since salary / returned payment / gambling / payday; T1–T5 coverage and unclassified share; T5b residual count.

Models: `experiment3_xgb_month3.joblib`, `experiment3_xgb_month6.joblib`. Features parquet: `outputs/experiment3_xgb_proposal_features.parquet`.

Script: `src/experiment3_xgb_pipeline.py`.

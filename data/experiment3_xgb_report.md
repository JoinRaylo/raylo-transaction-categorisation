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

## 50-feature cap (follow-up)

Same splits and screening as above. Selected XGB is hard-capped at **50** features by inner-train gain (no extra baseline dump). `created` / application timestamp is excluded. GINI is signed. Baseline and live rows are unchanged comparators from this same fit.

Month3 selected **50** features; month6 **50**.

### month3 OOT

| model | n | bads | signed_gini |
|---|---|---|---|
| taxonomy selected XGB | 4855 | 465 | 0.4771 |
| live Plaid logistic | 4855 | 465 | 0.3275 |
| live Plaid XGB | 4855 | 465 | 0.403 |
| taxonomy selected XGB, Plaid-train only | 4855 | 465 | 0.4485 |

Top gain (month3, capped set):

| feature | gain |
|---|---|
| streaming_months | 0.028012 |
| gen_general_retail_marketplaces_months | 0.025169 |
| gen_general_retail_marketplaces_debit_n | 0.017671 |
| gen_insurance_debit_n | 0.016001 |
| avg_credit_transaction_amount | 0.015808 |
| essential_spend_ratio | 0.01435 |
| essential_spend_amount_total | 0.012849 |
| streaming_n | 0.01262 |
| loan_payment_consistency_ratio | 0.010743 |
| pct_unclassified | 0.010657 |
| priority_debt_breadth | 0.01034 |
| credit_product_months | 0.009311 |
| gen_insurance_months | 0.009305 |
| gen_digital_subscriptions_services_debit_amt | 0.009298 |
| priority_debt_months | 0.00925 |

### month6 OOT

| model | n | bads | signed_gini |
|---|---|---|---|
| taxonomy selected XGB | 6652 | 410 | 0.5638 |
| live Plaid logistic | 6652 | 410 | 0.4045 |
| live Plaid XGB | 6652 | 410 | 0.3861 |
| taxonomy selected XGB, Plaid-train only | 6652 | 410 | 0.4883 |

Top gain (month6, capped set):

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

Capped models: `experiment3_xgb_month3_50.joblib`, `experiment3_xgb_month6_50.joblib`.

## month12_3plus_pia_from_subscription (follow-up)

Same 50-feature selected XGB spec as the cap follow-up. Train `2023-01-01` to `< 2025-06-01` (n=32,845, 5,090 bads; Equifax 32,845 / Plaid 0). OOT `2025-06-01` to `< 2025-09-01` (n=3,780, 420 bads; Plaid 499 / Equifax 3,281). Sep 2025 onwards is filled as 0 in PIA (immature) and is dropped. Plaid live-feature comparators only exist if the train window has Plaid (it largely does not — Plaid go-live is Aug 2025, which sits in OOT).

| model | n | bads | signed_gini |
|---|---|---|---|
| month12 taxonomy selected XGB | 3780 | 420 | 0.4843 |
| month12 taxonomy selected XGB (inner valid) | 6569 | 1019 | 0.4782 |
| month12 taxonomy baseline logistic | 3780 | 420 | 0.3477 |
| month12 taxonomy baseline XGB | 3780 | 420 | 0.3993 |

Selected **50** features. Top gain:

| feature | gain |
|---|---|
| salary_months | 0.038185 |
| loan_repayment_months | 0.023603 |
| avg_credit_transaction_amount | 0.018868 |
| gen_general_retail_marketplaces_months | 0.016861 |
| gen_digital_subscriptions_services_months | 0.016627 |
| streaming_months | 0.016124 |
| loan_payment_consistency_ratio | 0.015244 |
| credit_product_months | 0.014101 |
| salary_credit_amt | 0.012985 |
| priority_debt_months | 0.012111 |
| gen_insurance_months | 0.011604 |
| priority_debt_breadth | 0.010833 |
| mortgage_n | 0.010397 |
| gambling_betting_debit_amt | 0.010086 |
| cash_withdrawal_debit_amt | 0.009647 |

Model: `experiment3_xgb_month12_50.joblib`.

## Live 20-feature shortlist: Plaid-native vs our leaves (follow-up)

The published **taxonomy baseline** was *not* this test: it used the analog shortlist **plus** priority-debt / gambling-subtype extras, and trained on Equifax+Plaid. This follow-up uses the **same 20 live-model columns**, Plaid-train only, month3 OOT March–April 2026 (and the month6 OOT for completeness). Name mapping: `num_distinct_detailed_categories` → `num_distinct_leaves`; `mortgage_auto_payment_debit_amount` → `mortgage_debit_amount`; `loan_payment_months` → `loan_repayment_months`. Strict p2p (not unclassified_transfer). GINI is signed.

### month3 OOT (Plaid-train only, n=4,855 / 465 bads; train n=12,814 / 1145 bads)

| model | n | bads | signed_gini |
|---|---|---|---|
| month3 live 20 logistic | 4855 | 465 | 0.3275 |
| month3 our-leaves 20 logistic | 4855 | 465 | 0.3153 |
| month3 live 20 XGB | 4855 | 465 | 0.3899 |
| month3 our-leaves 20 XGB | 4855 | 465 | 0.3791 |

### month6 OOT (Plaid-train only, n=6,652 / 410 bads; train n=3,835 / 243 bads)

| model | n | bads | signed_gini |
|---|---|---|---|
| month6 live 20 logistic | 6652 | 410 | 0.4045 |
| month6 our-leaves 20 logistic | 6652 | 410 | 0.4304 |
| month6 live 20 XGB | 6652 | 410 | 0.3825 |
| month6 our-leaves 20 XGB | 6652 | 410 | 0.4419 |

## Addendum 2026-09-02 — Equifax as-of filter and full-refit live comparator

Two methodology fixes from the 2 Sep programme review
(`docs/review-2026-09-02-state-and-next-steps.md` §2.4–2.5), then the
`fetch → classify → features → train → train50` stages were re-run. The script
rewrites this file; the 27 Aug body above was restored from a backup and this
addendum appended, per the dated-report convention.

1. **As-of filter on Equifax history.** `_eqx_fetch_sql` now keeps only rows with
   `DATE(PostDate) <= DATE(financial_proposal_created_at)` and within
   `EQX_HISTORY_DAYS = 189` days before it. Before, 5.5% of Equifax proposals
   carried post-proposal transactions (`days_since_*` down to −944) and those
   proposals had roughly half the bad rate. Equifax train proposals fell
   36,126 → **35,483** (proposals with no in-window history drop out).
2. **Live comparator refit on the full Plaid train window** with the
   early-stopped `n_estimators`, exactly as the taxonomy models are. The old
   80%-inner-fit number is kept as a labelled row for comparison.

Same OOT windows and n/bads as 27 Aug (month3 4,855 / 465; month6 6,652 / 410).
Single seed; the stress test's 3-seed live full-refit mean was 0.392 / 0.411,
so treat ±0.01–0.02 as noise on any one row.

### Uncapped (gain prune cap 80)

| model | month3 | month6 |
|---|---:|---:|
| taxonomy selected XGB (Equifax+Plaid train) | **0.4738** (was 0.4781) | **0.5720** (was 0.5601) |
| taxonomy selected XGB, Plaid-train only | 0.4633 (was 0.4669) | 0.5210 (was 0.5316) |
| taxonomy baseline XGB | 0.3659 | 0.4722 |
| live Plaid XGB, full refit (new method) | **0.3820** | **0.3854** |
| live Plaid XGB, 80% inner fit (old method) | 0.3973 (was 0.403) | 0.3861 |
| live Plaid logistic | 0.3275 | 0.4045 |

### 50-feature cap (headline spec)

| model | month3 | month6 |
|---|---:|---:|
| taxonomy selected XGB (Equifax+Plaid train) | **0.4772** (was 0.4771) | **0.5620** (was 0.5638) |
| taxonomy selected XGB, Plaid-train only | **0.4448** (was 0.4485) | **0.5044** (was 0.4883) |
| live Plaid XGB, full refit | 0.3820 | 0.3854 |

### Read

- The as-of leak did **not** carry the headline: capped month3 is unchanged
  (0.477) and month6 moves within noise (0.564 → 0.562). The post-proposal rows
  were a knowability problem, not the source of the uplift.
- The honest like-for-like pair is still **Plaid-train-only vs full-refit live**:
  month3 **0.445 vs 0.382**, month6 **0.504 vs 0.385**. Quote these, not the
  pooled Equifax+Plaid rows, when the claim is "same population as the live model".
- The same-20-feature ablation in the stress test remains the only
  taxonomy-only comparison, and it is inconclusive; the uplift above is the
  whole feature/model bundle.
- Cached artefacts overwritten: `outputs/experiment3_xgb_proposal_features.parquet`,
  `experiment3_xgb_month{3,6}.joblib`, `_50.joblib`, `experiment3_xgb_selected_features.json`.
  The granularity ladder, stress test and champion search still read the 27 Aug
  features and have **not** been re-run on the as-of features.

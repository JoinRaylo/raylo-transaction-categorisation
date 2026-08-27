# Experiment 3 — unified taxonomy vs live Open Banking features

Live comparator: logistic regression on `ds_plaid_credit_features` (the Plaid-native feature table behind the live Open Banking risk model). Same learner on both sides so this is a feature-space comparison, not taxonomy-logistic vs a production GBM.

**Headline split (2026-08-24):** one development sample of Equifax + Plaid with `financial_proposal_created_at` < 2026-03-01, then OOT = March and April 2026 (`< 2026-05-01`). Equifax dump ends 2025-08-31, so every Equifax row is in development. Overlapping proposal_ids (41) keep the Plaid row. May 2026 is matured but not in this OOT; Jun–Aug 2026 month3 is filled as 0 and is excluded.

Development: Equifax 36,575 (3,947 bads, 10.8%) + Plaid 12,814 (1,145 bads, 8.9%) → combined 49,389 (5,092 bads). Inner train/test cut 2025-10-15 (last 20% of development by date). OOT March 2,416 (202 bads) + April 2,439 (263 bads) = 4,855 / 465 bads (9.6%).

Leaf assignment is the provider waterfall (Equifax T1–T6 including T3; Plaid T1/T2/T4/T5/T6). Gambling subtypes stay separate. Locked v5 was not scored (and is now retired as confirmation gold).

**GINI in the tables below is unsigned** (`max(AUC, 1−AUC)` at the time of the run). Code now uses signed GINI; do not re-quote 0.328 vs 0.308 as signed until a re-score. See the caveat at the bottom of this report.

B rebuilds the live MIV shortlist on our leaves: `p2p_to_salary_ratio` (p2p_transfer debits / salary+salary_gig credits — not `unclassified_transfer`), `pct_p2p_like_debit_amount`, `loan_payment_monthly_cv`, `bnpl_30d_vs_90d_ratio` (relative to application date), `essential_spend_amount_total`, `avg_credit_transaction_amount`, `mortgage_debit_amount`, `returned_payment_count`, `has_recent_salary_flag`, `legit_life_footprint_months`, `spend_hhi_leaf`, `loan_payment_consistency_ratio`. B+ adds priority-debt and gambling-subtype flags. The classifier is still not in this waterfall.

## March–April 2026 OOT GINI (month3_1plus_pia)

Models A–D are fit on **all** development through February, then scored on March–April. That is the confirmation number.

| Model | Train n | Train bads | Mar–Apr OOT GINI |
|---|---:|---:|---:|
| A live Plaid-native, Plaid through Feb | 12,814 | 1,145 | **0.328** |
| B taxonomy live-analogs, Plaid through Feb | 12,814 | 1,145 | **0.284** |
| B+ taxonomy analogs+extras, Plaid through Feb | 12,814 | 1,145 | **0.308** |
| B loose p2p (analogs, unclassified_transfer in p2p) | 12,814 | 1,145 | **0.281** |
| B+ loose p2p (analogs+extras, unclassified_transfer in p2p) | 12,814 | 1,145 | **0.306** |
| C taxonomy analogs+extras, Equifax only | 36,575 | 3,947 | **0.271** |
| D taxonomy analogs+extras, Equifax+Plaid through Feb | 49,389 | 5,092 | **0.299** |

Inner test (fit on first 80% of through-Feb by date, score the last 20%):

| Model | Test n | Test GINI |
|---|---:|---:|
| B taxonomy live-analogs, Plaid through Feb | 9,878 | 0.336 |
| B+ taxonomy analogs+extras, Plaid through Feb | 9,878 | 0.344 |
| D taxonomy analogs+extras, Equifax+Plaid through Feb | 9,878 | 0.384 |

**Reading.** Live Plaid-native (A) **0.328**. Strict taxonomy analogs (B) **0.284**; B+ **0.308**. Loose p2p (unclassified_transfer counted as p2p-like): B **0.281**, B+ **0.306**. Equifax-only (C) **0.271**. Pooled (D) **0.299**.

Loose p2p **matches the live column** (corr 0.84, median 0.46 vs live 0.55) and lifts standalone IV 0.04 → 0.11, but it does **not** close the multivariate GINI gap — slightly worse than strict. Live `p2p_to_salary` is still stronger (IV 0.17 vs 0.11). Do not promote `unclassified_transfer` to p2p; the remaining 0.308 → 0.328 is not that one recode.

### p2p sensitivity (same Mar–Apr OOT)

| Version | `p2p_to_salary` median | corr vs live | `p2p_to_salary` IV | `pct_p2p` corr vs live |
|---|---:|---:|---:|---:|
| Live Plaid-native | 0.545 | 1.00 | 0.1703 | 1.00 |
| Strict (`p2p_transfer` only) | 0.017 | 0.01 | 0.0435 | 0.29 |
| Loose (+ `unclassified_transfer`) | 0.462 | 0.84 | 0.1090 | 0.83 |

Plaid transactions come from `intermediate_credit_plaid_transactions` (100% of labelled feature-table rows).

## Head-to-head IVs on Plaid through April 2026 (month3)

### Taxonomy features

| Feature | month3 IV |
|---|---:|
| `spend_hhi_leaf` | 0.2080 |
| `essential_spend_ratio` | 0.1976 |
| `spend_hhi` | 0.1874 |
| `num_distinct_leaves` | 0.1560 |
| `essential_spend_amount_total` | 0.1375 |
| `num_distinct_merchants` | 0.1271 |
| `priority_debt_breadth` | 0.1186 |
| `avg_credit_transaction_amount` | 0.1164 |
| `priority_debt_months` | 0.1123 |
| `p2p_to_salary_ratio_loose` | 0.1090 |
| `bnpl_30d_vs_90d_ratio` | 0.1011 |
| `loan_payment_consistency_ratio` | 0.0716 |
| `streaming_months` | 0.0654 |
| `pct_p2p_like_debit_amount_loose` | 0.0639 |
| `gambling_lottery_months` | 0.0542 |
| `loan_payment_monthly_cv` | 0.0539 |
| `p2p_to_salary_ratio` | 0.0435 |
| `telco_months` | 0.0413 |
| `mortgage_months` | 0.0411 |
| `bnpl_months` | 0.0364 |
| `grocer_months` | 0.0361 |
| `legit_life_footprint_months` | 0.0345 |
| `cash_advance_months` | 0.0291 |
| `loan_repayment_months` | 0.0279 |
| `pct_p2p_like_debit_amount` | 0.0259 |
| `credit_product_months` | 0.0238 |
| `has_recent_salary_flag` | 0.0225 |
| `gambling_any_months` | 0.0223 |
| `income_months` | 0.0164 |
| `rent_months` | 0.0125 |
| `gambling_casino_months` | 0.0120 |
| `gambling_unspecified_months` | 0.0115 |
| `mortgage_debit_amount` | 0.0113 |
| `gambling_betting_months` | 0.0041 |
| `payday_loan_months` | 0.0034 |
| `returned_payment_count` | 0.0018 |
| `total_months` | 0.0017 |
| `gambling_bingo_months` | 0.0005 |

### Live Plaid-native features (MIV-audit shortlist)

| Feature | month3 IV |
|---|---:|
| `live_spend_hhi` | 0.2774 |
| `live_p2p_to_salary_ratio` | 0.1703 |
| `live_num_distinct_detailed_categories` | 0.1585 |
| `live_pct_p2p_like_debit_amount` | 0.1276 |
| `live_essential_spend_amount_total` | 0.1261 |
| `live_num_distinct_merchants` | 0.1256 |
| `live_avg_credit_transaction_amount` | 0.1164 |
| `live_essential_spend_ratio` | 0.1138 |
| `live_loan_payment_monthly_cv` | 0.1106 |
| `live_bnpl_30d_vs_90d_ratio` | 0.0936 |
| `live_loan_payment_consistency_ratio` | 0.0592 |
| `live_loan_payment_months` | 0.0441 |
| `live_telco_months` | 0.0428 |
| `live_legit_life_footprint_months` | 0.0391 |
| `live_grocer_months` | 0.0378 |
| `live_streaming_months` | 0.0344 |
| `live_returned_payment_count` | 0.0206 |
| `live_has_recent_salary_flag` | 0.0164 |
| `live_mortgage_auto_payment_debit_amount` | 0.0103 |
| `live_total_months` | 0.0034 |

## What this does not claim

- Beating a production GBM. Both sides are a freshly fit logistic on the same OOT.
- That Equifax month12 outcomes can be used as the Plaid promotion metric.
- A 90-day-window fix. Plaid history is still capped; Equifax in the train set does not lengthen Plaid applicants' lookback.

## GINI caveat (2026-08-26)

The headline numbers above (live **0.328**, taxonomy B+ **0.308**) used **unsigned** GINI: the old helper took `max(AUC, 1−AUC)`, so an inverted score would look as good as a correctly oriented one. Ranking across A–D on this run is still likely to hold — same learner, same `y`, same score orientation — but **do not re-quote these as signed GINI** until Experiment 3 is re-scored. The code now uses `signed_gini` in `src/credit_metrics.py` (`2*AUC−1`, never `abs`). This report was not regenerated.

## Earlier splits (not the headline)

An 80/20-within-mature Plaid split (OOT from 2026-04-04, including May) gave live 0.264 / taxonomy Plaid-only 0.281 / Equifax-only 0.226 / pooled 0.275. Same models, different holdout. Xylo gen2 GINI 0.393 on an Equifax 2024–2025 OOT is a different product's score, not this comparison.


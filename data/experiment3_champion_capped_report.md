# Experiment 3 champion under a hard feature cap (2026-09-07)

Question: the development champion uses 1,654–3,150 input features. How much of its uplift over the published 50-feature model survives a cap? Recipe and blend weight are the champion's; only the column set changes. Features ranked by mean normalised gain on the **pre-OOT training window only** (both families, seeds 0/17/42); both components share the same top-K columns. Same OOT windows and rows as the champion report; paired bootstrap CIs on identical rows. Locked v5/v6 not scored.

## month3 (OOT n=4,855 / bads 465)

Components: xgb = `xgb_d5_regularised|leaf_rich`; lgb = `lgb_d4_recent|leaf_rich`; blend 0.9 XGB / 0.1 LGB.

| Model | Features | Rolling CV mean GINI | OOT GINI | Δ vs champion (95% CI) | Δ vs published 50 (95% CI) | Δ vs live (95% CI) |
|---|---:|---:|---:|---:|---:|---:|
| Live model, full refit | — | — | 0.394 | | | |
| Published 50-feature XGB (Aug) | 50 | — | 0.477 | | | |
| Capped champion | **50** | 0.540 | **0.508** | -0.025 (-0.044 to -0.007) | +0.031 (+0.005 to +0.057) | +0.114 (+0.071 to +0.157) |
| Capped champion | **100** | 0.549 | **0.520** | -0.013 (-0.024 to -0.000) | +0.043 (+0.019 to +0.068) | +0.126 (+0.083 to +0.169) |
| Capped champion | **200** | 0.554 | **0.529** | -0.004 (-0.013 to +0.005) | +0.052 (+0.025 to +0.077) | +0.134 (+0.092 to +0.176) |
| Champion, uncapped | 3150/3150 | — | 0.533 | | | |

Component OOT GINI per cap: cap 50: XGB 0.508 / LGB 0.500 (CV re-chosen XGB weight 0.7); cap 100: XGB 0.520 / LGB 0.514 (CV re-chosen XGB weight 0.5); cap 200: XGB 0.528 / LGB 0.531 (CV re-chosen XGB weight 0.9)

Top 50 features by pre-OOT gain:

1. `essential_spend_ratio` (0.0295)
2. `avg_credit_transaction_amount` (0.0212)
3. `gen_insurance_months` (0.0184)
4. `spend_30d_vs_90d_ratio` (0.0173)
5. `n_credits` (0.0143)
6. `net_to_debit_ratio` (0.0129)
7. `gen_general_retail_marketplaces_months` (0.0126)
8. `loan_payment_monthly_cv` (0.0121)
9. `gen_digital_subscriptions_services_debit_amt` (0.0091)
10. `gen_general_retail_marketplaces_debit_n` (0.0072)
11. `gen_home_garden_debit_amt` (0.0067)
12. `gen_council_tax_government_debit_amt` (0.0067)
13. `leaf__mobile_phone_contract__avg_debit` (0.0062)
14. `spend_monthly_cv` (0.0051)
15. `priority_debt_breadth` (0.0050)
16. `gen_health_medical_months` (0.0048)
17. `leaf__salary__month_share` (0.0048)
18. `leaf__transfer_own_account__credit_amt` (0.0048)
19. `leaf__transfer_own_account__credit_amt_share` (0.0046)
20. `spend_hhi_leaf` (0.0044)
21. `leaf__broadband_tv_phone__avg_debit` (0.0043)
22. `leaf__credit_card_repayment__debit_txn_share` (0.0042)
23. `credit_card_repayment_credit_amt` (0.0042)
24. `leaf__insurance_general__month_share` (0.0041)
25. `leaf__credit_card_repayment__txn_share` (0.0040)
26. `income_monthly_cv` (0.0040)
27. `gen_transfers_debit_amt` (0.0039)
28. `leaf__benefits_state__avg_credit` (0.0039)
29. `bnpl_30d_vs_90d_ratio` (0.0038)
30. `leaf__transfer_international__debit_amt` (0.0038)
31. `leaf__unclassified_other__txn_share` (0.0037)
32. `leaf__cash_withdrawal__debit_txn_share` (0.0037)
33. `avg_debit_transaction_amount` (0.0037)
34. `leaf__clothing_general__txn_share` (0.0037)
35. `leaf__mobile_phone_contract__debit_txn_share` (0.0036)
36. `gen_entertainment_leisure_months` (0.0036)
37. `leaf__streaming__month_share` (0.0035)
38. `leaf__payment_intermediary__txn_share` (0.0035)
39. `discretionary_spend_ratio` (0.0033)
40. `cash_withdrawal_debit_amt` (0.0032)
41. `gen_business_self_employment_months` (0.0032)
42. `leaf__water__month_share` (0.0031)
43. `leaf__mobile_handset__debit_txn_share` (0.0031)
44. `leaf__mobile_phone_contract__txn_share` (0.0030)
45. `leaf__loan_repayment_manual__credit_amt` (0.0029)
46. `leaf__marketplace_amazon__txn_share` (0.0028)
47. `leaf__returned_payment__txn_share` (0.0028)
48. `leaf__transfer_p2p__avg_debit` (0.0028)
49. `leaf__payment_intermediary__month_share` (0.0028)
50. `leaf__personal_loan_repayment__avg_credit` (0.0027)

## month6 (OOT n=6,652 / bads 410)

Components: xgb = `xgb_d5_regularised|leaf_raw`; lgb = `lgb_d5_weighted|leaf_rich`; blend 0.7 XGB / 0.3 LGB.

| Model | Features | Rolling CV mean GINI | OOT GINI | Δ vs champion (95% CI) | Δ vs published 50 (95% CI) | Δ vs live (95% CI) |
|---|---:|---:|---:|---:|---:|---:|
| Live model, full refit | — | — | 0.417 | | | |
| Published 50-feature XGB (Aug) | 50 | — | 0.564 | | | |
| Capped champion | **50** | 0.553 | **0.583** | -0.035 (-0.057 to -0.014) | +0.019 (-0.006 to +0.045) | +0.165 (+0.123 to +0.206) |
| Capped champion | **100** | 0.569 | **0.589** | -0.029 (-0.047 to -0.010) | +0.025 (-0.002 to +0.054) | +0.172 (+0.130 to +0.215) |
| Capped champion | **200** | 0.600 | **0.600** | -0.018 (-0.032 to -0.004) | +0.036 (+0.006 to +0.068) | +0.183 (+0.140 to +0.227) |
| Champion, uncapped | 1654/3150 | — | 0.618 | | | |

Component OOT GINI per cap: cap 50: XGB 0.588 / LGB 0.559 (CV re-chosen XGB weight 1.0); cap 100: XGB 0.590 / LGB 0.579 (CV re-chosen XGB weight 0.8); cap 200: XGB 0.601 / LGB 0.592 (CV re-chosen XGB weight 0.7)

Top 50 features by pre-OOT gain:

1. `avg_credit_transaction_amount` (0.0112)
2. `gen_digital_subscriptions_services_debit_amt` (0.0108)
3. `leaf__streaming__txn_share` (0.0107)
4. `spend_30d_vs_90d_ratio` (0.0106)
5. `leaf__streaming__month_share` (0.0102)
6. `gen_insurance_months` (0.0092)
7. `n_credits` (0.0088)
8. `net_to_debit_ratio` (0.0077)
9. `essential_spend_ratio` (0.0076)
10. `cash_withdrawal_debit_amt` (0.0060)
11. `streaming_debit_amt` (0.0053)
12. `gen_home_garden_debit_amt` (0.0049)
13. `leaf__cash_withdrawal__debit_amt_share` (0.0049)
14. `priority_debt_breadth` (0.0048)
15. `gen_general_retail_marketplaces_debit_n` (0.0047)
16. `loan_payment_monthly_cv` (0.0046)
17. `spend_monthly_cv` (0.0044)
18. `loan_payment_consistency_ratio` (0.0042)
19. `leaf__tv_licence__debit_amt` (0.0041)
20. `leaf__mobile_phone_contract__avg_debit` (0.0040)
21. `leaf__tv_licence__n` (0.0039)
22. `leaf__tv_licence__debit_n` (0.0038)
23. `gen_entertainment_leisure_debit_amt` (0.0038)
24. `bnpl_30d_vs_90d_ratio` (0.0038)
25. `leaf__salary__avg_credit` (0.0038)
26. `gen_entertainment_leisure_months` (0.0038)
27. `days_since_salary` (0.0038)
28. `gen_general_retail_marketplaces_months` (0.0037)
29. `income_monthly_cv` (0.0037)
30. `spend_hhi` (0.0036)
31. `leaf__salary__credit_amt_share` (0.0036)
32. `gen_council_tax_government_debit_amt` (0.0035)
33. `gen_insurance_debit_n` (0.0034)
34. `benefits_state_credit_amt` (0.0032)
35. `credit_card_repayment_credit_amt` (0.0031)
36. `leaf__payment_intermediary__debit_amt` (0.0031)
37. `discretionary_spend_ratio` (0.0030)
38. `leaf__transfer_international__debit_amt` (0.0030)
39. `gen_health_medical_debit_amt` (0.0030)
40. `leaf__streaming__debit_amt` (0.0029)
41. `income_to_spend_ratio` (0.0029)
42. `leaf__pub_bar__debit_amt` (0.0029)
43. `gen_savings_investments_debit_amt` (0.0029)
44. `leaf__water__months` (0.0028)
45. `leaf__benefits_state__avg_credit` (0.0028)
46. `mixed_basket_spend_ratio` (0.0028)
47. `leaf__salary__month_share` (0.0028)
48. `leaf__credit_card_repayment__credit_amt` (0.0027)
49. `leaf__transfer_own_account__credit_amt` (0.0027)
50. `gen_home_garden_months` (0.0027)

## Single XGBoost at the 50-feature cap (2026-09-07, later) — adopted as the reference

Carlos: for comparison against other models a single library is cleaner. The blend weight was chosen on the uncapped models; re-choosing it on the capped folds picks pure XGBoost for month6 (weight 1.0). Numbers below are the XGBoost component of the cap-50 run above (same 50 columns, same 3 seeds), scored on the same OOT rows; deltas are paired bootstraps on identical rows.

| Target | XGBoost alone | Blend 0.7/0.3 | LightGBM alone | Δ XGB vs blend (95% CI) | Δ XGB vs published 50 (95% CI) | Δ XGB vs live (95% CI) |
|---|---:|---:|---:|---:|---:|---:|
| month3 | **0.508** | 0.508 | 0.500 | +0.000 (-0.000 to +0.001) | +0.031 (+0.005 to +0.058) | +0.114 (+0.071 to +0.157) |
| month6 | **0.588** | 0.583 | 0.559 | +0.005 (-0.000 to +0.011) | +0.024 (-0.000 to +0.049) | +0.170 (+0.129 to +0.211) |

**Decision:** the single-XGBoost 50-feature model (`outputs/experiment3_champion_capped_xgb_{month3,month6}_50.joblib`) is the reference carried forward. Same learner family as the live model, one artefact, one library. The blend was tried, matched or trailed a single XGBoost within noise at every cap, and is dropped for simplicity; the uncapped blend (0.533 / 0.618) remains the ceiling reference.

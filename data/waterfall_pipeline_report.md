# Full-pipeline accuracy (T1–T5 → classifier → T6/T7)

One eval set: labelled transactions whose exact row is **not** in `outputs/tuning_train.jsonl`. Same merchants as training are allowed; locked v5/v6 are not included. Hinge SVM v5 on rows that miss T1–T5.

Classifier dump: `outputs/distill_models/tfidf_linearsvm_sgd.joblib`.
Eval rows written to `outputs/gold_pipeline_eval.csv` (1884 after dedupe).

Composition: `gold_transactions.csv` `role=iter_eval` (v2/v3/v4 rows on holdout merchants) plus risk-gold rows that are not training keys.

Source mix: unified_v2_batch2 578, risk 508, unified_v2 459, unified_v3 285, unified_v4 54

## Pipeline eval (row-disjoint from training) (n=1884)

| Slice | n | leaf | general |
|---|---:|---:|---:|
| T1–T5 (when that tier fired) | 1384 | 88.2% | 93.7% |
| classifier on residual (T6/T7-bound) | 500 | 59.2% | 66.2% |
| T6/T7 backup on residual | 500 | 27.0% | 41.2% |
| full pipeline: T1–T5 then hinge | 1884 | 80.5% | 86.4% |
| rules-only waterfall (T1–T7, no ML) | 1884 | 72.0% | 79.8% |

Waterfall tier mix (rules-only leaf, including T6/T7):

| tier | n | rules-only leaf acc |
|---|---:|---:|
| `T4_dictionary` | 1285 | 88.4% |
| `T6_native_fallback` | 500 | 27.0% |
| `T5_R31` | 16 | 100.0% |
| `T2_compound_returned_payment` | 14 | 100.0% |
| `T1_direction_gambling_credit` | 12 | 25.0% |
| `T2_compound_refund` | 10 | 90.0% |
| `T5_R02` | 9 | 66.7% |
| `T5_R01` | 6 | 83.3% |
| `T2_compound_instore_atm` | 5 | 100.0% |
| `T5_R10` | 3 | 100.0% |
| `T2_compound_amazon_uk_services_salary` | 2 | 100.0% |
| `T2_compound_cms_not_child_benefit` | 2 | 100.0% |
| `T2_compound_paypal_credit_payin3` | 2 | 100.0% |
| `T5_R11` | 2 | 100.0% |
| `T5_R13` | 2 | 100.0% |
| `T5_R29` | 2 | 100.0% |
| `T2_compound_amber_valley_ips` | 1 | 100.0% |
| `T2_compound_natwest_westend_recollection` | 1 | 100.0% |
| `T2_compound_now_paypal` | 1 | 100.0% |
| `T2_compound_richard_haven` | 1 | 100.0% |
| `T2_compound_roadchef_whsmith` | 1 | 100.0% |
| `T2_compound_tesco_cafe` | 1 | 100.0% |
| `T2_compound_wembley_park_express` | 1 | 100.0% |
| `T5_R14` | 1 | 100.0% |
| `T5_R20` | 1 | 100.0% |
| `T5_R24` | 1 | 100.0% |
| `T5_R25` | 1 | 100.0% |
| `T5_R30` | 1 | 100.0% |

## Hinge vs T6 on the residual, by category

Same 500 T6-bound rows as the headline “rest” slices. Accuracy is **recall**: of rows whose gold label is this category, what share did each head get right. `train jsonl` is how many times that label appears in `tuning_train.jsonl` (leaf or rolled-up parent). 17 leaves have T6 ahead of hinge (any n); 4 of those have n≥3. Full tables: `data/waterfall_residual_hinge_vs_t6_leaf.csv`, `data/waterfall_residual_hinge_vs_t6_general.csv`.

### Leaves where T6 beats hinge (n≥3) — train-top-up candidates

| `gold_leaf` | n | hinge | T6 | T6−hinge | train jsonl |
|---|---:|---:|---:|---:|---:|
| `salary` | 7 | 42.9% (3/7) | 100.0% (7/7) | +57.1% | 187 |
| `insurance_general` | 4 | 25.0% (1/4) | 50.0% (2/4) | +25.0% | 1,049 |
| `savings_transfer` | 5 | 60.0% (3/5) | 80.0% (4/5) | +20.0% | 790 |
| `accommodation` | 8 | 50.0% (4/8) | 62.5% (5/8) | +12.5% | 1,973 |

### Leaves where T6 beats hinge (n=1–2, noisy)

| `gold_leaf` | n | hinge | T6 | T6−hinge | train jsonl |
|---|---:|---:|---:|---:|---:|
| `salary_gig` | 2 | 0.0% (0/2) | 100.0% (2/2) | +100.0% | 49 |
| `childcare` | 1 | 0.0% (0/1) | 100.0% (1/1) | +100.0% | 451 |
| `experience_days` | 1 | 0.0% (0/1) | 100.0% (1/1) | +100.0% | 185 |
| `fancy_dress` | 1 | 0.0% (0/1) | 100.0% (1/1) | +100.0% | 40 |
| `insurance_other` | 1 | 0.0% (0/1) | 100.0% (1/1) | +100.0% | 471 |
| `investment_trading` | 1 | 0.0% (0/1) | 100.0% (1/1) | +100.0% | 118 |
| `memberships` | 1 | 0.0% (0/1) | 100.0% (1/1) | +100.0% | 318 |
| `office_equipment` | 1 | 0.0% (0/1) | 100.0% (1/1) | +100.0% | 8 |
| `unclassified_transfer` | 1 | 0.0% (0/1) | 100.0% (1/1) | +100.0% | 36 |
| `vehicle_maintenance` | 1 | 0.0% (0/1) | 100.0% (1/1) | +100.0% | 1,183 |
| `adult_entertainment` | 2 | 0.0% (0/2) | 50.0% (1/2) | +50.0% | 196 |
| `delivery_courier` | 2 | 0.0% (0/2) | 50.0% (1/2) | +50.0% | 407 |
| `veterinary` | 2 | 50.0% (1/2) | 100.0% (2/2) | +50.0% | 505 |

### Parents where T6 beats hinge (any n)

| `gold_general` | n | hinge | T6 | T6−hinge | train jsonl |
|---|---:|---:|---:|---:|---:|
| `income_employment` | 9 | 33.3% (3/9) | 100.0% (9/9) | +66.7% | 289 |
| `savings_investments` | 13 | 61.5% (8/13) | 84.6% (11/13) | +23.1% | 1,834 |
| `childcare_education` | 14 | 64.3% (9/14) | 85.7% (12/14) | +21.4% | 2,720 |
| `business_self_employment` | 5 | 20.0% (1/5) | 40.0% (2/5) | +20.0% | 2,812 |
| `clothing_personal_care` | 21 | 66.7% (14/21) | 71.4% (15/21) | +4.8% | 10,743 |

### All residual leaves with n≥5 (sorted T6−hinge)

| `gold_leaf` | n | hinge | T6 | T6−hinge | train jsonl |
|---|---:|---:|---:|---:|---:|
| `salary` | 7 | 42.9% (3/7) | 100.0% (7/7) | +57.1% | 187 |
| `savings_transfer` | 5 | 60.0% (3/5) | 80.0% (4/5) | +20.0% | 790 |
| `accommodation` | 8 | 50.0% (4/8) | 62.5% (5/8) | +12.5% | 1,973 |
| `refund_received` | 10 | 0.0% (0/10) | 0.0% (0/10) | +0.0% | 430 |
| `mortgage` | 6 | 100.0% (6/6) | 100.0% (6/6) | +0.0% | 229 |
| `restaurant_cafe` | 17 | 82.4% (14/17) | 70.6% (12/17) | -11.8% | 26,002 |
| `pet_supplies` | 8 | 62.5% (5/8) | 50.0% (4/8) | -12.5% | 1,092 |
| `transfer_own_account` | 13 | 15.4% (2/13) | 0.0% (0/13) | -15.4% | 728 |
| `discount_store` | 6 | 100.0% (6/6) | 83.3% (5/6) | -16.7% | 1,725 |
| `sports_participation` | 6 | 33.3% (2/6) | 16.7% (1/6) | -16.7% | 3,377 |
| `education_general` | 6 | 83.3% (5/6) | 66.7% (4/6) | -16.7% | 1,027 |
| `gym_fitness` | 5 | 60.0% (3/5) | 40.0% (2/5) | -20.0% | 2,414 |
| `taxi_rideshare` | 5 | 100.0% (5/5) | 80.0% (4/5) | -20.0% | 2,568 |
| `unclassified_other` | 12 | 25.0% (3/12) | 0.0% (0/12) | -25.0% | 15,003 |
| `convenience_store` | 8 | 75.0% (6/8) | 50.0% (4/8) | -25.0% | 30,299 |
| `council_tax` | 6 | 50.0% (3/6) | 16.7% (1/6) | -33.3% | 2,728 |
| `debt_collection` | 5 | 60.0% (3/5) | 20.0% (1/5) | -40.0% | 1,090 |
| `government_services` | 5 | 60.0% (3/5) | 20.0% (1/5) | -40.0% | 2,417 |
| `groceries` | 5 | 40.0% (2/5) | 0.0% (0/5) | -40.0% | 14,359 |
| `charitable_donation` | 7 | 71.4% (5/7) | 28.6% (2/7) | -42.9% | 1,868 |
| `car_parking` | 6 | 50.0% (3/6) | 0.0% (0/6) | -50.0% | 3,304 |
| `holiday_uk` | 6 | 83.3% (5/6) | 33.3% (2/6) | -50.0% | 1,358 |
| `pub_bar` | 10 | 80.0% (8/10) | 20.0% (2/10) | -60.0% | 18,125 |
| `transfer_p2p` | 47 | 63.8% (30/47) | 2.1% (1/47) | -61.7% | 103,373 |
| `beauty_treatment` | 10 | 70.0% (7/10) | 0.0% (0/10) | -70.0% | 4,440 |
| `fuel` | 6 | 83.3% (5/6) | 0.0% (0/6) | -83.3% | 11,495 |
| `pawnbroker` | 6 | 100.0% (6/6) | 16.7% (1/6) | -83.3% | 77 |
| `overdraft_arranged` | 20 | 100.0% (20/20) | 0.0% (0/20) | -100.0% | 21 |
| `cash_advance` | 10 | 100.0% (10/10) | 0.0% (0/10) | -100.0% | 200 |

## Why the earlier three-file readout was not valid

The first pipeline pass scored v3 and v4 as if they were held-out traffic. Those files were merged into `gold_transactions.csv` as `role=train` and copied into the 382k jsonl, so the classifier (and Tier A labels) had already seen most of those **rows**. Merchant overlap is fine; row overlap is not.

| File | n | rows also in `tuning_train.jsonl` |
|---|---:|---:|
| holdout `gold_v2_slm_eval_holdout.csv` | 1055 | 0 (0.0%) |
| v3 volume `gold_transactions_v3_volume.csv` | 1500 | 1213 (80.9%) |
| v4 unmatched-Plaid `gold_transactions_v4_slm_volume.csv` | 900 | 843 (93.7%) |
| risk gold `gold_transactions_risk_categories.csv` | 711 | 154 (21.7%) |
| unified `gold_transactions.csv` | 5335 | 3953 (74.1%) |

Holdout is clean (0%). Do not quote the leaked v3/v4 full-pipeline leaf numbers (88.7% / 92.3%) as confirmation of residual accuracy.


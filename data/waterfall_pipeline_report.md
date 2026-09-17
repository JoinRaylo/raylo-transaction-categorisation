# Full-pipeline accuracy (T1–T5 → classifier → T6/T7)

One eval set: labelled transactions whose exact row is **not** in `outputs/tuning_train.jsonl`. Same merchants as training are allowed; locked v5/v6 are not included. Hinge SVM v5 on rows that miss T1–T5.

Classifier dump: `outputs/distill_models/tfidf_linearsvm_sgd.joblib`.
Eval rows written to `outputs/gold_pipeline_eval.csv` (2000 after dedupe).

Composition: `gold_transactions.csv` `role=iter_eval` (v2/v3/v4 rows on holdout merchants) plus risk-gold rows that are not training keys.

Source mix: risk 624, unified_v2_batch2 578, unified_v2 459, unified_v3 285, unified_v4 54

## Pipeline eval (row-disjoint from training) (n=2000)

| Slice | n | leaf | general |
|---|---:|---:|---:|
| T1–T5 (when that tier fired) | 1520 | 89.3% | 94.3% |
| classifier on residual (T6/T7-bound) | 480 | 58.1% | 65.6% |
| T6/T7 backup on residual | 480 | 26.2% | 41.0% |
| full pipeline: T1–T5 then hinge | 2000 | 81.8% | 87.4% |
| rules-only waterfall (T1–T7, no ML) | 2000 | 74.2% | 81.5% |
| full pipeline — debit rows | 1824 | 84.2% | 89.5% |
| full pipeline — credit rows | 176 | 57.4% | 65.3% |
| classifier on residual — credit rows | 58 | 39.7% | 44.8% |
| full pipeline — human_adjudicated_v2 rows | 1037 | 77.8% | 83.2% |
| full pipeline — llm_drafted_agent_adjudicated rows | 963 | 86.2% | 91.9% |

Waterfall tier mix (rules-only leaf, including T6/T7):

| tier | n | rules-only leaf acc |
|---|---:|---:|
| `T4_dictionary` | 1378 | 89.5% |
| `T6_native_fallback` | 416 | 30.3% |
| `T7_unclassified` | 64 | 0.0% |
| `T5_R37` | 20 | 100.0% |
| `T5_R31` | 16 | 100.0% |
| `T2_compound_returned_payment` | 15 | 100.0% |
| `T3_mechanism_override` | 13 | 84.6% |
| `T5_R02` | 9 | 66.7% |
| `T1_direction_gambling_credit` | 8 | 0.0% |
| `T5_R32` | 8 | 100.0% |
| `T2_compound_refund` | 7 | 85.7% |
| `T5_R01` | 7 | 71.4% |
| `T2_compound_instore_atm` | 5 | 100.0% |
| `T1_direction` | 4 | 100.0% |
| `T2_compound` | 3 | 66.7% |
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
| `T5_R30` | 1 | 100.0% |
| `T5_R34` | 1 | 100.0% |

## T1–T4 vs provider-native (same rows)

The 72.0% rules-only number is **T1–T7** (Plaid/Equifax as T6 on the leftover). This table is the other question: on rows our waterfall already resolves at **T1–T4** (n=1446 of 2000), how does that leaf compare with mapping the provider's own category through T6 only. Native-filled only — risk gold has no `native_category` (528 Plaid T1–T4 rows omitted).

| Slice | n | our T1–T4 leaf | our general | provider-native leaf | native general |
|---|---:|---:|---:|---:|---:|
| T1–T4 (all providers, including risk gold with blank native) | 1446 | 89.1% | 94.3% | 32.0% | 42.9% |
| T1–T4, native filled (Plaid + Equifax) | 873 | 91.2% | 94.7% | 53.0% | 70.9% |
| T1–T4 Plaid, native filled | 484 | 91.9% | 96.1% | 31.8% | 59.1% |
| T1–T4 Equifax, native filled | 389 | 90.2% | 93.1% | 79.4% | 85.6% |
| T4 Plaid, native filled | 457 | 91.7% | 95.8% | 31.9% | 60.6% |
| T1–T5 Plaid, native filled | 509 | 91.6% | 95.5% | 31.4% | 58.2% |

## Provider-native only (no T1–T5, no classifier)

Same 1,884 rows. Leaf is the T6 crosswalk of the provider's own category field — no dictionary, no T2/T5, no hinge. Blank native (mostly risk gold) maps to `unclassified_other`. This is the “just use Plaid/Equifax” baseline against **80.5%** (T1–T5 then hinge) and **72.0%** (T1–T7 rules-only).

| Slice | n | leaf | general |
|---|---:|---:|---:|
| all 1,884 (blank native → unclassified_other) | 2000 | 29.9% | 41.6% |
| native filled only | 1318 | 45.4% | 63.0% |
| Plaid, native filled | 794 | 26.2% | 49.9% |
| Equifax, native filled | 524 | 74.6% | 82.8% |

## Hinge vs T6 on the residual, by category

Same 480 T6-bound rows as the headline “rest” slices. Accuracy is **recall**: of rows whose gold label is this category, what share did each head get right. `train jsonl` is how many times that label appears in `tuning_train.jsonl` (leaf or rolled-up parent). 15 leaves have T6 ahead of hinge (any n); 3 of those have n≥3. Full tables: `data/waterfall_residual_hinge_vs_t6_leaf.csv`, `data/waterfall_residual_hinge_vs_t6_general.csv`.

### Leaves where T6 beats hinge (n≥3) — train-top-up candidates

| `gold_leaf` | n | hinge | T6 | T6−hinge | train jsonl |
|---|---:|---:|---:|---:|---:|
| `insurance_general` | 4 | 25.0% (1/4) | 50.0% (2/4) | +25.0% | 1,066 |
| `savings_transfer` | 5 | 60.0% (3/5) | 80.0% (4/5) | +20.0% | 2,687 |
| `accommodation` | 8 | 50.0% (4/8) | 62.5% (5/8) | +12.5% | 1,978 |

### Leaves where T6 beats hinge (n=1–2, noisy)

| `gold_leaf` | n | hinge | T6 | T6−hinge | train jsonl |
|---|---:|---:|---:|---:|---:|
| `childcare` | 1 | 0.0% (0/1) | 100.0% (1/1) | +100.0% | 465 |
| `experience_days` | 1 | 0.0% (0/1) | 100.0% (1/1) | +100.0% | 185 |
| `fancy_dress` | 1 | 0.0% (0/1) | 100.0% (1/1) | +100.0% | 40 |
| `insurance_other` | 1 | 0.0% (0/1) | 100.0% (1/1) | +100.0% | 471 |
| `investment_trading` | 1 | 0.0% (0/1) | 100.0% (1/1) | +100.0% | 161 |
| `memberships` | 1 | 0.0% (0/1) | 100.0% (1/1) | +100.0% | 319 |
| `office_equipment` | 1 | 0.0% (0/1) | 100.0% (1/1) | +100.0% | 8 |
| `unclassified_transfer` | 1 | 0.0% (0/1) | 100.0% (1/1) | +100.0% | 36 |
| `vehicle_maintenance` | 1 | 0.0% (0/1) | 100.0% (1/1) | +100.0% | 1,177 |
| `adult_entertainment` | 2 | 0.0% (0/2) | 50.0% (1/2) | +50.0% | 200 |
| `delivery_courier` | 2 | 0.0% (0/2) | 50.0% (1/2) | +50.0% | 408 |
| `veterinary` | 2 | 50.0% (1/2) | 100.0% (2/2) | +50.0% | 505 |

### Parents where T6 beats hinge (any n)

| `gold_general` | n | hinge | T6 | T6−hinge | train jsonl |
|---|---:|---:|---:|---:|---:|
| `savings_investments` | 13 | 61.5% (8/13) | 84.6% (11/13) | +23.1% | 3,806 |
| `childcare_education` | 14 | 64.3% (9/14) | 85.7% (12/14) | +21.4% | 2,748 |
| `business_self_employment` | 5 | 20.0% (1/5) | 40.0% (2/5) | +20.0% | 2,829 |
| `clothing_personal_care` | 21 | 66.7% (14/21) | 71.4% (15/21) | +4.8% | 10,751 |

### All residual leaves with n≥5 (sorted T6−hinge)

| `gold_leaf` | n | hinge | T6 | T6−hinge | train jsonl |
|---|---:|---:|---:|---:|---:|
| `savings_transfer` | 5 | 60.0% (3/5) | 80.0% (4/5) | +20.0% | 2,687 |
| `accommodation` | 8 | 50.0% (4/8) | 62.5% (5/8) | +12.5% | 1,978 |
| `refund_received` | 10 | 0.0% (0/10) | 0.0% (0/10) | +0.0% | 1,636 |
| `mortgage` | 6 | 100.0% (6/6) | 100.0% (6/6) | +0.0% | 229 |
| `restaurant_cafe` | 17 | 82.4% (14/17) | 70.6% (12/17) | -11.8% | 26,003 |
| `pet_supplies` | 8 | 62.5% (5/8) | 50.0% (4/8) | -12.5% | 1,091 |
| `discount_store` | 6 | 100.0% (6/6) | 83.3% (5/6) | -16.7% | 1,726 |
| `transfer_own_account` | 12 | 16.7% (2/12) | 0.0% (0/12) | -16.7% | 1,062 |
| `sports_participation` | 6 | 33.3% (2/6) | 16.7% (1/6) | -16.7% | 3,380 |
| `education_general` | 6 | 83.3% (5/6) | 66.7% (4/6) | -16.7% | 1,030 |
| `taxi_rideshare` | 6 | 83.3% (5/6) | 66.7% (4/6) | -16.7% | 2,583 |
| `gym_fitness` | 5 | 60.0% (3/5) | 40.0% (2/5) | -20.0% | 2,422 |
| `unclassified_other` | 12 | 25.0% (3/12) | 0.0% (0/12) | -25.0% | 15,328 |
| `convenience_store` | 8 | 75.0% (6/8) | 50.0% (4/8) | -25.0% | 30,279 |
| `council_tax` | 6 | 50.0% (3/6) | 16.7% (1/6) | -33.3% | 2,736 |
| `debt_collection` | 5 | 60.0% (3/5) | 20.0% (1/5) | -40.0% | 1,045 |
| `government_services` | 5 | 60.0% (3/5) | 20.0% (1/5) | -40.0% | 2,447 |
| `groceries` | 5 | 40.0% (2/5) | 0.0% (0/5) | -40.0% | 14,361 |
| `charitable_donation` | 7 | 71.4% (5/7) | 28.6% (2/7) | -42.9% | 1,872 |
| `car_parking` | 6 | 50.0% (3/6) | 0.0% (0/6) | -50.0% | 3,305 |
| `holiday_uk` | 6 | 83.3% (5/6) | 33.3% (2/6) | -50.0% | 1,365 |
| `pub_bar` | 10 | 80.0% (8/10) | 20.0% (2/10) | -60.0% | 18,129 |
| `transfer_p2p` | 48 | 62.5% (30/48) | 2.1% (1/48) | -60.4% | 117,814 |
| `beauty_treatment` | 10 | 70.0% (7/10) | 0.0% (0/10) | -70.0% | 4,452 |
| `credit_reporting_service` | 5 | 100.0% (5/5) | 20.0% (1/5) | -80.0% | 103 |
| `fuel` | 6 | 83.3% (5/6) | 0.0% (0/6) | -83.3% | 11,497 |
| `pawnbroker` | 6 | 100.0% (6/6) | 16.7% (1/6) | -83.3% | 43 |
| `cash_advance` | 8 | 100.0% (8/8) | 0.0% (0/8) | -100.0% | 200 |

## Why the earlier three-file readout was not valid

The first pipeline pass scored v3 and v4 as if they were held-out traffic. Those files were merged into `gold_transactions.csv` as `role=train` and copied into the 382k jsonl, so the classifier (and Tier A labels) had already seen most of those **rows**. Merchant overlap is fine; row overlap is not.

| File | n | rows also in `tuning_train.jsonl` |
|---|---:|---:|
| holdout `gold_v2_slm_eval_holdout.csv` | 1055 | 0 (0.0%) |
| v3 volume `gold_transactions_v3_volume.csv` | 1500 | 1036 (69.1%) |
| v4 unmatched-Plaid `gold_transactions_v4_slm_volume.csv` | 900 | 809 (89.9%) |
| risk gold `gold_transactions_risk_categories.csv` | 711 | 6 (0.8%) |
| unified `gold_transactions.csv` | 5335 | 3669 (68.8%) |

Holdout is clean (0%). Do not quote the leaked v3/v4 full-pipeline leaf numbers (88.7% / 92.3%) as confirmation of residual accuracy.


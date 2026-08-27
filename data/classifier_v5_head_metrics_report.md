# Classifier v5 head comparison — logreg vs hinge (2026-08-26)

Same tranche-4 TF-IDF dumps as `data/classifier_v5_retrain_report.md`. Classifier-only (gambling catch-all promote on). Locked v5/v6 not scored. Holdout MD5 `c075717405a183191a43d0eb33f8dca3` (matches the protected v5-retrain hash).
Micro-F1 equals accuracy for single-label classification. Macro-F1 averages per-class F1 over labels that appear in gold (unweighted), so rare leaves count the same as common ones. Weighted-F1 is the support-weighted mean. Balanced accuracy is mean recall. Per-class accuracy below is recall.

## Overall

### Holdout leaf (n=1055, merchant-disjoint)

| Metric | Logreg | Hinge | Δ (hinge − logreg) |
|---|---|---|---|
| Accuracy / micro-F1 | 50.9% | 52.8% | +1.9% |
| Balanced accuracy | 43.5% | 47.2% | +3.7% |
| Weighted F1 | 49.0% | 51.5% | +2.4% |
| Macro F1 (200 gold labels) | 43.4% | 45.3% | +1.9% |

### Holdout general (leaf rolled up)

| Metric | Logreg | Hinge | Δ (hinge − logreg) |
|---|---|---|---|
| Accuracy / micro-F1 | 59.0% | 60.3% | +1.3% |
| Balanced accuracy | 54.7% | 53.9% | -0.8% |
| Weighted F1 | 59.0% | 59.8% | +0.8% |
| Macro F1 (28 gold labels) | 56.1% | 55.2% | -0.9% |

### Risk gold leaf (n=711)

| Metric | Logreg | Hinge | Δ (hinge − logreg) |
|---|---|---|---|
| Accuracy / micro-F1 | 76.8% | 80.6% | +3.8% |
| Balanced accuracy | 58.8% | 61.7% | +2.9% |
| Weighted F1 | 79.4% | 81.7% | +2.3% |
| Macro F1 (50 gold labels) | 58.1% | 60.6% | +2.5% |

### Risk gold general (leaf rolled up)

| Metric | Logreg | Hinge | Δ (hinge − logreg) |
|---|---|---|---|
| Accuracy / micro-F1 | 82.1% | 85.5% | +3.4% |
| Balanced accuracy | 43.4% | 40.4% | -3.0% |
| Weighted F1 | 85.2% | 86.7% | +1.5% |
| Macro F1 (17 gold labels) | 42.2% | 40.3% | -1.9% |

### Risk-category bar (gambling / credit_loan / high-cost leaves)

| Metric | Logreg | Hinge | Δ |
|---|---|---|---|
| Accuracy (n=619) | 81.4% | 86.1% | +4.7% |
| Macro F1 | 83.4% | 86.9% | +3.5% |

Hinge risk-bar **86.1% OK** (threshold 70%). Logreg 81.4% OK.

## Per parent category

Hinge vs logreg on general-level F1: holdout **17 better / 11 worse / 0 tie**; risk gold **7 better / 4 worse / 6 tie**.

### Holdout

| General | n | Logreg acc | Hinge acc | Δ acc | Logreg F1 | Hinge F1 | Δ F1 |
|---|---|---|---|---|---|---|---|
| `groceries_household_essentials` | 87 | 83.9% | 82.8% | -1.1% | 72.6% | 76.6% | +4.0% |
| `entertainment_leisure` | 83 | 62.7% | 72.3% | +9.6% | 62.7% | 59.7% | -2.9% |
| `eating_drinking_out` | 81 | 80.2% | 74.1% | -6.2% | 61.6% | 60.6% | -1.0% |
| `general_retail_marketplaces` | 64 | 31.2% | 42.2% | +10.9% | 44.0% | 51.4% | +7.5% |
| `transport_motoring` | 60 | 73.3% | 78.3% | +5.0% | 71.0% | 75.2% | +4.2% |
| `transfers` | 55 | 63.6% | 56.4% | -7.3% | 47.6% | 51.2% | +3.6% |
| `clothing_personal_care` | 50 | 46.0% | 50.0% | +4.0% | 56.8% | 49.5% | -7.3% |
| `credit_loan_repayments` | 43 | 41.9% | 41.9% | +0.0% | 52.9% | 54.5% | +1.6% |
| `travel_holidays` | 42 | 59.5% | 57.1% | -2.4% | 64.9% | 64.0% | -0.9% |
| `pets` | 39 | 69.2% | 79.5% | +10.3% | 79.4% | 87.3% | +7.9% |
| `health_medical` | 38 | 71.1% | 78.9% | +7.9% | 74.0% | 80.0% | +6.0% |
| `utilities_household_bills` | 36 | 66.7% | 75.0% | +8.3% | 67.6% | 76.1% | +8.5% |
| `gambling` | 35 | 71.4% | 77.1% | +5.7% | 69.4% | 60.7% | -8.8% |
| `insurance` | 33 | 81.8% | 81.8% | +0.0% | 83.1% | 87.1% | +4.0% |
| `savings_investments` | 33 | 30.3% | 27.3% | -3.0% | 41.7% | 37.5% | -4.2% |
| `digital_subscriptions_services` | 32 | 50.0% | 68.8% | +18.8% | 48.5% | 66.7% | +18.2% |
| `home_garden` | 32 | 34.4% | 37.5% | +3.1% | 44.9% | 49.0% | +4.1% |
| `high_cost_distress_credit` | 27 | 70.4% | 74.1% | +3.7% | 74.5% | 75.5% | +1.0% |
| `income_other` | 25 | 28.0% | 24.0% | -4.0% | 28.6% | 25.5% | -3.0% |
| `childcare_education` | 21 | 61.9% | 57.1% | -4.8% | 74.3% | 68.6% | -5.7% |
| `charitable_political_giving` | 20 | 50.0% | 55.0% | +5.0% | 60.6% | 62.9% | +2.3% |
| `housing` | 20 | 60.0% | 60.0% | +0.0% | 61.5% | 64.9% | +3.3% |
| `income_benefits_state_support` | 19 | 0.0% | 10.5% | +10.5% | 0.0% | 19.0% | +19.0% |
| `unclassified` | 19 | 31.6% | 31.6% | +0.0% | 15.2% | 17.9% | +2.7% |
| `income_employment` | 18 | 61.1% | 27.8% | -33.3% | 50.0% | 31.2% | -18.8% |
| `council_tax_government` | 16 | 62.5% | 62.5% | +0.0% | 60.6% | 62.5% | +1.9% |
| `fees_charges` | 15 | 46.7% | 0.0% | -46.7% | 60.9% | 0.0% | -60.9% |
| `business_self_employment` | 12 | 41.7% | 25.0% | -16.7% | 41.7% | 30.0% | -11.7% |

### Risk gold

| General | n | Logreg acc | Hinge acc | Δ acc | Logreg F1 | Hinge F1 | Δ F1 |
|---|---|---|---|---|---|---|---|
| `credit_loan_repayments` | 245 | 91.0% | 93.9% | +2.9% | 89.6% | 90.6% | +1.0% |
| `gambling` | 230 | 82.6% | 87.4% | +4.8% | 90.3% | 92.6% | +2.4% |
| `high_cost_distress_credit` | 144 | 86.1% | 92.4% | +6.2% | 92.2% | 95.3% | +3.1% |
| `transfers` | 27 | 44.4% | 40.7% | -3.7% | 35.3% | 38.6% | +3.3% |
| `fees_charges` | 24 | 95.8% | 91.7% | -4.2% | 97.9% | 91.7% | -6.2% |
| `income_other` | 14 | 21.4% | 14.3% | -7.1% | 28.6% | 18.2% | -10.4% |
| `general_retail_marketplaces` | 6 | 0.0% | 0.0% | +0.0% | 0.0% | 0.0% | +0.0% |
| `groceries_household_essentials` | 6 | 66.7% | 66.7% | +0.0% | 66.7% | 72.7% | +6.1% |
| `transport_motoring` | 4 | 50.0% | 50.0% | +0.0% | 50.0% | 57.1% | +7.1% |
| `entertainment_leisure` | 2 | 50.0% | 50.0% | +0.0% | 50.0% | 28.6% | -21.4% |
| `savings_investments` | 2 | 50.0% | 100.0% | +50.0% | 66.7% | 100.0% | +33.3% |
| `unclassified` | 2 | 0.0% | 0.0% | +0.0% | 0.0% | 0.0% | +0.0% |
| `clothing_personal_care` | 1 | 0.0% | 0.0% | +0.0% | 0.0% | 0.0% | +0.0% |
| `digital_subscriptions_services` | 1 | 100.0% | 0.0% | -100.0% | 50.0% | 0.0% | -50.0% |
| `eating_drinking_out` | 1 | 0.0% | 0.0% | +0.0% | 0.0% | 0.0% | +0.0% |
| `home_garden` | 1 | 0.0% | 0.0% | +0.0% | 0.0% | 0.0% | +0.0% |
| `pets` | 1 | 0.0% | 0.0% | +0.0% | 0.0% | 0.0% | +0.0% |

## Per leaf — risk families (risk gold)

| Leaf | Parent | n | Logreg acc | Hinge acc | Δ acc | Logreg F1 | Hinge F1 | Δ F1 |
|---|---|---|---|---|---|---|---|---|
| `personal_loan_repayment` | `credit_loan_repayments` | 24 | 79.2% | 75.0% | -4.2% | 79.2% | 83.7% | +4.6% |
| `revolving_credit_repayment` | `credit_loan_repayments` | 23 | 56.5% | 73.9% | +17.4% | 68.4% | 69.4% | +1.0% |
| `credit_union_repayment` | `credit_loan_repayments` | 21 | 90.5% | 90.5% | +0.0% | 92.7% | 90.5% | -2.2% |
| `car_lease` | `credit_loan_repayments` | 20 | 95.0% | 100.0% | +5.0% | 97.4% | 100.0% | +2.6% |
| `credit_card_repayment` | `credit_loan_repayments` | 20 | 95.0% | 95.0% | +0.0% | 95.0% | 92.7% | -2.3% |
| `hire_purchase_repayment` | `credit_loan_repayments` | 20 | 100.0% | 100.0% | +0.0% | 100.0% | 100.0% | +0.0% |
| `student_loan_repayment` | `credit_loan_repayments` | 20 | 100.0% | 100.0% | +0.0% | 100.0% | 100.0% | +0.0% |
| `loan_repayment_manual` | `credit_loan_repayments` | 19 | 89.5% | 100.0% | +10.5% | 82.9% | 92.7% | +9.8% |
| `retail_finance_repayment` | `credit_loan_repayments` | 19 | 100.0% | 94.7% | -5.3% | 100.0% | 97.3% | -2.7% |
| `bnpl` | `credit_loan_repayments` | 18 | 88.9% | 94.4% | +5.6% | 82.1% | 85.0% | +2.9% |
| `car_finance_repayment` | `credit_loan_repayments` | 18 | 77.8% | 83.3% | +5.6% | 84.8% | 88.2% | +3.4% |
| `financial_services_other` | `credit_loan_repayments` | 8 | 62.5% | 62.5% | +0.0% | 58.8% | 58.8% | +0.0% |
| `loan_repayment_other` | `credit_loan_repayments` | 7 | 100.0% | 100.0% | +0.0% | 100.0% | 100.0% | +0.0% |
| `charge_card_repayment` | `credit_loan_repayments` | 6 | 100.0% | 100.0% | +0.0% | 52.2% | 52.2% | +0.0% |
| `balance_transfer` | `credit_loan_repayments` | 2 | 100.0% | 100.0% | +0.0% | 57.1% | 57.1% | +0.0% |
| `gambling_betting` | `gambling` | 93 | 83.9% | 84.9% | +1.1% | 90.2% | 91.3% | +1.2% |
| `gambling_casino` | `gambling` | 32 | 87.5% | 93.8% | +6.2% | 93.3% | 92.3% | -1.0% |
| `gambling_bingo` | `gambling` | 31 | 35.5% | 48.4% | +12.9% | 48.9% | 63.8% | +14.9% |
| `gambling_lottery` | `gambling` | 28 | 100.0% | 100.0% | +0.0% | 98.2% | 96.6% | -1.7% |
| `gambling_unspecified` | `gambling` | 25 | 60.0% | 80.0% | +20.0% | 66.7% | 81.6% | +15.0% |
| `prize_competitions` | `gambling` | 21 | 90.5% | 95.2% | +4.8% | 92.7% | 95.2% | +2.6% |
| `debt_collection` | `high_cost_distress_credit` | 33 | 57.6% | 57.6% | +0.0% | 71.7% | 70.4% | -1.3% |
| `debt_management_plan` | `high_cost_distress_credit` | 25 | 64.0% | 92.0% | +28.0% | 58.2% | 74.2% | +16.0% |
| `credit_reporting_service` | `high_cost_distress_credit` | 21 | 95.2% | 95.2% | +0.0% | 97.6% | 97.6% | +0.0% |
| `cash_advance` | `high_cost_distress_credit` | 20 | 100.0% | 100.0% | +0.0% | 100.0% | 100.0% | +0.0% |
| `pawnbroker` | `high_cost_distress_credit` | 20 | 95.0% | 95.0% | +0.0% | 97.4% | 97.4% | +0.0% |
| `debt_enforcement` | `high_cost_distress_credit` | 17 | 82.4% | 82.4% | +0.0% | 90.3% | 90.3% | +0.0% |
| `payday_loan` | `high_cost_distress_credit` | 7 | 28.6% | 57.1% | +28.6% | 44.4% | 72.7% | +28.3% |
| `money_management_service` | `high_cost_distress_credit` | 1 | 0.0% | 0.0% | +0.0% | 0.0% | 0.0% | +0.0% |

## Per leaf — holdout, support ≥ 8

Holdout is merchant-disjoint and most leaves have few rows; F1 on n=1–3 is not interpretable. Full per-leaf tables: `data/classifier_v5_head_metrics_{holdout,risk}_leaf.csv`.

| Leaf | n | Logreg acc | Hinge acc | Δ acc | Logreg F1 | Hinge F1 | Δ F1 |
|---|---|---|---|---|---|---|---|
| `transfer_p2p` | 43 | 69.8% | 62.8% | -7.0% | 46.5% | 50.9% | +4.4% |
| `restaurant_cafe` | 33 | 69.7% | 66.7% | -3.0% | 49.5% | 53.0% | +3.5% |
| `groceries` | 23 | 69.6% | 69.6% | +0.0% | 58.2% | 66.7% | +8.5% |
| `convenience_store` | 21 | 90.5% | 85.7% | -4.8% | 63.3% | 70.6% | +7.3% |
| `pet_supplies` | 20 | 60.0% | 70.0% | +10.0% | 68.6% | 75.7% | +7.1% |
| `benefits_state` | 19 | 0.0% | 10.5% | +10.5% | 0.0% | 19.0% | +19.0% |
| `pub_bar` | 19 | 78.9% | 78.9% | +0.0% | 49.2% | 46.9% | -2.3% |
| `refund_received` | 19 | 36.8% | 15.8% | -21.1% | 41.2% | 26.1% | -15.1% |
| `takeaway` | 17 | 76.5% | 82.4% | +5.9% | 70.3% | 82.4% | +12.1% |
| `marketplace_amazon` | 15 | 13.3% | 13.3% | +0.0% | 22.2% | 23.5% | +1.3% |
| `debt_collection` | 14 | 64.3% | 64.3% | +0.0% | 66.7% | 66.7% | +0.0% |
| `returned_payment` | 14 | 50.0% | 0.0% | -50.0% | 63.6% | 0.0% | -63.6% |
| `books` | 13 | 76.9% | 76.9% | +0.0% | 87.0% | 83.3% | -3.6% |
| `confectionary` | 13 | 84.6% | 84.6% | +0.0% | 88.0% | 88.0% | +0.0% |
| `salary` | 13 | 69.2% | 30.8% | -38.5% | 46.2% | 36.4% | -9.8% |
| `savings_transfer` | 13 | 30.8% | 30.8% | +0.0% | 40.0% | 40.0% | +0.0% |
| `software` | 13 | 30.8% | 61.5% | +30.8% | 33.3% | 55.2% | +21.8% |
| `unclassified_other` | 13 | 30.8% | 23.1% | -7.7% | 12.1% | 10.5% | -1.6% |
| `accommodation` | 12 | 33.3% | 33.3% | +0.0% | 47.1% | 47.1% | +0.0% |
| `credit_card_repayment` | 12 | 50.0% | 50.0% | +0.0% | 60.0% | 57.1% | -2.9% |
| `gambling_betting` | 12 | 91.7% | 83.3% | -8.3% | 95.7% | 90.9% | -4.7% |
| `gym_fitness` | 12 | 66.7% | 66.7% | +0.0% | 72.7% | 80.0% | +7.3% |
| `pharmacy` | 12 | 66.7% | 91.7% | +25.0% | 66.7% | 81.5% | +14.8% |
| `public_transport_rail_coach` | 12 | 83.3% | 83.3% | +0.0% | 64.5% | 69.0% | +4.4% |
| `streaming` | 12 | 83.3% | 91.7% | +8.3% | 90.9% | 95.7% | +4.7% |
| `veterinary` | 12 | 83.3% | 83.3% | +0.0% | 90.9% | 90.9% | +0.0% |
| `water` | 12 | 33.3% | 41.7% | +8.3% | 47.1% | 55.6% | +8.5% |
| `beauty_treatment` | 11 | 63.6% | 72.7% | +9.1% | 66.7% | 80.0% | +13.3% |
| `charity_shop` | 11 | 18.2% | 36.4% | +18.2% | 30.8% | 53.3% | +22.6% |
| `mortgage` | 11 | 54.5% | 63.6% | +9.1% | 70.6% | 77.8% | +7.2% |
| `fuel` | 10 | 60.0% | 80.0% | +20.0% | 57.1% | 72.7% | +15.6% |
| `insurance_general` | 10 | 50.0% | 40.0% | -10.0% | 58.8% | 53.3% | -5.5% |
| `car_parking` | 9 | 66.7% | 55.6% | -11.1% | 70.6% | 62.5% | -8.1% |
| `clothing_general` | 9 | 66.7% | 66.7% | +0.0% | 63.2% | 50.0% | -13.2% |
| `discount_store` | 9 | 55.6% | 77.8% | +22.2% | 52.6% | 58.3% | +5.7% |
| `council_tax` | 8 | 50.0% | 50.0% | +0.0% | 42.1% | 50.0% | +7.9% |
| `insurance_life` | 8 | 75.0% | 75.0% | +0.0% | 85.7% | 85.7% | +0.0% |
| `magazines` | 8 | 0.0% | 75.0% | +75.0% | 0.0% | 63.2% | +63.2% |
| `pension_contribution` | 8 | 12.5% | 0.0% | -12.5% | 18.2% | 0.0% | -18.2% |
| `rent` | 8 | 62.5% | 50.0% | -12.5% | 50.0% | 47.1% | -2.9% |
| `sports_participation` | 8 | 37.5% | 37.5% | +0.0% | 30.0% | 30.0% | +0.0% |

## Where hinge is worse

Parent-level **macro** F1 and balanced accuracy slightly favour logreg (holdout general macro F1 56.1% vs 55.2%; risk gold 42.2% vs 40.3%). That is a few thin parents going to zero, not a broad parent-level loss. On holdout: `fees_charges` 46.7%→0% recall (F1 60.9%→0%, n=15), `income_employment` 61.1%→27.8% (`salary` 69.2%→30.8%, n=13), `returned_payment` 50%→0% (n=14). Hinge also over-recalls `gambling` as a parent (holdout gambling F1 −8.8pp) while still winning gambling **leaf** F1 on the risk set.

## Verdict

At **leaf** level hinge wins every aggregate on both sets (accuracy, balanced accuracy, weighted F1, macro F1) and the risk bar (**86.1% vs 81.4%**, macro F1 **86.9% vs 83.4%**). Holdout leaf F1: hinge better on 59 leaves, worse on 38, tie 103. Risk gold: better 16 / worse 9 / tie 25. Largest risk-leaf F1 lifts: `payday_loan` +28pp, `debt_management_plan` +16pp, `gambling_unspecified` +15pp, `gambling_bingo` +15pp.

Parent-level accuracy still favours hinge; parent **macro** F1 does not, because of the thin-class zeros above.

Caveat unchanged: hinge has no `predict_proba`. A serving gate would use decision-function margin. If calibrated probabilities are required for audit, keep logreg or add a separate calibrator — do not treat hinge argmax as a probability. On leaf accuracy, F1, and the risk bar, hinge is the better head.

## Artefacts

- `data/classifier_v5_head_metrics_{holdout,risk}_{leaf,general}.csv`
- `src/score_classifier_heads.py`
- Predictions (gitignored): `outputs/classifier_v5_{holdout,risk}_clf_heads.csv`

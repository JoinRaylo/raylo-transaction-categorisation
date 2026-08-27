# General-category classifier bake-off (2026-08-26)

Dedicated 29-way general heads trained on the same `outputs/tuning_train.jsonl` (382,183 rows) as classifier v5. Labels are the taxonomy rollup of the existing leaf — no new labelling. Does not overwrite serving dumps. Locked v5/v6 not scored.

Holdout MD5 `c075717405a183191a43d0eb33f8dca3` (matches the v5-retrain protected hash).
Two feature settings: **frozen** TF-IDF from leaf logreg v5 (isolates 29-way vs 267-way on identical features) and **fresh** TF-IDF with the same hyper-parameters (char-wb 2–5 grams, 30k features, SGD `alpha=1e-6`, 50 epochs).

## Headline: general accuracy

Leaf models are scored by rolling the predicted leaf up to its parent. That is the number a cascade would have to beat.

| Model | Holdout general (n=1,055) | Risk gold general (n=711) | Risk-family parent (n=619) |
|---|---|---|---|
| leaf logreg v5 | 59.0% | 82.1% | 86.8% |
| leaf hinge v5 | 60.3% | 85.5% | 91.1% |
| general logreg frozen-tfidf | 62.1% | 81.0% | 85.6% |
| general hinge frozen-tfidf | 63.4% | 83.4% | 88.0% |
| general logreg fresh-tfidf | 62.0% | 81.0% | 85.6% |
| general hinge fresh-tfidf | 63.4% | 83.4% | 88.0% |

## Does a dedicated general head beat the leaf rollup?

Primary comparison: **general hinge frozen-tfidf** vs **leaf hinge v5** (hinge, frozen features — the clean ablation).

- Holdout: dedicated general 63.4% vs leaf-rollup 60.3% (+3.1%). Dedicated head beats the leaf model on parent accuracy.
- Risk gold: dedicated general 83.4% vs leaf-rollup 85.5% (-2.1%).
- Holdout disagreement vs gold: both right 573, leaf-only 63, general-only 96, neither 323.
- Risk disagreement vs gold: both right 568, leaf-only 40, general-only 25, neither 78.

`general-only` rows are the cascade's unique wins (leaf would have sent the specialist into the wrong family). `leaf-only` rows are cascade harm: the flat model already had the right parent and the 29-way head would throw it away.

Fresh TF-IDF matched frozen TF-IDF to the row on both hinge heads (holdout 63.4% = 63.4%). Re-fitting n-grams does not matter; the 29-way vs 267-way head is the whole effect.

## Verdict

A dedicated general head is a **small holdout win and a risk-set loss**. It is not a reason to replace the leaf model, and it is not yet a reason to build per-family specialists.

- Novel-merchant holdout: **+3.1pp** parent accuracy (63.4% vs 60.3%). Net unique wins 96 vs unique losses 63.
- Risk gold (the set that already has leaf structure): **−2.1pp** (83.4% vs 85.5%). Unique losses 40 vs unique wins 25.
- High-cost distress credit parent recall on risk gold **92.4% → 81.9%**. Credit-loan parent recall also dropped. Gambling parent was a wash (+1.7pp).
- Thin income / unclassified generals got worse on holdout (`income_employment` 27.8% → 5.6%, `unclassified` 31.6% → 10.5%, `income_benefits_state_support` 10.5% → 0%).
- Even with perfect specialists, holdout leaf accuracy cannot exceed 63.4% (today’s leaf hinge is 52.8% leaf / 60.3% parent). Realistic cascade leaf is closer to ~55% if within-family accuracy stays ~87%. Specialists were not trained.

**Do not switch serving to a general head. Do not train specialists unless the product can consume parent-level output and we accept a risk-family regression on the current gold.** The serving-head decision remains logreg vs hinge on the leaf model.

## Per-general recall on holdout (hinge frozen)

| General | n | Leaf-rollup recall | Dedicated recall | Δ |
|---|---|---|---|---|
| `groceries_household_essentials` | 87 | 82.8% | 82.8% | +0.0% |
| `entertainment_leisure` | 83 | 72.3% | 66.3% | -6.0% |
| `eating_drinking_out` | 81 | 74.1% | 81.5% | +7.4% |
| `general_retail_marketplaces` | 64 | 42.2% | 53.1% | +10.9% |
| `transport_motoring` | 60 | 78.3% | 70.0% | -8.3% |
| `transfers` | 55 | 56.4% | 67.3% | +10.9% |
| `clothing_personal_care` | 50 | 50.0% | 62.0% | +12.0% |
| `credit_loan_repayments` | 43 | 41.9% | 55.8% | +14.0% |
| `travel_holidays` | 42 | 57.1% | 81.0% | +23.8% |
| `pets` | 39 | 79.5% | 82.1% | +2.6% |
| `health_medical` | 38 | 78.9% | 63.2% | -15.8% |
| `utilities_household_bills` | 36 | 75.0% | 80.6% | +5.6% |
| `gambling` | 35 | 77.1% | 80.0% | +2.9% |
| `insurance` | 33 | 81.8% | 87.9% | +6.1% |
| `savings_investments` | 33 | 27.3% | 27.3% | +0.0% |
| `digital_subscriptions_services` | 32 | 68.8% | 53.1% | -15.6% |
| `home_garden` | 32 | 37.5% | 40.6% | +3.1% |
| `high_cost_distress_credit` | 27 | 74.1% | 66.7% | -7.4% |
| `income_other` | 25 | 24.0% | 40.0% | +16.0% |
| `childcare_education` | 21 | 57.1% | 66.7% | +9.5% |
| `charitable_political_giving` | 20 | 55.0% | 55.0% | +0.0% |
| `housing` | 20 | 60.0% | 55.0% | -5.0% |
| `income_benefits_state_support` | 19 | 10.5% | 0.0% | -10.5% |
| `unclassified` | 19 | 31.6% | 10.5% | -21.1% |
| `income_employment` | 18 | 27.8% | 5.6% | -22.2% |
| `council_tax_government` | 16 | 62.5% | 81.2% | +18.8% |
| `fees_charges` | 15 | 0.0% | 46.7% | +46.7% |
| `business_self_employment` | 12 | 25.0% | 50.0% | +25.0% |

## Risk families (gambling / credit_loan_repayments / high_cost_distress_credit)

A general head cannot clear the **leaf** risk bar. This table is parent-level recall on those three families on the risk gold set — the question a cascade stage-1 would actually answer.

| Family | n (risk gold) | Leaf-hinge recall | Dedicated-hinge recall | Δ |
|---|---|---|---|---|
| `credit_loan_repayments` | 245 | 93.9% | 90.6% | -3.3% |
| `gambling` | 230 | 87.4% | 89.1% | +1.7% |
| `high_cost_distress_credit` | 144 | 92.4% | 81.9% | -10.4% |

## What this does and does not decide

- **No extra labels were needed.** General is a deterministic rollup.
- A general-accuracy lift is **necessary but not sufficient** for a cascade. Leaf accuracy of `general_then_specialist` is still ≤ stage-1 general accuracy. Specialists were **not** trained in this bake-off.
- Gambling subtypes stay unmerged. Payday remains T5, not a classifier leaf.
- Serving dumps (`tfidf_logreg_v2.joblib`, `tfidf_linearsvm_sgd.joblib`) were not touched.

## Artefacts

- Weights: `outputs/distill_models/tfidf_*_general*_v5.joblib`
- Predictions: `outputs/classifier_general_v5_{holdout,risk}_{logreg,hinge}.csv`
- Scorer: `src/score_general_classifier.py`

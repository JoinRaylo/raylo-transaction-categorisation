# Repeatable waterfall evaluation

Status: **passed**. Mode: baseline. Evaluated 2026-09-15T16:11:06.789543+00:00.

No pipeline, model or serving configuration was changed by this run.

All percentages below use every row in the named view. The research pipeline
uses its original unclassified strings; serving maps T5b abstention to T7/null.
Do not pool these overlapping development/validation populations.

| Dataset | View | Head | Rows | Specific leaf accuracy | Coverage | Research exact |
|---|---|---|---:|---:|---:|---:|
| gold_credit_eval | research_pipeline | hinge | 2000 | 86.40% | 99.75% | 86.45% |
| gold_credit_eval | research_pipeline | transformer | 2000 | 89.25% | 99.85% | 89.30% |
| gold_credit_eval | serving_plaid | hinge | 2000 | 86.40% | 99.75% | 86.55% |
| gold_credit_eval | serving_plaid | transformer | 2000 | 89.25% | 99.85% | 89.30% |
| gold_merchant_labels | merchant_dictionary | dictionary | 1563 | 43.12% | 46.45% | 43.12% |
| gold_tail_labels | merchant_dictionary | dictionary | 247 | 23.48% | 26.72% | 29.55% |
| gold_transactions | research_pipeline | hinge | 5335 | 82.32% | 99.08% | 82.89% |
| gold_transactions | research_pipeline | transformer | 5335 | 83.24% | 98.61% | 83.96% |
| gold_transactions | serving_plaid | hinge | 3501 | 82.41% | 98.71% | 83.06% |
| gold_transactions | serving_plaid | transformer | 3501 | 82.80% | 98.00% | 83.86% |
| gold_transactions_risk_categories | head_only | hinge | 711 | 62.59% | 99.02% | 62.59% |
| gold_transactions_risk_categories | head_only | transformer | 711 | 74.40% | 98.17% | 74.40% |
| gold_transactions_risk_categories | legacy_head_plus_t5 | hinge | 711 | 65.96% | 99.16% | 65.96% |
| gold_transactions_risk_categories | legacy_head_plus_t5 | transformer | 711 | 74.82% | 98.17% | 74.82% |
| gold_transactions_risk_t6bound | research_pipeline | hinge | 400 | 67.25% | 96.25% | 67.50% |
| gold_transactions_risk_t6bound | research_pipeline | transformer | 400 | 72.25% | 96.50% | 72.75% |
| gold_transactions_risk_t6bound | serving_plaid | hinge | 400 | 67.25% | 96.25% | 67.50% |
| gold_transactions_risk_t6bound | serving_plaid | transformer | 400 | 72.25% | 96.50% | 72.75% |
| gold_transactions_v2 | research_pipeline | hinge | 1500 | 76.67% | 98.73% | 77.13% |
| gold_transactions_v2 | research_pipeline | transformer | 1500 | 77.40% | 98.20% | 77.80% |
| gold_transactions_v2 | serving_plaid | hinge | 1080 | 75.00% | 98.33% | 75.37% |
| gold_transactions_v2 | serving_plaid | transformer | 1080 | 75.56% | 97.50% | 76.11% |
| gold_transactions_v2_batch2 | research_pipeline | hinge | 1500 | 76.80% | 99.33% | 77.13% |
| gold_transactions_v2_batch2 | research_pipeline | transformer | 1500 | 79.20% | 99.00% | 79.53% |
| gold_transactions_v2_batch2 | serving_plaid | hinge | 661 | 75.49% | 98.94% | 75.95% |
| gold_transactions_v2_batch2 | serving_plaid | transformer | 661 | 76.70% | 98.34% | 77.46% |
| gold_transactions_v3_volume | research_pipeline | hinge | 1500 | 88.93% | 99.60% | 89.27% |
| gold_transactions_v3_volume | research_pipeline | transformer | 1500 | 89.60% | 99.40% | 90.00% |
| gold_transactions_v3_volume | serving_plaid | hinge | 900 | 88.89% | 99.33% | 89.44% |
| gold_transactions_v3_volume | serving_plaid | transformer | 900 | 89.56% | 99.00% | 90.33% |
| gold_transactions_v4_slm_volume | research_pipeline | hinge | 900 | 90.33% | 98.44% | 91.78% |
| gold_transactions_v4_slm_volume | research_pipeline | transformer | 900 | 89.67% | 97.44% | 92.00% |
| gold_transactions_v4_slm_volume | serving_plaid | hinge | 900 | 90.33% | 98.44% | 91.56% |
| gold_transactions_v4_slm_volume | serving_plaid | transformer | 900 | 89.67% | 97.44% | 91.78% |
| gold_v2_slm_eval_holdout | research_pipeline | hinge | 1055 | 78.01% | 99.24% | 78.20% |
| gold_v2_slm_eval_holdout | research_pipeline | transformer | 1055 | 80.38% | 98.67% | 80.85% |
| gold_v2_slm_eval_holdout | serving_plaid | hinge | 627 | 75.76% | 98.88% | 76.24% |
| gold_v2_slm_eval_holdout | serving_plaid | transformer | 627 | 77.51% | 97.77% | 78.31% |
| gold_v3_eyeball | research_pipeline | hinge | 1500 | 88.67% | 99.60% | 89.00% |
| gold_v3_eyeball | research_pipeline | transformer | 1500 | 89.33% | 99.40% | 89.73% |
| gold_v3_eyeball | serving_plaid | hinge | 900 | 88.56% | 99.33% | 89.11% |
| gold_v3_eyeball | serving_plaid | transformer | 900 | 89.22% | 99.00% | 90.00% |
| gold_v4_eyeball | research_pipeline | hinge | 900 | 89.78% | 98.44% | 91.22% |
| gold_v4_eyeball | research_pipeline | transformer | 900 | 89.11% | 97.44% | 91.44% |
| gold_v4_eyeball | serving_plaid | hinge | 900 | 89.78% | 98.44% | 91.00% |
| gold_v4_eyeball | serving_plaid | transformer | 900 | 89.11% | 97.44% | 91.22% |
| tuning_validation | head_only | hinge | 5000 | 71.56% | 97.30% | 72.48% |
| tuning_validation | head_only | transformer | 5000 | 77.44% | 96.08% | 79.22% |
| gold_pipeline_eval | research_pipeline | hinge | 2000 | 82.15% | 99.55% | 82.25% |
| gold_pipeline_eval | research_pipeline | transformer | 2000 | 83.55% | 99.20% | 83.80% |
| gold_pipeline_eval | serving_plaid | hinge | 1418 | 81.45% | 99.44% | 81.66% |
| gold_pipeline_eval | serving_plaid | transformer | 1418 | 82.44% | 98.87% | 82.79% |
| synthetic_credit_regressions | research_pipeline | hinge | 7 | 57.14% | 100.00% | 57.14% |
| synthetic_credit_regressions | research_pipeline | transformer | 7 | 57.14% | 100.00% | 57.14% |
| synthetic_credit_regressions | serving_plaid | hinge | 7 | 57.14% | 100.00% | 57.14% |
| synthetic_credit_regressions | serving_plaid | transformer | 7 | 57.14% | 100.00% | 57.14% |

## Inventory and limitations

- gold_credit_eval: passed. Original provider/native values, including blanks, retained; Plaid serving and mixed-provider research views reported separately.
- gold_merchant_labels: passed. Merchant labels lack transaction context: dictionary task only; no inferred direction/amount. Primary gold used; alternatives not substituted.
- gold_tail_labels: passed. Merchant labels lack transaction context: dictionary task only; no inferred direction/amount. Primary gold used; alternatives not substituted.
- gold_transactions: passed. Original provider/native values, including blanks, retained; Plaid serving and mixed-provider research views reported separately.
- gold_transactions_risk_categories: passed. Legacy risk data lacks provider/category: raw head and historical head+T5 only; complete waterfall unsupported.
- gold_transactions_risk_t6bound: passed. Original provider/native values, including blanks, retained; Plaid serving and mixed-provider research views reported separately.
- gold_transactions_v2: passed. Original provider/native values, including blanks, retained; Plaid serving and mixed-provider research views reported separately.
- gold_transactions_v2_batch2: passed. Original provider/native values, including blanks, retained; Plaid serving and mixed-provider research views reported separately.
- gold_transactions_v3_volume: passed. Original provider/native values, including blanks, retained; Plaid serving and mixed-provider research views reported separately.
- gold_transactions_v4_slm_volume: passed. Provider/category recovered by exact input join to hash-verified gold_v4_eyeball; 1:1 output count required.
- gold_transactions_v5_LOCKED: excluded_confirmation.
- gold_transactions_v6_LOCKED: excluded_confirmation.
- gold_v2_slm_eval_holdout: passed. Original provider/native values, including blanks, retained; Plaid serving and mixed-provider research views reported separately.
- gold_v3_eyeball: passed. Original provider/native values, including blanks, retained; Plaid serving and mixed-provider research views reported separately.
- gold_v4_eyeball: passed. Original provider/native values, including blanks, retained; Plaid serving and mixed-provider research views reported separately.
- tuning_validation: passed. Previously used selection validation; strict historical parser; head-only, no provider context or seed reselection.
- gold_pipeline_eval: passed. Original provider/native values, including blanks, retained; Plaid serving and mixed-provider research views reported separately.
- synthetic_credit_regressions: passed. Original provider/native values, including blanks, retained; Plaid serving and mixed-provider research views reported separately.

## Checks

- app_library_tests: passed.
- research_tests: passed.
- lint: passed.
- schemas: passed.
- deterministic_parity: passed.
- real_model_startup: passed.

## Interpretation

This is a regression baseline; it does not estimate independent production accuracy.
Historical training overlap and repeated selection limit generalisation claims.
The pipeline benchmark is its preserved historical export; training disjointness has not
been re-established against later training snapshots. Source tags are retained,
not upgraded to human review. Merchant datasets score dictionary lookup only; validation
and legacy risk data cannot establish full serving behaviour without provider context.
Per-leaf precision/F1 treat any nonmatching gold, including unknown gold, as a nonmatch;
Unknown-gold assignments are separately counted; they are not proven false positives.
Macro F1 uses specific leaves with gold support. Empty denominators are null.
GBP, account and date are API scaffolding only; currency eligibility, history features
and Taktile transport are not evaluated. Inference uses a fixed clock: no latency claim.
A passed run means evaluations executed; candidate quality gates require review.
Locked v5/v6 were not scored. The accuracy runner does not open them; research
integrity tests read retired-v5 membership to check exclusions, without scoring.
No deployment or retraining was performed.

# Experiment 3 — development champion model search

## Executive read

- **month3:** champion **0.533** GINI vs published capped taxonomy model **0.477** and reconstructed live model **0.394**. Paired uplift vs published: +0.056 (+0.030 to +0.081); vs live: +0.138 (+0.097 to +0.179).
- **month6:** champion **0.618** GINI vs published capped taxonomy model **0.564** and reconstructed live model **0.417**. Paired uplift vs published: +0.054 (+0.025 to +0.084); vs live: +0.200 (+0.158 to +0.245).

This is the strongest **development** recipe found in the saved data. It is
not a promotion result: the historical OOT windows have already been used
in earlier Experiment 3 work. Locked v5/v6 were not scored.

## What was searched

- Feature views: current **304**, all-leaf raw **1,654**, and all-leaf normalised **3,150** candidates.
- Eight initial XGBoost/LightGBM recipes varied depth, leaf size,
regularisation, class weighting, Equifax down-weighting and recency decay.
- Selection used three rolling Plaid-only validation windows before the
published OOT. Every fold used a separate chronological early-stopping
slice, then refit on all data available before that validation window.
- The final two-family blend and its weight were selected from OOF results.
Final estimates average seeds 0, 17 and 42.

## Pre-OOT model selection

### month3

| Candidate | Features | Mean GINI | Fold SD | Worst fold | Selection score |
|---|---:|---:|---:|---:|---:|
| `xgb_d5_regularised|leaf_rich` | 3150 | 0.544 | 0.025 | 0.529 | 0.537 |
| `xgb_d5_regularised|leaf_raw` | 1654 | 0.535 | 0.025 | 0.513 | 0.528 |
| `lgb_d4_recent|leaf_rich` | 3150 | 0.529 | 0.022 | 0.513 | 0.524 |
| `xgb_d3_balanced|leaf_rich` | 3150 | 0.532 | 0.038 | 0.494 | 0.522 |
| `xgb_d3_balanced|leaf_raw` | 1654 | 0.523 | 0.040 | 0.482 | 0.513 |
| `lgb_d5_weighted|leaf_rich` | 3150 | 0.523 | 0.042 | 0.481 | 0.513 |
| `xgb_d5_regularised|current` | 304 | 0.521 | 0.038 | 0.488 | 0.512 |
| `lgb_d4_recent|leaf_raw` | 1654 | 0.520 | 0.037 | 0.494 | 0.511 |
| `lgb_d5_weighted|leaf_raw` | 1654 | 0.516 | 0.050 | 0.464 | 0.503 |
| `lgb_d4_recent|current` | 304 | 0.508 | 0.038 | 0.475 | 0.498 |

Chosen blend: **0.9 XGBoost / 0.1 LightGBM**, mean fold GINI **0.544**, fold SD **0.025**.

### month6

| Candidate | Features | Mean GINI | Fold SD | Worst fold | Selection score |
|---|---:|---:|---:|---:|---:|
| `xgb_d5_regularised|leaf_raw` | 1654 | 0.581 | 0.036 | 0.540 | 0.572 |
| `xgb_d5_regularised|leaf_rich` | 3150 | 0.585 | 0.066 | 0.511 | 0.569 |
| `lgb_d5_weighted|leaf_rich` | 3150 | 0.575 | 0.042 | 0.527 | 0.564 |
| `xgb_d3_balanced|leaf_raw` | 1654 | 0.573 | 0.044 | 0.523 | 0.562 |
| `lgb_d4_recent|leaf_rich` | 3150 | 0.572 | 0.044 | 0.522 | 0.561 |
| `xgb_d3_balanced|leaf_rich` | 3150 | 0.573 | 0.074 | 0.489 | 0.554 |
| `lgb_d5_weighted|leaf_raw` | 1654 | 0.565 | 0.043 | 0.515 | 0.554 |
| `lgb_d4_recent|leaf_raw` | 1654 | 0.556 | 0.041 | 0.509 | 0.546 |
| `xgb_d5_regularised|current` | 304 | 0.548 | 0.059 | 0.480 | 0.533 |
| `lgb_d5_weighted|current` | 304 | 0.540 | 0.032 | 0.504 | 0.532 |

Chosen blend: **0.7 XGBoost / 0.3 LightGBM**, mean fold GINI **0.584**, fold SD **0.039**.

## Final saved-window confirmation

| Target | n / bads | Champion | Best XGB | Best LGB | Published capped | Live reconstruction |
|---|---:|---:|---:|---:|---:|---:|
| month3 | 4,855 / 465 | **0.533** | 0.533 | 0.525 | 0.477 | 0.394 |
| month6 | 6,652 / 410 | **0.618** | 0.611 | 0.618 | 0.564 | 0.417 |

The paired intervals above are applicant-stratified 2,000-sample bootstrap
intervals on the saved OOT. They quantify retrospective uncertainty, not
future-drift or categoriser-freeze uncertainty.

## Reproducibility, time stability and calibration

The saved model objects reproduce every saved champion prediction to
floating-point precision. GINI by final-window calendar month:

| Target | Month | n / bads | GINI |
|---|---|---:|---:|
| month3 | 2026-03 | 2,416 / 202 | 0.556 |
| month3 | 2026-04 | 2,439 / 263 | 0.507 |
| month6 | 2025-11 | 1,976 / 129 | 0.558 |
| month6 | 2025-12 | 2,704 / 177 | 0.655 |
| month6 | 2026-01 | 1,972 / 104 | 0.627 |

| Target | Component | Seed GINI range | Ensemble GINI |
|---|---|---:|---:|
| month3 | xgb | 0.528–0.532 | 0.533 |
| month3 | lgb | 0.521–0.525 | 0.525 |
| month6 | xgb | 0.605–0.613 | 0.611 |
| month6 | lgb | 0.613–0.619 | 0.618 |

Class/provider weighting improves rank ordering but inflates raw scores.
The saved artefacts therefore include Platt scaling fitted only on the
rolling pre-OOT blend predictions. It leaves GINI unchanged and improves
the saved-window probability metrics:

| Target | Event rate | Mean raw | Mean calibrated | Brier raw | Brier calibrated |
|---|---:|---:|---:|---:|---:|
| month3 | 0.096 | 0.165 | 0.074 | 0.0837 | 0.0779 |
| month6 | 0.062 | 0.114 | 0.051 | 0.0570 | 0.0512 |

## Promotion gate

Freeze the taxonomy, merchant dictionary, residual classifier, feature SQL
and selected recipe before a new outcome window. Promote only if that single
prospective test clears the pre-agreed GINI/non-inferiority bars, calibration
checks and category-level risk recall checks. Do not tune again on that window.

## Artefacts

- `outputs/experiment3_champion_features.parquet`
- `outputs/experiment3_champion_search.json`
- `outputs/experiment3_champion_oof_predictions.parquet`
- `outputs/experiment3_champion_oot_predictions.parquet`
- `outputs/experiment3_champion_validation.json`
- `outputs/experiment3_champion_month3.joblib`
- `outputs/experiment3_champion_month6.joblib`

Reproduce with `uv run python src/experiment3_champion_model.py all`.

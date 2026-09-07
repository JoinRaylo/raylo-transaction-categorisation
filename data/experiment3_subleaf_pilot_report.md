# Experiment 3 shadow-subleaf pilot

**Decision:** The pilot is inconclusive rather than evidence that more leaves are automatically better. Keep 275 as the production taxonomy and retain these children only as a shadow experiment.

## What was tested

Three existing parents were split into 15 mutually exclusive shadow buckets (12 net additional leaves, so 275 would become 287 if all were adopted). The production categorisation was not changed. Rules use only merchant and description text, were frozen before outcomes were inspected, and always fall back to the existing parent.

The clean expansion test is **subleaf overlay vs parent control**. Both models receive exact totals for the three existing parents; only the challenger receives the within-parent child composition. This prevents a gain from being misattributed to splitting when it really came from merely exposing the parent leaf. The frozen rich overlay was followed by a lean composition-only sensitivity and one-parent-at-a-time ablations, explicitly marked exploratory.

## Results

### Rolling pre-OOT Plaid validation (primary)

| target | current | + parent controls | + lean split | + rich split | lean delta (95% paired CI) | rich delta (95% paired CI) |
|---|---:|---:|---:|---:|---:|---:|
| month3 | 0.518 | 0.513 | 0.508 | 0.511 | -0.004 (-0.010 to +0.001) | -0.002 (-0.008 to +0.003) |
| month6 | 0.569 | 0.571 | 0.564 | 0.560 | -0.007 (-0.021 to +0.007) | -0.011 (-0.025 to +0.002) |

### One-parent-at-a-time rolling sensitivity (exploratory)

| target | streaming delta | marketplace delta | payment-intermediary delta |
|---|---:|---:|---:|
| month3 | -0.001 | -0.003 | -0.006 |
| month6 | -0.001 | -0.007 | -0.004 |

### Existing development OOT (secondary confirmation)

This window has been used by earlier Experiment 3 work, so it is confirmation evidence, not a fresh promotion test.

| target | current | + parent controls | + lean split | + rich split | lean delta (95% CI) | rich delta (95% CI) |
|---|---:|---:|---:|---:|---:|---:|
| month3 | 0.519 | 0.517 | 0.516 | 0.516 | -0.001 (-0.007 to +0.005) | -0.001 (-0.006 to +0.005) |
| month6 | 0.584 | 0.586 | 0.589 | 0.586 | +0.002 (-0.004 to +0.009) | +0.000 (-0.006 to +0.007) |

## Coverage of the frozen rules

| parent | shadow child | transactions | share within parent | proposal/provider rows |
|---|---|---:|---:|---:|
| marketplace_general | marketplace_resale_auction | 307,331 | 55.9% | 29,755 |
| marketplace_general | marketplace_amazon | 159,853 | 29.1% | 17,019 |
| marketplace_general | marketplace_social_commerce | 34,763 | 6.3% | 9,145 |
| marketplace_general | marketplace_low_cost_import | 27,167 | 4.9% | 7,017 |
| marketplace_general | marketplace_other | 20,477 | 3.7% | 7,621 |
| payment_intermediary | payment_digital_wallet | 220,363 | 76.7% | 15,756 |
| payment_intermediary | payment_collection_network | 29,256 | 10.2% | 5,007 |
| payment_intermediary | payment_marketplace_escrow | 15,659 | 5.4% | 3,065 |
| payment_intermediary | payment_merchant_processor | 14,060 | 4.9% | 1,319 |
| payment_intermediary | payment_other | 8,004 | 2.8% | 2,520 |
| streaming | streaming_video_subscription | 234,123 | 72.2% | 34,704 |
| streaming | streaming_audio_books | 52,170 | 16.1% | 12,946 |
| streaming | streaming_other | 28,752 | 8.9% | 7,772 |
| streaming | streaming_transactional_video | 8,290 | 2.6% | 3,178 |
| streaming | streaming_sports | 946 | 0.3% | 389 |

## Guardrails and interpretation

- Corrected as-of Experiment 3 transaction tables and current proposal features were used.
- The same fixed regularised XGBoost recipe and chronological folds were used for every feature set; no split rule was selected on the OOT result. The lean and single-parent runs are post-primary sensitivity checks and are not presented as fresh confirmatory tests.
- The primary comparison is paired on identical applicants. Final OOT predictions average seeds 0, 17 and 42.
- Aggregate child counts and amounts reconcile exactly to their parent totals; every unmatched row falls back to its current parent.
- No locked classifier v5/v6 evaluation set was read or scored.
- A positive risk-model result would establish predictive utility, not semantic correctness. Before adding real leaves, sample and human-label each child, set minimum support/accuracy bars, and run fairness/stability checks on a fresh outcome vintage.

Machine-readable results: `outputs/experiment3_subleaf_results.json`. Frozen rules: `taxonomy/experimental_subleaf_pilot.csv`.

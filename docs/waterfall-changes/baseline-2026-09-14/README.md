# T7 abstention versus T6 rescue — 14 September 2026

**Recommendation: retain the current zero-cutoff, T7-on-abstention policy.** With the selected transformer seed 123, T6 rescue adds three correct specific labels across the three development datasets, but 26 additional labels disagree with gold: 17 contradict a specific gold category and nine assign a category where gold remains unclassified. This is a coverage/reliability trade-off, not evidence that T7 maximises the number of correct specific labels. These are experiment counts, not a pooled estimate of production accuracy.

The targeted risk set makes the trade-off concrete: T6 recovers two exact risk labels, assigns the wrong specific category to three other risk transactions, creates five risk flags on known non-risk transactions, and assigns risk categories to four gold-unclassified transactions. The last four are unsupported assignments, not established false positives. No model, taxonomy, threshold, serving configuration or deployment was changed.

## Launch transformer, cutoff 0.0

| Dataset | Rows | Specific leaf accuracy: T7 / T6 | Coverage: T7 / T6 | Correct T6 additions | Incorrect/unsupported additions |
|---|---:|---:|---:|---:|---:|
| Plaid holdout | 627 | 77.51% / 77.67% | 97.77% / 99.68% | 1 | 11 |
| Credit evaluation | 2,000 | 89.25% / 89.25% | 99.85% / 100.00% | 0 | 3 |
| Targeted risk evaluation | 400 | 72.25% / 72.75% | 96.50% / 100.00% | 2 | 12 |

Only model-predicted `unclassified_*` rows abstain at cutoff zero. There are 14, 3 and 14 such rows respectively. The holdout has two T6 mappings to an unclassified subtype; these change the taxonomy string but add no classified coverage. Of the 29 specific labels added by T6, only three match gold.

Accuracy among transactions assigned a specific category falls from **79.28% to 77.92%** on the holdout, **89.38% to 89.25%** on credits, and **74.87% to 72.75%** on the risk set. Because that metric changes its denominator, the table above also gives accuracy over every source row.

## Metric definitions

- **Specific leaf accuracy:** correctly assigned non-`unclassified_*` leaves divided by every row in that dataset. T7 is an abstention, so does not count as a correct specific assignment, including when gold is unclassified. Missing/incorrect outputs remain in the denominator. The JSON also supplies accuracy restricted to known-gold rows.
- **Coverage:** proportion assigned a non-null, non-`unclassified_*` leaf. A mapped provider unclassified subtype does not count as covered.
- **Incorrect/unsupported additions:** new specific T6 assignments that do not equal the gold leaf. These include both contradictions of specific gold labels and unsupported labels on gold-unclassified rows.
- **General accuracy:** the same specific-assignment convention, using the frozen taxonomy parent. No separate model general-head prediction is substituted.
- **Research-style accuracy:** a separate diagnostic maps serving T7/null to `unclassified_other` and scores exact taxonomy strings, as research tables do. This can reward correct abstentions and is not the same as specific-category accuracy. It also does not preserve the model's other raw unclassified subtypes.
- **Risk categories:** the research definition: `gambling`, `credit_loan_repayments`, `high_cost_distress_credit`. A known non-risk false positive requires a specific non-risk gold label; gold-unclassified risk assignments are counted separately. Risk false negatives include abstentions. Housing and utilities are not included in this particular research risk bar.

## Launch transformer: general accuracy and risk outcomes

| Dataset | Specific general accuracy: T7 / T6 | Research-style leaf accuracy: T7 / T6 | Risk gold rows | Exact risk leaf accuracy: T7 / T6 |
|---|---:|---:|---:|---:|
| Plaid holdout | 83.89% / 84.21% | 78.31% / 77.67% | 57 | 84.21% / 84.21% |
| Credit evaluation | 90.60% / 90.60% | 89.30% / 89.25% | 119 | 89.92% / 89.92% |
| Targeted risk evaluation | 83.25% / 83.75% | 72.75% / 72.75% | 174 | 82.76% / 83.91% |

On the targeted set, exact risk recovery improves **144/174 to 146/174**. Risk-family false negatives fall **14 to 9**, because even the three incorrect specific risk labels still flag a risk family. That benefit comes with the five new known non-risk false positives and four new unclassified-gold risk assignments described above. The relative cost of those errors has not been measured downstream.

## Hinge v8, cutoff 0.0

| Dataset | Rows | Specific leaf accuracy: T7 / T6 | Coverage: T7 / T6 | Correct T6 additions | Incorrect/unsupported additions |
|---|---:|---:|---:|---:|---:|
| Plaid holdout | 627 | 75.76% / 75.76% | 98.88% / 99.68% | 0 | 5 |
| Credit evaluation | 2,000 | 86.40% / 86.40% | 99.75% / 99.85% | 0 | 2 |
| Targeted risk evaluation | 400 | 67.25% / 68.00% | 96.25% / 100.00% | 3 | 12 |

The fallback head shows the same trade-off: three correct additions and 19 incorrect/unsupported additions across these samples. On the targeted risk set, it adds five known non-risk risk flags and two risk assignments on unclassified gold.

## Predeclared cutoff 0.2 sensitivity

This was the earlier scaffold cutoff and was chosen before scoring this comparison. It is a sensitivity check, not a selected/calibrated threshold; margins from the two heads are on different scales. No threshold sweep or optimisation was performed.

### Transformer seed 123

| Dataset | Rows | Specific leaf accuracy: T7 / T6 | Coverage: T7 / T6 | Correct T6 additions | Incorrect/unsupported additions |
|---|---:|---:|---:|---:|---:|
| Plaid holdout | 627 | 77.03% / 77.67% | 94.90% / 99.20% | 4 | 23 |
| Credit evaluation | 2,000 | 88.70% / 89.05% | 98.15% / 99.50% | 7 | 20 |
| Targeted risk evaluation | 400 | 71.50% / 72.50% | 93.00% / 100.00% | 4 | 24 |

### Hinge v8

| Dataset | Rows | Specific leaf accuracy: T7 / T6 | Coverage: T7 / T6 | Correct T6 additions | Incorrect/unsupported additions |
|---|---:|---:|---:|---:|---:|
| Plaid holdout | 627 | 73.84% / 74.32% | 92.50% / 99.36% | 3 | 40 |
| Credit evaluation | 2,000 | 85.55% / 85.85% | 96.80% / 98.65% | 6 | 31 |
| Targeted risk evaluation | 400 | 63.75% / 65.00% | 84.75% / 100.00% | 5 | 56 |

T6 again buys extra coverage with mostly incorrect/unsupported specific labels. These results do not justify moving the launch cutoff from 0.0 to 0.2.

## Data selection and limitations

All three CSVs were checked against the frozen library registry by SHA-256 before parsing or scoring. Each is registered as **development**, even the file named holdout. No locked v5/v6 data was read or scored; no training data was read or model fitted.

| Dataset | Source rows | Included Plaid rows | T5b residual rows | Duplicate input rows | Conflicting-label input groups | Unique consistent inputs |
|---|---:|---:|---:|---:|---:|---:|
| Plaid holdout | 1,055 | 627 | 273 | 13 | 0 | 614 |
| Credit evaluation | 2,000 | 2,000 | 1,863 | 97 | 12 | 1,891 |
| Targeted risk evaluation | 400 | 400 | 333 | 12 | 0 | 388 |

No native category or amount is missing on the included rows. The holdout contributes 595 debits and 32 credits; the credit set contributes 2,000 credits; the targeted risk set contributes 400 debits. Equifax holdout rows are excluded because the app accepts Plaid. The older 711-row risk dataset has no provider category and cannot answer this paired fallback question. Training-contaminated volume sets and tuning validation are not used.

The adapter uses the original merchant, description, native category and absolute amount, restoring the API amount sign from the explicit research direction. No merchant/name fallback or description trimming is introduced. Currency is scaffolded as GBP because these CSVs lack a currency column; date and account IDs are synthetic and do not affect the waterfall. This is not evidence about currency eligibility or date-based features in live payloads.

**Duplicates and label uncertainty:** primary metrics retain the original dataset rows and their original labels. The sensitivity analysis groups exact merchant, description, amount, direction and native-category inputs. It keeps one row per consistent group, and excludes all 12 conflicting-label groups in the credit set without changing their labels. Transformer launch T6 additions then become **1 correct / 11 disagreeing**, **0 / 1**, and **2 / 12** respectively. The conclusion survives that check. All credit-set groups with conflicting labels should be adjudicated in a later data-quality task; this comparison does not relabel them.

**Provenance:** the historical holdout has human-adjudicated labels, but has repeatedly informed model/rule selection. Credit labels are 28 human-reviewed, 1,483 agent-consensus, 242 agent-tiebreak and 247 agent-review. Targeted risk labels are 383 human-reviewed and 17 agent-review. On its human-reviewed rows alone, transformer T6 adds two correct and nine disagreeing labels. Source provenance splits are retained in the JSON.

**Generalisation:** these are differently sampled development populations. Do not average their percentages into a production headline. Blank merchants dominate credits (1,924/2,000) and targeted risk (303/400); exact-text exclusions do not imply independent narrative families. These small abstention samples do not establish future error rates or a statistically validated downstream cost function. A final go/no-go evaluation remains separate.

## Execution and verification

- Executed locally on CPU using the verified bundle, transformer seed 123 and hinge v8. The actual `Waterfall` and `Classifier` produce T7 outputs; the counterfactual substitutes the original deterministic T6 only for classifier abstentions with a T6 mapping. T1–T5 decisions remain unchanged.
- Both head results are measured without runtime degradation. A fixed evaluation clock deliberately removes timing from this quality comparison; no latency, deployed-container or end-to-end Taktile claim is made.
- Model loading and inference were network-disabled. The bundle passed all 20 startup golden probes. Dataset hashes, bundle digest and code hashes are recorded in `summary.json`.
- All 12 paired comparisons passed identity, unchanged-protected-tier, identical-raw-prediction-across-cutoffs and metric-delta assertions.
- The research `confusion_analysis.analyse` independently reproduced leaf/general/risk metrics for all 24 policy outputs. Specific-category accuracy and coverage were independently recounted; direction/provenance subtotals and rescue deltas reconcile. Four hand-calculated unit tests cover unknown labels, denominator changes, risk flags, empty slices and protected tiers.

Assessment: **share with the stated caveats**. Aggregate evidence: [summary.json](summary.json), [validation.json](validation.json). Row-level outputs contain source line numbers and category diagnostics, not narratives or merchant names, and remain in local scratch rather than this repository.

## Reproduce

Run from the monorepo in the frozen app environment, with an empty output directory:

```sh
python apps/ob-txn-categoriser/scripts/compare_abstention.py \
  --research-root /path/to/raylo-transaction-categorisation \
  --bundle /path/to/verified/bundle \
  --bundle-sha a2553f3462205963254b0fb1ad9dff6d64e1399abdecaab93977265908c7f23d \
  --output /path/to/empty/local/scratch
```

Bundle SHA-256: `a2553f3462205963254b0fb1ad9dff6d64e1399abdecaab93977265908c7f23d`. Exact source/runtime/data identities and per-direction, per-provenance, residual and unique-input comparisons are in the JSON.

# Experiment 3 granularity — stress-test review

_Run 2026-09-01 from the saved Experiment 3 proposal features and ladder
aggregates. Three XGBoost seeds (0, 17, 42); 1,000 outcome-stratified,
applicant-level bootstrap resamples. Locked v5/v6 were not scored._

Script: `src/audit_experiment3_granularity.py`  
Full results: `outputs/experiment3_granularity_stress_test.json`  
Ensemble OOT predictions: `outputs/experiment3_granularity_stress_predictions.parquet`

## Assessment

**Share with substantial caveats; not yet sufficient evidence to simplify the
source taxonomy.** The risk-feature result is directionally robust: 275, the
current 69-feature grouping, and 29 groups are statistically indistinguishable
on both OOT targets. Seventeen groups is close but shows a small month-6 penalty
in the uncapped model. Nine groups loses material month-6 signal, and 7/4 groups
lose signal on both targets.

This experiment supports a **derived risk-feature rollup** at roughly 29 groups
(17 remains a candidate). It does not support replacing the 275-leaf source
taxonomy, because the transaction categoriser was not retrained at each rung
and because the taxonomy/dictionary was built after the OOT periods.

## Input QA

- Taxonomy and ladder both contain 275 unique leaves; no missing/extra leaves.
- The 29-general and 7-cash-flow mappings exactly match `taxonomy.csv`.
- 64,135 proposal/provider rows remain after the documented provider overlap
  rule; there are no duplicate proposal/provider rows.
- The 6,426,791-row long aggregate has no duplicate
  proposal/provider/rung/group keys.
- `g_debit_amt` is null on 301 repeated rung rows, originating from 43 Equifax
  proposals with null transaction amounts. XGBoost treats these as missing, but
  the upstream amount-null policy should be made explicit before promotion.
- The current rung has 69 possible groups but 68 observed in this cohort;
  `income_benefits_state_support` is the unobserved group. The code has 41, not
  40, `KEY_LEAVES`.

## Repeated-seed result (`dims_held`, uncapped)

Values are the mean signed GINI across three single models; the standard
deviation across seeds is in parentheses.

| Rung | Month 3 | Month 6 |
|---|---:|---:|
| 275 leaves | 0.485 (0.001) | 0.571 (0.008) |
| Current 69 | 0.482 (0.007) | 0.571 (0.005) |
| 29 generals | 0.479 (0.003) | 0.560 (0.003) |
| 17 budget groups | 0.479 (0.006) | 0.545 (0.004) |
| 9 macro groups | 0.468 (0.010) | 0.495 (0.006) |
| 7 cash-flow groups | 0.438 (0.003) | 0.474 (0.004) |
| 4 minimal groups | 0.431 (0.007) | 0.472 (0.004) |

Paired bootstrap differences are more informative than overlapping marginal
confidence intervals:

| Comparison (A − B), uncapped | Month 3 Δ GINI (95% CI) | Month 6 Δ GINI (95% CI) |
|---|---:|---:|
| 275 − current 69 | +0.003 (−0.016, +0.021) | −0.001 (−0.017, +0.016) |
| 29 − current 69 | −0.004 (−0.019, +0.012) | −0.010 (−0.028, +0.009) |
| 17 − current 69 | −0.003 (−0.025, +0.021) | **−0.026 (−0.051, −0.003)** |
| 9 − 17 | −0.011 (−0.032, +0.007) | **−0.050 (−0.069, −0.031)** |
| 7 − 17 | **−0.042 (−0.069, −0.018)** | **−0.072 (−0.106, −0.038)** |
| 4 − 17 | **−0.049 (−0.075, −0.023)** | **−0.074 (−0.105, −0.044)** |

The 50-feature-capped result is broadly consistent: 29 and 17 are not
distinguishable from current 69. Nine is lower than 17 on month 3 by 0.020
(95% CI 0.001–0.039) and on month 6 by 0.034 (0.013–0.054). Seven and four are
clearly lower. The 275-leaf cap is unstable and capacity-constrained: across
three seeds, only 32 of the 50 month-3 selected features were common to every
seed, while the union contained 70 features. Current 69 was similarly unstable
(34 common; 71 in the union). A single capped run should not be used to rank
the fine rungs.

## Live comparator and uplift attribution

The ladder's published live-feature XGBoost is an in-repo reconstruction, not
the saved production model or production predictions. It is also trained only
on the inner 80% train split, while each taxonomy model is refitted on 100% of
the train window. This audit additionally refit the live-feature reconstruction
on the full train window. Seed-mean GINI was 0.392 (month 3) and 0.411 (month 6),
versus the published single run's 0.403 / 0.386.

All ladder point estimates remain above the full-refit reconstruction, but the
4-group capped month-3 uplift is not conclusive: +0.035 GINI, paired 95% CI
−0.004 to +0.074. The month-6 difference is +0.058 (0.012 to 0.100).

The closest available categorisation-only ablation uses the same 20 feature
definitions, same Plaid-only train rows, same XGBoost, and changes Plaid-native
features to taxonomy-leaf versions:

| Same-20 XGBoost | Live features | Taxonomy features | Taxonomy − live (paired 95% CI) |
|---|---:|---:|---:|
| Month 3 | 0.392 | 0.375 | −0.017 (−0.049, +0.018) |
| Month 6 | 0.411 | 0.447 | +0.036 (−0.005, +0.077) |

Neither difference is conclusive and the direction changes by target. The
large headline uplift therefore belongs to the **whole feature/model bundle**
(categorisation, new engineered features, selection and training history), not
to the taxonomy alone.

## Methodological gaps to close

1. **Post-OOT taxonomy exposure.** The March–April 2026 and
   November 2025–January 2026 OOT rows were categorised with a dictionary and
   classifier built in August 2026 from the later Plaid vocabulary. Labels did
   not use arrears outcomes, so this is not direct target leakage, but it is
   transductive merchant-vocabulary leakage. A production claim needs an
   as-of-frozen taxonomy/dictionary/classifier or a future prospective cohort.
2. **Post-hoc rollup, not end-to-end retraining.** Every rung rolls up the same
   275-leaf predictions. A genuinely smaller taxonomy would train a smaller
   transaction head and could change accuracy, abstention and risk-family
   errors. The existing 29-way bake-off already proves this matters: direct
   parent training improved novel-merchant parent accuracy by 3.1pp but reduced
   risk-gold parent accuracy by 2.1pp.
3. **One hierarchy per category count.** The result confounds the number of
   groups with the chosen semantic mergers. Multiple plausible 17- and 9-group
   maps are needed to show the boundary is not an artefact of this one ladder.
4. **Only two OOT windows, reused for model decisions.** Use pre-declared rolling
   time splits and reserve one untouched promotion window. Bootstrap intervals
   quantify applicant sampling, not time drift.
5. **Comparator fidelity.** Score the actual production model artefact or its
   frozen OOT predictions. Give both sides identical train rows, feature budget,
   refit policy and hyperparameter-search budget.
6. **Aggregate GINI is not a taxonomy-quality metric.** It can hide regressions
   in gambling, high-cost credit, income and fairness-relevant distinctions.
   Keep the existing per-family confusion/risk bars as hard promotion gates.

## Recommended verification sequence

1. Freeze the current 275-leaf taxonomy, dictionary, T1–T5 rules and serving
   hinge with an effective date. Do not change the source taxonomy yet.
2. Train direct residual categorisers for 69, 29, 17 and 9 groups on the same
   merchant-disjoint split. Measure group accuracy, macro/weighted F1,
   abstention, coverage and the risk-family minimum bar. Compare each direct
   head with rolling up the leaf head.
3. Rebuild the full transaction stream using each direct head, then rebuild the
   risk features. This is the missing end-to-end test.
4. Run at least four rolling OOT windows per outcome and five fixed seeds, with
   screening and gain selection nested inside each train window. Report paired
   applicant bootstraps and the distribution across time windows.
5. At 17 and 9 groups, test at least three plausible business-authored merger
   maps. Pre-register a non-inferiority margin (suggested starting point:
   no worse than 0.02 signed GINI on either target) and risk-family tolerances.
6. Use the actual frozen live XGBoost as comparator. Keep the same-20-feature
   ablation alongside the richer challenger so taxonomy lift and feature-
   engineering lift are reported separately.
7. Score locked v6 only once, after the rung, feature budget, thresholds and
   decision rule are fixed. A future outcome-matured cohort categorised using
   the frozen stack is the final prospective confirmation.

## Decision recommendation now

- Keep the **275 leaves as the governed source-of-truth taxonomy**.
- For the credit-risk feature layer, treat **29 groups as the evidence-backed
  simplification**; keep 17 as a challenger pending direct-head and temporal
  validation.
- Do not go to 9 or fewer groups on the current evidence.
- Reword the existing headline from “flat 275 to 17; every rung beats live” to
  “275, 69 and 29 are indistinguishable; 17 is close but may lose month-6
  signal; 9 and below degrade, and the smallest-rung uplift is not conclusive
  on month 3.”

# Why Raylo should keep the 275-leaf transaction taxonomy

## Executive recommendation

**Keep 275 leaves as Raylo's governed source-of-truth taxonomy.** Keep the
29-group view as a benchmark and reporting rollup, while allowing each
credit-risk model to consume detailed leaves when time validation supports it.

The evidence does not show that 275 leaves hurt model performance. It shows that
the risk model can safely aggregate the leaves when it needs to. Keeping the
detailed source preserves information, explainability and important risk
distinctions; collapsing the source taxonomy would destroy information that
cannot be recovered later.

## The decision in one table

The same transactions, outcome windows and XGBoost design were rerun at seven
levels of category granularity. Results below are mean signed GINI across three
model seeds; the models retain Raylo's orthogonal attributes such as essential
spend, priority debt and high-cost-credit flags.

| Category view | Month-3 GINI | Month-6 GINI | Decision read |
|---|---:|---:|---|
| 275 detailed leaves | **0.485** | **0.571** | No performance penalty from detail |
| Current 69-feature grouping | 0.482 | **0.571** | Statistically tied with 275 |
| 29 general categories | 0.479 | 0.560 | Statistically tied with current 69 |
| 17 budget groups | 0.479 | 0.545 | Close; small month-6 penalty remains possible |
| 9 macro groups | 0.468 | 0.495 | Material month-6 loss |
| 7 cash-flow groups | 0.438 | 0.474 | Clear loss on both outcomes |
| 4 minimal groups | 0.431 | 0.472 | Clear loss on both outcomes |

Applicant-level paired bootstrap tests confirm the important boundaries:

- **275 vs current 69:** month 3 +0.003 GINI (95% CI −0.016 to +0.021);
  month 6 −0.001 (−0.017 to +0.016). There is no measurable difference.
- **29 vs current 69:** month 3 −0.004 (−0.019 to +0.012); month 6 −0.010
  (−0.028 to +0.009). There is no measurable difference.
- **9 vs 17:** month 6 loses **0.050 GINI** (−0.069 to −0.031).
- **7 vs 17:** month 3 loses **0.042** (−0.069 to −0.018) and month 6
  loses **0.072** (−0.106 to −0.038).

The conclusion is therefore not “the model needs all 275 leaves.” It is:
**the detailed taxonomy is free at the source layer, while the model can choose
the aggregation it needs.**

## The deeper model search found real value in the detailed leaves

The follow-up champion search was deliberately selected on three rolling Plaid
validation windows before the published OOT. Holding the XGBoost recipe fixed,
adding the detailed leaf blocks improved mean pre-OOT GINI as follows:

| Target | Current feature view | Detailed-leaf view | Gain |
|---|---:|---:|---:|
| Month 3 | 0.521 | **0.544** | **+0.022** |
| Month 6 | 0.548 | **0.581** | **+0.033** |

The final recipe then blended XGBoost and LightGBM and averaged three seeds. On
the saved historical OOT it achieved:

| Target | Published capped taxonomy model | New development champion | Paired uplift (95% CI) |
|---|---:|---:|---:|
| Month 3 | 0.477 | **0.533** | **+0.056** (+0.030 to +0.081) |
| Month 6 | 0.564 | **0.618** | **+0.054** (+0.025 to +0.084) |

This is the clearest modelling evidence for preserving the 275-leaf source:
once the search was allowed to use all detailed leaves, it found stable extra
signal that the smaller hand-selected view had left behind. It still does not
mean every leaf belongs in every production model—the trees choose useful
splits—but that is a reason to preserve the detailed inputs, not delete them.

These are development results, not a promotion test. Earlier work had already
used the same historical OOT windows, so the recipe must be frozen and tested
once on a new prospective outcome window before deployment.

## The new categorisation is materially better than provider categories

On the same 1,884 row-disjoint labelled transactions:

| Categorisation method | Leaf accuracy | General accuracy |
|---|---:|---:|
| Provider category alone | **31.8%** | 44.1% |
| Raylo rules/dictionary, provider only as backup | **72.0%** | 79.8% |
| Raylo rules/dictionary + serving hinge classifier | **80.5%** | 86.4% |

The improvement is especially clear on Plaid rows already resolved by Raylo's
T1–T4 logic: **91.9% leaf accuracy vs 31.8% for Plaid-native categories**.
This is evidence for owning the categorisation layer rather than allowing a
provider's changing labels to define model features.

## Why not replace 275 leaves with 29?

### 1. Detail can always be aggregated; lost detail cannot be recreated

A transaction stored as `gambling_lottery` can be rolled up to `gambling` at
feature-build time. A transaction stored only as `gambling` cannot later be
split reliably into lottery, casino, betting or bingo without recategorising
the raw transaction history.

The 29-group model view therefore gives the modelling simplicity stakeholders
want without deleting information from the governed taxonomy.

### 2. Aggregate model GINI hides important category-level risk

The combined `gambling_months` feature had IV **0.0053**, while lottery alone
had IV **0.0498**—more than nine times larger. A multivariate XGBoost can recover
some of that signal from correlated features, which is why aggregate GINI looks
flat, but the subtype remains important for transparent screening, monitoring
and explanation.

This same principle applies to payday lending, cash advances, debt-management
plans, revolving credit and returned payments. These are not interchangeable
merely because a headline GINI can remain similar after aggregation.

### 3. Direct coarse classification has already shown a risk regression

A dedicated 29-way transaction classifier improved parent accuracy on the
novel-merchant holdout from **60.3% to 63.4%**, but reduced risk-gold parent
accuracy from **85.5% to 83.4%**. High-cost-distress parent recall fell from
**92.4% to 81.9%**—a 10.5 percentage-point loss hidden by the aggregate result.

That is exactly why the source taxonomy and its per-risk-category validation
should remain detailed even if the downstream risk model consumes rollups.

### 4. The detailed taxonomy is a governance asset, not just a model input

The 275 leaves provide:

- stable Raylo-owned definitions across Plaid and Equifax;
- traceable merchant/rule decisions for each transaction;
- monitoring at the level of specific credit and gambling behaviours;
- the ability to build different rollups for credit risk, affordability,
  customer support or future products without relabelling the raw history.

Reducing the source taxonomy would trade away those capabilities without a
demonstrated model-performance benefit.

## What the risk-model uplift does—and does not—prove

The richer taxonomy feature/model bundle beats the reconstructed live-feature
XGBoost within the saved OOT sample. For the current capped grouping, the paired
uplift is:

- month 3: **+0.088 GINI** (95% CI +0.048 to +0.129);
- month 6: **+0.148 GINI** (+0.104 to +0.191).

This is strong evidence that the new overall feature approach is better in the
retrospective experiment. It is not evidence that taxonomy labels alone caused
the entire uplift: a strict same-20-feature ablation was inconclusive and changed
direction by outcome. The uplift also includes better engineered features,
feature selection and additional training history.

The stakeholder-safe wording is:

> Raylo's new categorisation and feature-engineering approach produces a large,
> statistically robust retrospective GINI uplift. Within that approach, keeping
> 275 source leaves has no measurable model cost, while collapsing below roughly
> 17 groups destroys signal. We should therefore preserve the detailed governed
> taxonomy and let individual models consume validated rollups.

## Decision and safeguards

1. Keep `taxonomy/taxonomy.csv` at 275 leaves.
2. Keep the 29 general categories as the benchmark/reporting rollup; use the
   validated detailed-leaf views in the new development champion.
3. Keep 17 groups as a coarse experimental challenger; do not move to 9 or fewer.
4. Continue to enforce category-level risk bars for gambling, credit repayments
   and high-cost/distress credit.
5. Validate the final model prospectively using a taxonomy, dictionary and
   classifier frozen before the outcome window. Locked v6 remains untouched
   until the model design and promotion rule are final.

## Evidence base

- `data/experiment3_champion_model_report.md`
- `data/experiment3_granularity_stress_test_report.md`
- `data/experiment3_granularity_ladder_report.md`
- `data/waterfall_pipeline_report.md`
- `data/classifier_general_bakeoff_report.md`
- `data/experiment3_xgb_report.md`

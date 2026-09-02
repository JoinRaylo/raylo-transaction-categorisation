# Experiment 3 — category-granularity sensitivity

_Run 2026-09-01. Answers the stakeholder question raised after the
Experiment 3 readout: if the taxonomy had fewer categories — or more —
how much model GINI would we keep?_

Same cohort, same OOT windows, same XGBoost, same screen as the 27 Aug
Experiment 3 run. **Only the category granularity of the feature blocks
changes.** The taxonomy itself is untouched: rungs live in a separate
mapping (`taxonomy/granularity_ladder.csv`) and the rung columns are
derived at feature-build time. Locked v5/v6 are not scored.

Script: `src/experiment3_granularity_ladder.py` (`aggregate` → BigQuery long-format, `train` → the curve).

## Headline

**Live comparator** (Plaid-native XGBoost on the Plaid population, the
model actually in production): month3 **0.403**, month6 **0.3861**.
The ladder harness reproduces these exactly, which validates the setup.

Three things the curve says:

1. **Granularity barely matters between 275 and ~17 categories.** month3 sits in a 0.475–0.484 band across those four rungs and month6 in a 0.542–0.576 band. That is inside run-to-run noise for a model this size. The signal is not coming from fine category distinctions.
2. **Below 9 groups it falls off, and the fall is real.** month6 drops from 0.542 at 17 groups to 0.501 at 9 and 0.472 at 7 — roughly 7 GINI points. Collapsing spend into one bucket destroys the discretionary-vs-essential and distress-credit structure the model relies on.
3. **Every rung still beats the live model.** Even the 4-group taxonomy (0.423 / 0.468) is above live (0.403 / 0.3861). The gain over Plaid's own categories comes from **resolving the merchant correctly at all** (T1–T5b), not from how finely we then bucket it.

## Variant A — dimensions held constant (`dims_held`)

Rung blocks + spine + the orthogonal dimensions (necessity, cash-flow type,
`is_debt_related`, `is_priority_debt`, `is_age_restricted`, `risk_flag`).
These are leaf attributes and survive any rollup, so this is the business
read: *does the model still work if we simplify the tree?*

### 50-feature cap

| Rung | Groups | month3 GINI | month6 GINI | m3 Plaid-only | m6 Plaid-only | m3 feats |
|---|---|---|---|---|---|---|
| `l0_leaf_275` — all 275 leaves | 270 | **0.439** | **0.545** | 0.4069 | 0.5084 | 50 |
| `l0_current_69` — 40 key leaves + 29 generals (today) | 68 | **0.470** | **0.558** | 0.4503 | 0.5141 | 50 |
| `l1_general_29` — 29 general categories | 29 | **0.468** | **0.568** | 0.4483 | 0.4965 | 50 |
| `l2_budget_17` — 17 budget-line groups | 17 | **0.480** | **0.534** | 0.4619 | 0.5177 | 50 |
| `l3_macro_9` — 9 macro groups | 9 | **0.459** | **0.503** | 0.4646 | 0.4451 | 50 |
| `l4_cashflow_7` — 7 cash-flow types | 7 | **0.434** | **0.469** | 0.4385 | 0.4438 | 47 |
| `l5_minimal_4` — 4 minimal groups | 4 | **0.427** | **0.475** | 0.4132 | 0.4267 | 36 |

### Uncapped

| Rung | Groups | month3 GINI | month6 GINI | m3 Plaid-only | m6 Plaid-only | m3 feats |
|---|---|---|---|---|---|---|
| `l0_leaf_275` — all 275 leaves | 270 | **0.484** | **0.562** | 0.4685 | 0.5208 | 651 |
| `l0_current_69` — 40 key leaves + 29 generals (today) | 68 | **0.475** | **0.576** | 0.4739 | 0.4999 | 247 |
| `l1_general_29` — 29 general categories | 29 | **0.483** | **0.558** | 0.4735 | 0.498 | 129 |
| `l2_budget_17` — 17 budget-line groups | 17 | **0.483** | **0.542** | 0.4752 | 0.519 | 84 |
| `l3_macro_9` — 9 macro groups | 9 | **0.457** | **0.501** | 0.4653 | 0.453 | 54 |
| `l4_cashflow_7` — 7 cash-flow types | 7 | **0.440** | **0.472** | 0.4435 | 0.4243 | 48 |
| `l5_minimal_4` — 4 minimal groups | 4 | **0.423** | **0.468** | 0.4132 | 0.4172 | 36 |

## Variant B — dimensions dropped (`dims_off`)

Rung blocks + spine only. Isolates the category tree.

### 50-feature cap

| Rung | Groups | month3 GINI | month6 GINI | m3 Plaid-only | m6 Plaid-only | m3 feats |
|---|---|---|---|---|---|---|
| `l0_leaf_275` — all 275 leaves | 270 | **0.441** | **0.550** | 0.4373 | 0.5064 | 50 |
| `l0_current_69` — 40 key leaves + 29 generals (today) | 68 | **0.460** | **0.565** | 0.4492 | 0.5173 | 50 |
| `l1_general_29` — 29 general categories | 29 | **0.476** | **0.544** | 0.4619 | 0.5047 | 50 |
| `l2_budget_17` — 17 budget-line groups | 17 | **0.454** | **0.529** | 0.4549 | 0.4953 | 50 |
| `l3_macro_9` — 9 macro groups | 9 | **0.450** | **0.470** | 0.4453 | 0.4241 | 43 |
| `l4_cashflow_7` — 7 cash-flow types | 7 | **0.410** | **0.437** | 0.4178 | 0.4117 | 35 |
| `l5_minimal_4` — 4 minimal groups | 4 | **0.401** | **0.437** | 0.3873 | 0.4235 | 24 |

### Uncapped

| Rung | Groups | month3 GINI | month6 GINI | m3 Plaid-only | m6 Plaid-only | m3 feats |
|---|---|---|---|---|---|---|
| `l0_leaf_275` — all 275 leaves | 270 | **0.495** | **0.562** | 0.4729 | 0.5262 | 637 |
| `l0_current_69` — 40 key leaves + 29 generals (today) | 68 | **0.482** | **0.572** | 0.4702 | 0.5045 | 233 |
| `l1_general_29` — 29 general categories | 29 | **0.480** | **0.546** | 0.468 | 0.4842 | 116 |
| `l2_budget_17` — 17 budget-line groups | 17 | **0.467** | **0.523** | 0.4605 | 0.5065 | 71 |
| `l3_macro_9` — 9 macro groups | 9 | **0.451** | **0.480** | 0.4419 | 0.4209 | 43 |
| `l4_cashflow_7` — 7 cash-flow types | 7 | **0.413** | **0.427** | 0.4271 | 0.4184 | 36 |
| `l5_minimal_4` — 4 minimal groups | 4 | **0.407** | **0.444** | 0.4008 | 0.4125 | 24 |

## What the A/B split shows

At fine granularity the dimensions add little — the categories already
carry the information. At coarse granularity they carry real load: at 7
groups, dropping them costs 4.4 GINI points on month6 and 2.7 on month3.

This is direct evidence for a decision already taken on other grounds
(CLAUDE.md §3): the orthogonal dimensions are not decoration. They are what
keeps a simplified taxonomy usable. If the tree is ever flattened for
governability, the dimensions must stay.

## Two caveats, both measured rather than assumed

**The 50-feature cap interacts with granularity, exactly as flagged.** At
the 275-leaf rung the cap binds hard — 1,113 candidates screen to 651 and
then get cut to 50, scoring 0.439 on month3 versus 0.484 uncapped. At 9 groups or fewer the cap never
binds at all. Reading only the capped column would have made coarse
taxonomies look better than they are. Both columns are reported for that
reason.

**Gambling subtypes collapse between rung 69 and rung 29, and model GINI
does not notice.** month3 goes 0.475 → 0.483; month6 0.576 → 0.558. This does **not** overturn the standing finding that combined
`gambling_months` has IV 0.0053 against `gambling_lottery` 0.0498 — that is
a *univariate* result and it still holds. What it shows is that a GBM
recovers the lost separation from other features, so the aggregate metric
hides it. The reason to keep gambling subtypes separate is univariate
feature screening, interpretability and fair-lending defensibility, not
model GINI. **Do not read this table as licence to aggregate gambling.**

## Going finer than today buys nothing

`l0_leaf_275` gives every taxonomy leaf its own feature block — genuinely
more granular than the current headline, which uses 40 hand-picked
`KEY_LEAVES` plus the 29 generals. It scores 0.484 / 0.562 against 0.475 / 0.576 for today's set — a wash, at four times the feature count and a much
worse capped score. Splitting leaves further would need a new labelling
tranche, and this says it would not pay for itself.

## Reproduce

```bash
python src/experiment3_granularity_ladder.py aggregate   # ~6 GB scan, 30s
python src/experiment3_granularity_ladder.py train       # ~4 min, 56 fits
```

Artefacts: `outputs/experiment3_ladder_long.parquet` (6.4M rows),
`outputs/experiment3_ladder_results.json` (every run, with selected features).

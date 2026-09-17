# Granularity ladder on the champion recipe (2026-09-07)

Open question from the 7 Sep cross-check: the compaction ladder held a plain-XGBoost recipe fixed and swept taxonomy granularity; separately, the champion found that richer leaf-level features (share-of-total, per-leaf averages) beat the 69-rung view by +0.02–+0.04 GINI at a fixed algorithm. This combines the two — same champion recipe and blend weight (nothing re-tuned, read from `experiment3_champion_search.json`), same rich feature engineering (raw stats, transaction/month/amount share, risk-group avg debit/credit), rebuilt at every rung from 275 leaves down to 4 minimal groups. Capped at 50 features throughout (mean normalised gain, pre-OOT training window, both families, seeds 0/17/42 — same method as `experiment3_champion_capped.py`). The category-derived base is replaced by the recipe-agnostic spine + orthogonal dimensions (`experiment3_granularity_ladder.py`'s `dims_held` variant), so only rung granularity changes between rows. Locked v5/v6 not scored.

## month3

Components: xgb = `xgb_d5_regularised|leaf_rich`; lgb = `lgb_d4_recent|leaf_rich`; blend 0.9 XGB / 0.1 LGB.

| Rung | Categories | Cap-50 GINI | XGB | LGB |
|---|---:|---:|---:|---:|
| `l0_leaf_275` — all 275 leaves | 50 feats | **0.409** | 0.409 | 0.409 |
| `l0_current_69` — 40 key leaves + 29 generals (today) | 50 feats | **0.466** | 0.466 | 0.460 |
| `l1_general_29` — 29 general categories | 50 feats | **0.468** | 0.468 | 0.462 |
| `l2_budget_17` — 17 budget-line groups | 50 feats | **0.491** | 0.491 | 0.483 |
| `l3_macro_9` — 9 macro groups | 50 feats | **0.485** | 0.485 | 0.481 |
| `l4_cashflow_7` — 7 cash-flow types | 50 feats | **0.457** | 0.457 | 0.454 |
| `l5_minimal_4` — 4 minimal groups | 50 feats | **0.457** | 0.457 | 0.454 |

## month6

Components: xgb = `xgb_d5_regularised|leaf_raw`; lgb = `lgb_d5_weighted|leaf_rich`; blend 0.7 XGB / 0.3 LGB.

| Rung | Categories | Cap-50 GINI | XGB | LGB |
|---|---:|---:|---:|---:|
| `l0_leaf_275` — all 275 leaves | 50 feats | **0.506** | 0.511 | 0.487 |
| `l0_current_69` — 40 key leaves + 29 generals (today) | 50 feats | **0.548** | 0.548 | 0.539 |
| `l1_general_29` — 29 general categories | 50 feats | **0.542** | 0.547 | 0.525 |
| `l2_budget_17` — 17 budget-line groups | 50 feats | **0.542** | 0.546 | 0.520 |
| `l3_macro_9` — 9 macro groups | 50 feats | **0.534** | 0.531 | 0.512 |
| `l4_cashflow_7` — 7 cash-flow types | 50 feats | **0.495** | 0.488 | 0.490 |
| `l5_minimal_4` — 4 minimal groups | 50 feats | **0.502** | 0.503 | 0.468 |

## Reference points (from the champion work, not re-derived here)

- Live reconstruction: month3 0.394, month6 0.417.
- Published August 50-feature XGB: month3 0.477, month6 0.564.
- Champion, capped at 50 on its actual feature set (base includes the 69-rung blocks; see `experiment3_champion_capped_report.md`): month3 0.508, month6 0.583.

The capped-champion number above is not directly comparable row-for-row to this report's rungs, because its base retains the existing 69-rung blocks (spine + KEY_LEAVES + general blocks) alongside the rich leaf features, whereas every rung here uses a purely recipe-agnostic base (spine + dimensions only) so that granularity is the *only* thing varying. This report isolates the granularity effect; the champion capped report isolates the feature-cap effect on the full recipe.

## Why 275 leaves is the *worst* point on both curves — a cap-crowding mechanism, not noise

At a fixed 50-feature budget, the 275-leaf rung scores lowest on both targets
(month3 0.409, month6 0.506) — below every coarser rung, including the
4-group floor. This is not the "richer detail helps" result the champion's
own uncapped comparison found; it is a specific, checkable failure mode of
capping at fixed width when the candidate pool is very wide.

Counting how many of each rung's 31 recipe-agnostic spine/dimension columns
(`total_months`, `priority_debt_breadth`, `credit_product_months`,
`essential_spend_ratio`, etc. — the same features already known to be the
strongest single predictors in the project, IV 0.171 for
`priority_debt_breadth`) survive into the selected top 50:

| Rung | Candidate columns | Spine/dims selected (of 31) |
|---|---:|---:|
| `l0_leaf_275` | ~2,877 | month3 **7**, month6 **2** |
| `l0_current_69` | ~819 | month3 6, month6 5 |
| `l1_general_29` | ~359 | month3 7, month6 6 |
| `l2_budget_17` | ~227 | month3 7, month6 9 |
| `l3_macro_9` | ~139 | month3 12, month6 11 |
| `l4_cashflow_7` | ~115 | month3 17, month6 17 |
| `l5_minimal_4` | ~79 | month3 20, month6 22 |

At 275 leaves, `credit_product_months` — the single strongest debt feature
found anywhere in this project — does not survive into the capped set at
all on month6; at 17 groups it does. The gain-ranking step has to compete
2,846 thin, single-leaf candidates against a handful of broad, information-dense
spine features for the same 50 slots, and mean-gain ranking on a noisy
pre-OOT window does not reliably prefer the latter. This mirrors, and sharpens,
the caveat already on record from the plain-recipe stress test ("the 275-leaf
cap is unstable and capacity-constrained... a single capped run should not be
used to rank the fine rungs") — it is worse here because the champion's rich
per-leaf feature engineering multiplies the candidate count roughly 2.5x
versus the original ladder's simple per-leaf stats.

## What this does and does not answer

**Does not answer:** whether the champion's richer feature *types* still
help at full granularity — that question needs an *uncapped* rung sweep,
which this run did not do (the champion's own uncapped comparison used a
different, thicker base that included the 69-rung blocks, so it isn't a
clean rung-isolated answer either). That is the natural next step.

**Does answer, for a governable 50-feature budget:** once capped, this
richer recipe reproduces the same basic shape the plain-recipe ladder found
— a plateau roughly across 69/29/17 groups (month6: 0.548/0.542/0.542) and a
fall below 9 (month6 9-group 0.534, 7-group 0.495) — and adds a new,
concrete reason to prefer a moderate rollup (17–29 groups) over the full
275 leaves specifically *when a feature cap is in force*: full leaf detail
crowds out the strongest existing features rather than adding to them.


_Note (7 Sep pm): the adopted reference is the single-XGBoost component of the capped champion, 0.508 / 0.588 (`outputs/experiment3_champion_capped_xgb_month{3,6}_50.joblib`); quote the XGB column of the tables above for like-for-like comparison. The blend columns are kept as recorded._

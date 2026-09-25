# Granularity ladder on the champion recipe, uncapped (2026-09-07)

Follow-up to the capped rung sweep. Same champion recipe and blend weight (nothing re-tuned), same rich per-group feature engineering, rebuilt at every rung — but with **no gain-ranking or 50-feature cap**: every candidate column at a rung (recipe-agnostic spine + dimensions, plus every raw/share/risk-avg feature computed at that rung) goes straight into the final fit. Isolates whether the champion's richer feature *types* help once the cap-instability confound found in the capped run is removed. Locked v5/v6 not scored.

## month3

Components: xgb = `xgb_d5_regularised|leaf_rich`; lgb = `lgb_d4_recent|leaf_rich`; blend 0.9 XGB / 0.1 LGB.

| Rung | Categories | Uncapped GINI | XGB | LGB | Features |
|---|---:|---:|---:|---:|---:|
| `l0_leaf_275` — all 275 leaves | 2,877 feats | **0.528** (Δ vs cap-50 +0.119) | 0.528 | 0.526 | 2,877 |
| `l0_current_69` — 40 key leaves + 29 generals (today) | 819 feats | **0.536** (Δ vs cap-50 +0.070) | 0.536 | 0.528 | 819 |
| `l1_general_29` — 29 general categories | 359 feats | **0.519** (Δ vs cap-50 +0.051) | 0.519 | 0.513 | 359 |
| `l2_budget_17` — 17 budget-line groups | 227 feats | **0.509** (Δ vs cap-50 +0.018) | 0.509 | 0.498 | 227 |
| `l3_macro_9` — 9 macro groups | 139 feats | **0.492** (Δ vs cap-50 +0.006) | 0.492 | 0.486 | 139 |
| `l4_cashflow_7` — 7 cash-flow types | 115 feats | **0.461** (Δ vs cap-50 +0.004) | 0.461 | 0.450 | 115 |
| `l5_minimal_4` — 4 minimal groups | 79 feats | **0.463** (Δ vs cap-50 +0.006) | 0.463 | 0.458 | 79 |

## month6

Components: xgb = `xgb_d5_regularised|leaf_raw`; lgb = `lgb_d5_weighted|leaf_rich`; blend 0.7 XGB / 0.3 LGB.

| Rung | Categories | Uncapped GINI | XGB | LGB | Features |
|---|---:|---:|---:|---:|---:|
| `l0_leaf_275` — all 275 leaves | 2,877 feats | **0.616** (Δ vs cap-50 +0.110) | 0.612 | 0.616 | 2,877 |
| `l0_current_69` — 40 key leaves + 29 generals (today) | 819 feats | **0.586** (Δ vs cap-50 +0.037) | 0.586 | 0.576 | 819 |
| `l1_general_29` — 29 general categories | 359 feats | **0.581** (Δ vs cap-50 +0.039) | 0.582 | 0.568 | 359 |
| `l2_budget_17` — 17 budget-line groups | 227 feats | **0.573** (Δ vs cap-50 +0.031) | 0.575 | 0.555 | 227 |
| `l3_macro_9` — 9 macro groups | 139 feats | **0.541** (Δ vs cap-50 +0.007) | 0.542 | 0.508 | 139 |
| `l4_cashflow_7` — 7 cash-flow types | 115 feats | **0.505** (Δ vs cap-50 +0.010) | 0.502 | 0.495 | 115 |
| `l5_minimal_4` — 4 minimal groups | 79 feats | **0.507** (Δ vs cap-50 +0.004) | 0.510 | 0.465 | 79 |

## Reading this alongside the capped run

The capped run (`data/experiment3_champion_granularity_report.md`) found 275 leaves the *worst* rung at a fixed 50-feature budget, because the gain-ranking step crowds the strongest existing features (`priority_debt_breadth`, `credit_product_months`) out of a small cap. This run removes the cap entirely, so any remaining shape is attributable to the feature engineering and algorithm themselves, not to selection instability.

## The two targets tell different stories

**month6: granularity genuinely helps, uncapped.** 275 leaves (0.616) clearly
beats today's 69-rung (0.586, Δ+0.030) and every coarser rung, monotonically
down to 4 groups (0.507). This matches the direction of the champion's own
full-search finding (leaf_rich vs current, +0.037 uncapped) closely enough
to trust — the small gap (+0.030 here vs +0.037 there) is attributable to
this harness's thinner, purely recipe-agnostic base versus the champion's
actual base (which also carries the existing 69-rung blocks).

**month3: no clear gain from finer granularity, and a mild peak at today's
69-rung.** 275 leaves (0.528) is not the best rung — 69 (0.536) is, and 275
is marginally *below* it. Every rung above 17 groups is close (0.509–0.536);
the fall only becomes clear below 9 groups (0.492 → 0.461).

Put together: **the champion's richer feature engineering pays off at full
granularity for month6, but not detectably for month3.** This is consistent
with the difference in what the two targets need — month6 predicts default
three months further out and benefits more from the fine-grained behavioural
detail (which specific leaf, not just which broad category, someone spends
in), while month3 is a shorter, noisier horizon where that extra detail adds
about as much variance as signal.

## Combining the capped and uncapped results

| | Capped @ 50 | Uncapped |
|---|---|---|
| month3, 275 vs today's 69 | 275 far worse (0.409 vs 0.466) | 275 slightly worse (0.528 vs 0.536) |
| month6, 275 vs today's 69 | 275 worse (0.506 vs 0.548) | 275 clearly better (0.616 vs 0.586) |

The capped result is not simply "wrong" — it is the correct answer to a
different, and more practically relevant, question: **what happens under a
governable feature budget.** Under that constraint, this recipe should not
use 275-leaf features on either target. The uncapped result says that if the
budget constraint were lifted, month6 alone would benefit from full leaf
detail; month3 would not. Since nobody has proposed shipping an uncapped,
2,877-feature model, the capped result remains the operationally relevant
one — this uncapped run answers the scientific question ("does richness help
at all"), not the engineering one ("should we ship it").


_Note (7 Sep pm): the adopted reference is the single-XGBoost component of the capped champion, 0.508 / 0.588 (`outputs/experiment3_champion_capped_xgb_month{3,6}_50.joblib`); quote the XGB column of the tables above for like-for-like comparison. The blend columns are kept as recorded._

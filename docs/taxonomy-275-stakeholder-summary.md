# Why Raylo should keep the 275-leaf transaction taxonomy

## Executive recommendation

**Keep 275 leaves as Raylo's governed production taxonomy.** Let each risk
model consume validated rollups or selected leaves, and keep proposed finer
categories in a shadow field until they show stable incremental value.

The current evidence supports both sides of that decision:

- collapsing too far loses information;
- a corrected, controlled pilot found no risk-GINI benefit from moving from
  275 to 287 leaves.

This is not a claim that 275 is a mathematical optimum forever. It is the
best-supported production boundary with today's data.

## The decision in one table

| Question | Evidence | Decision |
|---|---|---|
| Does the Raylo taxonomy/feature approach beat the live model? | Corrected as-of capped model: **0.477 / 0.562** month-3/month-6 GINI. Like-for-like Plaid-only: **0.445 / 0.504** vs full-refit live **0.382 / 0.385**. | Keep the Raylo-owned categorisation and feature layer. |
| Can the source taxonomy be rolled up? | Historical three-seed sensitivity found 275, current 69 and 29 statistically indistinguishable; 17 was close, while 9 and below degraded. This ladder predates the 2 Sep as-of rebuild and is directional, not a promotion result. | Keep rollups as model choices; do not delete source detail. |
| Do three plausible splits beyond 275 help? | Corrected as-of rolling test: lean split **−0.0045 / −0.0068**; rich split **−0.0020 / −0.0111** vs exact parent controls. Every combined 95% CI included zero. | Do not expand to 287 on current evidence. |
| Is the categorisation itself reliable enough to govern? | Current 2,004-row pipeline audit: **81.8% leaf / 87.3% general**. The fresh de-leaked risk-category classifier bar is **62.7%**, so risk leaves still require explicit controls. | Retain detailed monitoring and category-level risk gates. |

## The direct test of going beyond 275

Three high-support parents were split in shadow only:

- `streaming` into video subscription, audio/books, transactional video,
  sports and fallback;
- `marketplace_general` into resale/auction, Amazon, social commerce,
  low-cost import and fallback;
- `payment_intermediary` into wallet, collection network, marketplace escrow,
  merchant processor and fallback.

That creates 15 mutually exclusive buckets, or 12 net extra leaves: a simulated
275 → 287 expansion. The rules used only merchant and description text and
were frozen before outcomes were inspected. The existing production leaf was
left untouched.

The crucial control was to give both models the exact totals for the three
existing parents. Only the challenger received composition inside each parent.
This distinguishes a true split benefit from merely exposing an existing leaf.

### Primary rolling Plaid validation

| Target | Current | + exact parent controls | + lean split | + rich split | Lean delta vs parent (95% CI) | Rich delta vs parent (95% CI) |
|---|---:|---:|---:|---:|---:|---:|
| Month 3 | 0.518 | 0.513 | 0.508 | 0.511 | **−0.0045** (−0.0103 to +0.0010) | **−0.0020** (−0.0080 to +0.0034) |
| Month 6 | 0.569 | 0.571 | 0.564 | 0.560 | **−0.0068** (−0.0206 to +0.0067) | **−0.0111** (−0.0248 to +0.0023) |

No combined split improved pooled rolling GINI. One-parent-at-a-time deltas
were also non-positive on both horizons. Payment-intermediary alone produced a
small, statistically clear month-3 loss: **−0.0061** (95% CI −0.0117 to
−0.0005).

The already-used development OOT was essentially flat: lean **−0.0013 / +0.0024**
and rich **−0.0006 / +0.0003** for month 3 / month 6, all intervals spanning
zero. It is secondary confirmation, not a fresh promotion test.

## This was not a low-support failure

The affected shadow features appeared in **54,369 of 64,209** modelling rows.
The largest child groups had substantial transaction volume:

| Parent | Largest child | Transactions | Share of parent |
|---|---|---:|---:|
| Marketplace | Resale/auction | 307,331 | 55.9% |
| Payment intermediary | Digital wallet | 220,363 | 76.7% |
| Streaming | Video subscription | 234,123 | 72.2% |

All child counts and amounts reconciled exactly to the current parents. There
were 15 frozen child buckets; only sports streaming was genuinely thin at 946
transactions. A 51-feature lean composition overlay was tested after the rich
156-feature overlay to rule out the obvious overfitting objection. It did not
recover a rolling gain.

## Why keep 275 rather than collapse the source taxonomy?

1. **Detail is reversible; deletion is not.** A detailed leaf can be rolled up
   at feature-build time. A stored general label cannot be split later without
   recategorising history.
2. **Coarse model GINI can hide category-specific risk.** The historical
   analysis found lottery IV **0.0498** versus combined gambling-months IV
   **0.0053**. Governance still needs subtype monitoring even where a model can
   tolerate aggregation.
3. **Different consumers need different rollups.** Credit risk, affordability,
   operations and customer support need not share one destructive aggregation.
4. **The corrected model result remains positive.** On the as-of rebuild, the
   Plaid-only taxonomy model remains ahead of the full-refit live reconstruction
   by **+0.063 month 3** and **+0.119 month 6** GINI.

## What would justify adding leaves later?

Use the same shadow-overlay approach. A proposed split should meet all of the
following before production adoption:

1. semantic definitions and precedence frozen before outcome inspection;
2. sufficient volume in every child and an explicit parent fallback;
3. human-labelled child precision/recall, especially for risk-sensitive leaves;
4. positive rolling incremental GINI versus an exact parent control, with the
   paired interval excluding zero on the primary horizon;
5. stability across time, provider, seed and protected/fairness slices;
6. one untouched future outcome vintage for the final promotion decision.

This process does **not** require redoing the whole 275-leaf categorisation.
Only transactions in the selected parent need a shadow child assignment; the
existing parent remains valid for all historical labels and fallbacks.

## Stakeholder-safe wording

> Raylo should keep the 275-leaf taxonomy as its governed source of truth. The
> corrected risk experiment still outperforms the live reconstruction, and
> earlier granularity tests show that collapsing too far destroys signal. We
> also tested a targeted expansion to 287 leaves on the corrected cohort. It
> produced no stable incremental GINI after controlling for the existing
> parent leaves, so there is currently no evidence-based case for adding those
> categories. Future splits can be tested cheaply in shadow without relabelling
> the full history.

## Evidence base

- `data/experiment3_subleaf_pilot_report.md`
- `outputs/experiment3_subleaf_results.json`
- `taxonomy/experimental_subleaf_pilot.csv`
- `data/experiment3_xgb_report.md` (2 Sep as-of addendum)
- `data/experiment3_granularity_stress_test_report.md` (historical pre-as-of sensitivity)
- `data/waterfall_pipeline_report.md`
- `data/classifier_v6_deleaked_report.md`

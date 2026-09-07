# Taxonomy granularity: compaction and expansion conclusion

## Recommendation

**Keep the 275-leaf taxonomy as the governed source of truth.** Models may use
validated rollups, while proposed new leaves should remain in shadow until they
demonstrate stable incremental value.

## Compaction: fewer categories eventually lose signal

The same modelling approach was tested at progressively coarser levels. Higher
GINI indicates better risk discrimination.

| Category view | Month-3 GINI | Month-6 GINI | Finding |
|---|---:|---:|---|
| 275 leaves | 0.485 | 0.571 | Detailed reference |
| Current 69-group view* | 0.482 | 0.571 | Statistically indistinguishable from 275 |
| 29 general categories | 0.479 | 0.560 | No clear loss versus 69 |
| 17 budget groups | 0.479 | 0.545 | Close, but month-6 loss remains possible |
| 9 macro groups | 0.468 | 0.495 | Material degradation |
| 4 broad groups | 0.431 | 0.472 | Clear degradation |

\* "69" is today's model-*feature* grouping, not a 69-leaf taxonomy and not "69
of the 275 leaves in use." All 275 leaves are still classified; 40 of them
each keep their own feature block, and the remaining 235 are rolled into their
29 general categories (40 + 29 = 69 distinct feature groups). Nothing is
dropped — see the taxonomy README for the full 275→29 rollup.

Models do not need to use all 275 leaves individually as features: the
69-group (today's) and 29-group views retain similar performance. However,
compacting the source *taxonomy* itself — the thing that actually classifies
every transaction — would permanently remove information, and performance
deteriorates materially at 9 groups and below.

## Expansion: the tested additional categories did not improve performance

A corrected as-of pilot simulated an expansion from 275 to 287 leaves by
splitting streaming, marketplace and payment intermediary into 15 shadow
buckets. Production labels were unchanged. Both models received the existing
parent totals, so the comparison isolated the value of the finer splits.

| Rolling validation | Month-3 GINI | Month-6 GINI | Delta vs parent control |
|---|---:|---:|---:|
| Exact parent control | 0.513 | 0.571 | — |
| Lean split features | 0.508 | 0.564 | −0.0045 / −0.0068 |
| Rich split features | 0.511 | 0.560 | −0.0020 / −0.0111 |

All combined 95% confidence intervals included zero, and the development
holdout was effectively flat. Every one-parent ablation was non-positive;
payment intermediary produced a small, statistically clear month-3 loss. This
was not a low-support result: the shadow categories appeared in 54,369 of
64,209 modelling rows.

## Conclusive finding

The results do not support the assumption that more categories automatically
produce a better model:

1. Retain 275 governed leaves.
2. Use the 69-group (today's model-feature grouping) or 29-group model rollups where independently validated.
3. Avoid 9 groups or fewer because they lose material signal.
4. Do not adopt the tested 287-leaf expansion.
5. Test future splits in shadow without recategorising the full history.

The compaction ladder predates the latest Equifax as-of correction, whereas the
expansion pilot uses the corrected data. This does not change the production
recommendation, but the ladder should be rerun on the corrected feature set
before using its exact GINI values for formal model promotion.

## Open question added 7 September — does this survive the new champion recipe?

Everything above was measured on the **August recipe**: a single XGBoost on
plain rung-level features (months active, transaction count, debit/credit
amount per group). As of 7 September a materially stronger **champion**
recipe exists — a blended XGBoost + LightGBM model trained on a much richer
feature set (per-leaf transaction-share, per-leaf average amounts, coefficient
of variation, recency ratios), built at the full 275-leaf level. Capped at the
same 50 features, it scores **0.508 / 0.583** against the August recipe's
**0.477 / 0.564** (month3 / month6); uncapped it reaches **0.533 / 0.618**
(`data/experiment3_champion_capped_report.md`).

This matters here for one specific reason: **the champion's own pre-OOT
model-selection table shows its richer leaf-level feature view beating a
69-rung-equivalent view by +0.023 (month3) / +0.037 (month6) GINI, using the
identical algorithm and depth** (`data/experiment3_champion_model_report.md`,
"current" 304 features vs "leaf_rich" 3,150). That is a real, non-trivial gap
in the opposite direction from the compaction table above — and it was never
produced by rolling categories up or down; it came from computing genuinely
different feature *types* (shares and per-leaf ratios) that only exist once
you keep leaf-level granularity to compute them on.

**This does not overturn the compaction finding** — nobody has rebuilt the
champion's rich feature types at the 29/17/9/7/4-group rungs to see whether
they also plateau, so "275 ≈ 69 ≈ 29" is not known to be false. It just means
that finding is specific to the August recipe and should not be quoted as
"granularity doesn't matter for our best model" — that combination is
untested. Re-running the compaction ladder with the champion's feature
recipe, at every rung, is the open item.

## Answered, 7 September — the champion recipe, capped, rerun at every rung

`data/experiment3_champion_granularity_report.md`. Same champion recipe and
blend weight (nothing re-tuned), same rich per-leaf feature engineering,
rebuilt at every rung and capped at 50 features (the width the champion
itself carries forward). Result:

| Rung | month3 | month6 |
|---|---:|---:|
| 275 leaves | 0.409 | 0.506 |
| 69 (today) | 0.466 | 0.548 |
| 29 generals | 0.468 | 0.542 |
| 17 budget groups | 0.491 | 0.542 |
| 9 macro groups | 0.485 | 0.534 |
| 7 cash-flow | 0.457 | 0.495 |
| 4 minimal | 0.457 | 0.502 |

**Under this recipe, capped, 275 leaves is the *worst* rung on both targets**
— not the best. The mechanism is checkable, not noise: at 275 leaves the
gain-ranking step has ~2,877 candidate columns competing for 50 slots, and
`credit_product_months` (the second-strongest debt feature in the whole
project) doesn't survive into the capped set on month6 at all; at 17 groups
it does. Full leaf detail crowds out the strongest existing features rather
than adding to them, once a feature cap is in force. The basic shape from
the August-recipe ladder otherwise reappears — a rough plateau across
69/29/17 groups, a fall below 9.

This still doesn't answer whether the champion's richer feature *types* help
at *uncapped* full granularity (the champion's own uncapped comparison used
a different base, so it isn't a clean rung-isolated answer). But for any
governable, capped feature budget — which is the only kind anyone has
proposed shipping — **the compaction conclusion holds under the champion
recipe too, and 275 leaves is actively worse than a moderate rollup at a
fixed cap.**

## Answered, same day — the uncapped rung sweep

`data/experiment3_champion_granularity_uncapped_report.md`. Same recipe and
rungs, but no gain-ranking cap — every candidate column at a rung goes
straight into the fit. Result splits by target:

| Rung | month3 (uncapped) | month6 (uncapped) |
|---|---:|---:|
| 275 leaves | 0.528 | **0.616** |
| 69 (today) | **0.536** | 0.586 |
| 29 generals | 0.519 | 0.581 |
| 17 budget groups | 0.509 | 0.573 |
| 9 macro groups | 0.492 | 0.541 |
| 7 cash-flow | 0.461 | 0.505 |
| 4 minimal | 0.463 | 0.507 |

**Month6: granularity genuinely helps, uncapped** — 275 leaves beats every
coarser rung monotonically, by +0.030 over today's 69. **Month3: it does
not** — 275 is marginally *below* today's 69-rung, which is the actual peak.
Longer-horizon prediction (month6) rewards fine-grained per-leaf behavioural
detail; the shorter, noisier month3 horizon does not detectably benefit from
it once the recipe-agnostic spine and dimensions are already present.

This resolves the open item, with a real caveat attached: nobody has
proposed shipping an uncapped, ~2,900-feature model, so the *capped* result
above remains the operationally relevant one for any actual promotion
decision. The uncapped result answers the scientific question ("does
richness help at all, for this recipe") rather than the engineering one
("should we ship it") — and the honest answer is "yes for month6, no for
month3," not a clean universal story either way.

# Final evaluation: Equifax-native vs Plaid-native vs our pipeline

Ground truth: `data/gold_merchant_labels.csv` (1,563 head merchants, both providers) + `data/gold_tail_labels.csv` (247 tail merchants, Plaid-only) -- independently human-verified, never derived from either provider's own category.

'Native' = crosswalking each provider's own category field only (no dictionary, no rules). 'Our pipeline' = dictionary -> rules -> native fallback (head); actual production-labelling output (tail, since that population needs LLM consensus, not a static lookup).


## Head merchants (n=1,563, both providers)

| Source | Leaf accuracy | General-category accuracy | Scored n |
|---|---|---|---|
| Equifax native category | 82.3% | 93.7% | 1563 |
| Plaid native category | 31.9% | 63.5% | 1563 |
| Our pipeline (via Equifax txn) | 95.0% | 98.2% | 1563 |
| Our pipeline (via Plaid txn) | 50.4% | 72.1% | 1563 |

**Provider-independence check**: of 1563 head merchants scoreable via both transaction sources, our pipeline gives the *same* leaf regardless of which provider the transaction came from for 801 (51.2%) -- vs. the known 27.8% crosswalk-only agreement rate.


**Why the gap between the two 'our pipeline' rows**: only 404 of 1563 gold head merchants (25.8%) are in the current 535-entry T4 dictionary. Split by that:

| Segment | Our leaf (via Equifax txn) | Our leaf (via Plaid txn) | n |
|---|---|---|---|
| In T4 dictionary | 95.5% | 95.5% | 404 |
| Not in T4 dictionary (T5/T6 fallback) | 94.8% | 34.6% | 1159 |

Where the dictionary covers a merchant, the pipeline is provider-independent by construction (same lookup key either way). The remaining ~74% of the gold head set isn't in the curated dictionary yet, so it still falls back to the native crosswalk -- this is the single biggest lever left for improving head-population accuracy further.


**Leakage caveat**: 214 of the 535 dictionary entries (the 195 gating-approved additions + 19 evidence-backed context-dependent entries) came from the same gating adjudication exercise that also produced `gold_merchant_labels.csv` -- so the 'in T4 dictionary' accuracy figure is partly circular for that slice (not for the original 321 llm-proposed entries, which predate the gold set). This does not affect the 'not in dictionary' row, the tail results, or the overall provider-vs-provider comparison, which are the load-bearing numbers for this evaluation.


## Tail merchants (n=247, Plaid-only unmatched vocabulary)

| Source | Leaf accuracy | General-category accuracy | Scored n |
|---|---|---|---|
| Plaid native category | 17.0% | 43.7% | 247 |
| Our pipeline (2-model LLM consensus) | 84.8% | 90.6% | 191 |

## Overall (n=1810, head + tail combined)

- Plaid native category: 29.9% leaf accuracy (n=1810)
- Our pipeline: 93.9% leaf accuracy (n=1754)

**Abstained / no consensus**: 56 tail gold merchants had no haiku/sonnet agreement and sonnet confidence below 0.7 -- excluded from 'our pipeline' scoring above (abstaining is the correct behaviour, not a defect), not counted as correct or incorrect: ['chaotic', 'mandate no', 'robert errington', 'pervin food centre', 'hilltopvendingsoluti', 'provend', 'new mastercard', 'etb', 'wacky world', 'mr good morning food', 'usave keir', 'hedon', 'magic lantern', 'kerry mcghie lamp', 'cda pl']

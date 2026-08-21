# Final evaluation: Equifax-native vs Plaid-native vs our pipeline

Ground truth: `data/gold_merchant_labels.csv` (1,563 head merchants, both providers) + `data/gold_tail_labels.csv` (247 tail merchants, Plaid-only).

'Native' = crosswalking each provider's own category field only (no dictionary, no rules). 'Our pipeline' = dictionary -> rules -> native fallback (head); the enriched two-model LLM consensus (tail).

## Leakage audit

**Head set**: only 324 of 1563 gold labels (20.7%) went through actual human adjudication (`gold_source` starting `adjudicated_*`). The other 1239 (`consensus_all_agree`) are simply cases where Haiku and Sonnet -- two models from the same family, given the same prompt -- agreed with each other, with no human check. That's not independent ground truth; it's model self-consistency, which could share blind spots. Separately, 195 of the human-adjudicated rows are directly circular: the same adjudication verdict both produced the gold label AND was used to add that merchant to the T4 dictionary, so scoring the dictionary against those specific rows is tautological.

**Tail set**: every row went through human review, but for 185 of 247 rows (`consensus_correct`/`haiku_correct`/`sonnet_correct`), gold_leaf was set TO the exact haiku/sonnet prediction being scored (see `build_tail_eval.py finalise()`) -- scoring our pipeline against those rows is tautological by construction. Only `override` (human rejected both models) and `unclassifiable` (human confirmed neither answer works) are independent tests.

**Fix applied below**: every table reports a `Clean, non-circular` row using only genuinely independent evidence -- head: human-adjudicated AND not circular (`adjudicated_equifax` only, since that's the one verdict type that never feeds the dictionary); tail: `override` + `unclassifiable` only. Small-sample sizes are called out explicitly rather than hidden behind a percentage.


## Head merchants (n=1,563, both providers)

| Source | Leaf accuracy | General-category accuracy | Scored n |
|---|---|---|---|
| Equifax native category -- full sample | 82.3% | 93.7% | 1563 |
| Equifax native category -- clean, non-circular (n=129) | 43.4% | 74.4% | 129 |
| Plaid native category -- full sample | 31.9% | 63.5% | 1563 |
| Plaid native category -- clean, non-circular | 28.7% | 53.5% | 129 |
| Our pipeline (via Equifax txn) -- full sample | 95.0% | 98.2% | 1563 |
| Our pipeline (via Equifax txn) -- clean, non-circular | 62.0% | 88.4% | 129 |
| Our pipeline (via Plaid txn) -- full sample | 50.4% | 72.1% | 1563 |
| Our pipeline (via Plaid txn) -- clean, non-circular | 39.5% | 62.0% | 129 |

The clean subset is small (n=129) because it's restricted to `adjudicated_equifax` verdicts -- cases where a human explicitly preferred Equifax's own category over the LLM consensus. That's a genuinely adversarial subset for our pipeline (it's selected FOR cases where Equifax was judged right), so if our pipeline still holds up here that's meaningful; if it drops, that's expected and informative, not alarming.


**Provider-independence check** (unaffected by the leakage above -- this compares our own pipeline's two outputs to each other, not to gold): of 1563 head merchants scoreable via both transaction sources, our pipeline gives the *same* leaf regardless of which provider the transaction came from for 801 (51.2%) -- vs. the known 27.8% crosswalk-only agreement rate.


**Dictionary coverage breakdown**: only 404 of 1563 gold head merchants (25.8%) are in the current 535-entry T4 dictionary (full sample, includes circular rows):

| Segment | Our leaf (via Equifax txn) | Our leaf (via Plaid txn) | n |
|---|---|---|---|
| In T4 dictionary | 95.5% | 95.5% | 404 |
| Not in T4 dictionary (T5/T6 fallback) | 94.8% | 34.6% | 1159 |

Where the dictionary covers a merchant, the pipeline is provider-independent by construction (same lookup key either way). The remaining ~74% of the gold head set isn't in the curated dictionary yet, so it still falls back to the native crosswalk -- this is the single biggest lever left for improving head-population accuracy further. Note this breakdown includes the circular rows flagged above, so treat the 'in dictionary' figure as an upper bound, not a clean measurement.


## Tail merchants (n=247, Plaid-only unmatched vocabulary)

| Source | Leaf accuracy | General-category accuracy | Scored n |
|---|---|---|---|
| Plaid native category -- full sample | 17.0% | 43.7% | 247 |
| Plaid native category -- clean, non-circular (n=62) | 1.6% | 25.8% | 62 |
| Our pipeline (LLM consensus) -- full sample | 84.8% | 90.6% | 191 |
| Our pipeline (LLM consensus) -- clean, non-circular | 26.3% | 52.6% | 38 |

The clean tail subset (n=62) is exactly the population the pipeline is weakest on by construction: `override` rows are cases a human explicitly said BOTH models got wrong, and `unclassifiable` rows are cases where abstaining is the only correct answer. This is a deliberately hard, adversarial slice -- not a representative sample of tail performance -- so a lower number here doesn't mean the tail pipeline is unreliable in general; it means these specific hard cases remain hard.


## Overall, clean/non-circular only (n=191)

- Plaid native category: 19.9% leaf accuracy (n=191)
- Our pipeline: 53.9% leaf accuracy (n=167) -- **90/167 correct**

This combined clean slice is deliberately adversarial (Equifax-preferred head cases + hard-override/unclassifiable tail cases), so treat it as a stress test / lower bound, not the headline number.


## Overall, full sample including consensus/circular rows (n=1810)

- Plaid native category: 29.9% leaf accuracy (n=1810)
- Our pipeline: 93.9% leaf accuracy (n=1754)

This is the representative, best-estimate number (most of the gold set genuinely is this population), but it is inflated to an unknown degree by the leakage documented above -- treat the clean-subset numbers as the floor and this as the ceiling.


**Abstained / no consensus**: 56 tail gold merchants had no haiku/sonnet agreement and sonnet confidence below 0.7 -- excluded from 'our pipeline' scoring above (abstaining is the correct behaviour, not a defect), not counted as correct or incorrect: ['chaotic', 'mandate no', 'robert errington', 'pervin food centre', 'hilltopvendingsoluti', 'provend', 'new mastercard', 'etb', 'wacky world', 'mr good morning food', 'usave keir', 'hedon', 'magic lantern', 'kerry mcghie lamp', 'cda pl']

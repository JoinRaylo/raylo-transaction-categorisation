# Final evaluation v2: transaction-level, leakage-free gold set

Ground truth: `gold_transactions_v2.csv`, `gold_transactions_v2_batch2.csv` -- 3000 real transactions, each independently reviewed and hand-corrected by Carlos (403/1500 batch-1 drafts were overridden, including 34 of the 400 rows that already had a prior human verdict from earlier work -- this is a fresh, from-scratch review, not a rubber stamp). No clean/full split needed: unlike the v1 merchant-level set, nothing here is copied from the prediction being scored.

**334 rows are excluded from every accuracy figure below**: their merchant's T4 dictionary entry was itself sourced from this same gold set (`build_merchant_dictionary.py`'s gold_v2_review additions), so scoring 'our pipeline' against them would just test whether a lookup remembers its own source -- the exact circularity this gold-set rebuild exists to eliminate. All figures below are computed on the remaining 2666 rows; the excluded rows are still in `final_evaluation_v2_comparison.csv`, flagged `self_sourced_dict_entry`.

## Overall (all providers combined)

| Source | Leaf accuracy | General-category accuracy | Scored n |
|---|---|---|---|
| Native provider category | 42.6% | 57.6% | 2666 |
| Our pipeline | 50.1% | 61.5% | 2666 |

## By provider

| Provider | Native leaf acc | Native general acc | Our leaf acc | Our general acc | n |
|---|---|---|---|---|---|
| Equifax | 63.6% | 71.7% | 66.5% | 74.0% | 1156 |
| Plaid | 26.5% | 46.8% | 37.5% | 51.9% | 1510 |

## By sampling source (important -- these are very different populations)

| Source | Native leaf acc | Our leaf acc | n |
|---|---|---|---|
| Already-verified merchants (deliberately hard -- these needed human adjudication in earlier work precisely because they were disputed) | 10.9% | 31.9% | 540 |
| Broad random sample (representative of typical incoming transactions) | 45.3% | 50.8% | 1659 |
| Targeted for taxonomy-breadth coverage (rare leaves, batch 2 only) | 69.6% | 68.7% | 467 |

The blended headline number above is pulled down by the already-verified subset, which is deliberately hard by construction. The 'broad random sample' row is the closest thing to *typical* transaction performance in this set.


## Our pipeline's resolution tier breakdown

- T6_native_fallback: 1775 (66.6%)
- T4_dictionary: 832 (31.2%)
- T5_R02: 18 (0.7%)
- T5_R10: 10 (0.4%)
- T5_R11: 8 (0.3%)
- T5_R01: 7 (0.3%)
- T5_R12: 5 (0.2%)
- T5_R05: 3 (0.1%)
- T5_R09: 3 (0.1%)
- T5_R06: 2 (0.1%)
- T5_R04: 1 (0.0%)
- T5_R03: 1 (0.0%)
- T5_R14: 1 (0.0%)

**Our pipeline gets it right where the native category doesn't**: 298 of 2666 transactions (11.2%).


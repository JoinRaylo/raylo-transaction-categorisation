# Final evaluation v2: transaction-level, leakage-free gold set

Ground truth: `gold_transactions_v2.csv` -- 1500 real transactions, each independently reviewed and hand-corrected by Carlos (403/1500 batch-1 drafts were overridden, including 34 of the 400 rows that already had a prior human verdict from earlier work -- this is a fresh, from-scratch review, not a rubber stamp). No clean/full split needed: unlike the v1 merchant-level set, nothing here is copied from the prediction being scored.

## Overall (all providers combined)

| Source | Leaf accuracy | General-category accuracy | Scored n |
|---|---|---|---|
| Native provider category | 32.1% | 47.9% | 1500 |
| Our pipeline | 40.9% | 52.6% | 1500 |

## By provider

| Provider | Native leaf acc | Native general acc | Our leaf acc | Our general acc | n |
|---|---|---|---|---|---|
| Equifax | 51.9% | 59.0% | 59.8% | 66.0% | 420 |
| Plaid | 24.4% | 43.5% | 33.5% | 47.4% | 1080 |

## By sampling source (important -- these are very different populations)

| Source | Native leaf acc | Our leaf acc | n |
|---|---|---|---|
| Already-verified merchants (deliberately hard -- these needed human adjudication in earlier work precisely because they were disputed) | 9.5% | 23.8% | 400 |
| Broad random sample (representative of typical incoming transactions) | 40.4% | 47.1% | 1100 |

The blended headline number above is pulled down by the already-verified subset, which is deliberately hard by construction. The 'broad random sample' row is the closest thing to *typical* transaction performance in this set.


## Our pipeline's resolution tier breakdown

- T6_native_fallback: 878 (58.5%)
- T4_dictionary: 591 (39.4%)
- T5_R02: 12 (0.8%)
- T5_R01: 5 (0.3%)
- T5_R10: 4 (0.3%)
- T5_R05: 3 (0.2%)
- T5_R12: 3 (0.2%)
- T5_R11: 2 (0.1%)
- T5_R04: 1 (0.1%)
- T5_R06: 1 (0.1%)

**Our pipeline gets it right where the native category doesn't**: 205 of 1500 transactions (13.7%).


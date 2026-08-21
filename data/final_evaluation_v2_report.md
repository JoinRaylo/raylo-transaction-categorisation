# Final evaluation v2: transaction-level, leakage-free gold set

Ground truth: `gold_transactions_v2.csv`, `gold_transactions_v2_batch2.csv` -- 3000 real transactions, each independently reviewed and hand-corrected by Carlos (403/1500 batch-1 drafts were overridden, including 34 of the 400 rows that already had a prior human verdict from earlier work -- this is a fresh, from-scratch review, not a rubber stamp). No clean/full split needed: unlike the v1 merchant-level set, nothing here is copied from the prediction being scored.

## Overall (all providers combined)

| Source | Leaf accuracy | General-category accuracy | Scored n |
|---|---|---|---|
| Native provider category | 39.9% | 55.2% | 3000 |
| Our pipeline | 46.6% | 58.5% | 3000 |

## By provider

| Provider | Native leaf acc | Native general acc | Our leaf acc | Our general acc | n |
|---|---|---|---|---|---|
| Equifax | 61.3% | 69.6% | 64.0% | 71.6% | 1259 |
| Plaid | 24.5% | 44.9% | 34.1% | 48.9% | 1741 |

## By sampling source (important -- these are very different populations)

| Source | Native leaf acc | Our leaf acc | n |
|---|---|---|---|
| Already-verified merchants (deliberately hard -- these needed human adjudication in earlier work precisely because they were disputed) | 10.7% | 31.3% | 550 |
| Broad random sample (representative of typical incoming transactions) | 41.5% | 46.2% | 1936 |
| Targeted for taxonomy-breadth coverage (rare leaves, batch 2 only) | 65.4% | 64.6% | 514 |

The blended headline number above is pulled down by the already-verified subset, which is deliberately hard by construction. The 'broad random sample' row is the closest thing to *typical* transaction performance in this set.


## Our pipeline's resolution tier breakdown

- T6_native_fallback: 2102 (70.1%)
- T4_dictionary: 832 (27.7%)
- T5_R02: 24 (0.8%)
- T5_R10: 11 (0.4%)
- T5_R11: 8 (0.3%)
- T5_R01: 7 (0.2%)
- T5_R12: 5 (0.2%)
- T5_R05: 3 (0.1%)
- T5_R09: 3 (0.1%)
- T5_R06: 2 (0.1%)
- T5_R04: 1 (0.0%)
- T5_R03: 1 (0.0%)
- T5_R14: 1 (0.0%)

**Our pipeline gets it right where the native category doesn't**: 298 of 3000 transactions (9.9%).


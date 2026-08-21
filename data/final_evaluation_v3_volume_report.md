# Final evaluation v3: volume-weighted (true random sample, no category stratification)

1500 real transactions, true random sample (Equifax + Plaid sampled and reported separately -- see below). 14 excluded from scoring as self-sourced dictionary entries. This answers a different question from the v2 breadth evaluation: **what fraction of actual transaction VOLUME gets classified correctly today**, since high-volume merchants dominate this sample in roughly their true proportion.

## Equifax (n=596)

| Source | Leaf accuracy | General-category accuracy |
|---|---|---|
| Native provider category | 71.8% | 81.2% |
| Our pipeline | 82.0% | 87.4% |

## Plaid (n=890)

| Source | Leaf accuracy | General-category accuracy |
|---|---|---|
| Native provider category | 32.5% | 60.3% |
| Our pipeline | 63.4% | 74.2% |


# Hinge v8 — retrained with the T6-bound risk tranche (2026-09-03)

Same recipe as v5–v7. Training file **414,400** rows = v7's 409,417 + `data/tuning_risk_topup.csv`
(4,998 T6-bound risk-looking debits, all `agent_review`; 3 Sep). Holdout MD5 unchanged.
Comparator hinge v7 (credit tranche, no risk tranche). Serving dump (v5) not touched.
Locked v5/v6 not scored. Rules R33–R51 (3 Sep) are live in every "clf+T5" row.

| set | metric | v7 hinge | **v8 hinge (+risk tranche)** |
|---|---|---:|---:|
| holdout (1,055) | leaf / general | 56.6 / 64.4 | 57.1 / 64.3 |
| holdout | leaf with T5 | 57.1 | **58.3** |
| risk gold (711) | risk bar (n=619), classifier only | 63.0% | 64.6% |
| risk gold | risk bar with T5 | 66.4% | **68.5%** |
| credit eval (2,000) | leaf | 85.0% | **85.9%** |
| **risk T6-bound gold (400)** | leaf, classifier only | 51.5% | **67.2%** |
| risk T6-bound gold | risk-leaf acc (n=174), classifier only | 48.3% | **75.9%** |

## Read

1. **The honest T6-bound risk number is now above the 70% bar for the first time: 75.9%**
   on the 174 risk-leaf rows the classifier serves, from 48.3% this morning. Two things did
   it, in order: the R33–R37 rules (48 → 59% with v7) and then 5k rows of the same population
   in training (→ 76% for the classifier on its own; with the rules in front it will be
   higher, since the rules resolve the easy 57 rows before the classifier is asked).
2. **Nothing else moved.** Holdout +0.5pp, credit eval +0.9pp, 711-row risk bar +1.6pp. The
   tranche did what it targeted and did not disturb the rest — the same pattern as the
   credit tranche.
3. **Caveat on the 400-row set.** Its merchants are excluded from training, but 79% of rows
   have a blank merchant, so exclusion is by exact text, not by template: a `CREDIT CARD
   6000…` in gold and a `CREDIT CARD 6001…` in training are different rows of the same
   narrative family. That is exactly the generalisation production needs, but it means this
   number is "same population, unseen rows", not "unseen population". The 22-row
   `debt_collection` and 9-row `gambling_casino` leaves are still thin.

## Decisions
- v8 is the reference hinge for transformer comparisons from here.
- Serving still v5 weights; promotion of v8 (or the transformer) is a separate decision that
  also needs a serving path. The gap between the v5 dump and v8 is now large on credits (+24pp
  on the credit eval) and on T6-bound risk (+28pp): the serving dump is stale.

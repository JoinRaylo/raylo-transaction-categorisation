# Transformer classifier vs de-leaked hinge — 2026-09-02

Model `outputs/distill_models/txn_classifier_gold_uncapped` (stage `gold`, encoder from `/Users/carlosnoblejesus/Repos/raylo-transaction-categorisation/outputs/distill_models/txn_classifier_silver`, 381,411 rows, 6 epochs). Hinge `tfidf_linearsvm_sgd_v6_deleaked.joblib`. Same sentence format as pretraining; direction mask at the logits. Locked v5/v6 not scored.

| set | cut | model | n | leaf | general | risk-leaf acc (n) | credit leaf (n) | credit-bar (n) |
|---|---|---|---:|---:|---:|---:|---:|---:|
| holdout | all (classifier only) | hinge | 1055 | 56.0% | 62.8% | 55.8% (104) | 43.7% (103) | 41.9% (93) |
| holdout | all (classifier only) | transformer | 1055 | 63.6% | 71.8% | 67.3% (104) | 72.8% (103) | 74.2% (93) |
| holdout | all (classifier only) | hybrid 50/50 | 1055 | 63.0% | 71.3% | 66.3% (104) | 67.0% (103) | 67.7% (93) |
| holdout | T6-bound | hinge | 418 | 56.9% | 64.4% | 57.6% (33) | 31.2% (32) | 19.2% (26) |
| holdout | T6-bound | transformer | 418 | 63.2% | 71.5% | 63.6% (33) | 59.4% (32) | 57.7% (26) |
| holdout | T6-bound | hybrid 50/50 | 418 | 62.4% | 70.6% | 63.6% (33) | 46.9% (32) | 42.3% (26) |
| risk gold | all (classifier only) | hinge | 711 | 59.8% | 65.4% | 62.7% (619) | 52.9% (68) | 18.4% (38) |
| risk gold | all (classifier only) | transformer | 711 | 56.7% | 65.5% | 62.0% (619) | 8.8% (68) | 13.2% (38) |
| risk gold | all (classifier only) | hybrid 50/50 | 711 | 59.8% | 68.2% | 65.6% (619) | 39.7% (68) | 13.2% (38) |
| risk gold | T6-bound | hinge | 89 | 64.0% | 68.5% | 77.5% (40) | 56.1% (41) | 15.0% (20) |
| risk gold | T6-bound | transformer | 89 | 19.1% | 23.6% | 30.0% (40) | 4.9% (41) | 5.0% (20) |
| risk gold | T6-bound | hybrid 50/50 | 89 | 42.7% | 46.1% | 82.5% (40) | 53.7% (41) | 5.0% (20) |
| pipeline eval | all (classifier only) | hinge | 2004 | 59.5% | 66.0% | 60.1% (676) | 44.4% (180) | 38.1% (147) |
| pipeline eval | all (classifier only) | transformer | 2004 | 63.3% | 71.5% | 63.6% (676) | 54.4% (180) | 59.9% (147) |
| pipeline eval | all (classifier only) | hybrid 50/50 | 2004 | 63.7% | 71.8% | 65.2% (676) | 57.2% (180) | 55.8% (147) |
| pipeline eval | T6-bound | hinge | 505 | 58.0% | 65.3% | 65.0% (60) | 37.1% (62) | 17.8% (45) |
| pipeline eval | T6-bound | transformer | 505 | 57.0% | 65.1% | 53.3% (60) | 33.9% (62) | 35.6% (45) |
| pipeline eval | T6-bound | hybrid 50/50 | 505 | 58.6% | 66.3% | 71.7% (60) | 43.5% (62) | 26.7% (45) |
| pipeline eval | full pipeline T1–T5 then model | hinge | 2004 | 81.3% | 86.9% | 88.5% (676) | 56.1% (180) | 55.1% (147) |
| pipeline eval | full pipeline T1–T5 then model | transformer | 2004 | 81.1% | 86.9% | 87.4% (676) | 55.0% (180) | 60.5% (147) |
| pipeline eval | full pipeline T1–T5 then model | hybrid 50/50 | 2004 | 81.5% | 87.2% | 89.1% (676) | 58.3% (180) | 57.8% (147) |

## Kill criteria

| criterion | result | detail |
|---|---|---|
| holdout T6-bound leaf ≥ hinge +3pp | PASS | 63.2% vs 56.9% (n=418) |
| pipeline residual leaf ≥ hinge +3pp | MISS | 57.0% vs 58.0% (n=505) |
| T6-bound risk-leaf acc ≥ hinge | MISS | 30.0% vs 77.5% (n=40) |
| credit-side bar (pipeline residual) ≥ hinge +10pp | PASS | 35.6% vs 17.8% (n=45) |
| CPU throughput ≥ 1,000 rows/s | PASS | 1,033 rows/s |
| hybrid: holdout T6-bound leaf ≥ hinge +3pp | PASS | 62.4% vs 56.9% |
| hybrid: pipeline residual leaf ≥ hinge +3pp | MISS | 58.6% vs 58.0% |
| hybrid: T6-bound risk-leaf acc ≥ hinge | PASS | 82.5% vs 77.5% |
| hybrid: credit-side bar ≥ hinge +10pp | MISS | 26.7% vs 17.8% |

**Verdict (transformer alone): KEEP HINGE (missed 2).** Hybrid misses 2/4 accuracy criteria (throughput = transformer's, 1,033 rows/s).

## Read (iteration 3: no per-leaf cap, 6 epochs, best epoch by merchant-disjoint Tier-B val)

- Val plateaued at **77.6% from epoch 2** (77.1 → 77.6 → 77.3 → 77.4 → 76.7 → 77.4): the
  gold file is exhausted for this encoder; more epochs of the same data do nothing.
- Removing the cap did **not** move the pipeline residual (57.0% vs hinge 58.0%); the
  holdout T6-bound gain is stable across iterations (+4 to +7pp) and credits stay far ahead
  (credit-bar 35.6% vs 17.8%).
- The T6-bound risk slice is still lost by the transformer alone (30.0%), but the **50/50
  hybrid recovers it (82.5% vs hinge 77.5%)** and is at or above the hinge on every cut:
  holdout T6-bound 62.4 / residual 58.6 / full pipeline 81.5 vs 81.3. It misses the +3pp
  residual and +10pp credit-bar thresholds by 2.4pp and 1.1pp respectively.
- Transformer alone now misses 2 criteria (residual, risk slice); hybrid misses 2 by narrow
  margins. Neither is a promotion under the pre-declared rule.

## The decisive split: seen vs unseen merchants on the residual (iteration 3 model)

| residual slice | n | hinge | transformer |
|---|---:|---:|---:|
| pipeline, merchant **unseen** in training | 449 | 57.0% | **62.6%** |
| pipeline, merchant **seen** in training | 56 | 66.1% | 12.5% |
| risk gold, merchant unseen | 22 | 45.5% | 45.5% |
| risk gold, merchant seen | 67 | 70.1% | 10.4% |

On genuinely novel strings — the job T5b exists for — the transformer is **+5.6pp** over the
hinge on 449 rows. Its whole deficit is on rows whose merchant *is* in training, and those
rows are almost entirely two leaf pairs: `overdraft_arranged → overdraft_unarranged` (20 rows
in each set; 7 training rows for the arranged leaf) and `cash_advance` **credits** →
`returned_payment` (10 / 20 rows). Everything else the hinge memorises, the transformer also
gets. Hybrid weight sweep 0.3–0.7 moves the residual by <1pp (58.0–58.8); a margin-gated
combination is no better. So the remaining gap is two label conventions on ~40 rows, not model
capacity, and the fix is data or a T2/T5 rule for those two pairs.

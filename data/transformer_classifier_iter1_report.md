# Transformer classifier vs de-leaked hinge — iteration 1 (2026-09-02, taxonomy-only direction mask)

Model `outputs/distill_models/txn_classifier_gold` (stage `gold`, encoder from `/Users/carlosnoblejesus/Repos/raylo-transaction-categorisation/outputs/distill_models/txn_classifier_silver`, 380,540 rows, 3 epochs). Hinge `tfidf_linearsvm_sgd_v6_deleaked.joblib`. Same sentence format as pretraining; direction mask at the logits. Locked v5/v6 not scored.

| set | cut | model | n | leaf | general | risk-leaf acc (n) | credit leaf (n) | credit-bar (n) |
|---|---|---|---:|---:|---:|---:|---:|---:|
| holdout | all (classifier only) | hinge | 1055 | 56.0% | 62.8% | 55.8% (104) | 43.7% (103) | 41.9% (93) |
| holdout | all (classifier only) | transformer | 1055 | 63.2% | 70.4% | 67.3% (104) | 70.9% (103) | 72.0% (93) |
| holdout | T6-bound | hinge | 418 | 56.9% | 64.4% | 57.6% (33) | 31.2% (32) | 19.2% (26) |
| holdout | T6-bound | transformer | 418 | 64.1% | 72.0% | 66.7% (33) | 56.2% (32) | 53.8% (26) |
| risk gold | all (classifier only) | hinge | 711 | 59.8% | 65.4% | 62.7% (619) | 52.9% (68) | 18.4% (38) |
| risk gold | all (classifier only) | transformer | 711 | 57.2% | 66.1% | 61.7% (619) | 17.6% (68) | 28.9% (38) |
| risk gold | T6-bound | hinge | 89 | 64.0% | 68.5% | 77.5% (40) | 56.1% (41) | 15.0% (20) |
| risk gold | T6-bound | transformer | 89 | 22.5% | 25.8% | 35.0% (40) | 4.9% (41) | 5.0% (20) |
| pipeline eval | all (classifier only) | hinge | 2004 | 59.5% | 66.0% | 60.1% (676) | 44.4% (180) | 38.1% (147) |
| pipeline eval | all (classifier only) | transformer | 2004 | 63.3% | 70.8% | 63.3% (676) | 56.7% (180) | 62.6% (147) |
| pipeline eval | T6-bound | hinge | 505 | 58.0% | 65.3% | 65.0% (60) | 37.1% (62) | 17.8% (45) |
| pipeline eval | T6-bound | transformer | 505 | 58.6% | 66.1% | 58.3% (60) | 32.3% (62) | 33.3% (45) |
| pipeline eval | full pipeline T1–T5 then model | hinge | 2004 | 81.3% | 86.9% | 88.5% (676) | 56.1% (180) | 55.1% (147) |
| pipeline eval | full pipeline T1–T5 then model | transformer | 2004 | 81.5% | 87.1% | 87.9% (676) | 54.4% (180) | 59.9% (147) |

## Kill criteria

| criterion | result | detail |
|---|---|---|
| holdout T6-bound leaf ≥ hinge +3pp | PASS | 64.1% vs 56.9% (n=418) |
| pipeline residual leaf ≥ hinge +3pp | MISS | 58.6% vs 58.0% (n=505) |
| T6-bound risk-leaf acc ≥ hinge | MISS | 35.0% vs 77.5% (n=40) |
| credit-side bar (pipeline residual) ≥ hinge +10pp | PASS | 33.3% vs 17.8% (n=45) |
| CPU throughput ≥ 1,000 rows/s | MISS | 980 rows/s |

**Verdict: KEEP HINGE (missed 3).**

## Diagnosis of the T6-bound risk miss (n=89)

- **20 rows are `cash_advance` credits** (the disbursement, labelled with the product leaf by
  the gold convention). The taxonomy-only mask marks `cash_advance` debit-only, so the model
  *cannot* predict them: 0/20 vs hinge 20/20. Fix: the mask is now empirical — a leaf is legal
  for a direction if the taxonomy says so **or** the gold jsonl has ≥5 rows of that leaf in
  that direction (iteration 2).
- **20 rows `overdraft_arranged` → predicted `overdraft_unarranged`** (7 training rows for
  the arranged leaf; near-identical narratives).
- **7 account-switch "BALANCE TRANSFER" credits** (gold `transfer_own_account`) → predicted
  `balance_transfer`: a lexical trap the char-n-gram hinge happens to avoid.
- On the 69 legal rows the transformer is 29.0% vs hinge 53.6% — the gap is real on this
  slice but concentrated in two leaf pairs; the holdout T6-bound slice (n=418, 0 illegal)
  is 64.1% vs 56.9% in the transformer's favour, and credits 56.2% vs 31.2%.

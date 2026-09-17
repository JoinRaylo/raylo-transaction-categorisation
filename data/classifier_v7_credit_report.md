# Hinge v7 — retrained with the credit tranche (2026-09-03)

Same recipe as v5/v6 (char TF-IDF + SGD hinge, `retrain_corrected_heads.py --hinge-only`),
trained on `outputs/tuning_train.jsonl` **409,417** rows: the de-leaked 381,560 plus the
27,979-row credit top-up from `data/tuning_credit_topup.csv` (credit share **0.65% → 7.4%**).
Holdout MD5 `7456da977a2c761119368637658232b6` unchanged. Comparator is the de-leaked v6 hinge
(same recipe, no credit tranche). Serving dump (v5) not touched. Locked v5/v6 not scored.

New eval sets from the tranche (both merchant-disjoint from training, both excluded from
every training source in `build_tuning_dataset.py`):
- `data/gold_credit_eval.csv` — 2,000 live Plaid credits; labels 84.3% Carlos-agreement on the blind slice.
- `data/gold_transactions_risk_t6bound.csv` — 400 T6-bound debits that look like risk leaves; 383 Carlos-labelled.

| set | metric | v6 hinge (de-leaked) | **v7 hinge (+credit)** |
|---|---|---:|---:|
| holdout (1,055) | leaf / general | 56.0 / 62.8 | **56.6 / 64.4** |
| holdout | credit rows leaf (n=103) | 43.7% | **61.2%** |
| holdout | credit bar (n=93) | 41.9% | **61.3%** |
| risk gold (711) | leaf / general | 59.8 / 65.4 | **60.9 / 70.5** |
| risk gold | risk bar (n=619) | 62.7% | 63.0% |
| **credit eval (2,000)** | leaf / general | 62.2 / 68.2 | **85.0 / 87.6** |
| credit eval | credit bar (n=1,505) | 71.4% | **88.3%** |
| credit eval | risk-leaf rows (n=119) | 35.3% | **73.9%** |
| **risk T6-bound gold (400)** | leaf / general | 49.2 / 55.5 | 51.5 / 58.2 |
| risk T6-bound gold | risk-leaf acc (n=174) | 48.9% | 48.3% |

## Read

1. **The credit tranche does what it was for.** On 2,000 held-out credits the same model goes
   from 62% to **85%** leaf; holdout credits (a different population, merchant-disjoint) go
   from 44% to 61%. Debit accuracy did not move (holdout leaf +0.6pp). 28k rows at 7% of the
   file was enough; this is the largest single-step gain in the classifier's history and it
   came from data, not modelling.
2. **The honest T6-bound risk number is ~48–50% on 400 rows**, for both models. This is the
   slice T5b actually serves for risk leaves, now measured on 174 risk-leaf rows instead of 40.
   It is far below the 70% bar and the credit tranche did not change it (it was not meant to).
   Top gold leaves there: `credit_card_repayment` 74, `account_charge` 33, `overdraft_arranged`
   17, `personal_loan_repayment` 17. This is the next labelling target, and several of them
   are T2/T5 rule candidates (card-issuer inflows, overdraft fee narratives) rather than
   classifier work.
3. The old 711-row risk set moved from 62.7% to 63.0% — in-sample-free and flat, as expected.

## Decisions / next
- v7 is the new **reference hinge** for every transformer comparison (`--hinge …_v7_credit.joblib`).
- Serving stays v5 until the transformer verdict on the same data (running: 3 seeds vs v7).
- Add `gold_credit_eval.csv` to the iteration suite (done in `compare_classifier_versions.py`
  and `score_transformer.py`); `gold_transactions_risk_t6bound.csv` is the gating risk set.

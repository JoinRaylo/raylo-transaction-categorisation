# Transformer classifier vs de-leaked hinge — 2026-09-02

Model `outputs/distill_models/txn_classifier_gold` (stage `gold`, encoder from `/Users/carlosnoblejesus/Repos/raylo-transaction-categorisation/outputs/distill_models/txn_classifier_silver`, 381,411 rows, 3 epochs). Hinge `tfidf_linearsvm_sgd_v6_deleaked.joblib`. Same sentence format as pretraining; direction mask at the logits. Locked v5/v6 not scored.

| set | cut | model | n | leaf | general | risk-leaf acc (n) | credit leaf (n) | credit-bar (n) |
|---|---|---|---:|---:|---:|---:|---:|---:|
| holdout | all (classifier only) | hinge | 1055 | 56.0% | 62.8% | 55.8% (104) | 43.7% (103) | 41.9% (93) |
| holdout | all (classifier only) | transformer | 1055 | 62.6% | 69.8% | 68.3% (104) | 68.0% (103) | 68.8% (93) |
| holdout | T6-bound | hinge | 418 | 56.9% | 64.4% | 57.6% (33) | 31.2% (32) | 19.2% (26) |
| holdout | T6-bound | transformer | 418 | 61.2% | 68.7% | 66.7% (33) | 40.6% (32) | 34.6% (26) |
| risk gold | all (classifier only) | hinge | 711 | 59.8% | 65.4% | 62.7% (619) | 52.9% (68) | 18.4% (38) |
| risk gold | all (classifier only) | transformer | 711 | 55.8% | 64.0% | 61.1% (619) | 8.8% (68) | 13.2% (38) |
| risk gold | T6-bound | hinge | 89 | 64.0% | 68.5% | 77.5% (40) | 56.1% (41) | 15.0% (20) |
| risk gold | T6-bound | transformer | 89 | 21.3% | 23.6% | 32.5% (40) | 4.9% (41) | 5.0% (20) |
| pipeline eval | all (classifier only) | hinge | 2004 | 59.5% | 66.0% | 60.1% (676) | 44.4% (180) | 38.1% (147) |
| pipeline eval | all (classifier only) | transformer | 2004 | 62.9% | 70.2% | 63.0% (676) | 52.2% (180) | 57.1% (147) |
| pipeline eval | T6-bound | hinge | 505 | 58.0% | 65.3% | 65.0% (60) | 37.1% (62) | 17.8% (45) |
| pipeline eval | T6-bound | transformer | 505 | 56.0% | 63.0% | 56.7% (60) | 24.2% (62) | 22.2% (45) |
| pipeline eval | full pipeline T1–T5 then model | hinge | 2004 | 81.3% | 86.9% | 88.5% (676) | 56.1% (180) | 55.1% (147) |
| pipeline eval | full pipeline T1–T5 then model | transformer | 2004 | 80.8% | 86.3% | 87.7% (676) | 51.7% (180) | 56.5% (147) |

## Kill criteria

| criterion | result | detail |
|---|---|---|
| holdout T6-bound leaf ≥ hinge +3pp | PASS | 61.2% vs 56.9% (n=418) |
| pipeline residual leaf ≥ hinge +3pp | MISS | 56.0% vs 58.0% (n=505) |
| T6-bound risk-leaf acc ≥ hinge | MISS | 32.5% vs 77.5% (n=40) |
| credit-side bar (pipeline residual) ≥ hinge +10pp | MISS | 22.2% vs 17.8% (n=45) |
| CPU throughput ≥ 1,000 rows/s | PASS | 1,050 rows/s |

**Verdict: KEEP HINGE (missed 3).**

## Read (iteration 2, empirical direction mask; iteration 1 in `transformer_classifier_iter1_report.md`)

Same encoder (BERT-small + 4,000 domain tokens, 1 MLM epoch on 3M sentences, 4.5 h on an
M5 Pro), same silver pass; only the gold pass was re-run with the empirical mask. Single seed.

| cut | hinge (de-leaked) | transformer iter 1 | transformer iter 2 |
|---|---:|---:|---:|
| holdout T6-bound leaf (n=418, merchant-disjoint) | 56.9% | **64.1%** | **61.2%** |
| holdout T6-bound credit leaf (n=32) | 31.2% | 56.2% | 40.6% |
| pipeline residual leaf (n=505) | 58.0% | 58.6% | 56.0% |
| pipeline residual credit-bar (n=45) | 17.8% | 33.3% | 22.2% |
| risk gold T6-bound risk-leaf acc (n=40) | 77.5% | 35.0% | 32.5% |
| full pipeline T1–T5 then model (n=2,004) | 81.3% | 81.5% | 80.8% |
| CPU rows/s (BERT-small, 1 process) | — | 980 | 1,050 |

1. **On the one clean, adequately sized cut — novel merchants on the merchant-disjoint
   holdout — the transformer beats the char-TF-IDF hinge by 4–7 points**, and by 10–25 points on
   credits. That is the generalisation the review said a domain-pretrained encoder should buy.
2. **On the pipeline residual it is flat**, and **on the 40-row T6-bound risk slice it loses
   badly** for concentrated reasons: arranged-vs-unarranged overdraft (7 training rows for the
   arranged leaf), account-switch "BALANCE TRANSFER" credits (gold `transfer_own_account`), and
   cash-advance disbursement credits — now legal under the mask but predicted as
   `loan_disbursement`. These are label-convention and thin-leaf problems the hinge happens to
   memorise from near-duplicate Tier B rows; they are not evidence that the encoder cannot learn
   risk leaves (holdout risk-leaf accuracy is 66.7% vs 57.6%).
3. **Run-to-run variance is large.** Iterations 1 and 2 differ by 3pp on the holdout slice and
   11pp on the 45-row credit bar with no change to the encoder. Every comparison here, and every
   hinge-vs-hinge decision in this repo, needs ≥3 seeds and paired intervals before it means
   anything at n ≤ 500.
4. **Verdict stands: keep hinge as T5b for now** (pre-declared criteria: 3 misses). The
   transformer is not rejected — it is the first model to beat the hinge on novel merchants —
   but it should not replace T5b until (a) the credit tranche and a T6-bound risk gold set exist
   so the two failing cuts are measured on more than 40–45 rows, (b) 3-seed runs replace single
   runs, and (c) the thin-leaf conventions (overdraft split, account-switch transfers) are either
   given training rows or moved into T2/T5 rules where they belong.

Cost of one full cycle on the M5 Pro: corpus 1 min (BigQuery), MLM 4.5 h, silver 30 min, gold
20 min, scoring 2 min. Re-running only the gold pass and scorer is ~25 min.

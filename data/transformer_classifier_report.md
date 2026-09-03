# Transformer classifier vs de-leaked hinge — 2026-09-02

Model `outputs/distill_models/txn_classifier_gold_v4` (stage `gold`, encoder from `/Users/carlosnoblejesus/Repos/raylo-transaction-categorisation/outputs/distill_models/txn_classifier_silver`, 381,411 rows, 4 epochs). Hinge `tfidf_linearsvm_sgd_v6_deleaked.joblib`. Same sentence format as pretraining; direction mask at the logits. Locked v5/v6 not scored.

| set | cut | model | n | leaf | general | risk-leaf acc (n) | credit leaf (n) | credit-bar (n) |
|---|---|---|---:|---:|---:|---:|---:|---:|
| holdout | all (classifier only) | hinge | 1055 | 56.0% | 62.8% | 55.8% (104) | 43.7% (103) | 41.9% (93) |
| holdout | all (classifier only) | transformer | 1055 | 60.7% | 69.2% | 65.4% (104) | 55.3% (103) | 54.8% (93) |
| holdout | all (classifier only) | hybrid 50/50 | 1055 | 61.0% | 69.5% | 65.4% (104) | 55.3% (103) | 54.8% (93) |
| holdout | T6-bound | hinge | 418 | 56.9% | 64.4% | 57.6% (33) | 31.2% (32) | 19.2% (26) |
| holdout | T6-bound | transformer | 418 | 61.7% | 70.3% | 63.6% (33) | 53.1% (32) | 50.0% (26) |
| holdout | T6-bound | hybrid 50/50 | 418 | 62.4% | 70.8% | 63.6% (33) | 53.1% (32) | 50.0% (26) |
| risk gold | all (classifier only) | hinge | 711 | 59.8% | 65.4% | 62.7% (619) | 52.9% (68) | 18.4% (38) |
| risk gold | all (classifier only) | transformer | 711 | 59.5% | 70.5% | 65.3% (619) | 39.7% (68) | 13.2% (38) |
| risk gold | all (classifier only) | hybrid 50/50 | 711 | 59.5% | 69.3% | 65.4% (619) | 38.2% (68) | 10.5% (38) |
| risk gold | T6-bound | hinge | 89 | 64.0% | 68.5% | 77.5% (40) | 56.1% (41) | 15.0% (20) |
| risk gold | T6-bound | transformer | 89 | 39.3% | 50.6% | 77.5% (40) | 51.2% (41) | 0.0% (20) |
| risk gold | T6-bound | hybrid 50/50 | 89 | 40.4% | 51.7% | 80.0% (40) | 51.2% (41) | 0.0% (20) |
| pipeline eval | all (classifier only) | hinge | 2004 | 59.5% | 66.0% | 60.1% (676) | 44.4% (180) | 38.1% (147) |
| pipeline eval | all (classifier only) | transformer | 2004 | 62.1% | 71.0% | 64.8% (676) | 49.4% (180) | 46.3% (147) |
| pipeline eval | all (classifier only) | hybrid 50/50 | 2004 | 62.4% | 71.0% | 64.9% (676) | 48.9% (180) | 45.6% (147) |
| pipeline eval | T6-bound | hinge | 505 | 58.0% | 65.3% | 65.0% (60) | 37.1% (62) | 17.8% (45) |
| pipeline eval | T6-bound | transformer | 505 | 57.6% | 66.9% | 68.3% (60) | 45.2% (62) | 28.9% (45) |
| pipeline eval | T6-bound | hybrid 50/50 | 505 | 58.4% | 67.5% | 70.0% (60) | 45.2% (62) | 28.9% (45) |
| pipeline eval | full pipeline T1–T5 then model | hinge | 2004 | 81.3% | 86.9% | 88.5% (676) | 56.1% (180) | 55.1% (147) |
| pipeline eval | full pipeline T1–T5 then model | transformer | 2004 | 81.2% | 87.3% | 88.8% (676) | 58.9% (180) | 58.5% (147) |
| pipeline eval | full pipeline T1–T5 then model | hybrid 50/50 | 2004 | 81.4% | 87.5% | 88.9% (676) | 58.9% (180) | 58.5% (147) |

## Kill criteria

| criterion | result | detail |
|---|---|---|
| holdout T6-bound leaf ≥ hinge +3pp | PASS | 61.7% vs 56.9% (n=418) |
| pipeline residual leaf ≥ hinge +3pp | MISS | 57.6% vs 58.0% (n=505) |
| T6-bound risk-leaf acc ≥ hinge | PASS | 77.5% vs 77.5% (n=40) |
| credit-side bar (pipeline residual) ≥ hinge +10pp | PASS | 28.9% vs 17.8% (n=45) |
| CPU throughput ≥ 1,000 rows/s | PASS | 1,058 rows/s |
| hybrid: holdout T6-bound leaf ≥ hinge +3pp | PASS | 62.4% vs 56.9% |
| hybrid: pipeline residual leaf ≥ hinge +3pp | MISS | 58.4% vs 58.0% |
| hybrid: T6-bound risk-leaf acc ≥ hinge | PASS | 80.0% vs 77.5% |
| hybrid: credit-side bar ≥ hinge +10pp | PASS | 28.9% vs 17.8% |

**Verdict (transformer alone): PASS — candidate to replace T5b.** Hybrid misses 1/4 accuracy criteria (throughput = transformer's, 1,058 rows/s).

## Read (iteration 4 — first run with a consistent, correct direction mask; single seed)

Iterations 1–3 are in `transformer_classifier_iter{1,2,3}_report.md`. Iteration 2–3 had a
bug: the silver checkpoint's taxonomy-only mask buffers were inherited into the gold stage, so
`cash_advance` (and 40 other leaves) stayed illegal on credits during training and scoring.
Fixed (`load_heads()` drops the buffers). Recipe: BERT-small + 4,000 domain tokens, 1 MLM
epoch on 3M sentences; silver pass (1.83M keys); gold pass on all 381k rows, no cap, floor
300, 4 epochs, best epoch by the merchant-disjoint Tier-B val (epoch 2, 78.0%).

| cut | hinge (de-leaked) | transformer | hybrid 50/50 |
|---|---:|---:|---:|
| holdout T6-bound leaf (n=418) | 56.9% | **61.7%** | **62.4%** |
| holdout T6-bound credit leaf (n=32) | 31.2% | **53.1%** | 53.1% |
| pipeline residual leaf (n=505) | 58.0% | 57.6% | 58.4% |
| pipeline residual credit-bar (n=45) | 17.8% | **28.9%** | 28.9% |
| risk gold T6-bound risk-leaf acc (n=40) | 77.5% | **77.5%** | **80.0%** |
| full pipeline T1–T5 then model (n=2,004) | 81.3% | 81.2% | **81.4%** |
| full pipeline, credit rows (n=180) | 56.1% | **58.9%** | 58.9% |
| CPU rows/s | — | 1,058 | — |

Pre-declared criteria: transformer alone **4/5 pass** (misses only "residual ≥ +3pp": 57.6 vs
58.0); hybrid 4/5. By the rule ("miss two → stop") this is the first **candidate to replace
T5b**. It is not a promotion:

1. **Single seed.** Iterations 1–3 moved 3–11pp on the small cuts between runs. Seeds 7 and
   123 of this exact recipe are running; the verdict needs the 3-seed mean and paired CIs.
2. **The residual is flat, not better.** The transformer wins on unseen merchants (+5.6pp on
   449 rows in iteration 3's split) and loses on the ~40 rows of two label conventions
   (`overdraft_arranged` vs `unarranged`; account-switch "BALANCE TRANSFER" credits). Those
   are rule/label work, not model work.
3. **Credits are the clearest gain** (+22pp on holdout T6-bound credits, +11pp on the credit
   bar) — with 0.6% credits in the gold file. The credit tranche should widen this.
4. Serving would need the encoder packaged (PyTorch, ~120 MB with vocab) — ~1,050 rows/s on
   one CPU process, so 4.3M rows ≈ 70 CPU-minutes.

Next: 3 seeds → if the mean holds, (a) credit tranche + T6-bound risk gold, (b) full 22M
pretraining corpus and a 44–66M encoder on a rented GPU, (c) T5 rule for the overdraft
convention, (d) serving path design.

## Three seeds of the iteration-4 recipe (seeds 42 / 7 / 123; per-seed reports in `outputs/transformer/iter4_seed*_report.md`)

| cut | hinge | seed 42 | seed 7 | seed 123 | **mean** |
|---|---:|---:|---:|---:|---:|
| holdout T6-bound leaf (n=418) | 56.9% | 61.7% | 63.2% | 62.0% | **62.3%** |
| holdout T6-bound credit leaf (n=32) | 31.2% | 53.1% | 53.1% | 53.1% | **53.1%** |
| pipeline residual leaf (n=505) | 58.0% | 57.6% | 59.6% | 59.0% | **58.7%** |
| pipeline residual credit-bar (n=45) | 17.8% | 28.9% | 33.3% | 33.3% | **31.8%** |
| risk gold T6-bound risk-leaf acc (n=40) | 77.5% | 77.5% | 80.0% | 85.0% | **80.8%** |
| full pipeline T1–T5 then model (n=2,004) | 81.3% | 81.2% | 81.7% | 81.6% | **81.5%** |
| full pipeline, credit rows (n=180) | 56.1% | 58.9% | 60.0% | 60.0% | **59.6%** |

All three seeds pass 4/5 criteria (the +3pp residual threshold is the miss every time; the
residual is +0.7pp on average). Seed spread is ~1.5pp on the 418-row cut and ~2pp on the
505-row cut — far tighter than iterations 1–3, which were confounded by the mask bug.
**Verdict: the transformer is a confirmed candidate to replace T5b** — better on novel
merchants (+5.4pp), much better on credits (+22pp / +14pp), level-to-better on the T6-bound
risk slice, and neutral on the blended pipeline. Not yet promoted: needs the credit tranche
and T6-bound risk gold for the small cuts, a serving path, and one more look at the two
label conventions it loses on.

Paired bootstrap (2,000 resamples) of transformer − hinge, per seed:

| cut | seed 42 | seed 7 | seed 123 |
|---|---:|---:|---:|
| holdout T6-bound (n=418) | +4.8pp [+1.0, +8.6] | +6.2pp [+1.9, +10.3] | +5.0pp [+1.0, +9.3] |
| pipeline residual (n=505) | −0.4pp [−4.2, +3.8] | +1.6pp [−2.4, +5.7] | +1.0pp [−3.2, +5.0] |

The novel-merchant gain excludes zero on every seed; the residual is a statistical tie.

## Iteration 5 — both models retrained with the credit tranche (2026-09-03)

Training file `outputs/tuning_train.jsonl` **409,417** rows (credit share 7.4%, was 0.65%);
comparator is **hinge v7** trained on the same file (`data/classifier_v7_credit_report.md`).
Transformer: same encoder/silver stage; gold pass uncapped, 4 epochs, best epoch by Tier-B val
(epochs 1 / 1 / 3), seeds 42 / 7 / 123. New eval sets: `gold_credit_eval.csv` (2,000,
merchant-disjoint, 84.3% blind human agreement) and `gold_transactions_risk_t6bound.csv`
(400 T6-bound risk-looking debits, 383 Carlos-labelled).

| cut | hinge v7 | transformer (3-seed mean) | Δ, paired 95% CI |
|---|---:|---:|---:|
| holdout T6-bound leaf (n=418) | 57.2% | **60.9%** | +3.7pp [+0.3, +7.2] |
| credit eval leaf (n=2,000) | 85.0% | **87.4%** | +2.4pp [+1.3, +3.6] |
| credit eval general (n=2,000) | 87.6% | **88.9%** | — |
| pipeline residual leaf (n=505) | 59.2% | 57.9% | −1.3pp [−4.9, +2.2] |
| risk T6-bound gold leaf (n=400) | 51.5% | 49.4% | −2.1pp [−7.0, +2.7] |
| risk T6-bound gold, risk-leaf acc (n=174) | 48.3% | 47.3% (43.1–51.1) | tie |
| full pipeline T1–T5 then model (n=2,004) | 81.6% | 81.3% | tie |
| general accuracy, every cut | — | +1 to +6pp | consistently better |
| CPU rows/s | — | ~1,050 | — |

Kill criteria as written: every seed **misses ≥2** (residual +3pp; risk ≥ hinge on 2 of 3
seeds; the "+10pp credit bar" is now unreachable — both models sit at 89–91%). **Verdict:
keep hinge (v7) as T5b.**

### Read

1. **The credit lead was a data effect, not an architecture effect.** Once the hinge saw the
   same 28k credit rows it went 62 → 85% on the credit eval; the transformer is +2.4pp above
   it (CI excludes zero) — real, but small. Iteration 4's +22pp on credits was the encoder
   generalising from 0.6% credit data that the hinge could not; that advantage is what the
   tranche removed.
2. **What survives is the novel-merchant gain** (+3.7pp holdout T6-bound, CI excludes zero
   on the 3-seed mean, slightly narrower than iteration 4's +5.4) and **general-level accuracy**
   (+1–6pp on every cut), i.e. when the transformer is wrong it is wrong within the right
   family more often.
3. **T6-bound risk is a tie at ~48–51% for both**, now on 174 rows — the honest number for
   the slice T5b serves on risk leaves. Neither model is close to the 70% bar. The gold there
   is dominated by card-issuer inflows, account charges, overdraft narratives and personal
   loans: rule and labelling work, and the next tranche target.
4. **Net:** on today's data the two heads are near-equivalent. The transformer is a modest,
   consistent improvement on novel strings and on credits, at ~10× the serving cost of a
   65 MB linear model. The kill criteria were written when the gap was expected to be large;
   they should be re-cut around the general-level and novel-merchant gains, or the hybrid,
   before the promotion decision — but not re-cut *by* this result to make it pass.

### What would change the picture
- Scale pretraining (22M sentences, 2–3 epochs, 44–66M encoder on a GCP L4/A100): the
  encoder's edge is on unseen text, exactly where more domain pretraining acts. Cost £10–30.
- Row-level silver from the full 77M rows for the first fine-tune pass (the dictionary in
  context, tens of millions of examples), which is the Uncapped-scale data the hinge cannot
  exploit but the encoder can.
- T6-bound risk tranche + rules for card-issuer inflows / overdraft narratives — moves both.

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

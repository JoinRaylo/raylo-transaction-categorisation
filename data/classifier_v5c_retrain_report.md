# Classifier retrain — risk-guard oversample (v5c, 2026-08-27)

Same SGD as v5/v5b (char-wb TF-IDF 2–5, 30k, `alpha=1e-6`, 50 epochs). Training jsonl **383,066** (382,739 + 327 copies of `car_lease` / `debt_management_plan` / `revolving_credit_repayment` on merchants **not** on the risk-gold file). Liblinear not retrained.

Protected: holdout MD5 `1ac2eaaa494a49beab6d81f6cafe27c4`. **v6 not scored.**

Weights: `outputs/distill_models/tfidf_logreg_v5c.joblib` and `tfidf_linearsvm_sgd_v5c.joblib`. **Serving dumps restored to frozen v5.** Do not switch.

| | hinge v5 | hinge v5b | hinge v5c |
|---|---:|---:|---:|
| Holdout leaf (n=1,055) | 53.8% | 54.5% | **55.2%** |
| Risk bar (n=619) | **86.1%** | 79.8% | 79.0% |

Logreg v5c is down vs v5 on both (holdout 51.9% → 51.4%; risk bar 81.4% → 77.2%).

Hinge risk-gold leaves the guard targeted:

| Leaf | n | v5 | v5c |
|---|---:|---:|---:|
| `car_lease` | 20 | 20/20 | **20/20** (was 3/20 on v5b) |
| `debt_management_plan` | 25 | 23/25 | 16/25 |
| `revolving_credit_repayment` | 23 | 17/23 | 11/23 |
| `gambling_unspecified` (not guarded) | 25 | 20/25 | 12/25 |

The lease collapse is fixed without cloning risk-gold brand names. The bar still fails because DMP / revolving / unspecified gambling slipped, and leftover T6 mix is still in the jsonl.

Scorer: `src/compare_classifier_versions.py`. Predictions: `outputs/classifier_v5c_{hinge,logreg}_{holdout,risk}*.csv`.

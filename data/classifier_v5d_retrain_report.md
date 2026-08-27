# Classifier retrain — hinge-only v5d (2026-08-27)

Fresh char-wb TF-IDF + SGD hinge (50 epochs, no logreg) on the current jsonl (**383,066**). Same file as v5c. Serving dumps not overwritten. Liblinear not retrained.

Protected: holdout MD5 `7456da977a2c761119368637658232b6` (one PayPal Credit gold_leaf patch). **v6 not scored.**

Weights: `outputs/distill_models/tfidf_linearsvm_sgd_v5d.joblib`. **Serving stays frozen v5.**

| | hinge v5 | hinge v5c | hinge v5d |
|---|---:|---:|---:|
| Holdout leaf (n=1,055) | 53.9% | 55.2% | **56.6%** |
| Risk bar (n=619) | **86.1%** | 79.0% | 82.2% |

v5d is a better leftover/head trade than v5c but still fails the risk bar vs v5. Lease stays 20/20; DMP 15/25; revolving 13/23; `gambling_unspecified` 17/25. Do not switch.

Scorer: `src/compare_classifier_versions.py`. Predictions: `outputs/classifier_v5d_hinge_{holdout,risk}*.csv`.

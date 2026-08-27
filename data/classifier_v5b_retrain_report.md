# Classifier retrain — T6 residual top-up (v5b, 2026-08-27)

Same architecture as v5 (char-wb TF-IDF 2–5 grams, 30k features, SGD, `alpha=1e-6`, 50 epochs). Training jsonl **382,183 → 382,739** (+556 labelled T6 residual rows in `data/tuning_leaf_topup.csv`). Liblinear not retrained.

Protected: holdout MD5 `1ac2eaaa494a49beab6d81f6cafe27c4` unchanged. Risk gold and locked v5/v6 not in training. **v6 not scored.**

Weights: `outputs/distill_models/tfidf_logreg_v5b.joblib` and `tfidf_linearsvm_sgd_v5b.joblib`. **Serving dumps restored to frozen v5** (`tfidf_logreg_v2.joblib`, `tfidf_linearsvm_sgd.joblib`). Do not switch.

v5 headline numbers in `data/classifier_v5_retrain_report.md` were on the previous holdout hash (`c075…`). Both models below are scored on the **current** holdout (13 `gold_leaf` patches), so v5 here is 51.9% / 53.8% leaf, not 50.9% / 52.8%.

## Headline (classifier-only)

| | logreg v5 | logreg v5b | hinge v5 | hinge v5b |
|---|---|---|---|---|
| Holdout leaf / general (1,055) | 51.9 / 59.7 | 51.6 / 58.6 | 53.8 / 61.0 | **54.5 / 61.9** |
| Risk gold leaf / general (711) | 76.8 / 82.1 | 74.8 / 80.6 | **80.6 / 85.5** | 75.1 / 81.3 |
| Risk-category bar (n=619, ≥70%) | 81.4 OK | 80.5 OK | **86.1 OK** | 79.8 OK |

Hinge holdout **+0.7pp**. Risk bar **−6.3pp** (still above 70%). Logreg is flat-to-down on both.

T5-then-classifier still slightly dilutes these gold sets (same pattern as v5).

Scorer: `src/compare_classifier_versions.py`. Predictions: `outputs/classifier_v5b_{logreg,hinge}_{holdout,risk}*.csv`.

## Where the extra 556 rows helped (hinge, holdout)

| Leaf | n | v5 | v5b |
|---|---:|---:|---:|
| `loan_disbursement` | 5 | 0/5 | **3/5** |
| `refund_received` | 19 | 15.8% | **26.3%** |
| `transfer_p2p` | 45 | 64.4% | **71.1%** |

`salary` 4/13 unchanged. `salary_gig` 0/2. `utility_other` 0/3. `investment_trading` 0/3. `benefits_state` 2/19 → 0/19.

## Where it hurt (hinge, risk gold)

| Leaf | n | v5 | v5b | v5b confusions |
|---|---:|---:|---:|---|
| `car_lease` | 20 | 20/20 | **3/20** | 13 → `carwash` |
| `gambling_unspecified` | 25 | 20/25 | 14/25 | casino / debt_collection |
| `debt_management_plan` | 25 | 23/25 | 17/25 | 6 → `foreign_currency` |
| `revolving_credit_repayment` | 23 | 73.9% | 56.5% | — |

`cash_advance` 20/20 and `charge_card_repayment` 6/6 unchanged. Gambling-*family* recall is almost flat (87.4% → 86.9%); the bar drop is lease + DMP + revolving credit, not bingo/betting.

Likely cause: pack 1 is volume-heavy on `transfer_p2p` (71), `cashback` (45), `waste_services` (27) — T6-shaped leftover, not the risk-set distribution. 556 rows is small vs 382k but enough to move thin decision boundaries (lease vs carwash is a char-ngram collision).

## Decision

Keep serving at **v5**. Keep v5b dumps for ablation. Do not fold another residual pack into jsonl without a risk-gold check before overwriting serving. If we want the `loan_disbursement` holdout win without the lease collapse, try a **targeted** top-up (those leaves only) rather than the full pack-1 mix.

Fit: logreg 1,986s, hinge 1,069s. `python src/retrain_corrected_heads.py --skip-svc`.

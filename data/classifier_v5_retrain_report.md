# Classifier retrain report — tranche 4 (2026-08-26)

Follow-up to [`data/classifier_v4_retrain_report.md`](classifier_v4_retrain_report.md). Same architecture (char-wb TF-IDF 2–5 grams, 30k features, SGD logistic regression, `alpha=1e-6`, 50 epochs). Only the Tier B label source changes: `production_labels_tranche3.csv` → `production_labels_tranche4.csv` (100k merchants; tranche 4 is a full union, not incremental).

Deliberately excluded from training: `gold_transactions_risk_categories.csv` (this eval) and `gold_transactions_v5_LOCKED.csv` (never touched). v5 locked set was **not scored**.

**Protected asset check**: `data/gold_v2_slm_eval_holdout.csv` MD5 `c075717405a183191a43d0eb33f8dca3` is byte-identical before and after `build_tuning_dataset.py build`. (This is not the MD5 quoted in the v4 report — the holdout file was edited on disk before this retrain. Both models below are scored on the **current** file, so the comparison is fair even if the published 35.7% is not.)

Tranche-3 weights kept as `outputs/distill_models/tfidf_logreg_v4.joblib` (and the matching hinge/liblinear `_v4` dumps). New weights: `tfidf_logreg_v5.joblib`, also written to the serving name `tfidf_logreg_v2.joblib`. SGD hinge retrained to `tfidf_linearsvm_sgd_v5.joblib` (1,209s) — scored in the addendum below. Liblinear LinearSVC was **not** retrained on 382k: on ~167k rows (25 Aug) parallel OvR fitted in 40s and still lost to SGD hinge on every metric (`data/t5b_residual_gate_report.md`). The earlier “hours” hang was a sequential 251-class fit, not evidence the solver would win at this scale.

## What changed in the training set

| | v4 (tranche 3) | v5 (tranche 4) |
|---|---|---|
| Trusted-tier merchants (`auto_accept` / `accepted` / `human_reviewed`) | 18,543 | **91,803** |
| Tier B Plaid txns fetched (cap 10/merchant) | (inside 166k train jsonl) | 440,652 |
| Train rows after Tier A + top-up + starved oversample | 166,345 | **382,183** |
| Classes in train | — | 267 |
| `unclassified_other` share of labelled sources | — | 4.0% |

Tranche 4 contains every tranche-3 merchant. The jump is almost all `human_reviewed` (including strings that were `accepted_tiebreak` in tranche 3 and were previously excluded from training).

## Headline: same eval sets, both models

Classifier-only (`predict()`, including the gambling catch-all promote). T5-then-classifier in parentheses.

| | v4 (tranche 3 weights) | v5 (tranche 4 weights) |
|---|---|---|
| `gold_v2_slm_eval_holdout.csv` (1,055 rows, merchant-disjoint) leaf / general | 37.2% / 42.9% (T5: 37.1% / 42.9%) | **50.9% / 59.0%** (T5: 50.5% / 58.7%) |
| `gold_transactions_risk_categories.csv` (711 rows, held out) leaf / general | 67.2% / 76.2% (T5: 66.4% / 76.5%) | **76.8% / 82.1%** (T5: 75.7% / 82.6%) |
| Risk-category bar (619 gambling / credit-loan / high-cost rows) | 74.0% OK (T5: 73.0%) | **81.4% OK** (T5: 80.1%) |

Holdout **+13.7pp leaf**. Risk bar **+7.4pp**. T5 still slightly dilutes classifier-only accuracy on these gold sets (same pattern as the v4 addendum) because a handful of gold rows are T5-eligible with a different leaf than the gold label.

Scorer: `src/compare_classifier_versions.py`. Predictions: `outputs/classifier_v5_holdout_predictions.csv`, `outputs/classifier_v5_risk_predictions.csv` (T5-applied) and `outputs/classifier_v5_risk_clf_predictions.csv` (classifier only).

## Risk leaves of interest

Classifier-only, current risk gold file (row counts have moved since the v4 write-up — `payday_loan` is 7 rows here, not 20).

| Leaf | v4 | v5 |
|---|---|---|
| `cash_advance` | 20/20 | 20/20 |
| `charge_card_repayment` | 6/6 | 6/6 |
| `financial_services_other` | 5/8 | 5/8 |
| `gambling_unspecified` | 6/25 | **15/25** |
| `gambling_betting` | 71/93 | 78/93 |
| `gambling_bingo` | 9/31 | 11/31 |
| `personal_loan_repayment` | 14/24 | 19/24 |
| `payday_loan` | 3/7 | 2/7 |
| Gold gambling-family tagged as *some* gambling | 192/230 | 190/230 |

`gambling_unspecified` is the real serving-policy win from more labels (was the leaf the v4 confidence-gate was invented to cover). Bingo remains weak (17/31 → `transfer_p2p` in v5 — a new confusion, not unclassified). Payday is still not a classifier leaf; T5 R18/R19 remains the serving path.

## Addendum — SGD hinge SVM (same day)

Same TF-IDF features and training jsonl as logreg; `SGDClassifier(loss="hinge")`, 50 epochs. Scored via `decision_function` + the same gambling promote (`src/score_t5b_residual.py` `scores_and_margin`). Classifier-only:

| | logreg v4 | logreg v5 | hinge v4 | hinge v5 |
|---|---|---|---|---|
| Holdout leaf / general | 37.2% / 42.9% | 50.9% / 59.0% | 39.1% / 45.8% | **52.8% / 60.3%** |
| Risk set leaf / general | 67.2% / 76.2% | 76.8% / 82.1% | 70.6% / 77.5% | **80.6% / 85.5%** |
| Risk-category bar (n=619) | 74.0% | 81.4% | 79.2% | **86.1% OK** |

Hinge beats logreg on both weights dumps (~+2pp holdout, ~+4–5pp risk bar). `gambling_unspecified` 15/25 (logreg v5) → **20/25**; gambling-family recall 190/230 → **201/230**. Caveat: hinge has no `predict_proba`, so a confidence gate would use decision-function margin rather than a probability — the original bake-off picked logreg for that reason. Liblinear `LinearSVC` was not retrained on the 382k-row set.

Predictions: `outputs/classifier_v5_svm_holdout_predictions.csv`, `outputs/classifier_v5_svm_risk_predictions.csv`.

## Equifax dictionary top-up (asked the same day)

Not worth a 10k-merchant labelling tranche. Equifax has **6,518** distinct vendors in total. 610 are already exact T4 keys (37.4% of Equifax volume). The remaining 5,908 filled vendors are only **4.4%** of Equifax transactions; 58.2% have a blank vendor and cannot be helped by T4 at all.

"Top 10k rows worth" of residual volume is **one vendor** (`rainbow riches casino` with a non-breaking space — already in T4 under the clean key). Top 100 residual vendors are 1.14% of Equifax; top 500 are 2.92%. Live Plaid barely uses Equifax's canonical strings (`john lewis` 0 Plaid exact hits; `hello fresh` 0, while T4 already has `hellofresh`). Equifax is a dead dump; Plaid is live.

If Equifax historical coverage still matters for Experiment 3, the right next step is a **small alias pass** (nbsp/punctuation fold plus Equifax-name → existing T4 leaf for the top ~100–500 residual entities), not another LLM tranche.

## Addendum — provenance (same day, after this retrain)

The 91,803 “trusted-tier” figure above counted rows tagged `human_reviewed`. Almost all of those were agent consensus/tiebreak/review. Later the same day those rows were retagged (`human_reviewed` is now 4 Carlos rows; the rest are `agent_*`). Dictionary-eligible count is unchanged, so this retrain’s training set is the same merchants. Do not quote 91,803 as human-reviewed volume.

## Addendum — v5 locked gold retired (same day)

`gold_transactions_v5_LOCKED.csv` was not scored in this retrain and must not be scored later as confirmation gold: tranche 4 labelled 331 of its 952 merchants. Replacement is v6 (`src/build_gold_v6_locked.py`). Keep this CSV as reviewed labels; do not train on it.

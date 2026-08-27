# T5b residual gate — classifier vs T6 (remeasured 2026-08-27)

25 Aug numbers (n=695 Plaid residual, holdout hinge 39.1%) are history. This file is the post-91,822-dictionary remeasure: Plaid gold T6 residual **231**, holdout T6-bound hinge **57.7%**. Always-ML still beats T6; serving dumps not switched.

Question: on Plaid gold that **currently falls through T1–T5** to the provider crosswalk, does a margin-gated classifier beat T6, and does LinearSVC change that?

**Not scored:** locked confirmation sets (`gold_transactions_v5_LOCKED.csv` retired; `gold_transactions_v6_LOCKED.csv` once built).

## Population

Plaid gold pooled from `gold_transactions_v3_volume.csv` (Plaid slice) and `gold_transactions_v4_slm_volume.csv` (native category joined from `gold_v4_eyeball.csv`). 1800 Plaid gold rows; **231** are T6-bound after the current waterfall.

**Leakage (read this before quoting the 58%/79% figures).** v3 and v4 were added to `tuning_train.jsonl` via the unified gold file (`data/gold_transactions.csv`) in the v3/v4 classifier retrain. Always-ML on this residual is therefore an *in-sample, production-shaped* number — the right question for “should we serve this on repeated head traffic”, the wrong one for “how does it generalise to novel merchants”. The risk-set residual and the v2 holdout residual below are the leakage-free checks.

| waterfall tier | n | share of Plaid gold |
|---|---:|---:|
| T4_dictionary | 1505 | 83.6% |
| T6_native_fallback | 231 | 12.8% |
| T2_compound_hmrc_child_benefit | 16 | 0.9% |
| T2_compound_instore_atm | 9 | 0.5% |
| T2_compound_returned_payment | 9 | 0.5% |
| T1_direction_gambling_credit | 7 | 0.4% |
| T5_R02 | 5 | 0.3% |
| T2_compound_refund | 3 | 0.2% |
| T5_R11 | 2 | 0.1% |
| T2_compound_grocer_petrol | 1 | 0.1% |
| T2_compound_tesco_cafe | 1 | 0.1% |
| T5_R21 | 1 | 0.1% |
| T2_compound_sky_protect | 1 | 0.1% |
| T2_compound_instore_atm_deposit | 1 | 0.1% |
| T2_compound_asda_living | 1 | 0.1% |
| T2_compound_bolt_stackblitz | 1 | 0.1% |
| T2_compound_asda_mobile | 1 | 0.1% |
| T5_R29 | 1 | 0.1% |
| T5_R27 | 1 | 0.1% |
| T2_compound_ingle_store | 1 | 0.1% |
| T5_R01 | 1 | 0.1% |
| T2_compound_amazon_prime_video | 1 | 0.1% |

Models share the **same TF-IDF features** as `tfidf_logreg_v2.joblib` (char_wb 2–5 grams, 30k, + log1p(amount) + is_credit). The SVM head is `SGDClassifier(loss='hinge')` at the **same training budget** as logreg (alpha=1e-6, 50 epochs). liblinear `LinearSVC` was attempted and abandoned for this run (no fit after ~8 minutes on ~167k × 30k). Gate: top-1 minus top-2 on native scores (`predict_proba` for logreg, `decision_function` for the SVM). Gambling promotion matches `predict()`.

## Head-to-head on T6-bound rows with a Plaid native category

| model | n | leaf (always-ML) | general | T6 leaf | T6 general | ML risk bar | T6 risk bar |
|---|---:|---:|---:|---:|---:|---:|---:|
| tfidf_logreg_v2 | 231 | 68.0% | 71.9% | 17.7% | 40.7% | 50.0% (n=4) BELOW | 0.0% (n=4) |
| tfidf_linearsvm_sgd | 231 | 74.9% | 78.8% | 17.7% | 40.7% | 100.0% (n=4) OK | 0.0% (n=4) |
| tfidf_linearsvc_liblinear | 231 | 74.9% | 79.2% | 17.7% | 40.7% | 50.0% (n=4) BELOW | 0.0% (n=4) |

### By gold source

| model | source | n | always-ML leaf | T6 leaf |
|---|---|---:|---:|---:|
| tfidf_logreg_v2 | v3_plaid | 85 | 67.1% | 22.4% |
| tfidf_logreg_v2 | v4 | 146 | 68.5% | 15.1% |
| tfidf_linearsvm_sgd | v3_plaid | 85 | 74.1% | 22.4% |
| tfidf_linearsvm_sgd | v4 | 146 | 75.3% | 15.1% |
| tfidf_linearsvc_liblinear | v3_plaid | 85 | 70.6% | 22.4% |
| tfidf_linearsvc_liblinear | v4 | 146 | 77.4% | 15.1% |

## Margin gate (ML if margin ≥ threshold, else keep T6)

Coverage is the share of the T6 residual auto-served by ML, ranked by margin. `ML on served` is accuracy on that slice only. `Gated all` is the production metric: ML on the served slice, T6 on the rest.

### tfidf_logreg_v2

| auto-serve | margin ≥ | ML on served | T6 on that slice | gated (all residual) | risk on served |
|---|---:|---:|---:|---:|---|
| 50% | 0.4842 | 83.6% | 24.1% | 47.6% | 50.0% (n=2) |
| 70% | 0.2381 | 77.2% | 19.8% | 58.0% | 33.3% (n=3) |
| 80% | 0.1531 | 74.1% | 17.3% | 63.2% | 50.0% (n=4) |

First ≥10% coverage where ML-on-served beats T6-on-served by ≥1pp **and** gated end-to-end is ≥5pp above always-T6: **10%** (margin ≥ 0.9173; gated 25.5%).

Always-ML (68.0%) **beats every T6-fallback gate** on this population: T6 is only 17.7% leaf, so sending the uncertain tail back to the provider *lowers* accuracy. The serving rule is “ML, or abstain to unclassified”, not “ML or T6”.

Best gated leaf accuracy at coverage ≥30%: **68.8%** at 97% coverage (margin ≥ 0.0206; ML-on-served 69.3%).

- v3_plaid: always-ML 67.1% vs T6 22.4% (+44.7%)
- v4: always-ML 68.5% vs T6 15.1% (+53.4%)

### tfidf_linearsvm_sgd

| auto-serve | margin ≥ | ML on served | T6 on that slice | gated (all residual) | risk on served |
|---|---:|---:|---:|---:|---|
| 50% | 1.7453 | 87.9% | 22.4% | 50.6% | 100.0% (n=1) |
| 70% | 0.8211 | 86.4% | 18.5% | 65.4% | 100.0% (n=3) |
| 80% | 0.4938 | 85.4% | 18.4% | 71.4% | 100.0% (n=4) |

First ≥10% coverage where ML-on-served beats T6-on-served by ≥1pp **and** gated end-to-end is ≥5pp above always-T6: **10%** (margin ≥ 4.7571; gated 25.1%).

Always-ML (74.9%) **beats every T6-fallback gate** on this population: T6 is only 17.7% leaf, so sending the uncertain tail back to the provider *lowers* accuracy. The serving rule is “ML, or abstain to unclassified”, not “ML or T6”.

Best gated leaf accuracy at coverage ≥30%: **75.3%** at 88% coverage (margin ≥ 0.2309; ML-on-served 82.4%).

- v3_plaid: always-ML 74.1% vs T6 22.4% (+51.8%)
- v4: always-ML 75.3% vs T6 15.1% (+60.3%)

### tfidf_linearsvc_liblinear

| auto-serve | margin ≥ | ML on served | T6 on that slice | gated (all residual) | risk on served |
|---|---:|---:|---:|---:|---|
| 50% | 1.0789 | 94.0% | 16.4% | 56.7% | 100.0% (n=1) |
| 70% | 0.6287 | 87.0% | 15.4% | 68.0% | 100.0% (n=2) |
| 80% | 0.3535 | 83.2% | 15.7% | 71.9% | 66.7% (n=3) |

First ≥10% coverage where ML-on-served beats T6-on-served by ≥1pp **and** gated end-to-end is ≥5pp above always-T6: **10%** (margin ≥ 2.3757; gated 25.1%).

Always-ML (74.9%) **beats every T6-fallback gate** on this population: T6 is only 17.7% leaf, so sending the uncertain tail back to the provider *lowers* accuracy. The serving rule is “ML, or abstain to unclassified”, not “ML or T6”.

Best gated leaf accuracy at coverage ≥30%: **74.9%** at 100% coverage (margin ≥ 0.0124; ML-on-served 74.9%).

- v3_plaid: always-ML 70.6% vs T6 22.4% (+48.2%)
- v4: always-ML 77.4% vs T6 15.1% (+62.3%)

## Risk-category residual (T6-bound rows of the stratified risk set)

This set has no Plaid native category in the locked CSV, so it is **not** in the T6 head-to-head. T6-bound is still well-defined (T1–T5 did not fire). Most risk gold is dictionary-covered; the residual is the hard tail.

- tfidf_logreg_v2: n=88 residual, leaf 67.0%, risk-bar 72.1% (OK bar)
- tfidf_linearsvm_sgd: n=88 residual, leaf 73.9%, risk-bar 88.4% (OK bar)
- tfidf_linearsvc_liblinear: n=88 residual, leaf 42.0%, risk-bar 72.1% (OK bar)

## Merchant-disjoint holdout, T6-bound only

`data/gold_v2_slm_eval_holdout.csv` — merchants never seen in training. T6-bound = T1–T5 did not fire. Plaid native category is kept on the file so T6 can be scored on the Plaid slice (Equifax holdout rows use Equifax native, not Plaid).

| model | n T6-bound | ML leaf / general | Plaid n | ML on Plaid | T6 on Plaid |
|---|---:|---:|---:|---:|---:|
| tfidf_logreg_v2 | 428 | 54.9% / 62.1% | 275 | 55.3% / 63.3% | 17.5% / 36.4% |
| tfidf_linearsvm_sgd | 428 | 57.7% / 64.5% | 275 | 58.2% / 65.1% | 17.5% / 36.4% |
| tfidf_linearsvc_liblinear | 428 | 39.0% / 44.6% | 275 | 36.0% / 41.5% | 17.5% / 36.4% |


## What this does and does not decide

- **Does:** whether a gated linear model is already worth wiring as T5b on production-shaped T6 traffic, vs keeping T6.
- **Does not:** replace the merchant-disjoint holdout (~36% leaf) as a generalisation floor; does not score locked confirmation sets; does not authorise per-transaction LLM at runtime.
- Linear SVM is the same features, hinge instead of log loss. If it does not beat logreg on the gated metric, keep logreg.

Per-row predictions: `outputs/t5b_residual_predictions.csv`. Coverage curve: `outputs/t5b_residual_coverage_curve.csv`.

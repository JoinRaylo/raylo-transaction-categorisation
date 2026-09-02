# Classifier v6 (de-leaked training set) vs serving v5 hinge — 2026-09-02

**Why this exists.** The 2 Sep review found that `data/gold_transactions_risk_categories.csv`
was described as "held out of training" but 551/711 rows (77.5%) shared a merchant with
`outputs/tuning_train.jsonl` and 252 (35.4%) shared the exact merchant+description, because
Tier B fetches random Plaid rows for every tranche-4 merchant and the bookmakers/lenders in
the risk set are tranche-4 merchants. Every "risk bar 86.1%" quote was therefore in-sample.

**Fix.** `build_tuning_dataset.py` now excludes risk-gold merchants from Tier B, Tier A
training rows and the top-up (same mechanism as the frozen holdout). Rebuilt locally from the
cached `outputs/tuning_txns.json` (no BigQuery): 944 Tier B rows and 284 Tier A rows on 191
risk-gold merchants removed; jsonl **383,066 → 381,560**. Holdout MD5
`7456da977a2c761119368637658232b6` unchanged. Fresh TF-IDF + SGD hinge (same recipe as v5,
`retrain_corrected_heads.py --hinge-only`) → `outputs/distill_models/tfidf_linearsvm_sgd_v6_deleaked.joblib`.
Serving dump (`tfidf_linearsvm_sgd.joblib`, v5) **not** overwritten.

## Scores (`compare_classifier_versions.py`, classifier only, no T5 override)

| Set | Model | leaf | general | risk-leaf acc (n) | credit leaf (n) | credit-bar (n) |
|---|---|---:|---:|---:|---:|---:|
| Holdout (1,055, merchant-disjoint) | v5 serving (risk leaked) | 53.9% | 61.0% | 58.7% (104) | 20.4% (103) | 16.1% (93) |
| Holdout | **v6 de-leaked** | **56.0%** | **62.8%** | 55.8% (104) | **43.7%** (103) | **41.9%** (93) |
| Risk gold (711) | v5 serving (risk leaked) | 80.6% | 85.5% | **86.1% (619) — in-sample** | 44.1% (68) | 18.4% (38) |
| Risk gold (711) | **v6 de-leaked** | 59.8% | 65.4% | **62.7% (619) — FAIL vs 70% bar** | 52.9% (68) | 18.4% (38) |

With the T5 override (`clf+T5`): holdout v6 56.6% leaf; risk v6 62.6% leaf, risk bar 65.9% (still FAIL).

### What T5b actually serves (T6-bound rows only)

| Set | Model | T6-bound n | leaf | risk-leaf rows n | acc |
|---|---|---:|---:|---:|---:|
| Risk gold | v5 serving | 89 | 67.4% | 40 | 77.5% |
| Risk gold | v6 de-leaked | 89 | 64.0% | 40 | 77.5% |
| Holdout | v5 serving | 418 | 58.4% | 33 | 60.6% |
| Holdout | v6 de-leaked | 418 | 56.9% | 33 | 57.6% |

87.6% of risk-gold merchants are in the T4 dictionary, so the classifier never sees them in
the real waterfall; the 89 T6-bound rows are the slice that matters for serving.

## Read

1. **The honest risk bar for the classifier is ~63%, not 86%.** The 23-point gap is
   memorisation of risk-gold merchants that were in training. Every serving-head and
   v5b/v5c/v5d decision was taken on the leaked number; the *ranking* of those decisions is
   not re-litigated here, but none of them should be quoted as "risk bar 86%".
2. **Holdout improves** (53.9 → 56.0 leaf) and **credits improve a lot** (20.4 → 43.7%) with a
   fresh TF-IDF on the de-leaked file — the vocabulary re-fit matters more than the 1,506
   removed rows; treat the credit jump as fragile until the credit tranche exists.
3. **On the rows T5b actually serves (T6-bound), v5 and v6 are within noise** (n=89 / 418).
   There is no serving reason to switch dumps today; the fix changed the *measurement*, not
   the model's behaviour on novel merchants.
4. **Remedy is data, not tuning:** the review's Week 2–3 items (row-level credit tranche;
   T6-bound risk rows into gold; direction-aware T4) are what move a 63% risk bar. Do not
   tune the abstain margin or oversampling against this set to recover 70% — that would
   re-leak it through the back door.

## Decisions

- Serving stays `tfidf_linearsvm_sgd.joblib` (v5 weights) for now; `_v6_deleaked` is the
  reference dump for all future risk-bar quotes. Re-score any candidate head against v6, not v5.
- `compare_classifier_versions.py` and `confusion_analysis.py` now print per-direction accuracy
  and a credit-side bar (13 income/transfer leaves, 70%) alongside the risk bar.
- Locked v5/v6 gold not scored.

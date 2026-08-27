# Frontier LLMs vs serving hinge (v5)

Scored 2026-08-27. **Framing only** — Gemini 3.7 Flash and Sonnet 5 are not
candidates for per-transaction runtime. Same finalized prompt as CLAUDE.md §6a
(90,516 chars: taxonomy + TAIL_ADDENDUM + full worked-example notes).
Unique fingerprints labelled once, then joined to holdout / risk / pipeline.
Serving hinge is `outputs/distill_models/tfidf_linearsvm_sgd.joblib` (v5).
Locked v5/v6 were not scored.

## Headline

The serving linear SVM is in the same band as a frontier model **once T1–T5 have already fired** (80.5% vs Gemini 84.2% on the 1,884-row pipeline). On novel merchants and on the leftover those rules miss, Gemini is still well ahead (holdout **83.9% vs 53.9%**; leftover **73.0% vs 59.2%**). That gap is expected: the classifier is a local TF-IDF head, not a production LLM.

Leaf accuracy, 4-field input, same gold as the classifier scorers:

| Set | n | hinge v5 | Gemini 3.7 Flash | Sonnet 5 |
|---|---:|---:|---:|---:|
| Holdout (merchant-disjoint) | 1,055 | 53.9% | **83.9%** | 79.1% |
| Holdout T6-bound | 428 | 57.7% | **73.6%** | 67.3% |
| Risk gold (LLM-drafted; favours Gemini/Sonnet) | 711 | 80.6% | **86.6%** | 82.8% |
| Pipeline leftover (T1–T5 miss) | 500 | 59.2% | **73.0%** | 67.4% |
| T1–T5 then model (pipeline n=1,884) | 1,884 | 80.5% | **84.2%** | 82.7% |

Prompt: **90,516** chars / **465** worked notes (taxonomy + TAIL_ADDENDUM + examples). Bulk T4 provenance notes (`Luna A + parent review`, `Carlos review 2026-08-26`, …) were excluded so this matches the §6a labelling guide rather than the 1,026-note dictionary dump. Scorer: `src/score_frontier_vs_classifier.py`.

### Holdout (merchant-disjoint, n=1,055) — iteration suite

n=1055

- **hinge v5:** leaf 53.9% / general 61.0% / risk bar 58.7% (n=104)  n=1055
- **Gemini 3.7 Flash:** leaf 83.9% / general 90.0% / risk bar 85.6% (n=104)  n=1055
- **Sonnet 5:** leaf 79.1% / general 84.5% / risk bar 76.9% (n=104)  n=1055

### Holdout T6-bound (T1–T5 miss)

n=428

- **hinge v5:** leaf 57.7% / general 64.5% / risk bar 60.6% (n=33)  n=428
- **Gemini 3.7 Flash:** leaf 73.6% / general 84.3% / risk bar 72.7% (n=33)  n=428
- **Sonnet 5:** leaf 67.3% / general 74.8% / risk bar 57.6% (n=33)  n=428

### Risk gold — iteration suite (Gemini/Sonnet drafted some of these; mildly favours them)

n=711

- **hinge v5:** leaf 80.6% / general 85.5% / risk bar 86.1% (n=619)  n=711
- **Gemini 3.7 Flash:** leaf 86.6% / general 94.0% / risk bar 91.4% (n=619)  n=711
- **Sonnet 5:** leaf 82.8% / general 89.9% / risk bar 90.0% (n=619)  n=711

### Pipeline eval (row-disjoint, n=1,884) — 4-field model vs gold, no T1–T5

n=1884

- **hinge v5:** leaf 63.3% / general 70.0% / risk bar 76.9% (n=562)  n=1884
- **Gemini 3.7 Flash:** leaf 85.7% / general 91.7% / risk bar 89.0% (n=562)  n=1884
- **Sonnet 5:** leaf 81.8% / general 87.3% / risk bar 86.7% (n=562)  n=1884

### Pipeline leftover (T1–T5 miss) — where a runtime classifier would serve

n=500

- **hinge v5:** leaf 59.2% / general 66.2% / risk bar 67.3% (n=49)  n=500
- **Gemini 3.7 Flash:** leaf 73.0% / general 82.6% / risk bar 79.6% (n=49)  n=500
- **Sonnet 5:** leaf 67.4% / general 74.2% / risk bar 69.4% (n=49)  n=500

## Pipeline: T1–T5 then model

Same 1,884 rows as `data/waterfall_pipeline_report.md`. Deterministic tiers
keep the waterfall leaf; leftover rows take the model prediction.

- **T1–T5 then hinge v5:** leaf 80.5% / general 86.4% / risk bar 87.0% (n=562)  n=1884
- **T1–T5 then Gemini 3.7 Flash:** leaf 84.2% / general 90.8% / risk bar 88.1% (n=562)  n=1884
- **T1–T5 then Sonnet 5:** leaf 82.7% / general 88.5% / risk bar 87.2% (n=562)  n=1884

## Caveats

- Risk gold was drafted by Gemini+Sonnet before human review, so those two
  models are mildly favoured on that set. Holdout is the clean comparison.
- Gemini temperature=0 is not fully deterministic; this is a single run.
- Do not serve either LLM at runtime. The gap is the cost of a local linear
  head vs a frontier call, not a reason to put Gemini/Sonnet in the waterfall.

Predictions cache: `outputs/frontier_vs_clf_unique.csv`.


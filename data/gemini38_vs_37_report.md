# Gemini 3.8 Flash vs Gemini 3.7 Flash

Scored 2026-09-03. **Framing / labelling-stack bake-off only** — not a
runtime candidate. 3.7 labels are reused (not re-called): the 27 Aug
frontier unique-fingerprint cache (`outputs/frontier_vs_clf_unique.csv`).
Locked v5/v6 were not scored. Production labelling still uses 3.7 until
this bake-off is acted on.

Harness matches `src/score_frontier_vs_classifier.py`: finalized labelling
prompt (90,479 chars: taxonomy + TAIL_ADDENDUM + notes),
batch-of-25, JSON category-index schema, `temperature=0`, model `gemini-3.8-flash`.

## Headline

**Keep Gemini 3.7 Flash.** 3.8 is a statistical tie on the clean holdout and
slightly worse on every other cut; it is also ~3× slower.

On the merchant-disjoint holdout (n=1,055), Gemini 3.8 Flash is **83.7%** leaf /
90.2% general vs saved 3.7 **83.9%** / 90.0% (leaf Δ −0.2%; McNemar 3.7-only 16 /
3.8-only 14, two-sided p≈0.855). Label agreement 95.3%. No cut excludes a tie;
do not switch `production_labelling.py`.

| Set | n | Gemini 3.7 Flash (saved) | Gemini 3.8 Flash |
|---|---:|---:|---:|
| Holdout (merchant-disjoint) | 1055 | 83.9% | 83.7% |
| Holdout T6-bound (T1–T5 miss) | 404 | 72.8% | 71.0% |
| Risk gold (Gemini/Sonnet drafted some; mildly favours them) | 711 | 86.6% | 85.5% |
| Pipeline eval (row-disjoint, 4-field, no T1–T5) | 2004 | 86.0% | 85.5% |
| Pipeline leftover (T1–T5 miss) | 416 | 72.8% | 71.2% |
| T1–T5 then model (pipeline) | 2004 | 85.2% | 84.9% |

3.8 wall-clock: **1,855 s** (1.08 rows/s) vs 3.7's 598 s (3.35 rows/s) on the
same 2,004 unique rows. 3.8 thinks more by default at `temperature=0`.

### Holdout (merchant-disjoint)

n=1055

- **Gemini 3.7 Flash (saved):** leaf 83.9% / general 90.0% / risk bar 85.6% (n=104)  n=1055
- **Gemini 3.8 Flash:** leaf 83.7% / general 90.2% / risk bar 86.5% (n=104)  n=1055

leaf Δ -0.2%; label agreement 95.3%; McNemar 3.7-only 16 / 3.8-only 14 / both-right 869 / both-wrong 156 (two-sided p≈0.855)

### Holdout T6-bound (T1–T5 miss)

n=404

- **Gemini 3.7 Flash (saved):** leaf 72.8% / general 84.2% / risk bar 71.9% (n=32)  n=404
- **Gemini 3.8 Flash:** leaf 71.0% / general 83.2% / risk bar 71.9% (n=32)  n=404

leaf Δ -1.7%; label agreement 92.1%; McNemar 3.7-only 12 / 3.8-only 5 / both-right 282 / both-wrong 105 (two-sided p≈0.146)

### Risk gold (Gemini/Sonnet drafted some; mildly favours them)

n=711

- **Gemini 3.7 Flash (saved):** leaf 86.6% / general 94.0% / risk bar 91.4% (n=619)  n=711
- **Gemini 3.8 Flash:** leaf 85.5% / general 94.0% / risk bar 91.3% (n=619)  n=711

leaf Δ -1.1%; label agreement 97.3%; McNemar 3.7-only 13 / 3.8-only 5 / both-right 603 / both-wrong 90 (two-sided p≈0.099)

### Pipeline eval (row-disjoint, 4-field, no T1–T5)

n=2004

- **Gemini 3.7 Flash (saved):** leaf 86.0% / general 92.0% / risk bar 89.8% (n=676)  n=2004
- **Gemini 3.8 Flash:** leaf 85.5% / general 92.1% / risk bar 90.1% (n=676)  n=2004

leaf Δ -0.5%; label agreement 96.4%; McNemar 3.7-only 31 / 3.8-only 20 / both-right 1693 / both-wrong 260 (two-sided p≈0.161)

### Pipeline leftover (T1–T5 miss)

n=416

- **Gemini 3.7 Flash (saved):** leaf 72.8% / general 84.1% / risk bar 71.9% (n=32)  n=416
- **Gemini 3.8 Flash:** leaf 71.2% / general 83.2% / risk bar 71.9% (n=32)  n=416

leaf Δ -1.7%; label agreement 92.3%; McNemar 3.7-only 12 / 3.8-only 5 / both-right 291 / both-wrong 108 (two-sided p≈0.146)

## Pipeline: T1–T5 then model

Deterministic tiers keep the waterfall leaf; leftover rows take the model.

- **T1–T5 then Gemini 3.7 Flash (saved):** leaf 85.2% / general 91.4% / risk bar 90.1% (n=676)  n=2004
- **T1–T5 then Gemini 3.8 Flash:** leaf 84.9% / general 91.2% / risk bar 89.9% (n=676)  n=2004

## Verdict

Reuse 3.7 for labelling. 3.8 does not buy accuracy on this task, costs more
latency, and the holdout disagreement is 30 rows of ordinary leaf-boundary
noise (department vs discount store, software vs online services), not a
systematic fix. A `thinking_level=LOW` rerun is not warranted unless we need
the speed back and already know accuracy is flat.

## Caveats

- Single 3.8 run vs a single saved 3.7 run. The published 3.7 holdout is the
  23 Aug 3-run average **84.2% ± 0.15pp**; the 27 Aug cache can differ by ~1pp.
- Drop-in model-id swap at `temperature=0` (both models think by default).
- Risk gold was drafted by Gemini 3.7 + Sonnet; holdout is the clean cut.
- Do not serve either model at runtime.

3.8 predictions: `outputs/mlx_full_run/gemini38_frontier_preds.csv`.
Scorer: `benchmarks/score_gemini38_vs_37.py`.

## Secondary: 23 Aug holdout CSV

Saved `gemini37_finalprompt_predictions.csv`: leaf **84.1%** / general 90.8% (n=1055). One of the three runs behind 84.2%.
Prompt then was 84,348 chars; today's prompt is longer. Prefer the
frontier-cache comparison (same 27 Aug construction).


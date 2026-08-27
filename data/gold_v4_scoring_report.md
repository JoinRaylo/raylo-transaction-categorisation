# Gold v4 scoring report — the LLM tier on production-shaped volume (2026-08-23)

Scored `data/gold_transactions_v4_slm_volume.csv` (900 rows, true-random over the
**unmatched-Plaid** population, volume-weighted within that residual, fully
human-reviewed) with the finalized standard prompt (84,348 chars: taxonomy +
loan-keyword bugfix + full 375 worked examples). Harness: `src/score_gold_v4.py`
(same batch-of-25, forced-structured-output design as the v2-holdout benchmark).

The 18,825-entry dictionary and 40.4% T4-covered share below are **as of this
scoring**. Live T4 is 91,173 keys as of 26 Aug 2026 (Plaid T4 52.1% of all rows);
this report was not re-run.

Two population cuts matter:

- **ALL 900 rows** — the whole unmatched-Plaid population.
- **POST-T4 RESIDUAL (n=536)** — rows whose merchant is NOT in the current
  18,825-entry T4 dictionary. 364/900 (40.4%) of the unmatched population is
  already dictionary-covered, so in production those rows never reach the LLM
  tier; the residual cut is the LLM tier's true serving population.

## Results (leaf % / general %)

| Scorer | ALL (n=900) | Post-T4 residual (n=536) |
|---|---|---|
| **Consensus gate (Gemini+Sonnet agree, Opus tiebreak)** — on accepted rows | **89.9 / 93.3** (96.4% accepted) | **86.6 / 90.5** (94.4% accepted) |
| Consensus end-to-end (abstain counted wrong) | 86.7 / 90.0 | 81.7 / 85.4 |
| Gemini==Sonnet agreement subset only (78.6% coverage) | 95.6 leaf | — |
| Gemini 3.7 Flash (single model) | 88.3 / 93.1 | 83.8 / 89.7 |
| Claude Opus 5 (single model) | 85.9 / 89.6 | 81.9 / 85.8 |
| Claude Sonnet 5 (single model) | 80.0 / 85.8 | 72.4 / 80.0 |
| TF-IDF + logreg v2 (runtime classifier candidate) | 59.0 / 62.2 | 49.4 / 53.4 |
| Plaid native category (crosswalked) | 16.9 / 44.9 | 18.7 / 41.4 |

Model throughput on this run: Gemini 3.7 Flash 3.7 rows/sec, Opus 3.8, Sonnet 4.5
(batch-of-25, single worker, no concurrency).

## What this settles

1. **Option 1 (Gemini 3.7 + Sonnet consensus, Opus tiebreak) is confirmed on the
   production population.** Gemini leads every cut, exactly as on the v2 holdout.
   The consensus gate accepts 94–96% of rows at ~87–90% leaf accuracy, and the
   no-tiebreak Gemini==Sonnet subset is a 95.6%-precision tier covering 78.6% of
   rows. The `production_labelling.py` refactor can proceed as scoped.
2. **Volume-weighting flips the classifier story.** TF-IDF v2 scores 59.0% here vs
   32.0% on the merchant-disjoint v2 holdout — high-volume merchants repeat, and
   the classifier has memorised the labelled head. Its generalization floor is
   still weak (49.4% on the residual), but as a *runtime* tier over production-
   shaped traffic it is far more useful than the holdout number implied.
3. **Plaid native categories are near-useless on this population** (16.9% leaf) —
   worse than the whole-population v3 figure (32.5%), as expected: the unmatched
   residual is precisely where Plaid's own resolution fails.
4. **Where errors concentrate (Sonnet, but the pattern is shared):** roughly half
   the errors are either over-abstention (`unclassified_other` chosen where the
   human found an answer — transfers, takeaway, card repayments) or the
   groceries/convenience_store boundary. Both are addressable: the first with
   abstention-calibration examples, the second is a genuinely fuzzy convention
   boundary that mostly stays within the same general category.

## Measurement caveats (read before quoting)

- **Drafting bias:** v4's gold labels were drafted by Haiku+Sonnet before human
  review, so Sonnet's score is structurally favoured on the 568 human-*confirmed*
  agreement rows. Sonnet nonetheless scores LOWEST of the three — so the review
  was clearly not a rubber stamp, and the bias, if any, is not driving the
  ranking. Gemini and Opus scores are clean of this bias (neither drafted).
- **Prompt leakage split:** 364/900 rows' merchants appear verbatim in the
  prompt's worked examples/dictionary notes (this set coincides with the
  dictionary-covered rows, since the examples are drawn from the dictionary).
  Per-model "prompt-clean" numbers (equivalent to the residual cut): Gemini
  83.8/89.7, Opus 81.9/85.8, Sonnet 72.4/80.0.
- The residual cut is defined by *exact-string* dictionary membership, matching
  how the SQL T4 join works today.

Per-row predictions: `outputs/mlx_full_run/v4_{gemini,sonnet,opus}_predictions.csv`.

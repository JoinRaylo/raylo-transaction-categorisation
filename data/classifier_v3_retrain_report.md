# Classifier retrain report — 2026-08-24

Retrained `tfidf_logreg_v2.joblib` for the first time since 2026-08-21, adding
`gold_transactions_v3_volume.csv` (1,213 rows) and `gold_transactions_v4_slm_volume.csv`
(843 rows) as training-only supplementary data — 2,056 new rows, none of which
existed when this classifier was last trained. Deliberately excluded from
training: `gold_transactions_risk_categories.csv` (reserved as a clean eval for
this exact retrain) and `gold_transactions_v5_LOCKED.csv` (never touched by
training or scoring — see CLAUDE.md §12).

**Protected asset check**: `data/gold_v2_slm_eval_holdout.csv` is verified
byte-identical (MD5 match) before and after rebuilding the training set — the
new v3/v4 rows go straight to training via a separate path, never touching the
merchant-level holdout carve-out. Every §6a benchmark number stays comparable.

## Headline result: real improvement overall

| | Before (2026-08-21 model) | After (this retrain) |
|---|---|---|
| `gold_v2_slm_eval_holdout.csv` (unchanged, 1,057 rows) leaf / general | 32.0% / 37.6% | **37.4% / 43.9%** |
| `gold_transactions_risk_categories.csv` (711 rows, held out of training) leaf / general | not previously measured | **64.3% / 69.1%** |

+5.4pp leaf accuracy on the exact same holdout from adding 2,056 rows — a real,
measurable win from more labelled data, consistent with the "grow the
labelled corpus, don't hand-optimise the dictionary" direction agreed
2026-08-23/24.

## Critical finding: risk-category minimum bar FAILS (68.2% vs 70% bar)

Per the policy in CLAUDE.md §12, this is a required action item, not a
footnote — the 64.3% aggregate risk-category number hides it completely.

| Leaf | Training examples | Result on the held-out risk-category set |
|---|---|---|
| `cash_advance` | **0** | 100% wrong (20/20) |
| `charge_card_repayment` | **1** | 100% wrong (6/6) |
| `financial_services_other` | 5 | 100% wrong (8/8) |
| `gambling_unspecified` | 104 | 100% wrong (25/25) — defaults to `unclassified_other` |
| `gambling_bingo` | 284 | 74% wrong |
| `payday_loan` | 76 | 60% wrong |
| `revolving_credit_repayment` | 22 | 52% wrong |
| `debt_collection` | 436 | 39% wrong |

Two distinct causes, needing two distinct fixes:

1. **Zero/near-zero training-data leaves** (`cash_advance`, `charge_card_repayment`,
   `financial_services_other`) — the classifier has never seen these classes at
   all. Straightforward to fix: extend `data/tuning_leaf_topup.csv` (currently
   112 rows, the existing thin-leaf top-up mechanism) with real training
   examples for these specific leaves, sourced the same way the risk-category
   *eval* set was built (dictionary + narrative-keyword search) but routed to
   **training**, not held out.
2. **`gambling_unspecified` despite 104 examples** — genuinely the hardest
   class by construction (the catch-all for "gambling but subtype unclear"),
   outnumbered ~4:1 by `gambling_betting` in training. The model defaults to
   abstaining (`unclassified_other`) rather than confidently mislabelling a
   specific subtype, which is a safer failure mode than the alternative, but
   it means the classifier currently cannot serve this leaf at runtime at all.
   More training examples might help, but this may also need a runtime policy
   change: gate risk-category classifier predictions on confidence, and route
   low-confidence risk-leaf predictions elsewhere (dictionary miss → LLM
   queue) rather than trusting classifier argmax the way we might for a
   low-stakes retail category.

## Recommendation

Do not yet trust the classifier's fallback tier for risk-flagged categories
at runtime. Next concrete step: build targeted **training** data (not eval —
that already exists) for the zero/near-zero-example risk leaves, re-train,
re-check against `confusion_analysis.py`'s risk-category bar. This is now the
highest-leverage, cheapest next action given everything measured so far.

Per-row predictions: `outputs/classifier_v3_holdout_predictions.csv`,
`outputs/classifier_v3_risk_predictions.csv`.

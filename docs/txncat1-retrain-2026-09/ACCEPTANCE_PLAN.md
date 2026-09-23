# TxCat-1 retrain: predeclared acceptance plan

Status: **confirmed by Carlos on 2026-09-23, before any candidate was trained or
scored.** He accepted the three training-data decisions and the acceptance
criteria as written. The plan is now frozen: it may only be changed by a dated
amendment made *before* the affected scores are seen.

## What changes and what stays fixed

**Changes (the only behavioural change under test): TxCat-1.** That is the
DistilBERT classifier head (serving T6) and its hinge fallback, retrained from
rebuilt data:

- **Encoder.** Rebuilt from the guarded pretraining corpus
  (`build_pretrain_guarded.py`). No benchmark customer, account or transaction,
  and no benchmark narrative, is in it.
- **Training data.** Rebuilt under the training-data protection gate (3,295-row
  benchmark membership) with the shared labelling conventions
  (`raylo_txncat.label_conventions`) applied.
- **Recipe.** Same as serving: MLM encoder → consensus stage → gold stage, three
  seeds (42, 7, 123), same hyperparameters, masks rebuilt from the new training
  set.

**Fixed:**

- the waterfall rules, dictionary and T2 collisions of the staging bundle
  `1b402aeb…` (REVIEW-NOTES-001);
- the taxonomy;
- the serving code and thresholds (margin-0 T7 abstention);
- the classifier head configuration (transformer primary, hinge fallback).

A separate change record is needed for any rule change.

## Training-data decisions (confirmed 2026-09-23)

1. **The registered gold sets stay out of training.** `eval_registry.json` marks
   every registered set `exclude_from: supervised_training`, but the serving
   recipe trained on the `role=train` rows of `gold_transactions` (Tier A, 3,956
   rows). *Proposed:* follow the registry and drop Tier A from training. The
   gold sets then remain clean regression evaluations rather than partly-trained
   ones.
2. **Human and LLM labels that conflict with the rules.**
   - *Proposed:* where T1–T5 decides a row, LLM and merchant-level labels
     (Tier B, top-ups, consensus stage) take the rule's leaf. Serving never sends
     those rows to the model, so training on a different leaf only adds
     conflicting signal.
   - Human labels are not overridden by rules; conflicts are listed for review.
   - The shared conventions (`label_conventions`) apply to every source.
3. **Rows without IDs** (top-ups, legacy labels). Carlos approved ID recovery
   against BigQuery; rows that cannot be matched to exactly one transaction are
   dropped.

## Model selection (never uses the benchmark)

- **Seed.** Choose it with the existing policy: median seed on the validation
  split of the rebuilt training data (merchant-disjoint, as today). One
  selection, recorded before any benchmark scoring.
- **Epoch.** Best epoch per seed on the same validation split, as today.
- The benchmark, registered gold sets and locked sets are **not** used for
  selection, early stopping, thresholds or recipe choices. The locked v6 set
  stays locked.

## Evaluation

The candidate bundle is the staging bundle's rules plus the retrained TxCat-1.
It is compared with the staging bundle `1b402aeb…` on:

1. **The benchmark,** 3,295 rows once the expansion labels are final. Slices are
   reported separately, never pooled into one headline:
   - production-facing weighted slice;
   - unseen input;
   - unfamiliar merchant;
   - rare-leaf rows (row-level and merchant-group macro);
   - rows that reach T6 (where the change acts).

   Every slice is reported with and without the rule-exposed rows. The 1,295
   expansion rows were never used for development, so they are also reported
   alone as the **confirmation cohort**.
2. **The full repeatable suite**: 16 datasets, 92 views, the same harness.

## Acceptance criteria (all must hold)

Intervals are 95% customer-cluster bootstrap. Each difference is candidate minus
the staging bundle, on the same rows.

| # | Criterion | Threshold |
|---|---|---|
| A1 | Benchmark production-facing weighted leaf accuracy, T6-reaching rows | improvement, with the lower bound of the paired difference ≥ −1.0 pp |
| A2 | Benchmark production-facing weighted leaf accuracy, all rows | difference ≥ −0.5 pp |
| A3 | Confirmation cohort (1,295 expansion rows) leaf accuracy | difference ≥ −1.0 pp; must not contradict the direction of A1 |
| A4 | Risk leaves (`gold_transactions_risk_categories`, `gold_transactions_risk_t6bound`, benchmark risk leaves) | no increase in risk false negatives; risk-leaf correct count not lower by more than 1% |
| A5 | Salary precision on every set with salary gold | non-decreasing |
| A6 | `gold_credit_eval` serving transformer accuracy | difference ≥ −0.5 pp |
| A7 | Registered transaction development sets (serving Plaid, transformer) | no set drops by more than 1.0 pp; every right→wrong transition class explained |
| A8 | Rare-leaf rows | no drop in merchant-group macro accuracy |
| A9 | Parity, startup and tests | research/app parity, real-model startup and all test suites pass |
| A10 | Protection | every training input carries a verified receipt under the pinned release; bundle promotion provenance passes |

A candidate that fails any criterion is rejected and recorded, not re-tuned
against these sets. A second attempt needs a new predeclared record.

## What this plan cannot show

- The benchmark rules came from reviewing the benchmark. T1–T5 gains on the
  exposed rows are diagnostics, and the model change is measured mainly on
  T6-reaching and unexposed rows.
- Historical non-use of benchmark rows before protection existed cannot be
  certified. That covers the old encoder, which is being replaced, and old
  labels, which are dropped or re-matched.
- Production (Taktile) traffic, capacity and BigQuery delivery have their own
  acceptance gates.

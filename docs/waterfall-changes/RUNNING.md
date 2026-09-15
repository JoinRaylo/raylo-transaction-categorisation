# Run and compare waterfall evaluations

`run_evaluations.py` executes the full repeatable inventory, app/library and
research tests, lint/schema checks, broad deterministic parity, real-model startup
and independent metric verification. The runtime policy is unchanged: selected
transformer seed 123, hinge v8 and margin 0.0. Inference refuses degradation and
uses a fixed clock so this measures quality, not capacity or transport.

The checked-in `evaluation_inventory.json` extends the frozen 16-entry registry
with the existing 2,000-row `outputs/gold_pipeline_eval.csv` benchmark, pinned by
hash. The union has 15 repeatable data sets and two excluded confirmation sets.
Use the union's exclusion metadata for future data consumers. Do not regenerate
this historical benchmark against current training data or alter the frozen
bundle's registry as part of a rule correction.

The runner additionally evaluates seven synthetic examples separately. They
capture the five requested merchant transactions and two explicit refund/payroll
narratives. The bare Waitrose credits have user-specified intended meanings but
insufficient visible context to infer those meanings reliably. These diagnostics
are not representative accuracy evidence or justification for an amount threshold.

## Baseline command

Run from the monorepo root using the frozen app environment (Python 3.12 and the
model dependencies). Research code tests use the research environment, which also
needs pandas; its interpreter and package versions are recorded separately.

```sh
export TXNCAT_RESEARCH_ROOT=/path/to/raylo-transaction-categorisation
export TXNCAT_RESEARCH_PYTHON="$TXNCAT_RESEARCH_ROOT/.venv/bin/python"
export TXNCAT_BUNDLE=/path/to/verified-bundle
export TXNCAT_BUNDLE_SHA=a2553f3462205963254b0fb1ad9dff6d64e1399abdecaab93977265908c7f23d
export TXNCAT_EVAL_OUTPUT=/private/tmp/txncat-new-baseline

PYTHONPATH="$PWD/apps/ob-txn-categoriser/src:$PWD/lib/raylo-txncat/src" \
uv run --frozen --package ob-txn-categoriser python \
  apps/ob-txn-categoriser/scripts/run_evaluations.py \
  --monorepo-root "$PWD" \
  --research-root "$TXNCAT_RESEARCH_ROOT" \
  --research-python "$TXNCAT_RESEARCH_PYTHON" \
  --bundle "$TXNCAT_BUNDLE" --bundle-sha "$TXNCAT_BUNDLE_SHA" \
  --output "$TXNCAT_EVAL_OUTPUT"
```

The directory must be empty and outside both repositories. A missing file,
unknown/changed hash, missing required view, row-count mismatch, failed check or
independent metric disagreement stops the run. Interrupted runs remain incomplete.
No network or cloud credentials are needed for accuracy scoring once the runtime
environment and bundle are present. No Docker Desktop is used.

For the research entrypoint, use the identical scripts in
`tools/waterfall-evaluation/` instead of `apps/ob-txn-categoriser/scripts/`, retaining
the app environment, PYTHONPATH and explicit `--monorepo-root`. Both copies load
the same shared app/library implementation rather than independently reimplementing
the serving pipeline. The research source definitions must match bundle provenance.

## Candidate comparison

Run the same command against the candidate checkout/bundle, adding:

```sh
--baseline /private/tmp/txncat-previous-complete-run
```

Use a fresh output directory. Keep the completed baseline directory and its private
`rows.jsonl`; its digest is required for a paired comparison. The tool verifies
identical row identities, input hashes, labels, views and metric definitions.
Changing the harness, taxonomy rollup or input inventory requires rerunning the
baseline under the new evaluation definition, not comparing incompatible scores.

The JSON contains baseline/candidate/delta metrics, all prediction/rule/tier
transitions and a **fixed baseline residual** cohort. `changed_rows.jsonl` retains
the rows needing review. The full per-leaf scores and all slices are in each
run's summary. A successful execution does not automatically approve a candidate:
review all regressions and the predeclared acceptance criteria in POLICY.md.

## Artefacts and mirroring

- Commit `README.md`, `summary.json`, `validation.json` and relevant check receipts
  in a new dated directory under `waterfall-changes/` in both repositories.
- Verify byte-for-byte equality of the mirrored scripts, inventory, synthetic
  fixtures, reports and score files. Add a score-history row and update the
  research README/CLAUDE current-results pointer.
- Keep `rows.jsonl`, `changed_rows.jsonl` and command logs outside the repositories.
  Rows contain source positions and category diagnostics, not merchant/narrative
  text, but remain private evaluation evidence.
- Preserve every prior run and its hashes. The bundle manifest pins every model,
  dictionary, rule, taxonomy and mask file; the report also hashes both repos'
  implementation/tests, environment locks and all evaluator helpers.

Independent verification is built into the runner. It can also be repeated on
an existing completed run:

```sh
PYTHONPATH="$PWD/lib/raylo-txncat/src" \
uv run --frozen --package ob-txn-categoriser python \
  apps/ob-txn-categoriser/scripts/verify_evaluation_report.py \
  /private/tmp/txncat-complete-run --research-root "$TXNCAT_RESEARCH_ROOT"
```

This independently recounts all view totals with the original research confusion
analyser and scikit-learn precision/recall/F1. It never imports the research
module's top-level I/O or reads a confirmation set. Research integrity tests retain
their existing retired-v5 membership check; that is not accuracy scoring.

## Data limitations

Every registered repeatable set is accounted for. Merchant-only data scores the
dictionary; validation scores heads; the old risk set without provider fields
scores heads and its historical head+T5 view. Their full-waterfall status is
explicitly unsupported, even when the supported task passed. V4 transaction
context is recovered by a checked exact-input join to its registered eyeball
export. Original blank native categories remain blank; no values are inferred.

Historical overlap, training roles and prior tuning mean these are regression
benchmarks. Keep sets, providers and label provenance separate. Research pipeline
scores retain unclassified subtype strings; serving T7 scores use null. The
September research headline used three seeds; a seed-123 baseline is a different
comparison and must not be described as a gain over that mean.

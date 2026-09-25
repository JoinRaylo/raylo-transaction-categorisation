# Waterfall change and evaluation policy

Effective 15 September 2026, at Carlos's request. This policy applies to every
change that can affect a categorisation result: tier order, overrides, collision
rules, dictionary eligibility or contents, regex rules, crosswalks, input
normalisation, masks, model artefacts, thresholds, abstention and fallback.

The same policy and change records live in:

- `internal-services-monorepo/apps/ob-txn-categoriser/research/waterfall-changes/`
- `raylo-transaction-categorisation/docs/waterfall-changes/`

Keep the policy, change IDs, evaluation manifests, aggregate scores and decisions
identical in both repositories. Repository-specific entry-point links may differ.
The evaluation runner enforces inventory completeness, provenance and metric
checks. Candidate acceptance and promotion remain explicit review decisions.

## Before changing behaviour

1. Create a dated record from `CHANGE_TEMPLATE.md`. State the observed failure,
   the proposed rule and tier, expected effects, known exceptions and acceptance
   criteria before examining candidate scores. Make one isolated behavioural
   change at a time. Evaluate alternatives separately; do not bundle a new mask,
   dictionary policy and payroll rule into one unmeasurable fix.
2. Pin the baseline and candidate source in both repositories, including any
   uncommitted patch digest. Record the bundle, model, taxonomy, dictionary, rule,
   crosswalk, mask, config, registry, dataset and evaluation-code hashes, model
   seed, dependencies and runtime. Preserve the actual serving baseline.
3. Establish and run the complete repeatable evaluation inventory below before
   the first change. Then rerun it for each candidate revision. Compare baseline
   and candidate using the same input rows, labels, adapters and metrics. If the
   harness or data changes, rerun both sides and record that separate change.

## Required repeatable evaluation inventory

The hash-pinned registry is
`lib/raylo-txncat/contracts/eval_registry.json` in the monorepo and
`eval_registry.json` in research. They currently match: 13 development sets,
one validation set, one locked confirmation set and one retired confirmation set.
The runner's `evaluation_inventory.json` adds the hash-pinned historical
`gold_pipeline_eval` benchmark, bringing the repeatable data inventory to 15 sets.
Use the union of both registries and their exclusion metadata for data consumers.
Fail closed on unknown hashes; never silently omit a set or rename a locked file
to bypass its role. Protect evaluations from training, dictionary-candidate,
prompt-example and evidence-retrieval ingestion.

Every change record must account for all of the following:

| Group | Required coverage |
|---|---|
| Code and contract regressions | Complete app/library test suite; complete research test suite; taxonomy/rule integrity, API/schema and relevant shared CI checks. Add positive, negative and precedence cases for the change. |
| Research and app parity | All frozen synthetic goldens, startup probes, both deployed heads and the broad deterministic research/app comparison. Preserve old reference fixtures; record each intentional expected-output change in a new version. |
| Transaction development sets | `gold_transactions`, `gold_transactions_v2`, `gold_transactions_v2_batch2`, `gold_transactions_v3_volume`, `gold_transactions_v4_slm_volume`, `gold_v2_slm_eval_holdout`, `gold_v3_eyeball`, `gold_v4_eyeball`. |
| Credit and risk sets | `gold_credit_eval`, `gold_transactions_risk_categories`, `gold_transactions_risk_t6bound`; retain direction and risk-leaf denominators. |
| Historical full-pipeline benchmark | `gold_pipeline_eval`, the preserved 2,000-row development export, with Plaid serving and mixed-provider research views kept separate. |
| Merchant development sets | `gold_merchant_labels`, `gold_tail_labels`; run their defined merchant/dictionary evaluations, without inventing missing transaction context. |
| Validation | `tuning_validation`, reported explicitly as previously used for model selection. Do not retune or select another seed as part of a rule fix. |
| Targeted regression set | Separately versioned synthetic and independently labelled examples for the discovered failure, including ambiguous cases and counterexamples. Keep these separate from accuracy headlines. |

Use each dataset only with a documented, valid adapter and its original task.
Report Plaid serving results separately from research-only Equifax results.
Where fields needed for a full waterfall are absent, retain the appropriate
legacy/dictionary/head evaluation and explicitly mark full-waterfall scoring
unsupported. Do not fabricate a provider category, direction, amount or narrative
to create a comparable headline. Missing data, failed evaluation or unsupported
coverage must remain visible and prevent a claim that the complete suite passed.

Training-contaminated or repeatedly used development sets are regression
diagnostics, not independent evidence of generalisation. Keep their provenance
and metrics separate; do not pool different populations into a production score.

**Locked-set rule remains unchanged:** v5 is retired and must not be scored; v6
is reserved for the separately authorised final go/no-go evaluation. The request
to rerun all evaluations means the full permitted repeatable suite, not repeated
consumption of these confirmation sets.

## Measurements and acceptance

For every applicable dataset and both the selected transformer and hinge v8,
record baseline, candidate and delta with counts and explicit denominators:

- Specific leaf and general-category accuracy; precision, recall and F1 by leaf,
  including salary, refunds and the standing risk categories; macro summaries.
- Classified coverage and T7 abstention, plus accuracy among classified rows.
  Keep research-style unclassified-string accuracy separately labelled.
- Credit/debit, filled/blank merchant, provider, label provenance and tier splits;
  risk false positives/negatives, distinguishing unknown gold from known non-risk.
- Correct-to-wrong, wrong-to-correct and wrong-to-different-wrong transitions;
  all changed rows and explanations, with no raw customer data in committed logs.
- Fixed-cohort residual scores alongside actual candidate residual coverage,
  so a change in which rows reach T6 cannot masquerade as model improvement.
- Duplicate/conflicting-label sensitivity. Preserve gold labels; adjudication
  is a separate versioned task, not a way to make the candidate pass.

Review every regression. Default to retaining the baseline if a regression is
unexplained or a predeclared acceptance criterion fails. A higher aggregate score
does not justify a hidden salary, refund or risk regression. Any accepted trade-off
must be explicit in the record; do not invent a tolerance after seeing scores.

Record residual volume and rerun the relevant deadline/capacity checks when a
change sends more transactions to a model. Offline quality tests do not establish
deployed latency or Taktile transport correctness.

## Mirror implementations and scores before promotion

Update the research source of truth and the app/library port together. For T2 or
tier-order changes, inspect both `src/final_evaluation.py` and
`src/generate_crosswalk_sql.py`; regenerate the affected SQL from its generator
and verify parity. Do not hand-patch generated SQL or only update one Python
resolver. For dictionary/rule changes, update the owning build inputs rather
than only a compiled artefact. Model/policy adapters must use the same selected
head, preprocessing, masks and abstention semantics when comparing final outputs.

Keep provider-specific and research-overlay differences explicit. Require zero
unexplained research/app differences on comparable inputs, including detailed
tiers and rule provenance. Update source guards, bundle provenance and goldens
only with the documented behavioural change; never weaken parity assertions just
to obtain a passing run.

For each change, commit the same dated human-readable report and machine-readable
aggregate results in both repositories. Link both implementation revisions and
record exact reproduction commands, runtime and file hashes. Keep an append-only
score history in `README.md`; preserve rejected experiments and superseded scores
with their status. Update the research README/CLAUDE current-score pointer so new
work does not accidentally quote an old result. Keep row-level sensitive evidence
in an approved private location with a reproducible identity.

Do not mark the change complete or promote the candidate until implementation,
evaluation, review and documentation are complete in both repositories. Deploy a
versioned staging release through the existing release process, retain rollback
pins and rerun the signed synthetic API regression cases against that release.
Staging deployment and final production confirmation remain distinct steps.

## Execution

Existing reproducible commands, from the monorepo root in the frozen environment:

```sh
make -C apps/ob-txn-categoriser test
make -C apps/ob-txn-categoriser lint
make -C apps/ob-txn-categoriser schema-check
python apps/ob-txn-categoriser/scripts/verify_research_registry.py --research-root /path/to/research
python lib/raylo-txncat/scripts/verify_deterministic.py /path/to/bundle --research-root /path/to/research --report /path/to/new-run/parity.json
python apps/ob-txn-categoriser/scripts/verify_startup.py /path/to/bundle --report /path/to/new-run/startup.json
```

Research's existing code test entry point is `python -m pytest tests/ -q` from its
root in its compatible environment. Use `run_evaluations.py` for the complete
inventory and checks, following [RUNNING.md](RUNNING.md). The commands above are
individual diagnostics. The older `compare_abstention.py` covers only three sets
and does not substitute for a complete run.

The [15 September baseline](baseline-2026-09-15/README.md) establishes the starting
scores for the retailer-credit work. Each later candidate must repeat the suite,
including pass/fail/unsupported status for every set and the baseline comparison.
Evaluate one candidate change at a time. No retailer-credit change, retraining,
mask change or deployment is approved by baseline scores alone.

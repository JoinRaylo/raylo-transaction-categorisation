# Historical-regression-v1

Existing labels are useful for repeatable regression checks. Their historical
development, pretraining and selection exposure prevents treating them as a new
untouched benchmark. This cohort preserves those limitations and original roles.

## Frozen membership

The fixed, permitted evaluation inventory contains 26,111 source rows. The 5,000
selection-validation rows retain that role and are excluded from this cohort.
The remaining rows form 10,691 distinct applicable-input/task groups. Removing
10,420 repeated input rows and withholding 28 conflicting-label groups leaves
10,663 scored cases, partitioned by the task they can actually evaluate:

| Cohort | Consistent input cases | Explicit training-origin cases | Conflicting groups withheld |
|---|---:|---:|---:|
| Complete transaction input | 8,212 | 3,927 | 28 |
| Head / historical head-plus-T5 only | 641 | 0 | 0 |
| Merchant dictionary only | 1,810 | 0 | 0 |

These identify **input cases, not recovered economic events**. Complete-input
identity includes merchant, narrative, direction, amount, provider and native
category. Different tasks are not collapsed together. Identical inputs with
different labels go to the private conflict queue, even if one label has more
votes or an existing human-review tag. No disagreement was automatically resolved.

Every member retains all dataset/row-position references, source-file digests,
original roles and label-provenance tags. A training-origin copy cannot become an
independent test merely because another copy occurred in an evaluation file.
Only 397 transaction cases carry an explicit `human_reviewed` source tag; this
count is tag-based, not an audit proving the other labels received no human input.
All historical label quality remains subject to review; no new gold was created.

The 3,927 cases with an explicit `train` source role are reported separately as
`known_training_source_diagnostic`. The other 4,285 transaction cases are still
historical development evidence: absence of that particular role flag does not
prove absence from distillation, MLM, dictionaries, rules or selection.

## Scores on the frozen cases

Scores below are a **rescore of verified cached predictions** from the complete
15 September baseline, using new deduplicated denominators. They are not a new
model run or an improvement over previously reported scores. The baseline private
prediction digest and source hashes are checked before scoring. Both heads and
all applicable pipeline views must be present for every retained case; incomplete
coverage or conflicting predictions for an identical case fail the command.

| Historical development view | Cases | Hinge specific leaf accuracy | Seed-123 transformer specific leaf accuracy |
|---|---:|---:|---:|
| Complete inputs, head only | 4,285 | 72.51% | 80.26% |
| Complete inputs, mixed-provider research pipeline | 4,285 | 82.80% | 85.25% |
| Complete inputs, Plaid serving pipeline | 3,704 | 82.64% | 85.10% |
| Head-only cohort, raw head | 641 | 61.00% | 73.48% |
| Head-only cohort, historical head + T5 | 641 | 64.74% | 73.79% |

The separate known-training diagnostics score 82.63% / 83.24% for the research
pipeline (3,927 cases) and 83.14% / 83.25% for Plaid serving (2,681 cases).
Dictionary-only accuracy is 40.44% at 43.76% coverage on 1,810 cases. That dictionary
task cannot measure complete-transaction or whole-engine accuracy.

`legacy-summary.json` contains exact numerators, denominators, abstention/coverage,
general accuracy, macro F1, per-leaf support and confusion counts, plus the credit
and risk-category bars for all 19 groups. Abstaining or matching an unclassified
gold label does not count as a correct specific-category assignment. Existing
dataset-level score history is preserved; these diagnostic scores must not be
pooled with future representative, unseen-input or unfamiliar-family scores.

## Future changes

Keep v1 membership, labels and source snapshots fixed. Run the complete permitted
evaluation harness after every waterfall/model change, then run
`benchmark_score_legacy.py` on that completed run. Its receipt checks the frozen
membership, original source digests and private prediction object before scoring.
Use the existing evaluation comparison for paired regressions; compare the 19
curated groups on identical denominators as an additional view.

Adjudicating a conflict or correcting a historical label requires a documented
new cohort version and a label-change record. Newly labelled future transactions
enter separately governed training/validation/benchmark partitions; do not append
them to v1 or silently migrate these cases to training. Durable admission and all
consumer integrations remain B03/B04 work, not a capability of this offline scorer.

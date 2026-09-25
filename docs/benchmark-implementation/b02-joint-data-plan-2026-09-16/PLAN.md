# Joint benchmark and final retraining data plan

16 September 2026. This plan adds a training-augmentation workstream to the approved
three-view benchmark. The accompanying [profile](README.md) measures available
data; it does not reserve examples, certify historical non-exposure or authorize
model fitting. Staging, model weights, taxonomy and waterfall behaviour are unchanged.

## One allocation process, separate purposes

Use the audited, unambiguously customer-linked Plaid pool for v1 candidates. Other-
provider and historical regression evaluation remains separate. Stop recovery of
the excluded anonymous cohort. Materialize candidate lineage from source reports,
not just the globally transaction-ID-deduplicated profile table. Preserve assessment,
report, provider/account/event identity, pending/posted and reconnect aliases,
content versions, customer, source bounds and the exact effective input for each
head. Retain private IDs outside Git and use opaque annotation item IDs.

Classify rows as eligible, conflicting or unknown for a declared purpose. Unknown
benchmark eligibility is not permission to put a row into training. Training can
include historically learned examples, but it must independently clear every
protected evaluation, pilot and selection membership. Keep original source files
and existing training provenance rather than deleting excluded rows.

Allocate customer/account/event groups before label exports or new learning. Reserve
all evaluation views and model-selection validation first, then admit training from
the non-conflicting remainder. Apply the union of protections for multi-view members:

- Representative events protect their event, aliases, customer and account. Familiar
  merchants and naturally repeated inputs on independent events remain allowed,
  with known/unknown input exposure reported.
- Unseen-input members additionally protect applicable effective-input signatures
  across supervised learning, pretraining, distillation and fitted preprocessing.
- Unfamiliar-merchant members additionally protect reviewed merchant families across
  learning, dictionary/rule evidence and prompt examples. Unmatched spelling alone
  does not prove a new family; blank merchants have their own slice.
- Model-selection validation is separate from training and benchmark groups, with
  effective-input separation under the current contract. Retired or failed-label
  reservations remain protected permanently.

Use the existing [three-view amendment](../b02-initial/CONTRACT_AMENDMENT.md), not
three independently sampled datasets or a global ban on familiar merchants. Views
can overlap within a partition. Precompute group/input sampling blocks and measure
their size and exclusions before sampling; do not silently delete cross-partition
conflicts after drawing a supposedly representative sample.

The older corpora lack complete customer/event lineage. A large linked pool alone
does not prove clean benchmark eligibility. Use verified historical mappings where
available, or a documented prospective/new-customer **and new-event** cutoff after
the relevant exposure snapshots, with alias checks. A newly created customer can
bring old transaction history, so customer creation date alone is insufficient.
Require verified new-event and customer/account history plus alias checks for every
member in every view; quarantine unknown event/group history. Keep strict novelty
claims unknown where their ancestry evidence is incomplete.

## Sampling and annotation envelopes

The existing 20,000-row master envelope remains the starting budget, conditional on
eligible support, labelling quality and paired-comparison power. These are targets,
not counts of selected or clean rows.

| Purpose | Initial target | Use |
|---|---:|---|
| Annotation-method pilot | 500 | Separate permanently quarantined pool; improve instructions and estimate adjudication workload |
| Core | 10,000 | Probability sample of declared linked-customer traffic; repeated development monitoring |
| Challenge | 5,000 | Predefined critical, thin-category, blank-merchant and novelty searches; separate metrics |
| Sealed confirmation | 5,000 | 4,000 representative + 1,000 challenge, reported separately; final frozen comparison only |
| New model-selection validation | 5,000 proposed | 4,000 representative + 1,000 targeted, separated from every master partition; epochs/thresholds selected here |
| First training augmentation | Up to 10,000 proposed | Independently admitted new transaction examples shared by both heads; count unique examples separately from sampling copies |

Choose actual source dates and inclusion probabilities after the admission profile,
not from the convenience engineering sample. Measure month, credit/debit, amount,
merchant presence and business/consumer composition of both the source and the
eligible frame. Use customer-aware probability sampling with known event inclusion
probabilities and account for clustering in uncertainty estimates. Any cap on a
customer's contribution changes inclusion probabilities and must enter the weights.
Keep business rows visible as a stratum; do not silently remove them from the
currently approved linked-customer population. Missing currency, institution,
account-type or pending-state coverage needs the raw-source sidecar before final
quotas; the flattened profile does not establish those dimensions.

Aim for the existing 200 independently labelled examples per critical leaf and 20
per leaf where feasible across core/challenge. Do not equate those targets with
statistical power or force a rare class into the random core. Use provider categories
only as search proxies. Confirm class support after independent annotation and
publish shortfalls, ambiguity and sampling losses; expand the budget or narrow the
claim if needed. Do not pad coverage with duplicate inputs.

Final benchmark labels require two independent human labels, adjudication and a
frozen guide. Hide model/provider category suggestions from the primary labelling
view. Maintain the existing labelled historical regression cohort separately; it
can provide development diagnostics but cannot become an untouched master.

## Target useful training additions

The [training audit](training/TRAINING_AUGMENTATION.md) supplies measured raw and
distinct-input counts. Existing top-ups and consensus labels are not uniformly
independent human gold; retain their actual quality and source roles. The first
new batch should improve transaction-level breadth rather than multiply merchant
labels or copy existing rows.

Start from the measured missing leaves (`account_misuse`, `balance_transfer_fee`,
`interest_charged`, `loan_repayment_dd`) and thin support such as `housing_benefit`,
`credit_card_fee` and `money_transfer_fee`. Preserve source evidence needed to
distinguish them; do not invent examples or relabel a nearby category just to fill
a class. Separately review the 133 exact-input conflicting-label groups in the
current supervised file before fitting; no label is changed by this audit.

Within the proposed 10,000-example tranche, use the following provisional,
non-overlapping priority buckets. Apply them in table order; report each example's
other attributes as overlapping diagnostic slices. Fill only from training-admitted
groups and freeze the rubric before observing the new benchmark's errors.

| Priority bucket | Budget | Search and label requirements |
|---|---:|---|
| Credits | 4,000 | Income, transfers, refunds/reversals and ambiguous merchant credits; include blank merchants and meaningful narratives, avoid inferring salary/refund from amount alone |
| Critical/weakly supported debits | 3,000 | Use measured training support and existing development findings; cover distinct customers, merchants and narrative forms in risk/fee/debt leaves |
| Other blank-merchant debits | 2,000 | Bank narratives, fees and transfers outside the previous bucket; genuine input variation rather than account-number substitutions |
| Representative remainder | 1,000 | Random admitted traffic to retain ordinary categories and reduce targeting bias |

These numbers are a bounded proposal, not an asserted optimum. Pilot yields and
independent labels may justify reallocation **before fitting**. No category gets a
synthetic gold label because its quota is short. Explicit same-merchant credit/debit
and salary/refund contrasts belong here when source evidence supports their labels;
ambiguous rows keep an ambiguity status and are not forced into a target.

Use a common versioned labelled transaction manifest for the new additions to both
heads, preserving head-specific transformations. Keep unique events, unique logical
inputs, unique effective inputs and weighted/oversampled rows as separate counts.
Resolve conflicting labels on the same effective input before fitting or explicitly
exclude them with reasons. Where model input cannot distinguish two true meanings,
document the feature limitation rather than adjudicating by merchant alone.

Review training labels by their provenance and retain adjudication records. Model
consensus may propose training labels if its inputs and prompt evidence are admitted,
but it remains a lower-quality training tier; never promote consensus labels into
independent evaluation gold. Preserve useful ordinary examples in the base training
set rather than retraining only on the waterfall's residual slice.

## Retrain and compare once the data is protected

Pin the current hinge v8 and seed-123 iteration-8 transformer as baselines, together
with the same frozen waterfall, taxonomy, preprocessing, masks and thresholds.
Create new candidate paths; do not overwrite serving artifacts. The new additions
are shared, but total ancestry differs because the transformer also inherits the
historical MLM encoder and consensus stage.

For hinge, keep the current char-ngram TF-IDF plus numeric/direction features and
SGD hinge recipe. Refit the vectorizer on admitted training inputs only. For the
transformer, reuse the declared iteration-8 encoder/tokenizer ancestry and perform
the supervised stage with the augmented training data. **No new MLM or vocabulary
extension is proposed for this pass.** Fix the seed and recipe before scoring;
optional additional seeds are robustness runs, not a contest on confirmation data.

The existing transformer training code rebuilds empirical direction masks from
training counts. Capture the resulting mask diff: either keep the frozen supported
policy or treat any intended mask change as a separately reviewed behaviour change.
Do not call a data-only experiment unchanged merely because source code is identical.
Use the new selection set for model/epoch decisions; the old 5,000-row validation
file has documented exposure limitations and remains a historical diagnostic.

Rerun all 15 permitted legacy evaluations and the new development master partitions
for both standalone heads and the full frozen waterfall. Report weighted core and
targeted challenge metrics separately, with direction, leaf/general, critical-leaf,
blank-merchant, novelty, abstention and customer-aware paired uncertainty. Include
the frozen-baseline residual and actual candidate residual so routing changes cannot
hide regressions. Freeze the final candidate and endpoint/tolerance plan before the
single sealed confirmation run; do not repeatedly tune against its results.

Mirror every real model/waterfall change, dataset manifest, evaluation run and score
history in the app and research repos. Existing v5/v6 restrictions remain unchanged.
Promotion follows verified metrics and the normal release review; this plan does
not itself change staging or deploy a retrained model.

## Next implementation increment

Build the B03 reservation authority and connect the B04 training/export consumers
to it, using the already implemented shared B02 contract. First demonstrate with
synthetic data that competing reserve/train claims cannot both succeed, all six
data roles stay separate across all learning/enrichment consumers, inherited reservations survive retries/retirement, and a
direct unregistered fit cannot pass promotion. Prepare the scoped infrastructure
plan for review before any apply.

Then run a bounded, linked-only admission job that reports eligible populations,
group-block sizes and exclusion reasons; reserve the separate 500-row annotation
pilot. Final quotas and training allocation follow its measured label yield. This
advances both requested workstreams without reopening anonymous identity recovery
or allowing a new retrain to consume the future benchmark.

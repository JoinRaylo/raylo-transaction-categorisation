# Master benchmark identity and separation contract — proposed v2

Status: design specification; **not the deployed v1 Pydantic/schema contract**.
Do not change the frozen registry, its hashes or serving bundle to look like this
specification before implementing the migration and tests.

## 1. Distinct identities

| Field | Meaning and stability |
|---|---|
| `benchmark_id` | Permanent family: `txncat-master` |
| `benchmark_version` | Immutable membership/labels/input snapshot version, initially `1.0.0` |
| `benchmark_manifest_sha256` | Exact published manifest bytes; required by every score receipt |
| `example_id` | Opaque assigned ID, stable across label/input revisions of the same selected example |
| `observation_key` | Provider-scoped source occurrence; stable across export/report retries |
| `event_family_id` | Governed linkage of observations that represent the same economic event, including pending/posted aliases |
| `customer_group_id` | Stable pseudonymous internal customer identity across applications/providers; not an application ID |
| `account_group_id` | Stable pseudonymous linked account, including known reconnect aliases |
| `source_snapshot_id` | Immutable extraction identity, with event/as-of bounds, extraction time, query/schema hash and source lineage |
| `example_revision_sha256` | Exact input plus label revision; changes when bytes change, unlike permanent membership identities |
| `membership_epoch` | Monotonic authoritative reservation/exposure state used for admission |
| `partition_block_id` | Versioned sampling block linking indivisible customers and shared effective inputs; statistical grouping, not a claim of common identity |
| `confirmation_cohort_id` | Permanent sealed-cohort identity; label/manifest/version changes do not reset its claim or exposure history |

Observation identity starts with a namespace-qualified provider transaction ID and
stable account scope where provider semantics require it. Do not include report ID,
row number, filename, merchant, amount, transaction date, label or benchmark version
in this identity. Those can change while the same event remains held out.

Provider ID stability and account/customer mappings must first be verified against
the actual warehouse/API source. Existing HTTP DTOs expose transaction/account IDs;
that does not prove the historical warehouse links are present or reconnect-stable.
Map pending-to-posted explicitly when the source provides a link. Keep both immutable
observation IDs as aliases of one event family. Never infer a confirmed event match
from equal merchant/amount/date alone: distinct purchases can look identical.

Identity aliases are append-only. A merge discovered after partition assignment
propagates every previous reservation. If it joins train and benchmark, record a
contamination incident, invalidate affected comparisons and hold promotion; do not
relabel a split to conceal it. A new alias cannot free old IDs for training.

## 2. Privacy and deterministic encoding

Private identity service mints HMAC-SHA256 tokens using domain-separated canonical
objects, for example:

```json
{"domain":"txncat-observation-v2","namespace":"plaid/raylo","account":"<canonical-account>","transaction":"<provider-transaction-id>"}
```

This is a shape example, not a real identity or production key. Keep the encoding
version, key ID and namespace alongside every digest. Use the project's named
`txncat-json-v1` encoding where applicable; it is not claimed to be RFC8785. No
ambiguous delimiter concatenation. Reject duplicate JSON keys and invalid Unicode.
Canonical money uses finite decimal strings, normalized independently of display
format; direction is explicit and zero is debit at the Plaid adapter boundary.

HMAC keys live outside Git and are accessible only to the identity authority. Hashes
of low-entropy names are not anonymous merely because they look random. Do not
export benchmark text, identities or HMAC indexes into ordinary logs or public
model manifests. Training clients query admission or use authorized private indexes.

Key rotation requires a verified dual-key migration: retain old tokens/aliases and
build new tokens inside the authority; record a mapping and compare both versions
until migration completeness is proven. Missing key versions fail closed. Rotation
must not make a protected example appear new. Do not delete old exclusion identities
when the active key changes. Retention/deletion obligations use tombstones and an
explicit governance process; they never silently authorize use of retired gold.

## 3. Fingerprints: identity is not input exposure

Each observation records a **set** of versioned input fingerprints, not one universal
hash. Source identity answers “same event?”; these answer “same learning input?”.
Fingerprints exclude target labels, row IDs and partition. Otherwise a changed label
or export would evade overlap detection.

| Fingerprint | Coverage |
|---|---|
| Original logical input | Original prediction-time fields, null/missing distinctions and canonical amount/currency/direction; detects exact input copies under new IDs |
| Research row projection | Actual historical merchant/description/amount/direction normalisation and parsing, including legacy continuation-line behaviour |
| Transformer sentence | Actual `ClassifierInput`/MLM sentence: direction, amount bucket and stripped/lowercased text |
| Transformer encoded input | Effective non-padding token IDs/attention, truncation length, mask direction, tokenizer and preprocessing version; captures different suffixes truncated away |
| Hinge input | Actual lowercased text plus the retained numerical/direction transformation; pin vectorizer/preprocessor versions where fitting used transformed values |
| Teacher/distillation input | Effective prompt/task input, including any amount median/bucketing and field selection used to produce learning examples |
| Near-duplicate candidate | Versioned conservative similarity/template detector for human review, never proof of same customer/event |

Comparison is against the union of the fingerprints relevant to all learning stages
in a model's ancestry. New recipes add new projection versions; they do not discard
old ones. A tokenizer/vocabulary fit first needs an admission/exposure receipt for
its source inputs under the existing identity/projection policy. Freeze the resulting
transform and compute its new projection on both learning and held-out inputs before
allowing downstream model fitting or clean certification. Newly discovered collisions
hold certification; they do not authorize silently removing benchmark cases. Do not
compute vocabulary statistics on held-out text to build that tokenizer. Benchmark
evaluation may tokenize with an already frozen tokenizer; this is evaluation, not learning.

For current heads, GBP 6.99 and GBP 7.49 can share the same transformer amount bucket
and sentence even with different transaction IDs. Checking only the full amount
fingerprint is insufficient. Long descriptions that differ after token 48 can also
be identical to the retained transformer. MLM exposure counts even without category
labels. Pretraining windows/chunks need the same effective-input accounting.

Do not blanket-group every “Faster Payment” narrative into one customer/event. Treat
uncertain near-duplicates as a review/quarantine reason and report exclusion loss.
Common generic inputs can make strict novelty unrepresentative; apply DESIGN.md's
coverage limitation instead of silently changing the predicate.

## 4. Logical tables and manifests

These are logical entities, not invented production warehouse schemas:

| Entity | Required contents |
|---|---|
| `source_snapshots` | Snapshot ID; source/table/schema/query versions; event/as-of/extraction bounds; provider; row counts; identities available; immutable data object references |
| `observations` | Event/customer/account linkage; original app-visible fields; observation/as-of time; fingerprint sets; identity quality flags; raw-data reference |
| `identity_aliases` | Old/new scoped identities, evidence, resolver/version, review provenance, effective epoch; no guessed person links |
| `membership_events` | Operation ID; subject identities/groups/projections; reservation/retirement/contamination event; partition; policy version; commit epoch |
| `label_decisions` | Example/revision; independent votes; adjudicator; taxonomy/guide versions; status/leaf/ambiguity policy; permitted evidence hashes; timestamps |
| `benchmark_manifests` | ID/version; partition/cohort membership objects; input/label hashes; sampling weights and bounds; schema/identity/projection versions; exposure and QA receipts |
| `learning_manifests` | Purpose; actual selected/filtered rows and effective inputs; all source/parent artefact digests; feature/tokenizer/model code; admission receipt; immutable fit-input object hashes |
| `evaluation_runs` | Candidate and baseline artefact/config identities; benchmark version/hash; evaluator/metric version; sampling-aware counts/results; private diagnostics; confirmation claim |

A benchmark manifest contains row-set hashes by partition and cohort, source and
label lineage, taxonomy identity, exact projection/index versions, and count
reconciliation (sampled, reserved, ambiguous, unresolved, excluded, published).
No published manifest has placeholder hashes or a mutable `latest` data reference.
Physical URI plus GCS generation plus content digest identifies each referenced object.

A training file is not permitted merely because it has `split=train`. The immutable
learning manifest and authority-issued receipt must authorize its exact data and
purpose. Any augmentation, relabelling, shuffling that changes bytes, text templating,
synthetic generation from examples, oversampling, amount replacement or format export
preserves ancestry. Row order may have a distinct object hash while semantic row-set
identity remains stable; both are recorded. Admission is checked again on effective
inputs before `.fit`/GPU submission, not just on a source CSV before transformations.

## 5. Membership states and separation rules

Dataset lifecycle: `draft -> reserved -> labelled -> qa_passed -> frozen ->
active_repeatable | sealed -> spent -> retired`. Quarantine may occur at any stage.
There is **no transition to training**. Retirement preserves all exclusions.
An excluded/quarantined sampling candidate does not become a convenient training
example after reviewers have seen it. Reserve the finite labelling pool, not an
entire production table; keep unrelated unreserved traffic available.

Consumer-purpose vocabulary for proposed v2:

`supervised_training`, `domain_pretraining`, `distillation`,
`tokenizer_vectorizer_fit`, `feature_mask_statistics`, `dictionary_candidates`,
`rule_candidates`, `prompt_examples`, `evidence_retrieval`.

| Condition | Learning/enrichment admission | Benchmark admission |
|---|---|---|
| Protected event/alias | Reject | Existing matching reservation only; no duplicate new member |
| Protected customer/account group | Reject | Same assigned partition only |
| Matching protected effective input | Reject | No overlap between separately scored pools; aggregate/group repeats within a pool |
| Novelty-family reservation | Reject for that family under registered novelty policy | Novel-family cohort only; enforce across learning and dictionary/rule evidence |
| Familiar merchant, distinct eligible event/input | Can be allowed if no other exclusion applies | Core eligible; do not claim merchant novelty |
| Blank merchant, verified event/customer/input identities | Normal checks apply | Eligible, subject to other checks |
| Missing source/group identity or unsupported projection | Quarantine; no “best effort” train mode | Cannot certify strict master membership |
| Historical source/exposure unknown | Quarantine for clean claims and governed fit | Not admitted as verified unseen |
| Deprecated v1 protected merchant/family | Preserve old rejection | Keep legacy restrictions; no automatic migration to master |

Both training and model-selection validation are excluded from master customer,
event and input groups. Validation remains eligible for its **explicit selection
purpose**; it is not retrospectively called untouched confirmation. Protect every
version of master membership, not only the active version. Near-duplicate ambiguity
requires adjudication before either side is admitted; do not silently random-split it.

`model_selection_validation` is an additional reserved dataset role and exposure
purpose, separate from the nine learning/enrichment purposes above. Its admissions
use the same authority and are isolated from training by event, linked customer and
applicable input projections. Validation use is recorded as selection exposure;
it must not become training by relabelling its role. Existing historical validation
is retained with its documented limitations, not retroactively certified as v2.

Every governed export carries a sidecar manifest and per-row provenance containing
`example_id` (where assigned), observation/event/customer/account identities,
`source_snapshot_id`, role, partition, policy version and fingerprint-set reference.
The authority supports private lookup by any supported source identity or example
ID, returning permanent memberships and reason codes. Role columns are convenient
labels, not authorization: the content-bound receipt and authoritative lookup decide.
If an external labeller cannot return the original IDs, join via an opaque issued
job-item ID; never reconstruct identity from the returned merchant and category.
Missing or duplicate job-item mappings quarantine the batch. This lookup/export
contract is proposed functionality, not an endpoint that exists today.

## 6. Preventing races and stale exclusion indexes

A batch CSV anti-join alone has a race: training may prepare at epoch N while the
same rows are reserved for evaluation at N+1. Both benchmark reservation and learning
consumption must use the same authoritative commit protocol:

1. Read epoch N and immutable membership **and past/pending learning-exposure** indexes.
2. Materialize the exact proposal and its identity/projection indexes privately;
   perform deterministic joins and policy checks against those pinned inputs.
3. Upload verified immutable data/manifests/index delta, unreferenced by any worker.
4. In one small Firestore transaction, compare authority epoch with N and create
   an idempotent operation receipt, immutable manifest pointers and epoch N+1.
   The commit adds a reservation **or** a learning exposure claim. Epoch mismatch
   means re-read and recheck; do not retry the old approval blindly.
5. Only then may an authorized worker load the receipt-bound objects. The worker
   verifies their content/generation and purpose before consuming them.

Large membership sets live in immutable indexed objects, not one Firestore document
or an unbounded transaction. Each epoch exposes a complete snapshot plus immutable
deltas; index compaction is content-preserving and independently checked. Global
commit serialization is acceptable initially; joins/uploads occur outside the short
transaction. A future sharded authority must preserve cross-shard atomic conflict
semantics and is not necessary for the first implementation.

Declare learning inputs as exposed **before** starting fitting or enrichment, so a
concurrent benchmark reservation sees pending jobs too. A failed or uncertain job
remains conservatively exposed. A crash before the metadata commit creates only an
orphan object, not an authorization. A crash after commit resumes by operation ID;
the same ID with different proposal bytes is rejected. No cached “allowed” result
outlives its content/epoch-bound operation semantics.

Receipts are authority-authenticated (service identity/signed record), not self-issued
by the training script. Promotion checks receipts, parent lineage, actual input hashes
and exclusions independently. Offline experiments without that route may be performed
only as unregistered development; their artefacts cannot receive a clean benchmark
claim or be promoted until complete lineage is established. No silent allow fallback
when the authority, registry, key or projection implementation is unavailable.

## 7. Historical migration and contamination response

Inventory all frozen parent models, MLM corpora, tokenizer/vocabulary fits, silver and
teacher labels, supervised snapshots, validation choices, dictionary/rule evidence,
prompt examples and retrieval indexes. Prefer actual consumed snapshots and manifests;
current source code is not proof of what an older model consumed. Match historical
records without IDs through the exact historical input projections; mark customer
linkage unknown where it cannot be reconstructed. A proposed new master cannot
inherit the word “clean” from a merchant-only holdout filename.

If required history is missing, establish a prospective cutoff tied to immutable
model/source snapshots and collect provably new customer/event groups. Still check
recurring model-input overlap. Do not rebuild old training files with new rules and
pretend those regenerated bytes describe historical exposure.

A discovered leak creates an incident record identifying affected memberships,
artefacts and results. Hold promotion; label affected benchmark versions contaminated;
retain the historical score and invalidate its clean interpretation. Do not erase
exposure, change labels to rescue scores, or remove failed cases silently. Replace
with a new independently sampled version and rerun both baseline and candidate.

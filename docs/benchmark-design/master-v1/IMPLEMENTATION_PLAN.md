# Master benchmark implementation and acceptance plan

Status: **planned work, not completed controls**. Read [DESIGN.md](DESIGN.md) and
[DATA_CONTRACT.md](DATA_CONTRACT.md). Package IDs below are local design references,
not Linear tickets. No new training, extraction, labelling or infrastructure is
performed by this documentation change.

## Order and ownership

| Package | Deliverable | Depends on | Accountable role |
|---|---|---|---|
| B01 | Source population and historical exposure inventory | None | Data/ML engineer with source owner |
| B02 | Versioned identity, projection and admission contract | B01 identity findings | ML/platform engineer |
| B03 | Private authority, immutable manifests and reservation workflow | B02 | Platform engineer |
| B04 | Admission and lineage enforced at every data consumer and promotion | B02–B03 | ML engineer; application owner |
| B05 | Pilot, sampling, independent labels and frozen master-v1 | B01–B04 | Benchmark custodian; domain adjudicator |
| B06 | Paired evaluator, release gates and confirmation claims | B02–B03; B05 for real runs | Evaluation owner; release owner |

B06 can develop against synthetic fixtures alongside B04. B05 must not start
labelling the final reserve before B03 and B04 prevent competing consumption.
The benchmark custodian and sealed evaluator need separate access from model
developers; a second review of a developer's self-issued receipt is insufficient.
Carlos/domain ownership resolves category conventions and material regression
tolerances before scoring; implementation must name the actual responsible people.

## B01 — establish what we can prove

Produce an immutable inventory of the **actual** datasets and artefacts consumed
by the current serving heads and candidate ancestry. Include supervised examples,
silver labels, distillation inputs/teacher prompts, MLM corpus shards and chunks,
tokenizer additions, vocabulary/vectorizer fits, feature/mask statistics, validation
selection, rule/dictionary source evidence and worked prompt examples. Register
upstream artefacts imported from the OB-transformer repo if an evaluated model uses
them; a different repository is not a lineage boundary. Record what is unavailable.

For each source, determine the real transaction, pending/posted link, account,
customer and reconnect fields and their stability. Reconcile repeated Asset Reports
and corrections using source semantics. Do not invent warehouse column names from
HTTP DTOs. Historical projections can establish input overlap when IDs are absent;
they cannot establish missing customer isolation. Timestamp the exposure cutoff and
identify a defensible prospective/new-customer population where needed.

Profile intended Plaid traffic and eligible traffic separately using approved source
access. Count credit/debit/zero, merchant and narrative quality, banks/account types,
currencies, pending state, time, duplicate reports and exclusion reasons. Measure
population loss caused by exact and effective-input novelty, including generic
blank-merchant narratives. Review zero-support cells before proposing sample quotas.
No new benchmark text or labels should enter normal development prompts during this
inventory. Private linkage evidence is separate from the aggregate profile report.

**Acceptance:** every parent in the current comparison has a verified exposure
manifest or an explicit unknown status; source identity mappings have evidence;
the prospective admission scope is defensible. Unknowns block clean certification,
not the production service. Historical metrics retain their existing interpretation.

## B02 — implement one policy contract

Implement a versioned shared identity/projection package with mirrored adapters in
the app and research repos. Choose one canonical implementation and pin its version
in research; do not maintain two independently changing exclusion algorithms.
Package canonicalization, HMAC domains/key IDs, aliases, purpose/role types, immutable
manifests, decision reasons and content-bound receipt validation. Validate against
strict schemas; unknown schema, identity, key or projection versions fail closed.

Keep the frozen v1 registry and bundle schema intact until an explicit migration.
Import legacy transaction/merchant/reviewed-family restrictions without weakening
them. Proposed v2 permits verified blank merchants; it must not silently remove
v1 exclusions to accomplish that. Add the nine learning/enrichment purposes and
the separate model-selection-validation exposure purpose from DATA_CONTRACT.md.

Implement actual preprocessing adapters, including legacy row normalization,
transformer amount buckets and token-48 truncation, MLM sentences/chunks and hinge
transformations. Preserve parent fingerprint versions and compare new transformations
on both proposed inputs and the reserve without fitting on the reserve.

**Acceptance:** synthetic vectors produce identical identities and decisions across
app/research adapters; all identity and projection scenarios in
[acceptance-cases.json](acceptance-cases.json) pass. Those scenarios are specifications
today, not executable tests or evidence of enforcement.

## B03 — make reservation authoritative

Implement the private GCS/Firestore design using repository infrastructure patterns.
Resolve resource names, IAM, retention/deletion requirements and key custody before
applying infrastructure. The benchmark store is separate from serving artefacts and
training access. Large immutable membership/exposure indexes stay outside Firestore;
the authority serializes bounded metadata commits with a monotonic epoch.

Implement both reservation and learning/selection-exposure claims using the same
compare-and-commit path. Materialize and verify content before commit; grant worker
access only to receipt-bound snapshots. Record learning exposure before consumption.
Support idempotent exact retries, orphan cleanup, immutable alias changes, permanent
retirement, migration receipts and an authenticated private membership lookup.
Exports and annotation jobs retain opaque job-item IDs and exact provenance.

**Acceptance:** an integration race reserving and training on the same event,
customer or effective input permits only one conflicting claim. Exercise stale
indexes, upload/commit crashes, lost responses, changed bytes under an operation ID,
key rotation, authority outage, index compaction and alias merges. Verify denied
training/runtime access to sealed data with the actual service identities. Recovery
must retain every previous exclusion. A happy-path unit test alone is insufficient.

## B04 — close each ingestion and promotion route

These are observed entry points to integrate, not evidence they already enforce v2:

| Existing area | Required integration |
|---|---|
| Research `src/build_tuning_dataset.py`, `src/build_tuning_leaf_topup.py` and top-up callers | Admit source lineage and exact final train/validation snapshots; retain IDs through filtering, deduplication, augmentation and oversampling |
| Research `src/build_credit_tranche.py` | Gate ordinary/targeted/`distil` branches; retain provenance through amount replacement, text grouping and exports |
| Research `src/transformer/build_corpus.py` | Gate **both** `build_pretrain` and silver construction, including each corpus shard |
| Research `src/transformer/pretrain_mlm.py` | Gate vocabulary extension statistics, encoded sequences/chunks and MLM consumption |
| Research `src/transformer/train_classifier.py` and head retraining/bake-off entry points | Check admitted effective inputs before fitting; record parent encoder/tokenizer, masks, selection data and chosen seed |
| Research `src/distillation_bakeoff.py` and teacher/consensus builders | Gate prompt/source examples, distilled labels, TF-IDF fit and classifier training; consensus is training data, not gold |
| Research `src/build_merchant_dictionary.py`, manual rule packs and SQL generation | Require approved source evidence for dictionary/rule candidates, including manual additions; no benchmark-derived examples in candidate evidence |
| Planned LangGraph labeller/evidence/recommendation workflow | Apply purpose gate before retrieval, prompt examples, T1/T2/T4/T5 proposals and retraining-dataset recommendations |
| App `raylo_txncat.evalsets` and bundle/promotion verification | Add v2 receipts without erasing legacy exclusions; reject unregistered/mismatched data or model ancestry before promotion |

Discovery must expand this list to every caller found by imports, CLI entry points,
notebooks, training jobs and artefact manifests. File lists alone are not the gate.
Apply admission again after preprocessing to the effective data actually consumed;
preprocessing learned from training also needs its own lineage. A manually copied
CSV or direct `.fit` can bypass a wrapper, so promotion independently verifies the
authority's receipts and ancestry. Offline artefacts without evidence are unregistered.

Dataset roles stay explicit in new labelling campaigns: independent training,
model-selection validation, core, challenge, confirmation and annotation pilot.
Assignments occur before labels; the authority resolves membership after every
export/reimport. A training label correction must not override an evaluation
reservation, and a retired benchmark row never becomes fresh training material.

**Acceptance:** each consumer has a negative integration test containing one protected
example plus eligible examples. It fails before fitting, teacher calls or evidence
delivery; it cannot silently filter then claim the original snapshot. Test any
permitted filtering as a new manifest with reconciled exclusions. An artefact lacking
a valid receipt, including one from a bypassed local fit, fails promotion. Preserve
the existing permitted regression suite and locked-set restrictions throughout.

## B05 — collect and freeze a benchmark we can defend

1. Freeze the sampling specification: actual source/date bounds, eligible population,
   customer/effective-input block assignment, inclusion probabilities, challenge search rubric,
   intended critical quotas, label guide, ambiguity policy and quality criteria.
2. Reserve a separate 500-row annotation-method pilot using the authority. Measure
   independent human agreement and adjudication workload. Improve the guide, then
   permanently quarantine pilot membership; do not feed it into final gold or training.
3. Reserve the final sampling pools. Complete the historical/current exposure audit
   at commit, not only when the candidate list was first extracted. Assign customer
   groups to one partition through precomputed sampling blocks; prevent effective-input
   overlap across scored pools without order-dependent post-sampling deletions.
4. Collect two independent human labels, adjudicate disagreements and retain full
   provenance. Return labels by issued job-item IDs. Freeze the guide before final
   annotation and apply revisions consistently with recorded independent re-review.
5. Meet coverage targets from candidate-independent challenge sampling. Publish
   unsupported cells, ambiguity and unresolved counts. Increase the 20,000-row
   envelope or declare limits if coverage/power needs more; do not pad with duplicates.
6. QA labels, reconcile all selected/reserved/excluded/published counts and verify
   sample weights. Freeze immutable membership/input/label manifests and dual-repo
   aggregate dataset cards. Keep confirmation rows, labels and fingerprints private.

**Acceptance:** no unresolved identity/exposure conflict in certified members;
independent label provenance and sampling lineage complete; no hidden exclusions;
quotas and population loss visible. The confirmed 275-leaf/29-general taxonomy
digest is pinned. A lack of sufficient rare-category evidence yields an explicit
limitation or blocked gate, not an invented claim of complete category coverage.

## B06 — reproducible comparison and release evidence

Add a master adapter to the existing repeatable evaluation workflow, retaining the
15 legacy sets. Compare frozen baseline and candidate on identical benchmark
versions with each standalone head and the actual waterfall. Report core weights,
challenge support, ambiguity denominators, all transitions, fixed-baseline residual
and actual candidate residual, and customer-aware paired uncertainty separately.

Freeze primary metrics, critical endpoints, numerical tolerances and the approach
to multiple comparisons **before** any candidate scores. Size using expected paired
discordances from permitted development data and conservative clustering assumptions;
publish sensitivity to those assumptions. Validate interval coverage on simulated
paired data including sparse/zero discordances. The proposed 0.5/2 percentage-point
margins are not already approved, and a 200-row leaf target is not a power guarantee.

Implement an atomic confirmation claim for an already selected candidate/baseline,
benchmark hash and frozen endpoint plan. Exact retries retrieve retained results;
partial exposure spends the claim. Any new candidate needs a fresh independent
confirmation cohort; version/label changes never reset the permanent cohort claim.
Label amendments create a new immutable benchmark version;
rerun both sides and retain the old result with its limitations.

**Acceptance:** identical artefacts reproduce counts/scores; changed labels, adapters,
model bytes or thresholds change the run identity. Unsupported/underpowered gates
are inconclusive. Known harmful transitions cannot be hidden by an overall gain.
Tests prove parallel/different-candidate confirmation requests cannot gain another
look. Mirror the aggregate score/history receipts in both repos after real runs.

## Completion and first step

The design is ready for implementation when its files and taxonomy references
reconcile. The **benchmark is ready for use only after B01–B06 acceptance evidence**,
actual manifests and the first controlled baseline run exist. Documentation checks
do not satisfy those criteria.

Start with B01 and B02: establish the source IDs and historical exposure inventory,
then implement the shared identity/admission contract against synthetic fixtures.
The initial source-profile/annotation measurements will resolve exact sampling dates,
filled/blank critical quotas, final sample size and staffing. No production or
Taktile dependency is required to start those packages.

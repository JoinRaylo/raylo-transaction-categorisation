# B03-A synthetic reservation protocol design

Status: **local synthetic milestone; protocol review approved**. This is not the B03
managed authority, does not admit data, and does not issue an authenticated
receipt. The implementation uses only bytes created by the tests.

## Scope and safety boundary

B03-A extends the canonical B02 contract in
`raylo_txncat.benchmark`. It coordinates a reservation claim, a pending
learning exposure claim, or a pending model-selection exposure claim through one
epoch compare-and-commit protocol. The current target population remains the
customer-linked Plaid pool, but no customer-linked rows, private indexes,
identity keys, labels, models, locked sets, cloud resources or credentials are
read here.

`eligible_preflight` is still only a B02 decision. A locally committed
`OperationState` is synthetic evidence that the test double serialized a claim;
its `LocalReceipt.authorizes_consumption` and `authenticated` fields are both
literal `False`. A future consumer or promotion gate must reject it with
`require_authorized_receipt`.

## Contract mapping

| B03-A type/operation | Contract role | Safety assertion |
| --- | --- | --- |
| `ObjectReference` | Immutable object pointer | Name, positive generation, role, byte length and SHA-256 are bound together. The store re-hashes bytes; a valid-looking digest alone is insufficient. |
| `ProvenanceRefs` | Source, identity and legacy evidence | Optional missing references are reported as quarantine reasons; supplied references must have the expected role and digest relationship to the B02 subject/index. |
| `ClaimIntent` | Caller proposal content | B02 `Membership`, purpose, policy version, key version, data/manifest/parent references and claim kind are strict and cross-validated. |
| `ClaimProposal` | Epoch-bound proposal | The authority attaches the freshly read epoch, index digest and index object reference. `proposal_sha256` is the canonical content hash used for retries. |
| `Preparation` | Fresh read and policy result | Records `snapshot_epoch` and named checks. Reject/quarantine/invalid results never enter the store. Re-preparation reads a new snapshot and reruns B02 policy. |
| `AuthorityStorage` | Minimal durable boundary | Requires immutable upload/read, operation lookup, atomic compare-and-commit, worker access by committed operation, and append-only alias update. |
| `OperationState` | Pending committed exposure | A committed reservation or `exposed` learning/selection member is added to the index before `worker_started`; worker start is not part of the claim. |
| `LocalReceipt` / `CommitResult` | Local evidence only | Both are explicitly non-authorizing. Exact retry returns the retained operation without an epoch increment; changed content under an operation ID is invalid. Worker reads additionally require a matching local receipt. |
| `AliasUpdate` / `ContaminationIncident` | Append-only identity correction | Joining protected and learned groups increments the epoch, preserves old IDs, marks affected certification contaminated and holds certification. |

## Protocol sequence

1. Upload data, manifest, parent and provenance bytes to immutable storage. An
   unreferenced upload is an inaccessible orphan.
2. `prepare(intent)` looks up the operation ID first, then reads a fresh complete
   `AuthoritySnapshot`, verifies every referenced object and canonical manifest,
   and runs B02 `Preflight`. It evaluates every declared benchmark view and
   unions their protections; learning and selection use their explicit purpose.
3. `commit(preparation)` verifies the objects again, creates the operation state
   and calls `compare_and_commit(expected_epoch=N, operation)`. The store accepts
   at most one writer at epoch N and publishes the next immutable index snapshot.
4. A stale epoch returns `stale_epoch` with
   `stale_epoch_requires_reprepare`; it is never an allow. The caller must call
   `reprepare`, normally with a new operation ID, and use the new checks.
5. A later worker can read only receipt-bound objects through the synthetic
   operation lookup. This local path demonstrates ordering only; it cannot be
   used as real training, enrichment, evaluation or promotion authority.

An exact committed retry first compares the immutable intent hash and then
re-verifies the original object generation/digest. It returns the same
`OperationState` and epoch. A changed purpose, parent, bytes or object metadata
under that operation ID is invalid, with no new commit.

## Storage semantics for the later production adapter

The eventual GCS/Firestore adapter must keep large membership and exposure
indexes in immutable objects. GCS uploads should be create-only and return a
generation plus digest. The short Firestore transaction must, in one commit:

- compare the stored epoch with `observed_epoch`;
- check exact operation-ID idempotency and reject changed proposal bytes;
- verify the current index pointer and append one reservation/exposure event;
- write the next epoch and immutable manifest/index pointers; and
- return an authenticated service-issued receipt.

Preparation, joins and uploads stay outside that transaction. A worker receives
access only after the transaction and must re-check receipt purpose, object
generation/digest, parent lineage and exclusions. Authority outage, missing
keys/projections/history, incomplete provenance and stale indexes must fail
closed. Firestore/IAM/retention/key custody, cross-process races and signed
receipts are deliberately not implemented by this milestone.

## Exact synthetic assertions

The test module `lib/raylo-txncat/tests/test_benchmark_authority.py` constructs
source, identity, legacy, claim and parent references from actual synthetic
bytes, then asserts exact status/reason strings. It covers:

- ordered and concurrent reserve/train conflicts on event, customer, account and
  applicable effective-input identities;
- successful fresh re-preparation of a non-conflicting stale proposal;
- idempotent lost-response retry with no new epoch;
- changed operation purpose/parents, invalid schema and object digest/generation
  failures;
- orphan access denial and committed-but-not-started exposure;
- missing identity/input/family history and missing provenance quarantine;
- retired, quarantined and spent membership protection;
- representative recurrence versus strict input/family novelty and union views;
- selection-to-training relabelling and non-authorizing local receipt rejection;
- append-only alias contamination across protected/learning and protected partitions,
  including alias-to-alias joins; and
- unavailable authority with no cached allow.

The thread-safe `InMemoryAuthorityStore` is a test double only. It is useful for
deterministic interleavings, not evidence of IAM isolation, Firestore atomicity,
authenticated receipts or production completeness.

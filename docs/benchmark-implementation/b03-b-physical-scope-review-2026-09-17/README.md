# B03-B physical authority scope review

Status: **partially provisioned synthetic scope; registry, IAM and live proofs are pending**.

This packet is the next gate after the approved synthetic authenticated-receipt
boundary. It turns the existing [IAM plan](../b03-b-production-boundary-2026-09-16/IAM_PLAN.md)
into an explicit approval and proof checklist. The approved partial setup below
creates no customer-data path and does not authorize benchmark consumption. The
Firestore registry, service identities, IAM bindings, bucket CMEK attachment and
all live proofs remain unapplied.

## Verified partial physical scope (2026-09-17)

The following resources were created in the approved `raylo-production` project
under the active account, with no objects or customer content uploaded:

| Resource | Verified state |
| --- | --- |
| Project/location | `raylo-production` (`601576302267`), `europe-west2`; existing default Firestore remains separate and is not reused |
| Authority bucket | `gs://raylo-production-txncat-benchmark-authority-europe-west2`; regional `europe-west2`, Standard, uniform bucket-level access, public-access prevention, versioning, 30-day object retention and 7-day soft-delete recovery |
| KMS keyring | `projects/raylo-production/locations/europe-west2/keyRings/txncat-benchmark-authority-europe-west2` |
| Receipt key | `.../cryptoKeys/txncat-benchmark-receipts`, HSM RSA PKCS#1 2048 signing, enabled version 1; asymmetric-key rotation is manual/version-bound because automatic rotation is unsupported |
| Storage key | `.../cryptoKeys/txncat-benchmark-storage`, HSM symmetric encryption, enabled version 1, 90-day automatic rotation beginning 2026-12-16 |
| Pending registry | Dedicated `txncat-benchmark-authority` Firestore database was not created; no registry data exists |
| Pending identities/IAM | No service accounts or IAM bindings were created or changed |

The Cloud KMS API was enabled as the prerequisite for the approved key scope.
The bucket currently has no default CMEK attached; the storage key is reserved
for the later reviewed bucket/Firestore encryption wiring. No key or bucket
deletion, retention lock, customer-data read, label write or benchmark admission
occurred.

## Decisions and evidence required before any live probe

| Decision | Required resolution | Evidence required |
| --- | --- | --- |
| Project and location | Retain the recorded isolated `raylo-production` / `europe-west2` scope and confirm it is separate from serving/training paths | Approved resource record; serving and training stores shown separate |
| Object store | Use the created dedicated immutable bucket/prefix for authority objects, claim data, manifests and indexes; attach its reviewed CMEK before registry use | Versioning/retention, generation-zero create-only behavior and no broad worker listing |
| Registry | Create the dedicated `txncat-benchmark-authority` Firestore database for pointers, proposals, operations and holds | Transaction limits, CAS semantics, backup/recovery and no row payloads in documents |
| Worker identities | Create distinct `learning-worker`, `selection-worker` and `sealed-evaluator` principals | IAM binding export plus explicit deny/absence results for every cross-plane read |
| Authority identity | Create an `authority-writer` identity separate from serving and workers | Object create/readback, registry transaction, KMS signing and public-key self-verification |
| KMS custody | Retain the created authority-owned HSM keys; document manual receipt-key version rotation, storage-key schedule and audit ownership | Key policy, rotation/retirement procedure, audit-log access and recovery decision |
| Retention and deletion | Confirm the bucket's 30-day retention/7-day soft-delete policy and approve whether to lock or extend it before real admission | Deletion-recovery proof showing membership, alias and contamination history cannot be erased |
| Audit and logging | Approve access/audit log sinks and retention | Logs contain IDs, generations, digests, epochs, key version and caller identity, never payloads or labels |

Created resources are factual but not permission to consume data. Remaining rows
are explicit mutations or approvals, not defaults. Existing serving-app or
staging approval does not approve these resources.

## Receipt verification deployment decision

The reviewed adapter signs with an injected authority-owned KMS client and
revalidates the public key while consuming a receipt. Before a live proof,
resolve one of these designs explicitly:

1. `learning-worker` and `selection-worker` receive read-only permission to
   fetch the public key for the approved KMS version; neither can sign or
   mutate authority state.
2. A separately identified authority verifier performs signature verification
   and exposes only the exact receipt-bound read operation to workers.
3. A reviewed, rotation-aware public-key distribution mechanism is added, with
   its digest/version binding and revocation behavior proved.

The implementation does not assume that object-read permission implies KMS
public-key permission. A live worker read must fail closed when its identity
cannot verify the receipt, and must never fall back to a local receipt,
preflight decision, cached key or cached allow.

## Physical enforcement and dependency closure

The selected deployment must make the receipt check an enforced read boundary,
not merely a convention in the worker code. A worker process must not receive a
generic object-store client or a callable equivalent of `read_verified`; its
direct object-store `get` permission is denied. A receipt-bound gateway or
authority verifier may hold the narrow data-plane read permission, authenticate
the caller, bind the requested audience, perform the fresh registry lookup and
signature check, then fetch only the exact committed generation. If a design
gives a worker direct object access, it must prove an equally strong physical
enforcement mechanism; prefix/list denial alone is insufficient.

The approval record must close every dependency in the actual deployment:

| Operation path | Required dependencies | Principal/design to record |
| --- | --- | --- |
| Authority receipt issue | Registry operation lookup and transaction access; authority object readback; KMS asymmetric sign and public-key verification | `authority-writer` or a separately named signer/verifier pair |
| Worker receipt read using the current adapter shape | Authenticated worker identity; fresh registry operation lookup; KMS public-key verification; exact-generation object read | Receipt-bound gateway/verifier, or explicitly approved worker permissions; generic worker `get` remains denied |
| Separate verifier service | Authenticated caller/audience binding; fresh registry operation lookup; KMS public-key verification; exact-generation object read | `receipt-verifier`, with no registry mutation or signing |

The choice must state which principal performs each dependency, how key-version
rotation is discovered, and how a worker is prevented from bypassing the
receipt-bound path. The proof must attempt generic direct reads for an allowed
object, a pending object, a revoked/held object, an orphan and an opposite-plane
object; only the approved receipt-bound path may return bytes.

## Required role matrix

The approved design must show these permissions independently, including
absence/deny results for the crossed-out paths:

| Identity | Allowed | Explicitly denied |
| --- | --- | --- |
| `authority-writer` | Authority object create/readback; registry transaction writes and operation lookup; receipt signing and public-key verification | Serving reads; model fitting; sealed reads; worker fallback; generic worker paths |
| `admission-reader` | Private source/identity/history/index reads and candidate preparation | Labels; sealed reads; registry mutation; receipt signing; authority object writes |
| `learning-worker` | Authenticated receipt-bound gateway call and learning manifests; registry/KMS public-key reads only if the selected design places verification here | Generic object-store reads; selection objects; sealed objects; authority writes; signing |
| `selection-worker` | Authenticated receipt-bound gateway call and selection manifests; registry/KMS public-key reads only if the selected design places verification here | Generic object-store reads; learning objects; sealed objects; authority writes; signing |
| `receipt-verifier` (if used) | Fresh operation lookup; exact-generation object read; KMS public-key verification; authenticated worker/audience binding | Registry mutation; object writes; receipt signing; serving, training and sealed reads |
| `sealed-evaluator` | Frozen confirmation objects and evaluator artifacts only | Training/selection reads; mutable labels; item-level result export |
| `operator-break-glass` | No standing permission; separately approved incident path | Default access and worker fallback |

One permissive layer in bucket IAM, object ACLs, Firestore rules or KMS IAM
invalidates the separation claim.

## Staged live proof sequence after approval

Use synthetic objects and a fresh empty registry namespace only. Only the
identity-permission stage is read-only. All fixture/protocol/key mutations must
be separately approved, performed by named bootstrap/authority/key-admin
principals, and covered by retention handling. None of the stages may write
customer rows, labels, benchmark membership, model artifacts or locked-set
results.

### Stage 0 — synthetic fixture/bootstrap (separate approval)

The named fixture owner creates the empty namespace and synthetic operation,
pointer, object, proposal, hold and alias fixtures. A named key administrator
creates or selects disposable test key versions for rotation/retirement cases.
The authority writer is the only identity permitted to create synthetic
authority operations. Record the fixture manifest, namespace and cleanup or
retention owner before the read-only probe starts.

### Stage 1 — no-write identity and direct-read probe

Using the staged fixtures, verify each identity can perform only its approved
object/registry/KMS operation and receives a real denied/absent response for
every crossed-out path. Attempt generic direct reads of an allowed object, a
pending object, a revoked/held object, an orphan and an opposite-plane object;
all must be denied or unreachable. Only the selected receipt-bound
gateway/verifier path may return the exact committed generation. This stage
must not create, update, delete, rotate or retire anything.

### Stage 2 — synthetic mutation and cross-process protocol proof (separate approval)

Run two independent authority processes against the same synthetic epoch and
conflicting proposals. Expect one committed operation and one explicit
stale/conflict result; retrying the losing operation must re-read and rerun
policy rather than use a cached allow. Repeat with non-conflicting proposals
and an identical lost-response retry. Expect both valid operations to commit
serially and the retry to return the original operation without a duplicate
epoch.

### Stage 3 — synthetic failure, retention and key-lifecycle proof (separate approval)

Upload an unreferenced object and exercise a failed registry CAS. Confirm it is
unreachable by workers and is not deleted without the approved retention
procedure. Revoke or hold a synthetic operation, append a joining alias, and
rotate or retire the disposable signing version. Verify every affected read
fails closed with an auditable reason. The key administrator and retention owner
must be named in the evidence.

Across all stages capture only non-sensitive evidence: principal, operation ID,
object name, generation, digest, epoch, key version, outcome and timestamp. Do
not export payloads, labels, narratives, identities or sealed item decisions.

The live probe is a separate approval gate. It is not permission to admit the
customer-linked Plaid pool or to connect B04 consumers.

## Current evidence and hard stop

- Synthetic receipt boundary: **Sol APPROVE**; 49 focused tests and 1,385 app
  unit tests pass, with 115 startup checks passing.
- The KMS adapter is lazy and injected; the synthetic fake covers typed
  algorithm/checksum responses and non-2048-bit rejection.
- Partial physical scope is verified: dedicated bucket, retention/versioning,
  keyring and HSM receipt/storage keys exist; the bucket has no default CMEK.
- No Firestore registry, service identity, IAM binding or live identity proof
  exists yet. The staged packet has not written any object or registry fixture.
- No real rows, labels, benchmark membership, model fitting, retraining,
  locked-set access or scoring occurred.

The remaining approval record must name owners for the Firestore database/CMEK,
bucket CMEK attachment, service identities/IAM bindings and receipt-verification
design. Until those exact mutations are approved, do not provision further,
run live permission probes, connect B04, reserve candidates or label any
transaction.

The packet evidence is pinned in `verification.json` in this directory.

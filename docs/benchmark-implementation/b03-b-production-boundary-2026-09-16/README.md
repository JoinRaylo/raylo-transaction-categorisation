# B03-B production authority boundary

Status: **design prepared; not applied**. This follows the approved B03-A
protocol and the read-only linked-pool audit. It defines the production adapter
and permission boundary without selecting physical resource names, creating
cloud resources, changing IAM, or issuing an authority receipt.

## Adapter shape

The adapter implements the canonical `raylo_txncat.benchmark_authority.AuthorityStorage`
contract; policy and identity semantics remain in the shared package. It has two
storage planes:

1. Private immutable object storage for source snapshots, claim data, manifests,
   complete membership/index snapshots, alias evidence and labels. Every upload
   is generation-zero create-only, stores role metadata, and is read back with
   the observed generation, exact byte length and SHA-256 before a pointer can
   be published. An existing name is reusable only when all bytes and metadata
   match; conflicting bytes fail closed.
2. A small Firestore registry for the current epoch/index pointer, proposal-ID
   bindings, committed operation metadata and contamination/certification state.
   Large memberships never enter a Firestore document or transaction payload.

Preparation verifies all referenced objects and reruns B02 against the fresh
index. The adapter then creates any next immutable index object before the short
registry transaction. That transaction reads the current epoch, index pointer,
proposal binding and operation record before writing; it accepts exactly one
writer for epoch N, preserves exact operation-ID retries, rejects changed
proposal bytes, and publishes the N+1 pointer and operation atomically. A losing
next-index upload remains an unreferenced orphan and grants no access.

`read_for_worker` is not a broad bucket read. The eventual authenticated receipt
must bind operation ID, purpose, committed epoch, object generations/digests,
parent lineage and effective exclusions. The worker rechecks those claims before
opening the exact object. Local receipts remain permanently non-authorizing.

## Concrete implementation sequence

- Add lazy GCS and Firestore clients behind injected interfaces so ordinary app
  startup does not import cloud SDKs or contact the network.
- Store canonical JSON model bytes, not language-specific dict/list encodings;
  parse with strict validation and reject non-canonical bytes.
- Use GCS generation-zero preconditions, CRC32C transport checks and a second
  SHA-256/content-length check. Never list a bucket to discover authority state.
- Use a Firestore transaction for the epoch/operation/index-pointer CAS. Reads,
  retry classification and changed-operation rejection remain inside that
  transaction; object verification and joins remain outside it.
- Put receipt signing behind a KMS asymmetric-sign operation or equivalent
  authority-owned signer. A caller-provided boolean, local HMAC or cached allow
  cannot become `authenticated=True`.
- Add emulator/fake tests for concurrent reservation versus learning/selection,
  stale epochs, upload/commit crashes, lost responses, changed bytes, key
  rotation, unavailable authority, alias merges and permanent contamination.
  The first live proof must additionally use the actual service identities.

## Explicit non-goals in this increment

No resource is provisioned or mutated. No bucket, Firestore database, KMS key,
service account, role binding, retention policy or network path is named as an
approved deployment fact. No real membership, labels, candidate export, model,
locked set, retraining or scoring is authorized by this document.

The next review asks Carlos to approve the resource/IAM choices below. After
approval, implement and test the adapter in isolation, then run the required
cross-process and denied-access proofs before connecting B04 consumers.

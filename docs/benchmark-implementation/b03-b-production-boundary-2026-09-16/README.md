# B03-B production authority boundary

Status: **adapter implemented behind injected ports; cloud scope not applied**.
The executable adapter remains canonical in the app monorepo; this research
mirror records its contract and evidence without maintaining a second policy
implementation. No physical resource names are selected, cloud resources are
created, IAM is changed, or authority receipt is issued here.

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

## Implemented boundary and remaining sequence

Implemented in isolation in the canonical app package:

- explicit immutable-object and registry/CAS ports with lazy cloud SDK imports;
- GCS generation-zero, CRC32C, prefix-scoped and SHA-256/content-length-checked
  object operations;
- strict canonical JSON Firestore envelopes and transactional epoch,
  proposal, operation and index-pointer publication; and
- alias CAS updates that preserve permanent contamination holds while leaving
  failed next-index uploads unreachable.

The companion [adapter contract and synthetic evidence](ADAPTER_CONTRACT.md)
records the exact port shape and the fourteen passing fake-boundary tests. Receipt
signing, real service identities, IAM/retention/KMS proof and B04 integration
remain pending review.

The exact post-review hashes and command results are pinned in
[verification.json](verification.json).

## Explicit non-goals in this increment

No resource is provisioned or mutated. No bucket, Firestore database, KMS key,
service account, role binding, retention policy or network path is named as an
approved deployment fact. No real membership, labels, candidate export, model,
locked set, retraining or scoring is authorized by this document. Local receipts
and adapter test outcomes remain non-authorizing.

The next review asks Carlos to approve the resource/IAM choices below and the
remaining receipt model. After approval, run the required cross-process and
denied-access proofs before connecting B04 consumers.

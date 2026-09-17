# B03-B adapter contract and synthetic evidence

The executable implementation is the canonical app-library module
`lib/raylo-txncat/src/raylo_txncat/benchmark_authority_cloud.py`. The research
repository carries this contract mirror; it does not maintain a second policy
implementation.

## Boundary

`ProductionAuthorityStorage` composes two strict ports:

| Port | Authority responsibility | Required property |
| --- | --- | --- |
| `AuthorityObjectStore` | create/read immutable bytes | generation, role, size and SHA-256 are verified by the implementation |
| `AuthorityRegistry` | registry pointer, proposal binding, operation state and CAS | epoch and operation writes are atomic; pointer is the only publication authority |

The adapter reuses the canonical `ClaimProposal`, `OperationState`, B02
`IndexSnapshot` and `AuthorityStorage` contract. Preparation, object content
verification and B02 policy checks stay outside the short registry transaction.
The next immutable index is uploaded first. If its registry CAS loses or fails,
the object remains an unreferenced orphan and grants no worker access.

`GCSAuthorityObjectStore` is generation-pinned, create-only, CRC32C-checked and
prefix-scoped. `FirestoreAuthorityRegistry` persists canonical JSON envelopes
and performs the epoch/operation/index-pointer CAS in a Firestore transaction.
Both receive already-created clients; no project, resource, IAM, retention or
KMS choice is embedded here.

`read_for_worker` accepts only an authority-issued `AuthenticatedReceipt` for the
exact object and operation. It verifies the canonical signed payload, committed
operation state, held certification, exposed lifecycle, purpose/worker-role
pairing, authority-resolved audience against the current worker principal,
operation digests, and object membership before reading bytes. Local receipts,
preflight decisions, object pointers and cached state cannot authorize training,
selection, enrichment, evaluation or promotion.

The signing boundary is an injected `AuthorityReceiptSigner`. The production
adapter supplied here is `KMSAuthorityReceiptSigner`, which signs the SHA-256
digest using an injected RSA Cloud KMS key version and verifies with the current
public key fetched from that same version. It checks the returned key version,
algorithm, 2048-bit public-key size and KMS CRC32C integrity fields. A fake
signer is used only by tests; it is not an authority or a production credential.
Receipt payloads exclude the signature envelope and are bound by
`payload_sha256`; the verifier separately checks the key version and algorithm.

## Synthetic evidence

The focused command below ran in the dedicated app worktree with no credentials,
real rows or cloud calls:

```sh
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=lib/raylo-txncat/src:lib/raylo-txncat/tests \
/private/tmp/txncat-c2-env/bin/python -m pytest -q -m unit \
  lib/raylo-txncat/tests/test_benchmark_authority_cloud.py
```

Result before the receipt increment: **14 passed**. The current focused adapter
suite has **20 passed** and additionally covers synthetic KMS signing and
verification, exact learning/selection receipt issuance, local/forged receipt
denial, purpose/role/object scope, contamination denial and post-signature byte
verification.

This evidence does not prove Firestore emulator behavior, IAM isolation,
cross-process concurrency, KMS custody or live permissions, retention,
source-history completeness or permission to admit real customer-linked examples.

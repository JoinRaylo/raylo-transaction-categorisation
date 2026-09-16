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

`read_for_worker` is deliberately unconditional deny until an authority-owned,
authenticated receipt type is implemented and reviewed. Local receipts,
preflight decisions, object pointers and cached state cannot authorize training,
selection, enrichment, evaluation or promotion.

## Synthetic evidence

The focused command below ran in the dedicated app worktree with no credentials,
real rows or cloud calls:

```sh
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=lib/raylo-txncat/src:lib/raylo-txncat/tests \
/private/tmp/txncat-c2-env/bin/python -m pytest -q -m unit \
  lib/raylo-txncat/tests/test_benchmark_authority_cloud.py
```

Result: **14 passed**. The tests include stale concurrent writers, an upload /
commit failure with an unreferenced index, tampered bytes, a corrupt registry
pointer, cross-partition alias contamination, alias retry idempotency, strict
canonical-envelope rejection, generation-pinned object reuse and path/size
guards.

This evidence does not prove Firestore emulator behavior, IAM isolation,
cross-process concurrency, KMS signing, retention, source-history completeness
or permission to admit real customer-linked examples.

# B03-B scoped infrastructure and IAM plan

This is a proposed least-privilege boundary, not an applied configuration. The
physical project, bucket, Firestore database, KMS key and service-account names
are intentionally **TBD pending review**. Existing serving-app/staging approvals
do not cover these resources.

## Resource separation

| Plane | Proposed contents | Must not be shared with |
| --- | --- | --- |
| Authority object store | Immutable source/identity/legacy evidence, claim data, manifests, membership/index snapshots, alias evidence and signed receipt inputs | Serving artefact bucket, broad training bucket, public/runtime bundle |
| Registry store | Epoch, immutable pointers, proposal bindings, operation state, contamination holds and receipt metadata | Large row sets, labels, narratives or unbounded membership arrays |
| Training/learning read boundary | Only receipt-bound admitted learning objects after commit | Sealed confirmation objects, pending reservation objects, authority writes |
| Selection read boundary | Only receipt-bound model-selection objects | Training writes, sealed confirmation objects and authority mutation |
| Sealed evaluator boundary | Only the frozen confirmation objects and evaluator code required for one scored run | Training/selection reads, item-level export to workers or mutable labels |
| Signing boundary | Authority-owned KMS signing key and audit logs | Caller-supplied keys, local simulation receipts or model-serving identities |

## Identity roles to resolve

- `authority-writer`: generation-zero object creation/readback, registry
  transaction writes, and KMS signing; no serving or model-fit permission.
- `admission-reader`: private identity/history/index reads and candidate
  preparation; no labels, sealed reads, registry mutation or signing.
- `learning-worker`: read only on committed receipt-bound learning objects and
  manifests; no authority object creation, registry writes or sealed reads.
- `selection-worker`: read only on committed selection objects; no learning or
  sealed reads and no authority mutation.
- `sealed-evaluator`: read only on the confirmation prefix plus evaluator
  artifacts; no training/selection paths and no item-level result export.
- `operator-break-glass`: separate audited role, disabled by default; any use
  requires a recorded incident/change approval and cannot be a worker fallback.

Each role needs explicit deny/absence tests against the other prefixes. A runtime
service account must not inherit these roles merely because it can read serving
artifacts. Object ACLs, bucket IAM, Firestore rules and KMS IAM must be checked
as a combined path; one permissive layer invalidates the separation claim.

## Retention and failure controls

- Enable versioning/retention appropriate for permanent exclusions; no delete or
  overwrite path may remove a prior membership or contamination record.
- Keep orphan claim/index uploads unreachable from workers; a cleanup job may
  report candidates but must not delete without a separately approved retention
  policy and receipt/reference check.
- Log object generation, digest, role, operation ID, registry epoch, signer key
  version and caller identity. Do not log row payloads, labels, identity keys or
  sealed item decisions.
- Treat KMS, GCS, Firestore, registry, index and projection outages as deny;
  there is no cached allow or local preflight promotion.
- Verify cross-region/location choices, encryption/key custody, audit-log access,
  retention lock and deletion recovery before apply.

## Approval checklist before apply

1. Carlos approves the physical resource names and locations, confirming the
   benchmark store is separate from serving artifacts and training access.
2. Carlos approves the role-to-resource matrix and the sealed-evaluator export
   boundary.
3. Security/infra review confirms KMS custody, retention/deletion recovery,
   audit logs, Firestore transaction limits and cross-process identity tests.
4. Synthetic emulator/fake tests pass, followed by a separately approved live
   permission probe that writes no data and runs no candidate admission.
5. Only then may the adapter be connected to B04 consumer gates or any real
   candidate admission workflow.

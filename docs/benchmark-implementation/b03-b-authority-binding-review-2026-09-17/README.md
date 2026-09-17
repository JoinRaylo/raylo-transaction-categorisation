# B03-B authority binding review packet

Status: **proposal only; awaiting separate security approval**.

This packet follows the successful minimal API enablement recorded in
`b03-b-authority-api-enablement-2026-09-17`. It is the exact pre-apply review
boundary for the new authority project. It authorizes no IAM mutation, service
identity creation, resource creation, customer-data read, BigQuery export,
candidate reservation, labels, locked-set access, retraining, scoring or B04
integration.

Sol review: **APPROVE with control-plane conditions**. The API-only state is
accurately bounded, but this packet must not be treated as approval to mutate
IAM or create authority resources. Before real data, govern or replace the
direct Carlos Owner grant through the approved privileged/JIT path, complete
the organization-to-project effective-access review, and capture reproducible
command evidence with collection time and operation identifiers.

## Fixed scope

| Field | Value |
| --- | --- |
| Project | `raylo-txncat-authority-prod` (`357892832103`) |
| Region | `europe-west2` |
| Firestore database | `txncat-benchmark-authority` (regular Google-managed encryption; create pending) |
| Receipt key | `txncat-benchmark-receipts` (HSM asymmetric signing; create pending) |
| Storage key | `txncat-benchmark-storage` (HSM encryption; create pending) |
| Authority bucket | proposed `raylo-txncat-authority-prod-europe-west2`; confirm availability before creation; never reuse the old `raylo-production` bucket |

The four requested APIs and two automatically enabled dependencies are already
recorded in the API-enablement packet. Cloud Run and Artifact Registry remain
disabled.

## Proposed identities and permissions

Create these identities only after approval, with no project-wide broad roles:

- `txncat-authority-writer`: creates/gets private authority objects and writes
  registry records; signs receipts with the receipt key.
- `txncat-receipt-verifier`: gets only learning/selection worker objects,
  looks up the named registry, and verifies receipt public keys; it cannot
  issue receipts.
- `txncat-learning-worker` and `txncat-selection-worker`: invoke only the
  exact private verifier service; they receive no Storage, Firestore or KMS
  permissions.

The proposed custom-role/resource bindings are the matrix in
`b03-b-iam-isolation-design-2026-09-17/IAM_DESIGN.md`:

- Storage writer `create`/`get` only, restricted to `_authority/`, `private/`
  and the worker prefixes; no list, update, delete or `sealed/` access.
- Storage verifier `get` only, restricted to `worker/learning/` and
  `worker/selection/`; no list, create, update, delete or sealed/private
  authority access.
- Firestore writer only on the named database, with the smallest registry
  entity operations required by the adapter; no entity delete, database
  administration, import/export or other-database access.
- Firestore verifier `get` only on the named database; no registry list or
  mutation.
- Receipt signer only on the receipt key; no storage-key access, key
  administration, encryption/decryption or destruction.
- Receipt verifier only public-key/state-read permissions on the receipt key;
  no signing or key administration.

Every Storage condition must include the object resource type and canonical
`projects/_/buckets/<BUCKET>/objects/<PREFIX>` resource-name form. The adapter
must independently enforce claim-kind ↔ worker-prefix invariants; IAM
conditions are not a substitute for that protocol check.

Before any binding is applied, replace the placeholders in the reviewed diff
with the exact bucket/database/key/service names, service-account emails and
immutable unique IDs, complete CEL conditions, custom-role support checks,
service-account policies, `actAs`/token-creator absence, and the Storage
service-agent CMEK grant. Record the raw inventory command set, collection
time, operation identifiers or output hashes, and the effective allow/deny
matrix.

## Required apply and proof order

1. Security reviewer signs off the exact role permissions, conditions, service
   identities, key policy, inherited-access findings and the governed
   administrative Owner path.
2. Create the empty bucket, regular Firestore database and HSM keys with
   deletion protection/retention settings; verify the bucket CMEK service-agent
   grant separately.
3. Create the dedicated identities and custom roles, then apply only the
   reviewed resource/key/service bindings.
4. Read back direct and effective access, including ancestor group membership
   and service-account impersonation paths. Verify no default service account
   or broad project role has appeared.
5. Close the code gaps first: Google ID-token validation and immutable unique-ID
   mapping, authority/environment receipt binding, claim-kind namespace checks,
   verify-only separation, enabled key-version state checks, and retention/
   audit ownership.
6. Only when those checks pass, enable deployment APIs, deploy the private
   verifier, and repeat synthetic Stage 0–3 negative and positive proofs.

No fixture write is allowed until the resulting policy is proven to deny
worker direct reads, sealed/private reads, object listing, receipt signing and
cross-kind prefix substitution.

## Explicit non-goals

Do not reuse resources in `raylo-production`, grant project-level Storage or
Firestore administration, grant `roles/iam.serviceAccountTokenCreator` to
workers, create an admission/sealed-evaluator identity, access BigQuery or
Plaid, or claim that project creation/API enablement establishes dataset
membership or historical completeness.

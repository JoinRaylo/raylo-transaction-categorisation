# B03-B IAM and authority-isolation design

Status: **historical proposal; organization-level isolation gate superseded for
the internal benchmark; runtime IAM bindings applied and live proof pending**.

The later B03-B gate-reconciliation decision accepts inherited control-plane
administration as an internal-benchmark risk. This proposal's clean-ancestor
and effective-access requirements are no longer hard blockers for this use and
must not be read as evidence of effective isolation. Its exact runtime role
matrix, resource conditions, no-broad-access requirements and synthetic proof
sequence remain applicable before any real reservation. The applied identities
and bindings are recorded in the dated B03-B runtime-identities packet.

This packet records the next safe decision after the partially provisioned
synthetic scope. It does not authorize customer-data reads, candidate
reservation, labels, locked-set access, retraining, scoring, B04 integration,
or any IAM mutation.

## Read-only project finding

The current resources are in `raylo-production` (`601576302267`) and
`europe-west2`:

- `gs://raylo-production-txncat-benchmark-authority-europe-west2` has uniform
  bucket-level access, versioning, retention and the reviewed HSM storage
  CMEK, but its current bucket policy still contains legacy project-owner,
  project-editor and project-viewer bindings.
- Read-only project IAM inspection found unrelated project-level
  `roles/storage.admin` and `roles/storage.objectAdmin` grants, including
  service-account principals, and project-level `roles/datastore.user` grants
  including the Compute default service account and other unrelated runtime
  identities.
- `projects/raylo-production/databases/txncat-benchmark-authority` is empty,
  uses Google-managed encryption, and has the reviewed pessimistic concurrency,
  PITR and delete-protection settings. The project-level Firestore grants mean
  the named database is not an exclusive authority boundary in this project.
- No `txncat-*` service accounts or IAM bindings were found in the bounded
  inventory. No objects or Firestore documents were written.

These inherited permissions cannot be narrowed by adding a conditional allow
for new principals. Therefore the resources in `raylo-production` remain
**synthetic-only fixtures**. They must not hold a customer-linked Plaid
snapshot, membership, identity evidence, labels, sealed items or worker
artifacts. Do not remove existing production bindings as part of this task.

The approved remedy is a separately isolated authority project beneath
clean IAM ancestors, with no unrelated human/runtime principals. A project-level IAM deny design is a
possible alternative, but would need a separate security/infra review of every
principal and service-agent dependency; it is not assumed here.

At this design packet's capture, the approved project existed as
`raylo-txncat-authority-prod` (project number `357892832103`), under
`folders/45426850789` (`internal-services-monorepo`), with no APIs, service
accounts or authority resources. The later
`b03-b-runtime-identities-2026-09-18` packet records the applied identities and
bindings. It remains the only authority project planned for this increment;
no authority-staging project is needed.

## Receipt-verification deployment choice

Use one private Cloud Run service in `europe-west2` in the approved project:

`projects/raylo-txncat-authority-prod/locations/europe-west2/services/txncat-receipt-verifier`

The service has internal ingress, no unauthenticated access, and an image
pinned by digest. It exposes only the receipt-bound read operation. It does
not expose receipt issuance, registry mutation or arbitrary object reads.

`txncat-learning-worker` and `txncat-selection-worker` invoke this service and
receive no direct Cloud Storage, Firestore or KMS permissions. The service
validates a Google-issued ID token for the exact service audience and maps the
caller service-account unique ID to one fixed worker role. It must not trust a
role, audience or principal supplied in a request field or forwarded header.
The authority writer issues receipts separately, preferably as a
non-addressable job.

The current `AuthorityWorkerIdentity` is only an injected protocol. A
production token-validation adapter, fixed unique-ID mapping and synthetic
forged/forwarded/role-swapped token tests are still required.

## Exact matrix for the isolated project

The following is the proposed mutation set. The project ID is fixed; bucket,
database, key and service resource IDs are still pending exact resource review.
Grant only the listed permissions; do not substitute broad project roles.

| Identity | Resource and binding | Exact permissions/capability | Explicit absence |
| --- | --- | --- | --- |
| `txncat-authority-writer` | Authority bucket, conditional custom role `txncatAuthorityObjectCreateRead` | `storage.objects.create`, `storage.objects.get`; conditions for `_authority/`, `private/`, `worker/learning/` and `worker/selection/` only | No object list, update, delete or `sealed/` access |
| `txncat-authority-writer` | Named Firestore database through a project-level conditional custom role `txncatRegistryWriter` | `datastore.databases.get`, `datastore.entities.create`, `datastore.entities.get`, `datastore.entities.list`, `datastore.entities.update`; condition exactly `resource.name == "projects/raylo-txncat-authority-prod/databases/txncat-benchmark-authority"` | No entity delete, database create/update/delete, import/export, bulk delete or index administration |
| `txncat-authority-writer` | Receipt CryptoKey, key-level custom role `txncatReceiptSigner` | `cloudkms.cryptoKeyVersions.useToSign`, `cloudkms.cryptoKeyVersions.get` and `cloudkms.cryptoKeyVersions.viewPublicKey` for signing and the writer's self-check/state check | No key/key-version create, rotation, destruction, encryption/decryption or storage-key access |
| `txncat-receipt-verifier` | Authority bucket, conditional custom role `txncatWorkerObjectGet` | `storage.objects.get`; conditions for `worker/learning/` and `worker/selection/` only | No object list, create, update, delete, `_authority/`, `private/` or `sealed/` access |
| `txncat-receipt-verifier` | Named Firestore database through a project-level conditional custom role `txncatRegistryLookup` | `datastore.entities.get`; condition exactly on `projects/raylo-txncat-authority-prod/databases/txncat-benchmark-authority` | No registry list or mutation; no access to other databases |
| `txncat-receipt-verifier` | Receipt CryptoKey, key-level custom role `txncatReceiptVerifier` | `cloudkms.cryptoKeyVersions.get` and `cloudkms.cryptoKeyVersions.viewPublicKey` plus the role's required location/project-read permissions | No signing, verification-use, key administration or storage-key access |
| `txncat-learning-worker` | Exact verifier Cloud Run service | `roles/run.invoker` only | No bucket, Firestore, KMS, selection or sealed grants |
| `txncat-selection-worker` | Exact verifier Cloud Run service | `roles/run.invoker` only | No bucket, Firestore, KMS, learning or sealed grants |
| Cloud Storage service agent for the isolated project | Storage CryptoKey, key-level `roles/cloudkms.cryptoKeyEncrypterDecrypter` | Required only for the bucket's HSM CMEK attachment | No receipt-key access and no human/runtime substitution |
| Named deployer | Exact Cloud Run service and verifier runtime service account | `roles/run.developer` on that service and `roles/iam.serviceAccountUser` on the verifier runtime identity | No authority bucket, registry, KMS or token-creator grant |

Do not create or bind `admission-reader`, `sealed-evaluator` or break-glass
identities until their concrete resource boundaries and separately reviewed
need exist. In particular, the future admission identity must receive only
the customer-linked Plaid source access that is approved for candidate
preparation; it must not inherit authority-writer or worker permissions.

Cloud Storage prefix conditions must include the object resource type and use
the canonical `projects/_/buckets/<BUCKET>/objects/<PREFIX>` resource-name
form. A prefix condition is not a substitute for the adapter's claim-kind to
worker-prefix invariant. The adapter must reject a learning receipt pointing
to a selection object and vice versa before any live worker proof.

## Required code and proof gaps before mutation

The first five code controls are now implemented in the canonical adapter and
covered by the synthetic B03 suite; see
`b03-b-receipt-boundary-hardening-2026-09-17`. Live deployment wiring and
permission proofs remain pending.

1. Complete live Google ID-token/Cloud Run extraction and immutable
   service-account unique-ID proof.
2. Complete live authority/environment binding and claim-prefix configuration
   proof against the exact production resource names.
3. Prove verify-only deployment packaging cannot construct or receive an
   authority signer.
4. Define current/previous key-version overlap and retirement behavior, then
   prove it with live KMS permissions and state transitions.
5. Resolve retention/cleanup ownership and audit-log scope. The current
   30-day retention and 7-day soft-delete settings are not a claim of permanent
   exclusion-history retention.
6. In the isolated project, verify the Cloud Storage service-agent CMEK grant,
   bucket policy, Firestore conditional policy, key policy, inherited access,
   group membership and service-account impersonation paths before any fixture
   write.

## Review gate and next step

Sol review: **APPROVE with control-plane conditions** for the project
placement; IAM mutation and Stage 0 remain blocked by the unresolved
caller-authentication, namespace, key-lifecycle and effective-access
specifications. The production-project inherited-access finding remains a
hard stop for the old resources.

Minimal prerequisite APIs are now enabled; see the separate
`b03-b-authority-api-enablement-2026-09-17` packet for the exact post-operation
inventory. The concrete pre-apply binding proposal is recorded in
`b03-b-authority-binding-review-2026-09-17`. Cloud Run and Artifact Registry
remain disabled. The next decision is separate security approval of that exact
custom-role/resource-level binding packet. The local receipt hardening is
complete, but live deployment wiring and the remaining key/retention/access
proofs are not. Only after approval and live deny/allow proofs pass should the
synthetic-only Stage 0 bootstrap be considered.

### Evidence recorded

- Existing service-account inventory: bounded read-only list in
  `raylo-production`; no `txncat-*` identities found.
- Dedicated bucket IAM: read-only policy contained legacy project role
  bindings; project IAM showed unrelated storage-admin/object-admin grants.
- Project IAM: read-only query showed unrelated `roles/datastore.user`
  principals and other broad project roles.
- No customer data, Plaid rows, labels, benchmark membership, objects,
  Firestore documents, locked-set results, training or scoring were touched.

# B03-B authority resource provisioning

Status: **empty resources provisioned and verified; effective isolation waived
for the internal benchmark; runtime IAM remains pending**.

The bucket-policy snapshot in this packet is historical. The approved empty
bucket cleanup is recorded in the [follow-up IAM packet](../b03-b-authority-bucket-iam-cleanup-2026-09-17/README.md).

This packet records the current approved authority scope after the billing
prerequisite was resolved. It supersedes the resource coordinates and status
claims in `../b03-b-physical-scope-review-2026-09-17/` for the current authority
project only. That earlier packet is preserved as a historical record of a
`raylo-production` synthetic fixture scope; it is not an authority boundary and
must not hold customer-linked Plaid data.

The setup below creates infrastructure only. It does not authorise benchmark
consumption, candidate reservation, labelling, locked-set access, retraining,
scoring, promotion or B04 integration. No customer data, synthetic fixture,
object, Firestore document or row payload was written.

## Current resource scope

| Resource | Verified state |
| --- | --- |
| Project | `raylo-txncat-authority-prod` (`357892832103`), under `folders/45426850789` (`internal-services-monorepo`), `europe-west2` |
| Billing | `billingAccounts/012AD9-9C9BA6-3C2CAB`; read-back matched both `raylo-production` and the authority project |
| Keyring | `projects/raylo-txncat-authority-prod/locations/europe-west2/keyRings/txncat-benchmark-authority-europe-west2` |
| Receipt key | `.../cryptoKeys/txncat-benchmark-receipts`; HSM RSA PKCS#1 2048 signing, version 1 `ENABLED` |
| Storage key | `.../cryptoKeys/txncat-benchmark-storage`; HSM symmetric encryption, version 1 `ENABLED`, 90-day rotation, next rotation `2026-12-16T00:00:00Z` |
| Authority bucket | `gs://raylo-txncat-authority-prod-europe-west2`; regional `europe-west2`, Standard, uniform bucket-level access, public-access prevention, versioning, 30-day retention and 7-day soft delete; default HSM storage CMEK attached |
| Registry | `projects/raylo-txncat-authority-prod/databases/txncat-benchmark-authority`; Firestore Native Standard, `europe-west2`, pessimistic concurrency, PITR and delete protection enabled; Google-managed default encryption; no documents |
| User-managed service accounts | None created |

The Cloud Storage service identity was created only to satisfy the bucket's
HSM-CMEK dependency. Its key-level grant is exactly
`roles/cloudkms.cryptoKeyEncrypterDecrypter` on `txncat-benchmark-storage` for
`service-357892832103@gs-project-accounts.iam.gserviceaccount.com`. No worker or
authority runtime identity has been created or granted access.

Firestore deliberately uses Google's default encryption for registry metadata.
The new create command omitted `--kms-key-name`; no Firestore CMEK allowlist or
quota assumption is being used. The prior encrypted-database attempt belongs to
the historical physical-scope work and does not change this decision.

## Actual provisioning evidence

- Billing was enabled with the same account as `raylo-production` before the
  resource retry. The Firestore create returned operation
  `projects/raylo-txncat-authority-prod/databases/txncat-benchmark-authority/operations/LARkSKt_RZEgTbfjULS38hAqMnRzZXctZXBvcnRlDCIFEHqQyOAQBtWwleUICwovGg`.
- The first bucket create failed closed because the Cloud Storage service agent
  had not yet been granted access to the storage key. The service identity was
  then created, the exact key-level grant applied, and the bucket create
  retried successfully. This was an infrastructure bootstrap correction, not a
  data-path exception.
- The bucket read-back reports `versioning_enabled: true`,
  `public_access_prevention: enforced`, uniform bucket-level access, a
  2,592,000-second retention period and a 604,800-second soft-delete period.
- The Firestore read-back reports `PESSIMISTIC`,
  `POINT_IN_TIME_RECOVERY_ENABLED`, `DELETE_PROTECTION_ENABLED`, `STANDARD`,
  `FIRESTORE_NATIVE` and `europe-west2`.
- Enabled APIs are exactly `cloudbilling.googleapis.com`,
  `cloudkms.googleapis.com`, `firebaserules.googleapis.com`,
  `firestore.googleapis.com`, `iam.googleapis.com`,
  `iamcredentials.googleapis.com` and `storage.googleapis.com`. Cloud Run and
  Artifact Registry remain disabled.

## Post-provisioning access audit

The direct project policy contains Carlos's `roles/owner` grant and the
Firestore/Rules Google-managed service-agent grants. At provisioning time the
bucket had the normal legacy project-owner/editor/viewer bindings; those
bindings were subsequently removed from the empty bucket and are detailed in
the follow-up IAM packet. The parent folder policy grants
`group:team-infra-eng` `roles/owner`, and also grants folder administration and
project-creation/viewing roles to the listed engineering groups/users. The
organisation IAM policy could not be read by the active account, so the
organisation-to-project effective policy is not certified. The three managed
service-agent numeric IDs were exposed by failed metadata/policy reads, but
their service-account IAM policies were not readable by the active account;
impersonation paths are therefore not certified either.

Consequently the project is not proven to be an isolated authority boundary.
The later B03-B gate-reconciliation decision accepts that as an internal-
benchmark risk, so the inherited-access finding is no longer a hard blocker
for this use. It remains prohibited to represent the project as effectively
isolated or to treat a project-level allow matrix as preventing folder Owners
from bypassing it. Runtime identities, exact conditions, synthetic proof and
the authority CAS remain mandatory before any real reservation.

The next review must also fix the exact resource conditions and unique-ID
mapping for `authority-writer`, `receipt-verifier`, `learning-worker` and
`selection-worker`, choose the receipt public-key/rotation deployment, assign
retention and audit-log owners, and define the denied-access matrix. The staged
synthetic identity/CAS probes remain separately gated. No real linked-pool row
may be admitted until those proofs and the B04 admission review pass.

## Sol post-provisioning review

Sol reviewed the resource evidence as **CONDITIONAL**. The cryptographic and
storage bootstrap controls are accepted. The later internal-benchmark waiver
supersedes the clean-ancestor/effective-access condition for this use, but
service-account creation and IAM bindings still require the exact runtime
matrix and scoped cloud-change approval. The remaining conditions are:

1. Carlos, `team-infra-eng` and the inherited Joaquim administration path are
   recorded as governed control-plane principals, preferably through JIT/PAM;
2. Google-managed Firebase/Firestore/Storage service identities and their
   exact roles are inventoried, with impersonation paths checked;
3. the bucket's default `projectOwner`, `projectEditor` and `projectViewer`
   legacy bindings are removed through a separately approved change (completed
   for the empty bucket; see the follow-up IAM packet);
4. exact custom roles/CEL conditions, unique-ID mappings, key rotation overlap,
   audit logging and retention ownership are approved; and
5. the prior `raylo-production` bucket, registry and keys are marked
   superseded, synthetic-only and non-authoritative, with no old receipt keys
   accepted by the new verifier.

Until then, no identities, custom bindings, fixtures or live probes are
created. No data may be admitted.

## Evidence boundary

Infrastructure state changed (`cloud: true`), but all data-plane and model
state remains unchanged:

- no BigQuery/customer rows read or exported;
- no labels, benchmark membership, aliases or reservations written;
- no training, retraining, model fitting, locked-set access, scoring or B04
  consumer integration;
- no object or Firestore document written; and
- no deletion or retention lock performed.

The exact commands, collection time, resource identifiers, IAM findings and
mutation inventory are pinned in `verification.json`. The explicit historical
fixture decision is in [SUPERSESSION.md](SUPERSESSION.md).

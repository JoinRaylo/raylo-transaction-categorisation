# B03-B authority bucket IAM cleanup

Status: **complete for the approved empty-bucket cleanup; effective IAM remains a hard gate**.

This packet records the narrowly approved follow-up to the authority resource
provisioning packet. It removed the six legacy project convenience
member-role pairs from the empty authority bucket. The bucket policy is now
empty, and the temporary project-level recovery grant used to complete the
operation has been revoked. This packet does not create authority identities,
write fixtures, access customer-linked Plaid rows or authorise benchmark
consumption.

## Scope and evidence

The target was only:

`gs://raylo-txncat-authority-prod-europe-west2`

Before cleanup, the bucket policy was the default six member-role pairs with
etag `CAI=`:

| Role | Members |
| --- | --- |
| `roles/storage.legacyBucketOwner` | `projectEditor:raylo-txncat-authority-prod`, `projectOwner:raylo-txncat-authority-prod` |
| `roles/storage.legacyBucketReader` | `projectViewer:raylo-txncat-authority-prod` |
| `roles/storage.legacyObjectOwner` | `projectEditor:raylo-txncat-authority-prod`, `projectOwner:raylo-txncat-authority-prod` |
| `roles/storage.legacyObjectReader` | `projectViewer:raylo-txncat-authority-prod` |

The first two exact removals succeeded before the active account lost the
bucket-policy operator permission:

- removing `projectOwner` from `roles/storage.legacyBucketOwner` returned
  etag `CAM=`;
- removing `projectEditor` from `roles/storage.legacyBucketOwner` returned
  etag `CAQ=` and left exactly the four pairs shown in `verification.json`;
- the direct `projectViewer` removal then failed closed with
  `PERMISSION_DENIED storage.buckets.getIamPolicy`.

Carlos explicitly approved a short-lived project-level
`roles/storage.admin` recovery grant. It was bound to
`user:carlos.noblejesus@raylo.com` with the condition
`request.time < timestamp("2026-09-17T16:55:00Z")`, title
`temporary_bucket_policy_recovery`, and the stated cleanup description. Under
that grant, a fresh read confirmed the remaining four pairs and etag `CAQ=`;
the etag-protected empty policy update returned etag `CAU=`. A readback showed
the bucket policy as `{ "etag": "CAU=" }`. The temporary grant was then
removed with the exact matching condition.

## Final resource checks

The final project IAM readback contains only:

- Carlos's direct `roles/owner` binding; and
- the pre-existing Firebase Rules and Firestore Google-managed service-agent
  bindings.

The final bucket readback was performed while the recovery grant was active.
The bucket contained no live or noncurrent objects and no soft-deleted objects.
Its existing controls remained intact: regional `europe-west2`, Standard
storage, uniform bucket-level access, public-access prevention enforced,
versioning enabled, 30-day retention, 7-day soft delete and the default
authority storage HSM CMEK.

## Review boundary

Sol conditionally approved exactly the six legacy bucket binding removals while
the bucket was empty, subject to complete before/after policy and control
readbacks. Astra conditionally approved the temporary direct project
`roles/storage.admin` grant only as the explicitly authorised recovery path,
with immediate revocation and no broader IAM changes. Both reviews leave the
broader effective-IAM gate open.

The parent folder still inherits `group:team-infra-eng` as `roles/owner`, the
active account still cannot read organisation IAM, and managed-service-agent
metadata/impersonation policy paths remain uncertified. Carlos being the
project Owner does not resolve those inherited-control-plane questions. No
worker/writer/verifier identity, custom role, live probe, Firestore document,
synthetic object, customer row, label, reservation, model fit, retraining,
locked-set access, score or B04 consumer was added.

The exact commands, policy etags, approval/review record and mutation
inventory are pinned in [verification.json](verification.json). The earlier
resource packet remains the source for project, key, Firestore and billing
coordinates; this packet supersedes only its stale pre-cleanup bucket-policy
description.

## Next gate

Obtain a security/infra effective-access attestation covering inherited folder
and organisation access, IAM Deny/principal access boundaries, nested groups,
service-agent impersonation and governed control-plane principals. Only after
that review may the staged synthetic identity/CAS probes and later authority
fixtures proceed. This cleanup does not authorise customer-linked data access
or any evaluation-set admission.

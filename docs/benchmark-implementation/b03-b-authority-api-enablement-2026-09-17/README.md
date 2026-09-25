# B03-B authority API enablement

Status: **minimal prerequisite APIs enabled; IAM and authority resources pending**.

This is a control-plane milestone only. It authorizes no customer-data reads,
BigQuery export, candidate reservation, labels, locked-set access, retraining,
scoring or B04 integration. No staging authority project is being created;
local synthetic fakes and the existing staging application project remain
sufficient for development tests.

## Actual project state

| Field | Verified value |
| --- | --- |
| Project ID | `raylo-txncat-authority-prod` |
| Project number | `357892832103` |
| Lifecycle | `ACTIVE` |
| Parent | `folders/45426850789` (`internal-services-monorepo`) |
| API enablement | completed successfully on 2026-09-17 |
| Service accounts | none in project inventory after enablement |
| Direct project IAM | `user:carlos.noblejesus@raylo.com` → `roles/owner` only |

## Exact API result

The requested API set was:

- `cloudkms.googleapis.com`
- `firestore.googleapis.com`
- `storage.googleapis.com`
- `iam.googleapis.com`

The post-operation enabled-service inventory is:

- `cloudkms.googleapis.com` — `ENABLED`
- `firebaserules.googleapis.com` — `ENABLED` (automatically enabled dependency)
- `firestore.googleapis.com` — `ENABLED`
- `iam.googleapis.com` — `ENABLED`
- `iamcredentials.googleapis.com` — `ENABLED` (automatically enabled dependency)
- `storage.googleapis.com` — `ENABLED`

No Cloud Run or Artifact Registry API was enabled. No service-account,
bucket, database, KMS-key, Cloud Run service, object or Firestore-document
creation was performed in this step.

## Security interpretation

The direct project policy is currently narrow, but this does not by itself
prove the effective inherited policy is narrow. The parent folder remains a
privileged administrative trust root through `team-infra-eng@raylo.com`; the
complete ancestor chain and that group’s membership/impersonation paths still
require security review. API-created service agents must be re-audited if and
when resources are created.

## Next gated work

1. Complete and record the ancestor IAM/group audit through the organization.
2. Review the exact custom no-list Storage/Firestore roles and key-level KMS
   permissions, including service-agent CMEK access; IAM mutation requires
   separate security approval.
3. Close caller-token, claim-kind namespace, key-state/rotation,
   authority-binding and verify-only code gaps.
4. Only then enable deployment APIs, create dedicated identities/resources and
   repeat the synthetic Stage 0–3 proofs.

Until those gates pass, this project remains non-authorizing with respect to
the customer-linked Plaid pool.

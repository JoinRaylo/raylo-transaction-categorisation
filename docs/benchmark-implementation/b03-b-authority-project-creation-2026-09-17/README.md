# B03-B authority project creation

Status: **project provisioned; IAM and authority resources pending**.

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
| Display name | `TxnCat Authority Production` |
| Lifecycle | `ACTIVE` |
| Parent | `folders/45426850789` (`internal-services-monorepo`) |
| Labels | `purpose=benchmark-authority`, `environment=prod`, `data-classification=restricted` |
| Created | `2026-09-17T14:03:17.805Z` |
| Enabled APIs | none; created with `--no-enable-cloud-apis` |
| Service accounts | none |
| Buckets, databases, keys and services | none |

The project was created beneath the common internal-services folder, not the
staging child folder. The folder hierarchy was inspected read-only. The
`team-infra-eng@raylo.com` group inherits Owner on the parent folder and is
the administrative control-plane trust root; it is not an authority runtime,
worker audience, receipt issuer or normal deployer. This path must be governed
as privileged administration, with membership, IAM, impersonation, KMS and
Cloud Run deployment changes audited and alerted.

Sol review: **APPROVE with control-plane conditions**. The placement is
acceptable if the complete ancestor chain is audited, the administrative group
is tightly governed, and no runtime identity receives inherited broad access.
The existing staging project is not reused for authority data because its
deployer has broad Storage, Firestore, Cloud Run and IAM administration.

## Next gated work

1. Audit the complete ancestor chain through the organization and record the
   effective control-plane principals.
2. Obtain separate approval to enable only the required APIs; do not enable
   APIs or create service identities implicitly.
3. Review and apply the exact custom no-list Storage/Firestore roles and
   key-level KMS permissions in the isolated project. IAM changes require
   separate security approval.
4. Create the private receipt-verifier deployment and dedicated worker
   identities only after the caller-token, namespace, key-state and
   authority-binding code gaps are closed.
5. Repeat the synthetic Stage 0–3 proofs in this project before any real
   authority data is admitted.

Until those gates pass, the existing production-project bucket and registry
and this new project are both non-authorizing with respect to the customer-
linked Plaid pool.


# B03-B authority resource bootstrap

Status: **blocked before resource creation by project billing prerequisite**.

The approved next mutation was limited to creating an empty HSM keyring/keys,
an empty CMEK-backed authority bucket and an empty regular Firestore registry.
The first command attempted only the keyring, and Cloud KMS rejected it before
creation because billing is disabled. No IAM bindings, identities, data,
fixtures, labels, reservations, training or scoring were performed.

## Actual evidence

| Field | Verified value |
| --- | --- |
| Project | `raylo-txncat-authority-prod` (`357892832103`) |
| Project state | `ACTIVE` |
| Billing metadata | no `billingAccountName` returned by read-only project description |
| Attempted operation | `gcloud kms keyrings create txncat-benchmark-authority-europe-west2 --location=europe-west2 --project=raylo-txncat-authority-prod --quiet` |
| Result | `FAILED_PRECONDITION: Billing is disabled for project 357892832103` |
| Follow-on resource operations | not attempted |

The resource plan remains unchanged: the new project is the only authority
project, the old `raylo-production` fixtures remain synthetic-only, and no
staging authority project is needed.

## Required user-controlled prerequisite

Associate the project with an approved billing account, with the intended cost
and budget controls, before retrying. This is a financial/governance action and
must not be guessed or performed by the agent. After that prerequisite is
explicitly approved, recheck project metadata and the empty resource inventory
before retrying the resource sequence.

Until then, keep Cloud Run/Artifact Registry disabled, IAM unbound, and the
customer-linked Plaid pool inaccessible.

# B03-B effective IAM gate resolution

Status: **gate characterized; external control-plane action still required**.

This packet records the final read-only diagnosis of the authority boundary. It
does not apply IAM, enable APIs, create identities, write fixtures, read
BigQuery, or authorize benchmark consumption.

## What the live checks show

The approved authority project is `raylo-txncat-authority-prod`
(`357892832103`) in `europe-west2`. Its ancestry is:

`project → folder 45426850789 (internal-services-monorepo) → organization 978952261329`

The direct project IAM policy contains only Carlos as `roles/owner` and the
pre-existing Firebase Rules and Firestore managed service-agent bindings. The
bucket policy cleanup is complete and its temporary recovery grant was revoked,
as recorded in the companion cleanup packet. The authority bucket and
Firestore registry remain empty.

The parent folder directly grants `group:team-infra-eng@raylo.com`:

- `roles/owner`;
- `roles/resourcemanager.folderAdmin`; and
- `roles/resourcemanager.projectCreator`.

The folder also grants Joaquim folder administration/editor and the
contributor group folder viewer/project creator access. No dedicated
user-managed authority or worker service accounts exist yet.

This means Carlos's direct project Owner binding is not the missing permission.
It proves Carlos can operate the project, but it does not prove that the
authority project is isolated from the inherited control-plane group or from
organization-level IAM Deny, principal-access-boundary, nested-group or
service-account impersonation paths.

## Recommended resolution

The preferred fix is a security/infra-admin change that places the authority
project under a dedicated clean folder with no broad human/runtime inheritance.
Retain Carlos through a governed direct or JIT administrative path and keep
managed service agents limited to their exact service roles. The shared
`internal-services-monorepo` folder must not be changed just to fix this one
project.

The alternative is a separately reviewed project-level IAM Deny design for the
inherited group and every other effective principal. It must enumerate service
agent dependencies and cannot be applied safely from this packet. Adding more
Owner/Storage Admin bindings, relying on the empty bucket policy, or treating a
local preflight result as authority does not resolve the gate.

## Minimum control-plane attestation

Before any worker/authority identity or fixture is created, security/infra
should provide an export or signed attestation covering:

1. organization and folder allow/deny policies plus principal access
   boundaries;
2. direct and nested membership of `team-infra-eng@raylo.com` and all other
   principals inherited by the project;
3. service-agent identity, unique-ID and impersonation/token-creator paths;
4. the governed Carlos administrative path and break-glass process; and
5. the exact custom roles/CEL conditions for the authority writer, verifier,
   learning worker and selection worker from the reviewed IAM matrix.

The live proof then needs to show, without data writes, that the authority
writer can use only its authority paths, the verifier can read only committed
learning/selection objects and registry lookups, learning/selection workers
can invoke only the exact verifier, and all roles are denied sealed/private,
cross-kind, list, mutation and receipt-signing paths as applicable.

Only after those proofs pass can the next sequence begin: synthetic Stage 0
authority probes, then a fresh bounded customer-linked Plaid admission profile,
the managed 500-row pilot reservation, and three independent annotation batches.
No real candidate, label, locked set or training consumer is admitted by this
diagnosis.

## Read-only limitations observed

The current account cannot read organization IAM. Cloud Identity group-membership
inspection and Policy Troubleshooter checks also could not run because their
APIs are disabled in the authority project. They were not enabled: enabling
new APIs would change project state and would not itself establish the required
attestation. These limitations are evidence that the gate remains open, not
evidence that the inherited access is absent.

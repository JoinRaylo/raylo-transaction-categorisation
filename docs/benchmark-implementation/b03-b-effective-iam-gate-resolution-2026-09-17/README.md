# B03-B effective IAM gate resolution

Status: **strict effective-isolation gate waived for the internal benchmark; minimum integrity controls retained**.

This packet records the final read-only diagnosis and Carlos's internal-
benchmark risk acceptance. The project does not have certified organization-
level effective isolation, but that is no longer a blocker for this benchmark.
This packet does not apply IAM, enable APIs, create identities, write fixtures,
read BigQuery, or authorize benchmark consumption.

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

Carlos's direct project Owner binding is therefore not a missing-permission
issue. The read-only checks do show a broad inherited control-plane path, but
Carlos accepts that risk for this internal, versioned benchmark. This is a
scope decision, not evidence that the project is isolated from the inherited
group or from organization-level IAM Deny, principal-access-boundary,
nested-group or service-account impersonation paths.

## Accepted internal-benchmark disposition

The strict clean-folder move and organization-level effective-IAM attestation
are not required to start this internal benchmark. The existing dedicated
authority project, bucket and registry remain the benchmark scope, and trusted
infrastructure administrators may retain inherited control-plane access. The
shared `internal-services-monorepo` folder still must not be changed just to
fix this project.

This waiver does not permit broad runtime access, local authority, or a bypass
of dataset separation. The authority writer, verifier, learning worker and
selection worker still use named identities, least-privilege resource paths,
exact receipts, immutable/versioned artifacts and the canonical CAS protocol.
The three evaluation views remain permanently separated from training and
selection, with the existing event/account/customer, effective-input,
unfamiliar-family and alias protections. Only the customer-linked Plaid pool
is eligible, and anonymous-ID recovery remains closed.

## Minimum retained controls and future review

The next implementation steps may proceed after the no-data synthetic checks:

1. create the named authority/verifier/learning/selection identities and apply
   the reviewed least-privilege bindings;
2. run synthetic Stage 0 allow/deny, receipt and cross-process probes;
3. run a fresh bounded customer-linked Plaid admission profile and reserve the
   500-row pilot;
4. obtain three independent annotations using the approved Gemini 3.8 Flash,
   Gemini 3.7 Flash and Sonnet 5 routes, escalating disagreements to Carlos;
5. freeze the representative, unseen-input and unfamiliar-merchant views,
   augment hinge and transformer training, and record the supervised retrain.

The following remain required evidence, but are no longer organization-level
blockers: direct and nested membership of inherited admin groups, service-agent
unique IDs and impersonation paths, the exact custom roles/CEL conditions, and
the governed Carlos administrative path. Any benchmark schema, sampling policy,
authority project or intended use change creates a new benchmark version and
requires this risk acceptance to be revisited. Production promotion requires a
separate effective-isolation review.

The live permission proof must still show, without customer writes, that the
authority writer can use only its authority paths, the verifier can read only
committed learning/selection objects and registry lookups, learning/selection
workers can invoke only the exact verifier, and the runtime roles are denied
sealed/private, cross-kind, list, mutation and receipt-signing paths as
applicable.

## Previously identified control-plane limitations

The current account cannot read organization IAM. Cloud Identity group-membership
inspection and Policy Troubleshooter checks also could not run because their
APIs are disabled in the authority project. They were not enabled: enabling
new APIs would change project state and are not needed for the internal-
benchmark waiver. These limitations remain recorded for future security review;
they are not evidence that inherited access is absent.

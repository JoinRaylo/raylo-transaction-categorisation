# B03-B gate reconciliation

Status: **internal-benchmark risk accepted; runtime and data-integrity gates
retained**.

This packet records Carlos's decision that organization-level/effective IAM
isolation is not a hard requirement for this versioned internal benchmark. The
benchmark must not claim effective isolation. The decision accepts inherited
control-plane administration as a documented risk while retaining the controls
that make the benchmark trustworthy as an internal measurement instrument.

No cloud mutation, BigQuery query, customer-row export, reservation, label,
synthetic fixture, model call, retrain, locked-set access or score occurred for
this reconciliation packet.

## Canonical decision

- The dedicated authority scope remains `raylo-txncat-authority-prod` in
  `europe-west2`, with its named bucket, Firestore registry and HSM keys.
- No authority-staging project is needed for this benchmark version.
- The earlier `raylo-production` authority-shaped bucket, registry and keys
  remain preserved historical synthetic fixtures only; they are not in the
  verifier trust set and must not receive new data or receipts.
- The inherited `team-infra-eng` control-plane path and any uncertified
  organization-level IAM behavior are accepted risks for this internal use.
  This is not evidence that those administrators or service agents are unable
  to bypass project-level policy.
- A later production promotion, materially different intended use, schema or
  sampling policy, or authority-project change reopens the isolation review.

## Controls that remain mandatory

Before any real reservation:

1. Use only the customer-linked Plaid pool with one unambiguous
   assessment-to-checkout-to-user-to-customer link. Anonymous-ID recovery stays
   closed.
2. Complete and independently pin event aliases, identity history,
   effective-input exposure, legacy membership, merchant-family coverage and
   the representative sampling frame/weights. Unknown history remains
   quarantine, not a completeness claim.
3. Allocate whole connected event/account/customer/assignment blocks through
   the canonical compare-and-swap authority. Local preflight remains a
   non-authorizing screen.
4. Record an append-only exclusion ledger consumed by both hinge and
   transformer training/selection paths. A reserved evaluation row or any
   connected protected group is permanently excluded from training and model
   selection; freeze or release review never lifts that exclusion.
5. Prove the named authority/verifier runtime, least-privilege resource paths,
   authority/environment-bound receipts, claim-kind prefixes, signed lineage,
   idempotency and cross-process CAS behavior with synthetic data first.

Before the 500-row annotation pilot:

1. Commit an authoritative, opaque 500-row reservation and manifest after all
   preceding gates pass.
2. Bind each request to the manifest, source snapshot, content, taxonomy,
   guide and prompt digests. Send only the reviewed transaction projection;
   never send customer/account/source identifiers or provider category labels.
3. Submit exactly one independent batch for each of Gemini 3.8 Flash, Gemini
   3.7 Flash and Sonnet 5. Keep provider failures explicit and do not silently
   retry, substitute a model or fill a missing vote.
4. Treat three-model agreement as descriptive annotation-method evidence, not
   an automatic gold label. Any disagreement, incomplete result or schema
   failure is raised to Carlos for a decision. The separate requirement for
   two independent human labels plus adjudication still applies to a later
   human-gold evaluation set unless explicitly superseded.

## Reconciled gate state

| Gate | State | Effect |
| --- | --- | --- |
| Effective organization-level isolation | **Waived for this internal benchmark** | No isolation claim; no shared-folder mutation |
| Project/resource scope | **Verified** | New authority coordinates only; old resources remain synthetic-only |
| Runtime identities and exact bindings | **Applied** | Four keyless identities, six custom roles and scoped writer/verifier bindings; live proof pending |
| Synthetic live Stage 0–3 proof | **Pending** | No fixture or live allow/deny proof yet |
| Candidate history/family/legacy/block/weight evidence | **Pending** | Current 5,000-row engineering draw has zero eligible view combinations |
| Authoritative 500-row reservation | **Pending** | No rows reserved or labelled |
| Three provider annotations | **Pending** | No Gemini or Anthropic call for real data |

The current candidate profile remains planning evidence only: 5,000 linked
events were profiled, but representative view rows are all quarantined; the
unseen-input and unfamiliar-merchant views have overlap rejects plus unknown
history/family/legacy quarantine. The profile does not authorize consumption.

## Supersession notes

The older IAM design and binding-review packets retain useful permission
matrices, resource conditions and non-goals, but their clean-ancestor and
organization-level effective-access requirements are superseded for this
internal benchmark by this decision. Their runtime requirements are not
superseded: no broad worker access, direct generic object reads, local receipt
fallback, authority bypass, or cross-plane consumption is allowed.

The runtime identity/binding mutation is now recorded in the dated
`b03-b-runtime-identities-2026-09-18` packet. Synthetic fixture creation and
live proof remain separately controlled. The next bounded action is to run
synthetic-only authority proofs before returning to admission evidence.

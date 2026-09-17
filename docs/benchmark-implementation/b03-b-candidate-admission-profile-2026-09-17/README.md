# B03-B bounded candidate admission profile

Status: **candidate profile captured for admission planning; no candidate
admitted**.

This milestone makes the first bounded, customer-linked Plaid candidate draw
and profiles it against the pinned B01/B02 evidence. The draw is a deterministic
hash-ranked engineering sample, not a representative population sample and not
an evaluation set. It is intentionally private and opaque. No provider or human
label was requested, no row was reserved, and no benchmark/training/selection
state changed.

Carlos's decision to accept the organisation-level/effective-IAM isolation risk
for an internal benchmark is recorded in the preceding risk-acceptance packet.
The waiver does not remove logical train/selection separation, input and
merchant-family novelty checks, connected group protection, authority-owned
claims, CAS or authenticated receipts.

## Candidate draw

- Project/location: `raylo-production`, EU.
- Source: `raylo-production.dbt_production.intermediate_credit_plaid_transactions`.
- Query: bounded `SELECT`, current assessment → checkout → user → customer links,
  exactly one record at each required link, and no anonymous-ID recovery. The
  result carries and the loader validates the four one-to-one link counts.
- Seed: `b05-pilot-source-v1`; limit: 5,000; result: 5,000 distinct account /
  transaction events.
- Dry-run and executed bytes: `8,657,706,119`; billed:
  `8,658,092,032`; BigQuery job:
  `txncat_candidate_fe166fcb-13ce-4ce4-9685-4599fcf33f02`.
- SQL SHA-256:
  `4b457cf50800416d9db25391f179e30559b0303b4bc7e3d4e9a9b5d9d5b853da`.
- Runner SHA-256:
  `e6c52f5e584f3b9fa0b7e85e1986b16ce6efec5c33b7367a36b0418b283d0e0b`.
- Private result SHA-256:
  `f9c549ee7a8a6bbfaec8999d3edaf2dca22f0d4f4fa463a486dcc3fd5a8f32ef`.

The query and candidate result are owner-only private files. Provider category
fields are not included in the annotation projection.

## Profile evidence

The local profiler verifies the candidate receipt, exact B01 inventory hashes,
the B02 private exposure index and the prior legacy membership digests. It also
binds the receipt to the exact extractor scope contract and validates the
one-to-one link evidence. It
scans all 14 named historical input sources and 18 merchant sources plus the
two legacy membership streams. The aggregate profile is:

- effective-input matches: 378 hinge sparse, 2,222 surface-fold, and 2,195
  token-48; the union produces 2,224 strict-view overlap rejects;
- merchant text present on 3,212 rows, blank on 1,788; exact merchant-name
  presence found for 2,624 rows; reviewed families: 0;
- connected blocks: 4,672 accounts (maximum 4 rows), 4,542 customers and
  assignments (maximum 5 rows);
- representative view: 5,000 quarantined;
- unseen-input view: 2,224 rejected and 2,776 quarantined;
- unfamiliar-merchant view: 3,451 rejected and 1,549 quarantined;
- eligible view combinations: none.

The profile records `event_aliases_verified=false`,
`identity_history_complete=false`, `input_history_complete=false`,
`family_history_complete=false` and `legacy_index_complete=false`. It carries
`authorizes_consumption=false` and `rows_reserved_or_labelled=0`. The private
opaque sidecar is mode `0600`; only its digest is recorded in the aggregate
profile.

The profile is pinned to policy
`benchmark-admission-profile-policy-v1` and records code, query, scope-contract
and policy digests. These are lineage controls, not an authority signature.

## What this establishes

It establishes a reproducible, current customer-linked candidate draw and an
engineering screen that fails closed when the evidence needed for a view is
unknown. It does not establish representative weighting, historical identity
aliases, complete fit/selection exposure, unfamiliar merchant families, an
independent legacy exclusion index, or managed authority state. Exact merchant
name absence is not family absence.

No retrain, inference score, locked-set access, provider annotation, label write,
Firestore write, Cloud Storage write or authority reservation occurred.

## Review gate and next step

The independent protocol review is recorded in `verification.json`. A Sol review
held the pre-hardening profile on scope, linkage, permanent exclusion and
authority-lineage gaps; the concrete scope/linkage and code/policy pinning fixes
are now included, while the authority gaps remain intentionally open. The next
real-data gate is to complete the missing alias/history/family and block/weight
evidence, then prove the retained managed authority runtime and claim CAS. Only
after that gate may a 500-row manifest be reserved and sent separately to
Gemini 3.8 Flash, Gemini 3.7 Flash and Sonnet 5. Disagreements remain visible
for Carlos; they are not auto-adjudicated. The resulting benchmark remains
permanently unavailable to training and model selection until its freeze and
release review.

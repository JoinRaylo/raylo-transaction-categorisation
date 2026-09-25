# G3 admission design (AIE-510)

Gate: `candidate-read-authorised` → `admission-authorised`. Human approval:
Carlos, 2026-09-22 — "put together a suitable candidate evaluation dataset …
and … make sure that we can identify said transactions so that we can remove
them when it comes to doing a final retrain of our TxCat-1 model and our risk
model".

## Scope

G3 produces admission **design and evidence**: blocker resolution, the bounded
account-evidence read, deterministic proposed-membership selection for the
1,000-row core expansion (800 representative / 150 unseen-input / 50
unfamiliar-merchant on top of the immutable 500-row pilot), a proxy-targeted
bounded draw for the 500-row rare-leaf supplement, allocation verification
against the frozen `AllocationDesign`, and the expanded protected-keys artifact.
It does **not** commit membership: the admission receipt and the managed
reservation/consumer gate are the G4 authority boundary, and every artifact
here remains `authorizes_consumption=false`.

## Blocker resolution map (from the G2 lineage blockers)

| Blocker | Resolution | Cost |
|---|---|---|
| pending/reconnection aliases | full retained account-history pull over both materialized tables; pending-free reconnect-group history certifies no enumerable alias key | one bounded SELECT per table (~14 GB scan) |
| historical identity completeness | same pull: complete only when every retained observation for the account resolves to one customer | shared |
| effective-input history | declared-corpus completeness manifest binding the pinned exposure index; absent hits become certified not-found | artifact + sign-off |
| reviewed merchant-family index | deterministic proposal over candidate families; a reviewed version requires explicit human review | artifact + review |
| legacy membership migration | MembershipManifest over declared legacy memberships; all 10,663 regression members are `source_event_identity="unrecovered"`, so exclusion is input-level via the bound index | artifact |
| managed reservation gate | **not resolved at G3** — G4 boundary | — |

The certified alternative for aliases — a raw `external_requests`
`pending_transaction_id` sidecar — was costed at TB scale (the table is
clustered only on ingestion day) and is documented in the scope doc as a
rejected-for-cost path; the retained-history certificate bounds the same
admission surface.

## Removal identification

The proposed memberships are emitted in the `txncat-private-eval-membership-v1`
schema (raw provider `account_id`/`transaction_id`/`customer_id`, `role=eval`),
the format `load_protected_membership` parses into a `ProtectionSet`; committed
artifacts carry the membership digest and the opaque `protected_keys` union.
That is the mechanism by which the admitted rows are identified and removed at
the TxCat-1 and risk-model retrains — enforced by `check_member` /
`exclude_protected`, not a manual lookup.

## Results (evidence only, `authorizes_consumption=false`)

Private store: `~/.local/share/raylo-txncat/benchmark-expansion-2026-09-22/`.

**Evidence resolution** (`resolved/`, `account-evidence/`, `sibling-evidence/`):
all 10,000 candidate accounts covered; zero transaction-ID collisions; all
4,213 pending pairs resolve to posted history under the same key (pending is a
same-key state transition, not an enumerable alias); 1 churn account, 108
accounts with unresolved links, 673 candidates hit legacy member projections;
17,293 customer-account pairs discovered, 8,483 siblings, all covered. Two
human review gates remain open: declared-corpus sign-off and family-registry
review.

**Core expansion** (`selection-ifsigned/`): all three view targets fill
(800/150/50 = 1,000 rows) under the signed-manifest scenario; status is
`shortfall` only because **T1 route minimum is unmet — 17 T1 rows exist in the
whole frame (pilot: 0) vs 25 required**. All other constraints met (T2 25, T5
51, T7 308, T6+T7 793, unfamiliar T6/T7 share 0.70, customer cap 4). The T1
deficit is reported, not manufactured.

**Rare-leaf supplement** (`supplement-candidates/`, `supplement-proposal/`):
41,099-row bounded pool (1,101 targeted + 39,998 tail, 23.4 GB billed), 2,144
roster-hit rows across 22 leaves; proposal selects **413/500** — an honest
shortfall: `account_misuse`, `balance_transfer_fee`, `clothing_maternity` have
zero hits anywhere; `camping_equipment` 9/20, `housing_benefit` 10/20,
`card_payment_unspecified` and `transfer_mobile_app` 17/20. 87 rows excluded
as core overlap, 61 ownership-quarantined, 29 cap rejections. The supplement
is excluded from the headline denominator.

**Membership bundle** (`membership-bundle/`): 1,413 proposed `MembershipEntry`
records (manifest `g3-proposed-eval-membership-v1`), protected-key union
(1,913 events incl. the 500 pilot), the private raw-id CSV
(`proposed-protected-membership.csv`) loadable by
`load_protected_membership` — verified to fail closed at `check_member` — and
the opaque `protected-key-map.jsonl` for evidence tracing.

## Files

- `g3-admission-scope.json` — the approved scope, bounds and resolution design.
- `phase-ledger.json` — the ledger after the `admission-authorised` transition.
- `verification.json` — bound digests for every G3 artifact plus the explicit
  unresolved-items register (38 uncovered legacy members, unresolved-link
  accounts, T1 and supplement shortfalls, pending human gates).

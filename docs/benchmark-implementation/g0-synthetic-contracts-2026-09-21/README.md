# G0 synthetic two-cohort contracts (AIE-510)

Status: **complete bounded local milestone; synthetic only; non-authorizing**.

The app worktree now contains the contract layer for the 2,000-row benchmark
expansion: an unchanged 1,500-row core (500 pilot + 1,000 expansion rows) plus a
separately reported 500-row rare-leaf supplement. Cohort membership is immutable
and hash-bound, allocation is verified against a frozen design, the pilot parent
is checked byte-for-byte, an explicit eight-state phase ledger and append-only
receipt chain pin every gate, and annotation retries have bounded, labelled-free
exhaustion semantics.

This is a planning contract, not a real evaluation-set builder. No module reads
source data, queries BigQuery, calls a provider, touches cloud state or accepts
an authority receipt for a real gate. Every artifact carries
`authorizes_consumption=false` and `scope="synthetic_only"`. No real row was
read, reserved, labelled, scored or exported; the phase ledger's real state
remains `synthetic-only`.

## What was implemented

- `lib/raylo-txncat/src/raylo_txncat/benchmark_cohort.py` — `CohortMember` and
  `CohortMembership` with cross-cohort uniqueness, alias and ownership rules;
  `PilotParent`/`PilotVerification` proving pilot immutability with exception
  records instead of replacements; `AllocationDesign`/`AllocationReport`
  verifying counts, tier constraints, caps and alias coverage without filling
  shortfalls; `RareLeafSpecification`, proxy resolution and deterministic
  supplement selection that excludes core overlap and never borrows across
  leaves; `CohortMapping`, `protected_keys()` and `require_consumable` failing
  closed over the union of core and supplement keys.
- `lib/raylo-txncat/src/raylo_txncat/benchmark_lifecycle.py` — `PhaseLedger`
  with the eight-state no-skip progression, halting on failed or unavailable
  authority outcomes and unknown-stop clearance rejection; `CONFLICT_MATRIX_V1`
  (nine rules, transitive versus non-transitive semantics); `ReceiptChain` with
  ordered kinds, parent/root binding and stable-binding change rejection;
  `verify_admission_receipt` binding the exact expanded membership digest and
  `verify_derivation` subset semantics.
- `lib/raylo-txncat/src/raylo_txncat/benchmark_annotation.py` — backward
  compatible additions only: `"cancelled"` attempt status with the same
  error-code requirement as other failures, `RetryPolicy`, `ExhaustionRecord`,
  `exhausted_items` and `partial_batch_items`. Existing digests, models and
  patterns are unchanged.

## Allocation table

| cohort                | pilot | new  | final |
|-----------------------|-------|------|-------|
| representative        | 250   | 800  | 1050  |
| unseen_input          | 150   | 150  | 300   |
| unfamiliar_merchant   | 100   | 50   | 150   |
| rare_leaf_supplement  | 0     | 500  | 500   |
| **total**             | 500   | 1500 | 2000  |

Headline rule: only `cohort=core AND primary_view=representative` rows count
toward the production-weighted headline (denominator 1050). Supplement rows are
excluded even when they carry representative eligibility.

## Key negative guarantees

- A receipt bound to the old 1,500-row membership cannot authorize the expanded
  2,000-row membership; pilot verification is bound to its membership digest.
- Dropped, reassigned or re-contented pilot rows raise `PilotImmutabilityError`;
  eligibility defects become exception records, never substitutions.
- Local receipts, plain dicts and allocation reports cannot advance the ledger;
  unknown stop clearances are rejected; stale authority epochs halt.
- Supplement candidates carrying final labels, votes, agreement or adjudication
  fields are rejected; selection never authorizes consumption.
- Cancelled or exhausted annotation attempts produce no votes and no labels.

## Verification

- Focused tests: `test_benchmark_cohort.py` 30 cases, `test_benchmark_lifecycle.py`
  29 cases, `test_benchmark_annotation.py` 17 cases — 76 passed.
- Startup trio (benchmark, exposure, preflight): 116 passed, unchanged.
- Allocation/authority/membership/regression set: 65 passed.
- Full `lib/raylo-txncat/tests` unit suite: 1291 passed.
- Ruff check and format check: passed; `git diff --check`: clean.

Exact commands, fixture counts, negative-case mapping and file digests:
[`implementation.json`](implementation.json), [`verification.json`](verification.json).
Design note: [`DESIGN.md`](DESIGN.md).

## Limitations and next gate

Not implemented here: the candidate frame query, pilot probability
reconstruction, the core expansion sampler (G3), the annotation manifest for
expansion items (G4), the importer (AIE-512), B04 consumer wiring (AIE-513),
real phase ledger advancement and the research CLI adapter.

The next gate is G1 pilot closure — AIE-511 adjudication decision, AIE-512
importer evidence, AIE-513 enforcement evidence; no candidate read, reservation,
annotation dispatch or release is authorised by this packet.

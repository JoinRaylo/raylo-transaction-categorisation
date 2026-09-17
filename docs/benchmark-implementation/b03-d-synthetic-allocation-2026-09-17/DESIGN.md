# B03-D synthetic candidate allocation design

Status: **bounded local contract implemented; synthetic only; non-authorizing**.

This increment provides a deterministic planning primitive for assigning opaque
candidate blocks to the pilot, evaluation, selection and training roles in the
approved three-view plan. It is deliberately downstream of B02 preflight and
deliberately upstream of real source admission. It does not read source rows,
resolve identities, calculate history completeness, reserve data, label items,
or grant a worker permission to consume anything.

## Contract mapping

| B02 concept | B03-D representation | Boundary |
| --- | --- | --- |
| Hash-bound source snapshot | `source_snapshot_sha256` on the request and every candidate | All candidates must reference the same declared snapshot; the hash is not proof of the snapshot contents. |
| Verified subject/group identity | Opaque `observation`, `event_aliases`, `accounts` and `customers` | Group closure must be produced by a later verified admission job; this module rejects contradictory precomputed blocks. |
| Serving/research input projections | Versioned `Projection` values | Equality is `(projection version, opaque token)`; missing history is not treated as absence. |
| Three evaluation views | B02 `View` values in `views` | Views are metadata/questions. A member may carry several views in one role; protections are unioned. |
| Sampling block | `assignment_block` | The allocator selects whole blocks and never splits their rows. |
| Existing protection | `existing_assignments` and `existing_protection_sha256` | Prior assignments are immutable inputs to this preview and are canonically hashed; durable retention still belongs to B03 authority. |
| Planned purpose/role | Strict `AllocationPartition` and ordered `AllocationBudget` | Pilot/evaluation/selection budgets must precede training; duplicate roles and exact quota failures are rejected. |
| Proposal evidence | `AllocationResult` and `allocation_digest` | The result is explicitly `scope="synthetic_only"` and `authorizes_consumption=false`; it is not a reservation or receipt. |

The implementation reuses the canonical B02 `Frozen`, `Projection`, `View`,
`Sha256` and `Identifier` types. The synthetic candidate type is versioned and
has a literal `source_kind="synthetic_fixture"`, fixture ID and policy version.
The literal boundary is intentional: a future production admission adapter must
introduce a separately reviewed type and cannot pass real candidates through
this synthetic contract by changing a boolean or adding an environment field.
The allocator revalidates request and candidate model dumps at its entry point,
so Pydantic `model_copy(update=...)` cannot bypass that literal boundary.

## Role and protection semantics

`AllocationPartition` is a strict, versioned role vocabulary:

1. `annotation_pilot` — the separate annotation-method experiment; its output
   remains quarantined from gold, selection, training and evaluation headlines.
2. `core`, `challenge`, `confirmation` — benchmark partitions. Their `views`
   may overlap within the assigned partition, but the partitions are never
   aliases for representative, unseen-input and unfamiliar-merchant views.
3. `model_selection_validation` — a separate selection role.
4. `training` — considered only after all earlier roles in the request.

For every candidate pair, the allocator applies the approved union of
protections:

- event/alias, account and customer overlap is forbidden across roles;
- effective-input overlap is forbidden across roles and whenever either member
  claims `unseen_input` or `unfamiliar_merchant`, including inside a block;
- reviewed merchant-family overlap is forbidden across roles whenever either
  member claims `unfamiliar_merchant`;
- representative-only recurrence of an effective input on an independent group
  is allowed within a role and is reported as dependence rather than deleted.

An indivisible block cannot mix strata or inclusion probabilities. Exact targets
are filled only by whole blocks; if that is impossible, the allocator raises an
explicit capacity error. Non-exact previews return a visible shortfall. No quota
is padded with a duplicate or a row protected by another role.

## What the real admission job must still prove

This local helper is intentionally not the real allocator or authority. Before
any customer-linked row is admitted, a separately reviewed job must:

- query only the approved `raylo-production` EU customer-linked Plaid pool with
  a bounded, hash-pinned query and a fresh source receipt;
- resolve assessment → checkout → user → customer linkage, event aliases,
  pending/posted/reconnect ancestry, account/customer closure and reviewed
  merchant families; unresolved or contradictory history must quarantine;
- verify legacy transaction/merchant/family exclusions and applicable historical
  coverage without inventing completeness or a cutoff;
- construct the equivalent block/projection evidence, preserve inclusion
  probabilities and produce the representative versus targeted sampling
  certificates; and
- submit the resulting proposal to the managed B03 authority for an atomic,
  durable reservation/claim. A local digest, a successful preview or a cached
  allow cannot replace that authority decision.

Late aliases or family links must contaminate affected reservations and remain
protected; they must never trigger silent reassignment. Lifecycle transitions,
failed/ambiguous labels, pilot quarantine, sealed confirmation, worker receipts,
consumer gates and the final two-human-label process remain later B03/B04
contracts.

## Review disposition

Sol and Astra independently conditionally approved this local synthetic
direction. Their actionable findings were addressed by the strict synthetic
fixture/policy fields, explicit synthetic result scope, strict role vocabulary,
protected-before-training order, canonical prior-protection digest, strict-input
in-block rejection and candidate-ID reuse rejection. Cross-run authority
permanence, verified provenance and real source completeness remain explicitly
out of scope rather than being inferred from this helper.

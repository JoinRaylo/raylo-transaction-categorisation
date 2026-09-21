# G0 synthetic contracts for the 2,000-row benchmark (AIE-510)

Status: **synthetic-only; no real-data side effects; non-authorizing**.

This increment implements the G0 gate of the AIE-510 Devin handoff and its
2026-09-21 decision amendment: a versioned core/supplement membership contract,
the prespecified 1,500-row core allocation design, a pre-label rare-leaf
quota/proxy specification and selector, the phase state machine, the
append-only receipt chain, the conflict matrix and the required synthetic
negative tests. It reads no source rows, reserves nothing, calls no provider,
scores no locked data and cannot advance a real phase state.

## Scope decisions carried into code

| Decision | Representation |
| --- | --- |
| Final target is 2,000 rows = unchanged 1,500-row core + separately reported 500-row rare-leaf supplement | `CohortMembership.policy_version="two-cohort-2000-v1"`; `AllocationDesign.core_total=1500`, `supplement_total=500` |
| The 70/20/10 allocation applies only to the 1,500-row core | `AllocationDesign.core_targets` must sum to `core_total`; representative/unseen/unfamiliar defaults are 1,050/300/150 and a design whose targets are recomputed over 2,000 rows fails validation |
| The 500-row pilot is inside the core and is immutable | `CohortMember.origin="pilot"` is allowed only with `cohort="core"`; `verify_pilot_parent` rejects any dropped, reassigned or re-contented pilot row and issues an exception report for eligibility failures instead of replacing the row |
| Pilot rows whose selection probability cannot be reconstructed are a separately identified pilot cohort, not a probability sample | `CohortMember.selection_probability_reconstructed=False` permits `inclusion_probability=None` only for `origin="pilot"`; `AllocationReport.pilot_probability_sample=False` when any pilot row is unreconstructed |
| The supplement contributes zero rows to the production-weighted headline | `CohortMembership.headline_members()` returns only `cohort="core"` and `primary_view="representative"`; supplement rows with `view_eligibility.representative=True` are excluded and the report asserts `supplement_rows_in_headline == 0` |
| T6/T7 is a routing overlay, not a fourth view | `RoutingOverlay` is a separate field carrying baseline and candidate tiers; `primary_view` is one of the three B02 views |
| Intended proxy leaf is recorded separately from the final adjudicated leaf | `CohortMember.intended_proxy_leaf`/`proxy_source`/`proxy_value` live on the membership; final leaves live only in `SupplementOutcome`; the selector accepts no label input and its candidate type forbids extra fields |
| Protection covers the union of core and supplement | `CohortMembership.protected_keys()` unions events, aliases, accounts and customers across both cohorts; `require_consumable` fails closed for either cohort and for absent keys |
| Old 1,500-row receipts must not authorize the expanded membership | `verify_admission_receipt` requires the admission receipt to bind the exact union `membership_sha256` and the unchanged `pilot_parent_sha256` |
| No phase may skip a state or infer the next state from a local file | `PhaseLedger` only advances through explicit `GateTransition` records in `PHASE_ORDER`; `LocalReceipt` cannot be converted into a transition; failed/unavailable authority outcomes halt the ledger |

Existing reviewed modules (`benchmark.py`, `benchmark_allocation.py`,
`benchmark_annotation.py`, `benchmark_authority.py`, `benchmark_exposure.py`,
`membership_manifest.py`) are extended, not replaced. The hash-pinned
`benchmark-membership-entry-v1` schema is left byte-identical; the cohort field
is delivered as the hash-bound companion mapping that the amendment permits.

## New canonical modules

### `raylo_txncat.benchmark_cohort`

Reuses `Frozen`, `View`, `Projection` (`benchmark.py`), `Tier` (`evidence.py`),
`Identifier`, `Sha256` (`types.py`), `canonical_json`, `sha256` (`hashing.py`),
`MembershipManifest` (`membership_manifest.py`).

```
Cohort            = Literal["core", "rare_leaf_supplement"]
MemberOrigin      = Literal["pilot", "expansion"]
Direction         = Literal["credit", "debit"]
AliasCoverage     = Literal["complete", "incomplete", "unknown"]
OwnershipStatus   = Literal["verified", "conflicting", "unknown"]
FamilyStatus      = Literal["reviewed", "blank", "unknown"]
ConstraintStatus  = Literal["met", "unmet", "not_evaluable"]
HEADLINE_VIEW: View = "representative"
```

`class CohortValidationError(ValueError)`, `class PilotImmutabilityError(ValueError)`,
`class ProtectedMembershipError(PermissionError)`.

**`RoutingOverlay(Frozen)`** — `schema_version="benchmark-routing-overlay-v1"`,
`baseline_tier: Tier`, `baseline_runtime_sha256: Sha256`,
`candidate_tier: Tier | None = None`, `candidate_runtime_sha256: Sha256 | None = None`.
Validator: candidate tier and candidate runtime are both present or both absent.
Property `is_t6_t7: bool` uses the **baseline** tier (the fixed overlay).

**`ViewEligibility(Frozen)`** — `representative: bool`, `unseen_input: bool`,
`unfamiliar_merchant: bool`. Method `eligible(view: View) -> bool`.

**`CohortMember(Frozen)`** — `schema_version="benchmark-cohort-member-v1"`,
`source_kind: Literal["synthetic_fixture"]`, `key_id: Identifier`,
`observation_key: Sha256`, `event_aliases: tuple[Sha256, ...] = ()`,
`alias_coverage: AliasCoverage`, `accounts: tuple[Sha256, ...]` (min 1),
`customers: tuple[Sha256, ...]` (min 1), `ownership_status: OwnershipStatus`,
`associations: tuple[Sha256, ...]` (min 1; assessment/source associations,
multiplicity retained), `content_sha256: Sha256`,
`projections: tuple[Projection, ...]`, `merchant_family: Sha256 | None`,
`family_status: FamilyStatus`, `family_registry_version: Identifier | None`,
`cohort: Cohort`, `origin: MemberOrigin`, `primary_view: View`,
`view_eligibility: ViewEligibility`, `routing: RoutingOverlay`,
`stratum: Identifier`, `inclusion_probability: float | None`,
`selection_probability_reconstructed: bool`, `direction: Direction`,
`merchant_present: bool`, `intended_proxy_leaf: Identifier | None = None`,
`proxy_source: Identifier | None = None`, `proxy_value: Identifier | None = None`.

Validator (each raises `ValueError` with the quoted message):

- aliases/accounts/customers/associations unique; observation not in aliases; projection versions unique — "cohort member identities must be unique";
- `ownership_status == "verified"` — "cohort member requires verified ownership";
- `view_eligibility.eligible(primary_view)` — "primary view must be eligible";
- `primary_view == "unseen_input"` requires non-empty projections — "unseen-input primary view requires projections";
- `primary_view == "unfamiliar_merchant"` requires `family_status == "reviewed"` and `merchant_family` and `family_registry_version` — "unfamiliar-merchant primary view requires a reviewed family";
- `family_status == "reviewed"` iff `merchant_family is not None` — "family key must match family status"; `family_status == "blank"` requires `merchant_present is False` — "blank family cannot have a merchant present";
- `origin == "pilot"` requires `cohort == "core"` — "pilot rows belong to the core cohort";
- `inclusion_probability is None` only when `origin == "pilot"` and `selection_probability_reconstructed is False`; otherwise it is required, finite, in (0, 1], and `selection_probability_reconstructed` must be True — "inclusion probability evidence is inconsistent";
- `cohort == "rare_leaf_supplement"` requires all three proxy fields; `cohort == "core"` forbids all three — "proxy fields are only recorded for the supplement".

**`CohortMembership(Frozen)`** — `schema_version="benchmark-cohort-membership-v1"`,
`scope: Literal["synthetic_only"]`, `policy_version: Literal["two-cohort-2000-v1"]`,
`key_id: Identifier`, `taxonomy_sha256`, `source_snapshot_sha256`,
`pilot_parent_sha256`, `sampling_specification_sha256`,
`rare_leaf_specification_sha256`, `projection_versions: tuple[Identifier, ...]` (min 1),
`members: tuple[CohortMember, ...]`, `authorizes_consumption: Literal[False] = False`.

Validator:

- members sorted by `observation_key` and unique — "membership observation keys must be sorted and unique" (two members with the same observation and different associations or content are therefore rejected: multiplicity must be represented inside one member's `associations`);
- every member `key_id` equals the membership `key_id` — "member key version differs";
- every member carries exactly the projection versions in `projection_versions` — "member projections do not match the membership normalization versions";
- no event key (observation or alias) appears in two members — "event alias overlap between members";
- for any two members where either has `primary_view` or eligibility in `{unseen_input, unfamiliar_merchant}`, no shared `(version, token)` projection — "effective input collision across strict views"; representative-only repeats are permitted and counted;
- property `membership_sha256 = sha256(canonical_json(self))`;
- `lookup(observation_key) -> Cohort | Literal["neither"]` (also matches aliases);
- `protected_keys() -> ProtectedKeys(events, accounts, customers: frozenset[Sha256])` over **all** members regardless of cohort;
- `headline_members() -> tuple[CohortMember, ...]` = `cohort == "core" and primary_view == HEADLINE_VIEW`.

`build_cohort_membership(**fields, members: Iterable[CohortMember])` sorts and validates.

**`PilotParentEntry(Frozen)`** — `observation_key`, `primary_view`, `content_sha256`.
**`PilotParent(Frozen)`** — `schema_version="benchmark-pilot-parent-v1"`,
`manifest_sha256: Sha256`, `entries: tuple[PilotParentEntry, ...]` sorted/unique
by key; property `parent_sha256`.
**`PilotException(Frozen)`** — `observation_key`, `reasons: tuple[Identifier, ...]`.
**`PilotVerification(Frozen)`** — `membership_sha256: Sha256`, `pilot_rows: int`,
`matched_rows: int`, `exceptions: tuple[PilotException, ...]`, `probability_sample: bool`.
`verify_allocation` rejects a verification whose `membership_sha256` differs from
the membership it is given (`CohortValidationError("pilot verification belongs to another membership")`).

`verify_pilot_parent(membership, parent) -> PilotVerification`:
- `membership.pilot_parent_sha256 != parent.parent_sha256` → `PilotImmutabilityError("membership binds another pilot parent")`;
- a parent entry with no member whose `origin == "pilot"` and same key → `PilotImmutabilityError("pilot reservation dropped")`;
- a pilot member with a different `primary_view` → `PilotImmutabilityError("pilot primary view reassigned")`; different `content_sha256` → `PilotImmutabilityError("pilot content changed")`;
- a member with `origin == "pilot"` absent from the parent → `PilotImmutabilityError("unknown pilot member")`;
- eligibility failures on a retained pilot member (`alias_coverage != "complete"`, `family_status == "unknown"`, `selection_probability_reconstructed is False`) are **not** errors; they become `PilotException` reasons `alias_coverage_incomplete`, `family_status_unknown`, `selection_probability_unreconstructed`;
- `probability_sample` is True only when every pilot member is reconstructed.

**`AllocationDesign(Frozen)`** — `schema_version="benchmark-allocation-design-v1"`,
`policy_version: Literal["two-cohort-2000-v1"]`, `core_total: int = 1500`,
`supplement_total: int = 500`,
`core_targets: dict[View, int] = {"representative": 1050, "unseen_input": 300, "unfamiliar_merchant": 150}`,
`pilot_counts: dict[View, int] = {"representative": 250, "unseen_input": 150, "unfamiliar_merchant": 100}`,
`min_t6_t7_rows: int = 750`, `unfamiliar_t6_t7_share: tuple[float, float] = (0.6, 0.8)`,
`min_route_rows: dict[Tier, int] = {"T1": 25, "T2": 25, "T5": 25, "T7": 25}`,
`t3_policy: Literal["synthetic_only"] = "synthetic_only"`,
`per_leaf_quotas: Literal[False] = False`, `max_rows_per_customer: int = 4`,
`seed: int` (strict, ≥ 0). Validator: `sum(core_targets.values()) == core_total`
("core targets must sum to the core total; the 70/20/10 split is not recomputed
over the supplement"); `sum(pilot_counts.values()) == 500`; every
`pilot_counts[v] <= core_targets[v]`; share bounds in [0, 1] and ordered; all
tiers in `min_route_rows` are not `T3`, `T4` or `T6`. Property
`expansion_targets: dict[View, int]` = target − pilot (800/150/50).
Property `design_sha256`.

**`ConstraintResult(Frozen)`** — `constraint: Identifier`, `status: ConstraintStatus`,
`observed: int | None`, `required: int | None`, `detail: str`.
**`ViewFill(Frozen)`** — `view`, `target`, `pilot_rows`, `expansion_rows`,
`selected`, `shortfall` (≥ 0).
**`AllocationReport(Frozen)`** — `schema_version="benchmark-allocation-report-v1"`,
`scope="synthetic_only"`, `design_sha256`, `membership_sha256`,
`status: Literal["complete", "shortfall", "blocked"]`, `core_rows`, `supplement_rows`,
`views: tuple[ViewFill, ...]`, `constraints: tuple[ConstraintResult, ...]`,
`headline_denominator: int`, `supplement_rows_in_headline: Literal[0]`,
`same_view_input_repeats: int`, `shared_customer_blocks: int`,
`customer_cap_violations: int`, `alias_coverage_incomplete_expansion_rows: int`,
`pilot_probability_sample: bool`, `authorizes_consumption: Literal[False] = False`.

`verify_allocation(membership, design, pilot: PilotVerification) -> AllocationReport`:
- `ViewFill` per view over `cohort == "core"` members; `shortfall = max(0, target − selected)`; **over-fill** (selected > target) is a `CohortValidationError("core view exceeds its prespecified target")`;
- pilot rows per view must equal `design.pilot_counts` exactly, otherwise `CohortValidationError("pilot counts differ from the design")`;
- `supplement_rows` counted over `cohort == "rare_leaf_supplement"`; more than `supplement_total` → `CohortValidationError("supplement exceeds its prespecified total")`; fewer → constraint `supplement_total` `unmet` (shortfall, never fill);
- constraints (all evaluated over the core only): `min_t6_t7_rows`; `unfamiliar_t6_t7_share` (`not_evaluable` when the unfamiliar view is empty); one `min_route_rows:<tier>` each; `t3_real_rows` = `met` iff zero core rows have baseline `T3` (T3 stays synthetic-only), `per_leaf_quotas_absent` = `met` (the design literal);
- `headline_denominator = len(headline_members())`, `supplement_rows_in_headline = 0` (a supplement member with `view_eligibility.representative=True` must not change the denominator);
- `same_view_input_repeats` counts representative-only projection-token repeats within the core;
- `shared_customer_blocks` counts customers appearing in both cohorts (disclosed, not rejected);
- `customer_cap_violations` counts customers with more than `max_rows_per_customer` rows across the union;
- `alias_coverage_incomplete_expansion_rows` counts `origin == "expansion"` members with `alias_coverage != "complete"`;
- `status`: `blocked` if any `customer_cap_violations > 0` or `alias_coverage_incomplete_expansion_rows > 0`; else `shortfall` if any view shortfall or any constraint `unmet`; else `complete`. No branch redraws or substitutes rows.

**Rare-leaf specification.**
`ProxyKind = Literal["baseline_prediction", "provider_category", "dictionary_rule", "merchant_lexicon", "historical_label"]`.
**`ProxyDefinition(Frozen)`** — `proxy_id: Identifier`, `kind: ProxyKind`,
`version: Identifier`, `sha256: Sha256`, `precedence: int` (strict, ≥ 1).
**`RareLeafQuota(Frozen)`** — `leaf: Identifier`, `quota: int` (> 0),
`min_proxy_support: int` (≥ 1), `min_final_support: int` (≥ 1),
`min_distinct_customers: int` (≥ 1). Validator: `min_final_support <= quota`.
**`SupplementCaps(Frozen)`** — `max_rows_per_customer`, `max_rows_per_account`,
`max_rows_per_family` (all strict ints ≥ 1).
**`RareLeafSpecification(Frozen)`** — `schema_version="benchmark-rare-leaf-spec-v1"`,
`taxonomy_version: Identifier`, `taxonomy_sha256: Sha256`,
`candidate_population: Identifier`, `window_start: str`, `window_end: str`
(pattern `^\d{4}-\d{2}-\d{2}$`, start ≤ end), `rarity_definition: tuple[Literal["traffic_rarity", "training_under_support"], ...]` (min 1, unique),
`rarity_claim: str` (min 1, max 2000), `roster: tuple[RareLeafQuota, ...]` (min 1,
leaves unique, sorted), `total: int = 500`, `proxies: tuple[ProxyDefinition, ...]` (min 1;
unique ids and precedences), `seed: int` (≥ 0), `caps: SupplementCaps`,
`source_sha256`, `runtime_sha256`, `configuration_sha256`. Validator:
`sum(q.quota) == total` ("rare-leaf quotas must sum to the supplement total");
`proxies` consisting solely of `baseline_prediction` kinds → "a pinned baseline
prediction alone is an insufficient proxy". Property `specification_sha256`.
`validate_specification_taxonomy(spec, taxonomy_leaves: frozenset[str])` raises
`CohortValidationError("rare-leaf roster contains leaves outside the pinned taxonomy: …")`.

**`ProxySignal(Frozen)`** — `proxy_id: Identifier`, `value: Identifier | None`.
**`SupplementCandidate(Frozen)`** — `schema_version="benchmark-supplement-candidate-v1"`,
`source_kind: Literal["synthetic_fixture"]`, `key_id`, `observation_key`,
`event_aliases`, `alias_coverage`, `accounts`, `customers`, `ownership_status`,
`associations`, `content_sha256`, `projections`, `merchant_family`,
`family_status`, `family_registry_version`, `view_eligibility`, `routing`,
`stratum`, `inclusion_probability: float` (in (0, 1]), `direction`,
`merchant_present`, `proxy_signals: tuple[ProxySignal, ...]` (proxy ids unique).
`extra="forbid"` is inherited from `Frozen`, so a candidate constructed with
`final_leaf`, `adjudicated_leaf`, `votes` or `agreement` fails validation; this
is the tested guarantee that final labels cannot steer selection.

**`ProxyResolution(Frozen)`** — `outcome: Literal["roster_hit", "proxy_miss", "taxonomy_gap", "no_signal"]`,
`intended_proxy_leaf: Identifier | None`, `proxy_source: Identifier | None`,
`proxy_value: Identifier | None`.
`resolve_proxy(candidate, spec, taxonomy_leaves) -> ProxyResolution`: walk
`spec.proxies` by ascending precedence; the first proxy whose value is a roster
leaf yields `roster_hit`; a value outside the pinned taxonomy is recorded as a
`taxonomy_gap` for that proxy and the walk continues; when the walk ends with at
least one in-taxonomy non-roster value → `proxy_miss`; when every non-null value
was outside the taxonomy → outcome `taxonomy_gap` (counted only in
`taxonomy_gaps`, so gaps are retained rather than folded into misses); no values
→ `no_signal`. Ties between proxies are broken by precedence only.

**`SupplementAssignment(Frozen)`** — `candidate: SupplementCandidate`,
`intended_proxy_leaf: Identifier`, `proxy_source: Identifier`, `proxy_value: Identifier`.
**`LeafFill(Frozen)`** — `leaf`, `quota`, `eligible`, `selected`, `shortfall`,
`distinct_customers`, `proxy_support_status: ConstraintStatus`.
**`TaxonomyGap(Frozen)`** — `proxy_id`, `value`, `count`.
**`SupplementSelection(Frozen)`** — `schema_version="benchmark-supplement-selection-v1"`,
`scope="synthetic_only"`, `cohort: Literal["rare_leaf_supplement"]`,
`specification_sha256`, `taxonomy_sha256`, `status: Literal["complete", "shortfall"]`,
`assignments: tuple[SupplementAssignment, ...]` (sorted by leaf then key),
`per_leaf: tuple[LeafFill, ...]`, `proxy_misses: int`, `no_signal: int`,
`taxonomy_gaps: tuple[TaxonomyGap, ...]`, `excluded_core_overlap: int`,
`quarantined_ownership: int`, `quarantined_alias_coverage: int`,
`cap_rejections: int`, `shared_customer_blocks: int`,
`authorizes_consumption: Literal[False] = False`.

`select_rare_leaf_supplement(candidates, spec, *, taxonomy_leaves, core_protection: ProtectedKeys) -> SupplementSelection`:
1. strict-revalidate every candidate; duplicate observation keys →
   `CohortValidationError("duplicate supplement candidate")`; `spec.taxonomy_sha256`
   must equal the digest passed by the caller alongside `taxonomy_leaves`
   (the signature takes `taxonomy_sha256` too and compares).
2. quarantine `ownership_status != "verified"` and `alias_coverage != "complete"`
   (counted, never selected);
3. exclude candidates whose events/aliases or accounts intersect
   `core_protection` (`excluded_core_overlap`); customers shared with the core
   are permitted and counted as `shared_customer_blocks`;
4. resolve the proxy for each remaining candidate; count misses/no-signal/gaps;
5. for each roster leaf in sorted order, rank eligible candidates by
   `sha256(canonical_json({"algorithm": "benchmark-rare-leaf-rank-v1", "seed": spec.seed, "leaf": leaf, "observation_key": key}))`
   and take up to `quota`, skipping any candidate that would exceed a cap
   (`cap_rejections`); a leaf never borrows from another leaf's candidates;
6. `LeafFill.proxy_support_status` = `met` iff `selected >= min_proxy_support`;
   `status = "shortfall"` if any leaf `shortfall > 0`.

Determinism: identical inputs give identical `canonical_json(selection)`.

`supplement_members(selection, *, key_id) -> tuple[CohortMember, ...]` converts
assignments to `cohort="rare_leaf_supplement"`, `origin="expansion"`,
`primary_view` = first eligible view in the order representative → unseen_input →
unfamiliar_merchant (a supplement row keeps its properties but never enters the
headline), `selection_probability_reconstructed=True`.

**Outcomes (post-adjudication, report only).**
`FinalStatus = Literal["labelled", "ambiguous", "insufficient_evidence", "unresolved", "operationally_failed"]`.
**`SupplementOutcome(Frozen)`** — `observation_key`, `final_status`,
`final_leaf: Identifier | None` (required iff labelled), `candidate_tier: Tier | None`.
`OutcomeKind = Literal["proxy_hit", "proxy_miss", "common_leaf_outcome", "ambiguous", "insufficient_evidence", "unresolved", "operationally_failed"]`.
**`LeafCoverage(Frozen)`** — `leaf`, `intended_rows`, `final_support`,
`distinct_customers`, `coverage_status: Literal["met", "unsupported"]`.
**`SupplementCoverageReport(Frozen)`** — `specification_sha256`,
`outcome_counts: dict[OutcomeKind, int]`, `leaves: tuple[LeafCoverage, ...]`,
`cross_tab: tuple[CrossTabCell, ...]` where `CrossTabCell` has
`intended_proxy_leaf`, `final_leaf | None`, `baseline_tier`, `candidate_tier | None`,
`primary_view`, `direction`, `merchant_present`, `count`;
`coverage_objective: Literal["met", "failed"]`, `redraws: Literal[0] = 0`,
`authorizes_consumption: Literal[False] = False`.
`summarise_supplement_outcomes(members, outcomes, spec) -> SupplementCoverageReport`:
requires exactly one outcome per supplement member (missing or extra →
`CohortValidationError`); `proxy_hit` when `final_leaf == intended_proxy_leaf`;
`proxy_miss` when labelled with another roster leaf; `common_leaf_outcome` when
labelled with a non-roster leaf; per-leaf `coverage_status="met"` iff
`final_support >= min_final_support` and `distinct_customers >= min_distinct_customers`;
`coverage_objective="failed"` if any leaf is unsupported. It never returns a
replacement list.

**Hash-bound cohort companion for the v1 manifest.**
**`CohortMappingEntry(Frozen)`** — `observation_key`, `cohort`.
**`CohortMapping(Frozen)`** — `schema_version="benchmark-cohort-mapping-v1"`,
`manifest_sha256: Sha256`, `membership_sha256: Sha256`,
`entries: tuple[CohortMappingEntry, ...]` sorted/unique.
`bind_cohort_mapping(manifest: MembershipManifest, membership: CohortMembership) -> CohortMapping`
requires the set of manifest `role == "eval"` keys to equal the membership keys
(`CohortValidationError("manifest eval entries do not match cohort membership")`).
`verify_cohort_mapping(manifest, mapping)` re-checks the manifest digest and coverage.
**`ProtectedLookup(Frozen)`** — `role: LookupRole`, `cohort: Cohort | Literal["neither"]`.
`lookup_protected(manifest, mapping, key) -> ProtectedLookup`.
`require_consumable(manifest, mapping, key, *, purpose: Purpose) -> ProtectedLookup`
raises `ProtectedMembershipError` when `role != "train"` — including `eval`
(either cohort), `selection`, `excluded` **and** `neither` (message
"absent membership is not permission to consume"). It also raises when
`mapping.manifest_sha256 != manifest.manifest_sha256` ("stale cohort mapping").

### `raylo_txncat.benchmark_lifecycle`

```
PhaseState = Literal[
    "synthetic-only", "pilot-gates-accepted", "candidate-read-authorised",
    "admission-authorised", "protection-committed", "annotation-authorised",
    "outcomes-accepted", "release-authorised",
]
PHASE_ORDER: tuple[PhaseState, ...]  # in that order
TransitionAuthority = Literal["human_approval", "authority_receipt"]
AuthorityOutcome    = Literal["accepted", "failed", "unavailable"]
ReceiptKind = Literal[
    "root_configuration", "source_materialization", "candidate_frame",
    "admission", "annotation", "adjudication", "outcomes", "release",
]
RECEIPT_ORDER: tuple[ReceiptKind, ...]
```

`class PhaseTransitionError(ValueError)`, `class PhaseGateError(PermissionError)`,
`class ReceiptChainError(ValueError)`.

**`GateTransition(Frozen)`** — `schema_version="benchmark-gate-transition-v1"`,
`from_state`, `to_state`, `approver: Identifier`, `permitted_action: Identifier`,
`authority: TransitionAuthority`, `receipt_sha256: Sha256`,
`stop_conditions: tuple[Identifier, ...]` (min 1), `clears_stop_sha256: Sha256 | None = None`.
Validator: `to_state` is the element immediately after `from_state` in
`PHASE_ORDER` ("phase transitions cannot skip or reverse states").

**`StopRecord(Frozen)`** — `state: PhaseState`, `outcome: Literal["failed", "unavailable"]`,
`reason: Identifier`, `operation_id: Identifier | None`; property `stop_sha256`.

**`PhaseLedger(Frozen)`** — `schema_version="benchmark-phase-ledger-v1"`,
`benchmark_id: Identifier`, `transitions: tuple[GateTransition, ...] = ()`,
`stops: tuple[StopRecord, ...] = ()`. Validator: transitions form a contiguous
chain starting at `synthetic-only`; every `clears_stop_sha256` names a recorded
stop ("transition clears an unknown stop"). `advance` and
`record_authority_outcome` rebuild the ledger through its constructor so the
validator always reruns. Properties: `current_state` (last
`to_state`, else `synthetic-only`), `halted` (a stop exists whose `state ==
current_state` and no later transition cleared it).

- `advance(ledger, transition) -> PhaseLedger`: `transition.from_state` must equal
  `current_state` else `PhaseTransitionError`; if `halted`, the transition must
  carry `clears_stop_sha256` equal to the open stop's digest else
  `PhaseTransitionError("phase is halted by an authority failure")`.
- `record_authority_outcome(ledger, outcome, *, reason, operation_id=None) -> PhaseLedger`:
  `accepted` returns the ledger unchanged (acceptance is not a transition);
  `failed`/`unavailable` append a `StopRecord`; state is never advanced.
- `require_state(ledger, minimum: PhaseState, action: str) -> None` raises
  `PhaseGateError(f"{action} requires {minimum}; ledger is at {current_state}")`
  when the current index is lower **or** the ledger is halted.
- `transition_from_receipt(receipt: object, **fields)` accepts only
  `AuthenticatedReceipt` (`issuer == "benchmark-authority"`) and returns a
  `GateTransition` with `authority="authority_receipt"`; a `LocalReceipt`, a
  dict, or an `AllocationResult`/`AllocationReport` raises
  `PhaseTransitionError("local evidence cannot advance a phase")`.

**Conflict matrix.**
```
ConflictKey = Literal[
    "event", "event_alias", "account", "customer", "assessment_association",
    "effective_input", "merchant_family", "content_revision", "normalization_version",
]
ConflictTreatment = Literal["hard_exclusion", "grouping_constraint", "view_specific_eligibility", "informational"]
EvidenceState     = Literal["present", "missing", "disputed"]
ConflictOutcome   = Literal["exclude", "group", "ineligible_for_view", "informational", "quarantine"]
```
**`ConflictRule(Frozen)`** — `key`, `treatment`, `transitive: bool`,
`applies_to_views: tuple[View, ...]`, `missing_evidence: Literal["quarantine", "informational"]`,
`disputed_evidence: Literal["quarantine"]`. Validator: `applies_to_views` non-empty
iff `treatment == "view_specific_eligibility"`.

`CONFLICT_MATRIX_V1: tuple[ConflictRule, ...]`:

| key | treatment | transitive | views | missing | disputed |
| --- | --- | --- | --- | --- | --- |
| event | hard_exclusion | False | — | quarantine | quarantine |
| event_alias | hard_exclusion | True | — | quarantine | quarantine |
| account | grouping_constraint | True | — | quarantine | quarantine |
| customer | grouping_constraint | True | — | quarantine | quarantine |
| assessment_association | informational | False | — | informational | quarantine |
| effective_input | view_specific_eligibility | False | unseen_input, unfamiliar_merchant | quarantine | quarantine |
| merchant_family | view_specific_eligibility | False | unfamiliar_merchant | quarantine | quarantine |
| content_revision | hard_exclusion | False | — | quarantine | quarantine |
| normalization_version | view_specific_eligibility | False | unseen_input, unfamiliar_merchant | quarantine | quarantine |

`conflict_matrix_sha256() -> Sha256`. `evaluate_conflict(key, *, evidence, view: View | None) -> ConflictOutcome`:
`missing` → rule.missing_evidence mapped (`quarantine` or `informational`); `disputed` → `quarantine`;
`present` → `exclude` / `group` / `informational`, or for view-specific rules
`ineligible_for_view` when `view in applies_to_views` else `informational`.
Non-transitive keys are the tested guarantee that generic effective-input
collisions and merchant-family closure do not connect the whole population.

**Receipt chain.**
**`ReceiptBindings(Frozen)`** — all optional unless listed: `source_snapshot_sha256`,
`content_sha256`, `projection_version: Identifier | None`, `projection_sha256`,
`family_registry_version: Identifier | None`, `family_registry_sha256`,
`taxonomy_sha256`, `guide_sha256`, `prompt_sha256`, `runtime_sha256`,
`bundle_sha256`, `code_sha256`, `sampling_specification_sha256`,
`rare_leaf_specification_sha256`, `conflict_matrix_sha256`, `pilot_parent_sha256`,
`membership_sha256`, `candidate_frame_sha256`, `authority_epoch: int | None`,
`ledger_version: Identifier | None`, `operation_id: Identifier | None`,
`member_count: int | None`.

`REQUIRED_BINDINGS: dict[ReceiptKind, tuple[str, ...]]`:
- root_configuration: taxonomy, sampling_specification, rare_leaf_specification, conflict_matrix, code, runtime, pilot_parent
- source_materialization: source_snapshot, content, projection_version, projection_sha256, family_registry_version, family_registry_sha256
- candidate_frame: source_snapshot, candidate_frame_sha256, member_count
- admission: membership_sha256, pilot_parent_sha256, sampling_specification, rare_leaf_specification, source_snapshot, authority_epoch, ledger_version, operation_id, member_count
- annotation: membership_sha256, taxonomy, guide, prompt, runtime, bundle
- adjudication: membership_sha256, taxonomy, guide
- outcomes: membership_sha256, taxonomy, member_count
- release: membership_sha256, taxonomy, authority_epoch, operation_id

**`ChainReceipt(Frozen)`** — `schema_version="benchmark-chain-receipt-v1"`,
`kind: ReceiptKind`, `sequence: int` (≥ 0), `parent_sha256: Sha256 | None`,
`root_sha256: Sha256 | None`, `bindings: ReceiptBindings`,
`authorizes_consumption: Literal[False] = False`. Validator: required bindings
for `kind` are non-null ("receipt is missing required bindings: …"); root has
`sequence == 0`, `parent_sha256 is None`, `root_sha256 is None`; non-root has both.
Property `receipt_sha256`.

**`ReceiptChain(Frozen)`** — `schema_version="benchmark-receipt-chain-v1"`,
`receipts: tuple[ChainReceipt, ...]` (min 1). Validator: `receipts[0].kind ==
"root_configuration"`; kinds strictly follow `RECEIPT_ORDER` with no gaps
("receipt chain skipped a phase"); `sequence == index`; each `parent_sha256 ==
previous.receipt_sha256` and `root_sha256 == receipts[0].receipt_sha256`
("receipt chain parent mismatch"); for every binding field in
`STABLE_BINDINGS = ("taxonomy_sha256", "source_snapshot_sha256", "prompt_sha256",
"guide_sha256", "runtime_sha256", "family_registry_sha256", "pilot_parent_sha256",
"membership_sha256", "sampling_specification_sha256", "rare_leaf_specification_sha256")`
a later receipt that binds a different non-null value from an earlier receipt
fails ("receipt chain changed <field>"). Property `head`.

- `append_receipt(chain, kind, bindings) -> ReceiptChain` builds the next receipt
  with the correct sequence/parent/root and revalidates.
- `verify_derivation(candidate_keys: frozenset[Sha256], admitted_keys: frozenset[Sha256]) -> DerivationEvidence(candidate_count, admitted_count, subset: Literal[True])`
  raises `ReceiptChainError("admitted membership is not a subset of the candidate frame")`;
  digest equality between candidate frame and manifest is deliberately **not** required.
- `verify_admission_receipt(receipt: ChainReceipt, membership: CohortMembership) -> None`:
  `kind == "admission"`, `bindings.membership_sha256 == membership.membership_sha256`,
  `bindings.pilot_parent_sha256 == membership.pilot_parent_sha256`,
  `bindings.member_count == len(membership.members)`; otherwise
  `ReceiptChainError("admission receipt does not bind this membership")`.

### `raylo_txncat.benchmark_annotation` additions (backward compatible)

- `AttemptStatus` gains `"cancelled"`; cancelled attempts require `error_code`
  like the other failures and are never `received`.
- **`RetryPolicy(Frozen)`** — `schema_version="benchmark-retry-policy-v1"`,
  `max_attempts: int` (strict, 1–5), `prompt_sha256: Sha256`. A stricter-prompt
  retry is a different instrument: `exhausted_items` is given the batch's
  `prompt_sha256` and raises `ValueError("retry attempts under another prompt are a new instrument")` when a batch prompt differs.
- **`ExhaustionRecord(Frozen)`** — `item_id`, `attempts: int`,
  `status: Literal["operationally_unresolved"]`, `leaf: Literal[None] = None`.
- `exhausted_items(attempts: tuple[AnnotationAttempt, ...], policy: RetryPolicy, *, prompt_sha256: Sha256) -> tuple[ExhaustionRecord, ...]`:
  items with `>= policy.max_attempts` attempts and no `received` attempt; an
  item with more attempts than the cap → `ValueError("retry cap exceeded")`.
- `validate_batch` already rejects missing/unknown IDs; a new
  `partial_batch_items(manifest, batch) -> tuple[str, ...]` returns the missing
  item IDs for a partial batch **without** producing votes for them.

No change to `PilotManifest`, `PilotItem` or the `pilot-v1-` item pattern; the
expansion annotation manifest is G4 work.

## Required synthetic tests (exact assertions)

`lib/raylo-txncat/tests/test_benchmark_cohort.py`:

1. `test_member_rejects_conflicting_ownership` — `ownership_status="conflicting"` → `ValidationError` containing "verified ownership".
2. `test_membership_rejects_duplicate_observation_across_associations` — two members, same key, different `associations` → "sorted and unique"; one member with two associations validates.
3. `test_membership_rejects_changed_content_same_observation` — same key different `content_sha256` → rejected by the same uniqueness rule; assert the message.
4. `test_membership_rejects_alias_overlap` — member B's alias equals member A's observation → "event alias overlap".
5. `test_membership_rejects_normalization_version_change` — a member whose projection versions differ from `projection_versions` → "normalization versions".
6. `test_overlapping_eligibility_counts_once` — a core member eligible for all three views with `primary_view="unseen_input"` is counted only in the unseen `ViewFill`; `headline_denominator` excludes it.
7. `test_strict_view_input_collision_rejected_and_representative_repeat_counted` — same projection token: rejected when either member is unseen/unfamiliar (primary or eligibility flag); accepted and `same_view_input_repeats == 1` when both are representative-only.
8. `test_unfamiliar_requires_reviewed_family_and_unknown_status_rejected`.
9. `test_pilot_origin_only_in_core` and `test_pilot_probability_rules`.
10. `test_proxy_fields_only_for_supplement`.
11. `test_headline_excludes_supplement_with_representative_tag` — supplement member with `view_eligibility.representative=True` → not in `headline_members()`; `supplement_rows_in_headline == 0`; `headline_denominator` equals the count of core representative rows.
12. `test_protected_keys_union` — keys of a supplement member appear in `protected_keys()`.
13. `test_require_consumable_fails_closed` — parametrised over cohort core, cohort supplement, `selection`, `excluded`, and absent key → `ProtectedMembershipError`; `train` passes; stale mapping digest → error. Each negative case additionally asserts that a consumer sentinel (a list appended to only on success) is empty.
14. `test_pilot_parent_immutability` — dropped row, reassigned view, changed content, unknown pilot member → `PilotImmutabilityError` with the four exact messages; alias-coverage/unknown family/unreconstructed rows produce `PilotException` entries and `probability_sample is False` while `matched_rows == pilot_rows`.
15. `test_allocation_design_defaults_and_rejections` — defaults give `expansion_targets == {"representative": 800, "unseen_input": 150, "unfamiliar_merchant": 50}`; `core_targets={"representative":1400,"unseen_input":400,"unfamiliar_merchant":200}` fails ("not recomputed over the supplement"); `min_route_rows={"T3": 25}` fails.
16. `test_verify_allocation_complete_fixture` — builder produces exactly 500 pilot (250/150/100) + 1,000 expansion (800/150/50) + 500 supplement synthetic members with tiers arranged so `min_t6_t7_rows`, the 60–80 % unfamiliar share, the T1/T2/T5/T7 minima and zero T3 are met; assert `status == "complete"`, `core_rows == 1500`, `supplement_rows == 500`, `headline_denominator == 1050`, every constraint `met`, `pilot_probability_sample` True.
17. `test_verify_allocation_shortfall_is_reported_not_filled` — remove 10 expansion unseen rows → `status == "shortfall"`, `ViewFill(unseen_input).shortfall == 10`, `core_rows == 1490`; supplement count unchanged; over-fill (+1 representative) → `CohortValidationError`.
18. `test_verify_allocation_blocked_on_cap_or_alias_coverage`.
19. `test_verify_allocation_rejects_wrong_pilot_counts`.
20. `test_rare_leaf_spec_rules` — quotas not summing to total; baseline-only proxies; duplicate precedence; roster leaf outside taxonomy via `validate_specification_taxonomy`.
21. `test_supplement_candidate_forbids_final_labels` — `final_leaf=`, `votes=` → `ValidationError`.
22. `test_resolve_proxy_precedence_gap_and_miss`.
23. `test_select_supplement_deterministic_and_shortfall` — same inputs twice → identical `canonical_json`; quota 5 with 3 eligible → `shortfall == 2`, `status == "shortfall"`, no borrowing from another leaf (that leaf's `selected` unchanged).
24. `test_select_supplement_excludes_core_overlap_and_discloses_shared_customers`.
25. `test_select_supplement_caps_and_quarantine`.
26. `test_supplement_members_never_headline`.
27. `test_summarise_outcomes_retains_misses_and_fails_coverage` — outcomes include a hit, a miss, a common-leaf outcome, an ambiguous, an insufficient-evidence and an operationally-failed row; `outcome_counts` reflect each; a leaf below `min_final_support` → `coverage_objective == "failed"`, `redraws == 0`; missing outcome → `CohortValidationError`.
28. `test_bind_and_verify_cohort_mapping`.

`lib/raylo-txncat/tests/test_benchmark_lifecycle.py`:

1. `test_phase_order_and_no_skip` — `GateTransition(from="synthetic-only", to="candidate-read-authorised")` → `ValidationError`; full eight-state walk succeeds and `current_state == "release-authorised"`.
2. `test_advance_requires_current_state`.
3. `test_local_receipt_cannot_advance` — `LocalReceipt`, `dict`, `AllocationReport` → `PhaseTransitionError`; ledger unchanged.
4. `test_authority_failure_halts` — `record_authority_outcome(..., "unavailable")` → `halted`; `advance` → error; `require_state(ledger, "synthetic-only", "test")` also raises while halted; a transition with `clears_stop_sha256` proceeds; `accepted` returns an equal ledger and does not change state.
5. `test_require_state_blocks_real_actions` — parametrised over ("reserve", "admission-authorised"), ("dispatch_annotation", "annotation-authorised"), ("release", "release-authorised") on a fresh ledger → `PhaseGateError`; assert an action sentinel list is empty.
6. `test_conflict_matrix_pins_semantics` — exactly nine keys; `merchant_family`, `effective_input`, `normalization_version` are non-transitive; `event_alias`, `account`, `customer` are transitive; `evaluate_conflict("effective_input", evidence="present", view="representative") == "informational"` and `== "ineligible_for_view"` for `unseen_input`; `missing` on `assessment_association` → `informational`; `disputed` on any key → `quarantine`; `conflict_matrix_sha256()` is stable across two calls and is a 64-hex string.
7. `test_receipt_required_bindings` — each kind with an empty `ReceiptBindings` → `ValidationError` naming the missing field.
8. `test_receipt_chain_append_and_parent_binding` — eight appended receipts; `head.kind == "release"`; tampering with `receipts[3]` (rebuilding with another `membership_sha256`) → "parent mismatch"; skipping `candidate_frame` → "skipped a phase"; reordering → error.
9. `test_receipt_chain_rejects_changed_stable_bindings` — parametrised over taxonomy, source snapshot, prompt, runtime, family registry, membership, sampling spec, rare-leaf spec → "changed <field>".
10. `test_verify_derivation_subset_not_equality` — proper subset passes with counts; non-subset raises; equal sets pass.
11. `test_old_receipt_cannot_authorize_expanded_membership` — build a 1,500-row-style membership and a 2,000-row membership (small synthetic counts are fine: the test uses two memberships differing by supplement members); an admission receipt bound to the first fails `verify_admission_receipt` against the second; the correct receipt passes.
12. `test_stale_authority_epoch_mismatch` — reuse `InMemoryAuthorityStore`/`LocalAuthority` from `benchmark_authority` to show a stale-epoch commit result, then assert `record_authority_outcome(..., "failed")` halts the ledger and no transition exists (`len(ledger.transitions) == 0`).

`lib/raylo-txncat/tests/test_benchmark_annotation.py` additions:

1. `test_cancelled_attempt_requires_error_and_never_votes`.
2. `test_partial_batch_reports_missing_items_without_votes`.
3. `test_retry_exhaustion_is_not_a_label` — three failed attempts under `max_attempts=3` → one `ExhaustionRecord` with `leaf is None`; two attempts → none; four → "retry cap exceeded"; different `prompt_sha256` → "new instrument".
4. `test_duplicate_batch_ids_rejected` (already covered — extend with a second duplicate-attempt case if absent).

Every negative test asserts the prohibited effect did not occur (an untouched
ledger, an empty consumer sentinel, unchanged membership digests), not merely
that an exception was raised.

## What this increment does not do

It does not read the warehouse, materialize a candidate frame, reconstruct
pilot selection probabilities, resolve aliases or merchant families, draw the
core expansion sample, dispatch annotation, adjudicate, import outcomes, connect
B04 consumers, or move the real phase ledger past `synthetic-only`. The
`AllocationDesign` and checker are the frozen acquisition design and its
verifier; the bounded warehouse sampler for the core expansion is G3 work. The
in-process selector is for synthetic contract tests and small planning previews
only; a real supplement selection must run against the protected candidate
artifact after G2/G3 and be committed through the G4 authority transaction.

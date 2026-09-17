# TIER-NAMING-001 — final served tier names

Status: evaluated and verified in staging.
Created / evaluated: 2026-09-17. Owner: Carlos.

## Change and predeclared acceptance

The pre-launch contract used `T5b` for an accepted classifier result while `T6`
still named a provider-native fallback that serving no longer returned. This made
the final waterfall harder to explain and would make evidence queries ambiguous.

The candidate makes a terminology-only migration:

- deterministic T1–T5 remain unchanged;
- accepted transformer or hinge output is served as `T6`;
- classifier abstention remains `T7` with null leaf/general;
- provider-native mapping remains internal diagnostic context named
  `provider_native_fallback` and can never be served;
- `T5B_*` runtime settings become `T6_*`;
- LangGraph placements become `T5_provider_crosswalk` and `T6_training`;
- frozen historical fixtures and reports retain their original `T5b`/`T6`
  terminology and are interpreted through the documented legacy mapping.

Acceptance requires identical leaf, general, rule, head, margin, abstention,
degradation and row-order outputs on the complete permitted evaluation inventory.
The only permitted response transition is accepted model rows `T5b` → `T6`.
No transaction may move into or out of the classifier cohort, and no score,
coverage or T7 count may change. Both repositories' tests, generated schemas,
research parity and full evaluation must pass. Locked v5/v6 sets remain unopened.

## Contract and release consequences

This is deliberately a breaking pre-launch contract change. Responses and evidence
reject `T5b`; runtime configuration rejects the old `T5B_*` names and uses
`T6_ABSTAIN_MARGIN` / `T6_BUDGET_MS`. Renaming the canonical configuration fields
changes the config hash and therefore the release ID even though predictions are
unchanged. Existing staging ledger entries remain replayable under their archived
release; new evaluations use the new release identity after deployment.

## Verification

The complete permitted suite passed: 16 registered datasets, 92 scored views,
1,375 app/library tests, 74 research tests, lint, generated-schema checks,
34,880-case deterministic differential parity, real-model startup and independent
metric verification. Transformer seed 123 and hinge v8 were both evaluated; the
locked v5/v6 confirmation sets were not opened or scored.

The candidate produced 134,227 evaluation rows. A normalized paired comparison
against the completed CREDIT-PAYROLL-001 run found zero non-tier field differences
and zero unexpected tier transitions. Intentional transitions were:

- 4,846 `T5b_transformer` → `T6_transformer`;
- 4,920 `T5b_hinge` → `T6_hinge`;
- 6,297 `T6_native_fallback` → `provider_native_fallback` diagnostics;
- 118,164 rows unchanged, including frozen research projections that retain
  historical `T5b_*` labels.

All 92 score views retain identical numerators, denominators, coverage and T7
counts. Machine-readable evidence is in `summary.json`, `validation.json`,
`tier_comparison.json`, `parity.json` and `startup.json`. Private `rows.jsonl`
remains outside Git. The runner correctly refused its built-in comparison because
canonical config/harness source hashes changed; the explicit paired comparison
therefore allowed only the declared tier mappings and compared every other row
field byte-for-value.

## Staging verification

CI run [35237110119](https://github.com/JoinRaylo/internal-services-monorepo/actions/runs/35237110119)
deployed commit `111f114be5796a983413abfd46e15fd2cb660fcf` as image digest
`sha256:830c1ee245f7774dc182b8d66a7d586211406fb44adecb13c019b100eb684146`.
The reviewed apply changed one Cloud Run resource and added or destroyed none;
the serving bundle remained pinned to `a2553f3462205963254b0fb1ad9dff6d64e1399abdecaab93977265908c7f23d`.

The signed 84-row staging verification passed, including signature rejection,
durable evidence readback and exact pinned/gzip replay. Served tier counts were
T1=2, T2=11, T4=5, T5=9, T6=51 and T7=6, with no `T5b` response. The receipt is
stored as `staging_verification.json`. Real Taktile invocation is tracked
separately because this verifier calls the service's signed public endpoint.

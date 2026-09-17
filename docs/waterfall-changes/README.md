# Waterfall changes and score history

Follow [POLICY.md](POLICY.md) for every behavioural change. Start each record from
[CHANGE_TEMPLATE.md](CHANGE_TEMPLATE.md). The policy, records and aggregate scores
are mirrored in the research repository at `docs/waterfall-changes/`.

## Current status — 17 September 2026

The [master benchmark design](../benchmark-design/master-v1/DESIGN.md) records the
coverage audit, proposed fresh cohorts and durable training/evaluation separation.
This is a design with an implementation/acceptance plan, not a new scored dataset
or deployed exclusion gate. Existing score history and locked-set rules remain.

The latest evaluation is [TIER-NAMING-001](tier-naming-001/RECORD.md). It renames
served classifier output from T5b to T6 and the retired provider fallback to
diagnostic `provider_native_fallback`. Across 134,227 rows there were zero
non-tier changes, zero unexpected transitions and no score or T7-count changes.
Staging promotion remains pending.

The preceding behavioural evaluation is [CREDIT-PAYROLL-001](credit-payroll-001/RECORD.md): one
exact Waitrose payroll-credit collision. All 15 permitted datasets and both heads
were evaluated and replayed from research. Real-data scores are unchanged, with
zero regressions; the explicit synthetic payroll case now resolves to salary.
No existing dataset contains an exact-merchant Waitrose credit, so this is a
verified narrow behaviour, not evidence of generalisation. Staging retains the
original bundle; promotion is deferred. See the [baseline](baseline-2026-09-15/RECORD.md)
and [running guide](RUNNING.md).

The 14 September policy comparison remains historical baseline evidence for three
development sets. The new baseline reproduces those scores exactly. The identical
report, machine-readable summary and validation receipt are retained under
`baseline-2026-09-14/` in both repositories. Their original commands run from the
monorepo; importing these results is not a fresh research execution.

## Score history

| Record | Status | Evidence |
|---|---|---|
| BASELINE-2026-09-14 | Historical three-set comparison; T7 policy retained, no runtime change | [Report](baseline-2026-09-14/README.md), [scores](baseline-2026-09-14/summary.json), [validation](baseline-2026-09-14/validation.json), [origin and hashes](baseline-2026-09-14/origin.json) |
| PROCESS-2026-09-15 | Documentation only; no candidate scored | [Policy](POLICY.md) |
| BASELINE-2026-09-15 | Fresh complete inventory; current policy retained, no candidate change | [Record](baseline-2026-09-15/RECORD.md), [scores](baseline-2026-09-15/summary.json), [validation](baseline-2026-09-15/validation.json), [research replay](baseline-2026-09-15/replay.json) |
| CREDIT-PAYROLL-001 | Evaluated; offline criteria pass, promotion deferred; zero real-data changes | [Record](credit-payroll-001/RECORD.md), [scores](credit-payroll-001/summary.json), [validation](credit-payroll-001/validation.json), [paired review and research replay](credit-payroll-001/review.json) |
| TIER-NAMING-001 | Evaluated and staging-verified; behaviour-neutral contract migration | [Record](tier-naming-001/RECORD.md), [scores](tier-naming-001/summary.json), [validation](tier-naming-001/validation.json), [paired tier comparison](tier-naming-001/tier_comparison.json), [staging receipt](tier-naming-001/staging_verification.json) |

Append a new row for each candidate revision, including rejected changes. Do not
overwrite earlier scores or describe a proposed change as implemented.

## Open issue: retail merchant defaults on credits

Direct signed staging calls on 15 September found that Waitrose debit GBP 25.44
and two bare-description Waitrose credits (GBP 2.99 and GBP 1,989.11) all resolve
to `groceries` at T4. A second controlled call returned `refund_received` at T2
for `WAITROSE REFUND`, but `groceries` at T4 for `WAITROSE PAYROLL`. These are
synthetic diagnostics, not an accuracy estimate or proof of Taktile execution.

The amount signs reach the resolver correctly. Research and app both allow the
merchant dictionary to resolve these credits; the selected transformer's masks
also permit `groceries` on credits. A T4 bypass alone does not establish a fix.
The intended explicit scenarios are refund and salary respectively; the bare
merchant and amount alone cannot reliably distinguish them. No amount threshold
or blanket credit-mask change has been adopted.

The exact payroll override is evaluated in CREDIT-PAYROLL-001; broader dictionary/mask
changes remain separate, untested candidates. Include independent labelled retailer-credit coverage: 1,924 of the
2,000 existing credit-evaluation rows have blank merchants. Preserve bookmaker,
returned-payment and other documented exceptions. Candidate acceptance remains
subject to the complete evaluation and mirroring process.

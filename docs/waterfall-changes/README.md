# Waterfall changes and score history

Follow [POLICY.md](POLICY.md) for every behavioural change. Start each record from
[CHANGE_TEMPLATE.md](CHANGE_TEMPLATE.md). The policy, records and aggregate scores
are mirrored in the research repository at `docs/waterfall-changes/`.

## Current status — 15 September 2026

The complete repeatable evaluation runner and a fresh baseline are now available.
See [the running guide](RUNNING.md), [baseline record](baseline-2026-09-15/RECORD.md)
and [full scores](baseline-2026-09-15/README.md). All 15 permitted datasets and seven
synthetic examples were evaluated across 92 views; unsupported full-waterfall
inputs retain their appropriate dictionary/head evaluations. No retailer-credit
correction, model change or staging deployment has occurred.

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

Evaluate a narrow contextual override separately from broader dictionary/mask
changes. Include independent labelled retailer-credit coverage: 1,924 of the
2,000 existing credit-evaluation rows have blank merchants. Preserve bookmaker,
returned-payment and other documented exceptions. Candidate acceptance remains
subject to the complete evaluation and mirroring process.

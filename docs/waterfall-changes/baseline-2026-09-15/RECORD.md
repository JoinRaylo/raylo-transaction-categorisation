# BASELINE-2026-09-15 — complete repeatable evaluation baseline

Status: **baseline verified; no waterfall correction or candidate promotion**.
Assessment: **share with the limitations below**. This is the starting point for
measuring later changes, not evidence that the Waitrose issue is resolved.

## Scope and identities

The new runner executes 15 permitted datasets plus seven synthetic credit/debit
examples, producing 92 evaluation views. Every dataset retains its original task
and denominator. The frozen registry is unchanged; an explicit hash-pinned
extension adds the historical 2,000-row pipeline benchmark. Locked and retired
confirmation sets are excluded from scoring.

- Evaluator/app source: `e2e3a27f387619c137b56d245af67b5da9f9948c` in the monorepo.
- Research resolver source: `f8e47ef3f449309f733620607c05add8bb0b2723`; source and
  taxonomy definitions were verified against the bundle. The research checkout
  has unrelated existing local work; no such work was modified for this baseline.
- Bundle: `a2553f3462205963254b0fb1ad9dff6d64e1399abdecaab93977265908c7f23d`.
- Transformer seed 123 and hinge v8; unchanged masks and zero abstention cutoff.
  Quality execution uses a fixed clock and refuses model degradation.
- App Python 3.12; research code tests use its Python 3.14 environment. Exact
  package versions, commands, source/test hashes and bundle contents are recorded
  in [summary.json](summary.json).

The evaluation code, inventory, synthetic fixtures, process and results are
mirrored in the research repository. [RUNNING.md](../RUNNING.md) gives baseline,
candidate-comparison and independent-verification commands.

## Selected transformer: serving Plaid baseline

Specific accuracy counts correct non-unclassified assignments over every source
row. Coverage counts assignments of a specific category. These differently sampled
and overlapping populations must not be pooled.

| Dataset | Correct / rows | Specific leaf accuracy | Coverage |
|---|---:|---:|---:|
| Historical holdout, Plaid rows | 486 / 627 | 77.51% | 97.77% |
| Credit evaluation | 1,785 / 2,000 | 89.25% | 99.85% |
| Targeted risk evaluation, all rows | 289 / 400 | 72.25% | 96.50% |
| Historical pipeline benchmark, Plaid rows | 1,169 / 1,418 | 82.44% | 98.87% |

The targeted risk set's risk-leaf slice is 144/174 (82.76%) for the serving
waterfall. Do not replace its denominator with all 400 rows or confuse this with
the classifier-only risk score. Full results for both heads, merchant/direction/
provider/provenance/tier splits, confusion matrices, per-leaf precision/recall/F1,
coverage and duplicate/conflicting-label sensitivity are in [the report](README.md)
and [machine-readable scores](summary.json).

The research full-pipeline view on all 2,000 mixed-provider benchmark rows gives
**83.80% exact leaf accuracy for seed 123** and **82.25% for hinge v8**. Its residual
has 478 rows; seed 123 scores 66.32%, matching the historical per-seed 66.3% figure.
The previously quoted 83.2% transformer headline was a three-seed result; 83.80%
is not an improvement produced by this work. Research exact accuracy retains
unclassified taxonomy strings, unlike the specific-assignment metric above.

## Verification

- **1,163 app/library tests**, including 21 new evaluation-integrity tests, passed.
- **36 research tests**, lint and 11 generated contract checks passed.
- All **34,880 deterministic research/app combinations**, **88 full-model goldens**
  and **20 startup probes** passed. See [parity](checks/parity.json) and
  [startup](checks/startup.json). SQL structural/ordering tests ran in the research
  suite; no new live BigQuery parity query was performed for this tooling-only change.
- Independent verification used the original research confusion analyser,
  separate count calculations and scikit-learn precision/recall/F1:
  **92 views and 39,984 metric checks** passed. See [validation](validation.json).
- **30 metrics from the earlier three-set comparison matched exactly**, for both
  heads. Seed-123 validation also reproduced **3,961/5,000 (79.22%)** exact labels.
- A complete second run from the **research copy of the runner**, using
  `--baseline`, passed all checks and produced **zero changed rows**. All 134,227
  per-view prediction records and all aggregate metrics were identical. This
  record count includes repeated views/overlapping sets; it is not a count of
  unique transactions. See [the replay receipt](replay.json).

The first development run found that the app environment lacked pandas for the
research test suite. The final runner uses a separately specified research Python
and records both environments. Metric recounting was then integrated into the
runner before the final baseline and research replay. Preliminary runs remain
private scratch evidence; the retained baseline uses the final committed runner.

## Limitations and next change

Merchant-only datasets cannot establish full-transaction accuracy. The legacy
risk set and tuning validation lack provider context and retain their documented
head/legacy evaluations. V4 provider context comes from a verified exact-input
join to its registered eyeball export; no category values are invented.
Historical training overlap and prior model/rule selection make these development
regression benchmarks. The old pipeline export is preserved; its disjointness
was not re-established against later training snapshots. Unknown/conflicting gold
remains visible and is not relabelled to improve scores.

The synthetic set still has three mismatches to user-intended scenarios: two bare
Waitrose credits and the explicit `WAITROSE PAYROLL` credit resolve to groceries.
The first two lack narrative context; the third is a clear precedence defect.
`WAITROSE REFUND` resolves correctly. These examples are diagnostic evidence,
not a representative accuracy sample or justification for an amount threshold.

The next experiment is one narrow, predeclared contextual correction, followed by
the entire paired evaluation and review process. Broader T4 eligibility/mask
changes must be separate candidates. Models, runtime waterfall, staging release
and Taktile configuration remain unchanged by this baseline work.

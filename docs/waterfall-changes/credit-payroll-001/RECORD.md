# CREDIT-PAYROLL-001 — evaluation result

Status: **evaluated; predeclared offline criteria pass; staging promotion deferred**.
Evaluated/reviewed 15 September 2026 by Codex at Carlos's request. There is no
measured improvement on real labelled transactions. The single observed synthetic
payroll failure is corrected, and the repeatable data shows zero regressions.

## Change and decision

The [committed predeclaration](PREDECLARATION.md) preceded the implementation and
candidate scoring (monorepo `bd30839`, research `998e19b`). Exactly one CSV row
matches the normalized merchant `waitrose`, credit direction and the complete
`WAITROSE PAYROLL` narrative, case-insensitively with the declared ASCII whitespace
allowance. It assigns `salary` at `T2_compound_waitrose_explicit_payroll` before T4.
Amount plays no part. No salary/wages synonyms, references, fuzzy merchants,
blank-merchant inference, broad retailer rule, mask or model change was introduced.

**Decision:** retain the isolated evaluation candidate and its complete evidence.
It is suitable for review as this exact behavioural correction, but it has no
independently labelled Waitrose-credit support. Do not claim generalisation or
expand it to other narratives/retailers on the strength of these scores. A versioned
independently labelled retailer-credit set should precede any broader correction.
Staging remains on the original bundle; this evaluation did not publish a bundle,
change Cloud Run, send Taktile traffic or score the locked confirmation sets.

## Results: no real-data score changes

All 15 permitted datasets plus the seven original synthetic examples completed
for both heads, with 92 supported evaluation views. All **85 non-synthetic views**
have byte-equivalent metric objects to baseline: every leaf/general accuracy,
precision/recall/F1, macro metric, credit/risk statistic, coverage, tier/direction/
provider/merchant/provenance slice and duplicate/conflicting-label analysis is
unchanged. Unsupported full-waterfall tasks remain explicitly unsupported;
their defined dictionary/head/legacy views were evaluated. See [all scores](README.md),
[full aggregate comparison](summary.json) and the original
[baseline](../baseline-2026-09-15/summary.json).

Selected transformer serving Plaid specific accuracy (correct non-unclassified
assignments divided by all source rows):

| Dataset | Baseline | Candidate | Delta | Coverage, both |
|---|---:|---:|---:|---:|
| Historical holdout, Plaid | 486/627 = 77.51% | 486/627 = 77.51% | 0 pp | 613/627 = 97.77% |
| Credit evaluation | 1,785/2,000 = 89.25% | 1,785/2,000 = 89.25% | 0 pp | 1,997/2,000 = 99.85% |
| Targeted risk, all rows | 289/400 = 72.25% | 289/400 = 72.25% | 0 pp | 386/400 = 96.50% |
| Historical pipeline, Plaid | 1,169/1,418 = 82.44% | 1,169/1,418 = 82.44% | 0 pp | 1,402/1,418 = 98.87% |

The targeted risk-leaf slice remains 144/174 = 82.76%. The mixed-provider
research pipeline benchmark remains 1,676/2,000 = **83.80% exact leaf accuracy**
for seed 123 and 1,645/2,000 = **82.25%** for hinge v8. Its residual cohort remains
478 rows, with 317/478 = 66.32% for the transformer and 286/478 = 59.83% for hinge.
Do not pool these differently sampled/overlapping views into a production score.

Review covered all **134,227 per-view records**, including repeated views and
cross-dataset overlap. Exactly five records changed, all representing the **same
synthetic payroll input** in deterministic research, two research-head views and
two serving-head views. Each changed from wrong groceries/T4 to correct salary/T2.
There were **zero correct-to-wrong, wrong-to-different-wrong or non-synthetic
changes**. Raw head outputs, residual membership and all fixed-baseline residual
metrics were identical. The synthetic serving diagnostic improves **4/7 to 5/7**
for each head; this is not a population accuracy estimate.

| Synthetic input | Baseline | Candidate |
|---|---|---|
| WAITROSE PAYROLL, credit GBP 1,989.11 | groceries / T4 | salary / T2 |
| WAITROSE REFUND, credit GBP 2.99 | refund_received / T2 | unchanged |
| Waitrose, credit GBP 2.99, bare narrative | groceries / T4 | unchanged; intended refund is not inferable |
| Waitrose, credit GBP 1,989.11, bare narrative | groceries / T4 | unchanged; intended salary is not inferable |
| Waitrose debit, McDonalds debit, SkyBet debit | existing correct categories | unchanged |

[Changed synthetic records](synthetic-changes.jsonl), [independent paired review](review.json)
and its [reproduction script](review.py) preserve the complete comparison outcome.
Customer row-level diagnostics remain private; no raw customer narratives were committed.

## Coverage and precedence limits

The source-field audit found **zero exact-merchant Waitrose credits in any of the
15 existing datasets**, not merely zero matches to this narrow payroll pattern.
[Coverage counts](coverage.json) retain all dataset denominators. Merchant-only
sets have no direction context and cannot support a credit-specific conclusion.
The 2,000-row credit set has 1,924 blank merchants. Historical training overlap,
prior seed/rule selection and repeated evaluation make these regression diagnostics,
not independent estimates of production performance. No labels were changed.

The T2 placement uses the established salary-collision precedence. An exact payroll
narrative supersedes an Equifax T3 Refund category; this conflicting-evidence
scenario is explicitly tested and was declared in advance. Earlier native gambling,
council, gig and agency overrides remain intact. Refund, refunded, reversal and
returned-payment narratives containing extra text do not match the complete
payroll pattern, so their original results are preserved. Bare credits remain an
open classification issue, requiring additional evidence rather than an amount rule.

## Verification and identities

- **1,201 app/library tests and 74 research tests** passed, including 38 new tests
  in each repo; lint and all 11 generated contracts passed.
- All **88 frozen model goldens**, **20 startup probes** and **35,200 standard
  deterministic parity combinations** passed. Old golden bytes were retained.
- Additional synthetic assertions: **37 cases, 370 provider profiles, 333 API
  amount/direction checks, 148 emitted RE2 predicate checks**, and **69,030 extended
  research/app combinations** passed. See [targeted verification](targeted.json).
- Research SQL was regenerated from the unchanged, checksum-guarded generator.
  Its only diff is four new branches (leaf/tier for both providers). Those exact
  emitted predicates were checked locally using google-re2 1.1.20251105. No live
  BigQuery query was executed; this is not a fresh full-engine SQL parity claim.
- Independent original research-analyser/count/scikit-learn checks passed
  **39,984 metrics across 92 views**; see [validation](validation.json).
- The research copy repeated the entire suite with identical 134,227 prediction
  records, all aggregate metrics and the same five expected changes from baseline.
  [Review receipt](review.json) records its commands, checks and hashes.
- There is no increase in model-bound traffic: this is T4-to-T2, not T4-to-T5b.
  Existing deadline/cache/fallback tests passed. No new capacity or latency claim
  is made by fixed-clock offline quality runs.

Candidate implementation commits:
- Monorepo `2fbd9ac3ed956e6062b6652bdc39e3a83ecefa65`.
- Research `c0868b7a821407e9295ea8da6cca9b3ee0f9e536` (local; existing unpublished
  history and unrelated dirty report files are preserved, not pushed).

Parent bundle: `a2553f3462205963254b0fb1ad9dff6d64e1399abdecaab93977265908c7f23d`.
Candidate bundle: `ad825a7ad1f5ef5060fe282d1b4c864c55d142982d78a3387350e1bedac3cc41`.
Exactly `t2_collisions.json` and provenance differ; all other 16 payloads, including
both model heads, masks, dictionary, taxonomy, crosswalks and goldens, are identical.
The [manifest](bundle/MANIFEST.json) and [derivation provenance](bundle/provenance.json)
record hashes and inherited compiler/selection lineage. This is an explicit local
derivative of the retained B3/B5 bundle, not a fresh training/selection compilation.

The unchanged baseline evaluation harness was used on both sides; no baseline
rerun was required for a changed adapter or metric definition. Full source, dataset,
registry, model, rule, environment/package, config and dirty-patch identities are
in [summary.json](summary.json). Exact commands are in [REPRODUCTION.md](REPRODUCTION.md).

Serving rollback remains revision `ob-txn-categoriser-00005-xnl`, source
`631cc4a4e4d9424b639401f0dea27b920b5491b0`, bundle `a2553f3…`, release
`02bbaa7d087186b954edacb838c6181e3289fbbdde288cbbbc4bbe344b684467`.
The source and all score records are mirrored in research before any promotion.

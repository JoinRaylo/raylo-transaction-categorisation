# REVIEW-NOTES-001 — T2/T4/T5 corrections from the B05 benchmark review

Status: **accepted for staging. The full repeatable suite passed against the serving
baseline. Carlos accepted both convention trade-offs and approved the staging release
on 2026-09-23.** Created and evaluated 2026-09-23.
Owner: Carlos Noble Jesus. Implementation: Claude.

## Origin, declared

These rules come from Carlos's notes and rulings during the 2026-09-23 review of the
B05 2,000-row candidate benchmark. The master benchmark design says new rule
evidence must not originate in the reserved benchmark. Carlos asked for these rules
anyway, so the dependency is declared rather than hidden:

- the 122 benchmark rows whose deterministic outcome these rules decide are tagged
  `rule_exposure=["review-notes-001"]` in the private B05 final outcomes;
- T1–T5 scores on those rows are development diagnostics, not independent
  evidence;
- an untouched confirmation/OOT set must decide promotion claims.

## Changes (one hypothesis: apply the reviewer's merchant/narrative conventions)

| Tier | Change | Evidence |
|---|---|---|
| T2 builtin | `asda` + `asda\s*living` → `department_store` (was `home_accessories`); research `match_t2`, SQL generator, app `_t2_builtin.py` | note on review row |
| T2 collision | `usd_onlyfans`: merchant `usd`, debit, `\bto\s+of\s*,` → `adult_entertainment` | note ("OF is Only Fans") |
| T4 | `google play` → `gaming_mobile` (was `software`) | 2026-09-23 ruling |
| T4 | `post office` → `delivery_courier` (was `government_services`) | note |
| T4 | `angel hill site ca` → `restaurant_cafe` (was `car_parking`) | note |
| T5 R52 | description `^added to pot$` → `savings_transfer` | note |
| T5 R53 | description `^withdrew from pot$` → `transfer_own_account` | pilot ruling C, confirmed 2026-09-23 |
| T5 R54 | description `\bangel hill site\b`, debit → `restaurant_cafe` | note |
| T5 R55 | description `\bytc\b`, debit → `discount_store` | note (Yorkshire Trading Company) |
| T5 R56 | description `^daily od int`, debit → `interest_charged` | 2026-09-23 ruling (supersedes pilot ruling E; same principle as R36) |

Three noted rows needed no change, because the current dictionary already agreed:
Apple App Store → `software`, IVS France → `confectionary`, U.S. Post Office →
`delivery_courier`. Other rulings from the same day needed no rule:

- Gambling credits → `gambling_unspecified`: T1 already outputs it.
- Money-transfer providers → `money_transfer_service`: T4 already outputs it.

The Zilch ruling (visible merchant → merchant leaf) is not implemented. It needs
merchant re-parsing from the narrative, and it is not a single rule.

## Cases and false-positive scans

Research `tests/test_review_notes_001.py` has 11 positive, 5 negative and 2
precedence cases, plus a generated-SQL branch check. App
`test_tiers.py::test_asda_living_is_department_store_before_the_asda_dictionary_key`
covers the ported T2 builtin. Every new pattern was scanned on the 500,000-row B05
customer-linked pool and on `outputs/tuning_train.jsonl` (414,400 rows). Samples
showed no false positives:

| Rule | Pool hits | Tuning hits |
|---|---:|---:|
| R52 | 13,368 | 5 |
| R53 | 9,791 | 0 |
| R54 | 60 | 11 |
| R55 | 16 | 54 |
| R56 | 8,145 | 0 |
| usd_onlyfans | 7 | 5 |

## Identities

- Baseline: serving bundle `a2553f34…` built from research `f8e47ef`. Research
  `main` (`cc550d5`) also carries an unpromoted T2 collision
  (`waitrose_explicit_payroll`), so the candidate is based on `f8e47ef` to keep this
  change isolated.
- Candidate: research branch `claude/txncat-review-notes-001`; monorepo branch
  `claude/txncat-benchmark-2000`. `sql/apply_crosswalk.sql` is regenerated from
  the generator (baseline regeneration is byte-identical).

## Measured impact (deterministic waterfall, research `our_leaf`, Plaid native path)

- **500,000-row customer-linked pool** (label-free): 33,760 rows (6.8%) change route.
  25,615 of them change leaf; the other 8,145 are R56, which changes the tier only.

  | Transition | Rows |
  |---|---:|
  | `salary` → `savings_transfer` (R52) | 7,455 |
  | `savings_transfer` → `transfer_own_account` (R53) | 9,791 |
  | `savings_transfer` re-attributed to R52 | 5,913 |
  | `software` → `gaming_mobile` | 2,383 |
  | R54: `unclassified_transfer` 20, `gambling_unspecified` 19, other 10 | 49 |
  | R55 | 10 |
  | OnlyFans | 7 |
  | Asda Living | 6 |
  | Angel Hill T4 key | 1 |

  Salary false positives fall by 7,455. Behaviour-risk gambling false positives on
  Angel Hill cafeteria spend fall by 19. More rows leave T6 native fallback for T5.
- **B05 benchmark, labelled rows (1,761; development-exposed):** deterministic leaf
  accuracy rises from 53.27% to 56.27%. There are 53 wrong→right, 12 right→right
  (tier changed) and 0 right→wrong.

- **Serving engine, B05 benchmark (development-exposed, projected):** serving T6 is
  the classifier head, so the research-side view above understates some rules and
  overstates others.
  - R52 changes nothing in serving: "Added to Pot" is already `savings_transfer`,
    33/33.
  - R53 fixes 19/19 "Withdrew from Pot" rows.
  - R56 fixes the model's split on DAILY OD INT (41 `overdraft_arranged`, 6
    `bank_charge_other`).

  The projection replaces the 122 exposed rows with the rule output on the
  measured serving predictions. The production-facing slice goes from 80.4% to
  85.1%; all labelled rows go from 77.6% to 82.1%. 79 predictions change, all
  wrong→right. (Superseded by the measured result below.)
- R56 on the pool: 8,145 rows, research leaf unchanged (T6 crosswalk already said
  `interest_charged`), tier T6 → T5.

## Predeclared acceptance (for the full run)

1. Zero unexplained right→wrong transitions on every registered set, and no salary,
   refund or risk-leaf regression.
2. Salary precision is non-decreasing on every set that has salary gold.
3. Parity: research and app agree on every comparable input, including rule
   provenance.
4. The fixed-residual cohort is reported, because the change moves rows out of T6.

## Full repeatable evaluation (2026-09-23)

**Runs.**

- Candidate bundle `5d39f720…`: research `2d9f730`, B3 oracle `research-v2`,
  `seed-selection-v2` (seed 123; model files byte-identical to serving).
- Baseline: serving bundle `a2553f34…`, research `f8e47ef`, oracle `research-v1`.
- Monorepo code: `17ff133a` for the baseline and `58874910` (this branch) for the
  candidate. The harness is identical.

Both runs passed all six checks: app/library tests, research tests, lint, schemas,
research/app deterministic parity and real-model startup. Parity covered 35,200
synthetic combinations (baseline 34,880) plus 88 golden rows. Each run covered 16
repeatable datasets and 92 views. Independent verification passed: 92 views
recounted and 39,984 metric checks. Evidence is in this directory: `summary.json`,
`validation.json`, `RUN_REPORT.md` and `checks/` (candidate), and `baseline/`.

**Risk and credit: no change.** Risk-leaf correct counts, false negatives and false
positives on known non-risk gold are **unchanged in all 92 views**. The credit
evaluation (`gold_credit_eval`) is also unchanged: serving transformer 89.25%.

**Leaf transitions.** There are 197 changed rows, counted across overlapping views.
Every change is attributed to a cause:

| Cause | Effect on registered development gold |
|---|---|
| T4 `google play` → `gaming_mobile` | correct→wrong. Historical gold labels Google Play Apps `software`. The same handful of rows recurs across `gold_pipeline_eval`, `gold_transactions`, `v3_volume`/`v3_eyeball`, `v2_batch2`, `v2_slm_eval_holdout` and `gold_merchant_labels`. |
| T2 Asda Living → `department_store` | correct→wrong. Historical gold says `home_accessories` (1 unique row, in 3 sets). |
| T4 `post office` → `delivery_courier` | wrong→correct where gold is `delivery_courier`. Some rows go wrong→different-wrong where gold is `unclassified_other`/`cash_deposit` (research views only). |
| R54 Angel Hill | wrong→correct |

Serving Plaid transformer, correct leaves, baseline → candidate:

| Set | Baseline | Candidate |
|---|---:|---:|
| `gold_pipeline_eval` | 1,169/1,418 | 1,164 (6 c→w, 1 w→c) |
| `gold_transactions` | 2,899/3,501 | 2,892 (7 c→w) |
| `gold_transactions_v3_volume` | 806/900 | 800 (6 c→w) |
| `gold_v3_eyeball` | 803/900 | 797 (6 c→w) |
| `gold_transactions_v2_batch2` | 507/661 | 506 (1 c→w) |
| `gold_v2_slm_eval_holdout` | 486/627 | 485 (1 c→w) |

The research-pipeline views on `gold_transactions` and `gold_transactions_v2` gain 5
and 3 wrong→correct rows respectively (Post Office). `gold_transactions_risk_categories`
(legacy head+T5) gains 1.

**Acceptance.**

1. Zero *unexplained* right→wrong transitions: met. The explained right→wrong
   transitions all come from the Google Play and Asda Living conventions, which
   conflict with historical gold. Under the policy they are **explicit trade-offs
   for Carlos to accept or reject**. Gold is not edited to make the candidate pass;
   a versioned convention migration of development gold would be a separate task.
   There are no salary, refund or risk-leaf regressions.
2. Salary precision is non-decreasing: met (unchanged).
3. Parity: met.
4. Fixed residual: reported per view in `summary.json`
   (`comparison.comparisons[].fixed_baseline_residual`).

**B05 benchmark, measured candidate bundle** (transformer; development-exposed
because the rules came from this benchmark's review):

| Slice (labelled rows) | Baseline | Candidate |
|---|---:|---:|
| Production-facing: new representative core, weighted (738) | 80.4% (77.2–83.3) | **85.1% (82.4–87.6)** |
| All labelled (1,761) | 77.6% | 82.1% |
| Core, all views pooled (1,353) | 82.3% | 86.0% |
| Rare-leaf supplement (408) | 62.0% | 69.1% |

The measured figures equal the earlier projection. The 1,639 labelled rows that no
REVIEW-NOTES-001 rule touches score the same on both bundles: 80.72% overall and
83.71% production-facing. The whole gain comes from the 122 exposed rows.

**Release code.** Staging deploys from `feat/ob-txn-categoriser-plan`. The release
branch `claude/txncat-review-notes-001-promote` is that branch (`59423d0b`) plus this
change's own commits only. It excludes the unmerged AIE-513 merge (`37accf1d`) that
the evaluation branch also carried. The full suite was rerun on the release branch
code (`99c724f7`) with the same bundle, research source and baseline. It passed all
six checks and independent validation, with metrics **identical in all 92 views**
and the same 197 changed rows as the evaluated candidate. Evidence:
`promotion-branch/`.

**Rollback.** The app T2 port (`RESEARCH_SOURCE_SHA256` in `_t2_builtin.py`) and
`verify_deterministic.py` now pin research generator `73b2e0d8…` (was `93e3a7a5…`).
Candidate code refuses the old bundle and the reverse, so the image and bundle must
roll back together.

**Other bundle difference.** Provenance gains a `training_inputs` record. It comes
from the AIE-513 compiler merged into this branch (`37accf1d`), not from this
change, and does not change behaviour.

## Decision (2026-09-23)

Carlos accepted both trade-offs. Google Play → `gaming_mobile` and Asda Living →
`department_store` are the conventions going forward. The historical gold labels
that disagree (`software`, `home_accessories`) are known convention differences,
not engine errors. They stay unedited until a versioned gold migration.

## Remaining before promotion

- Staging release, each step with explicit approval:
  1. Publish `5d39f720…` to the staging artefacts bucket.
  2. Move the deployment bundle pin.
  3. Deploy the image built from this code.
  4. Rerun the live verifier and the signed synthetic API regression.
- After acceptance: reload the research T4 BigQuery scratch table
  (`load_t4_dictionary_bq.py`).
- Mirrored score-history row and research current-score pointer.
- AIE-503: R53 (pot withdrawals → `transfer_own_account`) and R56 (DAILY OD INT →
  `interest_charged`, tier only) may shift risk features.

# REVIEW-NOTES-001 — T2/T4/T5 corrections from the B05 benchmark review

Status: **proposed. Implemented on candidate branches, targeted checks passed, full
repeatable evaluation not run, not promoted.** Created 2026-09-23.
Owner: Carlos Noble Jesus. Implementation: Claude.

## Origin, declared

These rules come from Carlos's notes and rulings during the 2026-09-23 review of the
B05 2,000-row candidate benchmark. The master benchmark design says new rule
evidence must not originate in the reserved benchmark. Carlos asked for these rules
anyway, so the dependency is declared rather than hidden:

- the 65 benchmark rows whose deterministic outcome these rules decide are tagged
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

Three noted rows needed no change, because the current dictionary already agreed:
Apple App Store → `software`, IVS France → `confectionary`, U.S. Post Office →
`delivery_courier`. Other rulings from the same day needed no rule:

- DAILY OD INT → `interest_charged`: T6 already outputs it.
- Gambling credits → `gambling_unspecified`: T1 already outputs it.
- Money-transfer providers → `money_transfer_service`: T4 already outputs it.

The Zilch ruling (visible merchant → merchant leaf) is not implemented. It needs
merchant re-parsing from the narrative, and it is not a single rule.

## Cases and false-positive scans

Research `tests/test_review_notes_001.py` has 9 positive, 4 negative and 2
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

- **500,000-row customer-linked pool** (label-free): 25,615 rows (5.1%) change.

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

## Predeclared acceptance (for the full run)

1. Zero unexplained right→wrong transitions on every registered set, and no salary,
   refund or risk-leaf regression.
2. Salary precision is non-decreasing on every set that has salary gold.
3. Parity: research and app agree on every comparable input, including rule
   provenance.
4. The fixed-residual cohort is reported, because the change moves rows out of T6.

## Not yet run (blocks promotion)

- **Oracle v2 → candidate bundle → `run_evaluations.py`** (15 sets, both heads,
  parity, startup), with a baseline/candidate comparison. It is blocked by a
  pre-existing reproducibility gap. In a fresh checkout without bytecode caches, the
  frozen `research-v1` exporter audit flags `src/build_tail_eval.py`,
  `src/build_tuning_dataset.py` and `src/label_provenance.py`. They are imported by
  pinned `src/transformer/build_corpus.py`, but the oracle provenance does not record
  them. The fix is an exporter/provenance decision (record the transitive imports in
  a new oracle version). Bypassing the audit is not a fix.
- **Research T4 BigQuery scratch table**
  (`credit_risk_research.merchant_dictionary_t4`): reload through
  `load_t4_dictionary_bq.py` after acceptance. Not done here, because no cloud writes
  were made.
- Mirrored score-history row, staging release and signed API regression.

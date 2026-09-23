# REVIEW-NOTES-001 — T2/T4/T5 corrections from the B05 benchmark review

Status: **deployed to staging and live-verified on 2026-09-23.** Bundle `1b402aeb…`
is the version with Google Play reverted; it runs on image `sha256:09a862f3…`,
revision `ob-txn-categoriser-00024-jhk` and worker revision `00010-pkf`. The full
repeatable suite passed against the serving baseline, and Carlos approved the
release. Production is not deployed.
Owner: Carlos Noble Jesus. Implementation: Claude.

## Origin, declared

These rules come from Carlos's notes and rulings during the 2026-09-23 review of the
B05 2,000-row candidate benchmark. The master benchmark design says new rule
evidence must not originate in the reserved benchmark. Carlos asked for these rules
anyway, so the dependency is declared rather than hidden:

- the 113 benchmark rows whose deterministic outcome these rules decide are tagged
  `rule_exposure=["review-notes-001"]` in the private B05 final outcomes;
- T1–T5 scores on those rows are development diagnostics, not independent
  evidence;
- an untouched confirmation/OOT set must decide promotion claims.

## Changes (one hypothesis: apply the reviewer's merchant/narrative conventions)

| Tier | Change | Evidence |
|---|---|---|
| T2 builtin | `asda` + `asda\s*living` → `department_store` (was `home_accessories`); research `match_t2`, SQL generator, app `_t2_builtin.py` | note on review row |
| T2 collision | `usd_onlyfans`: merchant `usd`, debit, `\bto\s+of\s*,` → `adult_entertainment` | note ("OF is Only Fans") |
| T4 | `post office` → `delivery_courier` (was `government_services`) | note |
| T4 | `angel hill site ca` → `restaurant_cafe` (was `car_parking`) | note |
| T5 R52 | description `^added to pot$` → `savings_transfer` | note |
| T5 R53 | description `^withdrew from pot$` → `transfer_own_account` | pilot ruling C, confirmed 2026-09-23 |
| T5 R54 | description `\bangel hill site\b`, debit → `restaurant_cafe` | note |
| T5 R55 | description `\bytc\b`, debit → `discount_store` | note (Yorkshire Trading Company) |
| T5 R56 | description `^daily od int`, debit → `interest_charged` | 2026-09-23 ruling (supersedes pilot ruling E; same principle as R36) |

**Google Play: considered, then reverted (2026-09-23).** A same-day ruling moved
the `google play` T4 key to `gaming_mobile`. Carlos reverted it before release,
for three reasons:

- Play charges cover apps as well as games, and the narrative cannot tell them
  apart.
- `software` matches the Apple App Store ruling.
- `gaming_mobile` carries a compulsive-spend interpretation that app purchases
  should not inherit.

Research `f0afb9f` restores serving's dictionary row byte-for-byte, so Google Play
routing is unchanged from serving. The 9 B05 Google Play rows are relabelled
`software` through reconciliation rule R03.

Three noted rows needed no change, because the current dictionary already agreed:
Apple App Store → `software`, IVS France → `confectionary`, U.S. Post Office →
`delivery_courier`. Other rulings from the same day needed no rule:

- Gambling credits → `gambling_unspecified`: T1 already outputs it.
- Money-transfer providers → `money_transfer_service`: T4 already outputs it.

The Zilch ruling (visible merchant → merchant leaf) is not implemented. It needs
merchant re-parsing from the narrative, and it is not a single rule.

## Cases and false-positive scans

Research `tests/test_review_notes_001.py` has 11 positive, 5 negative and 2
precedence cases, plus a generated-SQL branch check. The Google Play case now
asserts `software`. App
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

- **Baseline:** serving bundle `a2553f34…`, built from research `f8e47ef`.
  Research `main` (`cc550d5`) also carries an unpromoted T2 collision
  (`waitrose_explicit_payroll`), so the candidate is based on `f8e47ef` to keep
  this change isolated.
- **Candidate research:** branch `claude/txncat-review-notes-001` at `f0afb9f`.
  `sql/apply_crosswalk.sql` is regenerated from the generator; regenerating the
  baseline the same way is byte-identical.
- **Candidate monorepo:** release branch `claude/txncat-review-notes-001-promote`,
  i.e. `feat/ob-txn-categoriser-plan` plus this change's own commits only.
- **Candidate bundle:** `1b402aeb2373474559586af84b9a018ba650accb0380ed1355542f2e00e91675`.
  It uses oracle `research-v3` and `seed-selection-v3` (seed 123), and was
  compiled with the release branch's own compiler. Compared with serving, only
  `MANIFEST.json`, `provenance.json`, `dictionary.marshal`, `rules.json` and
  `t2_collisions.json` differ; the model weights are byte-identical. The
  dictionary differs from serving in exactly two keys: `post office` and
  `angel hill site ca`.

## Measured impact (deterministic waterfall, research `our_leaf`, Plaid native path)

- **500,000-row customer-linked pool** (label-free): 31,377 rows (6.3%) change
  route. 17,318 of them change leaf. The other 14,059 change tier only: 8,145 R56,
  5,913 R52 re-attributions and 1 R54 row already at `restaurant_cafe`.

  | Transition | Rows |
  |---|---:|
  | `savings_transfer` → `transfer_own_account` (R53) | 9,791 |
  | `interest_charged`, T6 → T5 (R56) | 8,145 |
  | `salary` → `savings_transfer` (R52) | 7,455 |
  | `savings_transfer` re-attributed to R52 | 5,913 |
  | R54: `unclassified_transfer` 20, `gambling_unspecified` 19, other 10 | 49 |
  | R55 | 10 |
  | OnlyFans | 7 |
  | Asda Living | 6 |
  | Angel Hill T4 key | 1 |

  Salary false positives fall by 7,455. Behaviour-risk gambling false positives on
  Angel Hill cafeteria spend fall by 19. More rows leave T6 native fallback for T5.
- **B05 benchmark, labelled rows (1,761; development-exposed):** deterministic leaf
  accuracy rises from 53.78% to 56.27%. There are 44 wrong→right, 69 right→right
  (tier changed) and 0 right→wrong.

## Predeclared acceptance (for the full run)

1. Zero unexplained right→wrong transitions on every registered set, and no salary,
   refund or risk-leaf regression.
2. Salary precision is non-decreasing on every set that has salary gold.
3. Parity: research and app agree on every comparable input, including rule
   provenance.
4. The fixed-residual cohort is reported, because the change moves rows out of T6.

## Full repeatable evaluation (2026-09-23)

**Run.** The candidate is bundle `1b402aeb…`: research `f0afb9f`, monorepo release
branch `f649dd7b`, both trees clean. The baseline run is unchanged: serving bundle
`a2553f34…`, research `f8e47ef`, monorepo `17ff133a`, identical harness. All six
checks passed:

- app/library tests
- research tests
- lint
- schemas
- research/app deterministic parity: 35,200 synthetic combinations (baseline
  34,880) plus 88 golden rows
- real-model startup

The run covered 16 repeatable datasets and 92 views. Independent verification
passed: 92 views recounted and 39,984 metric checks. Evidence in this directory:
`summary.json`, `validation.json`, `RUN_REPORT.md`, `checks/` and `baseline/`.

**Risk and credit: no change.** Risk-leaf correct counts, false negatives and false
positives on known non-risk gold are **unchanged in all 92 views**. The credit
evaluation (`gold_credit_eval`) is also unchanged: serving transformer 89.25%.

**Leaf transitions.** There are 76 changed rows, counted across overlapping views.
Every change is attributed to a cause:

| Cause | Effect on registered development gold | Views (unique rows) |
|---|---|---:|
| T4 `post office` → `delivery_courier` | wrong→correct, gold `delivery_courier` | 36 (12) |
| T4 `post office` → `delivery_courier` | wrong→different-wrong, gold `unclassified_other` / `cash_deposit` (research views only) | 18 (6) |
| R54 / T4 Angel Hill → `restaurant_cafe` | wrong→correct | 7 (3) |
| T2 Asda Living → `department_store` | correct→wrong; historical gold says `home_accessories`. One transaction appearing in 3 sets; accepted trade-off. | 15 (3) |

Serving Plaid transformer, correct leaves, baseline → candidate:

| Set | Baseline | Candidate |
|---|---:|---:|
| `gold_pipeline_eval` | 1,169/1,418 | 1,170 (1 w→c) |
| `gold_transactions` | 2,899/3,501 | 2,898 (1 c→w, Asda Living) |
| `gold_transactions_v3_volume` | 806/900 | 805 (1 c→w, Asda Living) |
| `gold_v3_eyeball` | 803/900 | 802 (1 c→w, Asda Living) |

Every other serving view is unchanged. The research-pipeline views gain Post Office
and Angel Hill rows: `gold_transactions` +4 net, `gold_transactions_v2` +3,
`gold_pipeline_eval` +1, and `v3_volume` / `v3_eyeball` +1 each.
`gold_transactions_risk_categories` (legacy head+T5) gains 1.

**Acceptance.**

1. Zero *unexplained* right→wrong transitions: met. The only right→wrong transition
   is the Asda Living convention, which Carlos accepted as an explicit trade-off.
   There are no salary, refund or risk-leaf regressions.
2. Salary precision is non-decreasing: met (unchanged).
3. Parity: met.
4. Fixed residual: reported per view in `summary.json`
   (`comparison.comparisons[].fixed_baseline_residual`).

**B05 benchmark** (transformer; B05 final outcomes after the Google Play
relabel; development-exposed, because the rules came from this benchmark's review):

| Slice (labelled rows) | Serving `a2553f34` | Candidate `1b402aeb` |
|---|---:|---:|
| Production-facing: new representative core, weighted (738) | 81.1% (77.9–84.0) | **85.1% (82.4–87.6)** |
| All labelled (1,761) | 78.1% | 82.1% |
| Core, all views pooled (1,353) | 82.9% | 86.0% |
| Pilot (435) | 85.1% | 87.6% |
| Rare-leaf supplement (408) | 62.0% | 69.1% |
| Unseen-input / unfamiliar-merchant | 86.9% / 72.1% | 86.9% / 72.1% |

The hinge head's production-facing figure moves from 80.0% to 84.2%. The 1,648
labelled rows that no REVIEW-NOTES-001 rule touches score identically on both
bundles: 80.83% overall and 83.84% production-facing. The whole gain comes from the
113 exposed rows. The serving baseline is higher than the 80.4% quoted before the
relabel because serving already outputs `software` for Google Play.

**Rollback.** The app T2 port (`RESEARCH_SOURCE_SHA256` in `_t2_builtin.py`) and
`verify_deterministic.py` pin research generator `73b2e0d8…` (was `93e3a7a5…`). The
Google Play revert does not touch the generator. Candidate code refuses the old
bundle and the reverse, so the image and bundle must roll back together.

## Superseded candidate `5d39f720…` (never served)

The first candidate included Google Play → `gaming_mobile`. It was built from
research `2d9f730` with oracle `research-v2` and `seed-selection-v2`, and its
provenance carried an AIE-513 `training_inputs` record. Here is what happened to it:

- It passed the same suite: 197 changed rows, and the Google Play correct→wrong
  rows were recorded as a trade-off.
- It was re-evaluated on the release-branch code with identical metrics.
- It was published to the staging artefacts bucket (`bundle-build-rn001/`).
- The staging deploy was cancelled before any deploy step ran, when Carlos
  reverted Google Play.

It remains in the create-only bucket and is never pinned. Its evidence is in
`superseded-5d39f720/`. Its pre-relabel B05 outcomes are kept privately, under
`superseded-gaming-mobile-google-play/`.

## Decision (2026-09-23)

- Carlos accepted the Asda Living → `department_store` convention.
- Carlos reverted Google Play to `software`.

The historical gold label that disagrees on Asda Living (`home_accessories`) is a
known convention difference, not an engine error. It stays unedited until a
versioned gold migration.

## Staging release (2026-09-23)

1. **Publish.** Bundle `1b402aeb…` was published and independently read back
   ([bundle-build-rn001b](../../bundle-build-rn001b/README.md)).
2. **Pin.** Monorail staging `ARTEFACT_BUNDLE_SHA` was set to `1b402aeb…`, and both
   environment copies were verified.
3. **Deploy.** `feat/ob-txn-categoriser-plan` was fast-forwarded to `c74e53e1`,
   and CI dispatch run
   [35877757371](https://github.com/JoinRaylo/internal-services-monorepo/actions/runs/35877757371)
   succeeded. Service revision `00024-jhk` and worker `00010-pkf` both run image
   `sha256:09a862f3a4848c7bb879cf6dfd443f5f9aac2f143889f5c6f52e2aadd3171724` with
   bundle `1b402aeb…`. `/health` and `/ready` return 200.
4. **Verify.** `verify_staging.py` passed ([receipt](staging_verification.json)).
   It covers:
   - bearer-authenticated version and categorisation requests;
   - rejection of missing and wrong tokens;
   - an 84-row response;
   - exact pinned and gzip replay;
   - archive, publication and ledger read-back using operator credentials.

   Real Taktile traffic, BigQuery delivery and capacity were not in scope.
5. **Record the image.** Monorail `IMAGE_DIGEST` was updated to the verified
   image.

An earlier dispatch (run 35875138466, bundle `5d39f720…`) was cancelled before its
deploy step ran.

## Remaining

- Reload the research T4 BigQuery scratch table (`load_t4_dictionary_bq.py`).
- Add the research current-score pointer. The research branch is based on serving
  `f8e47ef`, which predates the mirrored score history.
- AIE-503: R53 (pot withdrawals → `transfer_own_account`) and R56 (DAILY OD INT →
  `interest_charged`, tier only) may shift risk features.
- Production rollout needs its own review.

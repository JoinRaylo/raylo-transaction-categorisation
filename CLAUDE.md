# CLAUDE.md — context for continuing this work

Research repo for Raylo's unified transaction categorisation. Read this before touching anything.

Full design rationale and stakeholder-facing write-up:
**Notion — [Unified Transaction Taxonomy: Research, Evidence & Design](https://app.notion.com/p/3bf5bb4b4a6581b6807add39671e56c2)**

Owner: Carlos (AI Engineer, AI Acceleration team). This is **research**, not production. Nothing here is referenced by any dbt model or scheduled job, and it must stay that way until explicitly promoted.

**Reading order for a new agent:** the 7 Sep block, then the 2 Sep block → `docs/project-summary.md` §8 + 27 Aug progress-log lines → `data/classifier_v5_retrain_report.md` if touching the classifier → `AGENT_RULES.md` for locked product conventions (the 100k review itself is closed). Do not treat `docs/architecture-remediation-handoff.md` as live coverage numbers (25 Aug proposal). Do not score `data/gold_transactions_v5_LOCKED.csv` (retired) or `data/gold_transactions_v6_LOCKED.csv` (locked; Carlos labelled the 8 flags 27 Aug; `apply` written). Do not score v6 until go/no-go.

## Standing waterfall change process (2026-09-15)

Carlos requires conservative, individually documented waterfall changes, a full
repeatable evaluation run after every candidate revision, and mirrored code plus
updated scores in this repo and the app monorepo. Read
[the change policy](docs/waterfall-changes/POLICY.md) and
[score history](docs/waterfall-changes/README.md) before editing classification
behaviour. Keep v5 retired and v6 reserved for final go/no-go. The [fresh complete baseline](docs/waterfall-changes/baseline-2026-09-15/RECORD.md)
now covers 15 permitted datasets plus seven synthetic examples across 92 views.
The [latest candidate, CREDIT-PAYROLL-001](docs/waterfall-changes/credit-payroll-001/RECORD.md),
adds exactly one Waitrose + complete PAYROLL narrative + credit collision to T2.
All 15 permitted datasets and both heads have identical real-data scores to the
baseline, with zero regressions; the explicit synthetic payroll changes groceries
T4 to salary T2 (5/7 synthetic cases now pass, previously 4/7). Bare credits remain
ambiguous and unchanged. There are no exact-merchant Waitrose credits in existing
evaluation sets, so the result does not establish generalisation. Research replay
is identical; 1,201 app/library and 74 research tests passed. SQL was regenerated;
four added predicates passed local RE2 checks, not a new live BigQuery execution.
See [RUNNING.md](docs/waterfall-changes/RUNNING.md) and the candidate reproduction guide.
Current seed-123 serving Plaid specific accuracy remains: holdout 77.51% (627),
credits 89.25% (2,000), targeted risk 72.25% (400). Mixed-provider research exact
accuracy remains 83.80% on 2,000 rows for this seed; the older 83.2% headline below
is a three-seed result. The candidate source/SQL is local research code, not a
production promotion. Models/masks and staging are unchanged; retain the original
staging bundle until a separate release decision.

## Dataset continuation handover (2026-09-16)

For dataset work, read [HANDOVER.md](docs/benchmark-handover/2026-09-16/HANDOVER.md)
and [the initial assignment](docs/benchmark-handover/2026-09-16/NEXT_AGENT_PROMPT.md)
first. They preserve the approved linked-only scope, three-view distinctions,
training augmentation, exact repo/evidence state and open gates. B03-A is a bounded
synthetic reservation-protocol milestone requiring review before real authority or
dataset admission. It is not completion of B03/B04. Use dedicated worktrees/branches
to avoid conflicting with the ongoing app work; preserve this checkout's unrelated
changes and unpublished history. The tested startup command passes 115 tests.
No benchmark membership, labels, model, metrics or staging changed in the handover.

## B03-A synthetic protocol (2026-09-16)

The canonical app module is `lib/raylo-txncat/src/raylo_txncat/benchmark_authority.py`,
with design/evidence mirrored at `docs/benchmark-implementation/b03-a-synthetic/`.
It has 29 passing synthetic tests for reservation, learning and selection claims,
object-generation/digest checks, stale epochs, operation retries, permanent
identity protections, three-view novelty, alias contamination and authority
outage. Final independent `gpt-5.6-sol` protocol review is approved with no
residual actionable findings; current evidence is `verification-v2.json` and the
original pre-correction snapshot remains unchanged. The in-memory store and
`LocalReceipt` are explicitly non-authorizing; no labels, locked sets, training,
scoring, cloud changes or consumer integration occurred. The scoped production
GCS/Firestore boundary is now implemented behind injected ports with synthetic
fake tests, while physical scope, IAM, authenticated receipts and all B03/B04,
source-history, sampling and label gates remain open for review.

## B03-B linked-pool audit (2026-09-16)

The new [aggregate-only live profile](docs/benchmark-implementation/b03b-linked-pool-audit-2026-09-16/README.md)
used one pinned `raylo-production` EU `SELECT` and the existing assessment →
checkout → user → customer linkage. It found 36,312,899 materialized source
observations and 20,474,043 unambiguous customer-linked observations across
46,051 customers, with 15,838,856 identity-excluded rows. This is a source
readiness snapshot only: zero repeats in the materialized transaction-ID table
does not prove raw-event uniqueness or pending/posted/reconnect alias completeness.
No raw rows were exported, and no reservation, label, model, locked set, training,
score or cloud mutation occurred. The adapter contract/evidence is mirrored at
`docs/benchmark-implementation/b03-b-production-boundary-2026-09-16/`; next is
review of the physical production boundary and authenticated receipt model,
then complete-history candidate admission—not a local preflight allow.

## B03-C annotation-method pilot runner (2026-09-16)

The provider runner is tools/benchmark/annotation_pilot.py; the strict item,
manifest, attempt, vote and three-way comparison contract is canonical in the
app monorepo at lib/raylo-txncat/src/raylo_txncat/benchmark_annotation.py.
It supports one-request-per-item online calls plus explicit asynchronous
batch-submit, batch-status and batch-collect modes. Anthropic uses its API
batch route with deterministic short custom IDs; Gemini batch uses the
API-key inline route because the Vertex batch route requires a GCS/BigQuery
source. The runner records digest-only job state before submission, fails
closed on uncertain operations, and never silently fills a label or chooses a
majority.

One synthetic item was sent through all three online routes and both
asynchronous provider routes. The online outputs passed strict parsing; a
valid Sonnet batch output was collected, while invalid batch fields were
recorded as schema failures rather than labels. This is only annotation-method
evidence. No real customer rows were downloaded or labelled, no 500-row pilot
was admitted, and no B04 consumer is wired to these outputs. The runner's
quarantine path is not a substitute for downstream gates; these artifacts
cannot authorize evaluation, training, selection, scoring or promotion. Physical authority,
authenticated receipts, complete linked-pool history/aliases, eligibility and
B04 consumer gates remain open.

## B03-B authenticated receipt boundary (2026-09-17)

The canonical app boundary now includes strict `AuthenticatedReceipt` and
`ReceiptSignature` types, an injected `AuthorityReceiptSigner`, and a lazy
`KMSAuthorityReceiptSigner`. `ProductionAuthorityStorage` issues and verifies
one exact-object receipt only for a committed, held learning or selection claim;
the receipt carries an authority-resolved audience and consumption rechecks the
current worker principal and role. It rejects local/forged receipts, wrong
worker scope, reservations, contaminated/stale operations and changed object
bytes. The KMS adapter receives an already-configured client and key version,
checks returned key identity, algorithm, 2048-bit key size and CRC32C fields;
it creates no resources and makes no calls at import time. Synthetic evidence is mirrored at
`docs/benchmark-implementation/b03-b-production-boundary-2026-09-16/`.

This does not prove live KMS custody, IAM, retention, cross-process races or
service-account denied-access behavior. No B04 consumer is connected, and no
real rows, labels, benchmark membership, model fit, locked-set score or cloud
state changed. The next gate is physical resource/IAM/KMS review and separately
approved live permission proofs, followed by B04 consumer integration.

## B03-B physical scope review (2026-09-17)

The [physical scope review packet](docs/benchmark-implementation/b03-b-physical-scope-review-2026-09-17/README.md)
is proposal-only. It converts the existing IAM plan into decisions and evidence
requirements for an isolated project/location, immutable object store, registry,
distinct worker and authority identities, retention/deletion, audit logging and
KMS custody. It also requires an explicit choice for how learning and selection
workers verify authority receipts; object-read permission must not be treated as
KMS public-key permission, and verification must fail closed without a local or
cached fallback.

No physical resource, IAM binding, KMS key or live permission/cross-process probe
has been created or run. The packet does not authorize customer-linked Plaid
admission, labels, benchmark membership, B04 consumers, training, scoring or
cloud mutation. Approval must record the concrete choices and owners before any
live probe begins.

## Joint benchmark and retraining data plan (2026-09-16)

Read [the full-pool profile and joint plan](docs/benchmark-implementation/b02-joint-data-plan-2026-09-16/README.md)
before new curation or retraining. Current production materialization: 36,312,899
rows, of which 20,473,397 have unambiguous existing customer links (46,049 customers,
71,103 accounts). Linked credits are 22.85%; blank merchants are 35.22%, including
90.26% of credits. These are already transaction-ID-deduplicated materialized rows,
not proven unique economic events or clean benchmark examples. This clarifies the
older “raw rows before deduplication” wording; original dated audit evidence stays
unchanged. Anonymous recovery remains out of scope.

The 414,400-row supervised file has 342,268 distinct exact input messages, 133
conflicting-label groups, 7.31% credits and 7.91% blank merchants. Four taxonomy
leaves are absent; 21 represented leaves have fewer than 20 distinct input/label
examples. Old selection validation has nine credits and no blank merchants; keep
its documented exposure limitations. The transformer also inherits the separate
404,982-text consensus/MLM ancestry, so these proportions are not its total exposure.

The proposed envelope retains the 20,000-row master and separate 500-row annotation
pilot, and adds a new 5,000-row selection set plus up to 10,000 training additions.
These are planning budgets, not reserved or labelled data. Implement B03/B04
reservation/consumer admission, verify linked candidate ancestry and group blocks,
then reserve the pilot. Protect evaluation/selection memberships before fitting
either head; never use failed or unknown admission as a training fallback. Review
the existing label conflicts without automatic relabelling. No new MLM/vocabulary
extension is proposed for the final supervised retrain. Capture direction-mask
changes explicitly and rerun/mirror the complete permitted evaluations after any
real model/waterfall change. Models, current scores, v5/v6 restrictions and staging
are unchanged. The scoped 39,427-event linked engineering exposure cross-profile
does not certify the full 20.47M-row population.

## Historical regression and identity/exposure increment (2026-09-16)

Read [the frozen cohort and audit](docs/benchmark-implementation/b02-curation-audit-2026-09-16/README.md)
before creating or consuming benchmark data. Historical-regression-v1 has 8,212
transaction input cases (3,927 explicit training-origin diagnostics, 4,285 other
historical cases), 641 head-only cases and 1,810 dictionary cases. Withhold the 28
conflicting-label groups; preserve the existing 5,000-row selection-validation role.
These are development cases with known/uncertain historical exposure, not independent
master events. Reuse their fixed membership with `benchmark_score_legacy.py` after
each complete permitted evaluation run. Baseline cached predictions give 85.10%
specific leaf accuracy for seed-123 Plaid serving on the 3,704 other-historical cases;
this new denominator is neither a performance gain nor a population accuracy claim.
All 19 groups and original label/role provenance are preserved separately.

The identity audit recovers 263 direct links in current checkout/user tables without
changing the old extract. Remaining 39,110 observations / 38,498 account-event keys
lack customer identity (mainly cancelled/abandoned checkouts). Do not substitute a
checkout-customer-info ID for a stable person. Effective-token, sparse and lexical
screens cover declared retained corpora/training/top-up/legacy inputs; exact known
merchant presence covers retained dictionaries, collisions and merchant-label data.
Unknown historical identity, aliases, reviewed merchant families, protected legacy
exports and B03/B04 enforcement still block fresh reservations and labelling. See
[FOLLOW_UP.md](docs/benchmark-implementation/b02-curation-audit-2026-09-16/FOLLOW_UP.md).
No v5/v6 contents, new-source predictions, waterfall/model changes or deployment.
The adapters import the canonical monorepo package; do not fork their algorithms.

## Linked-customer population decision (2026-09-16)

Read [the v1 scope decision](docs/benchmark-implementation/b02-linked-customer-scope-2026-09-16/DECISION.md)
first. V1 benchmark candidates use the audited linked-customer Plaid pool with
unambiguous existing assessment → checkout → user → customer links; unresolved or
ambiguous rows are excluded from admission, with source records preserved. The last
audited Plaid source had 20,084,276 of 35,553,295 raw rows linked (56.49%), covering
45,617 users/customers; these raw counts precede deduplication/exposure checks, are
not unique economic transactions, and are not admitted labelled examples. Other-
provider and historical regression evaluation remains separate.
The earlier requirement to recover anonymous identity before v1 is superseded.
No new identity system is required.

Next work profiles the linked pool and handles deduplication, aliases, and
view-specific exposure before sampling. Category coverage needs independent labels;
provider labels and model outputs are not category truth.

## Applicant identity and transport review (2026-09-16)

The fixed 49-checkout aggregate query found 49 nonblank canonical emails, 49 without
user IDs, zero direct user/customer matches and zero exact matches to known customers;
see [MEASUREMENTS.md](docs/benchmark-implementation/b02-applicant-identity-2026-09-16/MEASUREMENTS.md).
This is scoped evidence only; no other anonymous checkouts were joined. Alias, ancestry,
reviewed-family, B03 and B04 gates remain pending.

Read [the applicant identity review](docs/benchmark-implementation/b02-applicant-identity-2026-09-16/README.md)
before using applicant/customer identity in benchmark work. Assessment, checkout,
provider, account and transaction identifiers support correlation and repeat-event
grouping; anonymous applicant ownership remains unresolved. Use the assessment-first
warehouse/sidecar join and authoritative User/Customer or separately reviewed link
evidence where available. AIE-496 caller-context persistence is replay lineage work,
not a solution to anonymous identity. No categoriser DTO, runtime, provider or
auth-flow change is implied. Keep aggregate measurements in the separate
`MEASUREMENTS.md` artifact for the fixed-cohort aggregate and its limitations.

## Master benchmark design (2026-09-15)

Read [the design](docs/benchmark-design/master-v1/DESIGN.md),
[identity/separation contract](docs/benchmark-design/master-v1/DATA_CONTRACT.md) and
[implementation plan](docs/benchmark-design/master-v1/IMPLEMENTATION_PLAN.md) before
creating new evaluation or training datasets. Proposed master-v1 has core/challenge/
sealed confirmation cohorts and permanent event/customer/effective-input exclusions
covering supervised learning, MLM, distillation, fitted preprocessing and enrichment.
The current suite remains development evidence; historical non-exposure is not yet
certified. This is a design, not implemented enforcement or permission to open v6.
Start with source/exposure inventory and the shared identity/admission contract,
then integrate all consumers before reserving and labelling the final master.

## Historical exposure and source-identity audit (2026-09-15)

Read [B01 findings and evidence](docs/benchmark-audits/b01-2026-09-15/REPORT.md)
before treating older held-out/merchant-disjoint claims as ancestry-wide separation.
All 2,000 credit and 400 targeted-risk inputs match exact sentences in the preserved
21.5M MLM corpus, although neither set matches the current supervised tuning file.
Independent reconstruction of the distillation parent matches 1,885/5,000 selection
validation inputs, 1,741 with matching labels. This is corroborated history, not an
original fit-consumption receipt; full tokenized/near-duplicate exposure remains open.
The 35,553,295-row current Plaid source resolves existing user/customer IDs for
56.49% of rows; 43.51% remain unresolved. All 428,949 report IDs are null; source
identity/context repairs and shared exposure admission precede master collection.
Keep current scores as development evidence, with these limitations; this audit
does not quantify accuracy inflation, certify a clean cohort or change any model.
The old risk/sequence-model experiments have separate ancestry and are not certified
by this categorizer audit. No v5/v6 content was opened, and staging is unchanged.

## Benchmark source/index increment (2026-09-16)

Read [the source/index report](docs/benchmark-implementation/b02-source-index-2026-09-16/REPORT.md)
and pinned reproduction manifest. The private 78,537-observation engineering sample
recovers report ID, Item/institution, transaction currency and pending fields from raw
Taktile/Plaid requests. These are present in the raw source despite the flattened
schema gaps. The sample has 77,925 distinct account/transaction events, 612 repeat
observations and 39,373 observations without an unambiguous user/customer link.
The canonical `raylo_txncat.benchmark_exposure` index covers all 21,524,807 preserved
MLM sentences, their vocabulary prefix, consensus, tuning and selection sources.
All 40 B01 overlap checks agree after correcting the index adapter to use historical
raw consensus text; full app/library suite 1,337 passed, final targeted checks 39 passed.
The adapters in `tools/benchmark/` import the same monorepo package; private key,
source rows and SQLite files are outside Git. Do not consume them for learning or
labelling: no clean benchmark has been admitted. Identity/alias reconstruction,
effective token/sparse/near-duplicate indexes, controlled merchant families,
legacy memberships and B03/B04 enforcement remain pending. Current pipeline,
model bytes, accuracy scores and staging are unchanged. No locked labels were read.

## Benchmark curation foundation (2026-09-15)

The approved [three-view amendment](docs/benchmark-implementation/b02-initial/CONTRACT_AMENDMENT.md)
supersedes master-v1's universal input-novelty requirement: representative new events
may naturally repeat historical model inputs; strict unseen-input and unfamiliar-family
views keep their additional exclusions. All views protect event/customer/account
separation. Views may overlap within a partition; they are not independent datasets.
The canonical local preflight code is in the monorepo `raylo_txncat.benchmark`.
Run the mirrored `tools/benchmark/benchmark_preflight.py` with that checkout and
the hash-pinned implementation manifest; do not fork the exclusion algorithm here.
[Evidence](docs/benchmark-implementation/b02-initial/README.md): 1,298 app/library
and 93 payload-extractor tests passed; synthetic app/research profiling is checked
against the same source. Every result has `authorizes_consumption=false`. These are
local checks, not B03 reservation receipts or B04 consumer enforcement. Source identity
repair/backfill, complete historical projections/indexes and a real candidate export
remain pending. No labels, training, model scores, waterfall or deployment changed.

## Current state (2026-09-07) — read this first

Headline numbers as of 7 Sep. Everything below this block (2 Sep, 27 Aug) is still accurate history unless contradicted here. Stakeholder report: `docs/report-2026-09/OB_Transaction_Categorisation_Report_Sep2026.{html,pdf}` (Chrome-rendered; edit the HTML, re-print). Programme summary: `docs/programme-summary-2026-09-05.md`.

- **Training data:** jsonl **414,400** rows (de-leaked 381,560 + credit top-up 27,979 + risk top-up 4,998; credit share 7.4%). New eval sets, all merchant-disjoint from every training source: `data/gold_credit_eval.csv` (2,000), `data/gold_transactions_risk_t6bound.csv` (400; the honest risk metric is its 174 risk-leaf rows). Distillation labels `data/distillation_labels_consensus.parquet` (404,982 texts where Gemini 3.7 Flash == Sonnet 5, no tiebreak; training signal only, never eval/dictionary). Holdout MD5 `7456da977a2c761119368637658232b6`.
- **Rules:** T5 R33–R51 (card issuer / overdraft / blank-merchant description rules). Dictionary **90,264**, BQ reloaded. Parity **2,000/2,000**.
- **Hinge v8** (`tfidf_linearsvm_sgd_v8_risk.joblib`) is the reference hinge for every transformer comparison: holdout 57.1 / 64.3, credit eval **85.9%**, T6-bound risk-leaf acc **75.9%** (n=174; above the 70% bar honestly for the first time; 48% → 59% came from rules R33–R37, → 76% from the risk tranche). Serving dump is still **v5** and is 24pp behind on credits and 28pp on T6-bound risk; promoting v8 is the zero-risk interim. `data/classifier_v8_risk_report.md`.
- **Transformer categoriser, iteration 8 = best T5b candidate:** DistilBERT (66M) + 4,000 domain tokens, MLM on the full 21.5M-sentence corpus (GCP L4, 6.5 GPU-h, ~£7), first fine-tune pass on the consensus labels, then uncapped gold pass; 3 seeds vs hinge v8: holdout T6-bound **64.5 vs 59.4** (+5.1 [+1.8, +8.8]), pipeline residual **65.0 vs 59.8** (+5.2 [+2.0, +8.2]), credit eval **88.8 vs 85.9** (+2.9), T6-bound risk leaves **85.6 vs 75.9** (+9.8 [+5.2, +15.1]), full pipeline **83.2 vs 82.2**, general +7–13pp. Every accuracy criterion passes with CIs excluding zero. **CPU 360 rows/s (hinge ~1,050); Carlos accepts this for now.** Artefacts `outputs/distill_models/txn_classifier_gold_distilled_s{42,7,123}`, encoder `txn_encoder_mlm_distilbert_full` (tgz in `gs://raylo-txn-categorisation-scratch/transformer/`). `data/transformer_classifier_report.md` iterations 4–8. The BERT-small MLM encoder `txn_encoder_mlm` was overwritten by a smoke test; regenerate on GPU if ever needed.
- **Experiment 3 champion, capped at 50 features (carried forward):** the development champion (`experiment3_champion_month6.joblib`, 0.7 XGB + 0.3 LGB on 1,654–3,150 leaf-level columns) scores **0.533 / 0.618** but is not governable. Same recipe under a hard cap, features ranked by pre-OOT gain across both families and 3 seeds (`src/experiment3_champion_capped.py`): **50 → 0.508 / 0.583**, 100 → 0.520 / 0.589, 200 → 0.529 / 0.600 (month3 / month6). Six-month gap to uncapped at 50 is −0.035 [−0.057, −0.014]; ~1/3 of the champion's gain is recipe, ~2/3 is width. **Decision (Carlos, 7 Sep): the 50-feature capped champion is the reference for the prospective test; uncapped kept as ceiling. Later the same day: single XGBoost, not the blend** — at cap 50 the XGB component alone scores **0.508 / 0.588** vs blend 0.508 / 0.583 and LGB alone 0.500 / 0.559; re-choosing the blend weight on capped folds picks pure XGB for month6. Reference artefacts `outputs/experiment3_champion_capped_xgb_month{3,6}_50.joblib` (blend versions `_capped_month{3,6}_50.joblib` kept); `data/experiment3_champion_capped_report.md`. Quote **0.508 / 0.588** as the carried-forward model; the blend is "tried, no gain at any cap, dropped for simplicity". Only 21 of its 50 features overlap the August 50-feature XGB (0.477 / 0.562); the rest are leaf-level shares/averages the August model could not choose from.
- **Granularity on the champion recipe (7 Sep, `src/experiment3_champion_granularity.py`, `data/experiment3_champion_granularity{,_uncapped}_report.md`):** uncapped, month6 rewards detail (275 leaves 0.612 XGB vs today's 69 0.586, monotone down to 0.510 at 4 groups); month3 does not (69 peak 0.536, 275 0.528). Capped at 50 by gain from the raw rung pool, 275 leaves is the **worst** rung on both targets (0.409 / 0.511) — cap crowding: only 2 of 31 spine columns survive at 275 vs 9 at 17 groups. **Quote the August-recipe "275/69/29 indistinguishable" only as the August-recipe result**; the stakeholder report section 3 now gives both. Keep 275 governed; the capped champion selects from a curated base (spine + KEY_LEAVES blocks + leaf features), which is why it reaches 0.588 where the raw-pool 275 rung capped reaches 0.511.
- **OB-transformer hand-offs (that repo, `docs/phase1-benchmark.md`, `docs/phase2-pretraining.md`, `docs/summary-comparison.md`):** on the **single-XGBoost 50-feature champion** (their refit 0.265 PR-AUC / 0.588 Gini, 6,252 OOT / 397 bad; OB-transformer commit b43fa0e, 7 Sep pm), one bge-base text score adds **+0.034 PR-AUC / +0.024 Gini** (both sig.; was +0.012 / +0.009 on the uncapped champion); the frozen 15M sequence-encoder score adds +0.031 / +0.029; **both together 0.322 / 0.629**, above the uncapped champion (0.291 / 0.616) with 52 columns. (Blended-base run earlier that day: 0.261 / 0.580 base, both scores 0.316 / 0.621 — deltas within 0.003.) Text-only recipe stays **locked** (bge-base); text + encoder is the **registered challenger** for the prospective test. Full 8-encoder sweep on the single-XGB capped champion (7 Sep pm): +0.017 to +0.034 PR-AUC, all Gini CIs exclude zero, one band; bge-base 0.299 / 0.611 and our domain-pretrained DistilBERT 0.296 / 0.613 share the top with e5-large, 568M bge-m3 buys nothing, our category-fine-tuned encoder is weakest. **Decision (Carlos, 7 Sep): keep bge-base locked; our DistilBERT (half the serving cost, no third-party model, but its MLM corpus included the OOT period's text) is the named alternative to be scored alongside it in the prospective test.** Sequence encoder sizes 5.5M / 15M / 51M were tried: flat from 15M up. Harness picks the reference artefact via `OB_CHAMPION_MODEL`.

**Do not (added 7 Sep):** describe the carried-forward model as a blend (it is a single XGBoost at 50 features; the blend is the uncapped ceiling only); swap the text encoder to our DistilBERT before the prospective test; quote 0.618 without 0.583 beside it; compare a transformer against any hinge other than **v8**; call the sequence transformer "parked" without the capped-champion result; treat the champion recipe as promotable before the Feb–Apr 2026 prospective cohort; run the OB-transformer stacking script without `--ref champion_refit` when the champion is the intended reference (its default is the August 50-feature XGB).

**Next:** promote v8 (then the transformer once a serving artefact exists — ONNX/int8 if 360 rows/s becomes a constraint); scheduled per-row categorisation job keyed by transaction id; one-shot score of locked v6 at go/no-go; prospective test with two registered recipes; thin risk leaves (`debt_collection` 22 rows, `gambling_casino` 9); human blind slice on the risk tranche; 90-day Asset Report request (Plaid integration owner).

## Current state (2026-09-02) — read this first

**2 Sep programme review + Week-1 fixes landed** (`docs/review-2026-09-02-state-and-next-steps.md`; all evidence there). What changed and what you must now quote:

- **Risk bar:** `gold_transactions_risk_categories.csv` was *in* the training jsonl (77.5% merchant overlap via Tier B). `build_tuning_dataset.py` now excludes risk-gold merchants everywhere; jsonl **381,560**. Fresh hinge on it (`tfidf_linearsvm_sgd_v6_deleaked.joblib`): holdout **56.0%**, **risk bar 62.7% FAIL** (T6-bound rows only: 77.5%, n=40). **Do not quote 86.1%.** Serving dump is still v5 weights (no serving reason to switch; the fix is measurement). `data/classifier_v6_deleaked_report.md`.
- **Credits:** 24.7% of live Plaid rows (50% of GBP, 90% blank merchant) but 0.65% of the jsonl. Pipeline **debit 84.2% vs credit 57.8%**. `confusion_analysis.py` / `compare_classifier_versions.py` / `score_waterfall_pipeline.py` now print per-direction accuracy and a **credit-side bar** (`CREDIT_BAR_LEAVES`, 70%). Credit labelling tranche is the Week-2 item.
- **T4 purge:** 1,575 agent-sourced keys that tranche 4 marks `context_dependent` (`miss`, `dad`, `trading`, `new zealand`…) plus bare `credit` dropped by `build_merchant_dictionary.py` (tranche-4 downgrade guard). Dictionary **90,261**; BQ table reloaded. Test `test_t4_has_no_tranche4_context_dependent_agent_keys`.
- **Python = SQL waterfall:** `final_evaluation.our_leaf()` now fires Equifax T1/T2-gig/T3 and Plaid T1 **before** T4, as the SQL does; unmapped native → `T7_unclassified`. `src/check_waterfall_parity.py` runs the generator's own CASE bodies in BigQuery over the pipeline eval and asserts row-level agreement: **2,004/2,004**. It caught a real SQL bug: the 42 `T2_CARLOS_PACK` rules were double-escaped inside raw strings (`r'payin\\s*3'`), so 34 of them never fired in BigQuery — fixed in `_t2_carlos_when`; SQL regenerated (~204 KB). Run the parity check after any T2/T5/generator change.
- **Pipeline headline:** re-measured on **2,004** row-disjoint rows (risk rows freed by the de-leak): T1–T5 then hinge **81.8%** leaf / 87.3% general; rules-only 73.0%; **human-adjudicated v2 rows 77.7% vs LLM-drafted rows 86.1%**. Quote the split, not just the blend.
- **Experiment 3:** Equifax fetch now has an as-of filter (`PostDate <= created_at`, 189-day window; 5.5% of Equifax proposals had post-proposal rows) and the live XGB is refit on the full Plaid window. Capped headline unchanged (0.477 / 0.562); **like-for-like = Plaid-train-only 0.445 / 0.504 vs full-refit live 0.382 / 0.385** (single seed). Ladder / stress test / champion not re-run on the as-of features. 2 Sep addendum in `data/experiment3_xgb_report.md`.
- **Granularity wording:** "275, 69 and 29 indistinguishable; 17 close but may lose month-6 signal; 9 and below degrade; 4-group uplift over live not conclusive on month3" — not "flat 275→17, every rung beats live". **"69" is not a 69-leaf taxonomy or "69 of the 275 leaves in use."** It is today's model-*feature* grouping: 40 of the 275 leaves each get their own feature block (`KEY_LEAVES` in `experiment3_xgb_pipeline.py`), the other 235 fold into their 29 general categories, 40+29=69 feature groups. All 275 leaves are still classified; none are dropped. The taxonomy itself is still 275→29. **This finding is specific to the August recipe (plain XGB, rung-level months/n/amount features) and is now stale as a "how good is our best model" reference — the 7 Sep champion (below) is materially stronger and has not been re-tested across rungs.** The champion's own pre-OOT selection table shows its richer leaf-level feature view (share-of-total, per-leaf averages/CVs — not just more leaves) beating its "current"-equivalent (69-rung) view by +0.023 (month3) / +0.037 (month6) GINI at identical algorithm/depth (uncapped). **Re-run 7 Sep, capped at 50 features (`src/experiment3_champion_granularity.py`, `data/experiment3_champion_granularity_report.md`):** at a fixed feature budget the picture flips — **275 leaves is the worst rung on both targets** (month3 0.409, month6 0.506), below every coarser rung including the 4-group floor. Mechanism, not noise: at 275 leaves ~2,877 candidate columns compete for 50 slots and `credit_product_months` (2nd-strongest debt feature in the project) doesn't survive the cap on month6 at all; at 17 groups it does. The August-recipe shape reappears once capped — plateau ~69/29/17 (month6 0.548/0.542/0.542), fall below 9 (0.534→0.495). **Uncapped follow-up, same day (`experiment3_champion_granularity.py uncapped`, `data/experiment3_champion_granularity_uncapped_report.md`): splits by target.** month6 — granularity genuinely helps uncapped: 275 leaves 0.616 beats today's 69 (0.586) monotonically down to 4 groups (0.507). month3 — it does not: 275 (0.528) is marginally below today's 69, the actual peak (0.536). Longer-horizon prediction rewards fine per-leaf detail; the noisier month3 horizon doesn't. Since nobody is proposing to ship an uncapped ~2,900-feature model, the capped result (275 worst, above) stays the operationally relevant one; this just answers "does richness help at all" (yes for month6, no for month3), not "should we ship it."
- **Beyond-275 shadow pilot (2 Sep):** three supported parents (`streaming`, `marketplace_general`, `payment_intermediary`) were split into 15 frozen merchant/description buckets without changing production taxonomy. Against exact parent controls, rolling Plaid GINI deltas were **lean −0.0045 / −0.0068** and **rich −0.0020 / −0.0111** (month3 / month6); all combined 95% CIs include zero, while payment-intermediary alone is a small clear month3 loss. Development OOT is flat. **No evidence that 287 leaves improves risk GINI; keep 275 and use shadow children only.** `data/experiment3_subleaf_pilot_report.md`.

- **Transformer categoriser (started 2 Sep, Carlos's call to begin before the credit tranche):** `src/transformer/` — `build_corpus.py` (5.08M-sentence MLM corpus, 23.7% credit; 1.90M T1–T5 silver labels, 17.8% credit, holdout/risk merchants excluded), `pretrain_mlm.py` (BERT-small `google/bert_uncased_L-4_H-512_A-8` + 4,000 domain tokens, whole-word MLM; DistilBERT was 2× slower on MPS), `train_classifier.py` (leaf + general heads, hierarchy-consistency loss, `cash_flow_type` direction mask; silver pass then gold jsonl pass, class-balanced; direction-illegal labels dropped — 0.27% of gold, 3.6% of silver), `score_transformer.py` (kill criteria vs the **de-leaked** hinge; writes `data/transformer_classifier_report.md`). Sentence format `[DEBIT|CREDIT] [AMT_bucket] merchant | description`. Artefacts under `outputs/distill_models/txn_*`. **First full cycle done 2 Sep** (`data/transformer_classifier_report.md`, iter 1 in `_iter1_report.md`): holdout T6-bound **61–64% vs hinge 56.9%** (credits 41–56% vs 31%); pipeline residual flat (56–59% vs 58%); T6-bound risk slice **32–35% vs 77.5%** (n=40; overdraft arranged/unarranged, account-switch transfers, cash-advance disbursement credits). Single seed; iterations differ by 3–11pp on small cuts. Iterations 2–3 carried a stale-mask bug (buffers inherited from the silver checkpoint; fixed in `load_heads()`). **Iteration 4 (correct mask, uncapped gold pass, best epoch by Tier-B val): 4/5 kill criteria pass** — holdout T6-bound **61.7% vs 56.9%**, credits 53.1 vs 31.2, T6-bound risk 77.5 = 77.5, credit bar 28.9 vs 17.8, 1,058 rows/s; only the residual (+3pp) misses at 57.6 vs 58.0. Hybrid 50/50: 62.4 / 58.4 / 80.0 / 81.4 full pipeline. **Confirmed on 3 seeds (42/7/123): holdout T6-bound mean 62.3% vs 56.9%, residual 58.7 vs 58.0, T6-bound risk 80.8 vs 77.5, credit bar 31.8 vs 17.8, full pipeline 81.5 vs 81.3; every seed passes 4/5.** Candidate to replace T5b at that point. **3 Sep — credit tranche applied (`data/production_labels_credit_tranche.csv` 30,379 rows, Carlos 813 human_reviewed, blind-slice agreement 84.3%; `gold_credit_eval.csv` 2,000 merchant-disjoint; `gold_transactions_risk_t6bound.csv` 400; top-up 27,979; jsonl 409,417, credit share 7.4%).** Hinge **v7** on that file: credit eval **62.2 → 85.0%**, holdout credits 43.7 → 61.2%, debits unchanged (`data/classifier_v7_credit_report.md`). Transformer retrained on the same file, 3 seeds vs v7: holdout T6-bound **60.9 vs 57.2** (+3.7, CI excludes 0), credit eval **87.4 vs 85.0** (+2.4, CI excludes 0), pipeline residual 57.9 vs 59.2 (tie), **T6-bound risk 47–51% for both** (n=174; honest number, far below 70%), full pipeline 81.3 vs 81.6, general accuracy +1–6pp everywhere. **Verdict: keep hinge v7 as T5b; the credit lead was a data effect.** Reference hinge for all comparisons is now `tfidf_linearsvm_sgd_v7_credit.joblib`; serving dump still v5. Next: T6-bound risk tranche + card-issuer/overdraft rules; scaled pretraining on GCP (L4/A100 quota exists in europe-west2) if the transformer is to be pursued. `data/transformer_classifier_report.md` (iter 4) and `_iter{1,2,3}_report.md`.

- **T5 R33–R37 (3 Sep, from the 400-row T6-bound risk gold):** Amex → `charge_card_repayment`; card issuer + masked card token → `credit_card_repayment`; unarranged/unauthorised overdraft → `overdraft_unarranged`; bare `OVERDRAFT INTEREST` → `interest_charged`; arranged / `<Month> overdraft fees` / bare `Overdraft` → `overdraft_arranged`. FP-tested on the jsonl, dictionary, holdout and eval sets (`test_card_issuer_and_overdraft_t5_rules_no_labelled_false_positives`); parity 2,004/2,004. Effect with hinge v7: **T6-bound risk-leaf acc 48.3% → 58.6%** (n=174), 711-row risk bar 63.0 → 66.4%, holdout credits 61.2 → 67.0%; rules-only pipeline 73.0 → 74.2%. SQL ~213 KB.
- **Gemini 3.8 Flash (3 Sep):** drop-in vs saved 3.7 on the 2,004 unique frontier fingerprints. Holdout **83.7% vs 83.9%** (McNemar p≈0.86); slightly worse on T6-bound leftover and risk gold; **1.08 rows/s vs 3.35**. **Keep 3.7** in `production_labelling.py`. `data/gemini38_vs_37_report.md`.

**Do not (added 3 Sep):** train on merchants in `gold_credit_eval.csv` or `gold_transactions_risk_t6bound.csv` (`load_risk_merchants()` now covers both); quote the 40-row risk slice — use the 400-row T6-bound set; compare a transformer against any hinge other than v7; switch labelling from Gemini 3.7 Flash to 3.8 Flash.

**Do not (added 2 Sep):** quote the 86.1% risk bar; quote 80.5%/81.8% without the human-vs-LLM split; train on risk-gold merchants; add a T4 key tranche 4 marks `context_dependent`; hand-edit `sql/apply_crosswalk.sql` (regenerate, then run `check_waterfall_parity.py`); tune abstention or oversampling against the risk set to recover 70%.

---

## Previous current state (2026-08-27) — still accurate except where the block above overrides it

Tranche-4 100k review is **closed**. Dual-model abstains got two recovery passes, then **stop** (no third pass). Dictionary ingest and classifier retrain are done. **v5 is retired** as confirmation gold (tranche-4 novelty leak); **v6 is the replacement locked set** (Carlos labelled the 8 flags 27 Aug; `data/gold_transactions_v6_LOCKED.csv` written, **1,100** rows) **and is not scored until go/no-go.**

| Asset | State |
|---|---|
| Labels | `data/production_labels_tranche4.csv` — 100,000 merchants. **Provenance corrected 2026-08-26:** `human_reviewed` **4** (Carlos only, `reviewer_id=carlos`) / `agent_tiebreak` 53,907 / `agent_consensus` 30,479 / `agent_review` 7,413 / `context_dependent` 6,056 / `abstain_confirmed` 2,141 / `needs_review` **0**. Dictionary-eligible = human + agent_* = 91,803. Full union of tranches 1–4, not incremental. |
| T4 dictionary | `taxonomy/merchant_dictionary.csv` — **91,824** keys (27 Aug Trading 212). Matching requires `review_status=approved` and a classifiable leaf (`generate_crosswalk_sql.load_t4_dictionary`). Dropped 36 pending/unclassified (play.com, marketplace, junk strings, gold_v2 `unclassified_*`). Original seed (Tesco etc.) is **approved** — `pending` was a stale flag, not “unreviewed”. Skip `context_dependent`, abstains, T2 collision keys. Exceptions: `gamesys operation` → `gambling_unspecified`, `grab a` → `taxi_rideshare`. `creditspring` → `personal_loan_repayment`. `loans2go` → `payday_loan`. Plaid `icelandair` → `groceries` (Iceland Foods). Bare `morr` / `cd morr` → `groceries` (T2 petrol/cafe first). `barclays bank` → `mortgage` (Carlos). `admiral` → `insurance_general` (T2 `casino` → `gambling_casino`). `royal london` → `insurance_life` (`royal london pensions` stays `pension_contribution`). `ocado` → `groceries` (T2 `CENTRAL SERV` credit → `salary`). `trading 212` / `trading212` → `investment_trading`. `paypal credit` → `revolving_credit_repayment` (Pay in 3/4 stay `bnpl`). Bare `now` is **not** T4 (T2/T5 `Entertai` / `PAYPAL *NOW` → `streaming`). Do not T4 `lloyds bank`, `flex`, `water`, `mercedes-benz`, `plus`, `gem`, `home`, `city`, `orbit`, `spring`. |
| SQL | `sql/apply_crosswalk.sql` — T4 is a join to `raylo-production.credit_risk_research.merchant_dictionary_t4` (**reload after 91,824**; dataset EU). Regenerated SQL is **~200 KB**. Inline UNNEST of 91k merchants exceeded BQ's ~1 MB query limit — do not paste an old copy. Load with `python src/load_t4_dictionary_bq.py`. |
| Training | `src/build_tuning_dataset.py` reads tranche 4. `outputs/tuning_train.jsonl` = **383,066** rows (382,739 + 327 risk-guard copies of `car_lease` / DMP / revolving on non-risk-gold merchants). Holdout MD5 `7456da977a2c761119368637658232b6`. Do not reshuffle merchants. |
| Classifier dumps | **Serving head decided 2026-08-27: hinge SVM** (`tfidf_linearsvm_sgd.joblib`, v5 weights); `tfidf_logreg_v2.joblib` (also v5) is kept as rollback only. Abstention is margin-based (`decision_function` top1−top2), not `predict_proba`. v5b/v5c/v5d are `*_v5b.joblib` / `*_v5c.joblib` / `*_v5d.joblib` — **do not serve**; risk bar dropped vs v5. Frozen tranche-3: `*_v4.joblib`. Liblinear not retrained on 382k. |
| Eval | Iteration suite = `gold_v2_slm_eval_holdout.csv` + `gold_transactions_risk_categories.csv` + `confusion_analysis.py`. **v5 retired** (keep the CSV; do not score). **v6** locked file written (`data/gold_transactions_v6_LOCKED.csv`, **1,100** rows). Carlos labelled the 8 flags 27 Aug. Scorers call `eval_sets.refuse_confirmation_eval()`. Scored once at go/no-go. Pipeline remeasure 27 Aug (after R31/R32 + PayPal Credit T4): T1–T5 then hinge **80.5%** leaf (n=1,884); residual **500**. T5 R31 (StepChange) **16/16**. T5b Plaid gold T6 residual **231**; holdout T6-bound hinge **57.7%**. **Frontier framing (27 Aug, full labelling prompt, not for runtime):** holdout leaf hinge **53.9%** / Gemini 3.7 Flash **83.9%** / Sonnet 5 **79.1%**; leftover 59.2 / **73.0** / 67.4; T1–T5 then model 80.5 / **84.2** / 82.7. `data/frontier_vs_classifier_report.md`. T6 residual packs 1+2 labelled and in `tuning_leaf_topup.csv` (**1,426** rows; +556). Base jsonl after ingest **382,739**; with risk-guard copies **383,066**. v5b retrain (on 382,739): hinge holdout **+0.7pp**, risk bar **86.1% → 79.8%**. v5c risk-guard (383,066): holdout **55.2%**, `car_lease` **20/20**, risk bar **79.0%** — **serving stays v5.** Residual+proto hinge (drop T1–T5 jsonl rows, keep ≤20 head rows/leaf): **hurts** holdout T6-bound 57.7%→36.0% and pipeline residual 60.1%→38.0%. Fine-tuned MiniLM (1 epoch): leftover **17.5%** vs hinge **57.7%**. T6 stays **PFC `credit_category_detailed`** (list `category`/`category_path` 15.7% vs 18.6% leaf on T6-bound gold). `data/residual_prototype_train_report.md` · `data/encoder_finetune_minilm_report.md` · `data/plaid_legacy_category_t6_report.md`. |

**Plaid live coverage (remeasured 2026-08-26, 91,822 dictionary):** T4 exact merchant join **56.5%** of 4,279,707 rows (2,416,625; **89.0%** of filled-merchant volume; 36.6% blank merchant). 20% sample waterfall: T1–T4 **57.0%**, T1–T5 **57.7%**, T6 42.3%. Same day earlier: 91k keys T4 **52.1%** / T1–T4 **53.2%**; 91,730 keys T4 **55.9%**.

**Equifax:** T4 **37.4%** full-pop (was 34.8%). 2% sample T1–T4 **40.8%**. Unmatched *filled* vendors are only **4.4%** of Equifax volume (5,908 of 6,518 distinct vendors); **58.2% blank vendor**. A 10k Equifax labelling tranche is **not worth it** — “10k residual rows” is one vendor (`rainbow riches` with a non-breaking space, already in T4 under the clean key). Live traffic is Plaid; Equifax is a dead dump. If Equifax history still matters, a small alias pass (nbsp/punct fold + top ~100–500 Equifax names → existing T4 leaves), not another LLM tranche.

**Classifier v5 (tranche-4 labels, same TF-IDF + SGD, 50 epochs).** Scored vs frozen v4 weights on the *current* holdout/risk files. Full write-up: `data/classifier_v5_retrain_report.md`.

| | logreg v4 | logreg v5 | hinge SVM v5 |
|---|---|---|---|
| Holdout leaf / general (1,055, merchant-disjoint) | 37.2 / 42.9 | 50.9 / 59.0 | **52.8 / 60.3** |
| Risk gold leaf / general (711, held out of training) | 67.2 / 76.2 | 76.8 / 82.1 | **80.6 / 85.5** |
| Risk-category bar (n=619, ≥70%) | 74.0 OK | 81.4 OK | **86.1 OK** |

Hinge beats logreg on argmax **and** on leaf F1 (holdout weighted 51.5% vs 49.0%; risk-bar macro F1 86.9% vs 83.4%). It has no `predict_proba` (margin gate only). Parent-level macro F1 slightly favours logreg because hinge zeros a few thin classes (`fees_charges`, `salary`). Original bake-off kept logreg for auditability + probabilities; **decided 2026-08-27: hinge SVM is the serving head.** The probability's two jobs are both settled empirically — gated fallback to T6 is measured harmful at every threshold (`data/t5b_residual_gate_report.md`), and abstain-to-unclassified works on the hinge margin. Logreg dump kept as rollback; Platt-scale the margins if calibrated confidence is ever needed. Full pack: `data/classifier_v5_head_metrics_report.md`. Liblinear LinearSVC last time (25 Aug, ~167k rows) finished in **40s** as parallel OvR, ranked *below* hinge on every metric (T6 residual 73.1 vs hinge 79.0; risk residual bar 68.8 FAIL vs hinge 75.3 OK) — not worth retraining.

**29-way general head (same jsonl, 26 Aug):** hinge parent **63.4%** holdout vs leaf-rollup **60.3%**; **83.4% vs 85.5%** on risk gold (high-cost distress parent 92.4% → 81.9%). Fresh TF-IDF matched frozen. **Do not cascade.** `data/classifier_general_bakeoff_report.md`.

**Do not:** ingest collisions/abstains/`unclassified_*` into T4; dictionary `cd glasgow` / Drayton Court / Fountain Hotel / bare `now` / `lloyds bank`; treat FPS as `transfer_p2p` by default; resume `pack_abstain3_*`; score locked v5 or v6; serve `*_v5b.joblib` or `*_v5c.joblib` or `*_v5d.joblib`; switch T6 from PFC detailed to list `category`/`category_path`; quote 47.8% / 18,825 / “~40% T1–T4” as current; call agent labels `human_reviewed`; overwrite `production_predictions_opus.csv` (write `production_predictions_opus_filled.csv`); paste the old inline-UNNEST SQL into BigQuery.

**Key reports:** `data/frontier_vs_classifier_report.md` (27 Aug: Gemini/Sonnet vs serving hinge on holdout/risk/pipeline; framing only) · `data/classifier_v5_retrain_report.md` (26 Aug retrain + hinge + Equifax no) · `data/classifier_v5_head_metrics_report.md` (logreg vs hinge F1 / per-class; hinge wins leaf + risk bar) · `data/classifier_general_bakeoff_report.md` (29-way general vs leaf rollup; holdout +3.1pp parent, risk −2.1pp; do not cascade yet) · `data/waterfall_pipeline_report.md` (one row-disjoint set, n=1,884; T1–T5 then hinge **80.4%**; residual 516 hinge 60.1% vs T6 26.2%) · `data/t5b_residual_gate_report.md` (27 Aug remeasure: Plaid residual 231, holdout hinge 57.7%; always-ML still beats T6) · `data/residual_prototype_train_report.md` (27 Aug: drop T4-covered train rows **hurts** residual ~22pp) · `data/encoder_finetune_minilm_report.md` (CLS pooling, leftover 17.5%) · `data/encoder_finetune_minilm_meanpool_report.md` (pooling fix: holdout 52.1% vs hinge 53.8%; leftover and risk still lose) · `data/classifier_v5b_retrain_report.md` (T6 top-up jsonl; do not serve) · `data/classifier_v5c_retrain_report.md` (risk-guard oversample; lease recovered, bar still 79.0%) · `data/classifier_v5d_retrain_report.md` (hinge-only same jsonl; holdout 56.6%, bar 82.2%) · `data/plaid_legacy_category_t6_report.md` (list `category` vs PFC detailed; keep PFC) · `data/t6_residual_topup_fetch.md` (pack 1) · `data/t6_residual_topup2_fetch.md` (142 keyword-vetted, not Plaid-native) · `data/experiment3_xgb_report.md` (27 Aug feature rebuild + XGBoost; headline = 50-feature cap: month3 OOT **0.477** / month6 **0.564** vs live **XGB** 0.403 / 0.386 — the live OB model is XGBoost, not the logistic analog; uncapped 0.478 / 0.560 as reference) · `data/experiment3_iv_report.md` (24 Aug logistic analog; unsigned 0.308 vs 0.328; historical) · `data/gold_v4_scoring_report.md` (Option 1 confirmed).

Review conventions (Creditspring, 32 Red, Lime/Voi, Morr+town, payday = HCSTC only, …) still live in `AGENT_RULES.md` (review itself is closed).

---

## 1. What problem this solves

Raylo's live Open Banking risk model reads **Plaid's category names directly**. Plaid shipped a new taxonomy version (PFC v2, 3 Dec 2025) months after Raylo went live on Plaid (Aug 2025); the same transaction can be relabelled between versions. We need a taxonomy **Raylo owns**, with provider categories as evidence rather than as the definition.

## 2. Data landscape

Two providers. **AccountScore is Equifax** (Equifax acquired them; same categorisation engine).

| | Equifax | Plaid |
|---|---|---|
| Table | `raylo-production.equifax_data.open_banking_full_dump` (+ `..._with_matches`) | `raylo-production.dbt_production.credit_plaid_open_banking_transactions` |
| Rows | 73,246,476 | 4,279,707 |
| Period | Jul 2022 – Sep 2025 | Aug 2025 – present |
| Status | **DEAD** — one-time Oct 2025 batch | **LIVE** |
| History per proposal | 189 days avg | 90 days (hard cap) |
| Merchant field | `VendorDescription`, 41.8% filled, **6,518 distinct (curated/resolved)** | `merchant_name`, 63.4% filled, **212,300 distinct (raw text)** |

BigQuery project is always `raylo-production`. Access is read-only — write experiment outputs to a scratch dataset (e.g. `credit_risk_research`), never `dbt_production`.

### Critical schema facts (all verified — do not re-derive)

- **Equifax `TransactionTypeId`: 1 = credit, 2 = debit.** `Amount` is unsigned.
- **Plaid `amount`: negative = credit (money in), positive = debit.** Verified via `INCOME_SALARY` being 100% negative.
- **Equifax's two category fields are NOT parent/child.** 222 of 255 subcategories (87%) appear under multiple primaries, covering 98% of volume. `SubCategoryDescription` = WHAT (purpose), `PrimaryCategoryDescription` = HOW (mechanism). Example: `General Groceries` appears under Shopping (5.4M), Transfers/Other (79k), Refund (17.5k) and **Identified Salary (16.4k — salary *from* a supermarket employer)**.
- **Plaid `payment_method` and `reference_number` are 0% populated** — extracted in `intermediate_credit_plaid_transactions` but Plaid never returns them for UK Asset Reports. Don't plan around them. `payment_processor` is 1.35%, `location_country` 0%.
- **Plaid `confidence_level` is available from the API but not ingested.** Worth adding.
- Outcomes: `raylo-production.dbt_production.ds_first_order_proposal_pia_metrics`, join on `financial_proposal_id`. Equifax cohort = 37,404 proposals with outcomes; 4,006 bads at `month3_1plus_pia`, 7,441 at `month12_1plus_pia`, 5,474 at `month12_3plus_pia`. Exclude `final_matched_on = 'name_time'` (fuzzy, untrustworthy).

## 3. The taxonomy

`taxonomy/taxonomy.csv` — **275 detailed leaves → 29 general categories** (274 until the 2026-08-19 marketplace split — see §11 conventions). Verified: 0 uncovered provider values across all 255 Equifax subs, 47 Equifax primaries, 91 Plaid detailed categories.

Structure: `detailed_category` is the source of truth; `general_category` is a **strict rollup** (one parent per leaf — stricter than Equifax, which isn't a tree). Cross-cutting concerns are **orthogonal dimensions**, not hierarchy levels, because they aren't tree-shaped:

`necessity` · `cash_flow_type` · `is_debt_related` · `is_priority_debt` · `is_age_restricted` · `risk_flag`

**Do not "simplify" these** — each exists for a measured reason:

- `is_debt_related` is orthogonal to `necessity` so rent and mortgage are both `essential` while only mortgage is debt. Collapsing them makes `essential_spend_ratio` exclude mortgage for homeowners but include rent for renters — a tenure-based comparability distortion inside a credit-decision feature, with fair-lending implications.
- `is_priority_debt` yields the **strongest single feature found** (IV 0.171).
- `mixed_basket` exists because category alone genuinely can't determine necessity for mixed-goods retailers. Forcing a guess injects false precision.
- **Gambling subtypes must never be aggregated.** Combined `gambling_months` IV 0.0053 vs `Lottery` alone 0.0498. There's a test guarding this.

## 4. The categorisation strategy: precedence waterfall

Every transaction resolves at the highest tier that fires, and **records which tier** in `resolution_tier`. Provenance is mandatory — "resolved by merchant match on Tesco" is defensible in a fair-lending review; "model predicted 0.87" is much weaker.

| Tier | Mechanism | Status |
|---|---|---|
| T1 | Direction-dependent overrides | in `sql/apply_crosswalk.sql` |
| T2 | Compound rules (gig income; narrative-disambiguated merchant collisions) | in `sql/apply_crosswalk.sql` |
| T3 | **Mechanism-override primaries** | in `sql/apply_crosswalk.sql` |
| T4 | Merchant dictionary | `taxonomy/merchant_dictionary.csv` — wired in `sql/apply_crosswalk.sql` 2026-08-20 |
| T5 | Deterministic regex rules | `taxonomy/rules/deterministic_rules.csv` — wired in `sql/apply_crosswalk.sql` 2026-08-20 (R13/rent disabled via an `enabled` column, not a string flag) |
| T6 | Provider crosswalk | in `sql/apply_crosswalk.sql` |
| T7 | `unclassified` | explicit, monitored |

**T3 (mechanism override) was discovered by running the crosswalk on real data** and is easy to miss: 13 Equifax primaries (`Identified Salary`, `Refund`, `Benefits`, `Welfare`, `Pension Payout`, `Tax Refund`, `Cash Back`, `Cash Machine`, `Cash Deposit`, `Interest`, `Interests and Dividends`, `Balance Transfers`, `Adjustments`) determine the leaf **regardless of merchant**. Without it, `Identified Salary | General Groceries` wrongly resolves to `groceries`. 4.10% of volume.

**The Tesco provider-entity collisions (2026-08-23/24) are the same class of bug as T3, one level down — a provider's own entity resolution, not ours, erases the disambiguating information.** Plaid's `merchant_name` field collapses Tesco Bank, Tesco Petrol, and Tesco Phone Insurance (`TESCOPHONEINS.`) onto bare `Tesco`, identical to the supermarket's string, so the T4 dictionary's `tesco -> groceries` match (98.5% correct for that merchant string overall) silently mislabelled them. Three T2 narrative checks fire **before** T4 (`tesco bank` → `financial_institution_unspecified`, `petrol`/`pfs` → `fuel`, `tescophoneins` → `insurance_other`). Tesco Mobile is unaffected — Plaid keeps it as its own merchant string. **These live in `src/generate_crosswalk_sql.py` (`T2_TESCO_COLLISIONS`), not as a hand-patch on the generated SQL** — regenerating the SQL on 2026-08-24 dropped a hand-patched version; a test now guards this. Structurally the same shape as Marks & Spencer / M&S Bank, but that case is resolved on the Equifax side by Equifax's own vendor field keeping the two entities as different strings; Plaid does not.

**HMRC is the same collision (2026-08-24).** T4's `hmrc` / `hm revenue and customs` → `tax_payment` is the right debit default (Self Assessment, Shipley, Cumbernauld). Plaid also lands Child Benefit, tax credits, and SA *refunds* on those strings, so T4 was labelling Child Benefit credits as tax. Equifax already splits the product (`Child Benefits` → `benefits_state`). T2 (`T2_HMRC_COLLISIONS`) fires **before** T4 on credits only: `child benefit(s)` → `benefits_state`, work-and-child / working / child tax credit → `benefits_state`, `HMRC SA` / `gov.uk sa` / self-assess → `tax_refund`. Do not retarget T4 to `benefits_state` (that would mislabel tax bills) and do not put this in T5 (T4 would still win). Equifax sometimes parks Child Maintenance on vendor `Child Benefits`; T2 `DWPCMS` / `CMSGB2012` → `income_other_unspecified` (same leaf as R15).

**Further T2 / T1 from gold v3/v4 review (2026-08-24).** In-store ATM/LINK (`tesco`, `one stop`, `post office`, …) → `cash_withdrawal` / `cash_deposit`; grocer petrol in the *description* on Co-op / Sainsbury's / Asda (Tesco petrol T2 already existed); `\bkfc\b` in merchant or narrative on a **debit** → `takeaway` (Plaid collapses KFC onto Burton / Welcome Break / Klarna); TikTok Shop, Sky Protect, Asda Mobile/Living, Vodafone Device (`device` substring, so `VODAFONE LTDDEVICE` fires), Bolt/StackBlitz. Tesco Cafe: `tesco` + `caf[eé]` in the narrative → `restaurant_cafe` (before petrol). Amazon + `prime\s*video` debit → `streaming` (T4 `amazon` is marketplace). Credit + `\brefund(ed)?\b` after T1 gambling, before T4 → `refund_received`. Credit + returned DD / direct-debit reversal / `reversal of` → `returned_payment` (must precede T4). T5 R23 (credit, description) catches truncated DWP/HMRC benefit narratives. Do not T4 bare `royal london` (`royal london pensions` is already `pension_contribution`). Bookmaker **credits**: T1 `d.leaf IN gambling subtypes AND credit` → `gambling_unspecified`, because Plaid T1 only fires when Plaid's own category is gambling (salary-mislabeled Sky Bet credits used to lose to T4). Python `our_leaf` uses `match_t2()` from the generator so eval cannot drift.

**Morrisons truncation (2026-08-24; T4 catch 2026-08-25).** Plaid shortens `MORRISONS` to `Morr` + town (`Morr Paignton`). T4 cannot prefix-match unknown towns. T5 R21 on **merchant**, debit, `\bmorr\b`, exclude `petrol|pfs|fuel|caf[eé]`. Does not match `morrisons`, `morriston hospital`, `morrison supply`. `morrisons petrol` stays T4 fuel. Do not map bare `morr` as restaurant — gold v3/v4 `Morr *` + town is groceries. After tranche-4 ingest, **`morr paignton` is an exact T4 key**, so eval expects `T4_dictionary` not `T5_R21` for that string; R21 still exists for other Morr+town truncations not in the dictionary. Same-day T4 retargets (24 Aug): `depop` marketplace_amazon → marketplace_general, `lime` taxi_rideshare → bicycle, `tescophoneins.` (trailing period) → insurance_other, truncated off-licence / Goldwire / Ridgewood / Stagecoach Services, and `morr wetherby` / `morr catcliffe` → groceries so T4 cannot keep the wrong leaves.

**Sheriff court + truncated-merchant collisions (2026-08-25).** HMCTS sheriff-court taps are `government_services`, not `legal_services`. T5 R22 `\bsheriff\s+court\b` on the **description** (debit), same shape as R12 council tax — Plaid often collapses the till onto a truncated merchant (`cd glasgow`), so a T4 key cannot be the catch-all; do not dictionary `cd glasgow`. **T5 R31** (27 Aug): `\bstep[\s-]*change\b` on the description, debit → `debt_management_plan`. T4 already has `stepchange` / `step change`; Plaid often leaves merchant blank. Returned StepChange credits stay T2. Rail vs court on that string is T2. The 41 human-reviewed same-string splits (Glasgow Central, IPS parking, Subway-on-Glossop, …) plus the follow-up 19 (`egg` / `jasmine` / `paymy.vet` / …) live in `taxonomy/rules/t2_entity_collisions.csv` and fire in `match_t2()` / generated SQL **before T4**. Invented review-pack leaves were mapped onto the closed taxonomy (`parking` → `car_parking`, `p2p_transfer` → `transfer_p2p`, `clothing_retail` → `clothing_general`, `medical` → `health_other`, `charity` → `charitable_donation`, `travel_retail` → `airport_spend`, `coffee_shop` / `coffee_shop_cafe` → `restaurant_cafe`, `off_licence` → `alcohol_beer_spirits`, `vape_shop` → `vaping`, `garden_centre` → `garden`, `travel_lodging` → `accommodation`, `home_energy` → `energy`, `pet_grooming` → `pet_other`, `public_transport_bus` → `public_transport_rail_coach`, `newsagent` → `convenience_store`). `the drayton court` / `fountain hotel` are amount-only pub vs lodging on the **same** narrative — T2 cannot split them; they stay `context_dependent`. Those collision merchants must not ingest to T4 (`gamesys operation` → `gambling_unspecified` and `grab a` → `taxi_rideshare` are the two single-leaf exceptions).

**Any future "provider entity collision" bug of this shape belongs in T2 (compound: merchant + narrative), not T5 — T5 rules run after the T4 dictionary and would never fire.** Exception: a **description-only** pattern that must fire even when the merchant string is an unpredictable truncation (sheriff court, council tax, payday narrative) belongs in T5.

### The rule that matters most

**Where the merchant dictionary matches, it overrides both providers' categories.** This is not a coverage optimisation — it's the only thing that makes the taxonomy provider-independent.

Measured: for the 2,307 merchants both providers cover, applying the two crosswalks gives **different leaves for 72.2% of merchants (45.2% of volume)**. 925 are genuine conflicts between two specific leaves, e.g.:

| Merchant | Equifax → | Plaid → | Correct |
|---|---|---|---|
| uber eats | `takeaway` | `restaurant_cafe` | `takeaway` |
| marks & spencer | `credit_card_repayment` | `department_store` | `department_store` (Equifax matched M&S Bank) |
| vanquis bank | `credit_card_repayment` | `personal_loan_repayment` | `credit_card_repayment` |
| sky | `broadband_tv_phone` | `mobile_phone_contract` | `broadband_tv_phone` |

A crosswalk-only pipeline propagates these silently — both outputs are valid leaf names, nothing fails a test. It also poisons the ML plan, since training labels come from Equifax and inference runs on Plaid.

## 5. Coverage reality — read before estimating anything

**Equifax:** 60.96% purpose-known via subcategory, +4.80% via WHAT-carrying primaries, 28.08% mechanism-only, 6.15% nothing. So **65.8% well-resolved, 34.2% needs the merchant/ML layers.**

**Plaid:** 100% of transactions map to *a* leaf, but **50.6% land on coarse leaves** — `unclassified_transfer` (23.8%), `savings_transfer` (9.7%), `gambling_unspecified` (4.1%), `transport_other` (3.2%), `bnpl` (3.2%), `entertainment_other` (2.1%). **203 of 275 leaves have no Plaid source at all**, so `digital_subscriptions_services` gets zero Plaid volume.

**The merchant dictionary will NOT rescue Plaid the way it does Equifax.** Measured hard ceiling: Equifax's *entire* 6,518-vendor list matches only **41.3% of Plaid merchant volume** (2,315 of 212,300 strings). Our 321-entry dictionary gets 88.2% on Equifax but **47.8% on Plaid**; normalisation lifted that only to 48.8%.

> **Dictionary size and live hit-rate — read before quoting.** The 47.8% / 88.2% figures in the paragraph above are the *321-entry* measurement and must not be quoted as current. `taxonomy/merchant_dictionary.csv` holds **91,527** entries (26 Aug n≥50 T4-miss aliases). **Re-measured 2026-08-26 on the live Plaid table (91,173 keys, before this pack):** T4 exact `LOWER(TRIM(merchant_name))` join = **52.1% of all Plaid rows** (2,231,492 / 4,279,707); 82.2% of filled-merchant volume; 36.6% blank merchant (T4 cannot help). 20% sample waterfall: T1–T4 **53.2%**, T1–T5 **53.9%**, T6 46.1%. Equifax T4 = **37.4%** of 73.2M (610 of 6,518 vendors). Dated milestone records below still say 321, 535, 18,825, 30.5%, 39.1%, ~41.4% — those are accurate *as history*. BQ T4 reloaded at 91,527; live hit-rate not remeasured.

Reason: the two merchant fields are **different kinds of data**. Equifax emits a *resolved entity* from a controlled list. Plaid emits *lightly cleaned raw text*, including counterparty names on transfers. Breakdown of unmatched Plaid merchant volume:

| Pattern | Distinct | Txns | % |
|---|---|---|---|
| Genuine long-tail merchants | 135,820 | 1,765,472 | 65.0% |
| Two-word names (business vs person — ambiguous) | 65,350 | 610,420 | 22.5% |
| Short tokens (≤4 chars) | 3,222 | 251,827 | 9.3% |
| `initial + surname` | 3,049 | 57,971 | 2.1% |
| Personal titles | 4,848 | 27,557 | 1.0% |

**Implication: merchant *resolution* is a text-classification problem, not a lookup problem.** ML is core, not a mop-up.

## 6. Gating experiment — RESOLVED 2026-08-19: GREEN LIGHT (96.1% corrected accuracy)

**Human adjudication of the 376 consensus disputes completed 2026-08-19** (`data/gating_adjudication_completed.xlsx`): 216 llm_correct, 47 both_acceptable, 56 equifax_correct, 5 both_wrong, 49 context_dependent, 3 unsure. **Corrected consensus accuracy: 96.1% leaf-level (bounds 95.9–96.1%), 98.2% general-level — above the ≥95% green-light threshold.** By-products: `data/gating_dictionary_additions.csv` (195 human-approved T4 entries — merge pending, note `build_merchant_dictionary.py` regenerates the CSV so wire additions into the build, don't hand-edit the generated file), 49 context-dependent merchants documented as T1/T2 rule candidates (in `data/gating_adjudication_report.md` — revolut/monzo direction rules, provider-entity splits like marks & spencer and leon), and **`data/gold_merchant_labels.csv` — 1,563 merchants with human-verified labels, THE fair eval set for all classifier work** (never evaluate against raw Equifax labels; that metric is biased — see below).

Next: the four-field categoriser (name + description + amount + direction). Plan agreed with Carlos: (1) ML baseline trained on Equifax's 44.7M raw-`Description` rows, (2) context-enriched LLM labelling (per-string aggregates: top narratives, direction split, Plaid native category — Plaid has `transaction_name`/`original_description`), (3) compare both on the gold set, combine (LLM labels the head offline, classifier serves the tail at runtime, dictionary above both). LLM per-transaction at runtime remains forbidden.

### Original experiment record (methodology + caveats)

**Ran twice** (Haiku 4.5 first, then a methodology review + Sonnet 5 comparison the same day). `src/gating_experiment.py` (`fetch` / `label [haiku|sonnet]` / `score` / `run`). LLM-labels the 2,307 merchant strings present in both providers (taxonomy + curated-merchant examples cached in the system prompt, forced tool-call with a closed 274-value enum + echoed `index`, confidence + explicit abstain, per-batch retry of silently-dropped items, raw responses persisted to `outputs/gating_raw/`). Scored against Equifax's category-derived leaf. Full results: `outputs/gating_report.md`.

**Headline numbers (non-abstained):** Haiku 66.8% leaf / 86.7% general-category; Sonnet 5 68.8% leaf / 87.9% general-category. Sonnet is only ~2pp better — model capability is not the binding constraint. Sonnet's stated confidence is far better calibrated (91% accuracy at conf ≥0.9, monotonically declining to 38% below 0.5; Haiku's mid-band is unreliable).

**The critical measurement caveat discovered in review: the "ground truth" is Equifax's own merchant dictionary, not independent truth.** Modal-category share per shared merchant is ~100% (median 1.00; only 2% of merchants below 0.90), i.e. Equifax assigns one category per vendor — so the experiment measures "can an LLM reproduce Equifax's dictionary conventions". Those conventions demonstrably differ from our taxonomy's intent: on mismatches checkable against our own curated dictionary, our dictionary sides with the *LLM* ~75% of the time (Netflix→streaming not broadband, Boots→pharmacy, eBay→marketplace, B&M→discount_store…). ~60% of all leaf "errors" are within the correct general category.

**Cross-model consensus (the decisive artifact):** where both models independently agree (82% of jointly-attempted strings, 96% of test-set Plaid volume), agreement with the Equifax label is 76.7% at leaf / 91.6% at general level; the **376 rows where both models agree with each other but not with Equifax** are exported to `outputs/gating_candidate_gt_errors.csv` sorted by Plaid volume. **Human adjudication of those rows (~1–2 hours) settles the verdict**: if most are Equifax-convention artifacts (as the dictionary cross-check suggests), true LLM accuracy is ~90% leaf-level and the LLM route is viable; if most are genuine LLM errors, it's a firm stop. Two-model-consensus + Sonnet-confidence≥0.9 already scores 91.3% *even against the noisy measuring stick* — a high-precision subset exists regardless.

**Known-good facts for whichever route wins:**
- The Equifax dump's `Description` column is genuine raw bank-statement narrative ("3765 16JAN23 CD TESCO STORES 3213 STEVENAGE GB") paired with the resolved vendor + category — so the "train on 44.7M Equifax transactions" arm has raw-text→label pairs comparable to Plaid input, not just the 6,518 clean vendor names. Verified 2026-08-18.
- A caution about the original gating framing: "agreement with Equifax" structurally favours the train-on-Equifax arm (a classifier distilled from Equifax labels reproduces Equifax conventions by construction — including the ones our curated dictionary overrides). Whichever classifier is built, T4 (curated dictionary) must stay above it in the waterfall.
- Models silently drop items from long structured-output arrays (Sonnet dropped ~17/100 per batch before the fix; zero after adding echoed `index` + one-result-per-input instruction + retry loop). Any future batch-labelling must keep those safeguards.

### Cost model (for the LLM route, if adjudication green-lights it)

Classify **distinct merchant strings, not transactions.** 209,985 unmatched strings, ~100 per batched call, taxonomy in a cached system prompt → ~2,100 calls, ~$20, halved with the Batch API. Volume curve for prioritisation: top 1k strings = 44.9% of unmatched volume, top 5k = 58.4%, top 10k = 65.9%, top 50k = 84.8%; 101,357 singletons = 6.4%. Use two-model consensus + confidence gating (measured: consensus+conf≥0.9 → 91.3% vs even the noisy GT); route non-consensus/low-confidence strings to `unclassified_other` or human review, never force a guess.

**Never run an LLM per-transaction at runtime.** This applies regardless of the gating outcome.

## 6a. Frontier LLM benchmark, prompt-engineering fix, and fine-tuning experiments (2026-08-22/23)

All numbers below are scored against `data/gold_v2_slm_eval_holdout.csv` (1,055 real transactions, merchant-disjoint from all training data) — the standard SLM/LLM benchmark set. Scoring/comparison scripts live in the tracked `benchmarks/` directory (moved 2026-08-23 from the gitignored `outputs/mlx_full_run/` for reproducibility — see `benchmarks/README.md`); large model artefacts (fine-tuned adapter weights, checkpoint scans) remain in `outputs/mlx_full_run/`, regenerable via the fine-tuning runbook.

**Prompt bug found and fixed.** The labelling system prompt had silently grown to 2.39M characters: `load_example_notes()` in `src/gating_experiment.py` was including a `"LLM-consensus label, tier=..."` boilerplate string as if it were a human-authored disambiguation note (root cause: a bulk dictionary-wiring commit). Fixed by excluding that prefix (restores the genuine 375 notes) and added a hard guardrail — `load_example_notes()` now raises if the note count leaves the 300–600 band, so a future bulk-add can't silently re-inflate the prompt.

**Prompt-compression was tested and rejected — keep the full worked-example set.** Four alternative designs were measured against the full-375-example baseline on Haiku/Sonnet/Opus, controlling for leakage (excluding rows whose merchant appears verbatim in the examples) and for note-coverage (splitting by leaves with zero example coverage, to separate genuine reasoning transfer from lookup-table memorisation):
1. Full 375 examples (baseline) — but carrying a genuine bug: `TAIL_ADDENDUM` told models to default personal-name transfers to `transfer_p2p` even when the narrative had an explicit debt keyword (LOAN/LEND/OWE/DEBT/IOU).
2. 7 synthesized general principles, no examples: 4–4.5pp WORSE on all three models, and the gap widens (Opus +10pp) on categories with zero note coverage — proof the examples teach transferable reasoning, not just lookup.
3. Principles + a curated 75-example subset: recovered only 1–2.5pp of the gap.
4. Principles + the full 375 examples: still 1.8–2.6pp below plain baseline — principles text is mildly dilutive once full-breadth examples are already present.
5. **Adopted**: just the one verified bugfix + the full 375 examples, no principles text — ties variant 1 within noise while fixing the real bug. Full history is in `src/build_tail_eval.py`'s `TAIL_ADDENDUM` comment.

Conclusion: prompt length (84,348 chars) is not itself the risk — prompt caching (`cache_control` in `production_labelling.py`) neutralises most of the cost, and no instruction-following degradation was measured at this length. The real risk is *ungoverned* growth, now caught by the 300–600 note-count guardrail. **Do not re-attempt principle-based compression** without re-running this same leakage-and-coverage-adjusted test — it has failed twice at different compression levels.

**Full model comparison, final production prompt** (Haiku/Sonnet/Opus/Gemini 3.7 all scored on the identical 84,348-char prompt):

| Model | Leaf | General | Throughput |
|---|---|---|---|
| Gemini 3.7 Flash (untuned, 3-run avg) | 84.2% ± 0.15pp | 90.9% ± 0.12pp | ~3.1–3.9 rows/sec |
| Claude Opus 5 | 80.6–81.7% | 87.6–88.5% | ~1.2–3.8 rows/sec |
| Claude Sonnet 5 | 76.8–76.9% | 83.0–84.1% | ~1.3–4.7 rows/sec |
| Claude Haiku 4.5 | 72.9–73.7% | 81.1–81.6% | ~7.0 rows/sec |
| Tuned Gemini 2.5 Flash (fine-tuned endpoint, no prompt examples) | 53.9% | 61.6% | 20.2 rows/sec, 97.6% in-vocab |
| Local fine-tuned Gemma SLM (ckpt 38000, direct generation, closed vocab learned via fine-tune) | 50.0% | 59.5% | — |
| Local fine-tuned SLM + full taxonomy in context + constrained decoding | 39.5% | 55.0% | 3.1 rows/sec |
| TF-IDF + logistic regression (21 Aug dump; serving file now holds v5 weights) | 32.0% | 37.6% | — |
| Sentence-embedding (MiniLM) + logistic regression, same training data | 27.6% | 32.5% | — |
| Local vanilla Gemma (no fine-tune) + full taxonomy in context + constrained decoding | 17.7% | 36.7% | 3.65 rows/sec |
| Vanilla Gemma, taxonomy as text hint only (no constrained decoding) | 3.5% | 8.2% | 17.5% in-vocab |
| Vanilla Gemma, no taxonomy context at all | 0.0% | 0.0% | 0% in-vocab |

The TF-IDF 32.0% row is the **21 August** dump on this same holdout. After tranche-4 retrain (26 Aug) the serving logreg is **50.9%** leaf / 59.0% general and SGD hinge is **52.8% / 60.3%** — see the current-state table and `data/classifier_v5_retrain_report.md`. The SLM 50.0% row has **not** been re-run on the 382k jsonl.

**Genuine, load-bearing negative-interaction finding**: giving the *fine-tuned* local SLM the full taxonomy in its context window (plus constrained decoding to force a valid leaf) makes it WORSE (50.0%→39.5% leaf) — the fine-tune already learned direct merchant→leaf mappings and the extra list appears to distract it. The same technique helps the *vanilla* (non-fine-tuned) model enormously (0–3.5%→17.7%), because it never learned the taxonomy any other way. **Implication: a fine-tuned-SLM deployment should NOT show the full taxonomy at inference — closed-vocabulary direct generation from the fine-tune alone is both faster and more accurate.**

**Gemini's temperature=0 is not fully deterministic** (unlike the local MLX model's provably-deterministic greedy decode) — validated empirically rather than assumed, per Carlos's explicit request. Two identical temp=0 calls against Gemini 3.7 Flash differed on 5/40 rows (12.5%). However, **the 3-run aggregate benchmark above is stable** (leaf SD ≈0.15pp, general SD ≈0.12pp across 3 full 1,055-row runs) — row-level flips appear to roughly balance correct↔wrong, so single-run benchmark numbers for this model are trustworthy at the aggregate level even though individual predictions aren't.

**Platform facts (verified, don't re-derive):** Opus 5 / Sonnet 5 / Opus 4.8 all reject the `temperature` parameter (400 error, "deprecated for this model") — only Haiku 4.5 and older Sonnet 4.6/Opus 4.6 accept it. Gemini's `response_schema` rejects string enums above ~100–150 values (workaround: numbered index + bounded integer, mapped back locally). Gemini 3.7 Flash is only available via the direct Gemini Developer API (`vertexai=False` + explicit `api_key`) in this project/region, not Vertex AI — a stray un-stopped background process using the wrong (Vertex) config previously caused confusing 404s while debugging this; always verify no stale background job is still writing to a shared log before trusting its errors. Gemini 2.5's "thinking" can silently consume the whole output-token budget unless `thinking_config=ThinkingConfig(thinking_budget=0)` is set.

**Gemini 2.5 Flash fine-tuning (Vertex AI supervised tuning) works end-to-end and is essentially free.** Smoke test (15 rows) and full run (164,445 rows, `outputs/mlx_full_run/gemini_full_train.jsonl`) both SUCCEEDED (72.1min / 80.7min). Full run: 17,001,755 billable training tokens × ~$0.005/1M ≈ **$0.085 total**. Endpoint scored 53.9%/61.6% (table above) — genuine learned behaviour, but well behind the frontier models and even behind the un-tuned local fine-tune's direct-generation mode. Config notes: no `response_schema` at inference on a tuned model (Google's documented caveat — bake format into training data instead, validate post-hoc with an `unclassified_other` fallback); `thinking_budget=0`.

**Labelling-architecture decision (Option 1 — implemented 2026-08-23).** Gemini 3.7 Flash replaced Haiku in `PRODUCTION_MODELS` (`src/production_labelling.py`): Gemini + Sonnet consensus, Opus tiebreak. `run_labelling()` dispatches Anthropic vs Gemini backends; `apply_review()` still accepts tranches 1–3's `haiku_leaf`/`haiku_correct` workbooks. Smoke-tested on 12 tranche-3 strings, then used for tranche 4. The paragraph below that said “not yet implemented / unmodified as of 2026-08-23” is history.

**Gold v4 scored 2026-08-23 — Option 1 confirmed on the production population.** `data/gold_transactions_v4_slm_volume.csv` (900 rows, true-random over the *unmatched-Plaid* population specifically, unlike v3's whole-population sample; built/labelled/reviewed via `src/build_gold_v4_slm_volume.py`) scored with the finalized 84,348-char prompt via `src/score_gold_v4.py` — full table and caveats in `data/gold_v4_scoring_report.md`. Headlines (leaf/general): Gemini 3.7 Flash 88.3/93.1, Opus 85.9/89.6, Sonnet 80.0/85.8 on all 900; simulated Option-1 consensus gate (Gemini+Sonnet agree, Opus tiebreak) accepts 96.4% at 89.9/93.3, and the no-tiebreak Gemini==Sonnet subset is 95.6% leaf at 78.6% coverage. Two structural findings: (1) **40.4% of the unmatched-Plaid population is already T4-dictionary-covered** — on the true post-T4 residual (n=536, what the LLM tier actually serves) the consensus gate still gets 86.6/90.5 on accepted rows (94.4% accepted); (2) **TF-IDF v2 scores 59.0% leaf on this volume-weighted set vs 32.0% on the merchant-disjoint holdout** (49.4% on the residual) — the classifier memorises the labelled head, so it's a plausible instant-runtime tier for production-shaped traffic even though its generalization floor is weak. Plaid native: 16.9/44.9. Caveat: gold labels were Haiku+Sonnet-drafted before human review, mildly favouring Sonnet — which nonetheless scored lowest, so the ranking is trustworthy; Gemini/Opus scores are clean of drafting bias.

## 7. Backlog after that

1. ~~Four-field categoriser~~ — **done 2026-08-20** (bake-off adopted TF-IDF + logreg). **2026-08-26:** retrained on tranche 4; SGD hinge SVM now beats logreg on holdout/risk argmax (see current-state table). Serving dump is still logreg until Carlos picks a head. See `data/classifier_v5_retrain_report.md`.
2. ~~Merge dictionary additions + write direction rules~~ — **done 2026-08-20** (535 entries at that milestone). Now **91,527** after tranche 4 + residual T4 pack + n≥50 Plaid-miss aliases.
3. ~~Wire T4 + T5 into the crosswalk SQL~~ — **done 2026-08-20**. Historical sample: Equifax T4 34.8% / Plaid T4 30.5%. **2026-08-26 live remeasure:** Plaid T4 52.1%, T1–T4 53.2%; Equifax T4 37.4%. **Same day:** T4 served as a table join (`credit_risk_research.merchant_dictionary_t4`); generated SQL **~167 KB**. Reloaded at **91,527**.
4. ~~Recompute feature IVs / Experiment 3~~ — **rebuilt 2026-08-27**. T1–T5 + T5b hinge + T6/T7 on the labelled Equifax+Plaid cohort, then a screened XGBoost. **The live OB model is the XGBoost on Plaid-category features (0.403 month3 / 0.386 month6) — quote comparisons against it, not the logistic analog (0.328 / 0.405, simpler-learner reference only).** Headline = the **50-feature-capped** retrains (`experiment3_xgb_month3_50.joblib` / `_month6_50.joblib`; `created` excluded): signed Mar–Apr 2026 OOT `month3_1plus_pia` **0.477** (Plaid-train only **0.449**); `month6_3plus_pia_from_subscription` OOT Nov 2025–Jan 2026 **0.564** (Plaid-train only **0.488**). Uncapped reference: 0.478 / 0.560 at 102 / 96 features. Script `src/experiment3_xgb_pipeline.py`. Report: `data/experiment3_xgb_report.md` (50-cap addendum). The 24 Aug logistic analog run (`data/experiment3_iv_report.md`, unsigned 0.308 vs 0.328) is historical.
5. ~~Investigate the `rent` detection gap~~ — **done 2026-08-22**: R13 re-enabled with a targeted false-positive exclusion. IV essentially flat. Kept for audit-trail/fair-lending defensibility.
6. ~~Score `data/gold_transactions_v4_slm_volume.csv`~~ — **done 2026-08-23**: Option 1 confirmed; see §6a and `data/gold_v4_scoring_report.md`.
7. ~~Resume the `production_labelling.py` Option-1 refactor~~ — **done 2026-08-23**, then used for tranche 4.
8. ~~Human review on the two new gold sets~~ — **done 2026-08-23**. Risk set 711 rows; locked v5 1,100 rows (later **retired** as confirmation gold — tranche-4 novelty leak). Thin risk leaves: rare in Plaid (`data/thin_risk_leaves_volume.md`).
9. ~~Build targeted training data for the risk leaves the retrained classifier still fails~~ — **done 2026-08-24** (`data/classifier_v4_retrain_report.md`). Tranche-4 retrain 2026-08-26 lifted the bar further (logreg 81.4%, hinge 86.1%).
10. ~~Classifier serving rules for gambling catch-all + payday T5~~ — **done 2026-08-24**. **Creditspring is not payday** (2026-08-25).
11. ~~Applicant-level regularity for gig-platform credits~~ — **deferred 2026-08-26**. A Deliveroo credit cannot be labelled refund vs rider pay from one row, but a proposal-scoped pass would sit beside (not inside) the per-transaction waterfall, Plaid’s 90-day history is too short for cadence, and a naive “stable amount → salary” rule would mislabel pub-company/MLM/expense credits. Revisit only if Plaid history lengthens **and** a signed Experiment 3 re-score shows income as the remaining gap. Then treat it as a feature-layer test, not a new resolution tier.
12. ~~Tranche 4 100k review + T4 ingest~~ — **done 2026-08-25**. Snapshot `data/production_labels_tranche4.csv`. Two abstain recovery passes then stop.
13. ~~Rebuild classifier/SLM training on tranche 4~~ — **classifier done 2026-08-26**. SLM fine-tune **not** re-run on the new jsonl.
14. ~~Equifax high-volume fall-through tranche~~ — **rejected 2026-08-26** (4.4% of Equifax volume; blank vendor is 58%). Alias pass only if Experiment 3 still needs Equifax history.
15. ~~Decide serving head (logreg vs hinge SVM)~~ — **decided 2026-08-27: hinge SVM.** Wins leaf accuracy, weighted/macro F1, the risk bar (86.1 vs 81.4), and the T6 residual; logreg's `predict_proba` has no remaining consumer (T6 fallback gating measured harmful; abstain runs on margin). Logreg dump kept as rollback. Metrics: `data/classifier_v5_head_metrics_report.md`.
16. ~~Re-score Experiment 3~~ — **done 2026-08-27** (feature rebuild + XGBoost; signed GINI). See backlog item 4 and `data/experiment3_xgb_report.md`.
17. ~~Finish v6 locked sample~~ — **applied 27 Aug.** Carlos labelled the 8 flags. `data/gold_transactions_v6_LOCKED.csv` **1,100** rows, 0 blank. Do not score until go/no-go.
18. **Full-pipeline readout** — `python src/score_waterfall_pipeline.py`. **Remeasured 2026-08-27** after 91,822 T4: n=1,884, T1–T5 then hinge **80.4%** (was 74.9%); residual 516 (was 788). Same merchants OK. Re-run after material T2/T4/T5 changes. Not locked v5/v6. **Provider-native-only baseline (2026-08-31):** same 1,884 rows, mapping only the provider's own category through T6 (no T1–T5, no classifier) = **31.8%** leaf / **44.1%** general — the third number next to 80.5% (T1–T5 then hinge) and 72.0% (T1–T7 rules-only). Already in `data/waterfall_pipeline_report.md`, now a headline row there.
19. ~~Dedicated general-category classifier~~ — **measured 2026-08-26**. 29-way hinge **+3.1pp** holdout parent (63.4% vs leaf-rollup 60.3%) but **−2.1pp** on risk gold (83.4% vs 85.5%); high-cost distress parent recall 92.4% → 81.9%. Fresh TF-IDF matched frozen. **Do not cascade / do not switch serving.** Report: `data/classifier_general_bakeoff_report.md`. Specialists not trained.
20. ~~Label T6 residual top-up~~ — **ingested 27 Aug.** Packs 1+2 (`correct_category`) appended to `data/tuning_leaf_topup.csv` (+556; file **1,426**). jsonl **382,739**. Holdout MD5 unchanged.
21. ~~Retrain classifier on jsonl with T6 residual top-up~~ — **measured 27 Aug.** Hinge holdout 53.8% → 54.5%; risk bar **86.1% → 79.8%** (`car_lease` 20/20 → 3/20). Serving stays v5. Report: `data/classifier_v5b_retrain_report.md`.
22. ~~Drop T4-covered training rows~~ — **rejected 2026-08-27.** Residual+proto hinge (18k T6-bound jsonl + ≤20 head rows/leaf) **lost ~22pp** on holdout T6-bound and pipeline residual vs v5 hinge. Head rows transfer. `data/residual_prototype_train_report.md`. Do not switch serving. A 100k fall-through labelling tranche is not justified by this test.
23. ~~Fine-tuned encoder (MiniLM) on current jsonl~~ — **CLS pooling rejected; mean-pool retry 2026-08-27.** Wrong `[CLS]` head: leftover 17.5%. Mean-pool probe+unfreeze: holdout **52.1% vs hinge 53.8%**, leftover **53.0% vs 57.7%**, risk bar **68.7% FAIL vs 86.1%**. Do not serve. `data/encoder_finetune_minilm_meanpool_report.md`.
24. ~~Switch T6 to Plaid list `category` / `category_path`~~ — **rejected 2026-08-27.** T6-bound gold: PFC detailed **18.6%** leaf vs list field **15.7%**. Keep `credit_category_detailed` in `sql/apply_crosswalk.sql`. Map: `taxonomy/plaid_legacy_category_map.csv`. `data/plaid_legacy_category_t6_report.md`.
25. ~~Risk-guard oversample + retrain (v5c)~~ — **measured 27 Aug.** +327 copies of lease/DMP/revolving on non-risk-gold merchants. Hinge holdout **55.2%**; `car_lease` **20/20** again; risk bar **86.1% → 79.0%**. Serving stays v5. `data/classifier_v5c_retrain_report.md`.

26. ~~Category-granularity sensitivity~~ — **measured 2026-09-01; stress-tested 3 seeds + paired bootstrap the same day.** Same Experiment 3 cohort/windows/XGB, features rebuilt at 275 / 69 / 29 / 17 / 9 / 7 / 4 categories (69 = today's model-feature grouping — 40 individually-tracked leaves + the 235 remaining leaves rolled into 29 generals — not a 69-leaf taxonomy; see the Granularity wording note above). **275, current 69 and 29 groups are statistically indistinguishable; 17 is close but may lose month-6 signal (−0.026, 95% CI −0.051 to −0.003); 9 and below degrade; the 4-group uplift over live is not conclusive on month3.** Do not quote "flat 275→17, every rung beats live". Finer than today buys nothing; the live comparator in the ladder is an in-repo reconstruction (full refit 0.392 / 0.411). Rungs in `taxonomy/granularity_ladder.csv` (taxonomy.csv untouched). `src/experiment3_granularity_ladder.py` · `src/audit_experiment3_granularity.py` · `data/experiment3_granularity_ladder_report.md` · `data/experiment3_granularity_stress_test_report.md`.

## 8. Feature-layer findings (affect how features are built, not the taxonomy)

**Feature form beats category granularity.** Persistence (`COUNT(DISTINCT month)`) beat spend-share by up to **20×**: `Mobile Phone Contracts` 0.0061 → 0.1193. Also `Take Away` 9×, `Music and Downloads` 4.5×, `Internet/TV/Phone` 2.6×.

**But not universally** — `Cash Machine` and `Betting` are **frequency** (count), not persistence. **Presence flags are consistently weakest**, which matters because several existing features in `ds_plaid_credit_features` are `has_*_flag` binaries.

**Aggregate dimensions are the strongest features found:** `priority_debt_breadth` 0.1710, `credit_product_months` 0.1709, `priority_debt_months` 0.1523, `subscription_breadth` 0.0819.

**Signal decay was a false alarm.** Apparent month-12 decay was mostly *severity dilution* — at `month12_3plus_pia` signal largely recovers (Amazon 0.089→0.134; `priority_debt_breadth` hits its highest value, 0.1813). Model target matters as much as feature choice.

**Income is much weaker than spend:** best is `Identified Salary` persistence 0.0844.

## 9. Assumptions already disproved — don't repeat these

| Assumption | Reality |
|---|---|
| Lottery is the benign gambling subtype | **Highest** IV of all gambling subtypes (0.0498) |
| Alcohol doesn't compress under pressure → predictive | Near-zero (0.0043 / 0.0012) |
| Strained households shift to discount stores → signal | IV 0.0002 at 45% prevalence |
| Equifax doesn't separate unarranged overdraft | It does, at 126 txns |
| Returned payments are weak in Equifax | Wrong direction filter — they appear mainly as **credits** (30.3% vs 5.4%). Counting both directions: 0.0038 → 0.0263 |
| Plaid `reference_number` can crack the transfer bucket | 0% populated |
| Normalising merchant strings closes the Plaid gap | Only 43.1% → 48.8% |
| `_months` features just re-derive history length | Correlation with `total_months` only 0.18–0.37 |
| IV should decide which categories exist | **No** — IV is a risk-model feature-selection criterion. Low IV proves only that a category doesn't predict *that* outcome. Use IV to decide **where aggregation is safe**, never to prune categories. An earlier version pruned 127 leaves to 73 on this basis and had to be rebuilt. |
| Gemini is fully deterministic at temperature=0, like the local MLX model's greedy decode | **No** — 5/40 rows (12.5%) differed between two identical temp=0 Gemini 3.7 Flash calls. But a 3-run full-benchmark average was stable (leaf SD ≈0.15pp) — row-level flips roughly balance correct↔wrong, so aggregate single-run numbers still hold. See §6a. |
| A deterministic rules-DSL engine (FinLang) could replace or host the T1–T5 tiers | **No — evaluated 2026-08-23, see `docs/finlang-evaluation.md`.** Ran it for real: our 18,825-entry dictionary compiled to `.fin` scores 32.2% leaf on `gold_v2_slm_eval_holdout.csv` (94.7% precision at 34.0% coverage) — i.e. it faithfully reproduces T4 and does nothing for the long tail. T3 is inexpressible (six hard-coded fields, no provider-category slot) and T5 is worse than inexpressible: the DSL has no regex, and the only available glob translation of R07 (`*bet*`) mislabels 49 non-gambling merchants in our own dictionary. Throughput is ~2,800 rows/s with a real rulepack (the advertised 217K rows/s is benchmarked with **one** rule). Two ideas worth stealing anyway: reconcile/orphan detection and pre-merge impact reports. |
| A shorter, principles-based labelling prompt would perform as well as (or better than) the full 375 worked examples, since it's cheaper | **No, tested twice at different compression levels, both failed** — principles-only lost 4–4.5pp vs full examples even after excluding leakage; principles+full-375 also underperformed plain full-375. Prompt caching neutralises the cost concern anyway. See §6a. |
| liblinear `LinearSVC` will beat SGD hinge if we wait long enough for a “proper” SVM | **No — measured 2026-08-25.** Parallel OvR liblinear fitted in 40s on ~167k rows and ranked *below* SGD hinge on T6 residual (73.1 vs 79.0), holdout T6-bound (36.9 vs 39.1), and the risk residual bar (68.8 FAIL vs 75.3 OK). The earlier “hours” hang was a sequential multiclass fit, not evidence the solver is better. Do not retrain liblinear on the 382k-row set expecting a win. |
| A 10k Equifax-merchant labelling tranche will move T1–T4 much | **No — measured 2026-08-26.** Equifax has 6,518 vendors total. Unmatched filled vendors are 4.4% of Equifax volume; 58% have a blank vendor. Live traffic is Plaid; Equifax is dead. |
| Training only on T1–T5 fall-through (plus a small head prototype) will make the classifier better at serving | **No — measured 2026-08-27.** Residual+proto hinge lost ~22pp leaf on holdout T6-bound and the pipeline residual vs the head-heavy v5 hinge. T4-covered rows transfer. `data/residual_prototype_train_report.md`. |
| Fine-tuning MiniLM on the jsonl will beat char TF-IDF hinge on leftover / novel merchants | **Pooling was the first-run bug (`[CLS]` vs mean). Mean-pool retry still loses leftover (−4.7pp) and the risk bar (68.7% vs 86.1%). Holdout is close (52.1% vs 53.8%). `data/encoder_finetune_minilm_meanpool_report.md`. |
| T6 should use Plaid’s older list `category` / `category_path` instead of PFC detailed | **No — measured 2026-08-27.** T6-bound gold: list field **15.7%** leaf vs PFC detailed **18.6%**. Keep `credit_category_detailed`. `data/plaid_legacy_category_t6_report.md`. |
| Taking the absolute value of GINI (or `max(AUC, 1−AUC)`) is a harmless convenience | **No — 2026-08-26.** Unsigned GINI hides inverted scores. The 24 Aug Experiment 3 0.328 vs 0.308 used that helper. **Re-scored 27 Aug with signed GINI** (`data/experiment3_xgb_report.md`): live logistic Mar–Apr **0.328**, taxonomy XGB **0.478**. |

## 10. Separate high-impact finding (not taxonomy work)

**Every Plaid Asset Report since go-live requests exactly 90 days** — all 11,530, 2025-08-13 to 2025-11-03. This is a Raylo-side request parameter, not a Plaid limit. Consequences: `total_months` never exceeds 3; every `*_before_90d_amount` and `*_surge_vs_history_ratio` feature is structurally dead (`bnpl_before_90d_amount` is constant zero); `total_cash_advance_disbursement_amount` is zero for all 79,863 rows yet still returned non-trivial IV under naive ranking — **always apply a variance/non-null floor before trusting IV**.

The Equifax dump's 189-day history makes the hypothesis testable now. This is probably the single highest-impact fix in the whole project and it belongs to whoever owns the Plaid integration.

## 11. Conventions

- Keep `docs/project-summary.md` (plain-English stakeholder overview + progress log) updated as milestones land.
- **After every milestone, update in the same change:** (1) this file's current-state block, (2) `docs/project-summary.md` §8 plus a progress-log line, (3) `README.md` current-state table if headline numbers or the “do not” list moved. Dated reports in `data/` are snapshots — add an addendum, do not rewrite them as if they happened later.
- **`data/` holds human-verified, irreplaceable assets (gold eval set, adjudicated workbook, approved dictionary additions) — tracked in git, never overwrite programmatically.** `outputs/` is regenerable scratch, gitignored. `data/external_agent_adjudication_DO_NOT_INGEST.csv` is kept for provenance only.
- The repo is a git repository (since 2026-08-19). Commit after each substantive milestone; `.env` (API key) and `outputs/` are gitignored — verify with `git status` before any commit that adds new file types.
- Run `pytest tests/` after **every** taxonomy or dictionary edit. These tests already caught three invalid leaf references, a duplicate `Stationery` mapping, and a comma inside a regex that broke CSV parsing.
- Superseded work is in `archive/` with `_SUPERSEDED` / `_DISCARDED` suffixes. The AccountScore XML parser is discarded because the Equifax dump covers 99.997% of its references — don't resurrect it.
- Scratch output goes in `outputs/` (gitignored). Reusable benchmark/comparison scripts and their small text dependencies belong in tracked `benchmarks/`, not `outputs/` — anything needed to reproduce a quoted headline number must be in git.
- UK English in all artifacts and docs.

## 12. Evaluation methodology — locked test set, risk-category gold set, continuous improvement (2026-08-23)

Prompted by comparing notes against Bud's published transaction-categorisation testing methodology. Three decisions, all agreed with Carlos:

**The locked test set.** Every gold set we built before v5 had already been used to pick a winner at least once — `gold_v2_slm_eval_holdout.csv` decided prompt compression AND model choice AND Option 1; `gold_transactions_v4_slm_volume.csv` confirmed that choice. **v5** (`data/gold_transactions_v5_LOCKED.csv`, 1,100 rows, human-reviewed 2026-08-23) was built to be scored once at go/no-go. Tranche 4 then labelled 331 of its 952 merchants and 110 landed in the dictionary, so it is **retired as confirmation gold**. The CSV stays in git as reviewed labels; do not train on it and do not score it. **v6** (`src/build_gold_v6_locked.py`) is the replacement: same 400 Equifax + 700 Plaid true-random sample, exclusions via `eval_sets.v6_excluded_merchants()` (v5, risk gold, holdout, eyeballs, top-up, tranches 1–4, live dictionary). Sample fetched 2026-08-26 → `outputs/gold_v6_locked_sample.csv` (1,100 rows, 103,383 merchants excluded, zero overlap). Gemini+Sonnet drafts then agent adjudication 2026-08-26: **1,092** `final_leaf` set, **8** flagged for Carlos. Carlos labelled those 8 on 2026-08-27; `apply` wrote `data/gold_transactions_v6_LOCKED.csv` (**1,100**). Same scoring rule: **once, at go/no-go, never during development.** Scorers call `refuse_confirmation_eval()`.

**Bespoke high-risk-category gold set (`data/gold_transactions_risk_categories.csv`, once built).** `src/confusion_analysis.py` (new standing tool, see below) immediately confirmed the problem this set exists to fix: volume-weighted sampling structurally starves low-volume, high-consequence leaves — v4 got only 21 `gambling_betting` rows, and several risk leaves had only 3-4 rows across the entire 900-row set, with `financial_services_other` scoring 100% wrong (3/3) across all of Gemini, Sonnet, AND Opus — invisible in every one of those models' 80-88% aggregate leaf accuracy. `src/build_gold_risk_categories.py` deliberately stratifies ~20 rows per leaf across all 34 gambling / `credit_loan_repayments` (includes `bnpl`) / `high_cost_distress_credit` leaves (not the housing/utility priority-debt leaves like rent/mortgage — those are already well-covered by volume-weighted sampling), sourced via dictionary-merchant match + narrative-keyword fallback for the leaves with zero dictionary coverage, plus a 120-row undictionaried gambling pool specifically to catch subtypes the dictionary has never seen. 32/34 target leaves got real source rows (`cash_advance_fee` and `account_misuse` returned zero — itself a finding: check whether these leaves have real volume in the live population at all before assuming the sourcing query is at fault). **Human-reviewed and applied 2026-08-23** (plus a secondary adversarial-agent pass, see the completed workbook's `adversarial_status`/`adversarial_leaf`/`adversarial_reason` columns) — `data/gold_transactions_risk_categories.csv`, 711 rows. 7 leaves are still thin (<5 rows) after review — see backlog item 8.

**Standing confusion-matrix tool (`src/confusion_analysis.py`).** Institutionalises a lesson otherwise re-learned by hand every time: an aggregate leaf-accuracy number can hide bad performance on exactly the categories credit risk cares about most (mirrors Bud's own stated methodology: "not useful to have a 97% F1-score but then perform badly on categories like income, rent or gambling spend"). Takes any `{gold_leaf, pred_leaf}` prediction CSV and reports overall accuracy, a dedicated risk-category minimum-bar check (gambling / credit-loan-repayment / high-cost-distress-credit leaves specifically), per-leaf error rates, and top confusion pairs. Run this against every future benchmark, not just as a one-off.

**The continuous-improvement loop going forward.** The point of taking learnings forward isn't a one-time audit — it's a repeatable cadence:
1. Every `production_labelling.py` tranche gate, and every scored gold set, gets run through `confusion_analysis.py`. A risk-category leaf falling below the minimum bar is a required action item, not an FYI.
2. A leaf/pair `confusion_analysis.py` flags becomes the priority target for the *next* dictionary/rule addition or tranche's review queue — closing the loop from "found an error" to "fixed the underlying data," the same path the Tesco/Tesco Bank fix (§4) took, generalised into policy rather than one-off firefighting.
3. Any material pipeline change (new model, new prompt, dictionary tranche merge, new T1/T2/T5 rule) gets checked against the standard iteration suite — v3/v4-style volume-weighted evals plus the risk-category set plus `confusion_analysis.py` — before merging. The locked confirmation set (now v6; v5 retired) is never part of this loop; only the final promotion decision touches it.
4. Rising abstention/`needs_review` rate in a production tranche gate is the drift signal that it's time for the next tranche — new merchants (new BNPL providers, new gambling apps) enter the population continuously, so this is scheduled work, not reactive work.

**First real exercise of this policy, 2026-08-24 — the classifier's retrain.** `outputs/distill_models/tfidf_logreg_v2.joblib` was stale (trained 2026-08-21, before v3/v4/the risk-category set existed). Retrained with v3+v4 added as training-only data (`build_tuning_dataset.py`'s new `ADDITIONAL_TRAIN_FILES`, deliberately bypassing the merchant-level holdout carve-out so `data/gold_v2_slm_eval_holdout.csv` stays byte-identical — verified by MD5 before/after, since every §6a number is measured against that exact file). Real win on the unchanged holdout: **32.0% → 37.4% leaf**. But the risk-category minimum bar (§ above) **fails**: 68.2% vs the 70% bar, hidden behind a 64.3% aggregate. Root cause is mostly a training-data gap, not a modelling one — `cash_advance` had **zero** training examples, `charge_card_repayment` had 1, `financial_services_other` had 5, all scoring 100% wrong as a direct result. `gambling_unspecified` (104 examples) also scores 100% wrong despite non-trivial training volume, outnumbered ~4:1 by `gambling_betting` — defaults to abstaining rather than guessing a specific subtype, a safer failure mode but still means this leaf currently can't be served by the classifier at runtime at all. Full numbers: `data/classifier_v3_retrain_report.md`.

**Follow-up the same day — risk-leaf training top-up, bar now PASSES.** Targeted Plaid top-up (`src/build_risk_leaf_topup.py`) plus starved-class oversampling to 200 effective rows. Risk-category bar 68.2% → **72.4%**. Starved leaves no longer 100% wrong (`cash_advance` 20/20, `charge_card_repayment` 6/6, `financial_services_other` 5/8). `gambling_unspecified` is still ~92% → `unclassified_other` (zero consensus-accepted training rows of that leaf) — confidence-gate, not more labels. Holdout 37.4% → 35.7%. v5 not scored. Full numbers: `data/classifier_v4_retrain_report.md`.

**2026-08-25 — T5b residual vs T6.** On Plaid gold that currently falls through T1–T5 (n=695), T6 is 22.0% leaf. Always-ML beats it (hinge 79.0 > liblinear 73.1 > logreg 60.7) but v3/v4 were in training. Leakage-free holdout T6-bound: hinge 39.1 / liblinear 36.9 / logreg 34.5. Falling back to T6 when unsure is worse than always serving ML. `data/t5b_residual_gate_report.md`.

**2026-08-26 — retrained on tranche 4 + hinge scored.** `build_tuning_dataset.py` reads `production_labels_tranche4.csv`. Train rows 166k → 382k. Holdout MD5 `c075717405a183191a43d0eb33f8dca3` unchanged through the build. Logreg **37.2% → 50.9%** holdout leaf; risk bar **74.0% → 81.4%**. SGD hinge **52.8% / 86.1%** risk bar — beats logreg; no `predict_proba`. Liblinear not retrained. Plaid T1–T4 live **53.2%** (T4 52.1%). Equifax 10k tranche rejected. Locked v5 not scored. `data/classifier_v5_retrain_report.md`. Scorer: `src/compare_classifier_versions.py` (uses `decision_function` for hinge).

**2026-08-26 — provenance containment (handoff items 1–3).** Relabelled tranche 4: `human_reviewed` 91,803 → **4** (Carlos); rest `agent_tiebreak` / `agent_consensus` / `agent_review`. Dictionary-eligible count unchanged (91,803). T4 matching now skips pending + `unclassified_*` (36 rows dropped; Tesco seed is **approved**, not pending). `fill_agent_tiebreak.py` writes `production_predictions_opus_filled.csv` and never overwrites the Opus file. Tests: `test_tranche4_human_reviewed_is_carlos_only`, `test_t4_skips_pending_and_unclassified`, `test_fill_agent_tiebreak_does_not_overwrite_opus`. Classifier not retrained.

**2026-08-26 — GINI sign, T4 table join, v5 retired / v6 sample labelled.** Experiment 3 now uses `signed_gini` (`2*AUC−1`; inverted scores come out negative). Published 0.328 vs 0.308 were unsigned; ranking likely holds but do not re-quote as signed until a re-score. T4 SQL joins `credit_risk_research.merchant_dictionary_t4` (91,137 rows loaded; dataset EU); regenerated SQL **~158 KB**. v5 locked set retired as confirmation gold (tranche-4 novelty leak). v6 sample fetched (1,100 rows) then Gemini+Sonnet drafted: 1,100/1,100, 810 agree (73.6%), 290 disagreements. Review workbook `outputs/gold_v6_locked_review.xlsx`. Scorers call `eval_sets.refuse_confirmation_eval()`.

**2026-08-26 — v6 agent adjudication.** Reviewed all 1,100 rows against locked conventions. `final_leaf` set on **1,092**; **8** left blank for Carlos (`outputs/gold_v6_locked_human_review.csv`).

**2026-08-27 — Experiment 3 feature rebuild + XGBoost.** T1–T5 then T5b hinge on leftover (Plaid 1.81M keys, Equifax 6,259 vendors), then screened GBM. Signed GINI: month3 Mar–Apr OOT taxonomy XGB **0.478** (Plaid-train only **0.467**) vs live logistic **0.328** / live XGB **0.403**. month6 Nov 2025–Jan 2026 OOT taxonomy XGB **0.560** (Plaid-train only **0.532**) vs live logistic **0.405**. `src/experiment3_xgb_pipeline.py`. `data/experiment3_xgb_report.md`.

**2026-08-27 — Experiment 3 framing fix + 50-feature cap.** Carlos: the live OB model is the **XGBoost** on Plaid-category features, so the live comparator is 0.403 / 0.386, not the logistic analog. Retrained with a hard 50-feature cap by inner-train gain (`created` excluded): month3 OOT **0.477** (Plaid-train only 0.449), month6 **0.564** (0.488) — capping barely moves the headline vs 102/96 features, so the signal fits a governable feature set. Capped dumps `outputs/experiment3_xgb_month3_50.joblib` / `_month6_50.joblib`. Addendum at the bottom of `data/experiment3_xgb_report.md`. Stakeholder report + charts quote the capped numbers vs live XGB.

**2026-08-27 — frontier vs serving hinge (framing).** Gemini 3.7 Flash and Sonnet 5, full labelling prompt, unique union of holdout + risk + pipeline (2,004 fingerprints). Holdout leaf hinge **53.9%** / Gemini **83.9%** / Sonnet **79.1%**. Pipeline leftover 59.2 / **73.0** / 67.4. T1–T5 then model 80.5 / **84.2** / 82.7. Do not serve LLMs at runtime. `src/score_frontier_vs_classifier.py`. `data/frontier_vs_classifier_report.md`.

**2026-08-27 — v6 locked file applied.** Carlos labelled the 8 flags. `data/gold_transactions_v6_LOCKED.csv` **1,100** rows. Do not score until go/no-go.

**2026-08-27 — serving head decided: hinge SVM.** Carlos confirmed hinge (`tfidf_linearsvm_sgd.joblib`, v5) as the serving head; logreg (`tfidf_logreg_v2.joblib`, v5) is rollback only. Rationale: hinge wins every promotion-gating metric (holdout leaf 52.8 vs 50.9, weighted/macro F1, risk gold 80.6 vs 76.8, risk bar 86.1 vs 81.4, T6 residual 74.9 vs 68.0); logreg's probabilities have no consumer — T6-fallback gating was measured harmful at every threshold, and abstain-to-unclassified works on the `decision_function` margin (global threshold tuned on holdout to hold the risk bar; per-class only if monitoring shows a leaf abstaining badly). If calibrated confidence is ever required, Platt-scale the margins rather than reverting the head. Pipeline scorers already use hinge, so the 80.5% headline is unchanged. Locked v6 not scored for this.

**2026-08-27 — hinge-only v5d.** Same 383,066 jsonl, fresh TF-IDF, no logreg. Holdout **56.6%**; risk bar **82.2%** (v5 **86.1%**). Serving stays v5. `data/classifier_v5d_retrain_report.md`.

**2026-09-01 — category-granularity sensitivity: first pass, single seed (superseded same day).** Stakeholder question after the Experiment 3 readout. Seven rungs, same cohort/windows/XGB/screen. A single-seed, no-CI run read as "flat 275 → 17; every rung beats live 0.403/0.386" — **this framing does not survive stress-testing and must not be quoted.** See the corrected entry immediately below.

**2026-09-01 — category-granularity sensitivity, corrected: 3-seed stress test + paired bootstrap (`src/audit_experiment3_granularity.py`).** 275, current 69 (today's model-feature grouping — 40 leaves kept individually + the rest rolled into 29 generals, not a 69-leaf taxonomy) and 29 groups are statistically indistinguishable on both targets (no paired comparison among them excludes zero). 17 groups is close on month3 but has a real, small month6 loss vs 69 (−0.026, 95% CI −0.051 to −0.003 — excludes zero). 9 and below show material, unambiguous degradation. The ladder's live comparator was an in-repo reconstruction refit on the full train window, not the production artefact — seed-mean 0.392/0.411 (single earlier run read 0.403/0.386 from an inner-80%-split-only variant). Every rung's point estimate beats this reconstruction, but the smallest-rung (4-group, capped) uplift is **not conclusive on month3** (+0.035, 95% CI −0.004 to +0.074); month6 is conclusive (+0.058, CI +0.012 to +0.100). A same-20-feature taxonomy-vs-live ablation is inconclusive on both targets and flips sign by target, so the large headline uplift belongs to the whole feature/model bundle, not to taxonomy granularity alone. Recommendation: keep 275 as governed source of truth; treat 29 as the evidence-backed model rollup; keep 17 as a challenger pending direct-head retraining and temporal validation; do not go to 9 or fewer. Full methodological caveats (post-OOT merchant-vocabulary leakage, rollup-vs-direct-retrain gap, comparator fidelity) in the report. `data/experiment3_granularity_stress_test_report.md`, `docs/taxonomy-granularity-conclusion.md`.

**2026-09-01 — category *expansion* pilot (the opposite direction): inconclusive, do not adopt.** Three parents (`streaming`, `marketplace_general`, `payment_intermediary`) split into 15 frozen shadow child buckets (275 → 287 if adopted), rules on merchant/description only, frozen before outcomes inspected. Parent-control vs parent+children comparison isolates the split's own value. Rolling pre-OOT Plaid: parent control 0.513/0.571; +lean split 0.508/0.564 (Δ −0.0045/−0.0068, both CIs include zero); +rich split 0.511/0.560 (Δ −0.0020/−0.0111, both CIs include zero). Not low-support — shadow categories present in 54,369/64,209 rows. `payment_intermediary` alone gave a small, statistically clear month3 **loss**. **Do not adopt the 287-leaf expansion**; test further splits in shadow without recategorising history. `src/experiment3_subleaf_pilot.py`, `data/experiment3_subleaf_pilot_report.md`.

**2026-08-26 — 29-way general classifier bake-off.** Same 382k jsonl, same TF-IDF/SGD budget as v5; labels are the taxonomy rollup (no new labelling). Dedicated hinge **63.4%** holdout general vs leaf-rollup **60.3%** (+3.1pp); risk gold **83.4% vs 85.5%** (−2.1pp). High-cost distress parent recall dropped 92.4% → 81.9%. Fresh vocabulary = frozen vocabulary. Serving dumps not touched. Do not build specialists on this evidence. `data/classifier_general_bakeoff_report.md`. Scorer: `src/score_general_classifier.py`.

**2026-08-26 — logreg vs hinge F1 / per-class.** Same v5 dumps. Holdout leaf: hinge **52.8%** acc / **51.5%** weighted F1 / **45.3%** macro F1 vs logreg 50.9 / 49.0 / 43.4. Risk bar **86.1% vs 81.4%** (macro F1 86.9 vs 83.4). Parent macro F1 slightly favours logreg (thin `fees_charges` / `salary` zeros on hinge). Serving dumps not switched. `data/classifier_v5_head_metrics_report.md`.

**2026-08-26 — returned-payment / refunded T2, benefits T4+R23, pipeline readout.** T2 before T4: `refund(ed)?` → `refund_received`; returned DD / DD reversal / `reversal of` → `returned_payment`. T4 `work and child tax credit` → `benefits_state`. T5 R23 credit-side DWP/HMRC benefit narratives. Did **not** T4 bare `royal london` (insurance collision). No classifier retrain. Full-pipeline scorer: `src/score_waterfall_pipeline.py` → `data/waterfall_pipeline_report.md`. **One row-disjoint set** (`outputs/gold_pipeline_eval.csv`, n=1,884): T1–T5 then hinge **74.9%** leaf vs rules-only **67.9%**. Earlier v3/v4 pipeline numbers (88.7% / 92.3%) were **row-leaked** (those gold files are in the jsonl). Reload BQ T4 table before quoting live SQL coverage.

**2026-08-26 — residual T4 pack + holdout gold_leaf patches.** Dictionary **91,229** (`HUMAN_T4_20260826`). Retargets include `loans2go` → `payday_loan`, `wex europe` → `business_services`. T2: Amazon UK Services **credit** → `salary` (before T4 `amazon`); IPS/Roadchef/Wembley Express/NatWest recollection collisions. T5 R24 Scholastic Book (description), R25/R26 credit `wages`. Did **not** T4 bare Mercedes Benz (amount-split not in T5; dealer vs purchase already split on other keys). No global hotel-amount → restaurant/pub rule (Travelodge rooms can sit in the same band as bar tabs). Holdout MD5 `1ac2eaaa494a49beab6d81f6cafe27c4` (13 gold_leaf corrections). Classifier not retrained.

**2026-08-26 — n≥50 Plaid T4-miss aliases.** Filled unmatched merchants with volume ≥50 (817 keys; stayed at 50). Blank-merchant volume is pots/transfers, not T4. Two Luna agents proposed leaves; parent promoted **297** aliases (~161k rows of that residual), dictionary **91,527**, BQ reloaded. `icelandair` → `groceries` (Iceland Foods). Withheld collisions in `data/t4_residual_human_review.csv`. Live coverage not remeasured. Classifier not retrained.

**2026-08-26 — Carlos debit-default pack + direction T2.** 22 T4 keys (`data/t4_carlos_review_applied_20260826_debit.csv`): Ocado/Sodexo/Ask Italian/Fife/Avon/Prudential/Plum Fintech/Fluid debit defaults with T2 credit splits; Admiral casino T2; Royal London `insurance_life`; Places for People rent + leisure T2; Close Brothers motor finance; NOW TV via T2/T5 `Entertai` / `PAYPAL *NOW` (not bare `now`). YouLend credits are `loan_disbursement` after returned-DD T2. Dictionary **91,806**. Open queue 123 rows. Classifier not retrained.

**2026-08-26 — Carlos B-leftover T2/T4/T5.** 16 T4 keys plus narrative T2 for Mercedes/Gem/Home/City/Orbit/Plus/Wood J (no T4 on those tokens). Returned standing order added to T2. Off-licence T5 R29/R30. Grosvenor credits → salary before T1 gambling. Dictionary **91,822**. Open queue 99. Classifier not retrained.

**2026-08-27 — Trading 212 T4.** `trading 212` and `trading212` → `investment_trading` (`data/t4_trading212.csv`). Dictionary **91,824**, BQ reloaded. Exact merchant join only — `TRADING 212 UK LIM` in the narrative with a blank merchant still misses T4. Classifier not retrained.

**2026-08-27 — Plaid list `category` vs PFC T6.** Mapped 115 live `category_path` values. T6-bound gold (n=953): PFC detailed **18.6%** leaf vs list field **15.7%**. Do not change T6. `data/plaid_legacy_category_t6_report.md`.

**2026-08-27 — risk-guard retrain (v5c).** jsonl **383,066**. Hinge holdout 53.8% → **55.2%**; `car_lease` 20/20 (was 3/20 on v5b); risk bar **86.1% → 79.0%** (DMP / revolving / `gambling_unspecified` slipped). Serving stays v5. `data/classifier_v5c_retrain_report.md`.

**2026-08-27 — T5 R31 StepChange.** Description-level `\bstep[\s-]*change\b`, debit → `debt_management_plan`. Blank-merchant `STEPCHANGE` misses T4. Classifier not retrained.

**2026-08-27 — PayPal Credit → revolving.** T4 `paypal credit` retargeted from `bnpl`. Pay in 3/4 stay `bnpl`. T2 on merchant `paypal` (`PAYPAL *PAYPAL CRE`) and Pay in 3 on `paypal credit`. T5 R32 blank-merchant. Holdout gold_leaf patched (one row); MD5 `7456da977a2c761119368637658232b6`. Classifier not retrained. Reload BQ T4.

**2026-08-27 — T6 residual v5b retrain.** Same SGD on 382,739 jsonl. Hinge holdout 53.8% → **54.5%**; risk bar **86.1% → 79.8%** (`car_lease` 20/20 → 3/20 → `carwash`). Logreg flat-to-down. Serving restored to v5; v5b dumps kept. `data/classifier_v5b_retrain_report.md`.

**2026-08-27 — fine-tuned MiniLM vs hinge.** `sentence-transformers/all-MiniLM-L6-v2` 1 epoch on 382,739 jsonl (MPS, 9.4 min). Head-like val 56%; holdout T6-bound **17.5% vs serving hinge 57.7%**; pipeline residual 17.2% vs 60.1%; risk bar 1.9%. Train-head 54% (not a label bug). Do not serve. `src/experiment_finetune_encoder.py`. `data/encoder_finetune_minilm_report.md`.

**2026-08-27 — MiniLM mean-pool retry.** First run used `[CLS]` pooling on a mean-pool checkpoint. Retry: freeze encoder + linear head, then unfreeze. Probe val 61.3%, unfreeze val 72.9%. Vs serving hinge: holdout **52.1% vs 53.8%**, leftover **53.0% vs 57.7%**, risk bar **68.7% vs 86.1%**. Do not serve. `data/encoder_finetune_minilm_meanpool_report.md`.

**2026-08-27 — T6 residual top-up ingested.** Packs 1+2 reviewed labels appended (`src/append_t6_residual_topup.py`): **+556** → `tuning_leaf_topup.csv` **1,426**. Three pack-2 patches kept (Karim FPS `transfer_p2p`; Schneefangsysteme `income_other_unspecified`). jsonl **382,183 → 382,739**. Holdout MD5 `1ac2eaaa…` unchanged.

**2026-08-27 — T6 residual pack 2 (keyword nets).** After pack 1’s Plaid-native nets mostly missed the target leaf, pack 2 fetches T4-miss rows on narrative/entity only (`src/fetch_t6_residual_topup2.py`). **142** rows in `outputs/t6_residual_topup2_sample.csv`. Salary Finance / cashback / Slack FX rebates / personal overpayments dropped before write. Refunds **6**, utility_other **4**. Labelled then ingested the same day.

**2026-08-27 — residual+prototype hinge (train/serve mismatch).** Dropped the 95% of jsonl that T1–T5 catch; kept 18,487 residual rows + ≤20 head prototypes/leaf (23,520 train, 268 classes). Fresh-TF-IDF SGD hinge vs serving v5 hinge: holdout T6-bound **57.7% → 36.0%**; pipeline residual **60.1% → 38.0%**; risk bar 86.1% → 59.1% FAIL. Head examples transfer; do not train residual-only. Serving dumps not touched. `src/experiment_residual_prototype.py`. `data/residual_prototype_train_report.md`.

**2026-08-27 — pipeline + T5b remeasure; T6 residual fetch.** After 91,822 T4: same n=1,884 eval, T1–T5 then hinge **80.4%** (was 74.9%); residual **516** (was 788), hinge 60.1% vs T6 26.2%. Plaid gold T6 residual **231** (was 695); holdout T6-bound hinge **57.7%** (was 39.1%). Always-ML still beats T6. Unlabelled fetch: `outputs/t6_residual_topup_sample.csv` **414** rows (`data/t6_residual_topup_fetch.md`). Classifier not retrained.

**2026-09-02 — programme review + Week-1 fixes.** Review doc `docs/review-2026-09-02-state-and-next-steps.md`. Fixes: risk-gold merchants excluded from training (jsonl 381,560; honest risk bar **62.7%** vs leaked 86.1%; `data/classifier_v6_deleaked_report.md`); T4 tranche-4 downgrade guard (−1,575 keys + bare `credit`; dictionary **90,261**, BQ reloaded); Python waterfall reordered to SQL tier order + `check_waterfall_parity.py` (2,004/2,004 agree) which caught the Carlos-pack raw-string double-escaping bug (34 T2 rules dead in SQL until now); direction + provenance splits in all scorers with a credit-side bar; pipeline re-measured **81.8%** on 2,004 rows (credit 57.8% / debit 84.2%; human-v2 77.7% / LLM-drafted 86.1%); Experiment 3 as-of filter + full-refit live comparator (capped 0.477 / 0.562; Plaid-only 0.445 / 0.504 vs live 0.382 / 0.385). Tests 34. Locked v5/v6 not scored.

**2026-08-31 — provider-native-only baseline surfaced.** Same n=1,884 pipeline eval: mapping only the provider's own category through T6 (no T1–T5, no classifier) = **31.8%** leaf / **44.1%** general. This number already existed in `data/waterfall_pipeline_report.md`'s "Provider-native only" section; promoted to a headline row in that report's main table and referenced in `docs/project-summary.md` and `README.md` as the third apples-to-apples figure alongside 80.5% (T1–T5 then hinge) and 72.0% (T1–T7 rules-only). No new measurement, no retrain.

## Suggested skills

- `data:write-query` / `data:sql-queries` — BigQuery dialect, partition pruning (the Equifax dump is 20GB; select only needed columns)
- `select-bigquery-project` — defaults to `raylo-production`
- `data:explore-data` — profiling before trusting any new field
- `data:statistical-analysis` — for the IV / WoE work
- `data:validate-data` — before any result goes to stakeholders

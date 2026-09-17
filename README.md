# raylo-transaction-categorisation

Research repo for a single transaction taxonomy across Raylo's Open Banking providers (Equifax and Plaid).

**Status: research. Nothing here is in production.** No dbt model or scheduled job references this repo, and it must stay that way until work is explicitly promoted.

- **Dataset continuation handover (16 Sep):** [Start here](docs/benchmark-handover/2026-09-16/HANDOVER.md). Self-contained context, source pins, tested startup commands and B03-A synthetic reservation protocol assignment. Includes a fresh-agent prompt and explicit review boundaries before real admission, labelling, cloud changes or retraining.

- **B03-A synthetic protocol (16 Sep):** [Design and evidence](docs/benchmark-implementation/b03-a-synthetic/README.md). The canonical app package now exercises strict content-bound claims, fresh B02 preflight, epoch compare-and-commit, idempotent retries, permanent protections and alias contamination with 29 passing synthetic tests; independent Sol protocol review is approved. This is a local test double only: no real membership, label, model, locked-set or cloud authority exists.

- **B03-B linked-pool audit (16 Sep):** [Current aggregate-only source profile](docs/benchmark-implementation/b03b-linked-pool-audit-2026-09-16/README.md). A new bounded `raylo-production` EU `SELECT` found 20,474,043 unambiguous existing customer-linked observations across 46,051 customers from 36,312,899 materialized rows. This is source-readiness evidence, not candidate admission; no raw rows, labels, membership, training, scoring or cloud changes were made.

- **B03-B authority boundary (17 Sep):** [Adapter contract and synthetic evidence](docs/benchmark-implementation/b03-b-production-boundary-2026-09-16/ADAPTER_CONTRACT.md). The canonical app package has injected immutable-object and registry/CAS ports plus a strict exact-object authenticated receipt path bound to an authority-resolved worker audience and backed by an authority signer port and lazy KMS adapter; twenty synthetic boundary tests pass. A separate physical scope is now partially provisioned for synthetic proofs; IAM, live identity enforcement, real membership and B04 consumer integration remain open.

- **B03-B physical scope review (17 Sep):** [Scope and proof checklist](docs/benchmark-implementation/b03-b-physical-scope-review-2026-09-17/README.md). The approved partial setup now contains the dedicated EU bucket with its HSM storage CMEK attached, keyring and HSM keys; Firestore registry creation is blocked by the provider CMEK quota/allowlist, while service identities, IAM bindings and live proofs remain pending. No customer data, membership, labels or B04 consumer were accessed.

- **B03-C annotation-method pilot runner (16 Sep):** [Synthetic provider evidence](docs/benchmark-implementation/b03-c-annotation-method-pilot-2026-09-16/README.md). Strict independent-output contracts and explicit online/batch submit-status-collect paths are implemented for Gemini 3.8 Flash, Gemini 3.7 Flash and Sonnet 5. Synthetic online outputs and a valid Sonnet batch output passed; invalid batch fields were rejected. No real rows were downloaded or labelled, no 500-row pilot was admitted, and no B04 consumer is wired to these outputs.

- **Joint benchmark and retraining data plan (16 Sep):** [Profile and plan](docs/benchmark-implementation/b02-joint-data-plan-2026-09-16/README.md). Profiled 20,473,397 currently linked materialized rows across 46,049 customers (22.85% credits; 35.22% blank merchants). Audited distinct training inputs, 133 conflicting-label groups and selection coverage gaps. Plan protects evaluation and selection before new training additions shared by hinge and transformer. No new labels, fitted models, scores or staging deployment.

- **Historical regression and source-readiness audit (16 Sep):** [Frozen cohort and audit](docs/benchmark-implementation/b02-curation-audit-2026-09-16/README.md). Reuses 8,212 transaction input cases, 641 head-only cases and 1,810 dictionary cases; 28 label-conflict groups are withheld and 5,000 validation rows retain their role. Verified cached baseline predictions supply separate diagnostic scores. Current joins recover 263 direct customer links; 38,498 distinct events still lack customer identity. Scoped effective-input and merchant-name checks precede further family/alias/ancestry work and B03/B04 admission. No fresh rows reserved or labelled.

- **B02 source/index increment (16 Sep):** [Verified private extract and input-presence index](docs/benchmark-implementation/b02-source-index-2026-09-16/REPORT.md). A bounded 78,537-observation sample recovers raw report/Item/currency/pending fields; historical customer identity is still incomplete. Indexed the full 21.5M-row MLM snapshot plus distillation, training and selection inputs. All 40 historical overlap checks agree. No benchmark reserved, labels created, accuracy scores changed or staging deployed.

- **Applicant identity and transport review (16 Sep):** [Backend/transport evidence and next step](docs/benchmark-implementation/b02-applicant-identity-2026-09-16/README.md). Assessment, checkout, provider, account and transaction keys support correlation/grouping; anonymous applicant ownership remains unresolved. The minimal action is an assessment-first warehouse sidecar join; no categoriser DTO or runtime change is required.

- **Bounded applicant measurements (16 Sep):** [Fixed 49-checkout aggregate](docs/benchmark-implementation/b02-applicant-identity-2026-09-16/MEASUREMENTS.md). All 49 had nonblank canonical email and no user ID; direct user/customer and exact canonical-email matches were zero. This is scoped query evidence, not a population estimate or identity certification.

- **Linked-customer population decision (16 Sep):** [V1 scope amendment](docs/benchmark-implementation/b02-linked-customer-scope-2026-09-16/DECISION.md). The initial benchmark population is the audited linked-customer Plaid pool; benchmark candidates require an unambiguous existing assessment → checkout → user → customer link. Unresolved or ambiguous rows remain excluded, while source and audit records are preserved. The runtime categorisation contract is unchanged; the prior requirement to recover anonymous identity before v1 is superseded.

- **B02 initial curation foundation (15 Sep):** [Implementation and evidence](docs/benchmark-implementation/b02-initial/README.md), [three-view amendment](docs/benchmark-implementation/b02-initial/CONTRACT_AMENDMENT.md) and [source readiness](docs/benchmark-implementation/b02-initial/SOURCE_READINESS.md). Shared local checks distinguish representative new events, unseen inputs and unfamiliar merchants. Synthetic profiling and the app report-ID source fix are tested. Durable reservation, full exposure/source indexes and real candidate counts remain pending; no benchmark has been collected or labelled.

- **B01 exposure/source-identity audit (15 Sep):** [Findings and evidence](docs/benchmark-audits/b01-2026-09-15/REPORT.md). Exact pretraining matches cover all 2,000 credit and 400 targeted-risk evaluation inputs; selection validation also overlaps supervised distillation. Current Plaid data is large but only 56.49% links to users/customers, and all stored asset-report IDs are null. Existing scores remain development evidence; no clean master is certified and no pipeline changed.

- **Master benchmark design (15 Sep):** [Design](docs/benchmark-design/master-v1/DESIGN.md), [identity/separation contract](docs/benchmark-design/master-v1/DATA_CONTRACT.md) and [implementation plan](docs/benchmark-design/master-v1/IMPLEMENTATION_PLAN.md). Proposed 20,000-row core/challenge/confirmation benchmark with permanent training/pretraining/enrichment exclusions. Design only: no new dataset collected or admission enforcement deployed.

- **Latest evaluated correction (15 Sep):** [CREDIT-PAYROLL-001](docs/waterfall-changes/credit-payroll-001/RECORD.md) adds one exact Waitrose payroll-credit collision. Both heads and all 15 permitted datasets passed with unchanged real-data scores; the synthetic explicit payroll case is fixed. There are no exact-merchant Waitrose credits in the existing datasets. Research replay is identical; staging promotion is deferred.

- **Fresh waterfall baseline (15 Sep):** [Results and verification](docs/waterfall-changes/baseline-2026-09-15/RECORD.md), [run/compare guide](docs/waterfall-changes/RUNNING.md), [required process](docs/waterfall-changes/POLICY.md) and [score history](docs/waterfall-changes/README.md). All 15 permitted datasets plus seven synthetic examples ran; the research replay produced zero differences. No classification policy changed.

- **Agent context (read first):** [`CLAUDE.md`](CLAUDE.md) — includes **2026-09-07 and 2026-09-02 current-state** blocks
- **Stakeholder report (Sep 2026):** [`docs/report-2026-09/OB_Transaction_Categorisation_Report_Sep2026.pdf`](docs/report-2026-09/OB_Transaction_Categorisation_Report_Sep2026.pdf) (HTML source alongside)
- **Stakeholder overview + progress log:** [`docs/project-summary.md`](docs/project-summary.md)
- **Design rationale:** [Notion — Unified Transaction Taxonomy](https://app.notion.com/p/3bf5bb4b4a6581b6807add39671e56c2)
- **Labelling conventions (review closed):** [`AGENT_RULES.md`](AGENT_RULES.md)

## Why this exists

The live Open Banking risk model reads Plaid's category names directly. Plaid shipped a new taxonomy version (PFC v2, Dec 2025) after Raylo went live on Plaid, and the same transaction can be relabelled between versions. This repo builds a taxonomy Raylo owns, with provider categories as input evidence rather than as the definition.

## Layout

```
taxonomy/
  taxonomy.csv                    275 detailed leaves -> 29 general categories
  merchant_dictionary.csv         91,824 keys (T4) — regenerated by build_merchant_dictionary.py
  rules/deterministic_rules.csv   T5 regex (enabled column, not a string flag)
  rules/t2_entity_collisions.csv  T2 merchant+narrative splits (before T4)
sql/
  apply_crosswalk.sql             generated waterfall; T4 is a BQ table join (~167 KB)
src/
  generate_crosswalk_sql.py       regenerates apply_crosswalk.sql (T2 lives here, not as a hand-patch)
  load_t4_dictionary_bq.py        loads taxonomy/merchant_dictionary.csv → credit_risk_research.merchant_dictionary_t4
  build_merchant_dictionary.py    regenerates merchant_dictionary.csv (do not hand-edit)
  build_gold_v6_locked.py         locked confirmation sample (v5 retired)
  eval_sets.py                    confirmation-set guard + v6 exclusion list
  credit_metrics.py               signed GINI (2*AUC−1; never abs)
  build_tuning_dataset.py         Tier A gold + Tier B production_labels_tranche4.csv
  compare_classifier_versions.py  holdout + risk gold scorer (logreg and hinge)
  score_frontier_vs_classifier.py Gemini 3.7 / Sonnet 5 vs hinge (framing; full prompt)
  score_gemini38_vs_37.py Gemini 3.8 vs saved 3.7 (keep 3.7; data/gemini38_vs_37_report.md)
  confusion_analysis.py           standing risk-category bar
tests/
  test_taxonomy_integrity.py      run after every taxonomy / dictionary / T2 / T5 edit
data/                             human-verified gold + tranche snapshots (tracked; never overwrite)
outputs/                          scratch (gitignored) — models, jsonl, review packs
```

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest tests/ -q          # must pass before and after any taxonomy edit
```

BigQuery project is `raylo-production`, read-only. Write experiment output to a scratch dataset, never `dbt_production`.

## Current state (2026-09-07)

| Item | Status |
|---|---|
| Taxonomy (275 leaves / 29 generals) | Built, verified — 0 uncovered provider values |
| T4 dictionary | **91,824** keys (Trading 212 / `trading212` → `investment_trading`) |
| T1–T5 waterfall | Wired; Plaid live T4 **56.5%** of all transactions (89% of filled-merchant rows); T1–T4 **57.0%** on a 20% sample |
| Production labels | `data/production_labels_tranche4.csv` (100k; review **closed**; `human_reviewed` = Carlos only) |
| Classifier | Serving head is still the **v5 hinge SVM** dump (stale: 24pp behind on credits, 28pp on T6-bound risk). Reference hinge is **v8** (de-leaked + credit tranche + risk tranche, jsonl 414,400): credit eval **85.9%**, T6-bound risk-leaf acc **75.9%** on the 400-row set (first honest pass of the 70% bar; rules R33–R37 took it 48→59%, the 5k risk tranche to 76%). **Best T5b candidate: in-house DistilBERT** (domain MLM on 21.5M sentences, distilled from 405k Gemini==Sonnet consensus labels, gold pass; 3 seeds vs v8): novel merchants **64.5 vs 59.4**, residual **65.0 vs 59.8**, credit eval **88.8 vs 85.9**, T6-bound risk leaves **85.6 vs 75.9**, full pipeline **83.2 vs 82.2**, general +7–13pp, all CIs exclude zero; 360 rows/s CPU (accepted). `data/classifier_v8_risk_report.md`, `data/transformer_classifier_report.md` (iter 8). Do not quote the leaked 86.1% risk bar |
| Locked eval | v5 retired. v6 applied (**1,100** rows; Carlos labelled the 8 flags 27 Aug). Do not score until go/no-go |
| Full pipeline | **2,000** row-disjoint gold rows: T1–T5 then hinge v8 **82.2%** leaf, then transformer **83.2%**; rules-only T1–T7 **74.2%**; provider's own category alone **29.9%** leaf / 41.6% general (45% on provider-labelled rows). Residual (480 rows rules miss): transformer 65.0 / hinge 59.8 / provider 26.2. Direction split still matters (debit ~84% / credit ~57% with the de-leaked hinge; credits now served far better by v8/transformer). Python eval waterfall equals the BigQuery SQL on all rows (`src/check_waterfall_parity.py`). `data/waterfall_pipeline_report.md` |
| Experiment 3 | Live OB XGB reconstruction, full refit: **0.382 / 0.385** (month3 / month6). August 50-feature taxonomy XGB **0.477 / 0.562** (as-of filter applied). Development champion (0.7 XGB + 0.3 LGB, 1,654–3,150 leaf-level columns) **0.533 / 0.618**. **Same recipe capped at 50 features, single XGBoost: 0.508 / 0.588** (blend 0.508 / 0.583; blend at 100: 0.520 / 0.589; 200: 0.529 / 0.600) — **the 50-feature single-XGBoost champion is the reference carried forward (7 Sep)**; the XGB+LGB blend was tried, gained nothing at any cap, and is dropped; uncapped blend kept as ceiling. All development numbers; prospective test on the Feb–Apr 2026 cohort is the gate. `data/experiment3_champion_model_report.md`, `data/experiment3_champion_capped_report.md`. Granularity: with the August recipe (1 Sep) 275 / 69 / 29 groups indistinguishable, 17 close, ≤9 degrade; with the champion recipe uncapped (7 Sep) month6 rewards full leaf detail (275: 0.612 vs 69: 0.586), month3 does not; capped at 50 from the raw pool, 275 is worst (cap crowding). 287-leaf expansion no gain. `docs/taxonomy-granularity-conclusion.md` |
| Text / sequence scores on the risk model (OB-transformer repo) | On the single-XGBoost 50-feature champion (refit 0.265 PR-AUC / 0.588 Gini): + bge-base text score **+0.034 / +0.024** (locked recipe); + frozen 15M sequence-encoder score +0.031 / +0.029; **both 0.322 / 0.629**, above the uncapped champion, 52 columns — registered challenger. Our domain-pretrained DistilBERT is level with bge-base as the text encoder at half the cost; **bge-base stays locked**, ours is the registered alternative for the prospective test |
| Equifax extra tranche | **Rejected** — 6,518 vendors; unmatched filled = 4.4% of dump |
| LLM at runtime | Forbidden. Labelling is offline (Gemini 3.7 + Sonnet, Opus tiebreak) |

Full numbers and “do not” list: `CLAUDE.md` current-state block. Classifier write-up: `data/classifier_v5_retrain_report.md`. Frontier vs hinge (framing): `data/frontier_vs_classifier_report.md`. Head F1 pack: `data/classifier_v5_head_metrics_report.md`. General-head bake-off: `data/classifier_general_bakeoff_report.md`. Full pipeline (T1–T5 then hinge): `data/waterfall_pipeline_report.md`.

## Key numbers (do not mix dates)

- **Now (7 Sep 2026):** pipeline **83.2%** leaf on 2,000 rows (transformer) vs provider-native **29.9%**; risk model month6 Gini live **0.385** / August 50-feature **0.562** / capped champion (single XGB) **0.588** / uncapped **0.618** / capped + text + encoder **0.629**.
- **Coverage (26 Aug 2026):** Plaid T4 **56.5%** of 4.28M rows; T1–T4 **57.0%** on a 20% sample. Equifax T4 37.4%.
- **History:** 321-entry dictionary hit 47.8% of Plaid merchant volume; 21 Aug T4 was 39.1%. Those are superseded.
- Cross-provider conflict (unchanged finding): applying both crosswalks gives different leaves for 45.2% of shared-merchant volume — this is why T4 must override provider categories.
- Equifax: **65.8%** well-resolved from provider categories alone; 6,518 distinct vendors; **dead dump**.
- Plaid: 100% map to *a* leaf via native category, but historically **50.6% land on coarse leaves**; 203 of 275 leaves have no Plaid source.

## Before changing anything

1. **Don't prune categories on low IV.** IV is a risk-model feature-selection criterion, not a measure of categorisation quality. An earlier version pruned 274 leaves to 73 on that basis and had to be rebuilt. Use IV to decide where *aggregation* is safe.
2. **Don't aggregate gambling subtypes.** Combined IV 0.0053 vs 0.0498 for lottery alone. There's a test guarding it.
3. **Don't score locked v5 or v6** during development. Don't ingest `context_dependent` / T2 collision keys / `unclassified_*` into T4. Don't paste an old inline-UNNEST copy of `apply_crosswalk.sql` into BigQuery (current file is a table join; load the dictionary with `python src/load_t4_dictionary_bq.py`). Don't switch T6 from PFC `credit_category_detailed` to the older list `category` field (worse on leftover gold).

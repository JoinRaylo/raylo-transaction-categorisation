# Review of the categorisation programme and next steps (2026-09-02)

Agent review requested by Carlos: "check everything up to this point has been done
correctly, raise fundamental issues with fixes, decide the next steps, and assess the
Uncapped-style in-house transformer." Findings below are from reading the reports and
code, re-running local scorers, and three read-only BigQuery queries. Locked v5/v6 were
not scored. No tracked file other than this one was changed.

## 1. Verdict in one paragraph

The taxonomy, the waterfall design, the tranche-4 provenance containment and the
rejection log are sound and unusually well documented, and the direction of travel is
right. But the **measurement layer is weaker than the write-ups say**, and four things
are fundamentally wrong and must be fixed before promotion or before a transformer is
trained: (a) the whole stack is debit-shaped — credits are 25% of live Plaid rows and
half of the money, yet 0.65% of the classifier's training data and ~10% of every gold
set, and the pipeline scores **53% on credits vs 83% on debits**; (b) the risk-category
gold set is **not held out of training** (77.5% of its rows share a merchant with the
jsonl, 35% share the exact merchant+description), so the 86.1% risk bar that decided
the serving head is a memorisation number; (c) Experiment 3's Equifax training rows
include **post-proposal transactions** (no as-of filter), so only the Plaid-only rows
(0.449 / 0.488) are honest; (d) the T4 dictionary is direction-blind and still contains
**1,633 keys tranche 4 itself marks `context_dependent`** plus ~22k person-name keys
hard-wired to `transfer_p2p`. None of these invalidates the approach; all of them
inflate the current numbers, and each has a mechanical fix listed below.

## 2. Confirmed problems (evidence)

### 2.1 Credits are structurally under-served — the biggest gap in the stack

| Where | Credit share | Evidence |
|---|---:|---|
| Live Plaid rows | **24.7%** (1,056,650 of 4,279,707); **50% of GBP** (£272.8M of £546.9M) | BQ, 2 Sep |
| Live Plaid credits with blank merchant | **90.1%** | BQ, 2 Sep — T4 cannot touch them; they fall to T5/T6/classifier |
| `outputs/tuning_train.jsonl` (383,066 rows) | **0.65%** (2,493 rows) | local parse |
| Holdout / risk / pipeline / v6 gold | 9.8% / 9.6% / 9.5% / **3.7%** | local parse |

Serving hinge accuracy by direction (recomputed 2 Sep): holdout **20.4%** credit vs
57.6% debit; pipeline eval **25.7%** vs 67.1%; risk gold **44.1%** vs 84.0%.
Full pipeline (`outputs/waterfall_pipeline_rows.csv`): **53.1%** on the 179 credit rows
vs **83.4%** on 1,705 debit rows. Credit rows resolved by T4 are only **52.9%** right
(n=68); T6 native fallback on credits is 40.0% (n=70). The wrong credit gold leaves are
`refund_received` 28, `transfer_own_account` 14, `transfer_p2p` 12, `gambling_betting`
8, `salary` 7 — exactly the income/transfer distinctions the affordability and risk
features depend on (`salary_months`, `salary_credit_amt`, `days_since_salary` are all
top-gain features in Experiment 3).

Plaid's own credit categories are 44.1% `TRANSFER_IN_OTHER`, 31.1% `INCOME_SALARY`,
14.5% `TRANSFER_IN_SAVINGS` — i.e. T6 carries most live credits and is coarse.

**Why it happened:** `build_tuning_dataset.py` samples rows per labelled *merchant
string*, and labelled merchant strings are overwhelmingly debit-side card merchants.
Gold sets are true-random over rows but the labelling packs were T4-miss / merchant-
driven. Nobody had cut any table by direction.

**Fix (ordered):**
1. Add a `direction` split to every report the iteration suite prints
   (`confusion_analysis.py`, `score_waterfall_pipeline.py`, `compare_classifier_versions.py`).
   A credit-side minimum bar (say ≥70% on `salary`, `benefits_state`,
   `refund_received`, `transfer_own_account`, `returned_payment`, `loan_disbursement`)
   becomes a promotion gate alongside the existing risk bar.
2. Build a **credit-side labelling tranche**: stratified sample of live Plaid credits
   (blank-merchant included) keyed on `(description, amount band, native category)`,
   Gemini+Sonnet consensus with the existing prompt, Carlos on disputes. 20–30k rows is
   enough to lift the jsonl credit share from 0.65% to ~7%; oversample to ~15% at train
   time. Label at the row, not the merchant.
3. Make T4 direction-aware (below).
4. Re-score credits before/after; do not touch v6.

### 2.2 The risk-category gold set is in the training data

`data/gold_transactions_risk_categories.csv` (711 rows, 192 merchants) is described as
"held out of training". The file is not read as a source, but Tier B of
`build_tuning_dataset.py` fetches random Plaid rows for every labelled merchant, and
the bookmakers/lenders in the risk set are tranche-4 merchants. Recomputed 2 Sep:
**551/711 rows (77.5%) share a merchant with the jsonl; 252 (35.4%) share the exact
`(merchant, description)`; 154 (21.7%) share the full row key.** 623/711 (87.6%) are
also T4 dictionary merchants, so in the real waterfall the classifier never serves
them. The `RISK_GUARD` block only excludes risk merchants from the oversample copies,
not from the base Tier B rows. Consequence: the hinge-vs-logreg decision, the v5b/v5c/
v5d rejections and every "risk bar 86.1%" quote rest on an in-sample number; the honest
figure is the T5b residual bar (75.3%, small n) buried in
`data/t5b_residual_gate_report.md`. Similarly, 378 of the 1,884 pipeline-eval rows
(20.1%) share a merchant with training — 377 of them are the risk rows.

**Fix:** add risk-gold merchants to the Tier B exclusion (same mechanism as the holdout
carve-out), rebuild the jsonl (holdout MD5 must not change), retrain v5, re-score. Expect
the risk bar to drop; if it drops below 70%, that is the true state and the credit/risk
labelling tranche in §2.1 is the remedy, not a re-tune. Report the risk bar on
T6-bound rows only, since that is what T5b serves.

### 2.3 T4 dictionary is direction-blind, and carries keys the labels say are ambiguous

Direction: `taxonomy/merchant_dictionary.csv` has no direction column; the SQL joins on
merchant key only. Live Plaid: 104,509 filled-merchant credits, **93.7%** hit T4, and
**73.5%** of those hits map to a debit-shaped leaf (groceries, fuel, pub_bar…). The T2
`refund` / returned-payment / gambling-credit rules catch part of this, but only when
the narrative says so.

Ambiguous keys: **1,633** dictionary keys are merchants that tranche 4 finally marked
`context_dependent` (`miss`, `dad`, `mum`, `james`, `sarah`, `savannah` →
`transfer_p2p`; `credit` → `revolving_credit_repayment`; `trading` →
`investment_trading`; `new zealand` → `alcohol_wine`; `uk london` →
`marketplace_general`). They entered from tranche 3 and were never re-evaluated when
tranche 4 downgraded them; `is_t4_eligible_row` checks only `review_status` and
`unclassified*`. A further 41 agent-tier keys disagree with their own tranche-4 final
leaf. And **22,475 keys (24.5%) resolve to `transfer_p2p`**, ~2,540 starting with a
title and ~2,370 initial+surname: because T4 fires before T5 and ignores direction and
narrative, rent to a private landlord, informal loan repayments and tradesman payments
on those names can never reach R13 or the classifier — this quietly undoes the rent
work (backlog 5) and contradicts "do not treat FPS as `transfer_p2p` by default".

**Fixes:** (1) drop the 1,633 `context_dependent` keys and the 41 disagreeing keys from
T4 (add a test: no dictionary key may have tranche-4 tier `context_dependent`);
(2) move person-name keys out of T4 into a T5-level default that fires *after* R13 /
loan keywords, or keep them in T4 only for debits with no debt/rent keyword in the
narrative; (3) add a `credit_leaf` column (default `refund_received` for goods/services
merchants, `salary`/`income_other_unspecified` for employers, `gambling_unspecified`
for bookmakers, `loan_disbursement` for lenders, null = fall through) and pick by
direction in both `match_t4()` and the SQL. Uncapped's "direction constraints zero out
impossible categories" is the same idea; `cash_flow_type` in `taxonomy.csv` already
defines the legal leaves per direction, so the classifier can mask illegal leaves at
`decision_function` time today at zero training cost.

### 2.4 Experiment 3: Equifax training rows use post-proposal transactions (no as-of filter)

`_eqx_fetch_sql` in `src/experiment3_xgb_pipeline.py` (lines ~307–368) joins every
Equifax transaction for a matched proposal with **no `PostDate <= proposal_created_at`
predicate**; `as_of` is used only for the 30/90-day ratios and `days_since_*`. Measured
on `outputs/experiment3_xgb_proposal_features.parquet`: `days_since_salary` /
`_returned_payment` / `_gambling` / `_payday` are **negative** for 5.4–7.7% of Equifax
proposals (down to −944 days); Equifax `total_months` reaches 16; 1,984 of 36,126
Equifax proposals (5.5%) have post-proposal rows and their month3 bad rate is **6.25%
vs 11.1%** for the rest. Plaid rows are clean by construction (Asset Report is pulled at
application). So the pooled Equifax+Plaid headline (0.477 / 0.564) is trained partly on
features not knowable at decision time; the **Plaid-train-only rows (0.449 / 0.488)
are the honest like-for-like numbers**. OOT scoring itself is 100% Plaid and unaffected.

**Fix:** add `DATE(t.PostDate) <= DATE(c.financial_proposal_created_at)` (and a
189-day floor to match the live history length) to the Equifax fetch, rebuild features,
re-run the pipeline, the ladder and the champion search. Until then quote Plaid-only.

### 2.5 Experiment 3: the "live" comparator is a handicapped reconstruction

`_run_one` fits `live Plaid XGB` on the inner 80% split with early stopping and never
refits on the full train window, while every taxonomy model is refit on 100%. The
stress test already measured the full-refit live model at **0.392 / 0.411** (3 seeds)
vs the published 0.403 / 0.386 — month6 live is understated by ~0.03. The ladder
report's "reproduces the model actually in production exactly" is not true: it
reproduces its own reconstruction; the production model's real training set,
hyperparameters and (per `docs/miv-audit-results.md`) its single `month3_1plus_pia`
target were not used. **Fix:** refit live on full `plaid_train` (mirror the Plaid-only
branch), or better, obtain the frozen production scores for the OOT proposals.

### 2.6 Experiment 3 uplift is a feature-bundle effect, not a taxonomy effect (already documented, must not be lost)

`data/experiment3_granularity_stress_test_report.md` §"Methodological gaps" is correct
and should be treated as binding: OOT rows were categorised with a dictionary and
classifier built *after* the OOT window (transductive vocabulary leakage); the live
comparator is an in-repo reconstruction trained on 80% of the window (full refit gives
0.392 / 0.411, not 0.403 / 0.386); the same-20-feature ablation is inconclusive and
flips sign; the OOT windows were reused for selection. The **development champion**
(0.533 / 0.618) is a search over those same windows and must be described as such.
Stakeholder wording in `docs/taxonomy-275-stakeholder-summary.md` is already careful;
`README.md` / `CLAUDE.md` headline lines ("every rung beats live") are not, and should
adopt the stress-test wording.

### 2.7 The Python evaluation waterfall is not the SQL waterfall

`final_evaluation.our_leaf()` (used by `score_waterfall_pipeline.py`) runs T2 →
gambling-credit → refund → returned → **T4 → T5 → native (T1/T3/T6)**. The generated
SQL runs T1 native and **T3 mechanism override before T4**. So Equifax
`Identified Salary | General Groceries` with vendor `tesco` is `salary` in SQL and
`groceries` in the Python eval — the exact bug T3 exists to fix (4.1% of Equifax
volume). Tier names also differ (`T4_dictionary` vs `T4_merchant_dictionary`). The
80.5% headline is therefore measured on a slightly different waterfall from the one
in `sql/`. **Fix:** make `our_leaf()` call a shared ordered tier list that the SQL
generator also emits, add a test that asserts T1/T3-before-T4 in both, and re-run the
pipeline scorer (the number will move a little; both directions possible).

### 2.8 Abstention does not exist in code; the SQL is a coverage report

CLAUDE.md says abstention is a margin gate "tuned on holdout". No code applies a margin
cut-off: `score_waterfall_pipeline.py` drops `_margin` and serves argmax. "Abstain" is
a *learned class* — `unclassified_other` has 15,003 training rows — plus a hard-coded
`_promote_gambling` override. Either is defensible, but the documentation must say
what is actually served, and if a threshold is ever tuned it must be on
`tuning_val.jsonl`, not the holdout (which has already chosen head, prompt and model).
Separately, `sql/apply_crosswalk.sql` uses `TABLESAMPLE` and ends in
`GROUP BY provider, resolution_tier` — it is a sampled coverage report, not a per-row
categoriser. Nothing in `sql/` can be promoted as-is; a per-row version with
transaction and proposal ids is a prerequisite for both production and the as-of
Experiment 3 rebuild.

### 2.9 Gold labels are mostly LLM-drafted, agent-adjudicated; the headline is skewed by it

- **v6 (locked):** `final_leaf == gemini_leaf` on **1,001/1,100 (91%)**; 8 rows by
  Carlos; 282 disagreements decided by an agent. At go/no-go it will mostly measure
  agreement with Gemini 3.7 Flash — the same model that drafts tranche-4 labels
  (`agent_consensus` is Gemini==Sonnet on 30,479/30,479).
- **v3/v4/risk:** workbook notes are 100% agent-style; v3 has 746/1,500 and v4 167/900
  rows whose label was *copied from the v2 merchant-level leaf without re-review*
  (`build_gold_v3_volume.py` "established" pre-fill). Those v2 merchants are the head of
  T4, so gold == dictionary by construction on those rows (T4 scores 92–93% on v3/v4).
  It also asserts one-leaf-per-merchant, which CLAUDE.md §4 says is false.
- **Skew in the 80.5%:** on `outputs/waterfall_pipeline_rows.csv` the full pipeline is
  **77.0% on human-reviewed v2 rows (n=1,037) vs 84.8% on LLM-drafted v3/v4/risk rows
  (n=847)**; residual-hinge 57.6% vs 68.5%. The human-only headline is 77.0%.
- **Holdout patched against the system under test:** `outputs/_audit_gold_leaf.py`
  flags gold rows that disagree with the dictionary/T2/T5, and `_patch_gold_leaves.py`
  rewrote 17 merchant-level edits (holdout MD5 changed twice). Each edit may be right,
  but the procedure biases the frozen set toward the pipeline.
- **Noise floor:** n=1,055 gives ±3.0pp; hinge vs logreg on the holdout is p≈0.03
  (McNemar 59/38); the v5b/v5c/v5d deltas (+0.7 / +1.4 / +3.8pp) and risk-bar moves
  (n=619, ±2.7pp, and leaked per §2.2) are single-run and unpaired. `car_lease` 20/20 →
  3/20 is 20 rows from a handful of merchants.

**Fixes:** apply the tranche-4 provenance discipline to gold: add a `label_source`
column (`human_carlos` / `agent_adjudicated` / `established_copy` / `llm_consensus`) to
every gold file; report every headline split by that column; before go/no-go Carlos
blind-reviews a stratified ~300-row slice of v6 (all credits, all risk leaves, random
debits) and the human-vs-final agreement is published as the label-noise ceiling; stop
copying merchant-level leaves onto new rows; freeze gold edits behind a written
adjudication note that does not consult the pipeline output; report paired bootstrap
CIs for every model-vs-model decision (the Experiment 3 stress test already does this).

## 3. Risks (manage, do not block)

- **Class imbalance in the jsonl:** `transfer_p2p` is 27% of training rows (103k);
  `unclassified_other` 15k; 68 leaves have <100 rows, 20 have <20. Any encoder model
  will inherit the `transfer_p2p` prior (the MiniLM run defaulted to it). Cap head
  classes at ~20k rows, oversample thin risk leaves.
- **Merchant == description** in 24% of training rows (Plaid-shaped); the model
  learns little narrative structure. Fine for T4-miss card spend, poor for transfers.
- **Dictionary provenance:** 53,011 of 91,824 keys are `agent_tiebreak` (one Opus
  call breaking a Gemini/Sonnet split); ~1.9% of keys are human-touched;
  `review_status` is `approved` on 100% of rows so the SQL filter is a no-op and the
  column carries no governance signal; `confidence` is `medium` on 98.7%. 22,475 keys
  (24%) are `transfer_p2p`, including bare first names (`mum`, `dad`, `kim`, `lee`,
  `zoe`) as exact keys, and 409 keys are ≤3 characters. Sample-audit 200 tiebreak keys
  by live volume; give `review_status` real values (`agent`, `human`, `carlos`).
- **Over-broad T5 rules on the long tail:** simulated against the 91,824 dictionary
  keys, R01 (`mr|mrs|ms|dr` prefix → p2p) would mislabel `dr martens`, `mr pretzels`,
  `mrs l m simms` (rent); R02 (initial+surname) `c boots`, `d foodhub`; R03 (family
  words) `dad loan`, `mum owed`; R06 `(bingo|casino)` has no word boundaries
  (`bingol kebab`, `petit casino`). They run after T4 so damage is confined to
  undictionaried strings, which is exactly the long tail. Add word boundaries to R06;
  add exclude-patterns or move R01–R03 below the classifier when it is confident.
- **No reviewer/provenance field on rules:** all 63 commits are authored
  `carlos-raylo`; only R31/R32 and the `T2_CARLOS_PACK` are attributed to Carlos in
  comments; the 125-row T2 CSV has no reviewer column. Add one.
- **Dead/thin leaves:** 5 leaves have zero training rows and zero dictionary keys
  (`account_misuse`, `balance_transfer_fee`, `housing_benefit`, `interest_charged`,
  `savings_interest_received`); 27 leaves have <20 training rows; 28 leaves are
  `_other`/`_unspecified`/`_general` catch-alls. Keep them (IV must not prune the
  taxonomy) but expect the classifier never to emit the dead five.
- **`is_recurring_income`** is populated on 3/275 rows and not emitted anywhere: dead
  column, delete or fill.
- **SQL maintainability:** 1,717 lines, every predicate written four times (leaf and
  tier CASE × two providers); T2 patterns are raw strings, T5 patterns double-escaped;
  tests grep the SQL text and never dry-run it; `load_t4_dictionary_bq.py` does
  `WRITE_TRUNCATE` from the working tree with no version hash. NULL direction is
  silently mapped to `debit`.
- **No serving path for T5b:** the hinge bundle (65 MB, gitignored) is only invoked by
  eval scripts; production needs a BQ remote function or batch job.
- **Serving stack for the classifier does not exist yet** (no dbt, no job). This is
  correct for research but is the long pole for promotion.
- **DeBERTa fine-tune was started (27 Aug, `outputs/distill_models/deberta_v3_small_ft/`)
  but never finished or reported**; only `labels.json` and `class_weights.pt` exist.
  Not referenced in CLAUDE.md. Either finish it under §5 or delete the directory.
- **Uncommitted work:** 7 modified + 8 new files including the granularity ladder,
  champion model and stress test. Commit before anything else changes.

## 4. What is fine (keep)

Taxonomy design and the orthogonal dimensions; T1–T7 precedence with recorded tier;
T2-before-T4 handling of provider entity collisions; merchant-disjoint holdout with MD5
guard; risk-category gold + `confusion_analysis.py` bar; locked v6 never scored;
signed GINI; provenance containment (human_reviewed = 4); rejection log in CLAUDE.md §9;
the finding that head examples transfer (do not train residual-only); hinge as the
serving head.

## 5. The transformer question (Uncapped post + literature)

**What Uncapped actually did** (`weareuncapped.com` blog, read 2 Sep): a ~30M-parameter
encoder with a classification head (DistilBERT/MiniLM class), trained on **millions of
underwriter-corrected transactions** accumulated over years, direction constraints
that zero impossible classes, direction-merged classes during training and split at
inference, 10k transactions in <7 s on CPU, 97–99% on a handful of high-impact
business categories (revenue, debt repayment, tax). No architecture novelty; the data
and the constraints are the story.

**What the literature adds:** Flowcast (arXiv 2305.18430) — weak supervision (Snorkel
label model over heuristics + FastText anchors) with a discriminative DNN, beating Plaid
by ~20 points on hard categories; their key finding is that **off-the-shelf English
embeddings generalise badly to bank text and a transaction-corpus-trained FastText
was the pivotal improvement**. Trustly (arXiv 2511.12154) — BERT/DistilBERT pretrained
with MLM on 10M accounts of `[TYPE] [AMT bucket] [NAME] description` sentences, then
linear probes; DistilBERT wins most downstream tasks. Two-headed DragoNet (arXiv
2312.07730) — transformer + taxonomy-aware attention enforcing the macro/micro
hierarchy, 93–95% macro F1. FreeAgent (2021) — DistilBERT replaced a linear SVM whose
vocabulary had grown to tens of millions; accuracy "slightly higher"; `padding=longest`
was the main engineering lesson. SME paper (arXiv 2508.05425) — fine-tuned FinBERT 73%
vs TF-IDF 50% vs GPT-4o zero-shot 60%, with LLM-generated paraphrases for minority
classes.

**How that maps to our evidence.** We have already run the naive version of this twice
and lost: MiniLM 1-epoch (CLS bug) and MiniLM mean-pool (holdout 52.1 vs hinge 53.8;
leftover −4.7pp; risk bar 68.7 FAIL). Both used a general-English checkpoint, one
epoch, no domain pretraining, no class balancing, no direction masking, on a corpus
that is 0.65% credit. Uncapped's gap over third parties came from **years of human
corrections**, which we do not have. So the honest expectation is: a well-built
encoder should beat char-TF-IDF hinge by a few points on novel merchants and by more on
narrative-heavy transfers/credits, not by the 40 points Uncapped reports over a vendor.
The frontier gap (Gemini 83.9% vs hinge 53.9% on holdout) shows the headroom is real
and is mostly world knowledge about merchants, which a 30M encoder acquires only from
our data.

**Recommendation: yes, build it, but as a staged experiment with pre-declared kill
criteria, and only after the credit fix (§2.1) — otherwise it will learn the same
debit-only distribution.**

Stage 0 — data (1 week, no GPU):
- Fix credits (§2.1), cap `transfer_p2p`, oversample thin risk leaves.
- Build the **pretraining corpus**: every Equifax raw `Description` (44.7M) + every
  Plaid `original_description`/`merchant_name` (4.28M), unlabelled, formatted as
  Trustly-style sentences `[DEBIT|CREDIT] [AMT bucket] merchant | description`.
- Build a **weak-label corpus**: run the current SQL waterfall over all 77M rows and keep
  T1–T4 resolutions (high precision) as silver labels; keep T5b/T6 rows unlabelled.

Stage 1 — domain-adapted encoder (2–3 days on the M5 Pro or one A10 hour):
- Start from `distilbert-base-uncased` or `microsoft/deberta-v3-small`; train a
  **transaction-specific WordPiece/BPE tokenizer** (bank text is not English: `CD`,
  `FPS`, `DDR`, `PFS`, truncations) or extend the vocab; MLM for 1–2 epochs on the
  pretraining corpus. This is the step every paper says mattered and the step we
  skipped.
- Sanity gate: nearest neighbours of `stepchange`, `pfs`, `vzw`-style tokens look
  like categories, as in Flowcast Fig. 6.

Stage 2 — classifier head:
- Multi-task: leaf (275) + general (29) heads, hierarchy-consistency loss (DragoNet
  style, cheap), **direction mask** from `cash_flow_type` applied to logits.
- Train first on silver (T1–T4 waterfall labels, tens of millions of rows, 1 epoch),
  then fine-tune on the gold-quality jsonl (383k + credit tranche) for 3–5 epochs with
  class-balanced sampling; `padding=longest`, max_len 64.
- Calibrate margins/probabilities on `tuning_val.jsonl`; abstain threshold tuned on
  val, not the holdout.

Stage 3 — decide (kill criteria, all vs the *de-leaked* serving hinge from §2.2, same
scorers, paired bootstrap CIs):
- Holdout T6-bound leaf ≥ hinge +3pp; pipeline residual ≥ hinge +3pp; T6-bound risk bar
  no worse than hinge; credit-side bar ≥ hinge +10pp; CPU throughput ≥ 1,000 rows/s on
  one core-equivalent (10k in <10 s is Uncapped's number). Miss two → stop, keep hinge.
- If it passes: it replaces T5b only. T1–T4 stay above it; T6/T7 stay below.

Estimated effort: ~3 weeks of one engineer including the credit tranche; compute cost
under £100 if done on cloud GPU, zero on the M5 Pro (MiniLM took 12 min; DistilBERT
MLM on ~50M short sentences is roughly 6–10 h on MPS or ~1 h on one A100).

## 6. Recommended order of work

**Week 1 — make the numbers honest (no new modelling):**
1. Commit the current tree. Reword README/CLAUDE.md headlines: Experiment 3 = Plaid-only
   0.449 / 0.488 vs full-refit live 0.392 / 0.411 pending the as-of fix; granularity
   per the stress-test wording; pipeline 80.5% shown with the 77.0% human-only split.
2. Exclude risk-gold merchants from Tier B; rebuild jsonl; retrain v5 hinge; re-score
   (holdout MD5 unchanged). Publish the risk bar on T6-bound rows.
3. Purge the 1,633 `context_dependent` + 41 disagreeing T4 keys; add the guard test;
   reload BQ. Re-run the pipeline scorer.
4. Align `our_leaf()` tier order with the SQL (T1/T3 before T4); add a parity test that
   runs both on the pipeline eval and asserts identical leaves.
5. Direction split and credit-side bar in `confusion_analysis.py`,
   `score_waterfall_pipeline.py`, `compare_classifier_versions.py`; `label_source`
   column on every gold file.
6. Experiment 3: add the `PostDate <= created_at` filter and refit live on full train;
   re-run pipeline, ladder, champion; publish paired CIs.

**Weeks 2–3 — fix the data gaps:**
7. T4 `credit_leaf` column + direction-aware match in Python and SQL; person-name keys
   demoted below the rent/loan keywords.
8. Credit labelling tranche (20–30k live Plaid credits, row-level, blank-merchant
   included); ingest; retrain; re-run the suite. This should move the pipeline headline
   more than any further debit-side dictionary work.
9. Carlos blind-review slice of v6 (~300 rows) — label-noise ceiling for the promotion
   number.

**Weeks 3–6 — the transformer (Stages 0–3 above), only after 2, 5 and 8.**

**In parallel, ownership conversations:**
10. Per-row categorisation SQL (transaction + proposal ids) and a serving path for T5b
    (BQ remote function or batch job); dbt model for T1–T4/T6. Needed for both
    production and the as-of Experiment 3 rebuild.
11. Freeze taxonomy/dictionary/classifier with an effective date; score the next
    matured outcome window once; score v6 once, at the same gate.
12. Raise the 90-day Asset Report request (CLAUDE.md §10) with the Plaid-integration
    owner — still the highest-leverage single fix in the programme.

# Evaluation dataset audit — 15 September 2026

Assessment: useful development regression suite; unsuitable as a single unseen master benchmark without a new collection and provenance audit.

Read-only audit of hash-pinned permitted sources using the existing evaluation adapters. No models run; no new accuracy measurements; no v5/v6 file contents opened. Counts are original gold-label counts, not adjudicated truth. Source code and documented construction were inspected for the locked sets.

## Existing datasets

| Dataset | Rows | Credits | Blank merchant | Labelled leaves / 275 | Leaves with <20 rows among those present |
|---|---:|---:|---:|---:|---:|
| gold_credit_eval | 2,000 | 2000 | 1924 (96.2%) | 55 | 42 |
| gold_merchant_labels | 1,563 | n/a | n/a (merchant task) | 184 | 171 |
| gold_tail_labels | 247 | n/a | n/a (merchant task) | 70 | 69 |
| gold_transactions | 5,335 | 517 | 0 (0.0%) | 246 | 176 |
| gold_transactions_risk_categories | 711 | 68 | 84 (11.8%) | 50 | 31 |
| gold_transactions_risk_t6bound | 400 | 0 | 303 (75.8%) | 73 | 70 |
| gold_transactions_v2 | 1,500 | 231 | 0 (0.0%) | 176 | 159 |
| gold_transactions_v2_batch2 | 1,500 | 192 | 0 (0.0%) | 222 | 212 |
| gold_transactions_v3_volume | 1,500 | 89 | 0 (0.0%) | 134 | 116 |
| gold_transactions_v4_slm_volume | 900 | 21 | 0 (0.0%) | 115 | 104 |
| gold_v2_slm_eval_holdout | 1,055 | 103 | 0 (0.0%) | 199 | 194 |
| gold_v3_eyeball | 1,500 | 89 | 0 (0.0%) | 133 | 115 |
| gold_v4_eyeball | 900 | 21 | 0 (0.0%) | 116 | 105 |
| tuning_validation | 5,000 | 9 | 0 (0.0%) | 194 | 158 |
| gold_pipeline_eval | 2,000 | 176 | 68 (3.4%) | 209 | 182 |

## Interpretation

- 26,111 nominal rows across the 15 sets must not be described as that many independent held-out transactions. The 11 complete-transaction tasks contain 18,590 rows but only 8,240 distinct full input signatures; 28 signature groups carry differing gold labels between snapshots. These signatures are not verified real transaction IDs.
- Among 8,212 consistent signature groups, 256/275 leaves are represented; 186 leaves have fewer than 20 examples, including absent leaves. This union includes historical training-role material and must not be used as a clean holdout score.
- The 5,335-row unified gold file explicitly marks 3,956 rows as train. The training builder consumes that role. This audit did not independently rematch every row to every historical model artefact.
- The 1,055-row holdout has no blank merchants and has been repeatedly used to compare models and make development decisions. The 5,000-row validation has 4,991 debits and 9 credits and was used for seed selection.
- The 2,000-row pipeline benchmark has 176 credits, 68 blank merchants, and 209 leaves. Its coverage includes all 29 general categories but only 13 salary, 1 pension, 8 rent, 11 mortgage, 7 council-tax and 0 unarranged-overdraft examples. These counts cannot substantiate narrow per-leaf regression guarantees.
- The 2,000-credit set has 1,924 blank merchants and 1,033 transfer_p2p labels. Label provenance: 1,483 agent_consensus, 247 agent_review, 242 agent_tiebreak, 28 human_reviewed. Existing reports cite 84.3% human agreement on a blind slice; that is a sample result, not a verified error rate for every row.
- Both the credit and T6-bound risk sets date from May–October 2025. They do not measure recent transaction drift; newly labelled is not the same as newly occurring.
- The 400-row T6-bound risk set has only debits and 303 blank merchants. Its 174 risk-leaf rows are a useful targeted stress slice, not a representative engine benchmark.
- The current suite contains no exact-merchant Waitrose credits. Synthetic payroll tests establish prescribed behaviour; they do not fill that real-data gap.
- v6 is documented as 1,100 rows (700 Plaid, 400 Equifax), selecting one row per novel merchant with a non-empty merchant. It is a novelty confirmation set, not representative traffic. Existing once-at-go/no-go restriction remains; it was not scored or opened.
- Domain-pretraining source builds from both providers with no evaluation-membership exclusion in build_pretrain; the exclusions are applied to silver-label creation separately. Combined with the documented full-corpus MLM run, this prevents a never-seen claim without an actual corpus-overlap audit. It does not establish an exact overlap count.
- The historical pipeline and unified/holdout CSVs lack stable transaction/customer/account IDs and dates. The newer credit and T6-bound risk sets do retain transaction_date; this does not supply full customer/account isolation or historical exposure evidence. A new master needs stable identity and temporal provenance throughout.

## Recommended master benchmark design

One versioned, governed evaluation asset with separate scored cohorts and protected partitions. Never combine targeted oversampling with representative traffic into one unweighted headline.

1. Representative core: initially about 10,000 fresh transactions sampled across the actual Plaid service population, customers, accounts, banks and time. Retain both debit and credit, blank/filled/misleading merchants, native-category quality, pending status and narrative variation at measured traffic frequencies. Report Equifax separately if retained for research.
2. Challenge cohort: initially about 5,000 additional real independently labelled transactions, increasing where quotas demand it. Cover critical income/debt/risk leaves, refunds vs salary vs returned payments, known vs novel merchant families, and ambiguous records. Aim initially for 100–200 independent examples in priority leaves and explicit support reporting for rare leaves; exact quotas require the source population profile and a power calculation.
3. Blind confirmation reserve: initially about 5,000 separately held-out transactions, including representative and critical-category strata. Access only for predeclared promotion decisions, then replenish with genuinely fresh data. Keep legacy v6 separate under its existing rules.

These are planning sizes, not a demonstrated optimal sample size. At 85% accuracy the 95% Wilson interval is about 83.37–86.50% for n=2,000 and 84.29–85.69% for n=10,000, assuming independent observations. For a class with 200 examples it is still about 79.39–89.29%. Customer/merchant clustering and label noise reduce effective information. Paired regression-detection power depends on discordant predictions and the chosen non-inferiority margin, not this interval alone.

## Governance and scoring

- Never-trained-on can be preserved. A repeatedly inspected benchmark becomes development feedback even when its rows are excluded from fitting; retain a separate blind reserve and fresh temporal refreshes.
- Known merchants are necessary to measure the full engine: unseen transactions can legitimately belong to merchants already in the dictionary. Reserve entity/family-disjoint evaluation for the novelty cohort; do not remove every familiar merchant from representative evaluation. Audit exact and near-duplicate model inputs and report how exclusion/grouping changes the sampled population.
- Define a cutoff and traceable source snapshot covering supervised training, transformer domain pretraining, distillation, tokenizer/vocabulary fitting and historical rule/dictionary sources. Prefer new transaction events after all training extracts; inspect recurring text overlap rather than assuming a new row ID implies unseen model input.
- Freeze stable pseudonymous transaction/customer/account identifiers, grouping keys, original prediction-time fields, sample weights/strata, dates, label provenance and taxonomy version. Protect evaluation membership before any labelling batch enters training, rule/dictionary proposals, prompt examples or LangGraph evidence retrieval.
- Independent human labels should be blind to the engine/model output. Use two independent judgements and adjudication for disagreements; critical/ambiguous cases need careful review. Agreement between the same LLM teachers used for training is insufficient ground truth. Explicitly mark insufficient evidence; do not force salary from a large retailer credit.
- Run the same labels through each standalone head and the actual deployed waterfall separately. Report traffic-weighted leaf/general accuracy, per-leaf precision/recall/F1, risk false positives/negatives, credit/refund/salary slices, coverage/abstention, and both fixed-baseline and actual residual cohorts.
- Every behavioural change or retraining batch runs the repeatable suite and new stable master regression partition. Promotion requires predeclared overall/critical-category non-inferiority criteria, paired customer-aware uncertainty and review of regressions. A non-significant difference is not proof of equivalence. The blind reserve is not consulted after every experiment.
- Version rather than overwrite labels/membership. A v2 benchmark is compared by rerunning both baseline and candidate on v2, retaining v1 history. Training examples belong in separate assets even when sourced from the same new labelling campaign.

## Reproduction and source references

`coverage.json` contains exact source hashes, counts, columns, provenance tags and per-leaf supports. `audit.py` reproduces it with the app Python and current monorepo/research paths. It imports only the permitted inventory/adapters and performs no model inference.

- Research construction: `src/build_gold_v6_locked.py`, `src/build_tuning_dataset.py`, `src/transformer/build_corpus.py`, `src/score_waterfall_pipeline.py`.
- Research history: `data/classifier_v6_deleaked_report.md`, `data/classifier_v7_credit_report.md`, `data/distillation_labels_report.md`, `data/transformer_classifier_report.md`, `docs/project-summary.md`.
- [Scikit-learn: test-data leakage](https://scikit-learn.org/stable/common_pitfalls.html#data-leakage).
- [Dwork et al.: adaptive analysis and holdout reuse](https://proceedings.neurips.cc/paper/2015/hash/bad5f33780c42f2588878a9d07405083-Abstract.html).
- [NIST: confidence intervals for proportions](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm).

Confidence: high in the measured coverage counts and documented construction restrictions; limited in historical never-seen claims until all model-source artefacts are audited. No fresh production distribution was queried, no datasets were relabelled, and no pipeline or staging changes were made.

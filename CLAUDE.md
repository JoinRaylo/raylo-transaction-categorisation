# CLAUDE.md — context for continuing this work

Research repo for Raylo's unified transaction categorisation. Read this before touching anything.

Full design rationale and stakeholder-facing write-up:
**Notion — [Unified Transaction Taxonomy: Research, Evidence & Design](https://app.notion.com/p/3bf5bb4b4a6581b6807add39671e56c2)**

Owner: Carlos (AI Engineer, AI Acceleration team). This is **research**, not production. Nothing here is referenced by any dbt model or scheduled job, and it must stay that way until explicitly promoted.

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
| T2 | Compound rules (gig income) | in `sql/apply_crosswalk.sql` |
| T3 | **Mechanism-override primaries** | in `sql/apply_crosswalk.sql` |
| T4 | Merchant dictionary | `taxonomy/merchant_dictionary.csv` — wired in `sql/apply_crosswalk.sql` 2026-08-20 |
| T5 | Deterministic regex rules | `taxonomy/rules/deterministic_rules.csv` — wired in `sql/apply_crosswalk.sql` 2026-08-20 (R13/rent disabled via an `enabled` column, not a string flag) |
| T6 | Provider crosswalk | in `sql/apply_crosswalk.sql` |
| T7 | `unclassified` | explicit, monitored |

**T3 (mechanism override) was discovered by running the crosswalk on real data** and is easy to miss: 13 Equifax primaries (`Identified Salary`, `Refund`, `Benefits`, `Welfare`, `Pension Payout`, `Tax Refund`, `Cash Back`, `Cash Machine`, `Cash Deposit`, `Interest`, `Interests and Dividends`, `Balance Transfers`, `Adjustments`) determine the leaf **regardless of merchant**. Without it, `Identified Salary | General Groceries` wrongly resolves to `groceries`. 4.10% of volume.

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
| TF-IDF + logistic regression v2 (`outputs/distill_models/tfidf_logreg_v2.joblib`) | 32.0% | 37.6% | — |
| Sentence-embedding (MiniLM) + logistic regression, same training data | 27.6% | 32.5% | — |
| Local vanilla Gemma (no fine-tune) + full taxonomy in context + constrained decoding | 17.7% | 36.7% | 3.65 rows/sec |
| Vanilla Gemma, taxonomy as text hint only (no constrained decoding) | 3.5% | 8.2% | 17.5% in-vocab |
| Vanilla Gemma, no taxonomy context at all | 0.0% | 0.0% | 0% in-vocab |

**Genuine, load-bearing negative-interaction finding**: giving the *fine-tuned* local SLM the full taxonomy in its context window (plus constrained decoding to force a valid leaf) makes it WORSE (50.0%→39.5% leaf) — the fine-tune already learned direct merchant→leaf mappings and the extra list appears to distract it. The same technique helps the *vanilla* (non-fine-tuned) model enormously (0–3.5%→17.7%), because it never learned the taxonomy any other way. **Implication: a fine-tuned-SLM deployment should NOT show the full taxonomy at inference — closed-vocabulary direct generation from the fine-tune alone is both faster and more accurate.**

**Gemini's temperature=0 is not fully deterministic** (unlike the local MLX model's provably-deterministic greedy decode) — validated empirically rather than assumed, per Carlos's explicit request. Two identical temp=0 calls against Gemini 3.7 Flash differed on 5/40 rows (12.5%). However, **the 3-run aggregate benchmark above is stable** (leaf SD ≈0.15pp, general SD ≈0.12pp across 3 full 1,055-row runs) — row-level flips appear to roughly balance correct↔wrong, so single-run benchmark numbers for this model are trustworthy at the aggregate level even though individual predictions aren't.

**Platform facts (verified, don't re-derive):** Opus 5 / Sonnet 5 / Opus 4.8 all reject the `temperature` parameter (400 error, "deprecated for this model") — only Haiku 4.5 and older Sonnet 4.6/Opus 4.6 accept it. Gemini's `response_schema` rejects string enums above ~100–150 values (workaround: numbered index + bounded integer, mapped back locally). Gemini 3.7 Flash is only available via the direct Gemini Developer API (`vertexai=False` + explicit `api_key`) in this project/region, not Vertex AI — a stray un-stopped background process using the wrong (Vertex) config previously caused confusing 404s while debugging this; always verify no stale background job is still writing to a shared log before trusting its errors. Gemini 2.5's "thinking" can silently consume the whole output-token budget unless `thinking_config=ThinkingConfig(thinking_budget=0)` is set.

**Gemini 2.5 Flash fine-tuning (Vertex AI supervised tuning) works end-to-end and is essentially free.** Smoke test (15 rows) and full run (164,445 rows, `outputs/mlx_full_run/gemini_full_train.jsonl`) both SUCCEEDED (72.1min / 80.7min). Full run: 17,001,755 billable training tokens × ~$0.005/1M ≈ **$0.085 total**. Endpoint scored 53.9%/61.6% (table above) — genuine learned behaviour, but well behind the frontier models and even behind the un-tuned local fine-tune's direct-generation mode. Config notes: no `response_schema` at inference on a tuned model (Google's documented caveat — bake format into training data instead, validate post-hoc with an `unclassified_other` fallback); `thinking_budget=0`.

**Labelling-architecture decision (Option 1 chosen, NOT yet implemented).** Carlos decided to replace Haiku in the `production_labelling.py` consensus layer with Gemini 3.7 Flash (Gemini + Sonnet consensus, Opus tiebreak), given Gemini 3.7's clear lead above. The refactor (renaming `MODELS`/`PREDICTIONS` keys, `gate()`, `review_sheet()`'s `"haiku_leaf"` column, `REVIEW_VERDICTS`'s `"haiku_correct"`, `apply_review()`) was scoped but **not started** — paused when Carlos asked for the determinism validation above. `production_labelling.py` is unmodified on disk as of 2026-08-23. The determinism finding likely doesn't change the plan (aggregate accuracy is stable), but confirm before resuming.

**Gold v4 scored 2026-08-23 — Option 1 confirmed on the production population.** `data/gold_transactions_v4_slm_volume.csv` (900 rows, true-random over the *unmatched-Plaid* population specifically, unlike v3's whole-population sample; built/labelled/reviewed via `src/build_gold_v4_slm_volume.py`) scored with the finalized 84,348-char prompt via `src/score_gold_v4.py` — full table and caveats in `data/gold_v4_scoring_report.md`. Headlines (leaf/general): Gemini 3.7 Flash 88.3/93.1, Opus 85.9/89.6, Sonnet 80.0/85.8 on all 900; simulated Option-1 consensus gate (Gemini+Sonnet agree, Opus tiebreak) accepts 96.4% at 89.9/93.3, and the no-tiebreak Gemini==Sonnet subset is 95.6% leaf at 78.6% coverage. Two structural findings: (1) **40.4% of the unmatched-Plaid population is already T4-dictionary-covered** — on the true post-T4 residual (n=536, what the LLM tier actually serves) the consensus gate still gets 86.6/90.5 on accepted rows (94.4% accepted); (2) **TF-IDF v2 scores 59.0% leaf on this volume-weighted set vs 32.0% on the merchant-disjoint holdout** (49.4% on the residual) — the classifier memorises the labelled head, so it's a plausible instant-runtime tier for production-shaped traffic even though its generalization floor is weak. Plaid native: 16.9/44.9. Caveat: gold labels were Haiku+Sonnet-drafted before human review, mildly favouring Sonnet — which nonetheless scored lowest, so the ranking is trustworthy; Gemini/Opus scores are clean of drafting bias.

## 7. Backlog after that

1. ~~Four-field categoriser~~ — **done 2026-08-20**: three-way statistical tie between architectures (hashed n-grams / TF-IDF+logreg / LightGBM); adopted TF-IDF + logistic regression. See `docs/project-summary.md`.
2. ~~Merge dictionary additions + write direction rules~~ — **done 2026-08-20**: `build_merchant_dictionary.py` now merges the 195 gating-approved entries plus 19 evidence-backed context-dependent merchants (535 entries total, up from 321). 3 new T5 direction rules added (`R15`–`R17`: child maintenance, we buy any car). Of the ~100 context-dependent merchants accumulated across gating + all three production tranches, most were deliberately left unresolved — either genuine same-direction product ambiguity (e.g. building societies: mortgage vs savings) or merchant-string normalisation collisions (the production-tranche cases — e.g. `"water"` merging a Teemill order in Freshwater with an unrelated water-bill narrative) where forcing a single leaf would misclassify a real sub-population. Full reasoning per merchant is in `src/build_merchant_dictionary.py` and `data/gating_adjudication_completed.xlsx`.
3. ~~Wire T4 + T5 into the crosswalk SQL~~ — **done 2026-08-20**. Measured tier distribution (2%/20% BigQuery sample): Equifax now resolves 34.8% via T4 dictionary + 4.1% T3 + 0.5% T1 + 0.3% T5 rules + 0.1% T2, 54.4% still falls to the T6 provider-crosswalk fallback, 5.9% unclassified. Plaid resolves 30.5% via T4 + 3.1% T5 rules + 0.2% T1, 66.1% via T6 fallback. Also caught and fixed a genuine pre-existing bug while wiring this up: the T1 gambling-credit rule pointed at `gambling_winnings`, a leaf that doesn't exist in the taxonomy — silently orphaning ~8k+2k transactions per sample. Fixed to `gambling_unspecified`.
4. Recompute feature IVs on the new taxonomy; benchmark against the current live model on the same `oot` split (Experiment 3)
5. ~~Investigate the `rent` detection gap~~ — **done 2026-08-22**: R13 re-enabled with a targeted false-positive exclusion. Measured the real IV impact against outcomes (`src/rent_iv_analysis.py`, `data/rent_iv_report.md`): essentially flat (0.0086→0.0085 etc., within noise) — R13 fixed 16,282 transaction-level misclassifications, but only 0.6% of proposals (485/83,873) had their rent-persistence count actually change. Kept the fix for audit-trail/fair-lending defensibility, not as a risk-model win.
6. ~~Score `data/gold_transactions_v4_slm_volume.csv`~~ — **done 2026-08-23**: Option 1 confirmed; see §6a and `data/gold_v4_scoring_report.md`.
7. ~~Resume the `production_labelling.py` Option-1 refactor~~ — **done 2026-08-23**: Gemini 3.7 Flash replaces Haiku in `PRODUCTION_MODELS`; `run_labelling()` dispatches Anthropic vs Gemini backends; `apply_review()` keeps tranches 1–3's `haiku_leaf`/`haiku_correct` workbooks re-appliable. Smoke-tested on 12 real tranche-3 strings. Not yet run on a full tranche.

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
| A shorter, principles-based labelling prompt would perform as well as (or better than) the full 375 worked examples, since it's cheaper | **No, tested twice at different compression levels, both failed** — principles-only lost 4–4.5pp vs full examples even after excluding leakage; principles+full-375 also underperformed plain full-375. Prompt caching neutralises the cost concern anyway. See §6a. |

## 10. Separate high-impact finding (not taxonomy work)

**Every Plaid Asset Report since go-live requests exactly 90 days** — all 11,530, 2025-08-13 to 2025-11-03. This is a Raylo-side request parameter, not a Plaid limit. Consequences: `total_months` never exceeds 3; every `*_before_90d_amount` and `*_surge_vs_history_ratio` feature is structurally dead (`bnpl_before_90d_amount` is constant zero); `total_cash_advance_disbursement_amount` is zero for all 79,863 rows yet still returned non-trivial IV under naive ranking — **always apply a variance/non-null floor before trusting IV**.

The Equifax dump's 189-day history makes the hypothesis testable now. This is probably the single highest-impact fix in the whole project and it belongs to whoever owns the Plaid integration.

## 11. Conventions

- Keep `docs/project-summary.md` (plain-English stakeholder overview + progress log) updated as milestones land.
- **`data/` holds human-verified, irreplaceable assets (gold eval set, adjudicated workbook, approved dictionary additions) — tracked in git, never overwrite programmatically.** `outputs/` is regenerable scratch, gitignored. `data/external_agent_adjudication_DO_NOT_INGEST.csv` is kept for provenance only.
- The repo is a git repository (since 2026-08-19). Commit after each substantive milestone; `.env` (API key) and `outputs/` are gitignored — verify with `git status` before any commit that adds new file types.
- Run `pytest tests/` after **every** taxonomy or dictionary edit. These tests already caught three invalid leaf references, a duplicate `Stationery` mapping, and a comma inside a regex that broke CSV parsing.
- Superseded work is in `archive/` with `_SUPERSEDED` / `_DISCARDED` suffixes. The AccountScore XML parser is discarded because the Equifax dump covers 99.997% of its references — don't resurrect it.
- Scratch output goes in `outputs/` (gitignored). Reusable benchmark/comparison scripts and their small text dependencies belong in tracked `benchmarks/`, not `outputs/` — anything needed to reproduce a quoted headline number must be in git.
- UK English in all artifacts and docs.

## Suggested skills

- `data:write-query` / `data:sql-queries` — BigQuery dialect, partition pruning (the Equifax dump is 20GB; select only needed columns)
- `select-bigquery-project` — defaults to `raylo-production`
- `data:explore-data` — profiling before trusting any new field
- `data:statistical-analysis` — for the IV / WoE work
- `data:validate-data` — before any result goes to stakeholders

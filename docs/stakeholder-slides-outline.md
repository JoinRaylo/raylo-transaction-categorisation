# Stakeholder slides — outline

Skeleton for the upcoming stakeholder presentation. **Structure and talking points only — not final slides.** All three production tranches and the Gemini/Opus tiebreak comparison are now fully closed (2026-08-20). Source of truth for every number here: `docs/project-summary.md` and the Notion page.

---

### 1. Title
- Unified Transaction Taxonomy: a Raylo-owned category system for Open Banking
- Carlos, AI Acceleration — [date of presentation]

### 2. Why we're doing this (motivation #1 — provider risk)
- The live risk model reads **Plaid's category names directly**
- Plaid shipped a breaking taxonomy change (PFC v2, 3 Dec 2025) months after we went live (Aug 2025) — the same transaction can be relabelled between versions with no warning
- We don't control Plaid's roadmap. We should control our own categories.

### 3. Why we're doing this (motivation #2 — a stronger risk model)
- The live model trains on Plaid data only: **Aug 2025 → present**, a few months of history, few realised bad outcomes observed yet
- Equifax's one-time dump covers **Jul 2022 – Sep 2025** — 37,404 proposals with realised 3-month and 12-month arrears already observed
- A shared taxonomy is what lets that history become usable training data for a next-generation model, not just an archive
- Equifax is a **dead source** (no new data ever) — this is a one-off depth boost, not a second ongoing pipeline

### 4. Starting point — the data
| | Equifax | Plaid |
|---|---|---|
| Rows | 73.2M | 4.3M |
| Period | Jul 2022 – Sep 2025 | Aug 2025 – present |
| Status | dead (one-time dump) | live |
| History per proposal | 189 days avg | 90 days (hard cap — see backup) |
| Merchant field | resolved entity, 6,518 distinct | raw text, 212,300 distinct |
| Native category coverage | 65.8% purpose-known | 100% assigns *something*, but 50.6% lands on coarse catch-alls |

### 5. The naive option we rejected — just crosswalk the categories
- Tested: map Equifax categories → Plaid categories directly, no taxonomy work
- Result: for merchants both providers cover, the two crosswalks disagree on **72.2% of merchants (45.2% of volume)**
- Concrete examples: Uber Eats (takeaway vs restaurant), M&S (credit card repayment vs department store), Sky (broadband vs mobile) — table of 4-5 examples
- A crosswalk-only pipeline propagates these silently. Nothing fails a test; both outputs look valid.

### 6. Building a taxonomy Raylo owns
- 275 detailed categories → 29 general categories, strict rollup (one parent per leaf)
- Plus 6 **orthogonal dimensions** that aren't tree-shaped: necessity, cash-flow type, is-debt-related, is-priority-debt, is-age-restricted, risk flag
- Why orthogonal, not nested — one sharp example: rent vs mortgage (both essential, only mortgage is debt) — collapsing them distorts essential-spend features by tenure, a fair-lending problem
- Why granularity survives IV pruning — gambling subtypes example (Lottery IV 0.0498 alone vs 0.0053 combined)

### 7. The categorisation strategy — precedence waterfall
- Every transaction resolves at the highest tier that fires; the tier is recorded (`resolution_tier`) — provenance matters for fair-lending review
- T1 direction overrides → T2 compound rules → T3 mechanism-override primaries → **T4 merchant dictionary (provider-independence mechanism)** → T5 regex rules → T6 provider crosswalk (fallback) → T7 explicit unclassified
- One diagram slide: the waterfall as a flowchart

### 8. The hard problem — what do we benchmark against?
- Equifax's own categorisation is a **vendor-level dictionary** (modal category share ~100% per merchant) — reproducing it isn't independent truth, it's reproducing its conventions
- Measured: where our own curated dictionary disagrees with Equifax, it sides with an independent LLM's judgement ~75% of the time (Netflix→streaming not broadband, Boots→pharmacy, eBay→marketplace…)
- **Conclusion: Equifax cannot be the benchmark.** Needed an independent, evidence-based gold standard.

### 9. Building the gold standard — the gating experiment
- Two independent LLMs (Haiku 4.5, Sonnet 5) label merchant strings from a closed 275-value taxonomy, blind to each other
- Where they agree with each other but disagree with Equifax → escalate to human adjudication (376 rows)
- Human adjudication result (2026-08-19): **96.1% leaf-level, 98.2% general-level corrected accuracy** — GREEN LIGHT
- By-products: 1,563-merchant gold set (head), 247-merchant gold set (tail), 195 approved dictionary additions, 49+ direction-rule candidates

### 10. Scaling it up — production labelling (tranches 1–3)
- Same two-model + human-escalation approach, extended to the highest-volume unmatched Plaid merchant strings, plus a third-model tiebreak (Opus 5) on residual disagreements
- Policy gate: general-category consensus auto-accepts; risk-dimension disagreement always goes to a human; everything else abstains
| Tranche | Strings | Share of unmatched volume | Human review |
|---|---|---|---|
| 1 (top 5k) | 5,000 | 30.0% | 113 (2.3%) |
| 2 (top 20k) | 20,000 | 45.4% | 321 (0.7%) |
| 3 (top 50k) | 50,000 | 56.1% | 692 reviewed (1.4%) — closed |
- Net effect: an accepted, provenance-tracked category on **~41%+ of all Plaid transactions**, up from 26.2% with the crosswalk alone

### 11. The residual classifier — distillation bake-off
- Built a small offline classifier to serve the long tail no dictionary or LLM pass will ever cover economically
- Confirmed the same benchmark bias by testing it: trained on Equifax labels → 69% head / 30% tail, and only **10%** on merchants our adjudication had already overruled Equifax on
- Fixed by training on our own production labels instead → tail accuracy roughly doubled (30% → 57.5%)
- Three architectures (hashed n-grams, bounded TF-IDF + logistic regression, gradient-boosted trees) converged to a **statistical three-way tie**; adopted TF-IDF + logistic regression for practical reasons (34× smaller, fully auditable, no training instability)

### 12. Speed/accuracy check — Opus vs Gemini 3.7 Flash tiebreak
- Ran the same tiebreak role through both models on tranche 3's full 18,430-string disagreement queue as a side-by-side comparison
- Result: **73.6% leaf agreement, 82.7% general-category agreement** between the two models — neither is simply "right" (no adjudicated ground truth for this comparison), but the gap shows real per-model disagreement worth knowing about before picking one for future tranches
- Gemini measured at 2.8 strings/sec; comparable wall-clock on Opus's side (no built-in timing log to cite a precise figure)

### 13. Where this leaves us today
- One sentence per pillar: taxonomy built and tested; benchmark problem solved and validated; production coverage scaling (tranches 1–3); residual classifier resolved and adopted
- Coverage now vs at the start — before/after bar or table

### 14. What's next
- Wire the merchant dictionary (T4) and regex rules (T5) into the live crosswalk SQL
- Write direction/entity rules for the 100+ context-dependent merchants surfaced along the way
- Re-derive risk features on the unified taxonomy and benchmark against the current live model (Experiment 3)
- Investigate the rent-detection gap (IV 0.0093 vs mortgage 0.0653) — largest household outgoing, currently under-detected
- Fix the Plaid 90-day pull-window limit (every asset report requests exactly 90 days — a Raylo-side parameter, not a Plaid limit; this is what unlocks using longer history at all)

### 15. Backup / appendix (not for the main deck)
- Full cost model (LLM labelling cost, why cost was never the binding constraint)
- Full precedence-waterfall tier definitions
- Full data-quality caveats (Plaid `payment_method`/`reference_number` unpopulated, `confidence_level` not ingested, etc.)
- Link to Notion page and `docs/project-summary.md` for full detail and progress log

# Stakeholder slides — outline

For handoff to whoever builds the actual deck. Each slide below lists: **Title**, **Subtitle** (if any), **Main body** (the content/bullets), and **Chart** (if one is warranted — otherwise "None"). This is a skeleton, not final copy — polish wording to house style when building the real slides.

All numbers sourced from `docs/project-summary.md`, `data/final_evaluation_report.md`, and the Notion page. **This outline was written 2026-08-21.** Coverage, dictionary size, and classifier scores moved substantially on 25–26 August 2026 — pull current figures from `CLAUDE.md` (current-state block) and `docs/project-summary.md` §8, not from this outline.

**One rule that matters for slide 11 specifically: always show the audited/clean numbers alongside the full-sample numbers, never the full-sample number alone.** We found and fixed real leakage in our own evaluation (see that slide's notes) — presenting only the inflated figure would undermine the credibility this project has been built on.

---

### Slide 1 — Title
- **Title**: Unified Transaction Taxonomy
- **Subtitle**: A Raylo-owned category system for Open Banking
- **Main body**: Presenter name, AI Acceleration, date
- **Chart**: None

### Slide 2 — Why we did this (1): provider risk
- **Title**: Why We Did This
- **Subtitle**: Reason one — we don't control Plaid's category taxonomy
- **Main body**:
  - The live risk model reads Plaid's category names directly
  - Plaid shipped a breaking taxonomy change (PFC v2, 3 Dec 2025) months after go-live (Aug 2025) — same transaction, different label, no warning
  - We don't control Plaid's roadmap; we should control our own categories
- **Chart**: None (optional: simple before/after icon showing a transaction's label changing under PFC v1→v2)

### Slide 3 — Why we did this (2): a stronger risk model
- **Title**: Why We Did This
- **Subtitle**: Reason two — unlocking Equifax's history for a richer model
- **Main body**:
  - Live model trains on Plaid only: Aug 2025 → present, few realised bad outcomes observed yet
  - Equifax's one-time dump: Jul 2022 – Sep 2025, 37,404 proposals with realised 3-month and 12-month arrears already observed
  - A shared taxonomy is what makes that history usable as training data — Equifax is a dead source (no new data ever), so this is a one-off depth boost
- **Chart**: Simple timeline — Equifax bar (Jul 2022–Sep 2025) vs Plaid bar (Aug 2025–present), annotated with the outcome-richness gap

### Slide 4 — Where we started: the data
- **Title**: Where We Started
- **Subtitle**: Two providers, very different data
- **Main body**: comparison table —
  | | Equifax | Plaid |
  |---|---|---|
  | Rows | 73.2M | 4.3M |
  | Period | Jul 2022–Sep 2025 | Aug 2025–present |
  | Status | Dead (one-time dump) | Live |
  | Merchant field | Resolved entity, 6,518 distinct | Raw text, 212,300 distinct |
  | Native category coverage | 65.8% purpose-known | 100% assigns *something*, but 50.6% lands on coarse catch-alls |
- **Chart**: Two-bar comparison of "distinct merchant strings" (6,518 vs 212,300) — makes the scale difference visceral

### Slide 5 — The naive option we rejected
- **Title**: Why a Simple Crosswalk Isn't Enough
- **Subtitle**: Just mapping Equifax categories onto Plaid — tested and rejected
- **Main body**:
  - For merchants both providers cover, the two independent crosswalks disagree on 72.2% of merchants (45.2% of volume)
  - Examples table: Uber Eats (takeaway vs restaurant), M&S (credit-card repayment vs department store), Sky (broadband vs mobile)
  - A crosswalk-only pipeline propagates these silently — nothing fails a test, both answers look valid
- **Chart**: Small table of the 3 examples above (merchant / Equifax→leaf / Plaid→leaf / correct answer)

### Slide 6 — Building a taxonomy Raylo owns
- **Title**: A Taxonomy Raylo Owns
- **Subtitle**: 275 categories, 29 general groups, 6 risk dimensions
- **Main body**:
  - 275 detailed categories → 29 general categories, strict rollup (one parent per leaf)
  - Plus 6 orthogonal risk dimensions that aren't tree-shaped: necessity, cash-flow type, debt-related, priority-debt, age-restricted, risk flag
  - One sharp example: rent vs mortgage — both essential, only mortgage is debt; collapsing them distorts essential-spend features by tenure (a fair-lending problem)
- **Chart**: None (optional: simple 2-axis diagram showing a leaf plotted on necessity × debt-related to illustrate orthogonality)

### Slide 7 — How we resolve every transaction
- **Title**: The Categorisation Waterfall
- **Subtitle**: Every transaction resolves at the highest tier that fires — and we record which one
- **Main body**: T1 direction overrides → T2 compound rules → T3 mechanism-override primaries → T4 merchant dictionary (provider-independent) → T5 regex rules → T6 provider crosswalk (fallback) → T7 unclassified
- **Chart**: Flowchart of the 7 tiers (this is the single most useful diagram in the deck — worth real design effort)

### Slide 8 — The hard problem: what's the benchmark?
- **Title**: What Do We Compare Against?
- **Subtitle**: Equifax's own category isn't independent truth
- **Main body**:
  - Equifax's categorisation is a vendor-level dictionary (modal category share ~100% per merchant) — reproducing it isn't independent validation, it's reproducing its conventions
  - Where our curated dictionary disagrees with Equifax, an independent LLM sides with us ~75% of the time (Netflix→streaming not broadband, Boots→pharmacy, eBay→marketplace)
  - Conclusion: needed an independent, evidence-based gold standard
- **Chart**: None

### Slide 9 — Building an independent gold standard
- **Title**: Building the Gold Standard
- **Subtitle**: Two-model consensus + human adjudication
- **Main body**:
  - Two independent LLMs label merchants blind to each other; where they agree with each other but disagree with Equifax → escalate to human adjudication (376 disputes)
  - Result: 96.1% leaf-level / 98.2% general-level corrected accuracy — green light
  - By-products: 1,563-merchant gold set (head), 247-merchant gold set (tail), 195 approved dictionary entries
- **Chart**: Simple funnel — 2,307 shared merchants → 376 disputes → adjudicated verdicts

### Slide 10 — Scaling up: production labelling
- **Title**: Scaling Coverage
- **Subtitle**: Three tranches, 56.1% of unmatched Plaid volume
- **Main body**: tranche table —
  | Tranche | Strings | Share of unmatched volume | Human review |
  |---|---|---|---|
  | 1 (top 5k) | 5,000 | 30.0% | 113 (2.3%) |
  | 2 (top 20k) | 20,000 | 45.4% | 321 (0.7%) |
  | 3 (top 50k) | 50,000 | 56.1% | 692 (1.4%) |
  - Human review burden *shrinks* as a share of volume with every tranche
- **Chart**: Bar chart — cumulative coverage % per tranche (30.0% → 45.4% → 56.1%)

### Slide 11 — Does this actually work? The final validation
- **Title**: Does This Actually Work?
- **Subtitle**: Our pipeline vs trusting either provider's own category — audited for leakage before trusting it
- **Main body**:
  - Scored our pipeline, Equifax's own category, and Plaid's own category against the same independent gold sets
  - **Before presenting results, we explicitly checked our own evaluation for bias/leakage** — found two real issues (see notes below) and fixed the scoring to show both a full-sample figure and a clean, audited figure
  - Full sample (representative, but includes some unreviewed model-agreement rows): Equifax native 82.3% leaf / Plaid native 31.9% leaf / **our pipeline 95.0%** (via Equifax txns) / **50.4%** (via Plaid txns)
  - Clean, audited subset (small, deliberately adversarial — cases a human specifically checked): our pipeline still leads (e.g. 62.0% vs Equifax-native 43.4%), margin narrower, n=129
  - **Conclusion: directionally decisive — our approach beats trusting either provider's native category — most starkly against Plaid, the live data source**
- **Chart**: Grouped bar chart — 3 groups (Equifax native / Plaid native / Our pipeline) × 2 bars each (full sample / clean audited subset). This is the headline chart of the whole deck.
- **Speaker notes for whoever presents**: the leakage audit found (1) 79% of gold "head" labels were never human-reviewed — just two similar LLMs agreeing with each other — and (2) 75% of gold "tail" labels were literally copied from the exact prediction being scored. Both are now fixed with a clean-subset comparison. Be ready to explain this if asked — it's a credibility strength ("we checked ourselves"), not a weakness, but it means the precise 93.9%/95.0% figures shouldn't be quoted as exact facts, only the direction and rough scale.

### Slide 12 — Why the remaining gap, and what closes it
- **Title**: The Biggest Lever Left
- **Subtitle**: Dictionary coverage, not further taxonomy design
- **Main body**:
  - Only 25.8% of gold head merchants are in the current 535-entry merchant dictionary yet
  - Where covered: pipeline is provider-independent, ~95% either way
  - Where not covered: still falls back to the provider crosswalk, inheriting Plaid's weak native categories
  - Provider-independence check: our pipeline agrees with itself across Equifax vs Plaid transactions 51.2% of the time, vs 27.8% for naive crosswalk alone
- **Chart**: Simple 2-bar comparison — "in dictionary" vs "not in dictionary" accuracy (via Plaid txns)

### Slide 13 — The residual classifier
- **Title**: Handling the Long Tail
- **Subtitle**: A small offline classifier for what no dictionary will ever cover
- **Main body**:
  - Confirmed the same provider-bias risk by testing it: a classifier trained on Equifax labels scored 69% head / 30% tail / only 10% on merchants we'd already overruled Equifax on
  - Retrained on our own production labels instead — tail accuracy roughly doubled (30% → 57.5%)
  - Three architectures converged to a statistical tie; adopted TF-IDF + logistic regression (34× smaller, fully auditable, no training instability)
- **Chart**: Small table — 3 architectures × head/tail accuracy

### Slide 14 — Where this leaves us
- **Title**: Where We Are Today
- **Main body**: one line per pillar —
  - Taxonomy: built, tested, 0 uncovered provider values
  - Benchmark problem: solved and validated (independent gold standard, not provider-derived)
  - Production coverage: 56.1% of unmatched Plaid volume labelled across 3 tranches
  - Residual classifier: resolved and adopted
  - **Final validation: our approach beats native provider categories, audited for leakage**
- **Chart**: None (could reuse the slide-4 style provider comparison as a closing visual)

### Slide 15 — What's next
- **Title**: What's Next
- **Main body**:
  - Expand T4 dictionary coverage (biggest lever identified by the validation)
  - Wire the remaining direction/entity rules for the ~100 context-dependent merchant backlog
  - Experiment 3: re-derive risk features on the new taxonomy, benchmark GINI against the live model on the same out-of-time split
  - Investigate the rent-detection gap (IV 0.0093 vs mortgage 0.0653) — largest household outgoing, currently under-detected
  - Flag: fix the Plaid 90-day pull-window limit (Raylo-side parameter, not a Plaid limit) — unlocks real use of transaction history depth
- **Chart**: None

### Slide 16 — Backup / appendix (not for the main deck)
- **Title**: Appendix
- **Main body**:
  - Full leakage-audit methodology and the complete clean-vs-full numbers table
  - Full precedence-waterfall tier definitions
  - Cost model for the LLM labelling route
  - Data-quality caveats (Plaid `payment_method`/`reference_number` unpopulated, `confidence_level` not ingested)
  - Links: Notion page, `docs/project-summary.md`, `data/final_evaluation_report.md`
- **Chart**: None

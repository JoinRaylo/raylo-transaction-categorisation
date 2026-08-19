# Project summary — unified transaction categorisation

Plain-English overview of the whole project, for stakeholders and for re-orientation. Keep this updated as milestones land (add to §8 and the progress log at the bottom).

## 1. The problem we started with

Raylo's live credit-risk model reads Plaid's category names directly. That's fragile: Plaid released a new version of its taxonomy (December 2025) *after* Raylo went live on it, and the same transaction can get a different label between versions — meaning our model's features could silently change meaning. We also have two data providers who categorise the same spending differently: **Equifax** (73M transactions of history, Jul 2022–Sep 2025, a one-time data dump — no new data coming) and **Plaid** (4.3M transactions, live since Aug 2025). The goal: a transaction taxonomy **Raylo owns**, where provider categories are evidence feeding our definitions rather than being the definitions.

## 2. Understanding the data

Before building anything, we profiled both sources and found the differences run deep. Equifax's two category fields aren't a hierarchy at all — one says *what* the money was for, the other *how* it moved (the same "General Groceries" tag appears on supermarket shopping and on salary paid *by* a supermarket). And the two providers' merchant fields are different kinds of data: Equifax resolves every transaction to one of 6,518 clean, curated vendor names, while Plaid passes through 212,300 raw text strings — including people's names on bank transfers.

## 3. Why we couldn't just map categories to categories

We tested a direct category-to-category mapping and it failed in a predictable way: clean categories map cleanly (taxis, flights, gambling), but the catch-all buckets — which hold a huge share of volume — don't map at all. Worse, when we applied each provider's mapping to the ~2,300 merchants that appear in both datasets, they gave **different answers for 72% of merchants**. The conclusion that shaped everything after: *the merchant, not the category, is the stable anchor across providers.*

## 4. Building our own taxonomy

We built a two-level taxonomy: **274 detailed categories rolling up into 29 general ones**, verified to cover 100% of both providers' category values. Cross-cutting concerns — is it essential spending, is it debt, is it a priority debt (UK debt-advice concept), is it age-restricted — are separate flags rather than extra hierarchy, because those groupings aren't tree-shaped. Design was evidence-driven, including one important self-correction: an early version deleted categories that didn't predict arrears, which was the wrong test — predictive power tells you where it's *safe to aggregate*, not which categories deserve to exist. We also fixed a fairness trap (rent and mortgage are both "essential", so homeowners and renters are measured comparably) and confirmed gambling subtypes must never be merged (merging destroys the signal).

## 5. How transactions get categorised

Every transaction runs down a **precedence waterfall**: direction-based rules first (gambling winnings ≠ stakes), then mechanism rules (salary is salary regardless of who pays it), then a **curated merchant dictionary that overrides both providers** — that override is what makes the taxonomy provider-independent — then regex rules, then the provider mapping as fallback, and finally an explicit "unclassified". Every transaction records *which* tier decided it, so any categorisation is explainable in plain terms — important for fair-lending defensibility. We then measured the hard limit: our dictionary covers 88% of Equifax's merchant volume but only ~48% of Plaid's, because of Plaid's long tail of raw strings. So merchant matching alone can't finish the job — some kind of classifier is essential, not optional.

## 6. Testing whether AI can label merchants

We ran a cheap decisive experiment before committing to a big build: two different LLMs (Claude Haiku 4.5 and Claude Sonnet 5) independently labelled the 2,307 merchants that appear in both providers, and we scored them against Equifax's labels. First results looked poor (~67%) — but digging in revealed the *scoring stick* was the problem: Equifax's "ground truth" is just its own merchant dictionary, with conventions ours deliberately disagrees with (it files Netflix under broadband, Boots under beauty). So we isolated the 376 merchants where **both models agreed with each other but not with Equifax** and put them to a human reviewer with full evidence per merchant (the raw bank statement text, direction of money, what each provider says).

## 7. Human adjudication settled it (GREEN LIGHT)

The human review found the models were right or acceptably right on ~70% of disputes, Equifax right on 16%, and 13% genuinely unanswerable from the merchant name alone (a payment "to Revolut" can be different things; Equifax's "Marks & Spencer" turned out to be M&S *credit card* payments while Plaid's is store spending). Corrected score: **96.1% accuracy at detailed level, 98.2% at general level — a green light** for LLM-assisted labelling. The review also produced three assets: 195 pre-approved dictionary entries, 49 merchants flagged as needing transaction-level rules, and a **1,563-merchant gold-standard evaluation set** — the fair benchmark for everything that comes next.

## 8. Where we are now

Next task, scoped and agreed: a **four-field categoriser** using merchant name, raw description, amount, and direction. Plan: a conventional ML baseline trained on Equifax's 44.7M labelled transactions, a context-enriched LLM version, both scored on the gold set, then combined — LLM labels the merchant vocabulary offline, the fast classifier handles the long tail at runtime, and the human-curated dictionary outranks both.

Side-findings worth stakeholder attention independent of this project: every Plaid data pull requests only 90 days of history when it could ask for more (kills several model features structurally), and rent — most customers' biggest outgoing — is barely detectable in the data.

---

## Progress log

- **2026-08-19 (night)** — four-field ML baseline trained (1.79M Equifax transactions, char-n-gram + amount + direction linear model) and evaluated on both gold strata: **69% leaf on the head set, 30% leaf on the tail — far behind the enriched LLM (76% on tail)**. The breakdown confirms the predicted bias mechanically: on rows where the human ruled against Equifax's conventions, the Equifax-trained classifier scores 10%. Conclusion: the classifier cannot be distilled from Equifax labels; the LLM-consensus labels must be the distillation source. Vocabulary labelling via LLM is now clearly the primary route.

- **2026-08-17 and earlier** — data profiling, crosswalk rejection analysis, taxonomy v1–v3 (274 leaves / 29 generals, verified 0 uncovered provider values), merchant dictionary (321 entries), precedence waterfall design, feature-form and IV analyses.
- **2026-08-18** — gating experiment ran twice (Haiku 4.5, then methodology review + Sonnet 5 comparison). Discovered the ground truth is Equifax's own vendor dictionary; built cross-model consensus analysis; exported 376 disputes with per-row evidence to an adjudication workbook. Also verified both providers carry raw bank narratives (Equifax `Description`; Plaid `transaction_name`/`original_description`).
- **2026-08-19 (evening)** — tail evaluation set adjudicated: 260 strings sampled from the ~210k unmatched Plaid population (six strata), labelled by both models with transaction evidence, human-verified → `data/gold_tail_labels.csv` (247 gold labels + 9 more transaction-level rule candidates). First readout on the real deployment population: Sonnet 5 enriched hits 76% leaf / 83% general overall, 90% leaf on the top-volume stratum; hardest strata are two-word names and the uniform tail (~68–75%). Also surfaced: Plaid's own merchant entity resolution has errors (Iceland supermarket → "Icelandair"), so raw narratives outrank Plaid merchant names as classifier input.
- **2026-08-19 (later)** — taxonomy boundary conventions written into the leaf notes (groceries/convenience/discount/specialist, web vs online services, takeaway vs restaurant, lottery vs prize competitions, pharmacy vs beauty, insurance) and `marketplace_amazon` split: it is Amazon-only again, with a new `marketplace_general` leaf for eBay/Vinted/Depop/Etsy — preserving the Amazon-specific risk signal. Dictionary and gold set updated to match (275 leaves now). Repo put under git; human-verified assets moved to tracked `data/`.
- **2026-08-19** — human adjudication of all 376 disputes completed: **GREEN LIGHT, 96.1% corrected leaf accuracy / 98.2% general**. Produced the 1,563-merchant gold eval set, 195 approved dictionary entries, 49 transaction-level rule candidates. Four-field categoriser scoped as next stage.

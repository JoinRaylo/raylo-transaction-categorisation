# Unified Transaction Categorisation — Cross-Provider Analysis & Recommended Architecture

Analysis of Raylo's three open-banking transaction sources, and a recommended design for one taxonomy applied across all of them.

---

## 1. Source structure: two providers, and one of them has a redundant landing path

AccountScore *is* Equifax — Equifax acquired AccountScore, and Raylo's "AccountScore" integration and "Equifax open banking" are the same provider. There are therefore **two providers to unify: Equifax and Plaid.**

Within Equifax there are two landing paths, and one supersedes the other:

| Path | Rows / refs | Status |
|---|---|---|
| `equifax_data.open_banking_full_dump` → `..._with_matches` → `stg_landing_equifax__open_banking_transactions` (view, deduped) → `intermediate_equifax__transactions_enriched` (view, window flags) | 73.2M rows / 99,164 refs | **Canonical.** Flat, proposal-matched, already modelled in dbt |
| `landing_sentinel_proposal_v2.AccountScoreResults` (raw XML via Sentinel) | 88,927 reports / 75,912 refs | **Redundant** — 75,910 of its 75,912 `ClientApplicationReference` values (99.997%) already appear in the dump |

**Consequence: do not build an XML parser for `AccountScoreResults`.** The dump covers essentially all of it, in a better shape (flat, matched, deduped, already staged), and holds ~31% more references besides. Any drafted XML-parsing model should be dropped rather than shipped.

Note the earlier-observed live checkout node `equifax_uk_open_banking_insights` (4,137 calls in `raw_provider_responses`) does not appear to land transactions in any modelled table — worth confirming separately whether current Equifax OB pulls are being persisted at all, since the dump is a one-time October 2025 batch with no updates since.

---

## 2. Data inventory

| | Equifax dump | Plaid | AccountScore XML |
|---|---|---|---|
| Table | `equifax_data.open_banking_full_dump` (+ `..._with_matches`) | `dbt_production.credit_plaid_open_banking_transactions` | `landing_sentinel_proposal_v2.AccountScoreResults` |
| Rows | 73,246,476 | 4,279,707 | 88,927 reports (~11.6k txns per 20 reports sampled) |
| Period | Jul 2022 – Sep 2025 | Aug 2025 – Nov 2025 | through May 2025 |
| Loaded | One-time batch, Oct 2025 | Live, incremental | Live, raw XML, no staging model |
| Matched to proposals | Yes — 99.95% (`..._with_matches`) | Yes | Not yet verified |
| Avg history per proposal | 189 days (median 180) | 90 days (hard cap) | ~180 days observed |

### Field availability for categorisation purposes

| Field | Equifax | Plaid | Notes |
|---|---|---|---|
| Raw description | 100% | 100% | `Description` vs `original_description` — both usable |
| Merchant name | 41.8% (`VendorDescription`) | 63.4% (`merchant_name`) | Plaid better coverage; Equifax better *quality* (see below) |
| Amount | 100% | 100% | |
| Direction | Yes | Sign on amount | Trivially reconcilable |
| Running balance | 100% (`RunningBalance`) | Not in current model | Equifax-only advantage |
| Recurrence flag | 21.9% (`RecurrenceType`) | Not in current model | Equifax-only advantage |
| Salary confidence | `IsAmberSalary` / `IsRedSalary` + 175 salary subcategories | No equivalent | Equifax-only advantage |
| Account type/subtype | Yes | Via account join | |
| Confidence level | No | Available from Plaid API but **not currently ingested** | Worth adding — see recommendations |

**Verdict on the question "do we have the same data in both":** yes for everything the categoriser core needs (description, amount, merchant, date, direction). Equifax carries several extra signals (balance, recurrence, salary confidence) that Plaid's current model doesn't ingest but the Plaid API does support — worth closing that gap independently.

---

## 3. Is Equifax/AccountScore a better categorisation baseline than Plaid?

Mixed, and the answer differs by dimension. Neither is a clean winner.

| Metric | Equifax/AccountScore | Plaid |
|---|---|---|
| Primary categories | 45 | 24 |
| Distinct category pairs | **1,017** | 91 |
| Unclassified rate | 27.9% | **23.8%** |
| Merchant name populated | 41.8% | **63.4%** |
| Distinct merchant strings | **6,518 (curated)** | 212,300 (raw) |
| Native essential/discretionary split | **Yes** | No |
| Gambling granularity | **11 subcategories, 98.2% vendor fill** | 1 category |
| Recurring payment detection | **Yes** | Not ingested |

Unclassified rate definitions: Equifax = `PrimaryCategoryDescription IS NULL` (6.15%) + `Transfers / Other` with null subcategory (13.1%) + `Misc Card Spend` (8.68%). Plaid = `TRANSFER_IN_OTHER` + `TRANSFER_OUT_OTHER` + `OTHER_OTHER` (23.8%).

### Where Equifax is meaningfully better

1. **It already solves the `mixed_basket` problem.** Equifax splits shopping into `Shopping (Household Essentials)`, `Shopping (Discretionary)`, `Shopping (Fashion)`, `Shopping (Home)` — the exact necessity disambiguation that forced ~20% of Plaid's detailed categories into `mixed_basket` in the earlier crosswalk work. Worth noting Equifax's judgements differ from the ones drafted by hand: it files liquor stores under Household Essentials (47.6% of matched merchants) and convenience stores under Discretionary (53.8%). Those are debatable, but they are *consistent and already applied at scale*, which beats a hand-drafted guess.
2. **Gambling granularity** — 11 subcategories at 98.2% vendor fill vs Plaid's single bucket. Directly relevant to the FCA vulnerability-detection use case discussed earlier.
3. **Curated vendor dictionary** — 6,518 distinct vendors covering 30.6M transactions. Plaid's 212,300 distinct `merchant_name` values over 2.7M merchant-labelled transactions indicates raw, unnormalised strings. Equifax has effectively already done the merchant-normalisation work that would otherwise be Phase 1 of this project.

### Where Plaid is better

1. Lower unclassified rate (23.8% vs 27.9%).
2. Better merchant coverage (63.4% vs 41.8%).
3. Structured, hierarchical category naming (`PRIMARY_DETAILED`) — easier to parse and reason about programmatically than Equifax's free-text names with inconsistent conventions (`Transfers / Other`, `Amazon All`, `Misc Card Spend`).

**Overall:** use Equifax/AccountScore as the *semantic* baseline (its category structure, especially the necessity split and gambling detail, is closer to what Raylo needs), and use Plaid as the *coverage* baseline. Neither should be the source of truth — see architecture below.

---

## 4. Why a category→category crosswalk won't work

For the 2,315 exact-match merchants present in both datasets, mapping quality is strongly bimodal:

**Maps cleanly** (share of matched merchants landing in the modal Equifax category):
| Plaid category | → Equifax modal | Agreement |
|---|---|---|
| `TAXIS_AND_RIDE_SHARES` | Commuting and travel | 94.4% |
| `FLIGHTS` | Flights and Holidays | 89.5% |
| `GOVERNMENTS_AND_NON_PROFIT` | Utilities | 88.5% |
| `CASINOS_AND_GAMBLING` | Gambling and Betting | 84.1% |
| `GAS_AND_ELECTRICITY` | Utilities | 83.3% |
| `DONATIONS` | Charitable Giving | 81.5% |

**Maps poorly:**
| Plaid category | → Equifax modal | Agreement | Distinct Equifax cats |
|---|---|---|---|
| `TRANSFER_OUT_OTHER` | Financial Services | **15.2%** | 26 |
| `TRAVEL_..._OTHER` | Commuting and travel | 27.2% | 18 |
| `GENERAL_MERCHANDISE_OTHER` | Shopping (Household Essentials) | 27.8% | 16 |
| `GENERAL_SERVICES_OTHER` | Services | 30.9% | 15 |
| `RENT_AND_UTILITIES_RENT` | Rent and Mortgage | **37.5%** | 8 |

**Two distinct problems here:**
- **Catch-all categories don't map**, because they aren't categories — they're the absence of one. `TRANSFER_OUT_OTHER` scattering across 26 Equifax categories isn't a mapping failure, it's confirmation that neither provider's catch-all carries information.
- **Systematic semantic disagreements** exist and need explicit decisions, not averaging. `GOVERNMENTS_AND_NON_PROFIT` → `Utilities` at 88.5% is almost certainly council tax, which the two providers file under genuinely different concepts. `RENT_AND_UTILITIES_RENT` → `Rent and Mortgage` at only 37.5% deserves investigation before trusting either provider's rent signal.

**Conclusion:** a static category→category lookup would be reliable for maybe 60% of categories and actively misleading for the rest — and the unreliable ones cover the highest-volume buckets.

---

## 5. Recommended architecture

The merchant, not the category, is the stable cross-provider anchor. Where a merchant is identifiable, both providers largely agree; where it isn't, neither provider's category is trustworthy. So build merchant-first.

### Layer 1 — Canonical merchant dictionary (`merchant_entity` → `raylo_category`)

The primary categorisation mechanism. Deterministic, auditable, cheap to run, fully explainable in an adverse-action context.

- **Seed from Equifax's 6,518 curated vendors** — already normalised, already mapped to a 45-category taxonomy, covering 30.6M transactions. This is a substantial head start that didn't exist when the Plaid-only crosswalk was drafted.
- Extend with the highest-volume Plaid merchants not already covered.
- Store as a dbt seed or a managed table with PR-reviewed changes, same governance model as the earlier crosswalk design.

### Layer 2 — Merchant normalisation

The main engineering task, and the reason Layer 1 doesn't just work out of the box. Plaid's 212,300 raw merchant strings need collapsing onto canonical entities at roughly Equifax's 6,518 scale.

- Deterministic cleaning first: strip transaction IDs, POS/location codes, card suffixes, trailing reference numbers.
- Then fuzzy/embedding-based matching to canonical entities.
- Validate against the 2,315 exact-match merchants — normalisation should *increase* that overlap substantially. That number is the metric for whether Layer 2 is working.

### Layer 3 — ML classifier for the residual

For transactions with no identifiable merchant (~36% of Plaid, ~58% of Equifax by merchant-fill rate).

- Features: normalised description text (TF-IDF or embeddings), amount, direction, recurrence flag where available, **and both providers' native categories as input signals** — a provider's category is informative evidence even when it isn't the answer.
- Target: the unified Raylo taxonomy (reuse the `raylo_category` / `necessity` / `is_debt_related` / `risk_flag` schema already designed, revised to adopt Equifax's native necessity distinctions where they're better grounded than the hand-drafted guesses).
- Training data: ~77M transactions across both sources, with each provider's own labels as weak supervision, and the 2,315-merchant agreement set as high-confidence ground truth.

### Layer 4 — LLM, offline only

Never in the live per-transaction path (cost and latency, per the Ntropy finding from earlier research). Use it for:
- Bootstrapping labels for unmatched merchant clusters, for human review.
- **Adjudicating the systematic disagreements** — e.g. deciding whether council tax belongs under a government or utilities concept, and whether Equifax's "liquor stores are household essentials" call should be adopted or overridden.
- Cold-starting merchants that appear in one provider but not the other.

### Layer 5 — Drift monitoring

- Unmatched-merchant rate over time, tracked per provider.
- Share of volume falling through Layer 1 → Layer 3.
- New unmapped category values from either provider (scheduled dbt test, as designed earlier).
- Ingest and monitor Plaid's `confidence_level` field, which is currently available from the API but not captured in `intermediate_credit_plaid_transactions`.

---

## 6. The 2,315-merchant overlap set is the most valuable asset here

It gives three things at once:
1. **Ground truth** — where both providers agree independently, confidence is high. Use as the training/validation label set for Layer 3.
2. **A disagreement queue** — where they conflict, those are exactly the cases needing a deliberate Raylo decision (Layer 4), and there are few enough to review by hand.
3. **A normalisation metric** — the overlap count should grow substantially as Layer 2 improves. It's the clearest single measure of progress on the hardest part of the project.

---

## 7. Sequencing

1. **Adopt Equifax's taxonomy as the starting semantic skeleton**, revising the earlier hand-drafted crosswalk to use its necessity distinctions where better grounded. Cheaper and better-evidenced than continuing to hand-draft.
2. **Build the canonical merchant dictionary** seeded from Equifax's 6,518 vendors.
3. **Build merchant normalisation for Plaid strings**, measured against growth in the overlap set.
4. **Review the disagreement cases** (council tax, rent, liquor/convenience necessity calls) and decide them explicitly.
5. **Train the residual classifier** on the combined corpus.

There is no AccountScore-parsing step — see section 1. That work is unnecessary, and the corresponding drafted dbt model should be discarded rather than shipped.

## 8. Open items worth verifying

- **`bank_account`-matched rows in `..._with_matches`** (18% of volume, 13.1M rows / 15,738 proposals) use a weaker match method than direct ID joins. Spot-check for false positives before using them for anything outcome-linked.
- **The 189-day average history in the Equifax dump vs Plaid's 90-day cap** — this dataset can test whether the `*_before_90d` / `*_surge_vs_history` features (dead in `ds_plaid_credit_features`) actually carry signal when given real lookback depth. Strong supporting evidence for the 90-day pull-window fix, testable now without waiting for new data.
- **`RENT_AND_UTILITIES_RENT` → `Rent and Mortgage` at only 37.5%** — unexpectedly low for what should be an unambiguous category. Worth understanding before trusting rent signals from either provider.
- **Plaid's 212,300 distinct merchant strings over 2.7M merchant-labelled transactions** — a suspiciously high ratio, suggesting the field carries noise (references, IDs) rather than clean merchant identity. Confirm before relying on `merchant_name` as-is anywhere.

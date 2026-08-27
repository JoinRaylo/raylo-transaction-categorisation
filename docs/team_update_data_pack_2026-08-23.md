# Data pack for team progress update — 2026-08-23

> **Dated snapshot.** Dictionary size, T4 coverage, and classifier scores in this pack are **23 August 2026**. Current figures (91,173 T4 keys, Plaid T1–T4 53.2%, classifier v5) live in `CLAUDE.md` and `docs/project-summary.md`. Do not quote the 18,825-entry / ~36% dictionary-on-Plaid-other figures as today's numbers.

Raw points and numbers for slides. Organised into: (1) Plaid unclassified stats,
(2) Plaid-vs-us headline comparisons, (3) concrete rescue examples, (4) the full
benchmark catalogue across every eval set we've built, including the two you
asked about specifically (gold v4, just scored today, and the ~1,057-row
gold_v2_slm_eval_holdout set). Every number below is sourced from a tracked
report or a query run today — sources noted so you can pull the receipts if asked.

---

## 1. How much of Plaid's own categorisation is "no real answer"

Live query against `dbt_production.credit_plaid_open_banking_transactions`
(4,279,707 transactions total, the entire live Plaid population since go-live):

| Plaid's own category | Transactions | % of all Plaid volume |
|---|---|---|
| `TRANSFER_OUT_OTHER` | 552,764 | 12.9% |
| `TRANSFER_IN_OTHER` | 465,956 | 10.9% |
| `OTHER_OTHER` | 1 | ~0.0% (essentially unused) |
| **Total "Plaid has no real answer"** | **1,018,721** | **23.8%** |

**Nearly a quarter of every transaction Plaid sees, it files under "other."** This
is Plaid's single largest category bucket — bigger than groceries (7.8%), bigger
than salary (7.7%), bigger than dining (6.6%). Zero transactions have a genuinely
null category (Plaid always returns *something* — the problem is what it returns).

Of the 440,017 of those "other" transactions that carry an identifiable merchant
name, **~36% (159,657 transactions) resolve to a category through our
18,825-entry merchant dictionary alone** — before the LLM/classifier tier even
runs. Caveat found while fact-checking this pack (see section 3): the
dictionary matches on merchant string alone, so a small known slice of that
figure is wrong in the same way the Tesco/Tesco Bank case is (~1,150
transactions, well under 1% of the 159,657) — the ~36% headline is directionally
solid but not merchant-by-merchant verified. The rest of the "other" bucket is
a combination of dictionary/LLM/classifier tiers, as detailed in section 2.

*(Source: live BigQuery query, 2026-08-23; see also CLAUDE.md §5 — Plaid overall,
50.6% of transactions land on a coarse/low-information leaf, of which
`unclassified_transfer` is the single largest at 23.8% — this section is that
same number traced back to Plaid's own raw category values.)*

---

## 2. Headline comparisons — us vs. Plaid, at every level of rigour

We ran this comparison four times, each time on a harder, more honest test than
before. All four point the same direction; report the last one (v3) as the
headline, with the others as robustness checks if pressed.

| Evaluation | Population | Plaid native | Our pipeline | Source |
|---|---|---|---|---|
| **v3 — volume-weighted (real production mix)** | 1,500 txns, true random, no stratification | **32.5% leaf / 60.3% general** | **63.4% leaf / 74.2% general** | `data/final_evaluation_v3_volume_report.md` |
| v2 — clean, combined batches | 3,000 txns, hand-reviewed, breadth + random | 39.9% / 55.2% | 46.6% / 58.5% | `data/final_evaluation_v2_report.md` |
| v2 — hardest disputed merchants only | subset of above | 10.7% | 31.3% | same |
| First full validation (has some sampling bias toward famous brands — quote with caveat) | 1,754 txns | 29.9% overall | 93.9% overall | `data/final_evaluation_report.md` |
| **Gold v4 — production-population, unmatched-Plaid only** | 900 txns, volume-weighted, scored today | **16.9% leaf / 44.9% general** | **89.9% / 93.3%** (consensus gate, 96.4% coverage) | `data/gold_v4_scoring_report.md` |

**The v3 number is the one to lead with**: it's a true random, volume-weighted
sample — i.e., what a typical incoming transaction actually looks like in
production — and it shows **our pipeline nearly doubling Plaid's own accuracy**
(63.4% vs 32.5% leaf-level). The gold-v4 comparison (16.9% vs 89.9%) looks even
more dramatic, but that's because it's deliberately restricted to the subset of
transactions Plaid's own dictionary already fails on — it isolates the exact
population where our system earns its keep, which is a good "why does this
project exist" slide, paired with the v3 number as the "and it works overall"
slide.

**On the Equifax side (dead data source, but useful as a sanity check on
methodology):** native 71.8% / 82.0% ours (v3), and separately, native 82.3% /
95.0% ours on the 1,563-merchant head set — Equifax's own categories are much
better than Plaid's to begin with (it emits *resolved* vendor names, not raw
text), which is exactly why the "Plaid inherited categorisation is not
enough" argument needs its own evidence — Equifax was never the risk model's
real problem.

---

## 3. Concrete examples: Plaid says "other," we know exactly what it is

Real transactions, live production data, pulled today. All from Plaid's
`TRANSFER_OUT_OTHER` bucket — Plaid's largest single "no idea" category.

| Merchant | Plaid's raw narrative | Amount | Plaid's category | Our category |
|---|---|---|---|---|
| Very | "VERY ON 27 MAY BCC Very" | £193.44 | `TRANSFER_OUT_OTHER` | `catalogue_retail` |
| Capital One | "To Capital One - PBB00016786402..." | £198.24 | `TRANSFER_OUT_OTHER` | `credit_card_repayment` |
| Coinbase | "Coinbase Payments R2O7CK0G0..." | £10.00 | `TRANSFER_OUT_OTHER` | `crypto` |
| Remitly | "Remitly" | £10.00 | `TRANSFER_OUT_OTHER` | `transfer_international` |
| GoHenry | "Visa purchase GoHenry Auto Topup 5710" | £30.00 | `TRANSFER_OUT_OTHER` | `prepaid_card` |
| Go Local Extra | "Go Local Extra" | £1.59 | `TRANSFER_OUT_OTHER` | `convenience_store` |

**Why Plaid misses these**: they're all direct debits, card payments, or bank
transfers rather than card-terminal purchases, so Plaid's own merchant-category
logic falls back to a generic transfer bucket regardless of who the counterparty
actually is. Our merchant dictionary recognises the counterparty name itself
and doesn't care how the money moved.

**Correction (caught in review, worth keeping as a rigour note):** an earlier
draft of this table included a "Tesco → groceries" row. On closer inspection
that row's actual narrative was `"TESCO BANK ON 22 AUG BCC"` — a Tesco Bank
credit-card/direct-debit payment, not a supermarket purchase. Checked the scale
of the underlying issue: within Plaid's `TRANSFER_OUT_OTHER`/`TRANSFER_IN_OTHER`
bucket specifically, merchant name `"tesco"` appears 1,155 times, and **1,146 of
those (99.2%) are narrative-confirmed Tesco Bank transactions, not supermarket
purchases** — our merchant dictionary's blanket `tesco → groceries` mapping is
wrong almost every time for this specific subpopulation (it's dictionary-keyed
on the merchant string alone, and Plaid's own merchant-name resolution has
already collapsed "Tesco Bank" down to bare "Tesco," so the dictionary can't
tell the two apart without also reading the narrative). Scale: ~1,150
transactions out of 4.28M total Plaid volume (~0.03%) — small in aggregate, but
a systematic, wrong-direction miscategorisation (a debt repayment counted as
grocery spend) for the fraction of the population it hits, structurally
identical to the already-solved Marks & Spencer / M&S Bank case (CLAUDE.md §4).
**Logged as a real fix candidate** — a narrative-based override rule (same
pattern as the existing T1/T5 direction rules), not yet implemented. The five
other examples in the table above were independently re-verified against their
real transaction narratives before inclusion.

**A second, complementary example type — where BOTH providers give an answer,
but the wrong one** (shows the taxonomy also fixes disagreements, not just gaps):

| Merchant | Equifax says | Plaid says | Correct |
|---|---|---|---|
| Uber Eats | `takeaway` | `restaurant_cafe` | `takeaway` |
| Marks & Spencer | `credit_card_repayment` (matched M&S Bank) | `department_store` | `department_store` |
| Vanquis Bank | `credit_card_repayment` | `personal_loan_repayment` | `credit_card_repayment` |
| Sky | `broadband_tv_phone` | `mobile_phone_contract` | `broadband_tv_phone` |

*(Source: CLAUDE.md §4 — measured across 2,307 merchants both providers cover;
providers disagree on 72.2% of merchants, 45.2% of volume.)*

---

## 4. Full benchmark catalogue — every eval set, every number

We've built five independent hand-verified gold sets, each answering a different
question. This is the complete state as of today.

### 4a. The provider-comparison gold sets (is our taxonomy better than trusting the providers?)

| Gold set | Rows | What it tests | Headline result |
|---|---|---|---|
| `gold_merchant_labels.csv` | 1,563 | Merchants both providers cover ("head" population) | Equifax-own 82.3%/93.7%, Plaid-own 31.9%/63.5%, ours 95.0%/98.2% (via Eqfx txns) / 50.4%/72.1% (via Plaid txns) |
| `gold_tail_labels.csv` | 247 | Plaid-only long-tail merchants | Plaid-own 17.0%/43.7%, our LLM consensus 84.8%/90.6% (on the 191/247 it's confident enough to answer) |
| `gold_transactions_v2.csv` + `_batch2.csv` | 3,017 (combined) | Clean, hand-reviewed, breadth + random transaction-level | native 39.9%/55.2%, ours 46.6%/58.5% |
| `gold_transactions_v3_volume.csv` | 1,500 | **True random, volume-weighted — the realistic "how good is this today" number** | Equifax native 71.8%/81.2% → ours 82.0%/87.4%; **Plaid native 32.5%/60.3% → ours 63.4%/74.2%** |
| `gold_transactions_v4_slm_volume.csv` | 900 | Volume-weighted over the *unmatched-Plaid residual* specifically (what the LLM/SLM tier serves) | Plaid native 16.9%/44.9%; consensus gate 89.9%/93.3% (96.4% coverage) — see 4c |

All leaf-level accuracy percentages above are against human-adjudicated ground
truth (with documented, publicly-noted leakage/circularity fixes along the way —
happy to explain the methodology rigour if asked, it's a good "we've been
careful" talking point: three separate leakage audits caught and fixed real
circularity issues before we'd trust any of these numbers).

### 4b. The model-comparison benchmark (which LLM/SLM should do the actual labelling?)

Scored against **`gold_v2_slm_eval_holdout.csv` — 1,057 real transactions**,
deliberately **merchant-disjoint** from all training data (this is almost
certainly the "thousand and a hundred or so rows" set you were thinking of).
This is the *generalisation floor* test — hardest, cleanest test we have, no
merchant the model could have memorised.

| Model / approach | Leaf accuracy | General accuracy | Throughput |
|---|---|---|---|
| **Gemini 3.7 Flash** (untuned, 3-run average) | **84.2% ± 0.15pp** | **90.9% ± 0.12pp** | ~3.1–3.9 rows/sec |
| Claude Opus 5 | 80.6–81.7% | 87.6–88.5% | ~1.2–3.8 rows/sec |
| Claude Sonnet 5 | 76.8–76.9% | 83.0–84.1% | ~1.3–4.7 rows/sec |
| Claude Haiku 4.5 | 72.9–73.7% | 81.1–81.6% | ~7.0 rows/sec |
| Tuned Gemini 2.5 Flash (fine-tuned endpoint) | 53.9% | 61.6% | 20.2 rows/sec (fastest) |
| Local fine-tuned SLM (direct generation) | 50.0% | 59.5% | — |
| TF-IDF + logistic regression | 32.0% | 37.6% | — |
| Sentence-embedding + logistic regression | 27.6% | 32.5% | — |
| Vanilla (non-fine-tuned) local model | 0–17.7% (depends on prompting) | 0–36.7% | — |

**Decision made from this table**: Gemini 3.7 Flash replaces Haiku as one of the
two independent labelling models in our production consensus pipeline (Gemini +
Sonnet agree → accept; disagree → Opus tiebreak). This refactor is now
implemented in code as of today.

### 4c. Gold v4 — scored today, the production-population confirmation

**`data/gold_transactions_v4_slm_volume.csv` — 900 rows, true random, weighted
by real volume within the unmatched-Plaid population specifically** (i.e., not
"could a model generalise to anything," but "given the actual traffic this
system serves today, how accurate is it?"). Different question from 4b's
holdout, same models, both matter.

| Scorer | All 900 rows (leaf/general) | Post-dictionary residual, n=536 (leaf/general) |
|---|---|---|
| **Consensus gate (Gemini+Sonnet agree, Opus tiebreak)** | **89.9% / 93.3%** (96.4% of rows accepted) | **86.6% / 90.5%** (94.4% accepted) |
| Gemini 3.7 Flash alone | 88.3% / 93.1% | 83.8% / 89.7% |
| Claude Opus 5 alone | 85.9% / 89.6% | 81.9% / 85.8% |
| Claude Sonnet 5 alone | 80.0% / 85.8% | 72.4% / 80.0% |
| TF-IDF classifier (cheap, instant, no LLM call) | 59.0% / 62.2% | 49.4% / 53.4% |
| Plaid's own category | 16.9% / 44.9% | 18.7% / 41.4% |

**Two things worth a slide of their own:**
- **40.4% of "unmatched Plaid" volume is already dictionary-covered** — the LLM
  tier's *true* serving population is the other ~60% (the "residual" column
  above), where we still get 86.6%/90.5% accuracy at 94.4% coverage.
- **The cheap classifier looks much better on real traffic than it did on the
  hard generalisation test** (59.0% here vs. 32.0% in table 4b) — real
  production volume repeats merchants it's already seen, so it's a viable
  instant-answer tier after all, not just a fallback.

### 4d. The original feasibility gate (why we trusted the LLM route at all)

Before building any of the above, we ran a smaller gating experiment (2026-08-18)
to decide whether LLM-based labelling was worth the investment:

- Two models (Haiku + Sonnet) independently guessed categories for 2,307
  merchants blind to any provider category — Haiku 66.8%/86.7%, Sonnet
  68.8%/87.9% against Equifax's own dictionary.
- Where both models agreed with each other (82% of cases), agreement with
  Equifax was 76.7%/91.6% — and 376 of those agreement cases still disagreed
  with Equifax, so we had them independently human-adjudicated.
- **Result: 96.1% of those "LLM says X, Equifax says Y" disputes were won by the
  LLM** (Equifax's own dictionary conventions were simply outdated/inconsistent
  in those cases) — this was the green light to invest further, and it's held
  up in every benchmark since.

---

## Suggested slide flow

1. **The problem**: Plaid's own categorisation puts ~24% of all transactions in
   a generic "other" bucket (section 1) — bigger than any real spending category.
2. **The fix, in one number**: on real production-weighted traffic, our pipeline
   more than doubles Plaid's own accuracy (63.4% vs 32.5% leaf-level — section 2,
   v3).
3. **Show, don't tell**: the Tesco/Very/Capital One examples (section 3) — a
   non-technical audience will get these instantly.
4. **Rigour**: five independent hand-verified gold sets, three leakage audits
   that caught and fixed real measurement bugs before trusting any number
   (mention briefly, builds credibility without needing the detail).
5. **What's next**: model choice for the automated tier is settled (Gemini 3.7
   Flash, confirmed twice — sections 4b/4c) and already implemented; the
   dictionary/rules layer already resolves 40%+ of the hardest population
   before any model call is needed.

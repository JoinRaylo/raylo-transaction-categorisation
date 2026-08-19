# Review of `merchant_leaf_adjudication.csv` (external agent's adjudication)

**Verdict: do not ingest this file as an adjudication.** It is mechanically clean (all 376 merchants present, every `recommended_leaf` a valid taxonomy value) but it did not do the job: **334 of 376 rows (89%) were never judged** — marked `llm_only_no_dict` / `not_applicable` with the boilerplate rationale "Dictionary leaf is blank so the LLM leaf is the only supplied candidate", and `recommended_leaf` set to the LLM consensus on all 334. That misreads the task: the adjudication question is *LLM vs Equifax*, and the Equifax label is a live candidate on every row. The agent treated our dictionary as the only alternative and defaulted to the LLM wherever it was silent — which begs exactly the question the adjudication exists to answer.

If ingested as-is, corrected consensus accuracy would come out at (1239 + 375) / 1615 ≈ **99.9%** — a number produced by the default rule, not by judgment.

## The 42 rows it did touch

- 35 `both_agree` — restatements of the dictionary cross-check we had already run programmatically. No new information.
- 7 genuinely judged (each with a rationale and verification URL): `nisa`, `costcutter`, `spar`, `keystore`, `costco`, `mcqueens dairies` (`llm_wins`), `paypal credit` (`dict_wins`).

**On 6 of those 7 it overrode our human-curated dictionary in the LLM's favour** — without noticing that the dictionary encodes a deliberate convention: `spar`, `nisa`, `costcutter`, `keystore`, `londis`, `premier stores`, `one stop`, `best-one`, `centra` are *all* mapped to `groceries` (with `martin mccoll` alone as `convenience_store`). Flipping four of them row-by-row creates inconsistency with the five identical merchants the dictionary already covers. Whether symbol-group stores are `groceries` or `convenience_store` is a **convention decision to make once**, not a per-row adjudication — and both leaves sit in the same general category, so nothing rides on it at feature level. (`paypal credit` → `bnpl` is correct.)

Note the structural caveat: the adjudicating agent is an LLM ruling on a dispute between two LLMs and a human-curated dictionary. Three models sharing the same prior is not independent evidence — the 6 anti-dictionary verdicts illustrate the circularity.

## My substantive review of the disputes themselves

The 376 rows collapse into 219 patterns; the volume is concentrated in ~30. Where the LLM consensus agrees with our curated dictionary (google play, home bargains, b&m, netflix, boots, superdrug, gocardless, shein, matalan, onlyfans, holland & barrett, pret a manger, welcome break, creditspring…) **I agree with the consensus** — those are Equifax-convention artifacts, as suspected.

**Correction after checking transaction-level evidence (2026-08-18, later):** two rows I initially treated as clean LLM wins are actually a different phenomenon — **the same string names different things in the two datasets, or different things per transaction**:

- **marks & spencer**: Equifax's vendor "marks & spencer" is *100% `Financial Services | Credit Cards`* with raw descriptions literally reading `M&S CREDIT CARD` — Equifax was **correct for its transactions** (they are M&S Money direct debits). Plaid's string is 99.9% department-store spend. Neither side erred; the dispute is an artifact of joining on the string. For the *Plaid* string (the deployment target), `department_store` is right — same practical outcome, different reasoning, and it means this row says nothing about Equifax label quality.
- **revolut**: Equifax's own transaction mix is ~71% `Transfers/Other | Bank Transfer`, ~29% `Own Transfers | Bank Transfer`, varying by direction — no single merchant-level leaf is correct. Properly `context_dependent` (a T1/T2 direction-rule candidate), not `llm_correct`. The LLM's blanket 0.95-confidence `transfer_own_account` is overconfident; Equifax's `transfer_bank_unspecified` is the honest modal label.
- **freemans** gains nuance too: its top raw descriptions split between `FREEMANS - AGY` (catalogue-credit agency payments — the majority, supporting Equifax's `retail_finance_repayment`) and `PPOINT_*FREEMANS CON STOR` (a PayPoint convenience store that happens to share the name). Majority verdict unchanged (Equifax), but it's another string-collision case.

The adjudication workbook has been rebuilt with per-row evidence columns (Plaid's native category share, Equifax's full category mix, credit share, top raw descriptions) and a `context_dependent` verdict so these cases can be judged properly rather than forced into a binary.

**Where I disagree with the LLM consensus** (all rubber-stamped `llm_only_no_dict` by the agent, except where noted) — the common thread is that **the LLM reads the merchant's surface name while Equifax encoded the transaction's function**, and the function is the risk-relevant truth:

| merchant | Equifax (keep) | LLM consensus (reject) | why |
|---|---|---|---|
| freemans (vol 831) | `retail_finance_repayment` | `catalogue_retail` | Freemans bank payments are catalogue-credit repayments. `retail_finance_repayment` is the closest analogue to Raylo's own product — losing it to "shopping" damages a strategically important signal |
| next directory (vol 291) | `retail_finance_repayment` | `catalogue_retail` | Same — "Next Directory" specifically is the credit account, distinct from Next retail |
| pepper money (vol 44) | `mortgage` | `personal_loan_repayment` | Pepper Money is a specialist mortgage lender. Also breaks the mortgage/rent `essential_spend_ratio` logic for those customers |
| mortimer clarke solicitors | `debt_collection` | `legal_services` | A debt-litigation firm (Cabot group). Exactly the low-volume genuine distress marker §6 of the design doc says to protect |
| skillz esports, suprplay | `gambling_bingo` / `gambling_casino` | `gaming_online` | Cash-prize gaming platforms. Moving them out of the gambling general violates the never-lose-gambling-signal rule |
| castle community bank | `credit_union_repayment` | `financial_institution_unspecified` | It is a credit union (Edinburgh) |
| 247 money (vol 50) | `car_finance_repayment` | `payday_loan` | 247 Money is subprime *car finance*; high-cost, but the product is car finance |
| rbs (vol 13) | `personal_loan_repayment` | `financial_institution_unspecified` | Equifax saw the account context the string doesn't carry; the LLM's abstain-ish label is safe but less informative |
| child maintenance (vol 16) | `unclassified_transfer` | `income_other_unspecified` | Direction-dependent — could equally be an outgoing obligation. Without direction, Equifax's neutral label is safer |
| currys (vol 918) | `electrical_goods` | `computing_devices` | General electronics/white-goods retailer; `computing_devices` is too narrow (same general — low stakes) |
| wilkinson (vol 11) | `home_accessories` | `discount_store` | Our dictionary maps `wilko.com` → `home_accessories`; consistency |

**Genuinely arguable rows worth your own eyes** (no clear winner; convention decisions): the symbol-group cluster above; `vinted`/`depop`/`ebay` → `marketplace_amazon` (our dictionary uses that leaf as a generic marketplace, but the leaf's Equifax source is literally `Amazon` and its IV note is Amazon-specific — polluting it with eBay/Vinted changes what the `marketplace_amazon` feature measures; consider a `marketplace_other` leaf); `costco` (mixed-basket by nature); `patreon` (`memberships` is arguably better than `online_services`); `national trust` (`memberships` vs `days_out`); the `web_services` vs `online_services` boundary (undefined — tiktok, facebook, linkedin); `groceries` vs `groceries_specialist` (ethnic grocers, doorstep milk — undefined boundary, same general).

## What this changes

1. **Your Excel pass remains the decisive artifact.** Nothing in this file replaces it. The flagged rows above are the ones to scrutinise hardest; most of the rest of the volume is dictionary-corroborated convention where all evidence points the same way.
2. **Two taxonomy governance items surfaced:** (a) define the `groceries`/`convenience_store`/`discount_store`/`groceries_specialist` boundaries in the taxonomy notes (three near-identical undefined leaves in one general invite exactly these disputes); (b) decide whether `marketplace_amazon` is Amazon-only (and add `marketplace_other`) or genuinely generic (and rename it).
3. **A prompt improvement for any future LLM labelling:** the systematic failure mode is surface-name vs transaction-function (catalogue credit, debt litigation, specialist lenders). The labelling prompt should explicitly instruct: "for merchants that are lenders, debt collectors, or credit providers, classify by the financial product being repaid, not by the merchant's trade description."

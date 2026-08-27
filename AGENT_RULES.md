# AGENT_RULES.md — labelling conventions

**Review status (2026-08-26): CLOSED.** The tranche-4 / 100k merchant review is finished. Snapshot: `data/production_labels_tranche4.csv` (`needs_review` = 0). Two dual-model abstain recovery passes ran; **do not start a third** (`pack_abstain3_*` leftover agents were force-stopped). Do not re-open review packs unless Carlos asks.

This file is still the **locked product/entity convention list** for any future T2/T4/T5 work or a later tranche. UK English. Closed taxonomy: `taxonomy/taxonomy.csv` `detailed_category` only. Never invent a leaf.

Do not score `data/gold_transactions_v5_LOCKED.csv` (retired) or `data/gold_transactions_v6_LOCKED.csv` (locked). Same-string gold: `data/gold_transactions.csv`, `data/gold_merchant_labels.csv`.

If a future review is reopened, the labelling prompt is:
`outputs/tranche4_agent_review/labelling_system_prompt.txt`
(taxonomy + TAIL_ADDENDUM + 446 worked notes). Use evidence fields. Gemini / Sonnet / Opus are **votes**, not ground truth.

## Locked product / entity conventions

- **Sheriff court / HMCTS** → `government_services` (not `legal_services`). Station taps on the same truncated string stay rail.
- **StepChange / step change** → `debt_management_plan`. Filled merchant is T4 (`stepchange`, `step change`). Blank merchant with `STEPCHANGE` in the narrative is T5 R31 (debit). Returned DD stays T2.
- **PayPal Credit** → T4 `paypal credit` / `paypal cre` / `paypal credi` is **`revolving_credit_repayment`**, not `bnpl`. Pay in 3/4 stay `bnpl` (`paypal pay in 4`, T2 `PAYIN3` on `paypal` / `paypal credit`). T2 when merchant is `paypal` (T4 paypal is the rail). T5 R32 for blank-merchant `PAYPAL *PAYPAL CRE`. Do not T4 a new generic `credit` key beyond the existing gold_v2 `credit` row.
- **Creditspring / credit spring** → `personal_loan_repayment` (not payday). Shared collection-account fingerprints (e.g. Starling `16-22-24`) are **not** Creditspring.
- **32 Red / 32red** → `gambling_casino`. Credits are T1 → `gambling_unspecified` per transaction; do not park the merchant on unspecified.
- **Lime / Voi / e-scooters** → `bicycle`, not taxi.
- **Morr + UK town** → `groceries` unless petrol/cafe in the narrative. Bare `morr` / `cd morr` are T4 groceries (Carlos 26 Aug). T2 still steers petrol/PFS/fuel → `fuel` and `caf[eé]` → `restaurant_cafe` before T4. R21 still covers other Morr+town truncations not in the dictionary.
- **Grocer + petrol/PFS** → `fuel`. Tesco + cafe → `restaurant_cafe`. In-store ATM/LINK → cash by direction.
- **HMRC credits** child benefit / tax credit / work-and-child tax credit → `benefits_state`; SA refund → `tax_refund`; HMRC debit default → `tax_payment`. Truncated DWP/HMRC benefit narratives (credit) also fire T5 R23.
- **Returned DD / DD reversal / “reversal of”** on a credit → `returned_payment` (T2, before T4). Do not put this in T5 — T4 would win on the original merchant.
- **Retailer credits** with refund / refunded in the narrative → `refund_received` (T2, before T4). Bookmaker credits stay gambling via T1.
- **Trading 212 / Trading212** → `investment_trading` (exact T4 keys `trading 212` and `trading212`; longer strings like `trading 212 pi` were already in).
- **Admiral** → T4 `insurance_general`; T2 `casino` in the narrative → `gambling_casino` before T4.
- **Ocado** → T4 `groceries`; T2 credit `CENTRAL SERV` → `salary`.
- **NOW TV** → T2/T5 `Entertai` / `PAYPAL *NOW` → `streaming`. Do **not** T4 bare `now`.
- **Close Brothers** → `car_finance_repayment` (motor finance), not personal loan. Do not T4 bare `close`.
- **Places for People** → T4 `rent`; T2 `leisure`/`nyx` → `gym_fitness`. `places for people leisure` is already T4 gym.
- **Creditspring** stays T4 `personal_loan_repayment`. Bare `spring` is not T4 (observed traffic is returned-DD credits; T2 `returned_payment` already).
- **Virgin Mobile** → T4 `mobile_phone_contract`; T2 `virgin money` in the narrative → `credit_card_repayment`.
- **Mercedes-Benz** is not T4. T2: `MBFIN` → `car_finance_repayment`; `of <town>` debit → `vehicle_servicing`; credit `of` → `salary`.
- **Off licence** → T4 `alcohol_beer_spirits`; T5 R29/R30 catch it in merchant/narrative when the key is truncated.
- **TK Maxx** → `department_store`. **Savers** → `health_beauty_general` unless clearly a pharmacy.
- **Google One** → `web_services`. **Rebtel** → `mobile_phone_contract`.
- **Payday** = Wonga-class HCSTC only (includes Loans2Go; not Creditspring, not BNPL, not doorstep/home credit, not credit cards). Doorstep/home credit → `personal_loan_repayment`. **Creditspring** → `personal_loan_repayment`. **National Education First** → `education_general` (not student loan). **Domestic & General** → `insurance_general`. **Ajjb Law** → `debt_collection`.
- **BNPL** = Klarna / Clearpay / Zilch / Laybuy checkout. Bumper garage PayLater → `retail_finance_repayment`. **Assist** (Payment Assist garage) → `bnpl` (Carlos 26 Aug).
- **Norton Home Loan** → `mortgage`. **`barclays bank`** → `mortgage` (Carlos: Barclays UK Mortgages DD). **Places for People** housing-association DDs → `rent`; leisure NYX tills → `gym_fitness`.
- Gambling subtypes **never** merged. Takeaway ≠ `restaurant_cafe`. **Five Guys** → `takeaway`. **Too Good To Go (`tgtg`)** → `takeaway`.
- **ParentPay / iPayimpact** → `school_fees`. **Ticketmaster / DICE** → `live_music`. **Shopify / Ring** → `web_services`.
- Lenders / collectors: classify the **financial product**, not the trade description.
- Personal name + LOAN/LEND/OWE/DEBT/IOU → `loan_repayment_manual`, never `transfer_p2p` or `personal_loan_repayment`.
- Named-person FPS: classify the **counterparty** (`transfer_p2p`). A purpose word in the payment reference (tickets, trainers, petrol, council, rent abbreviation) is a memo, not a reason to look through to that product. Exception is the debt-keyword rule above. Do not treat FPS as `transfer_p2p` by default when the merchant is a business.
- Amount-only pub vs lodging / machines / cafe on a pub-named venue → `pub_bar` (the recognisable default). True two-way ties with no pub cue still stay flagged.
- T4 dictionary wins for the **same entity**. Same string, different products → `t2_candidate`, do not silent-overwrite T4. Do not ingest `context_dependent` / T2 collision keys / `unclassified_*` into T4. Do not dictionary `cd glasgow`, Drayton Court, Fountain Hotel.
- Bookmaker/casino **credits** stay in-family. Retailer refund credits → often `refund_received`.
- **mixed_basket** when mixed-goods retailers cannot determine necessity.

## Historical review output (do not resume)

When the 100k review was live, pack rows were:

`merchant,recommended_leaf,confidence,disagree_with,reason,web_sources,t2_candidate,human_review`

`human_review`: `yes` only if a human must decide; otherwise `no`.
`confidence`: high / medium / low.
Web-search UK-first (Companies House, brand site) for obscure names.

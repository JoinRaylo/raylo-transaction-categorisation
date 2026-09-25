# AGENT_RULES.md — labelling conventions

**Canonical names (Carlos, 17 Sep 2026):** the complete T1–T7 pipeline is the
**Raylo Transaction Categorisation Engine** or **Raylo TxCat Engine**. The T6
transformer is **TxCat-1**; this name does not include the hinge rollback or the
full engine. Follow [`docs/NAMING.md`](docs/NAMING.md) in new documentation and
communication while preserving historical artefacts.

**Waterfall change process (Carlos, 15 Sep 2026):** follow
[POLICY.md](docs/waterfall-changes/POLICY.md) for every behavioural change. Document
the hypothesis, rerun the complete permitted evaluation suite, mirror the app and
research implementations, and record baseline/candidate scores and regressions
in both repos. See [score history](docs/waterfall-changes/README.md). Locked-set
restrictions below still apply. No change is complete without this evidence.

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
- **Card-issuer repayments with a masked card token** (`HSBC BNK VSA…******4482`, `LLOYDS BANK PLATIN 3000…`, `ACC-NWESTPLAT 5522…`, `CREDIT CARD 6000…`, Aqua/Vanquis/MBNA/Barclaycard/Capital One/NewDay/Marbles/Fluid/Zopa/M&S/John Lewis/Virgin Money/Halifax/Tesco Bank card) on a **debit** → `credit_card_repayment` (T5 R34, description, after T4). **American Express** → `charge_card_repayment` (T5 R33). Card-issuer **credits** → `cash_advance` (Carlos 3 Sep). 3 Sep.
- **Overdraft narratives (debit, blank merchant):** `unarranged` / `unauthorised` / `unplanned overdraft` → `overdraft_unarranged` (R35); bare `OVERDRAFT INTEREST TO <date>` → `interest_charged` (R36, Carlos 3 Sep); `Arranged Overdraft …`, `<Month> overdraft fees`, and bare `Overdraft` → `overdraft_arranged` (R37; Carlos 3 Sep: default arranged).

## Risk-tranche conventions (Carlos accepted all 14 on 3 Sep 2026; 7 and 8 reworded)

1. Zettle / SumUp + unknown trader (incl. sole-trader personal names) → `retail_small_independent`, not `transfer_p2p`. Not a T5 rule (Zettle is a rail; 95% of Zettle rows have a known merchant).
2. Named-person FPS with an "overdraft" memo → `transfer_p2p`; "Overdraft repaymen" to a person → `loan_repayment_manual`. The R35–R37 overdraft rules are for blank-merchant bank narratives only.
3. `TRAVL PLUS/PCK FEE … PDP`, `SERVICE CHARGES REF`, `Llond Plat` → `account_charge` (T5 R51).
4. `CASE: DRS… CARD: ****` collections-portal card payment → `debt_collection` (T5 R50).
5. ACI UK Ltd / `ACIUKLTD` → `debt_collection` (T4 keys + T5 R47).
6. Debit Finance Collections (DFC) is a DD bureau → `unclassified_recurring`, or the underlying club if named. Never `debt_collection`.
7. "<Name> Collection": verify the entity first; only fashion brands go to `clothing_general`; never `debt_collection` by default (Sabas = wholesale perfume → `retail_other`).
8. Home Retail Group Card Services (Argos card, `HME RTL GRP CARDS`) → `revolving_credit_repayment` (same call as PayPal Credit), not `catalogue_retail` / `credit_card_repayment` (T4 key + T5 R46).
9. Racecourse tills (Chester Race Company) → `sports_tickets`; gambling needs an identifiable operator.
10. Payment Assist → `bnpl` (T4 `payment-assist.co.uk` retargeted; T5 R48). Fair for You → `personal_loan_repayment` (T4 `fairforyou` retargeted; T5 R49).
11. POA £16 monthly DD = Prison Officers' Association → `trade_union`; card-spend `poa` stays `restaurant_cafe` (rail split, not T4).
12. Ooodles → `retail_finance_repayment` (T4 `ooodles finance` retargeted from car finance).
13. Cashplus / APS Financial → `prepaid_card`; Airwallex / Venturist business sweeps → `transfer_bank_unspecified`; Securus → `broadband_tv_phone`; "To GBP Debt" pot → `transfer_own_account`.
14. Blank-merchant forms of known T4 keys become T5 description rules (R38–R45: your plan card payment, dfh, fgfs, ukcc, smart charge, madesimplegroup). Not added: imgflux / floxyhealth (EUR foreign-spend convention conflict).
Also: unpaid/returned-item **fees** on a debit are `bank_charge_other`, not `returned_payment` (that leaf is the credit-side reversal). Tide per-transaction fee → `account_charge`. `kmc main` → `mortgage` (Kensington Mortgage Company).

## Historical review output (do not resume)

When the 100k review was live, pack rows were:

`merchant,recommended_leaf,confidence,disagree_with,reason,web_sources,t2_candidate,human_review`

`human_review`: `yes` only if a human must decide; otherwise `no`.
`confidence`: high / medium / low.
Web-search UK-first (Companies House, brand site) for obscure names.

# Adjudicated gating verdict

Consensus rows (both models agree, non-abstained): 1615
- Already matched the Equifax label (assumed correct): 1239
- Disputes sent to adjudication: 376
- Annotation breakdown: both_acceptable=47, both_wrong=5, context_dependent=49, equifax_correct=56, llm_correct=216, unsure=3

## Corrected consensus accuracy (leaf level)
- Over resolved rows: **96.1%**
- 49 context_dependent rows excluded from the scoreable pool (1566 of 1615 remain)
- Bounds given 3 unresolved (blank/unsure) rows: 95.9% (all wrong) to 96.1% (all right)

## Context-dependent merchants (candidates for transaction-level T1/T2 rules, not dictionary entries)
- revolut -- Direction matters: Revolut transactions split between own-account and unspecified external transfers.
- monzo -- Direction and counterparty matter: Monzo transactions include own-account, external transfers and salary credits.
- marks & spencer -- Provider/entity split: Plaid is department-store spend; Equifax narratives are M&S CREDIT CARD repayments.
- tiktok -- The generic TikTok string can mean platform/services activity or TikTok Shop seller activity.
- welcome break -- Welcome Break service-area transactions span convenience retail and restaurants.
- freemans -- Provider/entity split: Plaid presents the catalogue retailer; Equifax includes Freemans agency/finance repayments.
- ticketmaster -- Ticketmaster sells music, sports and other event tickets; the underlying event is needed.
- legal & general -- Legal & General spans life insurance, general insurance and pension products.
- next directory -- Next Directory can represent catalogue purchases or account/retail-finance repayments.
- metlife -- MetLife spans life-insurance and pension products; the product is not identifiable from the merchant alone.
- mace -- Mace is polysemous and the Plaid native category conflicts with the grocery/convenience interpretation.
- fatsoma -- Fatsoma sells tickets across club nights, gigs, festivals, comedy, sports, business conferences and other categories—not exclusively live music.
- leon -- Provider/entity split: Plaid is the Leon restaurant chain; Equifax narratives are personal transfers to people named Leon.
- curve -- Provider/entity split: Curve may be the payment-card intermediary, while Equifax records CRV token exchange.
- jaguar land rover -- Jaguar Land Rover can represent a vehicle purchase, servicing/parts or salary credits.
- viagogo -- Viagogo ticket type varies with the underlying event (music, sport or other).
- aldermore bank -- Aldermore transactions span mortgage and other banking products; no single merchant-level leaf is reliable.
- wembley stadium -- Stadium transactions can be sports tickets, concerts or on-site spend.
- countrywide -- Provider/entity split: Countrywide can mean estate agency, while Equifax narratives here are insurance. Countrywide Assure are insurance/pension
- child maintenance -- Child maintenance can be incoming income or an outgoing transfer; direction is required.
- rbs -- RBS is a multi-product bank. Use transaction descriptions to identify personal-loan repayments; the generic merchant string alone is insufficient.
- savills -- Savills payments can be rent, property services or estate-agent fees.
- betuk -- BetUK offers betting and casino products; the underlying transaction is needed.
- paul smith -- Provider/entity split: Paul Smith can be the fashion merchant or a personal-transfer counterparty.
- aldo -- Provider/entity split: Aldo can be the footwear merchant or a personal-transfer counterparty.
- the bottle shop -- A bottle shop may sell wine, beer and spirits; product-level context is required.
- rangers fc -- A football-club descriptor can cover tickets, merchandise and other club spend.
- principality building society -- A building-society descriptor can represent mortgage payments or other banking activity.
- st vincent de paul society -- St Vincent de Paul transactions can be donations or charity-shop purchases.
- st barnabas hospice -- A hospice descriptor can represent a care payment or a charitable donation.
- arsenal fc -- A football-club descriptor can cover tickets, merchandise and other club spend.
- habitat -- Provider/entity split: Habitat can refer to the homewares retailer, a charity, or another organisation.
- tiso -- Provider/entity split: Plaid suggests the outdoor retailer, while Equifax narratives are personal transfers to people named Tiso.
- spicerhaart -- Estate-agent descriptor may represent rent collection, agency fees or salary; transaction context is required.
- reeds rains -- Estate-agent descriptor may represent rent collection or agency fees; transaction context is required.
- west bromwich building society -- Mostly mortgage, but may also be general banking - use transaction context to help decide
- jigsaw homes -- Housing-association payment is most plausibly rent; neither candidate captures the transaction purpose.
- we buy any car -- Direction matters: payments to and credits from We Buy Any Car represent different transaction purposes.
- willow wood hospice -- A hospice descriptor can represent a charitable donation or an adult-care service.
- emmaus -- Emmaus can be a charity-shop purchase or a donation.
- scrumbles -- Provider/entity split: Scrumbles can be the pet-food brand or an unrelated cake shop.
- poynton pakora -- Equifax records are mostly credits/transfers, while the merchant name implies a takeaway; direction/entity context is required.
- secc arena -- The arena hosts concerts, sports and other events; the event type is required.
- musto -- Provider/entity split: Musto can be the outdoor brand or a surname in personal transfers.
- the cash shop -- The Cash Shop may represent payday lending or pawnbroking; product context is required.
- toffs -- Provider/entity split: TOFFS can be the clothing brand or an unrelated food/restaurant merchant.
- kickers -- Provider/entity split: Kickers can be the footwear brand or Little Kickers sports classes.
- extracare -- ExtraCare can represent charity retail/donations or adult-care housing/services.
- bh live tickets -- BH Live ticket purchases vary across music, sport, theatre and other events.

## Verdict (CLAUDE.md §6 thresholds, applied to the corrected figure)
**>=95% GREEN LIGHT** even under the pessimistic bound -- proceed with consensus-gated LLM vocabulary labelling.

## Merchant-dictionary additions
195 adjudicated merchants exported to `gating_dictionary_additions.csv` (T4 candidates, already human-approved by this review).
# -*- coding: utf-8 -*-
import csv
import pathlib
from label_provenance import DICTIONARY_ELIGIBLE_TIERS

ROOT = pathlib.Path(__file__).resolve().parents[1]
# (merchant, leaf, confidence, note)
D = [
# ---- GROCERIES / SUPERMARKETS
("tesco","groceries","high",""),("asda","groceries","high",""),("sainsbury's","groceries","high",""),
("co-op","groceries","high",""),("morrisons","groceries","high",""),("aldi","groceries","high",""),
("lidl","groceries","high",""),("iceland","groceries","high",""),("spar","groceries","high",""),
("one stop","groceries","high",""),("nisa","groceries","high",""),("londis","groceries","high",""),
("costcutter","groceries","high",""),("heron foods","groceries","high",""),("waitrose","groceries","high",""),
("farmfoods","groceries","high",""),("budgens","groceries","high",""),("premier stores","groceries","high",""),
("best-one","groceries","high",""),("centra","groceries","high",""),("keystore","groceries","high",""),
("martin mccoll","convenience_store","high",""),("central england co-op","groceries","high",""),
("the southern co-op","groceries","high",""),("scotmid co-op","groceries","high",""),
("east of england co-op","groceries","high",""),("marks and spencer food","groceries","high",""),
("costco","groceries","medium","warehouse club - mixed basket; Plaid says superstore, Equifax says dept store"),
("mcqueens dairies","groceries_specialist","high","doorstep milk delivery - adjudicated 2026-08-19"),
("bargain booze","alcohol_beer_spirits","high","age-restricted"),
# ---- DISCOUNT / VARIETY
("home bargains","discount_store","high",""),("b&m","discount_store","high",""),
("poundland","discount_store","high",""),("poundstretcher","discount_store","high",""),
("onebelow","discount_store","high",""),("the range","home_accessories","high",""),
("wilko.com","home_accessories","high",""),("the works","books","medium","books/craft discount retailer"),
# ---- EATING OUT
("mcdonalds","takeaway","high",""),("mcdonald's","takeaway","high",""),("kfc","takeaway","high",""),
("subway","takeaway","high",""),("burger king","takeaway","high",""),("dominos pizza","takeaway","high",""),
("pizza hut","takeaway","high",""),("nandos","restaurant_cafe","high",""),("leon","restaurant_cafe","high",""),
("greggs","restaurant_cafe","high",""),("costa","restaurant_cafe","high",""),("starbucks","restaurant_cafe","high",""),
("caffe nero","restaurant_cafe","high",""),("pret a manger","restaurant_cafe","high",""),
("just eat","takeaway","high","delivery aggregator - Plaid says DINING, we say takeaway"),
("uber eats","takeaway","high","delivery aggregator"),("deliveroo","takeaway","high","delivery aggregator"),
("foodhub","takeaway","high",""),("takeaway.je","takeaway","high",""),
("wetherspoon","pub_bar","high","age-restricted"),("greene king","pub_bar","high","age-restricted"),
("the red lion","pub_bar","medium","generic pub name - may aggregate many venues"),
("selecta","confectionary","medium","vending machine operator"),
("lavazza professional","confectionary","medium","workplace coffee vending"),
("welcome break","convenience_store","medium","motorway services - mixed fuel/food/retail"),
# ---- GAMBLING (all age-restricted)
("sky bet","gambling_betting","high",""),("skybet","gambling_betting","high",""),
("ladbrokes","gambling_betting","high",""),("bet365","gambling_betting","high",""),
("paddy power","gambling_betting","high",""),("william hill","gambling_betting","high",""),
("betfred","gambling_betting","high",""),("betfair","gambling_betting","high",""),
("betvictor","gambling_betting","high",""),("virgin bet","gambling_betting","high",""),
("betway","gambling_betting","high",""),("unibet","gambling_betting","high",""),
("livescore bet","gambling_betting","high",""),("boylesports","gambling_betting","high",""),
("lc international","gambling_betting","high","Ladbrokes Coral trading entity"),
("electraworks limit","gambling_casino","high","Entain/bwin trading entity"),
("skill on net ltd","gambling_casino","high","casino operator"),
("virgin games","gambling_casino","high",""),("monopoly casino","gambling_casino","high",""),
("32 red online casino","gambling_casino","high",""),("rainbow riches casino","gambling_casino","high",""),
("grosvenor casinos","gambling_casino","high",""),("888 games","gambling_casino","high",""),
("tombola","gambling_bingo","high",""),("mecca bingo","gambling_bingo","high",""),
("jackpot joy","gambling_bingo","high",""),("sun bingo","gambling_bingo","high",""),
("double bubble bingo","gambling_bingo","high",""),("butlers bingo","gambling_bingo","high",""),
("buzz group ltd","gambling_bingo","high","Buzz Bingo"),("mrq","gambling_casino","high","MrQ casino"),
("the national lottery","gambling_lottery","high",""),("postcode lottery","gambling_lottery","high",""),
("lotto land","gambling_lottery","high",""),
("that prize guy","prize_competitions","high","prize competition - gambling-adjacent"),
# ---- BNPL / CREDIT
("clearpay","bnpl","high",""),("zilch","bnpl","high",""),("klarna","bnpl","high",""),
("laybuy","bnpl","high",""),("monzo flex","bnpl","high",""),
("paypal credit","revolving_credit_repayment","high","revolving line, not Klarna-style BNPL"),
("capital one","credit_card_repayment","high",""),("barclaycard","credit_card_repayment","high",""),
("vanquis bank","credit_card_repayment","high","subprime card - Plaid mislabels as personal loan"),
("aqua","credit_card_repayment","high","NewDay subprime card"),
("newday limited","credit_card_repayment","high","issuer of Aqua/Marbles"),
("zable credit card","credit_card_repayment","high",""),
("american express","credit_card_repayment","high",""),
("creation online","retail_finance_repayment","high","Creation Finance - retail credit"),
("v12 retail finance","retail_finance_repayment","high",""),
("barclays partner finance","retail_finance_repayment","high",""),
("very","catalogue_retail","high","catalogue with embedded credit"),
("jd williams","catalogue_retail","high","catalogue with embedded credit"),
("next directory","catalogue_retail","high","catalogue with embedded credit"),
("zopa","personal_loan_repayment","high",""),("lendable","personal_loan_repayment","high",""),
("creditspring","personal_loan_repayment","high","credit-builder / subscription lender, not payday"),
("118 money","payday_loan","high","high-cost lender"),
("lending stream","payday_loan","high","high-cost short-term lender"),
("lowell financial","debt_collection","high",""),
("moorcroft debt recovery","debt_collection","high",""),
("cabot","debt_collection","high","Cabot Credit Management"),
("raylo","retail_finance_repayment","high","RAYLO'S OWN PRODUCT - 11,226 txns. Consider a dedicated leaf"),
# ---- BANKS / FINTECH / PAYMENTS
("revolut","transfer_own_account","medium","neobank - could be transfer or spend"),
("monzo","transfer_own_account","medium","neobank"),("starling bank","transfer_own_account","medium","neobank"),
("halifax","financial_institution_unspecified","low","bank name only - purpose unknown"),
("lloyds","financial_institution_unspecified","low",""),("natwest","financial_institution_unspecified","low",""),
("santander bank","financial_institution_unspecified","low",""),("barclays","financial_institution_unspecified","low",""),
("nationwide","financial_institution_unspecified","low",""),("tsb","financial_institution_unspecified","low",""),
("hsbc","financial_institution_unspecified","low",""),("tesco bank","financial_institution_unspecified","low",""),
("paypal","payment_intermediary","high","obscures underlying merchant"),
("gocardless","payment_intermediary","high",""),("stripe","payment_intermediary","high",""),
("mangopay","payment_intermediary","high",""),("trustly group","payment_intermediary","high",""),
("gohenry","prepaid_card","high","children's prepaid card"),
("remitly","transfer_international","high","remittance"),
("taptap send uk limited","transfer_international","high","remittance"),
("coinbase","crypto","high",""),
# ---- SAVINGS
("save the change","savings_transfer","high","Lloyds round-up"),
("save the pennies","savings_transfer","high","round-up"),
("plum","savings_transfer","high",""),("moneybox","savings_transfer","high",""),
("loqbox","savings_transfer","medium","savings-based credit builder - arguably credit_reporting_service"),
# ---- BENEFITS / STATE (credits)
("universal credit","benefits_state","high",""),("child benefits","benefits_state","high",""),
("carers allowance","benefits_state","high",""),("personal independence payment","benefits_state","high",""),
("employment and support allowance","benefits_state","high",""),
("disability living allowance","benefits_state","high",""),("child tax credit","benefits_state","high",""),
("work and child tax credit","benefits_state","high","HMRC combined WTC/CTC; Plaid merchant string"),
("housing benefits","benefits_state","high",""),("pension credit","benefits_state","high",""),
("state pension","pension_received","high",""),
("child maintenance","income_other_unspecified","medium","direction-dependent: received or paid"),
("overpayments","income_other_unspecified","low","likely benefit overpayment recovery - ambiguous"),
("hmrc","tax_payment","medium","debit default; T2 splits Child Benefit / tax-credit credits and SA refunds"),
("hm revenue and customs","tax_payment","medium","debit default; T2 splits Child Benefit / tax-credit credits and SA refunds"),
# ---- UTILITIES / TELCO
("british gas","energy","high",""),("utilita","energy","high",""),("ovo energy","energy","high",""),
("scottish power","energy","high",""),("octopus energy","energy","high",""),("e.on","energy","high",""),
("edf","energy","high",""),("united utilities","water","high",""),("severn trent","water","high",""),
("thames water","water","high",""),("anglian water","water","high",""),
("tv licensing","tv_licence","high",""),
("o2","mobile_phone_contract","high",""),("vodafone","mobile_phone_contract","high",""),
("ee mobile","mobile_phone_contract","high",""),("three","mobile_phone_contract","high",""),
("sky mobile","mobile_phone_contract","high",""),("tesco mobile","mobile_phone_contract","high",""),
("id mobile","mobile_phone_contract","high",""),("giffgaff.com","mobile_phone_contract","high",""),
("voxi","mobile_phone_contract","high",""),("smarty","mobile_phone_contract","high",""),
("lebara","mobile_phone_contract","high",""),
("sky","broadband_tv_phone","high","Plaid mislabels as telecoms/mobile"),
("virgin media","broadband_tv_phone","high",""),("bt","broadband_tv_phone","high",""),
("talktalk","broadband_tv_phone","high",""),
("domestic and general","insurance_general","high","appliance warranty/insurance"),
# ---- TRANSPORT
("tfl","public_transport_rail_coach","high",""),("transport for london","public_transport_rail_coach","high",""),
("thetrainline","public_transport_rail_coach","high",""),("arriva","public_transport_rail_coach","high",""),
("stagecoach","public_transport_rail_coach","high",""),("first bus","public_transport_rail_coach","high",""),
("national express","public_transport_rail_coach","high",""),("go north east","public_transport_rail_coach","high",""),
("lothian buses","public_transport_rail_coach","high",""),("go south coast","public_transport_rail_coach","high",""),
("citylink","public_transport_rail_coach","medium","Scottish Citylink coaches; may collide with defunct courier"),
("uber","taxi_rideshare","high","rides - distinct from uber eats"),("bolt","taxi_rideshare","high",""),
("voi","bicycle","high","Voi UK e-scooter/e-bike hire; same leaf as Lime"),
("voi uk","bicycle","high","Plaid merchant string for Voi"),
("shell","fuel","high",""),("bp","fuel","high",""),("esso","fuel","high",""),("texaco","fuel","high",""),
("motor fuel group","fuel","high",""),("applegreen","fuel","high",""),
("tesco fuel","fuel","high",""),("asda (petrol)","fuel","high",""),
("morrisons (petrol)","fuel","high",""),("sainsbury's petrol","fuel","high",""),
("dvla","road_tax","high",""),
("ringgo parking","car_parking","high",""),("apcoa parking","car_parking","high",""),
("ncp","car_parking","high",""),("mipermit","car_parking","high",""),("pay by phone","car_parking","high",""),
("halfords","vehicle_maintenance","high",""),("aa","breakdown_cover","high",""),("rac","breakdown_cover","high",""),
("hastings direct","insurance_motor","high",""),("admiral insurance","insurance_motor","high",""),
# ---- TRAVEL
("ryanair","flights","high",""),("easyjet","flights","high",""),
("booking.com","accommodation","high",""),("trip.com","accommodation","high",""),
("haven holidays","holiday_uk","high",""),("loveholidays.com","holiday_package","high",""),
# ---- DIGITAL / SUBSCRIPTIONS
("netflix","streaming","high","video streaming subscription"),
("spotify","streaming","high",""),("disney plus","streaming","high",""),
("amazon prime video","streaming","high",""),("now tv","streaming","high",""),
("audible","streaming","high",""),("prime","streaming","medium","Amazon Prime subscription - 161k txns"),
("apple app store","software","high",""),("google play","software","high",""),
("google one","web_services","high","Google One cloud storage, not App Store software"),
("rebtel","mobile_phone_contract","high","international calling / VoIP, not a software store"),
("bandoo","health_beauty_general","high","Bandoo ionic foot-detox retail"),
("3s retail ltd","convenience_store","high","SIC 47110 food/drink/tobacco shop"),
("ingle store","convenience_store","high","Ingle Store convenience; Plaid sometimes collapses onto Apple Store"),
("morr derby","groceries","high","Plaid Morrisons truncation"),
("microsoft","software","high","Plaid mislabels as computing hardware"),
("mircosoft","software","high","misspelling in source data"),
("adobe","software","high",""),("google","software","medium","ambiguous - could be Play/Workspace/Ads"),
("apple","software","medium","ambiguous - App Store vs hardware"),
("playstation","gaming_console_pc","high",""),("xbox","gaming_console_pc","high",""),
("steamgames","gaming_console_pc","high",""),("nintendo","gaming_console_pc","high",""),
("sony","gaming_console_pc","medium","could be PlayStation or consumer electronics"),
("play.com","gaming_console_pc","low","AMBIGUOUS 300k txns - defunct retailer vs Google/PlayStation. NEEDS REVIEW"),
("tiktok","online_services","medium","in-app purchases/gifting"),
("facebook","online_services","medium",""),
("onlyfans","adult_entertainment","high","age-restricted"),
("ring.com","home_accessories","medium","smart doorbell - device + subscription"),
# ---- RETAIL
("amazon","marketplace_amazon","high",""),("ebay","marketplace_general","high","split from marketplace_amazon 2026-08-19"),
("vinted","marketplace_general","high","secondhand marketplace - Equifax says fashion"),
("etsy","marketplace_general","medium",""),("aliexpress","marketplace_general","high",""),
("marketplace","marketplace_general","low","AMBIGUOUS 405k txns - likely Facebook Marketplace. NEEDS REVIEW"),
("argos","catalogue_retail","high",""),("home retail","catalogue_retail","high","Argos parent"),
("marks and spencer","department_store","high","Equifax mislabels as credit card (M&S Bank)"),
("primark","clothing_general","high",""),("shein","clothing_general","high",""),
("h&m","clothing_general","high",""),("zara","clothing_general","high",""),("asos","clothing_general","high",""),
("boohoo","clothing_general","high",""),("new look","clothing_general","high",""),
("river island","clothing_general","high",""),("matalan","clothing_general","high",""),
("burton","clothing_general","high",""),("next","clothing_general","high",""),
("tk maxx","department_store","high","TK Maxx is off-price department, not clothing-only"),("pretty little things","clothing_general","high",""),
("george at asda","clothing_general","high",""),
("jd sports","sportswear","high",""),("sports direct","sportswear","high",""),("nike","sportswear","high",""),
("boots","pharmacy","medium","pharmacy + beauty - genuine mixed basket"),
("superdrug","pharmacy","medium","pharmacy + beauty"),("savers health","health_beauty_general","medium","beauty-led retail, not a chemist"),
("holland & barrett","supplements","high",""),("specsavers","optician","high",""),
("currys","computing_devices","high",""),("cex","computing_devices","high","secondhand electronics"),
("ikea","home_accessories","high",""),("dunelm","home_accessories","high",""),
("b&q (diy.com)","home_improvement","high",""),("wickes","home_improvement","high",""),
("screwfix","tools","high",""),("toolstation","tools","high",""),
("card factory","gifts_flowers","high",""),("moonpig","gifts_flowers","high",""),
("smyths toys","toys","high",""),("w.h.smith","books","high",""),
("pets at home","pet_supplies","high",""),("vets gen","veterinary","medium","veterinary practice"),
("animal friends insurance","insurance_pet","high",""),
("royal mail","delivery_courier","high",""),("post office","government_services","medium","mixed: postal, banking, bill payment"),
("u.s. post office","delivery_courier","low","US entity in UK data - likely mislabel"),
# ---- HEALTH / LEISURE
("pure gym","gym_fitness","high",""),("the gym website","gym_fitness","high",""),
("vue cinemas","cinema","high",""),("cineworld","cinema","high",""),("odeon","cinema","high",""),
# ---- INSURANCE / LIFE
("legal & general","insurance_life","high",""),("aviva li","insurance_life","high",""),
("aviva","insurance_general","high",""),("sunlife","insurance_life","high",""),
# ---- EDUCATION
("parent pay","school_fees","high","school payment platform"),
# ---- 2026-08-24 human T4 overrides ----
# Winnerz: Carlos confirmed convenience store; overwrites tranche-3 gambling_unspecified.
# The rest are gold_v2 holdout merchants that T1-T5 missed (classifier then
# wrongly promoted them to gambling_unspecified). Exact merchant_raw keys.
# Skipped: "expo" (too generic -- trade shows vs supermarket),
# "genistar limited" (gold is unclassified_card_spend -- T4 must not encode unclassified).
# Expo International: T4 is exact-match, so the LIKE "sup%" is two keys -- the
# untruncated name plus the Plaid truncation already labelled in tranche 3
# (38 txns, accepted_tiebreak, excluded from auto-merge). Bare "expo" stays out.
("rk winnerz","convenience_store","high","human override 2026-08-24: convenience store, not gambling"),
("expo international","groceries_specialist","high","Expo International supermarket; not generic expo"),
("expo international superm","groceries_specialist","high","Plaid truncation of Expo International supermarket"),
("accessorize","jewellery","high","gold_v2 holdout; T4 gap"),
("ai-acc.co.uk","online_services","high","gold_v2 holdout; T4 gap"),
("alton towers","days_out","high","gold_v2 holdout; T4 gap"),
("model management limited","income_agency_work","medium","gold_v2 holdout credit from a model agency; direction-blind T4"),
("fedex","delivery_courier","high","gold_v2 holdout; T4 gap"),
("which?","magazines","high","gold_v2 holdout; T4 gap"),
("amber pool & sports","sports_participation","high","gold_v2 holdout; T4 gap"),
("brokersure ltd","insurance_general","high","gold_v2 holdout; T4 gap"),
("hutchison 3g uk","mobile_phone_contract","high","Three / Hutchison; gold_v2 holdout; T4 gap"),
# ---- JUNK / UNRESOLVABLE
("e","unclassified_other","low","JUNK STRING 21k txns - truncated merchant name"),
("current","unclassified_other","low","JUNK STRING 21k txns"),
("debit finance","unclassified_other","low","DD collection agent - underlying purpose unknown"),
("apple store gb","computing_devices","medium","Apple retail - hardware"),
]

# ---- context-dependent merchants from gating adjudication (2026-08-19), resolved to a
# single best-guess leaf where the evidence (eqx_category_mix dominance, or an explicit
# human correct_leaf) clearly favours one reading. The other ~30 of the 49 flagged
# context-dependent merchants had no dominant signal and are deliberately left out --
# forcing a leaf there would misclassify a large minority share. See
# data/gating_adjudication_completed.xlsx for the full set and reasoning.
CONTEXT_DEPENDENT = [
    ("marks & spencer","department_store","medium","alias of 'marks and spencer' - M&S Bank credit card vs store entity split"),
    ("freemans","catalogue_retail","low","Plaid native 100% marketplace; Equifax's own retail-finance tag reflects its dictionary convention, not independent evidence"),
    ("betuk","gambling_casino","low","evidence-backed: eqx 100% Poker and Casino Games, despite betting-sounding brand name"),
    ("the bottle shop","alcohol_beer_spirits","medium","evidence-backed: eqx 100% Alcoholic Beverages Wines"),
    ("rangers fc","sports_tickets","low","evidence-backed: eqx 97% Sporting General"),
    ("st vincent de paul society","charitable_donation","medium","evidence-backed: eqx 99% Charitable Giving, overrides LLM's charity_shop guess"),
    ("arsenal fc","sports_tickets","low","evidence-backed: eqx 95% Sporting General"),
    ("habitat","home_accessories","medium","evidence-backed: eqx 85% Home Improvements"),
    ("tiso","clothing_outdoor","low","evidence-backed: eqx 70% Sports Equipment; outdoor-gear retailer"),
    ("reeds rains","estate_agent","low","evidence-backed: eqx 96% Property Rental; safe either way (housing general category)"),
    ("jigsaw homes","rent","medium","human-adjudicated correct_leaf (gating review) - housing-association payment"),
    ("emmaus","charity_shop","low","evidence-backed: eqx 77% Charitable Giving; charity_shop and charitable_donation share a general category"),
    ("scrumbles","pet_supplies","medium","evidence-backed: eqx 98% Pet Care"),
    ("secc arena","days_out","medium","evidence-backed: eqx 100% Days Out, overrides LLM's live_music guess"),
    ("the cash shop","payday_loan","medium","evidence-backed: eqx 97% Payday Loans, overrides LLM's pawnbroker guess"),
    ("toffs","sportswear","medium","evidence-backed: eqx 100% Sportswear"),
    ("kickers","footwear","medium","evidence-backed: eqx 95% General Fashion"),
    ("extracare","charitable_donation","medium","evidence-backed: eqx 100% Charitable Giving, overrides LLM's adult_care guess"),
    ("bh live tickets","live_music","medium","evidence-backed: eqx 100% Music Tickets, overrides LLM's sports_tickets guess"),
]

seen=set(); rows=[]
for m,leaf,conf,note in D:
    if m in seen: print("DUPLICATE:",m); continue
    seen.add(m)
    # Original seed was written as pending and never flipped after gating
    # green-lit T4. Tesco/Asda/etc. are the curated dictionary, not drafts.
    # Leave genuine NEEDS REVIEW / unclassified_* as pending so T4 skips them.
    note_u = (note or "").upper()
    if leaf.startswith("unclassified") or "NEEDS REVIEW" in note_u:
        status = "pending"
    else:
        status = "approved"
    rows.append({"normalised_merchant":m,"detailed_category":leaf,
        "confidence":conf,"source":"llm_proposed","review_status":status,"notes":note})

for m,leaf,conf,note in CONTEXT_DEPENDENT:
    if m in seen: print("DUPLICATE:",m); continue
    seen.add(m); rows.append({"normalised_merchant":m,"detailed_category":leaf,
        "confidence":conf,"source":"gating_adjudication","review_status":"approved","notes":note})

for r in csv.DictReader(open(ROOT / "data" / "gating_dictionary_additions.csv")):
    m = r["normalised_merchant"]
    if m in seen: print("DUPLICATE:",m); continue
    seen.add(m); rows.append(r)

# ---- candidates from the gold_transactions_v2 hand review (2026-08-21) ----
# Only promotes a merchant to a blanket T4 override when it's SAFE to do so:
#   - every occurrence in the gold set agrees on the same leaf (a merchant that
#     shows genuine conflict -- e.g. "revolut" resolving to three different
#     leaves depending on the transaction -- proves by construction that it
#     must NOT get a single fixed answer)
#   - not a generic payment rail/processor string (revolut, paypal, gocardless,
#     allpay, stripe, ...) even if this small sample happened to only show one
#     use of it
#   - not a mechanism-dependent leaf (refund_received, salary, cashback,
#     transfer_p2p, ...) -- those describe what a SPECIFIC transaction's
#     direction/mechanism was, not a stable property of the merchant. Adding
#     "selfridges -> refund_received" would wrongly override every normal
#     Selfridges purchase, which is a debit, not a refund.
#   - has a reviewer note -- the note is what distinguishes "the reviewer
#     worked out something specific and non-obvious" from "an unremarkable
#     single observation," and a spot-check of the un-noted candidates found
#     they're full of garbled reference-number strings and generic words that
#     do not generalise (e.g. "spring", "faster", "2awrs mandate no").
import re as _re_gv2
from collections import defaultdict as _defaultdict

_GOLD_V2_FILES = [ROOT / "data" / "gold_transactions_v2.csv", ROOT / "data" / "gold_transactions_v2_batch2.csv"]
_GENERIC_RAIL_PATTERN = _re_gv2.compile(
    r"revolut|monzo|starling|paypal|gocardless|\bstripe\b|sumup|izettle|worldpay|allpay|"
    r"faster payment|direct debit|standing order|card payment|bank transfer|"
    r"transfer to|transfer from|payment to|payment from|sent from|withdrawal|\bdeposit\b",
    _re_gv2.I)
_MECHANISM_LEAVES = {"refund_received", "salary", "salary_gig", "income_agency_work", "benefits_state",
    "pension_received", "tax_refund", "cashback", "cash_withdrawal", "cash_deposit",
    "savings_interest_received", "balance_transfer", "adjustment", "transfer_p2p",
    "transfer_own_account", "transfer_bank_unspecified", "transfer_mobile_app",
    "overdraft_arranged", "returned_payment", "income_other_unspecified", "tax_payment",
    "debt_collection"}

_by_merchant = _defaultdict(list)
for _f in _GOLD_V2_FILES:
    if _f.exists():
        for _r in csv.DictReader(open(_f)):
            _by_merchant[_r["merchant_raw"].strip().lower()].append(_r)

_gv2_added = 0
for m, recs in sorted(_by_merchant.items()):
    if m in seen:
        continue
    leaves = {r["gold_leaf"] for r in recs}
    if len(leaves) > 1 or _GENERIC_RAIL_PATTERN.search(m):
        continue
    leaf = next(iter(leaves))
    if leaf in _MECHANISM_LEAVES:
        continue
    notes = [r["notes"] for r in recs if r["notes"] and r["notes"].strip()]
    if not notes:
        continue
    seen.add(m); _gv2_added += 1
    rows.append({"normalised_merchant": m, "detailed_category": leaf, "confidence": "medium",
        "source": "gold_v2_review", "review_status": "approved", "notes": notes[0]})
print(f"gold_v2_review additions: {_gv2_added}")

# ---- production-labelling tranches (2026-08-20/21) ----
# The 50,000-string production-labelled vocabulary (two-model consensus + Opus
# tiebreak + policy gate) was built and validated for the classifier/SLM training
# set, but was never wired into the live T4 dictionary that actually serves the
# crosswalk -- this closes that gap. Same tiered-trust filter already validated
# against the clean gold set (auto_accept/accepted/human_reviewed measured at
# 82-91% accuracy; accepted_tiebreak at 66.9% and accepted_general at 33.3% are
# excluded as too weak). Agent_* tiers from tranche 4 are the same weak-supervision
# ingest, not human review. Tier A (gold_transactions_v2/v3) supersedes: any merchant
# already resolved there is skipped here, both because Tier A is higher-trust and
# to avoid re-introducing the exact circularity the gold-set leakage audit found.
_PROD_GOOD_TIERS = DICTIONARY_ELIGIBLE_TIERS
_prod_added = 0
for r in csv.DictReader(open(ROOT / "data" / "production_labels_tranche3.csv")):
    m = r["merchant"].strip().lower()
    # exclude the FULL Tier A merchant set (_by_merchant), not just `seen` -- most Tier A
    # merchants never passed the stricter gold_v2_review promotion filter above and so
    # aren't in `seen` yet, but they're still higher-trust and excluding only `seen` would
    # silently reintroduce the exact circularity the leakage audit found.
    if r["tier"] not in _PROD_GOOD_TIERS or m in seen or m in _by_merchant:
        continue
    seen.add(m); _prod_added += 1
    rows.append({"normalised_merchant": m, "detailed_category": r["final_leaf"], "confidence": "medium",
        "source": f"production_tranche3_{r['tier']}", "review_status": "approved",
        "notes": f"LLM-consensus label, tier={r['tier']}, measured 82-91% accurate against the clean gold set"})
print(f"production_tranche3 additions: {_prod_added}")

# ---- 2026-08-24 gold v3/v4 T4 adds + retargets (applied last so they beat tranche-3) ----
HUMAN_T4_FINAL = [
    ("sony playstation", "gaming_console_pc", "high", "Plaid PSN string; playstation already mapped, this key is not"),
    ("amazon prime", "streaming", "high", "Amazon Prime subscription; distinct from amazon marketplace"),
    ("chaotic", "prize_competitions", "high", "Chaotic.co.uk competition tickets, not a restaurant"),
    ("temu", "marketplace_general", "high", "temu.com; temu cd already mapped"),
    ("taptap send", "transfer_international", "high", "remittance; longer UK-limited keys exist"),
    ("ringgo", "car_parking", "high", "RingGo parking; ringgo parking already mapped"),
    ("microsoft xbox", "gaming_console_pc", "high", "Plaid Xbox/Game Pass string"),
    ("jd wetherspoon", "pub_bar", "high", "singular Wetherspoon; jd wetherspoons already mapped"),
    ("b & q", "home_improvement", "high", "B&Q with spaces; b&q already mapped"),
    ("home retail group", "catalogue_retail", "high", "Argos parent, shopping not store-card"),
    ("disney+", "streaming", "high", "Disney Plus; disney plus already mapped"),
    ("trainpal", "public_transport_rail_coach", "high", "rail tickets; trainpal cd already mapped"),
    ("oodle car finance", "car_finance_repayment", "high", "car-finance DDR; must not fall to T6 mortgage"),
    ("first central serv", "insurance_motor", "high", "1st Central motor insurance DD"),
    ("t j morris ltd", "discount_store", "high", "Home Bargains operator"),
    ("too good to go", "takeaway", "high", "surplus-meal app, same convention as Just Eat"),
    ("first west yorkshire", "public_transport_rail_coach", "high", "First Bus"),
    ("stageco", "public_transport_rail_coach", "medium", "Plaid truncation of Stagecoach"),
    ("www.amazon.uk.co", "marketplace_amazon", "high", "Amazon retail card string"),
    ("duelz", "gambling_casino", "high", "duelz.com casino; keep subtype not unspecified"),
    ("ring basic plan", "online_services", "high", "Ring Protect-style subscription"),
    ("domino's", "takeaway", "high", "Plaid apostrophe form; dominos pizza already mapped"),
    ("zippa loans", "payday_loan", "high", "Skyline Direct high-cost short-term credit"),
    ("gdk borough", "takeaway", "high", "German Doner Kebab Borough, not government"),
    ("kiley", "transfer_p2p", "medium", "named person (Kiley Sillett); not an energy supplier"),
    ("depop", "marketplace_general", "high", "Depop is a C2C marketplace, not Amazon; dictionary bug"),
    ("lime", "bicycle", "high", "UK Lime is e-bikes/scooters, not taxis"),
    ("tescophoneins.", "insurance_other", "high", "Plaid keeps the trailing period; T2 only fires when merchant is exactly tesco"),
    ("off licence gs wi", "alcohol_beer_spirits", "high", "Plaid truncation of an off-licence"),
    ("off licence gs wi", "alcohol_beer_spirits", "high", "Plaid truncation variant"),
    ("goldwire conve", "convenience_store", "high", "Goldwire Convenience truncation"),
    ("goldwire conve", "convenience_store", "high", "Goldwire Convenience truncation variant"),
    ("cd ridgewood stores", "convenience_store", "high", "Ridgewood Stores CD truncation"),
    ("cd ridgewood stores", "convenience_store", "high", "Ridgewood Stores truncation variant"),
    ("stagecoach services", "public_transport_rail_coach", "high", "Stagecoach bus; stageco already mapped"),
    ("morr wetherby", "groceries", "high", "Plaid Morrisons truncation; was pet_supplies"),
    ("morr catcliffe", "groceries", "high", "Plaid Morrisons truncation; was pub_bar"),
    ("prime video add-on", "streaming", "high", "Prime Video add-on; merchant is not amazon so T2 cannot fire"),
    ("prime video rent buy", "streaming", "high", "Prime Video rental; merchant is not amazon"),
    ("amazon prime video", "streaming", "high", "Amazon Prime Video as its own merchant string"),
    ("prime video", "streaming", "high", "Prime Video merchant string"),
    ("creditspring", "personal_loan_repayment", "high", "credit-builder / subscription lender, not payday"),
    ("tk maxx", "department_store", "high", "off-price department store"),
    ("google one", "web_services", "high", "Google One cloud storage"),
    ("voi", "bicycle", "high", "Voi micromobility"),
    ("voi uk", "bicycle", "high", "Voi micromobility"),
    ("rebtel", "mobile_phone_contract", "high", "Rebtel calling app"),
    ("bandoo", "health_beauty_general", "high", "Bandoo foot-detox retail"),
    ("3s retail ltd", "convenience_store", "high", "3S Retail convenience"),
    ("ingle store", "convenience_store", "high", "Ingle Store convenience"),
    ("morr derby", "groceries", "high", "Plaid Morrisons truncation"),
]
_by_m = {r["normalised_merchant"]: r for r in rows}
_final_added = _final_updated = 0
for m, leaf, conf, note in HUMAN_T4_FINAL:
    if m in _by_m:
        _by_m[m]["detailed_category"] = leaf
        _by_m[m]["confidence"] = conf
        _by_m[m]["source"] = "human_override_20260824"
        _by_m[m]["review_status"] = "approved"
        _by_m[m]["notes"] = note
        _final_updated += 1
    else:
        rec = {"normalised_merchant": m, "detailed_category": leaf, "confidence": conf,
               "source": "human_override_20260824", "review_status": "approved", "notes": note}
        rows.append(rec)
        _by_m[m] = rec
        _final_added += 1
_savers = 0
for r in rows:
    if r["normalised_merchant"].startswith("savers health") and r["detailed_category"] == "pharmacy":
        r["detailed_category"] = "health_beauty_general"
        r["source"] = "human_override_20260824"
        r["notes"] = "Savers is beauty-led retail, not a chemist (gold_v2 convention)"
        _savers += 1
print(f"human_override_20260824: added {_final_added}, retargeted {_final_updated}, savers pharmacy->beauty {_savers}")

# ---- tranche 4 (Gemini+Sonnet gate + agent/Carlos review, 2026-08-25) ----
# Dictionary-eligible tiers only. context_dependent, needs_review, abstain, and
# t2_candidate collisions are not ingested. unclassified_* is not a T4 mapping
# (it would freeze a string as unknown and block T5/T6). Eligible-tier retargets
# beat tranche-3 and the 2026-08-24 list for the same string.
# `human_reviewed` is Carlos only; agent_* are weak supervision.
_T4_LABELS = ROOT / "data" / "production_labels_tranche4.csv"
_T4_SKIP_LEAVES = {
    "unclassified_other", "unclassified_card_spend", "unclassified_transfer",
    "unclassified_recurring",
}
_PAYDAY_FP = _re_gv2.compile(
    r"\b(payday(?:\s*loans?)?|wonga|quick\s?quid|lending\s?stream|118\s*(?:118\s*)?money|"
    r"cashfloat|quid\s?market|morses\s?club|moneyboat|tick\s?tock\s*loans?|"
    r"sunny\s+loans?|cash\s?asap|fast\s+loan)\b",
    _re_gv2.I,
)
_t4_added = _t4_updated = _t4_skipped_unclass = _t4_skipped_t2 = 0
if _T4_LABELS.exists():
    _by_norm = {r["normalised_merchant"]: r for r in rows}
    for r in csv.DictReader(open(_T4_LABELS)):
        m = r["merchant"].strip().lower()
        if r["tier"] not in _PROD_GOOD_TIERS or m in _by_merchant:
            continue
        if str(r.get("t2_candidate", "")).lower() in {"yes", "y", "true"}:
            _t4_skipped_t2 += 1
            continue
        leaf = r["final_leaf"]
        if leaf in _T4_SKIP_LEAVES:
            _t4_skipped_unclass += 1
            continue
        # Personal-name collisions with payday tokens (e.g. "joe wheeler wonga")
        # stay out of T4; R18/R19 would otherwise fail the dict FP test.
        if leaf != "payday_loan" and _PAYDAY_FP.search(m):
            continue
        if r["tier"] in _PROD_GOOD_TIERS and m in _by_norm:
            if _by_norm[m]["detailed_category"] != leaf:
                _by_norm[m]["detailed_category"] = leaf
                _by_norm[m]["source"] = f"production_tranche4_{r['tier']}"
                _by_norm[m]["notes"] = (
                    f"Tranche-4 label, tier={r['tier']}, source={r.get('resolution_source','')}"
                )
                _t4_updated += 1
            continue
        if m in seen:
            continue
        seen.add(m)
        _t4_added += 1
        rec = {"normalised_merchant": m, "detailed_category": leaf, "confidence": "medium",
               "source": f"production_tranche4_{r['tier']}", "review_status": "approved",
               "notes": f"LLM-consensus label, tier={r['tier']}, tranche=4"}
        rows.append(rec)
        _by_norm[m] = rec
print(f"production_tranche4: added {_t4_added}, retargeted {_t4_updated}, "
      f"skipped_unclassified {_t4_skipped_unclass}, skipped_t2 {_t4_skipped_t2}")

# T2 collision keys and amount-only same-narrative splits must not sit in T4
# (T2 fires first, but unmatched narratives would still take the wrong T4 leaf).
# gamesys operation is the documented single-leaf exception (unspecified, not casino).
_T2_DICT_ALLOW = {"gamesys operation"}
_T2_BLOCK = {
    r["merchant"].strip().lower()
    for r in csv.DictReader(open(ROOT / "taxonomy" / "rules" / "t2_entity_collisions.csv"))
} - _T2_DICT_ALLOW
_T2_BLOCK |= {"the drayton court", "fountain hotel", "cd glasgow"}
_n_drop = len(rows)
rows = [r for r in rows if r["normalised_merchant"] not in _T2_BLOCK]
print(f"t2_collision_dict_drop: {_n_drop - len(rows)}")
_n_pd = len(rows)
rows = [r for r in rows if r["detailed_category"] == "payday_loan"
        or not _PAYDAY_FP.search(r["normalised_merchant"])]
print(f"payday_token_non_payday_drop: {_n_pd - len(rows)}")

# Carlos 2026-08-26 residual/T6 review — last so tranche-4 labels cannot overwrite.
HUMAN_T4_20260826 = [
    ("travelodge", "accommodation", "high", "hotel chain"),
    ("holiday inn", "accommodation", "high", "hotel chain; holiday inn express already mapped"),
    ("audleys wood", "accommodation", "high", "Audleys Wood Hotel"),
    ("admireme", "adult_entertainment", "high", ""),
    ("admire me", "adult_entertainment", "high", ""),
    ("streamray", "adult_entertainment", "high", ""),
    ("my nametags", "baby_products", "high", ""),
    ("beds.co.uk", "bedding", "high", "beds co uk already mapped"),
    ("amazon kindle", "books", "high", "Kindle content, not marketplace"),
    ("plusnet", "broadband_tv_phone", "high", ""),
    ("wework", "business_services", "high", "wework uk already mapped"),
    ("park resorts", "holiday_uk", "high", "UK holiday park, not camping_holiday"),
    ("europcar", "car_hire", "high", ""),
    ("hertz", "car_hire", "high", ""),
    ("lex autolease", "car_lease", "high", ""),
    ("batleys", "cash_and_carry", "high", ""),
    ("aramark", "catering", "high", ""),
    ("wex europe", "business_services", "high", "WEX Europe Services fleet/admin; was fuel"),
    ("wex europe services", "business_services", "high", ""),
    ("wex europe services (uk) limited", "business_services", "high", ""),
    ("wex europe services limited", "business_services", "high", ""),
    ("abercrombie & fitch", "clothing_general", "high", ""),
    ("abercrombie and fitch", "clothing_general", "high", ""),
    ("checkmyfile", "credit_reporting_service", "high", ""),
    ("check my file", "credit_reporting_service", "high", ""),
    ("pra group", "debt_collection", "high", ""),
    ("moneyplus group", "debt_management_plan", "high", ""),
    ("packlink", "delivery_courier", "high", ""),
    ("tsb returns", "delivery_courier", "medium", "Carlos residual review"),
    ("debenhams", "department_store", "high", ""),
    ("home super store", "groceries", "high", "Carlos residual review"),
    ("fancy dress shop", "fancy_dress", "high", ""),
    ("emirates", "flights", "high", ""),
    ("wizz air", "flights", "high", ""),
    ("vueling", "flights", "high", ""),
    ("ajet", "flights", "high", ""),
    ("shoe zone", "footwear", "high", ""),
    ("travelex", "foreign_currency", "high", ""),
    ("co-op funeralcare", "funeral", "high", ""),
    ("coop funeralcare", "funeral", "high", ""),
    ("santeda international limited", "gambling_casino", "high", ""),
    ("tree2mydoor", "garden", "high", ""),
    ("tree 2 my door", "garden", "high", ""),
    ("supervalu", "groceries", "high", ""),
    ("coop", "groceries", "high", "Plaid often drops the hyphen; co-op already mapped"),
    ("david lloyd", "gym_fitness", "high", ""),
    ("cult beauty", "health_beauty_general", "high", ""),
    ("nicholl fuel oil", "heating_oil", "high", ""),
    ("on the beach", "holiday_package", "high", ""),
    ("virgin holidays", "holiday_package", "high", ""),
    ("preply", "home_learning", "high", ""),
    ("the best connection", "income_agency_work", "high", ""),
    ("domestic & general", "insurance_general", "high", "appliance-care insurer"),
    ("domestic and general", "insurance_general", "high", ""),
    ("scottish widows", "insurance_general", "high", ""),
    ("the insurance emporium", "insurance_other", "high", ""),
    ("pet plan", "insurance_pet", "high", ""),
    ("nutmeg", "investment_general", "high", ""),
    ("scottish friendly", "investment_general", "high", ""),
    ("plus500", "investment_trading", "high", ""),
    ("ajjb law", "debt_collection", "high", "debt solicitor, not generic legal_services"),
    ("lights4fun", "lighting", "high", ""),
    ("festive lights", "lighting", "high", ""),
    ("fatsoma", "live_music", "high", ""),
    ("e2save", "mobile_handset", "high", ""),
    ("one money mail", "money_transfer_service", "high", ""),
    ("optimum credit", "mortgage", "high", ""),
    ("pepper money", "mortgage", "high", ""),
    ("office furniture", "office_equipment", "medium", "generic string; Carlos residual review"),
    ("lenstore", "optician", "high", ""),
    ("loans2go", "payday_loan", "high", "HCSTC; was personal_loan_repayment"),
    ("loans 2 go", "payday_loan", "high", ""),
    ("republic of cats", "pet_supplies", "high", ""),
    ("xtra dog", "pet_supplies", "high", ""),
    ("jollyes", "pet_supplies", "high", ""),
    ("conservative party", "political_donation", "high", ""),
    ("labour party", "political_donation", "high", ""),
    ("greater anglia", "public_transport_rail_coach", "high", ""),
    ("lavazza", "restaurant_cafe", "high", "cafe/coffee; lavazza professional stays vending"),
    ("tgi fridays", "restaurant_cafe", "high", ""),
    ("tgi friday's", "restaurant_cafe", "high", ""),
    ("brewers fayre", "restaurant_cafe", "high", ""),
    ("birkbeck college", "school_fees", "high", ""),
    ("american golf", "sports_equipment", "high", ""),
    ("fordhouses cricket and social club", "private_members_club", "high", ""),
    ("adidas", "sportswear", "high", ""),
    ("national education first", "education_general", "high", "not student_loan"),
    ("life extension", "supplements", "high", ""),
    ("robert dyas", "tools", "high", ""),
    ("copart", "vehicle_purchase", "high", ""),
    ("united utilities water", "water", "high", "united utilities already mapped"),
    ("spotless water", "water", "high", ""),
    ("utility warehouse", "utility_other", "high", "multi-utility bundle, not energy"),
    ("happy tails vets", "veterinary", "high", ""),
    ("go groopie", "vouchers", "high", ""),
    ("d ag communications", "gambling_unspecified", "high", "holdout gold correction; not broadband"),
]
_by26 = {r["normalised_merchant"]: r for r in rows}
_h26_add = _h26_upd = 0
for m, leaf, conf, note in HUMAN_T4_20260826:
    if m in _by26:
        _by26[m]["detailed_category"] = leaf
        _by26[m]["confidence"] = conf
        _by26[m]["source"] = "human_override_20260826"
        _by26[m]["review_status"] = "approved"
        _by26[m]["notes"] = note
        _h26_upd += 1
    else:
        rec = {"normalised_merchant": m, "detailed_category": leaf, "confidence": conf,
               "source": "human_override_20260826", "review_status": "approved", "notes": note}
        rows.append(rec)
        _by26[m] = rec
        _h26_add += 1
print(f"human_override_20260826: added {_h26_add}, retargeted {_h26_upd}")

# High-volume Plaid T4 misses, Luna A/B then parent review.
# Withheld: data/t4_residual_human_review.csv
_RESIDUAL_ADD_FILES = [
    (ROOT / "data" / "t4_residual_dictionary_additions.csv", "human_override_20260826_residual"),
    (ROOT / "data" / "t4_residual_dictionary_additions_10_49.csv", "human_override_20260826_residual_10_49"),
    (ROOT / "data" / "t4_carlos_review_applied_20260826.csv", "human_override_20260826_carlos_review"),
    (ROOT / "data" / "t4_carlos_review_applied_20260826_debit.csv", "human_override_20260826_carlos_debit"),
    (ROOT / "data" / "t4_carlos_review_applied_20260826_b_leftovers.csv", "human_override_20260826_carlos_b"),
    (ROOT / "data" / "t4_trading212.csv", "human_override_20260827_trading212"),
]
_by_res = {r["normalised_merchant"]: r for r in rows}
for _path, _src in _RESIDUAL_ADD_FILES:
    if not _path.exists():
        continue
    _res_add = _res_upd = 0
    for r in csv.DictReader(open(_path)):
        m = r["normalised_merchant"].strip().lower()
        leaf = r["detailed_category"].strip()
        note = (r.get("notes") or "residual alias").strip()
        if m in _by_res:
            _by_res[m]["detailed_category"] = leaf
            _by_res[m]["confidence"] = "high"
            _by_res[m]["source"] = _src
            _by_res[m]["review_status"] = "approved"
            _by_res[m]["notes"] = note
            _res_upd += 1
        else:
            rec = {"normalised_merchant": m, "detailed_category": leaf, "confidence": "high",
                   "source": _src, "review_status": "approved", "notes": note}
            rows.append(rec)
            _by_res[m] = rec
            _res_add += 1
    print(f"{_src}: added {_res_add}, retargeted {_res_upd}")

# PayPal Credit is a revolving facility (Carlos 2026-08-27). Last so residual
# aliases cannot put it back on bnpl. Pay in 3/4 stay bnpl via T2 / paypal pay in 4.
_pc = _by_res.get("paypal credit")
if _pc:
    _pc["detailed_category"] = "revolving_credit_repayment"
    _pc["confidence"] = "high"
    _pc["source"] = "human_override_20260827_paypal_credit"
    _pc["review_status"] = "approved"
    _pc["notes"] = "revolving line, not Klarna-style BNPL"
    print("human_override_20260827_paypal_credit: retargeted paypal credit")

# Tokens that must not be T4: narrative T2/T5 only.
_BARE_TOKEN_DROP = {
    "now",
    "mercedes-benz", "plus", "gem", "home", "city", "orbit", "spring", "wood j",
}
_n_bare = len(rows)
rows = [r for r in rows if r["normalised_merchant"] not in _BARE_TOKEN_DROP]
print(f"bare_token_drop: {_n_bare - len(rows)}")

# T4 matching excludes pending and unclassified_* (same rule as load_t4_dictionary).
_n_t4 = len(rows)
rows = [r for r in rows
        if r.get("review_status") == "approved"
        and not r["detailed_category"].startswith("unclassified")]
print(f"pending_or_unclassified_drop: {_n_t4 - len(rows)}")

# Last-wins on normalised_merchant (HUMAN_T4_FINAL listed a few keys twice).
_dedup = {}
for r in rows:
    _dedup[r["normalised_merchant"]] = r
rows = list(_dedup.values())

# validate leaves exist in taxonomy
tax={r['detailed_category'] for r in csv.DictReader(open(ROOT / "taxonomy" / "taxonomy.csv"))}
bad=[r for r in rows if r['detailed_category'] not in tax]
print("INVALID LEAF REFERENCES:", [(r['normalised_merchant'],r['detailed_category']) for r in bad] or "none")

with open(ROOT / "taxonomy" / "merchant_dictionary.csv",'w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=["normalised_merchant","detailed_category","confidence","source","review_status","notes"])
    w.writeheader(); w.writerows(rows)

from collections import Counter
print("\nmerchants labelled:",len(rows))
print("confidence:",dict(Counter(r['confidence'] for r in rows)))
print("distinct leaves used:",len(set(r['detailed_category'] for r in rows)))
print("needs review (low conf):",sum(1 for r in rows if r['confidence']=='low'))

# -*- coding: utf-8 -*-
import csv
import pathlib
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
("laybuy","bnpl","high",""),("monzo flex","bnpl","high",""),("paypal credit","bnpl","high",""),
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
("creditspring","payday_loan","high","subscription lending - high cost"),
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
("tk maxx","clothing_general","high",""),("pretty little things","clothing_general","high",""),
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
    seen.add(m); rows.append({"normalised_merchant":m,"detailed_category":leaf,
        "confidence":conf,"source":"llm_proposed","review_status":"pending","notes":note})

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
# excluded as too weak). Tier A (gold_transactions_v2/v3) supersedes: any merchant
# already resolved there is skipped here, both because Tier A is higher-trust and
# to avoid re-introducing the exact circularity the gold-set leakage audit found.
_PROD_GOOD_TIERS = {"auto_accept", "accepted", "human_reviewed"}
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

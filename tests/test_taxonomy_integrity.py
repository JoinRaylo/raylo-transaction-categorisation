"""Integrity tests for the taxonomy and merchant dictionary.

These exist because manual edits to the taxonomy have already introduced real bugs
during development: three invalid leaf references (`electronics_computing` instead of
`computing_devices`) and one provider value (`Stationery`) mapped to two leaves.
Run these after every edit.
"""
import csv
import pathlib
import collections
import sys
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
TAX = ROOT / "taxonomy" / "taxonomy.csv"
DICT = ROOT / "taxonomy" / "merchant_dictionary.csv"
RULES = ROOT / "taxonomy" / "rules" / "deterministic_rules.csv"
T2_COLLISIONS = ROOT / "taxonomy" / "rules" / "t2_entity_collisions.csv"

VALID_NECESSITY = {"essential", "discretionary", "mixed_basket", "not_applicable"}
VALID_CASH_FLOW = {"spend", "income", "debt_repayment", "debt_disbursement",
                   "transfer_own_accounts", "p2p_transfer", "fee_or_penalty", "unclassified"}


@pytest.fixture(scope="module")
def taxonomy():
    return list(csv.DictReader(TAX.open()))


@pytest.fixture(scope="module")
def leaves(taxonomy):
    return {r["detailed_category"] for r in taxonomy}


def test_no_duplicate_leaves(taxonomy):
    dupes = [k for k, v in collections.Counter(
        r["detailed_category"] for r in taxonomy).items() if v > 1]
    assert not dupes, f"duplicate leaf names: {dupes}"


def test_strict_tree_one_parent_per_leaf(taxonomy):
    """general_category must be a strict rollup. Equifax's taxonomy is NOT a tree
    (87% of its subcategories have multiple parents) - ours must be."""
    parents = collections.defaultdict(set)
    for r in taxonomy:
        parents[r["detailed_category"]].add(r["general_category"])
    multi = {k: v for k, v in parents.items() if len(v) > 1}
    assert not multi, f"leaves with >1 parent: {multi}"


def test_dimension_values_valid(taxonomy):
    bad_nec = [r["detailed_category"] for r in taxonomy
               if r["necessity"] not in VALID_NECESSITY]
    bad_cf = [r["detailed_category"] for r in taxonomy
              if r["cash_flow_type"] not in VALID_CASH_FLOW]
    assert not bad_nec, f"invalid necessity: {bad_nec}"
    assert not bad_cf, f"invalid cash_flow_type: {bad_cf}"


def test_booleans_are_booleans(taxonomy):
    for col in ("is_debt_related", "is_priority_debt", "is_age_restricted"):
        bad = [r["detailed_category"] for r in taxonomy if r[col] not in ("true", "false")]
        assert not bad, f"{col} not boolean for: {bad}"


def test_provider_value_maps_to_exactly_one_leaf(taxonomy):
    """A provider category mapped to two leaves is ambiguous and will silently
    produce inconsistent output. This caught the `Stationery` bug."""
    for col in ("equifax_source", "plaid_source"):
        seen = collections.defaultdict(list)
        for r in taxonomy:
            for src in (s.strip() for s in r[col].split(";") if s.strip()):
                if "+" in src or "|" in src:
                    continue  # compound rules handled in precedence logic, not the map
                seen[src].append(r["detailed_category"])
        dupes = {k: v for k, v in seen.items() if len(v) > 1}
        assert not dupes, f"{col} values mapped to multiple leaves: {dupes}"


def test_priority_debt_set_is_expected(taxonomy):
    """is_priority_debt yielded the strongest single feature found (IV 0.171).
    Guard against accidental drift in its membership."""
    actual = {r["detailed_category"] for r in taxonomy if r["is_priority_debt"] == "true"}
    expected = {"rent", "mortgage", "council_tax", "energy", "water", "tv_licence",
                "tax_payment", "utility_other", "heating_oil", "property_management"}
    assert actual == expected, f"priority_debt drift: +{actual-expected} -{expected-actual}"


def test_merchant_dictionary_leaves_exist(leaves):
    bad = [(r["normalised_merchant"], r["detailed_category"])
           for r in csv.DictReader(DICT.open())
           if r["detailed_category"] not in leaves]
    assert not bad, f"dictionary references non-existent leaves: {bad}"


def test_merchant_dictionary_no_duplicate_keys():
    rows = list(csv.DictReader(DICT.open()))
    dupes = [k for k, v in collections.Counter(
        r["normalised_merchant"] for r in rows).items() if v > 1]
    assert not dupes, f"duplicate merchant keys: {dupes}"


def test_rules_reference_valid_leaves(leaves):
    bad = [(r["rule_id"], r["detailed_category"])
           for r in csv.DictReader(RULES.open())
           if r["detailed_category"] not in leaves]
    assert not bad, f"rules reference non-existent leaves: {bad}"


def test_t2_entity_collision_csv_valid(leaves):
    """Human-review same-string splits live in the CSV, not as invented leaves."""
    rows = list(csv.DictReader(T2_COLLISIONS.open()))
    assert rows, "t2_entity_collisions.csv is empty"
    bad = [(r["rule_id"], r["detailed_category"])
           for r in rows if r["detailed_category"] not in leaves]
    assert not bad, f"T2 collision CSV references non-existent leaves: {bad}"
    dupes = [k for k, v in collections.Counter(r["rule_id"] for r in rows).items() if v > 1]
    assert not dupes, f"duplicate T2 collision rule_ids: {dupes}"
    bad_dir = [r["rule_id"] for r in rows if r["direction"] not in {"any", "debit", "credit"}]
    assert not bad_dir, f"invalid T2 collision direction: {bad_dir}"


def test_paypal_credit_revolving_not_bnpl():
    """PayPal Credit is revolving; Pay in 3/4 stay bnpl."""
    sql = (ROOT / "sql" / "apply_crosswalk.sql").read_text()
    dict_rows = list(csv.DictReader((ROOT / "taxonomy" / "merchant_dictionary.csv").open()))
    pc = next(r for r in dict_rows if r["normalised_merchant"] == "paypal credit")
    assert pc["detailed_category"] == "revolving_credit_repayment"
    assert sql.count("T2_compound_paypal_credit_line") == 2
    assert sql.count("T2_compound_paypal_payin3") == 2
    assert sql.count("T5_rule_R32") == 2


def test_stepchange_t5_description_blank_merchant():
    """Blank-merchant STEPCHANGE narratives miss T4 (exact key stepchange).
    T5 R31 is description-level, debit, same shape as R22/R23."""
    sql = (ROOT / "sql" / "apply_crosswalk.sql").read_text()
    rules = (ROOT / "taxonomy" / "rules" / "deterministic_rules.csv").read_text()
    assert r"\bstep[\s-]*change\b" in rules
    assert sql.count("T5_rule_R31") == 2


def test_sheriff_court_t5_and_t2_precede_t4():
    """Sheriff-court fees are government_services (HMCTS), not legal_services.
    T5 R22 is description-level (truncated merchants vary). cd glasgow rail vs
    court also has T2 rows so the collision is explicit before T4."""
    sql = (ROOT / "sql" / "apply_crosswalk.sql").read_text()
    rules = (ROOT / "taxonomy" / "rules" / "deterministic_rules.csv").read_text()
    assert "t2_entity_collisions.csv" in (ROOT / "src" / "generate_crosswalk_sql.py").read_text()
    assert r"sheriff\s+court" in rules
    assert sql.count("T5_rule_R22") == 2
    assert sql.count("T2_compound_cd_glasgow_sheriff") == 2
    for block_name, block in (
        ("eqx_resolved", sql.split("eqx_resolved AS (")[1].split("plaid_raw AS (")[0]),
        ("plaid_resolved", sql.split("plaid_resolved AS (")[1].split("combined AS (")[0]),
    ):
        leaf_case = block.split("END AS leaf")[0]
        t4 = leaf_case.find("WHEN d.leaf IS NOT NULL THEN d.leaf")
        assert t4 != -1, f"{block_name}: T4 dictionary WHEN missing"
        t2_pos = leaf_case.find("'cd glasgow'")
        assert t2_pos != -1 and t2_pos < t4, f"{block_name}: cd glasgow T2 missing or after T4"
        t5_pos = leaf_case.find("T5_rule_R22")
        # R22 lives in the tier CASE; the leaf CASE still has the sheriff pattern after T4
        sheriff_after_t4 = leaf_case.find("sheriff", t4)
        assert sheriff_after_t4 != -1, f"{block_name}: R22 sheriff pattern missing after T4"


def test_gambling_subtypes_not_collapsed(leaves):
    """Aggregating gambling DESTROYS signal (0.0053 vs 0.0498 for lottery alone).
    Subtypes must remain distinct."""
    for leaf in ("gambling_betting", "gambling_casino", "gambling_bingo", "gambling_lottery"):
        assert leaf in leaves, f"{leaf} missing - gambling must not be aggregated"


def test_tesco_t2_collisions_owned_by_generator():
    """Hand-patched T2 Tesco collisions were dropped by generate_crosswalk_sql.py
    on 2026-08-24. The generator is the source of truth; generated SQL must
    carry all three on both providers, and they must precede T4."""
    sql = (ROOT / "sql" / "apply_crosswalk.sql").read_text()
    gen = (ROOT / "src" / "generate_crosswalk_sql.py").read_text()
    markers = (
        "T2_compound_tesco_bank",
        "T2_compound_tesco_petrol",
        "T2_compound_tesco_phoneins",
        "T2_compound_tesco_cafe",
    )
    for marker in markers:
        assert marker in gen, f"{marker} missing from generate_crosswalk_sql.py"
        assert sql.count(marker) == 2, (
            f"{marker} must appear on Equifax and Plaid tier CASE (got {sql.count(marker)})")
    for block_name, block in (
        ("eqx_resolved", sql.split("eqx_resolved AS (")[1].split("plaid_raw AS (")[0]),
        ("plaid_resolved", sql.split("plaid_resolved AS (")[1].split("combined AS (")[0]),
    ):
        leaf_case = block.split("END AS leaf")[0]
        t4 = leaf_case.find("WHEN d.leaf IS NOT NULL THEN d.leaf")
        assert t4 != -1, f"{block_name}: T4 dictionary WHEN missing"
        for needle in (r"\btesco bank\b", r"petrol|\bpfs\b", "tescophoneins", r"caf[eé]"):
            pos = leaf_case.find(needle)
            assert pos != -1, f"{block_name}: {needle!r} missing from leaf CASE"
            assert pos < t4, f"{block_name}: {needle!r} must precede T4"


def test_hmrc_t2_collisions_owned_by_generator():
    """T4 maps hmrc / hm revenue and customs -> tax_payment. Child Benefit and
    SA refund credits must be T2 (before T4); a T5 rule would never fire."""
    sql = (ROOT / "sql" / "apply_crosswalk.sql").read_text()
    gen = (ROOT / "src" / "generate_crosswalk_sql.py").read_text()
    markers = (
        "T2_compound_hmrc_child_benefit",
        "T2_compound_hmrc_tax_credit",
        "T2_compound_hmrc_sa_refund",
    )
    for marker in markers:
        assert marker in gen, f"{marker} missing from generate_crosswalk_sql.py"
        assert sql.count(marker) == 2, (
            f"{marker} must appear on Equifax and Plaid tier CASE (got {sql.count(marker)})")
    for block_name, block in (
        ("eqx_resolved", sql.split("eqx_resolved AS (")[1].split("plaid_raw AS (")[0]),
        ("plaid_resolved", sql.split("plaid_resolved AS (")[1].split("combined AS (")[0]),
    ):
        leaf_case = block.split("END AS leaf")[0]
        t4 = leaf_case.find("WHEN d.leaf IS NOT NULL THEN d.leaf")
        assert t4 != -1, f"{block_name}: T4 dictionary WHEN missing"
        for needle in (r"child\s+benefits?", r"\bhmrc\s+sa\b", "hm revenue and customs"):
            pos = leaf_case.find(needle)
            assert pos != -1, f"{block_name}: {needle!r} missing from leaf CASE"
            assert pos < t4, f"{block_name}: {needle!r} must precede T4"
        assert "r.direction='credit'" in leaf_case, (
            f"{block_name}: HMRC T2 must be credit-only so SA debits stay tax_payment")


def test_hmrc_t2_eval_harness_matches_gold_examples():
    """Eval waterfall must split the HMRC collision the same way as generated SQL."""
    import sys
    sys.path.insert(0, str(ROOT / "src"))
    import final_evaluation as fe
    fe.SUB_MAP, fe.PRI_MAP, fe.PLAID_MAP, _ = fe.load_crosswalk()
    fe.DICTIONARY = fe.load_dictionary()
    fe.RULES = fe.load_rules()

    cases = [
        ("HM Revenue and Customs", "credit",
         "HMRC CHILD BENEFIT  KELLY00LAURA920227 BGC",
         "benefits_state", "T2_compound_hmrc_child_benefit"),
        ("HMRC", "credit", "HMRC WORK AND CHILD TC",
         "benefits_state", "T2_compound_hmrc_tax_credit"),
        ("HMRC", "credit", "HMRC SA  2377880224K00002 BGC",
         "tax_refund", "T2_compound_hmrc_sa_refund"),
        ("HMRC", "debit", "Hmrc Gov.uk Sa",
         "tax_payment", "T4_dictionary"),
        ("HM Revenue and Customs", "debit", "HMRC CHILD BENEFIT",
         "tax_payment", "T4_dictionary"),
        ("Child Benefits", "credit", "HMRC CHILD BENEFIT",
         "benefits_state", "T4_dictionary"),
        ("Child Benefits", "credit", "BANK GIRO CREDIT REF DWPCMSGB2012SCHEME",
         "income_other_unspecified", "T2_compound_cms_not_child_benefit"),
        ("Burton", "debit", "KFC - BURTON",
         "takeaway", "T2_compound_kfc"),
        ("Klarna", "debit", "KLARNA*KFC BARLOW MO LONDON GB",
         "takeaway", "T2_compound_kfc"),
        ("Welcome Break", "debit", "VISA Debit Transaction WELCOME BREAK KFC",
         "takeaway", "T2_compound_kfc"),
        ("KFC", "debit", "ZILCH * KFC BEACON",
         "takeaway", "T2_compound_kfc"),
        ("Klarna", "debit", "KLARNA*ASOS",
         "bnpl", "T4_dictionary"),
        ("Tesco", "debit", "Cash at Tesco Lodge Pk Exp",
         "cash_withdrawal", "T2_compound_instore_atm"),
        ("Sky Bet", "credit", "Visa credit Sky Betting Gaming",
         "gambling_unspecified", "T1_direction_gambling_credit"),
        ("Co-op", "debit", "CO-OP GROUP PETROLPOUNDS HILL",
         "fuel", "T2_compound_grocer_petrol"),
        ("Tesco", "debit", "TESCO CAFE LLANELLI",
         "restaurant_cafe", "T2_compound_tesco_cafe"),
        ("Vodafone", "debit", "DIRECT DEBIT PAYMENT TO VODAFONE LTDDEVICE REF 1003551045",
         "mobile_handset", "T2_compound_vodafone_device"),
        ("Amazon", "debit", "Prime Video*H73XV8  ON 31 OCT BCC PRIME VIDEO ADD-ON",
         "streaming", "T2_compound_amazon_prime_video"),
        ("Iceland", "credit", "5029 02OCT24 ICELAND FOODS FLINTSHIRE GB REFUND",
         "refund_received", "T2_compound_refund"),
        ("Depop", "debit", "DEPOP LONDON",
         "marketplace_general", "T4_dictionary"),
        ("Lime", "debit", "Lime",
         "bicycle", "T4_dictionary"),
        ("Creditspring", "debit", "CREDITSPRING",
         "personal_loan_repayment", "T4_dictionary"),
        ("Haven Holidays", "debit", "SUMUP *RICHARD HAV  ON 28 JAN CLP SUMUP  *RICHARD HAVEN",
         "beauty_treatment", "T2_compound_richard_haven"),
        ("Apple Store", "debit", "INGLE STORE (VIA APPLE PAY), ON 27-08-2025",
         "convenience_store", "T2_compound_ingle_store"),
        ("Google One", "debit", "GOOGLE *Google One",
         "web_services", "T4_dictionary"),
        ("Voi UK", "debit", "Voi UK",
         "bicycle", "T4_dictionary"),
        ("TK Maxx", "debit", "TK MAXX",
         "department_store", "T4_dictionary"),
        ("Tescophoneins.", "debit", "TESCOPHONEINS.",
         "insurance_other", "T4_dictionary"),
        ("Morr Paignton", "debit", "MORR PAIGNTON Morr Paignton",
         "groceries", "T4_dictionary"),
        ("Morrisons Petrol", "debit", "MORRISONS PETROL",
         "fuel", "T4_dictionary"),
        ("CD Glasgow", "debit",
         "6474 16OCT25 CD   GLASGOW SHERIFF   COURT             GLASGOW GB",
         "government_services", "T2_compound_cd_glasgow_sheriff"),
        ("CD Glasgow", "debit",
         "3818 15AUG25 CD   GLASGOW CENTRAL   LOW LE            GLASGOW 9922 GB",
         "public_transport_rail_coach", "T2_compound_cd_glasgow_central"),
        ("CD Glasgow", "debit",
         "3818 15AUG25 CD   GLASGOW QST STN   OTS               GLASGOW 6306 GB",
         "public_transport_rail_coach", "T2_compound_cd_glasgow_qst"),
        ("CD Edinburgh", "debit", "EDINBURGH SHERIFF COURT",
         "government_services", "T5_R22"),
        ("Glossop", "debit", "SUMUP  *GLOSSOP   SUB LT            LEICESTER GB",
         "takeaway", "T2_compound_glossop_subway"),
        ("The Black", "debit", "THE BLACK COUNTRY CHIP              WEST BROMWICH GB",
         "takeaway", "T2_compound_the_black_chip"),
        ("The Black", "debit", "The Blackheath",
         "pub_bar", "T2_compound_the_black_heath"),
        ("Wik", "debit", "Wiktoria Sopel - SortCodeAccountNumber: 04007559771623",
         "transfer_p2p", "T2_compound_wik_sopel"),
        ("Wik", "debit", "Wiktoria Maciagowska repayment",
         "loan_repayment_manual", "T2_compound_wik_repayment"),
        ("Jasmine", "debit", "JASMINE RESTAURANT  ON 18 AUG CLP",
         "restaurant_cafe", "T2_compound_jasmine_restaurant"),
        ("Jasmine", "debit", "Jasmine Chesney - SortCodeAccountNumber: 07043623878452",
         "transfer_p2p", "T2_compound_jasmine_p2p"),
        ("paymy.vet", "debit", "PAYMY.VET* PETS GROOMI FARNHAM GB",
         "pet_other", "T2_compound_paymyvet_groom"),
        ("Reddish", "debit", "REDDISH SERVICE STATIO (VIA APPLE PAY)",
         "fuel", "T2_compound_reddish_pfs"),
        ("Wirral MBC", "debit", "Visa purchase WIRRAL MBC ATP",
         "car_parking", "T2_compound_wirral_atp"),
        ("Egg", "debit", "Direct debit EGG 162224 10135836",
         "energy", "T2_compound_egg_energy"),
        ("Gamesys Operation", "debit", "GAMESYS OPERATION",
         "gambling_unspecified", "T2_compound_gamesys_unspecified"),
        ("Work and Child Tax Credit", "credit", "HMRC WORK AND CHILD TC",
         "benefits_state", "T4_dictionary"),
        ("Truncated Benefit Rail", "credit", "204M46U31 DWP UC",
         "benefits_state", "T5_R23"),
        ("F Tait", "credit", "F Tait Refunded",
         "refund_received", "T2_compound_refund"),
        ("Spring", "credit", "Returned direct debit CREDITSPRING 070806 13191414",
         "returned_payment", "T2_compound_returned_payment"),
        ("Creation.co.uk", "credit", "REVERSAL OF 14-07 CREATION.CO.UK",
         "returned_payment", "T2_compound_returned_payment"),
        ("Agbx", "credit", "DIRECT DEBIT REVERSAL REF 1AGBX27496, MANDATE NO 0008",
         "returned_payment", "T2_compound_returned_payment"),
        ("Royal London Pensions", "debit", "ROYAL LONDON PENSIONS",
         "pension_contribution", "T4_dictionary"),
        ("Amazon UK Services", "credit", "AMAZON UK SERVICES BGC",
         "salary", "T2_compound_amazon_uk_services_salary"),
        ("Payroll Co", "credit", "WAGES WEEK 12",
         "salary", "T5_R25"),
        ("Amber Valley Borough Council", "debit",
         "Amber Valley Borou-Ips AMBER VALLEY BOROU-IPS Doncaster     GBR",
         "car_parking", "T2_compound_amber_valley_ips"),
        ("Roadchef", "debit", "VMS ROADCHEF WHSMISTAFFORD",
         "convenience_store", "T2_compound_roadchef_whsmith"),
        ("Park Resorts", "debit", "Sunnydale Holiday Park PARK RESORTS",
         "holiday_uk", "T4_dictionary"),
        ("Ajjb Law", "debit", "AJJB LAW  ON 13 SEP BCC",
         "debt_collection", "T4_dictionary"),
        ("Loans2go", "debit", "LOANS2GO",
         "payday_loan", "T4_dictionary"),
        ("Parentpay", "debit", "PARENTPAY DDR",
         "school_fees", "T4_dictionary"),
        ("Five Guys", "debit", "FIVE GUYS",
         "takeaway", "T4_dictionary"),
        ("Morr", "debit", "MORR PAIGNTON",
         "groceries", "T4_dictionary"),
        ("Morr", "debit", "MORR PETROL PAIGNTON",
         "fuel", "T2_compound_grocer_petrol"),
        ("Morr", "debit", "MORR CAFE PAIGNTON",
         "restaurant_cafe", "T2_compound_morr_cafe"),
        ("Barclays Bank", "debit", "BARCLAYS UK MTGES",
         "mortgage", "T4_dictionary"),
        ("Utility Warehouse", "debit", "UTILITY WAREHOUSE",
         "utility_other", "T4_dictionary"),
        ("Scholastic Rail", "debit", "SCHOLASTIC BOOK FAIR",
         "books", "T5_R24"),
        ("Admiral", "debit", "ADMIRAL INSURANCE P72566661010000020",
         "insurance_general", "T4_dictionary"),
        ("Admiral", "debit", "Transfer to Admiral Casino 2025-07-30",
         "gambling_casino", "T2_compound_admiral_casino"),
        ("Ocado", "debit", "OCADO GROCERIES",
         "groceries", "T4_dictionary"),
        ("Ocado", "credit", "OCADO CENTRAL SERV",
         "salary", "T2_compound_ocado_salary"),
        ("Youlend", "debit", "YOULEND REPAYMENT",
         "business_loan_repayment", "T4_dictionary"),
        ("Youlend", "credit", "YOULEND YL123 OUT",
         "loan_disbursement", "T2_compound_youlend_disbursement"),
        ("Youlend", "credit", "Returned direct debit YOULEND",
         "returned_payment", "T2_compound_returned_payment"),
        ("Now", "debit", "NOW C386A Entertai",
         "streaming", "T2_compound_now_entertai"),
        ("Now", "debit", "PAYPAL *NOW 477B9",
         "streaming", "T2_compound_now_paypal"),
        ("PayPal", "debit", "PAYPAL *NOW F9A9C GB",
         "streaming", "T2_compound_paypal_now"),
        ("Royal London", "debit", "ROYAL LONDON 93263483",
         "insurance_life", "T4_dictionary"),
        ("Places for People", "debit", "PLACES FOR PEOPLE 1572070214",
         "rent", "T4_dictionary"),
        ("Places for People", "debit", "PLACES FOR PEOPLE LEISURE NYX",
         "gym_fitness", "T2_compound_places_for_people_leisure"),
        ("Ask Italian", "debit", "ASK ITALIAN DINNER",
         "restaurant_cafe", "T4_dictionary"),
        ("Ask Italian", "credit", "AZZURRI ACCOUNT BGC",
         "salary", "T2_compound_ask_italian_salary"),
        ("Kwiff", "debit", "KWIFF",
         "gambling_betting", "T4_dictionary"),
        ("Close Brothers", "debit", "CLOSEBROSMOTFIN",
         "car_finance_repayment", "T4_dictionary"),
        ("Cox", "debit", "Sophie cox Holiday",
         "transfer_p2p", "T4_dictionary"),
        ("White Lion", "debit", "Contactless Payment White Lion",
         "pub_bar", "T4_dictionary"),
        ("White Lion", "debit", "White Lion Hotel",
         "accommodation", "T2_compound_white_lion_hotel"),
        ("Spring", "credit", "Returned direct debit CREDITSPRING 070806 13191414",
         "returned_payment", "T2_compound_returned_payment"),
        ("Lets Win", "debit", "LETS WIN (VIA APPLE PAY)",
         "prize_competitions", "T4_dictionary"),
        ("Cts", "debit", "CTS LOCAL",
         "public_transport_rail_coach", "T4_dictionary"),
        ("Cts", "debit", "NAPA AUTO PARTS - SUND Cts",
         "spares_repairs", "T2_compound_cts_napa"),
        ("Transferwise", "debit", "ROHAN TRANSFERWISE VIA MOBILE - PYMT",
         "transfer_p2p", "T2_compound_transferwise_p2p"),
        ("Mercedes-Benz", "debit", "MBFIN S0DF23UFD02 DDR Mercedes-Benz",
         "car_finance_repayment", "T2_compound_mercedes_finance"),
        ("Mercedes-Benz", "debit", "CARD PAYMENT TO MERCEDES-BENZ OF FARNB",
         "vehicle_servicing", "T2_compound_mercedes_dealer"),
        ("Mercedes-Benz", "credit", "Mercedes-Benz Of N",
         "salary", "T2_compound_mercedes_salary"),
        ("Grosvenor Casino", "debit", "GROSVENOR CASINO BOURNEMO",
         "gambling_casino", "T4_dictionary"),
        ("Grosvenor Casino", "credit", "Grosvenor Casino Coven",
         "salary", "T2_compound_grosvenor_salary"),
        ("Help to Buy", "debit", "DIRECT DEBIT PAYMENT TO HELP TO BUY",
         "personal_loan_repayment", "T4_dictionary"),
        ("Virgin Mobile", "debit", "103336435 Virgin Mobile",
         "mobile_phone_contract", "T4_dictionary"),
        ("Virgin Mobile", "debit", "VIRGIN MONEY CREDIEXTRA PAYMENT VIA MOBILE",
         "credit_card_repayment", "T2_compound_virgin_money_on_mobile"),
        ("The Grove", "debit", "THE GROVE WELWYN GARDEN",
         "accommodation", "T2_compound_grove_hotel"),
        ("The Grove", "debit", "The Grove ON 27 JUL CPM",
         "pub_bar", "T4_dictionary"),
        ("Standing Order", "credit", "Returned standing order NIHE 070246",
         "returned_payment", "T2_compound_returned_payment"),
        ("Standing Order", "debit", "STANDING ORDER",
         "transfer_bank_unspecified", "T4_dictionary"),
        ("Off Licence", "debit", "GREENPARK OFF LICENCE WAKEFIELD",
         "alcohol_beer_spirits", "T4_dictionary"),
        ("Wood J", "debit", "WOOD J *HSM HOLIDAY",
         "holiday_package", "T2_compound_wood_j_hsm"),
        ("Plus", "debit", "PLUS500",
         "investment_trading", "T2_compound_plus500"),
        ("Plus", "debit", "Direct debit PLUS1342407-1",
         "personal_loan_repayment", "T2_compound_plus_finance"),
        ("Council", "debit", "MHDC COUNCIL TAX 01",
         "council_tax", "T2_compound_council_tax_narrative"),
        ("Home", "debit", "247 HOME RESCUE GC657090 DDR",
         "home_repair", "T2_compound_home_rescue"),
        ("Paypal Credit", "debit", "PAYPAL *PAYPAL CRE",
         "revolving_credit_repayment", "T4_dictionary"),
        ("PayPal", "debit", "Visa purchase PAYPAL *PAYPAL CREDIT 1536",
         "revolving_credit_repayment", "T2_compound_paypal_credit_line"),
        ("Paypal Credit", "debit", "CARD PAYMENT TO PAYPAL *PYPL PAYIN3 ON 27-08-2024",
         "bnpl", "T2_compound_paypal_credit_payin3"),
        ("Paypal Pay in 4", "debit", "CARD PAYMENT TO PAYPAL *PYPL PAYIN3 ON 31-08-2025",
         "bnpl", "T4_dictionary"),
        ("", "debit", "PAYPAL *PAYPAL CRE",
         "revolving_credit_repayment", "T5_R32"),
        ("", "debit", "STEPCHANGE",
         "debt_management_plan", "T5_R31"),
        ("", "debit", "Direct debit STEPCHANGE 074456 32470265",
         "debt_management_plan", "T5_R31"),
        ("", "debit", "STEPCHANGE                            REFERENCE: 1119617",
         "debt_management_plan", "T5_R31"),
        ("Stepchange", "debit", "STEPCHANGE  3452322 DDR Stepchange",
         "debt_management_plan", "T4_dictionary"),
        ("", "credit", "Returned direct debit STEPCHANGE",
         "returned_payment", "T2_compound_returned_payment"),
    ]
    for merchant, direction, desc, want_leaf, want_tier in cases:
        leaf, tier = fe.our_leaf(
            merchant, direction, desc, fe.plaid_native_leaf, "INCOME_SALARY", direction)
        assert (leaf, tier) == (want_leaf, want_tier), (
            f"{merchant!r} {direction} {desc!r}: got {(leaf, tier)}, want {(want_leaf, want_tier)}")


def test_kfc_atm_t2_owned_by_generator():
    """KFC-in-narrative and in-store ATM must precede T4 on both providers."""
    sql = (ROOT / "sql" / "apply_crosswalk.sql").read_text()
    gen = (ROOT / "src" / "generate_crosswalk_sql.py").read_text()
    for marker in ("T2_compound_kfc", "T2_compound_grocer_petrol",
                   "T1_direction_gambling_credit", "T2_compound_refund",
                   "T2_compound_returned_payment",
                   "T2_compound_youlend_disbursement"):
        assert marker in gen, f"{marker} missing from generator"
        assert sql.count(marker) == 2, f"{marker} count={sql.count(marker)}, want 2"
    for marker in ("T2_compound_admiral_casino", "T2_compound_ocado_salary",
                   "T2_compound_now_entertai", "T2_compound_paypal_now",
                   "T2_compound_grosvenor_salary"):
        assert marker in gen or "T2_CARLOS_PACK" in gen
        assert sql.count(marker) == 2, f"{marker} count={sql.count(marker)}, want 2"
    assert "T2_compound_instore_atm" in gen
    assert sql.count("T2_compound_instore_atm_deposit") == 2
    assert sql.count("T2_compound_instore_atm") - sql.count("T2_compound_instore_atm_deposit") == 2
    for block_name, block in (
        ("eqx_resolved", sql.split("eqx_resolved AS (")[1].split("plaid_raw AS (")[0]),
        ("plaid_resolved", sql.split("plaid_resolved AS (")[1].split("combined AS (")[0]),
    ):
        leaf_case = block.split("END AS leaf")[0]
        t4 = leaf_case.find("WHEN d.leaf IS NOT NULL THEN d.leaf")
        kfc = leaf_case.find(r"\bkfc\b")
        atm = leaf_case.find(r"\batm\b")
        assert kfc != -1 and kfc < t4, f"{block_name}: KFC T2 missing or after T4"
        assert atm != -1 and atm < t4, f"{block_name}: ATM T2 missing or after T4"
        refunded = leaf_case.find(r"refund(ed)?")
        returned = leaf_case.find("returned")
        assert refunded != -1 and refunded < t4, f"{block_name}: refund T2 missing or after T4"
        assert returned != -1 and returned < t4, f"{block_name}: returned-payment T2 missing or after T4"


def test_t4_gold_v3v4_overrides_present():
    rows = {r["normalised_merchant"]: r["detailed_category"]
            for r in csv.DictReader(DICT.open())}
    expect = {
        "sony playstation": "gaming_console_pc",
        "amazon prime": "streaming",
        "zippa loans": "payday_loan",
        "gdk borough": "takeaway",
        "kiley": "transfer_p2p",
        "savers health": "health_beauty_general",
        "oodle car finance": "car_finance_repayment",
        "duelz": "gambling_casino",
        "domino's": "takeaway",
        "depop": "marketplace_general",
        "lime": "bicycle",
        "tescophoneins.": "insurance_other",
        "off licence gs wi": "alcohol_beer_spirits",
        "goldwire conve": "convenience_store",
        "cd ridgewood stores": "convenience_store",
        "stagecoach services": "public_transport_rail_coach",
        "morr wetherby": "groceries",
        "morr catcliffe": "groceries",
        "prime video": "streaming",
        "creditspring": "personal_loan_repayment",
        "tk maxx": "department_store",
        "google one": "web_services",
        "voi": "bicycle",
        "bandoo": "health_beauty_general",
        "3s retail ltd": "convenience_store",
        "travelodge": "accommodation",
        "coop": "groceries",
        "loans2go": "payday_loan",
        "tesco petrol": "fuel",
        "costa coffee": "restaurant_cafe",
        "trainline": "public_transport_rail_coach",
        "icelandair": "groceries",
        "www.amazon.": "marketplace_amazon",
        "jackpotjoy": "gambling_bingo",
        "tiktok shop": "marketplace_general",
        "the tanning shop": "beauty_treatment",
        "german doner kebab": "takeaway",
        "colchester zoo": "days_out",
        "parentpay": "school_fees",
        "five guys": "takeaway",
        "morr": "groceries",
        "barclays bank": "mortgage",
        "ticketmaster": "live_music",
        "wex europe": "business_services",
        "utility warehouse": "utility_other",
        "ajjb law": "debt_collection",
        "jollyes": "pet_supplies",
        "domestic & general": "insurance_general",
        "national education first": "education_general",
        "admiral": "insurance_general",
        "ocado": "groceries",
        "youlend": "business_loan_repayment",
        "royal london": "insurance_life",
        "royal london pensions": "pension_contribution",
        "places for people": "rent",
        "kwiff": "gambling_betting",
        "close brothers": "car_finance_repayment",
        "ask italian": "restaurant_cafe",
        "peacock": "clothing_womens",
        "bupa": "insurance_health",
        "nuffield health": "gym_fitness",
        "classic plus": "transfer_own_account",
        "plum fintech": "savings_transfer",
        "fife council": "council_tax",
        "sodexo": "catering",
        "avon": "health_beauty_general",
        "prudential": "pension_contribution",
        "fluid": "credit_card_repayment",
        "aspire": "prize_competitions",
        "national trust": "memberships",
        "finance coll": "personal_loan_repayment",
        "k sounds group lim": "car_finance_repayment",
        "cox": "transfer_p2p",
        "white lion": "pub_bar",
        "lets win": "prize_competitions",
        "saga services": "insurance_general",
        "cts": "public_transport_rail_coach",
        "transferwise": "money_transfer_service",
        "help to buy": "personal_loan_repayment",
        "grosvenor casino": "gambling_casino",
        "the kingfisher": "pub_bar",
        "cotswold outdoor": "clothing_outdoor",
        "council": "government_services",
        "off licence": "alcohol_beer_spirits",
        "liberty": "department_store",
        "virgin mobile": "mobile_phone_contract",
        "the grove": "pub_bar",
        "standing order": "transfer_bank_unspecified",
    }
    for m, leaf in expect.items():
        assert rows.get(m) == leaf, f"{m}: got {rows.get(m)}, want {leaf}"
    assert "now" not in rows, "bare now must not be T4; T2/T5 streaming only"
    for banned in ("mercedes-benz", "plus", "gem", "home", "city", "orbit",
                   "spring", "wood j"):
        assert banned not in rows, f"{banned} must not be a T4 key"
    savers_pharm = [m for m, leaf in rows.items()
                    if m.startswith("savers health") and leaf == "pharmacy"]
    assert not savers_pharm, f"savers still pharmacy: {savers_pharm[:8]}"


def test_payday_rule_no_dictionary_false_positives():
    """R18/R19 must not fire on dictionary merchants that are not payday_loan.
    loans2go is in T4 as payday_loan, so a dictionary hit is not a false positive."""
    import re
    rules = [r for r in csv.DictReader(RULES.open()) if r["rule_id"] in {"R18", "R19"}]
    assert rules, "R18/R19 payday rules missing"
    pattern = rules[0]["pattern"]
    compiled = re.compile(pattern, re.I)
    fps = []
    for r in csv.DictReader(DICT.open()):
        if compiled.search(r["normalised_merchant"]) and r["detailed_category"] != "payday_loan":
            fps.append((r["normalised_merchant"], r["detailed_category"]))
    assert not fps, f"payday rule hits non-payday dictionary merchants: {fps}"


def test_morr_t5_word_boundary_and_exclusions():
    """R21 must catch Morr Paignton and not Morrisons / Morriston / Morrison supply."""
    import re
    rules = [r for r in csv.DictReader(RULES.open()) if r["rule_id"] == "R21"]
    assert rules, "R21 Morrisons-truncation rule missing"
    rule = rules[0]
    assert rule["detailed_category"] == "groceries"
    assert rule["direction"] == "debit"
    assert rule["field"] == "merchant_name"
    pat = re.compile(rule["pattern"], re.I)
    excl = re.compile(rule["exclude_pattern"], re.I)
    assert pat.search("morr paignton")
    assert pat.search("morr")
    assert not pat.search("morrisons")
    assert not pat.search("morriston hospital")
    assert not pat.search("morrison supply")
    assert excl.search("morr petrol paignton")
    assert not excl.search("morr paignton")


def test_t4_skips_pending_and_unclassified():
    """Pending and unclassified_* must not be deterministic T4 matches.
    Tesco is the original seed dictionary — it must remain eligible."""
    sys.path.insert(0, str(ROOT / "src"))
    from generate_crosswalk_sql import is_t4_eligible_row, load_t4_dictionary
    import final_evaluation as fe

    dmap = load_t4_dictionary()
    assert dmap.get("tesco") == "groceries"
    assert "play.com" not in dmap
    assert "marketplace" not in dmap
    for leaf in dmap.values():
        assert not leaf.startswith("unclassified"), leaf
    raw = list(csv.DictReader(DICT.open()))
    assert all(is_t4_eligible_row(r) for r in raw), (
        "merchant_dictionary.csv must only contain T4-eligible rows")
    assert len(dmap) == len({r["normalised_merchant"] for r in raw})
    fe.DICTIONARY = fe.load_dictionary()
    assert fe.DICTIONARY == dmap


def test_trading_212_is_t4_investment_trading():
    sys.path.insert(0, str(ROOT / "src"))
    from generate_crosswalk_sql import load_t4_dictionary

    dmap = load_t4_dictionary()
    assert dmap.get("trading 212") == "investment_trading"
    assert dmap.get("trading212") == "investment_trading"


def test_tranche4_human_reviewed_is_carlos_only():
    t4 = ROOT / "data" / "production_labels_tranche4.csv"
    rows = list(csv.DictReader(t4.open()))
    human = [r for r in rows if r["tier"] == "human_reviewed"]
    assert human, "expected a handful of Carlos human_reviewed rows"
    assert len(human) < 20, f"human_reviewed ballooned to {len(human)}"
    for r in human:
        assert r.get("resolution_source") == "carlos", r["merchant"]
        assert r.get("reviewer_id") == "carlos", r["merchant"]
    agent_tiers = {"agent_consensus", "agent_tiebreak", "agent_review"}
    assert sum(1 for r in rows if r["tier"] in agent_tiers) > 80_000
    assert "human_reviewed" not in {
        r["tier"] for r in rows if r.get("resolution_source", "").startswith("agent_")
    }


def test_fill_agent_tiebreak_does_not_overwrite_opus():
    src = (ROOT / "src" / "fill_agent_tiebreak.py").read_text()
    assert "FILLED" in src
    assert "production_predictions_opus_filled.csv" in src
    assert 'open(OPUS, "w"' not in src
    assert "open(OPUS, 'w'" not in src


def test_t4_sql_is_table_join_under_1mb():
    """91k dictionary rows cannot be inlined; BQ query text maxes out at ~1 MB."""
    sql = (ROOT / "sql" / "apply_crosswalk.sql").read_text()
    assert "credit_risk_research.merchant_dictionary_t4" in sql
    assert "UNNEST([STRUCT<merchant STRING, leaf STRING>" not in sql
    assert len(sql.encode("utf-8")) < 1_000_000, len(sql.encode("utf-8"))


def test_refuse_confirmation_eval_blocks_v5_and_v6():
    sys.path.insert(0, str(ROOT / "src"))
    import pytest
    from eval_sets import refuse_confirmation_eval, v6_excluded_merchants

    refuse_confirmation_eval(ROOT / "data" / "gold_v2_slm_eval_holdout.csv")
    with pytest.raises(SystemExit):
        refuse_confirmation_eval(ROOT / "data" / "gold_transactions_v5_LOCKED.csv")
    with pytest.raises(SystemExit):
        refuse_confirmation_eval(ROOT / "data" / "gold_transactions_v6_LOCKED.csv")
    seen = v6_excluded_merchants()
    assert "tesco" in seen
    v5 = ROOT / "data" / "gold_transactions_v5_LOCKED.csv"
    v5_m = next(
        (r["merchant_raw"].strip().lower()
         for r in csv.DictReader(v5.open()) if r.get("merchant_raw", "").strip()),
        "",
    )
    assert v5_m and v5_m in seen
    t4 = ROOT / "data" / "production_labels_tranche4.csv"
    t4_m = next(r["merchant"].strip().lower() for r in csv.DictReader(t4.open()) if r.get("merchant"))
    assert t4_m in seen


def test_plaid_legacy_category_map_valid_leaves():
    leaves = {r["detailed_category"] for r in csv.DictReader(TAX.open())}
    rows = list(csv.DictReader((ROOT / "taxonomy" / "plaid_legacy_category_map.csv").open()))
    bad = [r["category_path"] for r in rows if r["leaf"] not in leaves]
    assert not bad, f"legacy category map unknown leaves: {bad}"
    paths = [r["category_path"] for r in rows]
    dupes = [k for k, n in collections.Counter(paths).items() if n > 1]
    assert not dupes, f"duplicate category_path: {dupes}"

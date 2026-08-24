"""Integrity tests for the taxonomy and merchant dictionary.

These exist because manual edits to the taxonomy have already introduced real bugs
during development: three invalid leaf references (`electronics_computing` instead of
`computing_devices`) and one provider value (`Stationery`) mapped to two leaves.
Run these after every edit.
"""
import csv
import pathlib
import collections
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
TAX = ROOT / "taxonomy" / "taxonomy.csv"
DICT = ROOT / "taxonomy" / "merchant_dictionary.csv"
RULES = ROOT / "taxonomy" / "rules" / "deterministic_rules.csv"

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
        ("Tescophoneins.", "debit", "TESCOPHONEINS.",
         "insurance_other", "T4_dictionary"),
        ("Morr Paignton", "debit", "MORR PAIGNTON Morr Paignton",
         "groceries", "T5_R21"),
        ("Morrisons Petrol", "debit", "MORRISONS PETROL",
         "fuel", "T4_dictionary"),
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
                   "T1_direction_gambling_credit"):
        assert marker in gen, f"{marker} missing from generator"
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
    }
    for m, leaf in expect.items():
        assert rows.get(m) == leaf, f"{m}: got {rows.get(m)}, want {leaf}"
    savers_pharm = [m for m, leaf in rows.items()
                    if m.startswith("savers health") and leaf == "pharmacy"]
    assert not savers_pharm, f"savers still pharmacy: {savers_pharm[:8]}"


def test_payday_rule_no_dictionary_false_positives():
    """R18/R19 must not fire on dictionary merchants that are not payday_loan.
    loans2go is deliberately omitted from the pattern (T4 maps it to personal_loan)."""
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

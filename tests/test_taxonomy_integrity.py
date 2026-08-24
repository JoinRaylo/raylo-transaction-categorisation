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
        for needle in (r"\btesco bank\b", r"petrol|\bpfs\b", "tescophoneins"):
            pos = leaf_case.find(needle)
            assert pos != -1, f"{block_name}: {needle!r} missing from leaf CASE"
            assert pos < t4, f"{block_name}: {needle!r} must precede T4"


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

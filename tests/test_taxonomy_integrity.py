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

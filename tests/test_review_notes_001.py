"""REVIEW-NOTES-001: rule changes from Carlos's 2026-09-23 benchmark review.

Positive, negative and precedence cases through the pinned research waterfall
(``final_evaluation.our_leaf`` with the Plaid native path), plus generated-SQL
branch checks.  Cases are synthetic narratives in the observed formats.
"""

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import final_evaluation as fe  # noqa: E402
import generate_crosswalk_sql as generator  # noqa: E402

fe.SUB_MAP, fe.PRI_MAP, fe.PLAID_MAP, _ = fe.load_crosswalk()
fe.DICTIONARY = fe.load_dictionary()
fe.RULES = fe.load_rules()

CASES = [
    # (case_id, merchant, direction, description, plaid native, leaf, tier)
    ("added_to_pot", "", "credit", "Added to Pot", "INCOME_SALARY", "savings_transfer", "T5_R52"),
    ("withdrew_from_pot", "", "debit", "Withdrew from Pot", "TRANSFER_OUT_SAVINGS",
     "transfer_own_account", "T5_R53"),
    ("angel_hill_blank", "", "debit", "7611 17OCT25 CD   ANGEL HILL SITE   033.1   WREXHAM GB",
     "TRANSFER_OUT_OTHER", "restaurant_cafe", "T5_R54"),
    ("angel_hill_t4_key", "Angel Hill Site Ca", "debit",
     "Contactless Payment ANGEL HILL SITE CA414 APPLEPAY 3425", "TRANSFER_OUT_OTHER",
     "restaurant_cafe", "T4_dictionary"),
    ("ytc_blank", "", "debit", "CARD PAYMENT TO YTC SKIPTON ON 13-12-2025", "TRANSFER_OUT_OTHER",
     "discount_store", "T5_R55"),
    ("onlyfans_usd", "USD", "debit", "CARD PAYMENT TO OF ,90.00 USD, RATE 0.7403/GBP ON 18-08-2025",
     "TRANSFER_OUT_OTHER", "adult_entertainment", "T2_compound_usd_onlyfans"),
    ("asda_living", "Asda", "debit", "ASDA STORES  ON 21 SEP BDC ASDA LIVING BROUGH",
     "FOOD_RETAIL_GROCERIES", "department_store", "T2_compound_asda_living"),
    ("google_play_apps", "Google Play", "debit", "Google Play Apps  ON 15 MAR CPM GOOGLE PLAY APPS",
     "ENTERTAINMENT_VIDEO_GAMES", "gaming_mobile", "T4_dictionary"),
    ("post_office_counter", "Post Office", "debit", "POST OFFICE  25OCT",
     "TRANSFER_OUT_CHECKS_AND_ATM", "delivery_courier", "T4_dictionary"),
]
NEGATIVE = [
    # (case_id, merchant, direction, description, native, leaf that must NOT result, tier prefix)
    ("pot_phrase_not_exact", "", "credit", "Added to Pot for holiday", "INCOME_SALARY",
     None, "T5_R52"),
    ("ytc_credit_not_spend", "", "credit", "YTC SKIPTON REFUND", "TRANSFER_IN_OTHER", None, "T5_R55"),
    ("usd_other_merchant", "USD", "debit", "CARD PAYMENT TO AMAZON ,9.00 USD, RATE 0.74/GBP",
     "TRANSFER_OUT_OTHER", "adult_entertainment", None),
    ("angel_hill_place_name", "", "debit", "ANGEL HILL SURGERY", "MEDICAL_OTHER_MEDICAL",
     "restaurant_cafe", None),
]


def resolve(merchant, direction, description, native):
    return fe.our_leaf(merchant, direction, description, fe.plaid_native_leaf, native, direction)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c[0])
def test_review_note_rules_fire(case):
    _, merchant, direction, description, native, leaf, tier = case
    assert resolve(merchant, direction, description, native) == (leaf, tier)


@pytest.mark.parametrize("case", NEGATIVE, ids=lambda c: c[0])
def test_review_note_rules_do_not_overreach(case):
    _, merchant, direction, description, native, bad_leaf, bad_tier = case
    leaf, tier = resolve(merchant, direction, description, native)
    if bad_tier:
        assert not tier.startswith(bad_tier)
    if bad_leaf:
        assert leaf != bad_leaf


def test_existing_higher_precedence_rules_are_unchanged():
    # T2 in-store ATM still beats the corrected Post Office dictionary key.
    assert resolve("Post Office", "debit", "POST OFFICE CASH WITHDRAWAL ATM", None)[0] == (
        "cash_withdrawal"
    )
    # Gambling credits stay gambling_unspecified via T1 (native and dictionary paths).
    assert resolve("Betfair", "credit", "BETFAIR", "ENTERTAINMENT_CASINOS_AND_GAMBLING") == (
        "gambling_unspecified", "T1_direction"
    )
    assert resolve("Betfair", "credit", "BETFAIR", None) == (
        "gambling_unspecified", "T1_direction_gambling_credit"
    )


def test_generated_sql_contains_each_new_branch_once():
    sql = (ROOT / "sql/apply_crosswalk.sql").read_text()
    row = next(r for r in generator.T2_COLLISION_ROWS if r["rule_id"] == "usd_onlyfans")
    for merchant in (generator.EQX_MERCHANT_EXPR, generator.PLAID_MERCHANT_EXPR):
        for value in ("adult_entertainment", "T2_compound_usd_onlyfans"):
            branch = generator._t2_collision_when(row, merchant, generator.EQX_DESC_EXPR, value)
            assert sql.count(branch) == 1
    for rule_id in ("R52", "R53", "R54", "R55"):
        assert sql.count(f"THEN 'T5_rule_{rule_id}'") == 2
    assert sql.count("r'asda\\s*living') THEN 'department_store'") == 2
    assert "r'asda\\s*living') THEN 'home_accessories'" not in sql

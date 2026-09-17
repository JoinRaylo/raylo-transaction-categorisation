"""CREDIT-PAYROLL-001 boundary and generated SQL regression cases."""
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import generate_crosswalk_sql as generator

CASES = json.loads((ROOT / "tools/waterfall-evaluation/payroll_cases.json").read_bytes())["cases"]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["case_id"])
def test_waitrose_explicit_payroll(case):
    result = generator.match_t2(case["merchant_raw"], case["direction"], case["description_raw"])
    assert (result == ("salary", "T2_compound_waitrose_explicit_payroll")) == case["matches_new_t2"]


def test_generated_sql_contains_each_new_branch_once():
    row = next(r for r in generator.T2_COLLISION_ROWS if r["rule_id"] == "waitrose_explicit_payroll")
    assert row["direction"] == "credit"
    assert row["merchant"] == "waitrose"
    sql = (ROOT / "sql/apply_crosswalk.sql").read_text()
    for merchant in (generator.EQX_MERCHANT_EXPR, generator.PLAID_MERCHANT_EXPR):
        for value in ("salary", "T2_compound_waitrose_explicit_payroll"):
            branch = generator._t2_collision_when(row, merchant, generator.EQX_DESC_EXPR, value)
            assert sql.count(branch) == 1

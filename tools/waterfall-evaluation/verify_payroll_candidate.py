"""Verify the declared synthetic boundary, Python parity and emitted RE2 clauses.

Requires google-re2 in an isolated test dependency directory. No cloud SQL is
executed: all four changed SQL predicates use RE2 locally; the rest of the SQL
must remain byte-identical. No customer data is read by this check.
"""

import argparse
import importlib.metadata
import importlib.util
import json
import subprocess
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import re2
from derive_payroll_candidate import CSV_PATH, PARENT, RULE, verify_append
from raylo_txncat.bundle import load_local
from raylo_txncat.compile_artefacts import read_csv
from raylo_txncat.hashing import canonical_json, sha256
from raylo_txncat.tiers import DeterministicTiers
from raylo_txncat.types import ProviderCategory, Transaction

PROFILES = [
    ("plaid", "", False),
    ("plaid", "FOOD_AND_DRINK_GROCERIES", False),
    ("plaid", "ENTERTAINMENT_CASINOS_AND_GAMBLING", True),
    ("equifax", "General Shopping | General Groceries", False),
    ("equifax", "Refund | General Groceries", False),
    ("equifax", "Identified Salary | General Groceries", False),
    ("equifax", "Gambling and Betting | General Groceries", True),
    ("equifax", "Identified Salary | Council", True),
    ("equifax", "Identified Salary | Delivery", True),
    ("equifax", "Identified Salary | Employment Agencies", True),
]


def verify(parent_path, candidate_path, research, monorepo):
    parent = load_local(parent_path, expected_sha=PARENT)
    candidate = load_local(candidate_path)
    changed_files = {name for name, raw in parent.files.items() if candidate.files.get(name) != raw}
    assert changed_files == {"t2_collisions.json", "provenance.json"}
    assert set(candidate.files) == set(parent.files)
    source = candidate.json("provenance.json")["derivation"]
    assert source["parent_bundle_sha"] == PARENT
    assert source["source_after"]["sha256"] == sha256((research / CSV_PATH).read_bytes())
    assert (
        read_csv(research / CSV_PATH, allow_extra_notes=True)
        == candidate.json("t2_collisions.json")["csv_rows"]
    )
    baseline = DeterministicTiers.from_bundle(parent)
    proposed = DeterministicTiers.from_bundle(candidate)
    # The source guard in differential additionally verifies both frozen Python
    # resolvers. Importing the generator only reads its local CSV definitions.
    generator_path = research / "src/generate_crosswalk_sql.py"
    assert (
        sha256(generator_path.read_bytes())
        == candidate.json("t2_collisions.json")["code_defined_rules_source"]["sha256"]
    )
    spec = importlib.util.spec_from_file_location("payroll_research_generator", generator_path)
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    parent_commit = parent.json("provenance.json")["research_commit"]
    old_csv = subprocess.check_output(["git", "show", f"{parent_commit}:{CSV_PATH}"], cwd=research)
    verify_append(old_csv, (research / CSV_PATH).read_bytes())
    old_sql = subprocess.check_output(
        ["git", "show", f"{parent_commit}:sql/apply_crosswalk.sql"], cwd=research
    )
    sql = (research / "sql/apply_crosswalk.sql").read_bytes()
    branches = [
        generator._t2_collision_when(RULE, merchant, generator.EQX_DESC_EXPR, value)
        for merchant in (generator.EQX_MERCHANT_EXPR, generator.PLAID_MERCHANT_EXPR)
        for value in ("salary", "T2_compound_waitrose_explicit_payroll")
    ]
    # Both providers currently share the identical lowered narrative expression.
    assert generator.EQX_DESC_EXPR == generator.PLAID_DESC_EXPR
    restored = sql
    for branch in branches:
        assert restored.count((branch + "\n").encode()) == 1
        restored = restored.replace((branch + "\n").encode(), b"")
    assert restored == old_sql, "SQL changed outside the four declared branches"
    cases_path = Path(__file__).with_name("payroll_cases.json")
    cases = json.loads(cases_path.read_bytes())["cases"]
    diagnostics, sql_checks = [], 0
    for case in cases:
        merchant, description = case["merchant_raw"], case["description_raw"]
        direction = case["direction"]
        research_t2 = generator.match_t2(merchant, direction, description)
        expected_t2 = ("salary", "T2_compound_waitrose_explicit_payroll")
        assert (research_t2 == expected_t2) == case["matches_new_t2"], case["case_id"]
        for branch in branches:
            # Execute the exact emitted raw pattern, not a separately escaped copy.
            pattern = branch.split(", r'", 1)[1].split("') THEN", 1)[0]
            sql_hit = (
                (merchant or "").strip().lower() == "waitrose"
                and direction == "credit"
                and bool(re2.search(pattern, (description or "").lower()))
            )
            assert sql_hit == case["matches_new_t2"], case["case_id"]
            sql_checks += 1
        for provider, native, preempts_credit in PROFILES:
            before = baseline.resolve(merchant, direction, description, native, provider)
            after = proposed.resolve(merchant, direction, description, native, provider)
            expected_change = case["matches_new_t2"] and not preempts_credit
            if expected_change:
                assert (after.leaf, after.tier, after.rule_id) == (
                    "salary",
                    "T2_compound_waitrose_explicit_payroll",
                    "waitrose_explicit_payroll",
                )
            else:
                assert after == before, (case["case_id"], provider, native)
            diagnostics.append(
                {
                    "case_id": case["case_id"],
                    "provider": provider,
                    "native_category": native,
                    "baseline": before.golden(),
                    "candidate": after.golden(),
                    "changed": after != before,
                }
            )
            if provider == "plaid":
                for amount in (Decimal("2.99"), Decimal("1989.11"), Decimal("0")):
                    wire = Transaction(
                        transaction_id=case["case_id"],
                        account_id="synthetic",
                        date=date(2000, 1, 1),
                        currency="GBP",
                        merchant_name=merchant,
                        description=description,
                        transaction_name=None,
                        is_pending=False,
                        amount=-amount if direction == "credit" else amount,
                        provider_category=ProviderCategory(detailed=native),
                    )
                    actual = proposed.resolve_transaction(wire)
                    wire_direction = "credit" if wire.amount < 0 else "debit"
                    assert actual == proposed.resolve(
                        merchant, wire_direction, description, native, provider
                    )
                    if amount == 0:
                        assert actual.rule_id != "waitrose_explicit_payroll"
    sys.path.insert(0, str(monorepo / "lib/raylo-txncat/scripts"))
    from verify_deterministic import differential

    golden = [json.loads(line) for line in candidate.files["golden.jsonl"].splitlines()]
    extended = golden + [{"research_input": c} for c in cases]
    parity = differential(research, candidate, proposed, extended)
    return {
        "status": "passed",
        "change_id": "CREDIT-PAYROLL-001",
        "parent_bundle_sha": PARENT,
        "candidate_bundle_sha": candidate.manifest.bundle_sha,
        "changed_payloads": sorted(changed_files),
        "old_goldens_unchanged": True,
        "cases_sha256": sha256(cases_path.read_bytes()),
        "cases": len(cases),
        "profile_checks": len(diagnostics),
        "wire_checks": len(cases) * 3 * 3,
        "re2_predicate_checks": sql_checks,
        "re2_version": importlib.metadata.version("google-re2"),
        "sql_sha256": sha256(sql),
        "sql_added_branches": 4,
        "sql_execution": "changed predicates checked locally with RE2; no BigQuery execution",
        "extended_research_app_parity": parity,
        "diagnostics": diagnostics,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("parent", "candidate", "research-root", "monorepo-root", "report"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    args = parser.parse_args()
    result = verify(args.parent, args.candidate, args.research_root, args.monorepo_root)
    args.report.write_bytes(canonical_json(result) + b"\n")
    print(canonical_json({k: v for k, v in result.items() if k != "diagnostics"}).decode())


if __name__ == "__main__":
    main()

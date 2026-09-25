"""Synthetic guards for the admission profiler's fail-closed view policy."""

import hashlib
import json

import pytest
from benchmark_profile_candidates import (
    SCOPE_CONTRACT,
    SCOPE_CONTRACT_SHA256,
    _load_candidates,
    _validate_candidate_receipt,
    _view_decisions,
)

pytestmark = pytest.mark.unit


def _base(**changes):
    values = {
        "current_identity": True,
        "aliases_verified": True,
        "identity_history_complete": True,
        "input_sources": set(),
        "input_history_complete": True,
        "merchant_present": True,
        "merchant_known": False,
        "family_reviewed": True,
        "family_history_complete": True,
        "legacy_index_complete": True,
    }
    values.update(changes)
    return _view_decisions(**values)


def test_representative_allows_familiar_input_but_strict_views_do_not():
    decisions = _base(input_sources={"tuning_train"})
    assert decisions["representative"]["status"] == "eligible_preflight"
    assert decisions["unseen_input"]["status"] == "reject"
    assert "effective_input_overlap" in decisions["unfamiliar_merchant"]["reasons"]


def test_unknown_history_quarantines_even_when_no_local_match_exists():
    decisions = _base(
        aliases_verified=False,
        identity_history_complete=False,
        input_history_complete=False,
        family_history_complete=False,
        legacy_index_complete=False,
    )
    for decision in decisions.values():
        assert decision["status"] == "quarantine"
    assert "event_alias_history_unknown" in decisions["representative"]["reasons"]
    assert "unknown_input_history" in decisions["unseen_input"]["reasons"]
    assert "missing_legacy_exclusion_index" in decisions["unfamiliar_merchant"]["reasons"]


def test_known_merchant_rejects_unfamiliar_view_but_not_representative():
    decisions = _base(merchant_known=True)
    assert decisions["representative"]["status"] == "eligible_preflight"
    assert decisions["unseen_input"]["status"] == "eligible_preflight"
    assert decisions["unfamiliar_merchant"]["status"] == "reject"


def test_blank_merchant_never_claims_unfamiliar_family():
    decisions = _base(merchant_present=False)
    assert decisions["representative"]["status"] == "eligible_preflight"
    assert decisions["unfamiliar_merchant"]["status"] == "quarantine"
    assert "blank_not_unfamiliar" in decisions["unfamiliar_merchant"]["reasons"]


def _receipt_fixture(tmp_path, row=None):
    result_path = tmp_path / "candidates.jsonl"
    if row is None:
        row = {"synthetic": True}
    result_path.write_text(json.dumps(row, sort_keys=True) + "\n")
    extractor_sql = tmp_path / "benchmark_candidate_extract.sql"
    extractor = tmp_path / "benchmark_candidate_extract.py"
    extractor_sql.write_text("-- synthetic candidate SQL\n")
    extractor.write_text("# synthetic candidate runner\n")
    receipt = {
        "schema_version": "benchmark-candidate-extract-v1",
        "purpose": "private_customer_linked_plaid_candidate_draw",
        "project": "raylo-production",
        "location": "EU",
        "statement_type": "SELECT",
        "source_table": SCOPE_CONTRACT["source_table"],
        "source_kind": SCOPE_CONTRACT["source_kind"],
        "scope_contract": SCOPE_CONTRACT,
        "scope_contract_sha256": SCOPE_CONTRACT_SHA256,
        "anonymous_id_recovery": False,
        "authorizes_consumption": False,
        "executed": True,
        "sql_sha256": hashlib.sha256(extractor_sql.read_bytes()).hexdigest(),
        "runner_sha256": hashlib.sha256(extractor.read_bytes()).hexdigest(),
        "result_sha256": hashlib.sha256(result_path.read_bytes()).hexdigest(),
        "candidate_limit": 1,
        "result_rows": 1,
        "dry_run_bytes": 1,
        "bytes_processed": 1,
        "bytes_billed": 1,
    }
    (tmp_path / "receipt.json").write_text(json.dumps(receipt, sort_keys=True) + "\n")
    return receipt, result_path, extractor_sql, extractor


def test_candidate_receipt_is_bound_to_scope_and_extractor(tmp_path):
    receipt, result_path, extractor_sql, extractor = _receipt_fixture(tmp_path)
    _validate_candidate_receipt(receipt, result_path, extractor_sql, extractor)

    receipt["scope_contract"] = {**SCOPE_CONTRACT, "source_table": "wrong"}
    with pytest.raises(ValueError, match="approved source contract"):
        _validate_candidate_receipt(receipt, result_path, extractor_sql, extractor)


def test_candidate_loader_rejects_non_unique_link_evidence(tmp_path):
    row = {
        "account_id": "account-synthetic",
        "transaction_id": "transaction-synthetic",
        "customer_id": "customer-synthetic",
        "assessment_id": "assessment-synthetic",
        "checkout_id": "checkout-synthetic",
        "user_id": "user-synthetic",
        "assessment_checkout_count": 2,
        "checkout_user_count": 1,
        "user_customer_count": 1,
        "customer_record_count": 1,
    }
    _, result_path, extractor_sql, extractor = _receipt_fixture(tmp_path, row)
    with pytest.raises(ValueError, match="unique current links"):
        _load_candidates(tmp_path, extractor_sql, extractor)

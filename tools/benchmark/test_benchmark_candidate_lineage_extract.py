import pytest
from benchmark_candidate_lineage_extract import (
    _validate_lineage,
    _validate_profile,
    summarise,
)

pytestmark = pytest.mark.unit


def _candidate(account: str, transaction: str, customer: str) -> dict:
    return {
        "account_id": account,
        "transaction_id": transaction,
        "customer_id": customer,
    }


def _lineage(
    account: str,
    transaction: str,
    *,
    source: str = "plaid_materialized_history",
    pending: bool | None = False,
    report: str | None = "report-1",
    customer: str | None = "customer-1",
    linked_customer: str | None = None,
    amount: str = "10",
) -> dict:
    return {
        "source_kind": source,
        "observation_at": "2026-09-18T00:00:00+00:00",
        "assessment_id": "assessment-1",
        "account_id": account,
        "transaction_id": transaction,
        "transaction_date": "2026-09-17",
        "date_transacted": None,
        "amount": amount,
        "merchant_name": "Merchant",
        "transaction_name": "Merchant",
        "description": "Merchant purchase",
        "asset_report_id": report,
        "report_date_generated": "2026-09-18",
        "client_report_id": None,
        "is_pending": pending,
        "pending_transaction_id": None,
        "source_customer_id": customer,
        "linked_customer_id": linked_customer,
        "checkout_count": None,
        "user_count": None,
        "customer_count": None,
        "customer_record_count": None,
    }


def test_summary_fails_closed_on_missing_pending_alias_and_reports_variants():
    candidates = [_candidate("account-1", "transaction-1", "customer-1")]
    lineage = [
        _lineage(
            "account-1",
            "transaction-1",
            source="current_materialized",
            pending=None,
            report=None,
            customer=None,
            linked_customer="customer-1",
        ),
        _lineage(
            "account-1", "transaction-1", pending=False, amount="11", report="report-2"
        ),
        _lineage("account-1", "transaction-1", pending=True, amount="10"),
    ]
    result = summarise(candidates, lineage, "profile-sha")
    assert result["alias_signals"]["pending_transaction_id_available"] is False
    assert result["alias_signals"]["events_with_multiple_source_observations"] == 1
    assert result["alias_signals"]["events_with_content_variants"] == 1
    assert result["alias_signals"]["events_with_source_metadata_variants"] == 1
    assert result["alias_signals"]["events_with_pending_and_posted_states"] == 1
    assert result["admission"]["eligible_rows"] == 0


def test_summary_reports_identity_conflict_and_block_sizes_without_authority():
    candidates = [
        _candidate("account-1", "transaction-1", "customer-1"),
        _candidate("account-1", "transaction-2", "customer-2"),
        _candidate("account-2", "transaction-3", "customer-1"),
    ]
    lineage = [
        _lineage(
            "account-1",
            "transaction-1",
            source="current_materialized",
            pending=None,
            report=None,
            customer=None,
            linked_customer="customer-1",
        ),
        _lineage(
            "account-1",
            "transaction-2",
            source="current_materialized",
            pending=None,
            report=None,
            customer=None,
            linked_customer="customer-2",
        ),
        _lineage(
            "account-2",
            "transaction-3",
            source="current_materialized",
            pending=None,
            report=None,
            customer=None,
            linked_customer="customer-1",
        ),
    ]
    result = summarise(candidates, lineage, "profile-sha")
    assert (
        result["identity_signals"][
            "accounts_with_multiple_customer_ids_in_selected_lineage"
        ]
        == 1
    )
    assert result["identity_signals"]["customers_with_multiple_candidate_accounts"] == 1
    assert result["candidate_blocks"]["account_max_rows"] == 2
    assert result["candidate_blocks"]["customer_max_rows"] == 2
    assert result["family_evidence"]["family_absence_certified"] is False
    assert result["admission"]["authorizes_consumption"] is False


def test_summary_rejects_an_unexpected_account_transaction_pair():
    candidates = [
        _candidate("account-1", "transaction-1", "customer-1"),
        _candidate("account-2", "transaction-2", "customer-2"),
    ]
    lineage = [
        _lineage(
            "account-1",
            "transaction-1",
            source="current_materialized",
            pending=None,
            report=None,
            customer=None,
            linked_customer="customer-1",
        ),
        _lineage(
            "account-1",
            "transaction-2",
            source="current_materialized",
            pending=None,
            report=None,
            customer=None,
            linked_customer="customer-2",
        ),
    ]
    with pytest.raises(ValueError, match="unexpected candidate event pair"):
        summarise(candidates, lineage, "profile-sha")


def test_summary_rejects_a_missing_current_candidate_pair():
    candidates = [_candidate("account-1", "transaction-1", "customer-1")]
    lineage = [_lineage("account-1", "transaction-1", customer="customer-1")]
    with pytest.raises(ValueError, match="does not cover the exact candidate"):
        summarise(candidates, lineage, "profile-sha")


def test_summary_rejects_a_current_customer_mismatch():
    candidates = [_candidate("account-1", "transaction-1", "customer-1")]
    lineage = [
        _lineage(
            "account-1",
            "transaction-1",
            source="current_materialized",
            pending=None,
            report=None,
            customer=None,
            linked_customer="customer-2",
        )
    ]
    with pytest.raises(ValueError, match="does not match the candidate"):
        summarise(candidates, lineage, "profile-sha")


def test_lineage_rejects_non_boolean_pending_state():
    row = _lineage("account-1", "transaction-1", pending=1)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="pending state"):
        _validate_lineage(row)


def test_profile_requires_all_exact_false_history_flags_and_integer_zero(tmp_path):
    profile = tmp_path / "profile.json"
    profile.write_text(
        '{"schema_version":"benchmark-admission-profile-v1",'
        '"source_snapshot_sha256":"candidate-sha",'
        '"authorizes_consumption":false,"rows_reserved_or_labelled":false,'
        '"history_flags":{}}'
    )
    with pytest.raises(ValueError, match="candidate profile"):
        _validate_profile(profile, {"result_sha256": "candidate-sha"})

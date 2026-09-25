"""Synthetic tests for private evaluation-pilot allocation."""

import csv
import hashlib
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "benchmark"))

from build_eval_pilot import (  # noqa: E402
    MembershipProtection,
    PilotCandidate,
    _existing_protection,
    _membership_input_receipts,
    _validate_customer_token_mapping,
    _validate_lineage_rows,
    allocate_pilot,
    filter_separated_candidates,
)


def candidate(index, *, customer=None, unseen=True, unfamiliar=False):
    customer = index if customer is None else customer
    opaque = {
        "customer": f"{customer:064x}",
        "input_sources": [] if unseen else ["synthetic-history"],
        "merchant_present": unfamiliar,
        "merchant_known_sources": [] if unfamiliar else ["synthetic-merchant-source"],
    }
    return PilotCandidate(
        index=index,
        row={
            "account_id": f"account-{index}",
            "transaction_id": f"transaction-{index}",
            "customer_id": f"customer-{customer}",
        },
        opaque=opaque,
    )


def budgets(representative=2, unseen=2, unfamiliar=2):
    return {
        "representative": representative,
        "unseen_input": unseen,
        "unfamiliar_merchant": unfamiliar,
    }


def test_allocation_is_deterministic_and_assigns_exact_view_budgets():
    rows = [candidate(i, unfamiliar=i < 4) for i in range(10)]
    first = allocate_pilot(rows, budgets=budgets(), seed="synthetic-seed")
    second = allocate_pilot(rows[::-1], budgets=budgets(), seed="synthetic-seed")
    assert first == second
    assert len(first) == 6
    assert list(first.values()).count("unfamiliar_merchant") == 2
    assert list(first.values()).count("unseen_input") == 2
    assert list(first.values()).count("representative") == 2


def test_customer_block_is_never_split_across_views():
    rows = [
        candidate(0, customer=7, unfamiliar=True),
        candidate(1, customer=7, unfamiliar=True),
        candidate(2),
        candidate(3),
    ]
    result = allocate_pilot(
        rows,
        budgets=budgets(representative=1, unseen=1, unfamiliar=2),
        seed="synthetic-seed",
    )
    assert result[0] == result[1] == "unfamiliar_merchant"


def test_strict_views_require_every_row_in_the_customer_block_to_qualify():
    mixed = [
        candidate(0, customer=9, unfamiliar=True),
        candidate(1, customer=9, unseen=False, unfamiliar=False),
        candidate(2, unfamiliar=True),
        candidate(3),
        candidate(4),
    ]
    with pytest.raises(ValueError, match="unfamiliar_merchant cannot fill"):
        allocate_pilot(
            mixed,
            budgets=budgets(representative=1, unseen=1, unfamiliar=2),
            seed="synthetic-seed",
        )


def test_exact_capacity_shortfall_fails_closed():
    rows = [candidate(0, customer=1), candidate(1, customer=1)]
    with pytest.raises(ValueError, match="cannot fill exact target"):
        allocate_pilot(
            rows,
            budgets=budgets(representative=1, unseen=1, unfamiliar=1),
            seed="synthetic-seed",
        )


def test_existing_membership_loader_rejects_invalid_rows_and_returns_events(tmp_path):
    path = tmp_path / "membership.csv"
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=("provider", "account_id", "transaction_id", "role"),
        )
        writer.writeheader()
        writer.writerow(
            {
                "provider": "plaid",
                "account_id": "account",
                "transaction_id": "transaction",
                "role": "train",
            }
        )
    protection = _existing_protection([path])
    assert protection.events == {("account", "transaction")}
    assert protection.accounts == {"account"}

    path.write_text(
        "provider,account_id,transaction_id,role\nplaid,account,transaction,neither\n"
    )
    with pytest.raises(ValueError, match="invalid"):
        _existing_protection([path])


def test_pilot_candidate_rejects_malformed_opaque_evidence():
    row = candidate(1)
    malformed = PilotCandidate(index=1, row=row.row, opaque={**row.opaque, "input_sources": None})
    with pytest.raises(ValueError, match="input sources"):
        _ = malformed.unseen


def test_historical_input_exposure_is_retained_for_representative_allocation():
    rows = [
        candidate(0, customer=7),
        candidate(1, customer=7, unseen=False),
        candidate(2, customer=8),
    ]
    eligible, metrics = filter_separated_candidates(
        rows,
        protected=MembershipProtection(),
    )
    assert [row.index for row in eligible] == [0, 1, 2]
    assert metrics["historical_input_exposure_rows"] == 1
    assert metrics["historical_input_exposure_block_rows"] == 2


def test_existing_account_membership_excludes_the_whole_customer_block():
    rows = [
        candidate(0, customer=7),
        candidate(1, customer=7),
        candidate(2, customer=8),
    ]
    eligible, metrics = filter_separated_candidates(
        rows,
        protected=MembershipProtection(accounts=frozenset({"account-1"})),
    )
    assert [row.index for row in eligible] == [2]
    assert metrics["connected_membership_overlap_rows"] == 1
    assert metrics["membership_excluded_block_rows"] == 2


def test_representative_can_be_familiar_but_strict_views_cannot():
    rows = [
        candidate(0, unfamiliar=True),
        candidate(1),
        candidate(2, unseen=False),
    ]
    result = allocate_pilot(
        rows,
        budgets=budgets(representative=1, unseen=1, unfamiliar=1),
        seed="synthetic-seed",
    )
    assert result[2] == "representative"
    assert all(rows[index].unseen for index, view in result.items() if view != "representative")


def test_customer_grouping_uses_private_raw_customer_id():
    first = candidate(0, customer=7)
    second = candidate(1, customer=7)
    split_token = PilotCandidate(
        index=second.index,
        row=second.row,
        opaque={**second.opaque, "customer": f"{8:064x}"},
    )
    assert first.customer_block == split_token.customer_block
    assert first.opaque_customer != split_token.opaque_customer
    with pytest.raises(ValueError, match="grouping is inconsistent"):
        _validate_customer_token_mapping([first, split_token])


def test_historical_lineage_customer_conflict_fails_closed():
    events = {("account", "transaction"): "current-customer"}
    lineage = [
        {
            "account_id": "account",
            "transaction_id": "transaction",
            "source_kind": "current_materialized",
            "linked_customer_id": "current-customer",
        },
        {
            "account_id": "account",
            "transaction_id": "transaction",
            "source_kind": "historical_asset_report",
            "source_customer_id": "other-customer",
        },
    ]
    with pytest.raises(ValueError, match="historical lineage contradicts"):
        _validate_lineage_rows(events=events, lineage=lineage)


def test_membership_input_receipts_bind_hash_and_row_count(tmp_path):
    path = tmp_path / "membership.csv"
    path.write_text(
        "provider,account_id,transaction_id,role\n"
        "plaid,account,transaction,train\n",
        encoding="utf-8",
    )
    assert _membership_input_receipts([path]) == [
        {
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "rows": 1,
        }
    ]

"""Synthetic tests for ID-bearing training/selection membership sidecars."""

import csv
import json
import pathlib
import shutil
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import build_tuning_dataset as builder  # noqa: E402
import training_membership as membership_module  # noqa: E402
from build_tuning_dataset import build_linked_tier_b_query, tier_b_role  # noqa: E402
from training_membership import (  # noqa: E402
    SourceMembership,
    TrackedExample,
    canonical_sha256,
    exact_plaid_membership,
    publish_training_export,
    unavailable_membership,
    verify_training_export,
)


def plaid_row(name="one", *, description="synthetic coffee"):
    return {
        "account_id": f"account-{name}",
        "transaction_id": f"transaction-{name}",
        "customer_id": f"customer-{name}",
        "merchant": "synthetic merchant",
        "description": description,
        "amount": "12.34",
        "is_credit": "0",
        "target": "restaurant_cafe",
    }


def tracked(membership, *, leaf="restaurant_cafe"):
    return TrackedExample(
        messages={
            "messages": [
                {"role": "system", "content": "synthetic instruction"},
                {"role": "user", "content": "synthetic transaction"},
                {"role": "assistant", "content": leaf},
            ]
        },
        membership=membership,
    )


def publish(tmp_path, train, selection):
    paths = {
        "train_path": tmp_path / "train.jsonl",
        "selection_path": tmp_path / "selection.jsonl",
        "lookup_path": tmp_path / "membership.csv",
        "coverage_path": tmp_path / "coverage.json",
    }
    coverage = publish_training_export(train, selection, **paths)
    return coverage, paths


def test_exact_identity_requires_both_provider_ids_and_plaid_scope():
    row = plaid_row()
    membership = exact_plaid_membership(source="synthetic_plaid", row=row)
    assert membership.identity_status == "exact"
    assert membership.provider == "plaid"

    for missing in ("account_id", "transaction_id"):
        invalid = row | {missing: ""}
        with pytest.raises(ValueError, match="requires account and transaction"):
            exact_plaid_membership(source="synthetic_plaid", row=invalid)

    with pytest.raises(ValueError, match="customer-linked Plaid"):
        SourceMembership(
            source="synthetic_equifax",
            identity_status="exact",
            source_row_sha256=canonical_sha256(row),
            provider="equifax",
            account_id="account",
            transaction_id="transaction",
        )


def test_unavailable_identity_never_invents_provider_identifiers():
    membership = unavailable_membership(
        source="legacy_gold",
        row={"merchant": "synthetic", "provider": "Plaid"},
        provider="Plaid",
    )
    assert membership.identity_status == "unavailable"
    assert membership.provider == "plaid"
    assert membership.account_id is None
    assert membership.transaction_id is None

    with pytest.raises(ValueError, match="cannot assert"):
        SourceMembership(
            source="legacy_gold",
            identity_status="unavailable",
            source_row_sha256=canonical_sha256({"row": 1}),
            provider="plaid",
            account_id="invented",
        )


def test_lookup_deduplicates_oversampling_and_reports_unresolved(tmp_path):
    exact = exact_plaid_membership(source="synthetic_plaid", row=plaid_row())
    legacy = unavailable_membership(source="legacy_gold", row={"row": 1})
    coverage, paths = publish(
        tmp_path,
        [tracked(exact), tracked(exact), tracked(legacy)],
        [],
    )

    rows = list(csv.DictReader(paths["lookup_path"].open()))
    assert len(rows) == 1
    assert rows[0]["transaction_id"] == "transaction-one"
    assert rows[0]["role"] == "train"
    assert rows[0]["current_export_row_count"] == "2"
    assert coverage["current_unique_exact_transactions"] == 1
    assert coverage["permanent_unique_exact_transactions"] == 1
    assert coverage["roles"]["train"] == {
        "effective_rows": 3,
        "exact_identity_rows": 2,
        "unresolved_identity_rows": 1,
    }
    assert json.loads(paths["coverage_path"].read_text()) == coverage
    assert set(json.loads(paths["train_path"].read_text().splitlines()[0])) == {"messages"}
    assert coverage["model_files"]["train"]["rows"] == 3
    assert coverage["model_files"]["selection"]["rows"] == 0


@pytest.mark.parametrize(
    ("changed_role", "changed_row"),
    [
        (
            "selection",
            plaid_row(),
        ),
        (
            "train",
            plaid_row(description="changed payload"),
        ),
    ],
)
def test_lookup_rejects_cross_role_or_changed_payload_identity(
    tmp_path, changed_role, changed_row
):
    original = tracked(exact_plaid_membership(source="synthetic_plaid", row=plaid_row()))
    changed = tracked(exact_plaid_membership(source="synthetic_plaid", row=changed_row))
    with pytest.raises(ValueError, match="across roles, sources, or changed payloads"):
        publish(tmp_path, [original, changed] if changed_role == "train" else [original],
                [changed] if changed_role == "selection" else [])


def test_rejected_successive_build_preserves_previous_complete_export(tmp_path):
    original = tracked(exact_plaid_membership(source="synthetic_plaid", row=plaid_row()))
    _, paths = publish(tmp_path, [original], [])
    before = {name: path.read_bytes() for name, path in paths.items()}

    reassigned = tracked(exact_plaid_membership(source="synthetic_plaid", row=plaid_row()))
    with pytest.raises(ValueError, match="across roles, sources, or changed payloads"):
        publish_training_export([ ], [reassigned], **paths)

    assert {name: path.read_bytes() for name, path in paths.items()} == before


def test_successive_build_retains_permanent_assignment_and_binds_model_hashes(tmp_path):
    first = tracked(exact_plaid_membership(source="synthetic_plaid", row=plaid_row("first")))
    coverage, paths = publish(tmp_path, [first], [])
    second = tracked(exact_plaid_membership(source="synthetic_plaid", row=plaid_row("second")))
    coverage = publish_training_export([second], [], **paths)

    rows = list(csv.DictReader(paths["lookup_path"].open()))
    assert [row["transaction_id"] for row in rows] == [
        "transaction-first",
        "transaction-second",
    ]
    assert [row["current_export_row_count"] for row in rows] == ["0", "1"]
    assert coverage["current_unique_exact_transactions"] == 1
    assert coverage["permanent_unique_exact_transactions"] == 2
    for role, path_key in (("train", "train_path"), ("selection", "selection_path")):
        import hashlib

        assert coverage["model_files"][role]["sha256"] == hashlib.sha256(
            paths[path_key].read_bytes()
        ).hexdigest()


def test_corrupt_previous_model_binding_fails_closed(tmp_path):
    first = tracked(exact_plaid_membership(source="synthetic_plaid", row=plaid_row()))
    _, paths = publish(tmp_path, [first], [])
    paths["train_path"].write_text("tampered\n")
    with pytest.raises(ValueError, match="model digest does not match"):
        publish_training_export([first], [], **paths)


def test_failed_replacement_leaves_no_private_temp_files(tmp_path, monkeypatch):
    first = tracked(exact_plaid_membership(source="synthetic_plaid", row=plaid_row("first")))
    _, paths = publish(tmp_path, [first], [])
    second = tracked(exact_plaid_membership(source="synthetic_plaid", row=plaid_row("second")))
    real_replace = membership_module.os.replace
    calls = 0

    def fail_during_publish(source, destination):
        nonlocal calls
        calls += 1
        if calls == 3:
            raise OSError("synthetic replacement failure")
        return real_replace(source, destination)

    monkeypatch.setattr(membership_module.os, "replace", fail_during_publish)
    with pytest.raises(OSError, match="synthetic replacement failure"):
        publish_training_export([second], [], **paths)

    assert not list(tmp_path.glob(".*.tmp"))
    with pytest.raises(ValueError, match="digest does not match"):
        verify_training_export(**paths)


def test_failed_temp_fsync_cleans_private_temp_file(tmp_path, monkeypatch):
    first = tracked(exact_plaid_membership(source="synthetic_plaid", row=plaid_row()))

    def fail_fsync(_):
        raise OSError("synthetic fsync failure")

    monkeypatch.setattr(membership_module.os, "fsync", fail_fsync)
    with pytest.raises(OSError, match="synthetic fsync failure"):
        publish(tmp_path, [first], [])
    assert not list(tmp_path.iterdir())


def test_upload_verifies_and_copies_commit_marker_last(tmp_path, monkeypatch):
    first = tracked(exact_plaid_membership(source="synthetic_plaid", row=plaid_row()))
    _, paths = publish(tmp_path, [first], [])
    monkeypatch.setattr(builder, "TRAIN_JSONL", paths["train_path"])
    monkeypatch.setattr(builder, "VAL_JSONL", paths["selection_path"])
    monkeypatch.setattr(builder, "MEMBERSHIP_LOOKUP", paths["lookup_path"])
    monkeypatch.setattr(builder, "MEMBERSHIP_COVERAGE", paths["coverage_path"])
    calls = []

    def record(command, check):
        calls.append((command, check))

    monkeypatch.setattr("subprocess.run", record)
    builder.upload("gs://synthetic/private")

    assert len(calls) == 4
    assert all(check is True for _, check in calls)
    assert calls[-1][0][-1] == "gs://synthetic/private/membership_coverage.json"

    uploaded = tmp_path / "uploaded"
    uploaded.mkdir()
    destinations = {pathlib.Path(command[-1]).name: pathlib.Path(command[3]) for command, _ in calls}
    for destination, source in destinations.items():
        shutil.copyfile(source, uploaded / destination)
    verify_training_export(
        train_path=uploaded / "train.jsonl",
        selection_path=uploaded / "val.jsonl",
        lookup_path=uploaded / "membership_lookup.csv",
        coverage_path=uploaded / "membership_coverage.json",
    )


def test_upload_rejects_tampered_export_before_any_copy(tmp_path, monkeypatch):
    first = tracked(exact_plaid_membership(source="synthetic_plaid", row=plaid_row()))
    _, paths = publish(tmp_path, [first], [])
    paths["train_path"].write_text("tampered\n")
    monkeypatch.setattr(builder, "TRAIN_JSONL", paths["train_path"])
    monkeypatch.setattr(builder, "VAL_JSONL", paths["selection_path"])
    monkeypatch.setattr(builder, "MEMBERSHIP_LOOKUP", paths["lookup_path"])
    monkeypatch.setattr(builder, "MEMBERSHIP_COVERAGE", paths["coverage_path"])
    calls = []
    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: calls.append((args, kwargs)))

    with pytest.raises(ValueError, match="model digest does not match"):
        builder.upload("gs://synthetic/private")
    assert calls == []


def test_tier_b_query_is_id_bearing_customer_linked_and_deterministic():
    query = build_linked_tier_b_query(["synthetic merchant"], 7)
    assert "account_id" in query
    assert "transaction_id" in query
    assert "chosen.customer_id AS customer_id" in query
    assert "intermediate_credit_plaid_transactions" in query
    assert "credit_plaid_open_banking_transactions` t" not in query
    assert "checkout_count = 1" in query
    assert "user_count = 1" in query
    assert "customer_count = 1" in query
    assert "customer_record_count = 1" in query
    assert "SELECT s.*" in query
    assert "COUNT(DISTINCT payload_sha256) = 1" in query
    assert "COUNT(DISTINCT customer_id) = 1" in query
    assert "ARRAY_AGG" in query
    assert "source_payload_sha256" in query
    assert "ORDER BY TO_HEX(SHA256" in query
    assert "RAND()" not in query


def test_tier_b_role_is_stable_when_the_pool_changes():
    merchants = [f"synthetic-{i}" for i in range(100)]
    original = {merchant: tier_b_role(merchant) for merchant in merchants}
    expanded = {merchant: tier_b_role(merchant) for merchant in merchants + ["new-merchant"]}
    assert {merchant: expanded[merchant] for merchant in merchants} == original
    assert set(original.values()) == {"train", "selection"}


def test_tier_b_query_rejects_unsafe_empty_inputs():
    for merchants, cap in (([], 1), ([""], 1), (["synthetic"], 0), (["synthetic"], True)):
        with pytest.raises(ValueError):
            build_linked_tier_b_query(merchants, cap)


def write_eval_membership(path, rows):
    fields = ("provider", "account_id", "transaction_id", "customer_id", "role")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_eval_protection_excludes_exact_account_and_customer_groups(tmp_path):
    lookup = tmp_path / "eval.csv"
    write_eval_membership(
        lookup,
        [
            {
                "provider": "plaid",
                "account_id": "eval-account",
                "transaction_id": "eval-transaction",
                "customer_id": "eval-customer",
                "role": "eval",
            }
        ],
    )
    protection = builder.load_eval_protection([lookup])
    rows = [
        plaid_row("safe"),
        plaid_row("exact")
        | {
            "account_id": "eval-account",
            "transaction_id": "eval-transaction",
            "customer_id": "eval-customer",
        },
        plaid_row("same-account")
        | {"account_id": "eval-account", "customer_id": "eval-customer"},
        plaid_row("same-customer") | {"customer_id": "eval-customer"},
    ]
    retained, excluded = builder.exclude_eval_membership(rows, protection)
    assert retained == [plaid_row("safe")]
    assert excluded == {"exact_event": 1, "account_group": 1, "customer_group": 1}
    assert protection["inputs"][0]["rows"] == 1
    assert protection["inputs"][0]["sha256"] == __import__("hashlib").sha256(
        lookup.read_bytes()
    ).hexdigest()


@pytest.mark.parametrize(
    "row",
    [
        {
            "provider": "equifax",
            "account_id": "account",
            "transaction_id": "transaction",
            "customer_id": "customer",
            "role": "eval",
        },
        {
            "provider": "plaid",
            "account_id": "account",
            "transaction_id": "transaction",
            "customer_id": "customer",
            "role": "train",
        },
    ],
)
def test_eval_protection_rejects_out_of_scope_membership(tmp_path, row):
    lookup = tmp_path / "eval.csv"
    write_eval_membership(lookup, [row])
    with pytest.raises(ValueError, match="outside the protected scope"):
        builder.load_eval_protection([lookup])


@pytest.mark.parametrize(
    "text",
    [
        (
            "provider,account_id,transaction_id,customer_id,customer_id,role\n"
            "plaid,account,transaction,customer,shadow,eval\n"
        ),
        (
            "provider,account_id,transaction_id,customer_id,role\n"
            "plaid,   ,transaction,customer,eval\n"
        ),
        (
            "provider,account_id,transaction_id,customer_id,role\n"
            "plaid,account,transaction,customer,eval,extra\n"
        ),
    ],
)
def test_eval_protection_rejects_malformed_csv(tmp_path, text):
    lookup = tmp_path / "eval.csv"
    lookup.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError):
        builder.load_eval_protection([lookup])


def test_eval_protection_rejects_account_customer_contradiction(tmp_path):
    lookup = tmp_path / "eval.csv"
    write_eval_membership(
        lookup,
        [
            {
                "provider": "plaid",
                "account_id": "eval-account",
                "transaction_id": f"transaction-{index}",
                "customer_id": f"customer-{index}",
                "role": "eval",
            }
            for index in range(2)
        ],
    )
    with pytest.raises(ValueError, match="account crosses customer"):
        builder.load_eval_protection([lookup])


def test_fetched_account_customer_contradiction_fails_closed(tmp_path):
    lookup = tmp_path / "eval.csv"
    write_eval_membership(
        lookup,
        [
            {
                "provider": "plaid",
                "account_id": "eval-account",
                "transaction_id": "eval-transaction",
                "customer_id": "eval-customer",
                "role": "eval",
            }
        ],
    )
    protection = builder.load_eval_protection([lookup])
    with pytest.raises(ValueError, match="contradicts eval customer"):
        builder.exclude_eval_membership(
            [plaid_row("other") | {"account_id": "eval-account"}],
            protection,
        )


def test_tier_b_fetch_receipt_binds_eval_lookup_and_result(tmp_path):
    lookup = tmp_path / "eval.csv"
    write_eval_membership(
        lookup,
        [
            {
                "provider": "plaid",
                "account_id": "eval-account",
                "transaction_id": "eval-transaction",
                "customer_id": "eval-customer",
                "role": "eval",
            }
        ],
    )
    protection = builder.load_eval_protection([lookup])
    data_path = tmp_path / "txns.json"
    receipt_path = tmp_path / "receipt.json"
    builder.write_tier_b_fetch(
        [plaid_row("safe")],
        protection,
        data_path=data_path,
        receipt_path=receipt_path,
    )
    assert builder.read_verified_tier_b_fetch(
        [lookup],
        data_path=data_path,
        receipt_path=receipt_path,
    ) == [plaid_row("safe")]

    receipt = json.loads(receipt_path.read_text())
    receipt["eval_membership_inputs"] = [{"sha256": "not-a-hash", "rows": -1}]
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(ValueError, match="verified eval protection"):
        builder.read_verified_tier_b_fetch(
            [lookup],
            data_path=data_path,
            receipt_path=receipt_path,
        )

    builder.write_tier_b_fetch(
        [plaid_row("safe")],
        protection,
        data_path=data_path,
        receipt_path=receipt_path,
    )
    data_path.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="verified eval protection"):
        builder.read_verified_tier_b_fetch(
            [lookup],
            data_path=data_path,
            receipt_path=receipt_path,
        )

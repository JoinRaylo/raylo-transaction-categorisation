"""Synthetic tests for preparing the private 500-row annotation bundle."""

import csv
import hashlib
import json
import os
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
APP_ROOT = pathlib.Path(
    os.environ.get("TXNCAT_APP_WORKTREE", "/private/tmp/txncat-b03a-app-worktree")
)
sys.path.insert(0, str(ROOT / "tools" / "benchmark"))
sys.path.insert(0, str(APP_ROOT / "lib/raylo-txncat/src"))

from prepare_eval_annotation_bundle import (  # noqa: E402
    MEMBERSHIP_FIELDS,
    build_bundle,
    redact_obvious_identifiers,
)
from raylo_txncat.benchmark_annotation import PilotManifest  # noqa: E402


def digest_bytes(value):
    return hashlib.sha256(value).hexdigest()


def write_source(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    pilot_path = source / "pilot.jsonl"
    membership_path = source / "membership.csv"
    summary_path = source / "summary.json"
    rows = []
    memberships = []
    for index in range(500):
        primary = (
            "representative"
            if index < 250
            else "unseen_input"
            if index < 400
            else "unfamiliar_merchant"
        )
        views = ["representative"]
        if primary != "representative":
            views.append("unseen_input")
        if primary == "unfamiliar_merchant":
            views.append("unfamiliar_merchant")
        pilot_id = "pilot-v1-" + hashlib.sha256(f"item-{index}".encode()).hexdigest()
        row = {
            "schema_version": "txncat-private-eval-pilot-item-v1",
            "pilot_id": pilot_id,
            "primary_view": primary,
            "views": views,
            "merchant": "synthetic merchant",
            "description": (
                "contact person@example.com ref 123456789"
                if index == 0
                else "synthetic narrative"
            ),
            "amount": 12.34,
            "direction": "debit",
            "source_stratum": "synthetic",
        }
        rows.append(row)
        memberships.append(
            {
                "schema_version": "txncat-private-eval-membership-v1",
                "provider": "plaid",
                "account_id": f"account-{index}",
                "transaction_id": f"transaction-{index}",
                "customer_id": f"customer-{index}",
                "role": "eval",
                "primary_view": primary,
                "views": "+".join(views),
                "pilot_id": pilot_id,
                "source_snapshot_sha256": hashlib.sha256(b"snapshot").hexdigest(),
                "row_sha256": hashlib.sha256(
                    json.dumps(row, sort_keys=True).encode()
                ).hexdigest(),
            }
        )
    pilot_path.write_bytes(
        b"".join(
            json.dumps(row, sort_keys=True, separators=(",", ":")).encode() + b"\n"
            for row in rows
        )
    )
    with membership_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=tuple(MEMBERSHIP_FIELDS))
        writer.writeheader()
        writer.writerows(memberships)
    summary = {
        "pilot_rows": 500,
        "authorizes_consumption": False,
    }
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    receipt = {
        "schema_version": "txncat-private-eval-pilot-receipt-v1",
        "source_kind": "customer_linked_plaid_materialized",
        "anonymous_id_recovery": False,
        "authorizes_consumption": False,
        "pilot_rows": 500,
        "candidate_result_sha256": hashlib.sha256(b"snapshot").hexdigest(),
        "pilot_sha256": digest_bytes(pilot_path.read_bytes()),
        "membership_sha256": digest_bytes(membership_path.read_bytes()),
        "summary_sha256": digest_bytes(summary_path.read_bytes()),
    }
    (source / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
    return source


def write_taxonomy(tmp_path):
    path = tmp_path / "taxonomy.csv"
    fields = (
        "detailed_category",
        "general_category",
        "cash_flow_type",
        "equifax_source",
        "plaid_source",
        "notes",
    )
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(
            [
                {
                    "detailed_category": "groceries",
                    "general_category": "shopping",
                    "cash_flow_type": "expense",
                    "equifax_source": "Food",
                    "plaid_source": "FOOD_GROCERIES",
                    "notes": "Synthetic definition.",
                },
                {
                    "detailed_category": "unclassified_other",
                    "general_category": "unclassified",
                    "cash_flow_type": "unknown",
                    "equifax_source": "",
                    "plaid_source": "",
                    "notes": "Use only when no supported category fits.",
                },
            ]
        )
    return path


def test_obvious_identifier_redaction_is_local_and_counted():
    value, counts = redact_obvious_identifiers(
        "mail person@example.com call 07123 456789 ref 12345678"
    )
    assert "person@example.com" not in value
    assert "07123 456789" not in value
    assert "12345678" not in value
    assert sum(counts.values()) == 3


def test_build_bundle_produces_bound_real_manifest_without_source_ids(tmp_path):
    source = write_source(tmp_path)
    taxonomy = write_taxonomy(tmp_path)
    output = tmp_path / "annotation_method_experiment"
    receipt = build_bundle(
        app_root=APP_ROOT,
        pilot_dir=source,
        taxonomy_path=taxonomy,
        output=output,
    )
    manifest = PilotManifest.model_validate_json(
        (output / "manifest.json").read_bytes(), strict=True
    )
    prompts = [
        json.loads(line) for line in (output / "prompts.jsonl").read_text().splitlines()
    ]
    assert manifest.manifest_kind == "real_pilot"
    assert len(manifest.items) == len(prompts) == 500
    assert all(
        prompt["manifest_sha256"] == manifest.manifest_sha256 for prompt in prompts
    )
    assert all(
        not any(
            field in prompt for field in ("account_id", "transaction_id", "customer_id")
        )
        for prompt in prompts
    )
    assert "person@example.com" not in prompts[0]["prompt"]
    assert receipt["obvious_identifier_redactions"]["email"] == 1
    assert receipt["explicit_source_identity_fields"] == 0
    assert output.stat().st_mode & 0o777 == 0o700
    assert all(path.stat().st_mode & 0o777 == 0o600 for path in output.iterdir())


def test_changed_source_pilot_fails_receipt_verification(tmp_path):
    source = write_source(tmp_path)
    with (source / "pilot.jsonl").open("ab") as stream:
        stream.write(b"{}\n")
    with pytest.raises(ValueError, match="source pilot receipt"):
        build_bundle(
            app_root=APP_ROOT,
            pilot_dir=source,
            taxonomy_path=write_taxonomy(tmp_path),
            output=tmp_path / "annotation_method_experiment",
        )

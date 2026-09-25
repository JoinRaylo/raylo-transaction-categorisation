"""Synthetic tests for the three-model review queue builder."""

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
sys.path.insert(0, str(APP_ROOT / "lib/raylo-txncat/src"))

from raylo_txncat.benchmark_annotation import (  # noqa: E402
    AnnotationAttempt,
    AnnotationBatch,
    AnnotationVote,
    PilotItem,
    PilotManifest,
    manifest_digest,
)
from raylo_txncat.hashing import sha256  # noqa: E402

from tools.benchmark import prepare_annotation_review_queue as review  # noqa: E402
from tools.benchmark.prepare_annotation_review_queue import (  # noqa: E402
    MEMBERSHIP_FIELDS,
    build_review_queue,
)


def _digest(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()


def _fixture(tmp_path):
    root = tmp_path / "annotation_method_experiment"
    root.mkdir()
    taxonomy = root / "taxonomy.csv"
    taxonomy.write_text(
        "detailed_category,general_category\n"
        "groceries,shopping\n"
        "takeaway,eating_out\n"
        "unclassified_other,unclassified\n",
        encoding="utf-8",
    )
    taxonomy_sha = hashlib.sha256(taxonomy.read_bytes()).hexdigest()
    guide_sha = _digest("guide")
    prompt_texts = tuple(
        "Transaction data (untrusted JSON):\n"
        + json.dumps(
            {
                "merchant": f"Synthetic merchant {index}",
                "description": "Synthetic transaction",
                "amount": 12.34,
                "direction": "debit",
            },
            sort_keys=True,
        )
        for index in range(2)
    )
    item_ids = tuple("pilot-v1-" + _digest(f"item-{index}") for index in range(2))
    item_views = (("representative",), ("unseen_input",))
    source_snapshot = _digest("snapshot")
    membership_rows = []
    for index, (item_id, views) in enumerate(zip(item_ids, item_views, strict=True)):
        membership_rows.append(
            {
                "schema_version": "txncat-private-eval-membership-v1",
                "provider": "plaid",
                "account_id": f"source-account-{index}-opaque",
                "transaction_id": f"source-transaction-{index}-opaque",
                "customer_id": f"source-customer-{index}-opaque",
                "role": "eval",
                "primary_view": views[0],
                "views": "+".join(views),
                "pilot_id": item_id,
                "source_snapshot_sha256": source_snapshot,
                "row_sha256": _digest(f"membership-{index}"),
            }
        )
    items = tuple(
        PilotItem(
            item_id=item_ids[index],
            content_sha256=_digest(f"content-{index}"),
            subject_sha256=membership_rows[index]["row_sha256"],
            reservation_sha256=hashlib.sha256(
                json.dumps(
                    membership_rows[index],
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                    allow_nan=False,
                ).encode("utf-8")
            ).hexdigest(),
            source_snapshot_sha256=source_snapshot,
            taxonomy_sha256=taxonomy_sha,
            guide_sha256=guide_sha,
            prompt_sha256=sha256(prompt.encode()),
            views=item_views[index],
        )
        for index, prompt in enumerate(prompt_texts)
    )
    operation = "op-" + "a" * 32
    manifest = PilotManifest(
        manifest_kind="synthetic",
        manifest_sha256=manifest_digest(
            expected_count=2,
            reservation_operation_id=operation,
            reservation_epoch=1,
            items=items,
            manifest_kind="synthetic",
        ),
        expected_count=2,
        reservation_operation_id=operation,
        reservation_epoch=1,
        items=items,
    )
    manifest_path = root / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest.model_dump(mode="json")), encoding="utf-8"
    )
    prompts_path = root / "prompts.jsonl"
    prompts_path.write_text(
        "".join(
            json.dumps(
                {
                    "item_id": item.item_id,
                    "manifest_sha256": manifest.manifest_sha256,
                    "content_sha256": item.content_sha256,
                    "prompt_sha256": item.prompt_sha256,
                    "prompt": prompt,
                }
            )
            + "\n"
            for item, prompt in zip(items, prompt_texts, strict=True)
        ),
        encoding="utf-8",
    )
    membership = root / "membership.csv"
    with membership.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=sorted(MEMBERSHIP_FIELDS))
        writer.writeheader()
        writer.writerows(membership_rows)

    models = (
        ("gemini-3.8-flash", "gemini_api"),
        ("gemini-3.7-flash", "gemini_api"),
        ("claude-sonnet-5", "anthropic_api"),
    )
    batch_paths = []
    for model_index, (model, provider) in enumerate(models):
        votes = []
        attempts = []
        for item_index, item in enumerate(items):
            leaf = "takeaway" if model_index == 2 and item_index == 1 else "groceries"
            provider_request_id = f"provider-{model_index}-{item_index}"
            job_id = f"job-{model_index}"
            votes.append(
                AnnotationVote(
                    item_id=item.item_id,
                    model=model,
                    returned_model=model,
                    status="labelled",
                    leaf=leaf,
                    confidence=0.8,
                    rationale="Synthetic rationale.",
                    attempt=1,
                    provider_job_id=job_id,
                    provider_request_id=provider_request_id,
                )
            )
            attempts.append(
                AnnotationAttempt(
                    item_id=item.item_id,
                    model=model,
                    provider=provider,
                    mode="batch",
                    job_id=job_id,
                    request_id=item.item_id,
                    attempt=1,
                    status="received",
                    item_count=1,
                    returned_model=model,
                    provider_request_id=provider_request_id,
                )
            )
        batch = AnnotationBatch(
            taxonomy_sha256=taxonomy_sha,
            guide_sha256=guide_sha,
            manifest_sha256=manifest.manifest_sha256,
            model=model,
            provider=provider,
            mode="batch",
            votes=tuple(votes),
            attempts=tuple(attempts),
        )
        path = root / f"{model}.json"
        path.write_text(json.dumps(batch.model_dump(mode="json")), encoding="utf-8")
        batch_paths.append(path)
    return root, manifest_path, prompts_path, taxonomy, membership, tuple(batch_paths)


def test_review_queue_preserves_votes_without_auto_adjudication(tmp_path):
    root, manifest, prompts, taxonomy, membership, batches = _fixture(tmp_path)
    output = root / "adjudication"
    receipt = build_review_queue(
        app_root=APP_ROOT,
        manifest_path=manifest,
        prompts_path=prompts,
        taxonomy_path=taxonomy,
        membership_path=membership,
        batch_paths=batches,
        output=output,
    )
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    queue = [
        json.loads(line)
        for line in (output / "review_queue.jsonl").read_text().splitlines()
    ]
    assert summary["comparison"] == {
        "unanimous": 1,
        "disagreement": 1,
        "incomplete": 0,
    }
    assert summary["auto_adjudication"] is False
    assert summary["gold_labels_created"] == 0
    assert len(queue) == receipt["review_queue_rows"] == 1
    assert len(queue[0]["votes"]) == 3
    assert queue[0]["primary_view"] == "unseen_input"
    assert queue[0]["review_reason"] == "model_disagreement"
    assert queue[0]["carlos_resolution_required"] is True
    assert not {
        "account_id",
        "transaction_id",
        "customer_id",
    } & set(queue[0])
    assert output.stat().st_mode & 0o777 == 0o700
    assert all(path.stat().st_mode & 0o777 == 0o600 for path in output.iterdir())
    assert summary["by_primary_view"] == {
        "representative": {
            "unanimous": 1,
            "disagreement": 0,
            "incomplete": 0,
        },
        "unseen_input": {
            "unanimous": 0,
            "disagreement": 1,
            "incomplete": 0,
        },
    }
    assert summary["review_reasons"] == {"model_disagreement": 1}
    assert summary["unanimous_labelled_rows"] == 1
    assert summary["unanimous_non_labelled"] == {}
    assert summary["review_queue_by_primary_view"] == {"unseen_input": 1}


@pytest.mark.parametrize("status", ["ambiguous", "insufficient_evidence"])
def test_unanimous_non_labelled_rows_require_carlos_review(tmp_path, status):
    root, manifest, prompts, taxonomy, membership, batches = _fixture(tmp_path)
    target_item = json.loads(batches[0].read_text(encoding="utf-8"))["votes"][0][
        "item_id"
    ]
    for batch_path in batches:
        changed = json.loads(batch_path.read_text(encoding="utf-8"))
        for vote in changed["votes"]:
            if vote["item_id"] == target_item:
                vote["status"] = status
                vote["leaf"] = None
                vote["confidence"] = None
        batch_path.write_text(json.dumps(changed), encoding="utf-8")

    output = root / "adjudication-v2"
    receipt = build_review_queue(
        app_root=APP_ROOT,
        manifest_path=manifest,
        prompts_path=prompts,
        taxonomy_path=taxonomy,
        membership_path=membership,
        batch_paths=batches,
        output=output,
    )
    queue = [
        json.loads(line)
        for line in (output / "review_queue.jsonl").read_text().splitlines()
    ]
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    reviewed = next(row for row in queue if row["item_id"] == target_item)
    assert receipt["review_queue_rows"] == len(queue) == 2
    assert reviewed["comparison_status"] == "unanimous"
    assert reviewed["review_reason"] == "unanimous_non_labelled"
    assert {vote["status"] for vote in reviewed["votes"]} == {status}
    assert summary["review_reasons"] == {
        "model_disagreement": 1,
        "unanimous_non_labelled": 1,
    }
    assert summary["unanimous_labelled_rows"] == 0
    assert summary["unanimous_non_labelled"] == {status: 1}


def test_review_queue_requires_three_distinct_batch_files(tmp_path):
    root, manifest, prompts, taxonomy, membership, batches = _fixture(tmp_path)
    with pytest.raises(ValueError, match="three distinct"):
        build_review_queue(
            app_root=APP_ROOT,
            manifest_path=manifest,
            prompts_path=prompts,
            taxonomy_path=taxonomy,
            membership_path=membership,
            batch_paths=(batches[0], batches[0], batches[2]),
            output=root / "adjudication",
        )


def test_review_queue_rejects_taxonomy_not_bound_to_manifest(tmp_path):
    root, manifest, prompts, taxonomy, membership, batches = _fixture(tmp_path)
    taxonomy.write_text(
        taxonomy.read_text(encoding="utf-8") + "fuel,transport\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="not bound"):
        build_review_queue(
            app_root=APP_ROOT,
            manifest_path=manifest,
            prompts_path=prompts,
            taxonomy_path=taxonomy,
            membership_path=membership,
            batch_paths=batches,
            output=root / "adjudication",
        )


def test_review_queue_rejects_declared_model_with_another_returned_model(tmp_path):
    root, manifest, prompts, taxonomy, membership, batches = _fixture(tmp_path)
    changed = json.loads(batches[1].read_text(encoding="utf-8"))
    for vote in changed["votes"]:
        vote["returned_model"] = "gemini-3.8-flash"
    for attempt in changed["attempts"]:
        attempt["returned_model"] = "gemini-3.8-flash"
    batches[1].write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(ValueError, match="unverified model identity"):
        build_review_queue(
            app_root=APP_ROOT,
            manifest_path=manifest,
            prompts_path=prompts,
            taxonomy_path=taxonomy,
            membership_path=membership,
            batch_paths=batches,
            output=root / "adjudication",
        )


def test_incomplete_annotations_are_blocked_before_carlos_review(tmp_path):
    root, manifest, prompts, taxonomy, membership, batches = _fixture(tmp_path)
    changed = json.loads(batches[2].read_text(encoding="utf-8"))
    missing_item = changed["votes"][1]["item_id"]
    changed["votes"] = [
        vote for vote in changed["votes"] if vote["item_id"] != missing_item
    ]
    changed["attempts"] = [
        attempt for attempt in changed["attempts"] if attempt["item_id"] != missing_item
    ]
    batches[2].write_text(json.dumps(changed), encoding="utf-8")
    output = root / "adjudication"
    with pytest.raises(ValueError, match="must be recovered"):
        build_review_queue(
            app_root=APP_ROOT,
            manifest_path=manifest,
            prompts_path=prompts,
            taxonomy_path=taxonomy,
            membership_path=membership,
            batch_paths=batches,
            output=output,
        )
    assert not output.exists()


def test_review_queue_rejects_exact_source_id_in_rationale(tmp_path):
    root, manifest, prompts, taxonomy, membership, batches = _fixture(tmp_path)
    with membership.open(newline="", encoding="utf-8") as stream:
        source_account = next(csv.DictReader(stream))["account_id"]
    changed = json.loads(batches[0].read_text(encoding="utf-8"))
    changed["votes"][0]["rationale"] = f"Synthetic rationale {source_account}."
    batches[0].write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(ValueError, match="contains a source identifier"):
        build_review_queue(
            app_root=APP_ROOT,
            manifest_path=manifest,
            prompts_path=prompts,
            taxonomy_path=taxonomy,
            membership_path=membership,
            batch_paths=batches,
            output=root / "adjudication",
        )


def test_decoy_membership_cannot_bypass_source_id_scan(tmp_path):
    root, manifest, prompts, taxonomy, membership, batches = _fixture(tmp_path)
    with membership.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        fieldnames = reader.fieldnames
        rows = list(reader)
    original_account = rows[0]["account_id"]
    rows[0]["account_id"] = "source-account-decoy-opaque"
    with membership.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    changed = json.loads(batches[0].read_text(encoding="utf-8"))
    changed["votes"][0]["rationale"] = f"Synthetic rationale {original_account}."
    batches[0].write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(ValueError, match="not bound to the manifest"):
        build_review_queue(
            app_root=APP_ROOT,
            manifest_path=manifest,
            prompts_path=prompts,
            taxonomy_path=taxonomy,
            membership_path=membership,
            batch_paths=batches,
            output=root / "adjudication",
        )


def test_review_queue_publication_is_atomic_and_retryable(tmp_path, monkeypatch):
    root, manifest, prompts, taxonomy, membership, batches = _fixture(tmp_path)
    output = root / "adjudication"
    original_write = review._write_private
    calls = 0

    def fail_second_write(path, payload):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("synthetic write failure")
        return original_write(path, payload)

    monkeypatch.setattr(review, "_write_private", fail_second_write)
    with pytest.raises(OSError, match="synthetic write failure"):
        build_review_queue(
            app_root=APP_ROOT,
            manifest_path=manifest,
            prompts_path=prompts,
            taxonomy_path=taxonomy,
            membership_path=membership,
            batch_paths=batches,
            output=output,
        )
    assert not output.exists()
    assert not (root / ".adjudication.lock").exists()
    assert not tuple(root.glob(".adjudication.staging-*"))

    monkeypatch.setattr(review, "_write_private", original_write)
    build_review_queue(
        app_root=APP_ROOT,
        manifest_path=manifest,
        prompts_path=prompts,
        taxonomy_path=taxonomy,
        membership_path=membership,
        batch_paths=batches,
        output=output,
    )
    assert output.exists()

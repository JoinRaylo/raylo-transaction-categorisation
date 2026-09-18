"""Synthetic adversarial tests for failed-item Gemini batch recovery."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

import pytest
from google.genai import types
from pydantic import ValidationError

APP_ROOT = Path(
    os.environ.get("TXNCAT_APP_WORKTREE", "/private/tmp/txncat-b03a-app-worktree")
)
sys.path.insert(0, str(APP_ROOT / "lib/raylo-txncat/src"))

from raylo_txncat.benchmark_annotation import (  # noqa: E402
    PilotItem,
    PilotManifest,
    manifest_digest,
    validate_batch,
)
from raylo_txncat.hashing import sha256, strict_json_loads  # noqa: E402

from tools.benchmark import annotation_pilot as pilot  # noqa: E402
from tools.benchmark import recover_gemini_annotation_batch as recovery  # noqa: E402


def _digest(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()


SYSTEM = "Synthetic guide"


def _fixture(*, failed_indices=(1,), invalid_leaf: str | None = None):
    canonical = pilot._load_canonical(APP_ROOT)
    items = []
    prompts = []
    for index in range(2):
        prompt_text = f"Synthetic transaction prompt {index}."
        item = PilotItem(
            item_id="pilot-v1-" + _digest(f"item-{index}"),
            content_sha256=_digest(f"content-{index}"),
            subject_sha256=_digest(f"subject-{index}"),
            reservation_sha256=_digest(f"reservation-{index}"),
            source_snapshot_sha256=_digest("snapshot"),
            taxonomy_sha256=_digest("taxonomy"),
            guide_sha256=_digest(SYSTEM),
            prompt_sha256=sha256(prompt_text.encode()),
            views=("representative",),
        )
        items.append(item)
    operation = "op-" + "a" * 32
    manifest = PilotManifest(
        manifest_kind="synthetic",
        manifest_sha256=manifest_digest(
            expected_count=len(items),
            reservation_operation_id=operation,
            reservation_epoch=1,
            items=tuple(items),
            manifest_kind="synthetic",
        ),
        expected_count=len(items),
        reservation_operation_id=operation,
        reservation_epoch=1,
        items=tuple(items),
    )
    for index, item in enumerate(items):
        prompt_text = f"Synthetic transaction prompt {index}."
        prompts.append(
            pilot.PrivatePrompt(
                item_id=item.item_id,
                manifest_sha256=manifest.manifest_sha256,
                content_sha256=item.content_sha256,
                prompt_sha256=sha256(prompt_text.encode()),
                prompt=prompt_text,
            )
        )

    attempts = []
    votes = []
    for index, item in enumerate(items):
        if index in failed_indices:
            attempts.append(
                canonical[0](
                    item_id=item.item_id,
                    model="gemini-3.8-flash",
                    provider="gemini_api",
                    mode="batch",
                    job_id="batch/base",
                    request_id=item.item_id,
                    attempt=1,
                    status="schema_failed",
                    item_count=1,
                    error_code="JSONDecodeError",
                )
            )
            continue
        provider_request_id = f"response-base-{index}"
        attempts.append(
            canonical[0](
                item_id=item.item_id,
                model="gemini-3.8-flash",
                provider="gemini_api",
                mode="batch",
                job_id="batch/base",
                request_id=item.item_id,
                attempt=1,
                status="received",
                item_count=1,
                returned_model="gemini-3.8-flash",
                provider_request_id=provider_request_id,
            )
        )
        votes.append(
            canonical[2](
                item_id=item.item_id,
                model="gemini-3.8-flash",
                returned_model="gemini-3.8-flash",
                status="labelled",
                leaf=invalid_leaf or "groceries",
                confidence=0.9,
                rationale="Synthetic first-attempt response.",
                attempt=1,
                provider_job_id="batch/base",
                provider_request_id=provider_request_id,
            )
        )
    base = canonical[1](
        taxonomy_sha256=_digest("taxonomy"),
        guide_sha256=_digest(SYSTEM),
        manifest_sha256=manifest.manifest_sha256,
        model="gemini-3.8-flash",
        provider="gemini_api",
        mode="batch",
        votes=tuple(votes),
        attempts=tuple(attempts),
    )
    base_raw = (
        json.dumps(
            base.model_dump(mode="json"),
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode()
    return canonical, manifest, tuple(prompts), base_raw, base


class _FakeBatches:
    def __init__(self, job):
        self.job = job
        self.created = None

    def create(self, **kwargs):
        self.created = kwargs
        return SimpleNamespace(name="batch/recovery")

    def get(self, *, name):
        assert name == "batch/recovery"
        return self.job


class _FakeClient:
    def __init__(self, job):
        self.batches = _FakeBatches(job)


def _state_path(tmp_path, canonical, manifest, prompts, base_raw, base, leaves):
    requests = recovery._recovery_requests(prompts, SYSTEM, leaves, types)
    serialized_bytes = recovery._serialized_inline_batch_bytes(
        "gemini-3.8-flash", requests
    )
    state = recovery._initial_state(
        manifest=manifest,
        prompts=prompts,
        model="gemini-3.8-flash",
        base_raw=base_raw,
        base_vote_count=len(base.votes),
        leaves=leaves,
        system=SYSTEM,
        serialized_request_bytes=serialized_bytes,
        canonical=canonical,
    )
    submitted = recovery.RecoveryState.model_validate(
        {
            **state.model_dump(mode="python"),
            "state": "submitted",
            "provider_job_id": "batch/recovery",
            "provider_status": "submitted",
        },
        strict=True,
    )
    path = tmp_path / "recovery-state.json"
    pilot._write_json(path, submitted.model_dump(mode="json"), exclusive=True)
    return path, submitted


def _result(item_id: str, *, leaf="groceries", returned_model="gemini-3.8-flash"):
    response = SimpleNamespace(
        text=json.dumps(
            {
                "status": "labelled",
                "leaf": leaf,
                "confidence": 0.8,
                "rationale": "Synthetic recovery response.",
            }
        ),
        model_version=returned_model,
        response_id="response-recovery",
        usage_metadata=None,
    )
    return SimpleNamespace(
        error=None,
        metadata={"item_id": item_id},
        response=response,
    )


def test_recovery_schema_enumerates_exact_taxonomy_and_bounds_confidence():
    schema = recovery._result_schema(frozenset({"utilities", "groceries"}))
    assert schema["additionalProperties"] is False
    assert schema["properties"]["status"]["enum"] == list(pilot.RESULT_STATUSES)
    assert schema["properties"]["leaf"]["anyOf"][0]["enum"] == [
        "groceries",
        "utilities",
    ]
    assert schema["properties"]["confidence"]["anyOf"][0] == {
        "type": "number",
        "minimum": 0,
        "maximum": 1,
    }


def test_recovery_requests_use_low_thinking_larger_ceiling_and_one_item_each():
    _, _, prompts, _, _ = _fixture()
    selected = (prompts[1],)
    requests = recovery._recovery_requests(
        selected,
        "Synthetic guide",
        frozenset({"groceries", "unclassified_other"}),
        types,
    )
    assert len(requests) == 1
    assert requests[0].metadata == {"item_id": prompts[1].item_id}
    assert requests[0].config.max_output_tokens == 4096
    assert requests[0].config.thinking_config.thinking_level == types.ThinkingLevel.LOW
    enum = requests[0].config.response_json_schema["properties"]["leaf"]["anyOf"][0][
        "enum"
    ]
    assert enum == ["groceries", "unclassified_other"]


def test_inline_size_measurement_uses_actual_sdk_unicode_wire_encoding():
    content = "é" * 2_000
    requests = [
        types.InlinedRequest(
            contents=content,
            metadata={"item_id": "pilot-v1-" + "a" * 64},
            config=types.GenerateContentConfig(max_output_tokens=4096),
        )
    ]
    wire_bytes = recovery._serialized_inline_batch_bytes("gemini-3.8-flash", requests)
    assert wire_bytes > len(content.encode("utf-8")) * 2
    assert recovery.INLINE_BATCH_SAFE_LIMIT_BYTES < (
        recovery.INLINE_BATCH_PROVIDER_LIMIT_BYTES
    )


def test_base_validation_and_selection_retry_only_failed_items():
    _, manifest, prompts, _, base = _fixture()
    leaves = frozenset({"groceries", "unclassified_other"})
    failed = recovery._validate_base_output(
        base, manifest=manifest, model="gemini-3.8-flash", leaves=leaves
    )
    assert failed == frozenset({manifest.items[1].item_id})
    selected = recovery._select_failed_prompts(prompts, manifest, failed)
    assert [prompt.item_id for prompt in selected] == [manifest.items[1].item_id]


def test_complete_base_is_never_resubmitted():
    _, manifest, _, _, base = _fixture(failed_indices=())
    with pytest.raises(ValueError, match="already complete"):
        recovery._validate_base_output(
            base,
            manifest=manifest,
            model="gemini-3.8-flash",
            leaves=frozenset({"groceries", "unclassified_other"}),
        )


def test_base_with_unknown_taxonomy_leaf_is_rejected_before_submission():
    _, manifest, _, _, base = _fixture(
        failed_indices=(1,), invalid_leaf="invented_leaf"
    )
    with pytest.raises(ValueError, match="unknown taxonomy leaf"):
        recovery._validate_base_output(
            base,
            manifest=manifest,
            model="gemini-3.8-flash",
            leaves=frozenset({"groceries", "unclassified_other"}),
        )


def test_recovery_state_binds_base_failed_set_and_generation_contract(monkeypatch):
    canonical, manifest, prompts, base_raw, base = _fixture()
    leaves = frozenset({"groceries", "unclassified_other"})
    selected = (prompts[1],)
    state = recovery._initial_state(
        manifest=manifest,
        prompts=selected,
        model="gemini-3.8-flash",
        base_raw=base_raw,
        base_vote_count=len(base.votes),
        leaves=leaves,
        system=SYSTEM,
        serialized_request_bytes=recovery._serialized_inline_batch_bytes(
            "gemini-3.8-flash",
            recovery._recovery_requests(selected, SYSTEM, leaves, types),
        ),
        canonical=canonical,
    )
    assert state.request_count == 1
    assert state.base_vote_count == 1
    assert state.base_vote_count + state.request_count == state.manifest_item_count
    assert state.thinking_level == "low"
    assert state.max_output_tokens == 4096
    assert state.serialized_request_bytes > 0
    with pytest.raises(ValidationError, match="do not reconcile"):
        recovery.RecoveryState.model_validate(
            {**state.model_dump(mode="python"), "base_vote_count": 0}, strict=True
        )
    with pytest.raises(ValueError, match="immutable inputs"):
        recovery._validate_state_binding(
            state,
            manifest=manifest,
            prompts=selected,
            model="gemini-3.8-flash",
            base_raw=base_raw + b"changed",
            base_vote_count=len(base.votes),
            leaves=leaves,
            system=SYSTEM,
            serialized_request_bytes=state.serialized_request_bytes,
            canonical=canonical,
        )
    original_prompt = pilot._prompt
    monkeypatch.setattr(
        pilot,
        "_prompt",
        lambda item: "Changed wrapper.\n\n" + item.prompt,
    )
    with pytest.raises(ValueError, match="immutable inputs"):
        recovery._validate_state_binding(
            state,
            manifest=manifest,
            prompts=selected,
            model="gemini-3.8-flash",
            base_raw=base_raw,
            base_vote_count=len(base.votes),
            leaves=leaves,
            system=SYSTEM,
            serialized_request_bytes=state.serialized_request_bytes,
            canonical=canonical,
        )
    monkeypatch.setattr(pilot, "_prompt", original_prompt)


def test_submit_creates_only_failed_item_request_and_refuses_overwrite(
    tmp_path, monkeypatch
):
    canonical, manifest, prompts, base_raw, base = _fixture()
    leaves = frozenset({"groceries", "unclassified_other"})
    selected = (prompts[1],)
    client = _FakeClient(SimpleNamespace())
    monkeypatch.setattr(pilot, "_clients", lambda args, provider: (client, types))
    root = tmp_path / "annotation_method_experiment"
    args = Namespace(
        model="gemini-3.8-flash",
        experiment_root=root,
        job_state=(
            root
            / "jobs"
            / f"gemini-3.8-flash-recovery-a2-{manifest.manifest_sha256[:16]}.json"
        ),
    )
    requests = recovery._recovery_requests(selected, SYSTEM, leaves, types)
    serialized_bytes = recovery._serialized_inline_batch_bytes(args.model, requests)
    recovery._submit(
        args,
        selected,
        requests,
        serialized_bytes,
        SYSTEM,
        leaves,
        manifest,
        base_raw,
        base,
        canonical,
    )
    assert len(client.batches.created["src"]) == 1
    assert client.batches.created["src"][0].metadata == {"item_id": prompts[1].item_id}
    state = recovery._load_state(args.job_state, strict_json_loads)
    assert state.state == "submitted"
    with pytest.raises(ValueError, match="refusing to overwrite"):
        recovery._submit(
            args,
            selected,
            requests,
            serialized_bytes,
            SYSTEM,
            leaves,
            manifest,
            base_raw,
            base,
            canonical,
        )


def test_alternate_state_filename_cannot_duplicate_submission(tmp_path, monkeypatch):
    canonical, manifest, prompts, base_raw, base = _fixture()
    leaves = frozenset({"groceries", "unclassified_other"})
    selected = (prompts[1],)
    requests = recovery._recovery_requests(selected, SYSTEM, leaves, types)
    serialized_bytes = recovery._serialized_inline_batch_bytes(
        "gemini-3.8-flash", requests
    )
    client = _FakeClient(SimpleNamespace())
    monkeypatch.setattr(pilot, "_clients", lambda args, provider: (client, types))
    root = tmp_path / "annotation_method_experiment"
    args = Namespace(
        model="gemini-3.8-flash",
        experiment_root=root,
        job_state=root / "jobs" / "alternate.json",
    )
    with pytest.raises(ValueError, match="canonical manifest/model attempt marker"):
        recovery._submit(
            args,
            selected,
            requests,
            serialized_bytes,
            SYSTEM,
            leaves,
            manifest,
            base_raw,
            base,
            canonical,
        )
    assert client.batches.created is None


def test_oversized_inline_batch_is_rejected_before_state_or_transport(
    tmp_path, monkeypatch
):
    canonical, manifest, prompts, base_raw, base = _fixture()
    leaves = frozenset({"groceries", "unclassified_other"})
    selected = (prompts[1],)
    requests = recovery._recovery_requests(selected, SYSTEM, leaves, types)
    client = _FakeClient(SimpleNamespace())
    monkeypatch.setattr(pilot, "_clients", lambda args, provider: (client, types))
    root = tmp_path / "annotation_method_experiment"
    args = Namespace(
        model="gemini-3.8-flash",
        experiment_root=root,
        job_state=(
            root
            / "jobs"
            / f"gemini-3.8-flash-recovery-a2-{manifest.manifest_sha256[:16]}.json"
        ),
    )
    with pytest.raises(ValueError, match="inline request size limit"):
        recovery._submit(
            args,
            selected,
            requests,
            recovery.INLINE_BATCH_SAFE_LIMIT_BYTES + 1,
            SYSTEM,
            leaves,
            manifest,
            base_raw,
            base,
            canonical,
        )
    assert not args.job_state.exists()
    assert client.batches.created is None


def test_collect_preserves_first_attempt_and_merges_only_recovery_vote(
    tmp_path, monkeypatch
):
    canonical, manifest, prompts, base_raw, base = _fixture()
    leaves = frozenset({"groceries", "unclassified_other"})
    selected = (prompts[1],)
    job = SimpleNamespace(
        state=SimpleNamespace(value="JOB_STATE_SUCCEEDED"),
        dest=SimpleNamespace(inlined_responses=[_result(prompts[1].item_id)]),
    )
    client = _FakeClient(job)
    monkeypatch.setattr(pilot, "_clients", lambda args, provider: (client, types))
    state_path, state = _state_path(
        tmp_path, canonical, manifest, selected, base_raw, base, leaves
    )
    output = tmp_path / "recovery-output.json"
    merged_output = tmp_path / "merged-output.json"
    args = Namespace(
        model="gemini-3.8-flash",
        job_state=state_path,
        output=output,
        merged_output=merged_output,
    )
    recovery._collect(
        args,
        selected,
        leaves,
        manifest,
        base_raw,
        base,
        state,
        canonical,
    )
    recovery_batch = canonical[1].model_validate_json(output.read_bytes(), strict=True)
    merged = canonical[1].model_validate_json(merged_output.read_bytes(), strict=True)
    assert len(recovery_batch.votes) == 1
    assert recovery_batch.votes[0].item_id == prompts[1].item_id
    assert recovery_batch.votes[0].attempt == 2
    assert len(merged.votes) == 2
    attempt_evidence = [
        (attempt.item_id, attempt.attempt, attempt.status)
        for attempt in merged.attempts
    ]
    assert attempt_evidence == [
        (prompts[0].item_id, 1, "received"),
        (prompts[1].item_id, 1, "schema_failed"),
        (prompts[1].item_id, 2, "received"),
    ]
    validate_batch(manifest, merged)
    assert recovery._load_state(state_path, strict_json_loads).state == "collected"
    assert recovery._sha256(base_raw) == state.base_output_sha256


def test_unknown_recovery_leaf_remains_failed_and_never_becomes_a_vote(
    tmp_path, monkeypatch
):
    canonical, manifest, prompts, base_raw, base = _fixture()
    leaves = frozenset({"groceries", "unclassified_other"})
    selected = (prompts[1],)
    job = SimpleNamespace(
        state=SimpleNamespace(value="JOB_STATE_SUCCEEDED"),
        dest=SimpleNamespace(
            inlined_responses=[_result(prompts[1].item_id, leaf="invented_leaf")]
        ),
    )
    monkeypatch.setattr(
        pilot, "_clients", lambda args, provider: (_FakeClient(job), types)
    )
    state_path, state = _state_path(
        tmp_path, canonical, manifest, selected, base_raw, base, leaves
    )
    args = Namespace(
        model="gemini-3.8-flash",
        job_state=state_path,
        output=tmp_path / "recovery-output.json",
        merged_output=tmp_path / "merged-output.json",
    )
    recovery._collect(
        args,
        selected,
        leaves,
        manifest,
        base_raw,
        base,
        state,
        canonical,
    )
    recovered = canonical[1].model_validate_json(args.output.read_bytes(), strict=True)
    merged = canonical[1].model_validate_json(
        args.merged_output.read_bytes(), strict=True
    )
    assert recovered.votes == ()
    assert recovered.attempts[0].status == "schema_failed"
    assert merged.votes == base.votes
    assert recovery._load_state(state_path, strict_json_loads).state == (
        "collected_incomplete"
    )


def test_provider_cannot_return_a_successful_item_in_recovery(tmp_path, monkeypatch):
    canonical, manifest, prompts, base_raw, base = _fixture()
    leaves = frozenset({"groceries", "unclassified_other"})
    selected = (prompts[1],)
    job = SimpleNamespace(
        state=SimpleNamespace(value="JOB_STATE_SUCCEEDED"),
        dest=SimpleNamespace(
            inlined_responses=[
                _result(prompts[1].item_id),
                _result(prompts[0].item_id),
            ]
        ),
    )
    monkeypatch.setattr(
        pilot, "_clients", lambda args, provider: (_FakeClient(job), types)
    )
    state_path, state = _state_path(
        tmp_path, canonical, manifest, selected, base_raw, base, leaves
    )
    args = Namespace(
        model="gemini-3.8-flash",
        job_state=state_path,
        output=tmp_path / "recovery-output.json",
        merged_output=tmp_path / "merged-output.json",
    )
    with pytest.raises(ValueError, match="unknown item ID"):
        recovery._collect(
            args,
            selected,
            leaves,
            manifest,
            base_raw,
            base,
            state,
            canonical,
        )
    assert not args.output.exists()
    assert not args.merged_output.exists()


def test_recovery_paths_cannot_alias_or_escape_quarantine(tmp_path):
    root = tmp_path / "annotation_method_experiment"
    args = Namespace(
        experiment_root=root,
        base_output=root / "outputs" / "base.json",
        output=root / "outputs" / "recovery.json",
        merged_output=root / "outputs" / "merged.json",
        job_state=root / "jobs" / "recovery.json",
        bundle_receipt=root / "receipt.json",
    )
    recovery._validate_paths(args)
    args.merged_output = args.base_output
    with pytest.raises(ValueError, match="must be distinct"):
        recovery._validate_paths(args)
    args.merged_output = tmp_path / "training" / "escaped.json"
    with pytest.raises(ValueError, match="under experiment root"):
        recovery._validate_paths(args)

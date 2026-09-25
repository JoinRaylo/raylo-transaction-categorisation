"""Synthetic adversarial tests for the gated Gemini attempt-3 retry."""

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
from tools.benchmark import gemini_schema_acceptance as acceptance  # noqa: E402
from tools.benchmark import recover_gemini_annotation_batch as recovery  # noqa: E402


def _digest(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()


SYSTEM = "Synthetic guide using a detailed_category taxonomy field."
LEAVES = frozenset({"groceries", "utilities", "unclassified_other"})


def _attempt3_fixture():
    canonical = pilot._load_canonical(APP_ROOT)
    items = []
    prompts = []
    for index in range(3):
        prompt_text = f"Synthetic transaction prompt {index}."
        item = PilotItem(
            item_id="pilot-v1-" + _digest(f"a3-item-{index}"),
            content_sha256=_digest(f"a3-content-{index}"),
            subject_sha256=_digest(f"a3-subject-{index}"),
            reservation_sha256=_digest(f"a3-reservation-{index}"),
            source_snapshot_sha256=_digest("a3-snapshot"),
            taxonomy_sha256=_digest("a3-taxonomy"),
            guide_sha256=_digest(SYSTEM),
            prompt_sha256=sha256(prompt_text.encode()),
            views=("representative",),
        )
        items.append(item)
    operation = "op-" + "b" * 32
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
        if index == 0:
            attempts.append(
                canonical[0](
                    item_id=item.item_id,
                    model="gemini-3.8-flash",
                    provider="gemini_api",
                    mode="batch",
                    job_id="batch/original",
                    request_id=item.item_id,
                    attempt=1,
                    status="received",
                    item_count=1,
                    returned_model="gemini-3.8-flash",
                    provider_request_id="response-original",
                )
            )
            votes.append(
                canonical[2](
                    item_id=item.item_id,
                    model="gemini-3.8-flash",
                    returned_model="gemini-3.8-flash",
                    status="labelled",
                    leaf="groceries",
                    confidence=0.9,
                    rationale="Synthetic original response.",
                    attempt=1,
                    provider_job_id="batch/original",
                    provider_request_id="response-original",
                )
            )
            continue
        attempts.append(
            canonical[0](
                item_id=item.item_id,
                model="gemini-3.8-flash",
                provider="gemini_api",
                mode="batch",
                job_id="batch/original",
                request_id=item.item_id,
                attempt=1,
                status="schema_failed",
                item_count=1,
                error_code="ValueError",
            )
        )
        attempts.append(
            canonical[0](
                item_id=item.item_id,
                model="gemini-3.8-flash",
                provider="gemini_api",
                mode="batch",
                job_id="batch/recovery-a2",
                request_id=item.item_id,
                attempt=2,
                status=("received" if index == 1 else "schema_failed"),
                item_count=1,
                returned_model=("gemini-3.8-flash" if index == 1 else None),
                provider_request_id=("response-a2" if index == 1 else None),
                error_code=(None if index == 1 else "ValueError"),
            )
        )
        if index == 1:
            votes.append(
                canonical[2](
                    item_id=item.item_id,
                    model="gemini-3.8-flash",
                    returned_model="gemini-3.8-flash",
                    status="ambiguous",
                    leaf=None,
                    confidence=None,
                    rationale="Synthetic attempt-2 response.",
                    attempt=2,
                    provider_job_id="batch/recovery-a2",
                    provider_request_id="response-a2",
                )
            )
    base = canonical[1](
        taxonomy_sha256=_digest("a3-taxonomy"),
        guide_sha256=_digest(SYSTEM),
        manifest_sha256=manifest.manifest_sha256,
        model="gemini-3.8-flash",
        provider="gemini_api",
        mode="batch",
        votes=tuple(votes),
        attempts=tuple(attempts),
    )
    raw = (
        json.dumps(base.model_dump(mode="json"), sort_keys=True, allow_nan=False) + "\n"
    ).encode()
    return canonical, manifest, tuple(prompts), raw, base


def _binding(canonical):
    return acceptance._expected_binding(
        model="gemini-3.8-flash",
        system=SYSTEM,
        leaves=LEAVES,
        canonical=canonical,
    )


def _parent_raws(canonical, base):
    original = canonical[1](
        **{
            **base.model_dump(mode="python"),
            "votes": tuple(vote for vote in base.votes if vote.attempt == 1),
            "attempts": tuple(
                attempt for attempt in base.attempts if attempt.attempt == 1
            ),
        }
    )
    prior_recovery = canonical[1](
        **{
            **base.model_dump(mode="python"),
            "votes": tuple(vote for vote in base.votes if vote.attempt == 2),
            "attempts": tuple(
                attempt for attempt in base.attempts if attempt.attempt == 2
            ),
        }
    )
    return (
        (json.dumps(original.model_dump(mode="json"), sort_keys=True) + "\n").encode(),
        (
            json.dumps(prior_recovery.model_dump(mode="json"), sort_keys=True) + "\n"
        ).encode(),
    )


def _passing_gate(tmp_path, canonical):
    binding = _binding(canonical)
    state_path, receipt_path = acceptance._canonical_paths(
        tmp_path,
        "gemini-3.8-flash",
        str(binding["test_suite_sha256"]),
        str(binding["response_schema_sha256"]),
        str(binding["request_payload_sha256"]),
    )
    state = acceptance.AcceptanceState(
        **binding,
        serialized_request_bytes=1000,
        state="collected_passed",
        provider_job_id="batches/synthetic-gate",
        provider_status="JOB_STATE_SUCCEEDED",
        results_sha256=_digest("synthetic-results"),
        valid_count=len(acceptance.ACCEPTANCE_CASES),
        failed_count=0,
        returned_models=("gemini-3.8-flash",),
    )
    receipt = acceptance.AcceptanceReceipt(
        **binding,
        accepted=True,
        provider_job_id=state.provider_job_id,
        provider_status=state.provider_status,
        results_sha256=state.results_sha256,
        valid_count=state.valid_count,
        failed_count=state.failed_count,
        returned_models=state.returned_models,
    )
    pilot._write_json(state_path, state.model_dump(mode="json"), exclusive=True)
    pilot._write_json(receipt_path, receipt.model_dump(mode="json"), exclusive=True)
    return state_path, receipt_path


def _provider_result(item_id: str):
    part = SimpleNamespace(
        text=json.dumps(
            {
                "status": "labelled",
                "leaf": "utilities",
                "confidence": 0.8,
                "rationale": "Synthetic attempt-3 response.",
            }
        ),
        thought=False,
    )
    response = SimpleNamespace(
        text=part.text,
        model_version="gemini-3.8-flash",
        response_id="response-a3",
        usage_metadata=None,
        candidates=[
            SimpleNamespace(
                finish_reason="STOP",
                content=SimpleNamespace(parts=[part]),
            )
        ],
    )
    return SimpleNamespace(
        error=None,
        metadata={"item_id": item_id},
        response=response,
    )


class _FakeBatches:
    def __init__(self, job):
        self.job = job

    def get(self, *, name):
        assert name == "batch/recovery-a3"
        return self.job


class _FakeClient:
    def __init__(self, job):
        self.batches = _FakeBatches(job)


def test_attempt3_schema_and_instructions_forbid_alternate_field_names():
    schema = recovery._result_schema(LEAVES, recovery_attempt=3)
    assert schema["additionalProperties"] is False
    assert "detailed_category" in schema["properties"]["leaf"]["description"]
    assert "rationale" in schema["properties"]["rationale"]["description"]
    effective = recovery._effective_system(SYSTEM, recovery_attempt=3)
    assert effective.startswith(SYSTEM)
    assert "exactly these four keys" in effective
    assert "Never emit detailed_category" in effective


def test_attempt3_base_validation_preserves_success_and_retries_only_last_failure():
    _, manifest, prompts, _, base = _attempt3_fixture()
    failed = recovery._validate_base_output(
        base,
        manifest=manifest,
        model="gemini-3.8-flash",
        leaves=LEAVES,
        recovery_attempt=3,
    )
    assert failed == frozenset({manifest.items[2].item_id})
    selected = recovery._select_failed_prompts(prompts, manifest, failed)
    assert [row.item_id for row in selected] == [manifest.items[2].item_id]
    assert [vote.item_id for vote in base.votes] == [
        manifest.items[0].item_id,
        manifest.items[1].item_id,
    ]


def test_attempt3_base_must_exactly_match_parent_artifacts():
    canonical, manifest, _, _, base = _attempt3_fixture()
    original_raw, recovery_raw = _parent_raws(canonical, base)
    original_digest, recovery_digest = recovery._validate_parent_artifacts(
        base=base,
        original_raw=original_raw,
        recovery_raw=recovery_raw,
        annotation_batch=canonical[1],
        strict_json_loads=strict_json_loads,
        manifest=manifest,
        model="gemini-3.8-flash",
        leaves=LEAVES,
    )
    assert original_digest == recovery._sha256(original_raw)
    assert recovery_digest == recovery._sha256(recovery_raw)
    altered = canonical[1](
        **{
            **base.model_dump(mode="python"),
            "votes": tuple(vote for vote in base.votes if vote.attempt == 1),
            "attempts": tuple(
                canonical[0](
                    **{
                        **attempt.model_dump(mode="python"),
                        "status": "schema_failed",
                        "returned_model": None,
                        "provider_request_id": None,
                        "error_code": "ValueError",
                    }
                )
                if attempt.item_id == manifest.items[1].item_id and attempt.attempt == 2
                else attempt
                for attempt in base.attempts
            ),
        }
    )
    with pytest.raises(ValueError, match="exact attempt-1/2 merge"):
        recovery._validate_parent_artifacts(
            base=altered,
            original_raw=original_raw,
            recovery_raw=recovery_raw,
            annotation_batch=canonical[1],
            strict_json_loads=strict_json_loads,
            manifest=manifest,
            model="gemini-3.8-flash",
            leaves=LEAVES,
        )


def test_attempt3_base_rejects_returned_model_mismatch():
    canonical, manifest, _, _, base = _attempt3_fixture()
    attempts = tuple(
        canonical[0](
            **{
                **attempt.model_dump(mode="python"),
                "returned_model": "gemini-3.8-flash-999",
            }
        )
        if attempt.item_id == manifest.items[1].item_id and attempt.attempt == 2
        else attempt
        for attempt in base.attempts
    )
    mismatched = canonical[1](
        **{**base.model_dump(mode="python"), "attempts": attempts}
    )
    with pytest.raises(ValueError, match="retry-after-success"):
        recovery._validate_base_output(
            mismatched,
            manifest=manifest,
            model="gemini-3.8-flash",
            leaves=LEAVES,
            recovery_attempt=3,
        )


def test_attempt3_rejects_missing_attempt2_and_retry_after_success():
    canonical, manifest, _, _, base = _attempt3_fixture()
    missing = canonical[1](
        **{
            **base.model_dump(mode="python"),
            "attempts": tuple(
                attempt
                for attempt in base.attempts
                if not (
                    attempt.item_id == manifest.items[2].item_id
                    and attempt.attempt == 2
                )
            ),
        }
    )
    with pytest.raises(ValueError, match="every prior failed attempt"):
        recovery._validate_base_output(
            missing,
            manifest=manifest,
            model="gemini-3.8-flash",
            leaves=LEAVES,
            recovery_attempt=3,
        )
    extra = canonical[0](
        item_id=manifest.items[0].item_id,
        model="gemini-3.8-flash",
        provider="gemini_api",
        mode="batch",
        job_id="batch/illegal",
        request_id=manifest.items[0].item_id,
        attempt=2,
        status="schema_failed",
        item_count=1,
        error_code="ValueError",
    )
    post_success = canonical[1](
        **{
            **base.model_dump(mode="python"),
            "attempts": (*base.attempts, extra),
        }
    )
    with pytest.raises(ValueError, match="retry-after-success"):
        recovery._validate_base_output(
            post_success,
            manifest=manifest,
            model="gemini-3.8-flash",
            leaves=LEAVES,
            recovery_attempt=3,
        )


def test_attempt3_state_requires_and_binds_passing_gate(tmp_path):
    canonical, manifest, prompts, base_raw, base = _attempt3_fixture()
    state_path, receipt_path = _passing_gate(tmp_path, canonical)
    state_digest, receipt_digest, returned_models = acceptance.validate_gate(
        state_path=state_path,
        receipt_path=receipt_path,
        model="gemini-3.8-flash",
        system=SYSTEM,
        leaves=LEAVES,
        canonical=canonical,
    )
    requests = recovery._recovery_requests(
        (prompts[2],), SYSTEM, LEAVES, types, recovery_attempt=3
    )
    wire_bytes = recovery._serialized_inline_batch_bytes("gemini-3.8-flash", requests)
    state = recovery._initial_state(
        manifest=manifest,
        prompts=(prompts[2],),
        model="gemini-3.8-flash",
        base_raw=base_raw,
        base_vote_count=len(base.votes),
        leaves=LEAVES,
        system=SYSTEM,
        serialized_request_bytes=wire_bytes,
        canonical=canonical,
        recovery_attempt=3,
        acceptance_state_sha256=state_digest,
        acceptance_receipt_sha256=receipt_digest,
        parent_original_output_sha256=_digest("original-parent"),
        parent_recovery_output_sha256=_digest("recovery-parent"),
        accepted_returned_models=returned_models,
    )
    assert state.recovery_attempt == 3
    assert state.output_contract_sha256 is not None
    with pytest.raises(ValidationError, match="gated v2 contract"):
        recovery.RecoveryState.model_validate(
            {**state.model_dump(mode="python"), "acceptance_receipt_sha256": None},
            strict=True,
        )
    tampered = json.loads(receipt_path.read_text())
    tampered["sdk_version"] = "tampered-sdk"
    receipt_path.write_text(json.dumps(tampered))
    with pytest.raises(ValueError, match="contract"):
        acceptance.validate_gate(
            state_path=state_path,
            receipt_path=receipt_path,
            model="gemini-3.8-flash",
            system=SYSTEM,
            leaves=LEAVES,
            canonical=canonical,
        )


def test_acceptance_rejects_normal_json_with_alternate_keys():
    part = SimpleNamespace(
        text=json.dumps(
            {
                "status": "labelled",
                "detailed_category": "groceries",
                "confidence": 0.8,
                "commentary": "Wrong field names.",
            }
        ),
        thought=False,
    )
    result = SimpleNamespace(
        error=None,
        response=SimpleNamespace(
            model_version="gemini-3.8-flash",
            candidates=[
                SimpleNamespace(
                    finish_reason="STOP",
                    content=SimpleNamespace(parts=[part]),
                )
            ],
        ),
    )
    with pytest.raises(ValueError, match="schema mismatch"):
        acceptance._strict_provider_result(
            result, "gemini-3.8-flash", LEAVES, strict_json_loads
        )


def test_shared_validator_rejects_bad_confidence_and_non_stop_finish():
    def result_for(*, confidence: float, finish_reason: str):
        part = SimpleNamespace(
            text=json.dumps(
                {
                    "status": "labelled",
                    "leaf": "groceries",
                    "confidence": confidence,
                    "rationale": "Synthetic response.",
                }
            ),
            thought=False,
        )
        return SimpleNamespace(
            error=None,
            response=SimpleNamespace(
                model_version="gemini-3.8-flash",
                response_id="synthetic-response",
                usage_metadata=None,
                candidates=[
                    SimpleNamespace(
                        finish_reason=finish_reason,
                        content=SimpleNamespace(parts=[part]),
                    )
                ],
            ),
        )

    with pytest.raises(ValueError, match="outside"):
        acceptance._strict_provider_result(
            result_for(confidence=2.0, finish_reason="STOP"),
            "gemini-3.8-flash",
            LEAVES,
            strict_json_loads,
        )
    with pytest.raises(ValueError, match="STOP"):
        acceptance._strict_provider_result(
            result_for(confidence=0.8, finish_reason="MAX_TOKENS"),
            "gemini-3.8-flash",
            LEAVES,
            strict_json_loads,
        )


def test_acceptance_binding_uses_exact_production_wrapper(monkeypatch):
    canonical, _, _, _, _ = _attempt3_fixture()
    before = _binding(canonical)["request_payload_sha256"]
    original = pilot._prompt
    monkeypatch.setattr(
        pilot,
        "_prompt",
        lambda item: "Changed production wrapper.\n\n" + item.prompt,
    )
    after = _binding(canonical)["request_payload_sha256"]
    monkeypatch.setattr(pilot, "_prompt", original)
    assert before != after


def test_acceptance_binding_uses_exact_generation_configuration(monkeypatch):
    canonical, _, _, _, _ = _attempt3_fixture()
    before = _binding(canonical)["request_payload_sha256"]
    original = recovery._recovery_requests

    def high_thinking_requests(*args, **kwargs):
        requests = original(*args, **kwargs)
        for request in requests:
            request.config.thinking_config.thinking_level = types.ThinkingLevel.HIGH
        return requests

    monkeypatch.setattr(recovery, "_recovery_requests", high_thinking_requests)
    after = _binding(canonical)["request_payload_sha256"]
    assert before != after


def test_validator_binding_includes_finish_reason_normalizer(monkeypatch):
    canonical, _, _, _, _ = _attempt3_fixture()
    before = recovery._validator_sha256(canonical)

    def always_stop(candidate):
        return "STOP"

    monkeypatch.setattr(recovery, "_normal_finish_reason", always_stop)
    after = recovery._validator_sha256(canonical)
    assert before != after


def test_stale_recovery_state_update_cannot_overwrite_newer_state(tmp_path):
    canonical, manifest, prompts, base_raw, base = _attempt3_fixture()
    gate_state, gate_receipt = _passing_gate(tmp_path / "gate", canonical)
    state_digest, receipt_digest, returned_models = acceptance.validate_gate(
        state_path=gate_state,
        receipt_path=gate_receipt,
        model="gemini-3.8-flash",
        system=SYSTEM,
        leaves=LEAVES,
        canonical=canonical,
    )
    requests = recovery._recovery_requests(
        (prompts[2],), SYSTEM, LEAVES, types, recovery_attempt=3
    )
    state = recovery._initial_state(
        manifest=manifest,
        prompts=(prompts[2],),
        model="gemini-3.8-flash",
        base_raw=base_raw,
        base_vote_count=len(base.votes),
        leaves=LEAVES,
        system=SYSTEM,
        serialized_request_bytes=recovery._serialized_inline_batch_bytes(
            "gemini-3.8-flash", requests
        ),
        canonical=canonical,
        recovery_attempt=3,
        acceptance_state_sha256=state_digest,
        acceptance_receipt_sha256=receipt_digest,
        parent_original_output_sha256=_digest("original-parent"),
        parent_recovery_output_sha256=_digest("recovery-parent"),
        accepted_returned_models=returned_models,
    )
    path = tmp_path / "recovery-state.json"
    pilot._write_json(path, state.model_dump(mode="json"), exclusive=True)
    updated = recovery._update_state(
        path,
        state,
        state="submitted",
        provider_job_id="batch/recovery-a3",
        provider_status="submitted",
    )
    assert updated.state == "submitted"
    with pytest.raises(ValueError, match="stale"):
        recovery._update_state(
            path,
            state,
            state="submission_uncertain",
            error_code="RuntimeError",
        )


def test_attempt3_collection_appends_one_attempt_and_binds_artifacts(
    tmp_path, monkeypatch
):
    canonical, manifest, prompts, base_raw, base = _attempt3_fixture()
    gate_state, gate_receipt = _passing_gate(tmp_path / "gate", canonical)
    state_digest, receipt_digest, returned_models = acceptance.validate_gate(
        state_path=gate_state,
        receipt_path=gate_receipt,
        model="gemini-3.8-flash",
        system=SYSTEM,
        leaves=LEAVES,
        canonical=canonical,
    )
    selected = (prompts[2],)
    requests = recovery._recovery_requests(
        selected, SYSTEM, LEAVES, types, recovery_attempt=3
    )
    initial = recovery._initial_state(
        manifest=manifest,
        prompts=selected,
        model="gemini-3.8-flash",
        base_raw=base_raw,
        base_vote_count=len(base.votes),
        leaves=LEAVES,
        system=SYSTEM,
        serialized_request_bytes=recovery._serialized_inline_batch_bytes(
            "gemini-3.8-flash", requests
        ),
        canonical=canonical,
        recovery_attempt=3,
        acceptance_state_sha256=state_digest,
        acceptance_receipt_sha256=receipt_digest,
        parent_original_output_sha256=_digest("original-parent"),
        parent_recovery_output_sha256=_digest("recovery-parent"),
        accepted_returned_models=returned_models,
    )
    state = recovery.RecoveryState.model_validate(
        {
            **initial.model_dump(mode="python"),
            "state": "submitted",
            "provider_job_id": "batch/recovery-a3",
            "provider_status": "submitted",
        },
        strict=True,
    )
    state_path = tmp_path / "recovery-state.json"
    pilot._write_json(state_path, state.model_dump(mode="json"), exclusive=True)
    job = SimpleNamespace(
        state=SimpleNamespace(value="JOB_STATE_SUCCEEDED"),
        dest=SimpleNamespace(inlined_responses=[_provider_result(prompts[2].item_id)]),
    )
    monkeypatch.setattr(
        pilot, "_clients", lambda args, provider: (_FakeClient(job), types)
    )
    args = Namespace(
        model="gemini-3.8-flash",
        job_state=state_path,
        output=tmp_path / "recovery-a3.json",
        merged_output=tmp_path / "complete-v3.json",
    )
    recovery._collect(
        args,
        selected,
        LEAVES,
        manifest,
        base_raw,
        base,
        state,
        canonical,
    )
    merged = canonical[1].model_validate_json(
        args.merged_output.read_bytes(), strict=True
    )
    validate_batch(manifest, merged)
    assert len(merged.votes) == 3
    assert [
        attempt.attempt
        for attempt in merged.attempts
        if attempt.item_id == prompts[2].item_id
    ] == [1, 2, 3]
    final_state = recovery._load_state(state_path, strict_json_loads)
    assert final_state.state == "collected"
    assert final_state.recovery_output_sha256 == recovery._sha256(
        args.output.read_bytes()
    )
    assert final_state.merged_output_sha256 == recovery._sha256(
        args.merged_output.read_bytes()
    )
    assert final_state.collected_vote_count == 1

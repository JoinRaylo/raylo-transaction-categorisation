"""Synthetic unit tests for the provider-independent pilot runner guards."""

import json
import os
import sys
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

import pytest
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
from tools.benchmark.annotation_pilot import (  # noqa: E402
    BatchState,
    PrivatePrompt,
    _binding_digests,
    _collection_state,
    _provider_request_id,
    _strict_result,
    _validate_experiment_paths,
)
from tools.benchmark import annotation_pilot as pilot  # noqa: E402


def _digest(seed: str) -> str:
    import hashlib

    return hashlib.sha256(seed.encode()).hexdigest()


def _fixture():
    canonical = pilot._load_canonical(APP_ROOT)
    item = PilotItem(
        item_id="pilot-v1-" + _digest("item"),
        content_sha256=_digest("content"),
        subject_sha256=_digest("subject"),
        reservation_sha256=_digest("reservation"),
        source_snapshot_sha256=_digest("snapshot"),
        taxonomy_sha256=_digest("taxonomy"),
        guide_sha256=_digest("guide"),
        prompt_sha256=sha256(b"Synthetic transaction prompt."),
        views=("representative",),
    )
    operation = "op-" + "a" * 32
    manifest = PilotManifest(
        manifest_kind="synthetic",
        manifest_sha256=manifest_digest(
            expected_count=1,
            reservation_operation_id=operation,
            reservation_epoch=1,
            items=(item,),
            manifest_kind="synthetic",
        ),
        expected_count=1,
        reservation_operation_id=operation,
        reservation_epoch=1,
        items=(item,),
    )
    prompt_text = "Synthetic transaction prompt."
    prompt = PrivatePrompt(
        item_id=item.item_id,
        manifest_sha256=manifest.manifest_sha256,
        content_sha256=item.content_sha256,
        prompt_sha256=sha256(prompt_text.encode()),
        prompt=prompt_text,
    )
    return canonical, manifest, (prompt,)


def _submitted_state(tmp_path, canonical, manifest, prompts, model="gemini-3.8-flash"):
    provider = "gemini_api"
    state = pilot._initial_job_state(manifest, prompts, model, provider, canonical)
    state = BatchState.model_validate(
        {
            **state.model_dump(),
            "state": "submitted",
            "provider_job_id": "batch/synthetic",
            "provider_status": "submitted",
        },
        strict=True,
    )
    path = tmp_path / "state.json"
    pilot._write_json(path, state.model_dump(mode="json"), exclusive=True)
    return path


class _FakeBatches:
    def __init__(self, job):
        self.job = job
        self.created = None

    def create(self, **kwargs):
        self.created = kwargs
        return SimpleNamespace(name="batch/synthetic")

    def get(self, *, name):
        assert name == "batch/synthetic"
        return self.job


class _FakeClient:
    def __init__(self, job):
        self.batches = _FakeBatches(job)


def test_provider_result_is_exact_and_status_fields_cannot_smuggle_labels():
    valid = {
        "status": "labelled",
        "leaf": "groceries",
        "confidence": 0.75,
        "rationale": "Synthetic rationale.",
    }
    assert _strict_result(valid) == valid
    with pytest.raises(ValueError, match="schema mismatch"):
        _strict_result({**valid, "extra": "nope"})
    with pytest.raises(ValueError, match="non-labelled"):
        _strict_result(
            {
                "status": "ambiguous",
                "leaf": None,
                "confidence": 0.25,
                "rationale": "Synthetic ambiguity.",
            }
        )
    with pytest.raises(ValueError, match="non-finite"):
        _strict_result({**valid, "confidence": float("nan")})


def test_private_prompt_forbids_source_identity_and_batch_state_is_digest_only():
    prompt = {
        "item_id": "pilot-v1-" + "a" * 64,
        "manifest_sha256": _digest("manifest"),
        "content_sha256": _digest("content"),
        "prompt_sha256": _digest("prompt"),
        "prompt": "Synthetic transaction text.",
    }
    with pytest.raises(ValidationError):
        PrivatePrompt.model_validate(
            {**prompt, "transaction_id": "real-source-id"}, strict=True
        )
    state = BatchState(
        manifest_sha256=_digest("manifest"),
        model="gemini-3.8-flash",
        provider="gemini_api",
        request_count=1,
        request_ids_sha256=_digest("requests"),
        state="submission_started",
        taxonomy_sha256=_digest("taxonomy"),
        guide_sha256=_digest("guide"),
    )
    assert state.purpose == "annotation_method_experiment"
    assert state.provider_job_id is None


def test_provider_request_ids_are_deterministic_and_anthropic_ids_fit_limit():
    item_id = "pilot-v1-" + "b" * 64
    anthropic_id = _provider_request_id(item_id, "anthropic_api")
    assert anthropic_id == _provider_request_id(item_id, "anthropic_api")
    assert len(anthropic_id) <= 64
    assert _provider_request_id(item_id, "gemini_api") == item_id


def test_experiment_artifacts_must_be_under_dedicated_quarantine_root(tmp_path):
    root = tmp_path / "annotation_method_experiment"
    args = Namespace(
        experiment_root=root,
        output=root / "outputs" / "gemini.json",
        job_state=root / "jobs" / "gemini.json",
    )
    _validate_experiment_paths(args)
    args.output = tmp_path / "training" / "gemini.json"
    with pytest.raises(ValueError, match="under experiment root"):
        _validate_experiment_paths(args)


def test_manifest_binding_hashes_must_match_supplied_files(tmp_path):
    taxonomy = tmp_path / "taxonomy.csv"
    guide = tmp_path / "guide.txt"
    taxonomy.write_text("taxonomy", encoding="utf-8")
    guide.write_text("guide", encoding="utf-8")
    item = SimpleNamespace(
        taxonomy_sha256=_digest("taxonomy"),
        guide_sha256=_digest("guide"),
    )
    manifest = SimpleNamespace(items=(item,))
    assert _binding_digests(manifest, taxonomy, guide) == (
        _digest("taxonomy"),
        _digest("guide"),
    )
    guide.write_text("changed guide", encoding="utf-8")
    with pytest.raises(ValueError, match="not bound"):
        _binding_digests(manifest, taxonomy, guide)


def test_partial_provider_collection_has_an_explicit_incomplete_state():
    assert _collection_state(1, 1) == "collected"
    assert _collection_state(0, 1) == "collected_incomplete"


def test_real_pilot_manifest_is_not_provider_executable():
    manifest = SimpleNamespace(manifest_kind="real_pilot")
    with pytest.raises(ValueError, match="synthetic manifests only"):
        pilot._validate_runner_manifest(manifest)


def test_batch_state_invariants_and_transitions_are_fail_closed(tmp_path):
    canonical, manifest, prompts = _fixture()
    state_path = _submitted_state(tmp_path, canonical, manifest, prompts)
    state = pilot._load_job_state(state_path, strict_json_loads)
    with pytest.raises(ValidationError, match="requires a job/status"):
        BatchState.model_validate(
            {
                **state.model_dump(),
                "state": "submitted",
                "provider_job_id": None,
            },
            strict=True,
        )
    with pytest.raises(ValueError, match="illegal batch state transition"):
        pilot._update_job_state(
            state_path,
            state,
            state="submission_uncertain",
            error_code="late_failure",
        )


def test_fake_batch_submit_records_job_only_after_digest_state(tmp_path, monkeypatch):
    canonical, manifest, prompts = _fixture()
    root = tmp_path / "annotation_method_experiment"
    args = Namespace(
        model="gemini-3.8-flash",
        job_state=root / "jobs" / "state.json",
        gcp_project="synthetic-project",
        gcp_location="global",
    )
    client = _FakeClient(
        SimpleNamespace(state=SimpleNamespace(value="JOB_STATE_SUCCEEDED"))
    )
    monkeypatch.setattr(pilot, "_clients", lambda args, provider: (client, None))
    monkeypatch.setattr(pilot, "_batch_requests", lambda *args: [])
    pilot._submit_batch(args, prompts, "Synthetic guide", manifest, canonical)
    state = pilot._load_job_state(args.job_state, strict_json_loads)
    assert state.state == "submitted"
    assert state.provider_job_id == "batch/synthetic"
    assert client.batches.created is not None


def test_fake_batch_status_updates_only_status(tmp_path, monkeypatch, capsys):
    canonical, manifest, prompts = _fixture()
    state_path = _submitted_state(tmp_path, canonical, manifest, prompts)
    job = SimpleNamespace(state=SimpleNamespace(value="JOB_STATE_SUCCEEDED"))
    client = _FakeClient(job)
    monkeypatch.setattr(pilot, "_clients", lambda args, provider: (client, None))
    pilot._batch_status(Namespace(job_state=state_path), canonical)
    state = pilot._load_job_state(state_path, strict_json_loads)
    assert state.state == "submitted"
    assert state.provider_status == "JOB_STATE_SUCCEEDED"
    capsys.readouterr()


def test_fake_batch_collect_maps_one_result_to_one_vote(tmp_path, monkeypatch):
    canonical, manifest, prompts = _fixture()
    item = prompts[0].item_id
    response = SimpleNamespace(
        text=json.dumps(
            {
                "status": "labelled",
                "leaf": "groceries",
                "confidence": 0.9,
                "rationale": "Synthetic response.",
            }
        ),
        model_version="gemini-3.8-flash",
        response_id="response-1",
        usage_metadata=None,
    )
    result = SimpleNamespace(error=None, metadata={"item_id": item}, response=response)
    job = SimpleNamespace(
        state=SimpleNamespace(value="JOB_STATE_SUCCEEDED"),
        dest=SimpleNamespace(inlined_responses=[result]),
    )
    state_path = _submitted_state(tmp_path, canonical, manifest, prompts)
    output = tmp_path / "output.json"
    monkeypatch.setattr(
        pilot, "_clients", lambda args, provider: (_FakeClient(job), None)
    )
    pilot._collect_batch(
        Namespace(
            model="gemini-3.8-flash",
            job_state=state_path,
            output=output,
        ),
        prompts,
        "Synthetic guide",
        frozenset({"groceries", "unclassified_other"}),
        manifest,
        canonical,
    )
    batch = canonical[1].model_validate_json(output.read_bytes(), strict=True)
    validate_batch(manifest, batch)
    assert len(batch.votes) == 1
    assert pilot._load_job_state(state_path, strict_json_loads).state == "collected"


def test_fake_batch_collect_records_missing_result_as_incomplete(tmp_path, monkeypatch):
    canonical, manifest, prompts = _fixture()
    job = SimpleNamespace(
        state=SimpleNamespace(value="JOB_STATE_SUCCEEDED"),
        dest=SimpleNamespace(inlined_responses=[]),
    )
    state_path = _submitted_state(tmp_path, canonical, manifest, prompts)
    output = tmp_path / "output.json"
    monkeypatch.setattr(
        pilot, "_clients", lambda args, provider: (_FakeClient(job), None)
    )
    pilot._collect_batch(
        Namespace(model="gemini-3.8-flash", job_state=state_path, output=output),
        prompts,
        "Synthetic guide",
        frozenset({"groceries", "unclassified_other"}),
        manifest,
        canonical,
    )
    assert (
        canonical[1].model_validate_json(output.read_bytes(), strict=True).votes == ()
    )
    assert (
        pilot._load_job_state(state_path, strict_json_loads).state
        == "collected_incomplete"
    )

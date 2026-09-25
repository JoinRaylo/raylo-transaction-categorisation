"""Synthetic unit tests for the provider-independent pilot runner guards."""

import hashlib
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

from tools.benchmark import annotation_pilot as pilot  # noqa: E402
from tools.benchmark.annotation_pilot import (  # noqa: E402
    BatchState,
    PrivatePrompt,
    _binding_digests,
    _collection_state,
    _provider_request_id,
    _strict_result,
    _validate_experiment_paths,
)


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


def test_provider_rationale_obvious_identifiers_are_redacted_before_storage():
    rationale = "Email person@example.com or call 07123 456789 ref 123456789."
    redacted = pilot._redact_output_rationale(rationale)
    assert "person@example.com" not in redacted
    assert "07123 456789" not in redacted
    assert "123456789" not in redacted
    assert redacted.count("[redacted-") == 3


@pytest.mark.parametrize(
    ("requested", "returned"),
    [
        ("gemini-3.8-flash", "gemini-3.8-flash"),
        ("gemini-3.8-flash", "models/gemini-3.8-flash-001"),
        ("gemini-3.7-flash", "gemini-3.7-flash-20260918"),
        ("claude-sonnet-5", "claude-sonnet-5-20260918"),
    ],
)
def test_returned_model_identity_allows_only_requested_revision_family(
    requested, returned
):
    assert pilot._validate_returned_model(requested, returned) == returned


@pytest.mark.parametrize(
    "returned",
    [None, "", "gemini-3.7-flash", "gemini-3.8-flash-preview", "claude-sonnet-5"],
)
def test_returned_model_identity_rejects_missing_or_other_models(returned):
    with pytest.raises(ValueError, match="unverified model identity"):
        pilot._validate_returned_model("gemini-3.8-flash", returned)


def test_anthropic_result_requires_exactly_one_named_tool_call():
    correct = SimpleNamespace(type="tool_use", name="submit_annotation")
    assert pilot._anthropic_tool_result([correct]) is correct
    with pytest.raises(ValueError, match="exactly one"):
        pilot._anthropic_tool_result([])
    with pytest.raises(ValueError, match="exactly one"):
        pilot._anthropic_tool_result(
            [correct, SimpleNamespace(type="tool_use", name="other")]
        )
    with pytest.raises(ValueError, match="exactly one"):
        pilot._anthropic_tool_result([SimpleNamespace(type="tool_use", name="other")])


def test_anthropic_client_disables_automatic_retries(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "synthetic-key")
    client, types = pilot._clients(Namespace(), "anthropic_api")
    try:
        assert types is None
        assert client.max_retries == 0
    finally:
        client.close()


def test_anthropic_batch_results_disable_response_compression():
    class FakeResults:
        def __init__(self):
            self.extra_headers = None

        def results(self, job_id, *, extra_headers):
            assert job_id == "batch-synthetic"
            self.extra_headers = extra_headers
            return ()

    batches = FakeResults()
    client = SimpleNamespace(messages=SimpleNamespace(batches=batches))
    assert pilot._anthropic_results(SimpleNamespace(id="batch-synthetic"), client) == {}
    assert batches.extra_headers == {"Accept-Encoding": "identity"}


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
    with pytest.raises(ValueError, match="reviewed-local-pilot"):
        pilot._validate_runner_manifest(manifest)
    pilot._validate_runner_manifest(manifest, allow_reviewed_real_pilot=True)


def _real_bundle_fixture(tmp_path):
    root = tmp_path / "annotation_method_experiment"
    root.mkdir(parents=True)
    paths = {
        "manifest": root / "manifest.json",
        "prompts": root / "prompts.jsonl",
        "taxonomy": root / "taxonomy.csv",
        "system": root / "system.txt",
    }
    for name, path in paths.items():
        path.write_text(f"synthetic {name}\n", encoding="utf-8")
    manifest = SimpleNamespace(
        manifest_kind="real_pilot",
        manifest_sha256=_digest("real-manifest"),
        items=tuple(None for _ in range(500)),
    )
    receipt = {
        "schema_version": "txncat-annotation-bundle-receipt-v1",
        "purpose": "three_independent_model_annotations",
        "manifest_kind": "real_pilot",
        "manifest_sha256": manifest.manifest_sha256,
        "rows": 500,
        "manifest_file_sha256": hashlib.sha256(
            paths["manifest"].read_bytes()
        ).hexdigest(),
        "prompts_sha256": hashlib.sha256(paths["prompts"].read_bytes()).hexdigest(),
        "taxonomy_sha256": hashlib.sha256(paths["taxonomy"].read_bytes()).hexdigest(),
        "system_sha256": hashlib.sha256(paths["system"].read_bytes()).hexdigest(),
        "primary_views": {
            "representative": 250,
            "unseen_input": 150,
            "unfamiliar_merchant": 100,
        },
        "obvious_identifier_redactions": {"email": 1},
        "explicit_source_identity_fields": 0,
        "provider_submission_review_required": True,
        "authorizes_consumption": False,
        "provider_calls": 0,
        "labels_created": 0,
    }
    receipt_path = root / "receipt.json"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    args = Namespace(
        mode="batch-submit",
        bundle_receipt=receipt_path,
        **paths,
    )
    return args, manifest


def test_real_pilot_requires_batch_and_an_unchanged_bundle_receipt(tmp_path):
    args, manifest = _real_bundle_fixture(tmp_path)
    pilot._validate_real_pilot_execution(args, manifest, strict_json_loads)

    args.prompts.write_text("changed prompts\n", encoding="utf-8")
    with pytest.raises(ValueError, match="receipt is incomplete or changed"):
        pilot._validate_real_pilot_execution(args, manifest, strict_json_loads)

    args.mode = "online"
    with pytest.raises(ValueError, match="discounted batch mode"):
        pilot._validate_real_pilot_execution(args, manifest, strict_json_loads)


def test_bundle_receipt_can_validate_one_read_only_snapshot(tmp_path):
    args, manifest = _real_bundle_fixture(tmp_path)
    snapshot = {
        "receipt_raw": args.bundle_receipt.read_bytes(),
        "manifest_raw": args.manifest.read_bytes(),
        "prompts_raw": args.prompts.read_bytes(),
        "taxonomy_raw": args.taxonomy.read_bytes(),
        "system_raw": args.system.read_bytes(),
    }
    args.system.write_text("concurrent replacement\n", encoding="utf-8")
    pilot._validate_bundle_receipt_contents(
        **snapshot,
        manifest=manifest,
        strict_json_loads=strict_json_loads,
    )
    with pytest.raises(ValueError, match="receipt is incomplete or changed"):
        pilot._validate_bundle_receipt(
            args.bundle_receipt,
            manifest_path=args.manifest,
            prompts_path=args.prompts,
            taxonomy_path=args.taxonomy,
            system_path=args.system,
            manifest=manifest,
            strict_json_loads=strict_json_loads,
        )


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("rows",), 500.0),
        (("primary_views", "representative"), 250.0),
        (("explicit_source_identity_fields",), False),
        (("provider_calls",), False),
        (("labels_created",), False),
    ],
)
def test_real_bundle_receipt_rejects_non_strict_integer_counts(tmp_path, path, value):
    args, manifest = _real_bundle_fixture(tmp_path)
    receipt = json.loads(args.bundle_receipt.read_text(encoding="utf-8"))
    target = receipt
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    args.bundle_receipt.write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(ValueError, match="receipt is incomplete or changed"):
        pilot._validate_real_pilot_execution(args, manifest, strict_json_loads)


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


def test_batch_collection_clears_stale_error_after_success(tmp_path, monkeypatch):
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
    job = SimpleNamespace(
        state=SimpleNamespace(value="JOB_STATE_SUCCEEDED"),
        dest=SimpleNamespace(
            inlined_responses=[
                SimpleNamespace(
                    error=None,
                    metadata={"item_id": item},
                    response=response,
                )
            ]
        ),
    )
    state_path = _submitted_state(tmp_path, canonical, manifest, prompts)
    submitted = pilot._load_job_state(state_path, strict_json_loads)
    pilot._update_job_state(
        state_path,
        submitted,
        state="collection_uncertain",
        error_code="SyntheticTransportError",
    )
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
    state = pilot._load_job_state(state_path, strict_json_loads)
    assert state.state == "collected"
    assert state.error_code is None


def test_batch_collection_recovers_identical_output_after_state_write_failure(
    tmp_path, monkeypatch
):
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
    job = SimpleNamespace(
        state=SimpleNamespace(value="JOB_STATE_SUCCEEDED"),
        dest=SimpleNamespace(
            inlined_responses=[
                SimpleNamespace(
                    error=None,
                    metadata={"item_id": item},
                    response=response,
                )
            ]
        ),
    )
    state_path = _submitted_state(tmp_path, canonical, manifest, prompts)
    output = tmp_path / "output.json"
    monkeypatch.setattr(
        pilot, "_clients", lambda args, provider: (_FakeClient(job), None)
    )
    original_update = pilot._update_job_state

    def fail_final_state_write(path, current_state, **changes):
        if changes.get("state") == "collected":
            raise RuntimeError("synthetic state write failure")
        return original_update(path, current_state, **changes)

    monkeypatch.setattr(pilot, "_update_job_state", fail_final_state_write)
    args = Namespace(model="gemini-3.8-flash", job_state=state_path, output=output)
    with pytest.raises(RuntimeError, match="synthetic state write failure"):
        pilot._collect_batch(
            args,
            prompts,
            "Synthetic guide",
            frozenset({"groceries", "unclassified_other"}),
            manifest,
            canonical,
        )
    assert output.exists()

    monkeypatch.setattr(pilot, "_update_job_state", original_update)
    pilot._collect_batch(
        args,
        prompts,
        "Synthetic guide",
        frozenset({"groceries", "unclassified_other"}),
        manifest,
        canonical,
    )
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

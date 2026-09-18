"""Retry only failed Gemini annotation-batch items and merge their evidence.

The first batch output is immutable evidence.  A recovery job is bound to its
exact digest and to the deterministic set of manifest items that have no valid
vote.  Successful first-attempt items are never resubmitted.  Recovery uses
Gemini batch mode only, low thinking, a larger output ceiling and an exact
taxonomy-leaf enum.  Collection writes a separate recovery output and a merged
batch that retains both attempts; it never invents or adjudicates a label.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.benchmark import annotation_pilot as pilot

RECOVERY_ATTEMPT = 2
RECOVERY_MAX_OUTPUT_TOKENS = 4096
RECOVERY_THINKING_LEVEL = "low"
RECOVERY_PROVIDER = "gemini_api"
GEMINI_MODELS = ("gemini-3.8-flash", "gemini-3.7-flash")
INLINE_BATCH_PROVIDER_LIMIT_BYTES = 20_000_000
INLINE_BATCH_SAFE_LIMIT_BYTES = 18_000_000


class RecoveryState(BaseModel):
    """Digest-only state for one failed-item Gemini recovery batch."""

    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    schema_version: Literal["benchmark-annotation-recovery-job-v1"] = (
        "benchmark-annotation-recovery-job-v1"
    )
    purpose: Literal["annotation_method_experiment"] = "annotation_method_experiment"
    manifest_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    manifest_item_count: Annotated[int, Field(gt=0, strict=True)]
    model: Literal["gemini-3.8-flash", "gemini-3.7-flash"]
    provider: Literal["gemini_api"] = RECOVERY_PROVIDER
    request_count: Annotated[int, Field(gt=0, strict=True)]
    request_ids_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    request_payload_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    serialized_request_bytes: Annotated[
        int, Field(gt=0, le=INLINE_BATCH_SAFE_LIMIT_BYTES, strict=True)
    ]
    inline_safe_limit_bytes: Literal[18000000] = INLINE_BATCH_SAFE_LIMIT_BYTES
    base_output_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    base_vote_count: Annotated[int, Field(ge=0, strict=True)]
    recovery_attempt: Literal[2] = RECOVERY_ATTEMPT
    thinking_level: Literal["low"] = RECOVERY_THINKING_LEVEL
    max_output_tokens: Literal[4096] = RECOVERY_MAX_OUTPUT_TOKENS
    response_schema_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    state: Literal[
        "submission_started",
        "submitted",
        "submission_uncertain",
        "collection_uncertain",
        "collected",
        "collected_incomplete",
    ]
    taxonomy_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    guide_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    provider_job_id: str | None = None
    provider_status: str | None = None
    error_code: str | None = None

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.base_vote_count + self.request_count != self.manifest_item_count:
            raise ValueError("recovery counts do not reconcile to the manifest")
        if self.provider_job_id is not None and not self.provider_job_id.strip():
            raise ValueError("recovery provider job ID cannot be empty")
        if self.provider_status is not None and not self.provider_status.strip():
            raise ValueError("recovery provider status cannot be empty")
        if self.error_code is not None and not self.error_code.strip():
            raise ValueError("recovery error code cannot be empty")
        if self.state == "submission_started":
            if any(
                value is not None
                for value in (
                    self.provider_job_id,
                    self.provider_status,
                    self.error_code,
                )
            ):
                raise ValueError(
                    "submission_started recovery cannot carry provider metadata"
                )
        elif self.state == "submitted":
            if (
                not self.provider_job_id
                or not self.provider_status
                or self.error_code is not None
            ):
                raise ValueError(
                    "submitted recovery requires a job/status and no error"
                )
        elif self.state == "submission_uncertain":
            if self.error_code is None:
                raise ValueError("submission_uncertain recovery requires an error code")
        elif self.state == "collection_uncertain":
            if not self.provider_job_id or self.error_code is None:
                raise ValueError(
                    "collection_uncertain recovery requires a job and error code"
                )
        elif self.state in {"collected", "collected_incomplete"}:
            if (
                not self.provider_job_id
                or not self.provider_status
                or self.error_code is not None
            ):
                raise ValueError(
                    "collected recovery requires a job/status and no error"
                )
        return self


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _result_schema(leaves: frozenset[str]) -> dict[str, object]:
    """Build the provider constraint from the pinned taxonomy, never model output."""

    if not leaves or any(type(leaf) is not str or not leaf for leaf in leaves):
        raise ValueError("recovery requires pinned taxonomy leaves")
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "status": {"type": "string", "enum": list(pilot.RESULT_STATUSES)},
            "leaf": {
                "anyOf": [
                    {"type": "string", "enum": sorted(leaves)},
                    {"type": "null"},
                ]
            },
            "confidence": {
                "anyOf": [
                    {"type": "number", "minimum": 0, "maximum": 1},
                    {"type": "null"},
                ]
            },
            "rationale": {"type": "string"},
        },
        "required": ["status", "leaf", "confidence", "rationale"],
    }


def _schema_sha256(leaves: frozenset[str], canonical) -> str:
    return canonical[5](canonical[4](_result_schema(leaves)))


def _request_payload_sha256(
    prompts,
    *,
    model: str,
    guide_sha256: str,
    response_schema_sha256: str,
    canonical,
) -> str:
    """Bind the exact wrapped contents and generation contract without storing text."""

    payload = {
        "model": model,
        "provider": RECOVERY_PROVIDER,
        "guide_sha256": guide_sha256,
        "thinking_level": RECOVERY_THINKING_LEVEL,
        "max_output_tokens": RECOVERY_MAX_OUTPUT_TOKENS,
        "response_schema_sha256": response_schema_sha256,
        "requests": [
            {
                "item_id": item.item_id,
                "content_sha256": item.content_sha256,
                "prompt_sha256": item.prompt_sha256,
                "wrapped_content_sha256": _sha256(pilot._prompt(item).encode("utf-8")),
            }
            for item in prompts
        ],
    }
    return canonical[5](canonical[4](payload))


def _load_base_output(path: Path, annotation_batch, strict_json_loads):
    raw = path.read_bytes()
    strict_json_loads(raw)
    return raw, annotation_batch.model_validate_json(raw, strict=True)


def _validate_base_output(
    base,
    *,
    manifest,
    model: str,
    leaves: frozenset[str],
) -> frozenset[str]:
    """Return exactly the failed item IDs after proving first-attempt completeness."""

    expected = {item.item_id for item in manifest.items}
    if (
        base.model != model
        or base.provider != RECOVERY_PROVIDER
        or base.mode != "batch"
        or base.manifest_sha256 != manifest.manifest_sha256
        or base.taxonomy_sha256 != manifest.items[0].taxonomy_sha256
        or base.guide_sha256 != manifest.items[0].guide_sha256
    ):
        raise ValueError("base output does not match requested manifest/model")
    if len(base.attempts) != len(expected):
        raise ValueError(
            "base output must contain exactly one attempt per manifest item"
        )
    attempt_ids = [attempt.item_id for attempt in base.attempts]
    if set(attempt_ids) != expected or len(set(attempt_ids)) != len(attempt_ids):
        raise ValueError("base output attempts do not exactly cover the manifest")
    if any(attempt.attempt != 1 for attempt in base.attempts):
        raise ValueError("base output must contain only first attempts")
    if any(
        attempt.status not in {"received", "schema_failed", "transport_failed"}
        for attempt in base.attempts
    ):
        raise ValueError("base output contains a non-terminal attempt")
    for vote in base.votes:
        pilot._validate_returned_model(model, vote.returned_model)
        if vote.attempt != 1:
            raise ValueError("base output vote is not from the first attempt")
        if vote.status == "labelled" and vote.leaf not in leaves:
            raise ValueError("base output contains an unknown taxonomy leaf")
    vote_ids = {vote.item_id for vote in base.votes}
    failed_attempt_ids = {
        attempt.item_id
        for attempt in base.attempts
        if attempt.status in {"schema_failed", "transport_failed"}
    }
    failed_ids = expected - vote_ids
    if failed_ids != failed_attempt_ids:
        raise ValueError("base output votes and failed attempts do not reconcile")
    if not failed_ids:
        raise ValueError("base output is already complete; recovery is forbidden")
    return frozenset(failed_ids)


def _select_failed_prompts(prompts, manifest, failed_ids: frozenset[str]):
    by_id = {prompt.item_id: prompt for prompt in prompts}
    selected = tuple(
        by_id[item.item_id] for item in manifest.items if item.item_id in failed_ids
    )
    if len(selected) != len(failed_ids) or {row.item_id for row in selected} != set(
        failed_ids
    ):
        raise ValueError("failed recovery prompts do not exactly match failed items")
    return selected


def _recovery_requests(prompts, system, leaves, types):
    schema = _result_schema(leaves)
    return [
        types.InlinedRequest(
            contents=pilot._prompt(item),
            metadata={"item_id": item.item_id},
            config=types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
                response_json_schema=schema,
                max_output_tokens=RECOVERY_MAX_OUTPUT_TOKENS,
                thinking_config=types.ThinkingConfig(
                    thinking_level=types.ThinkingLevel.LOW,
                ),
            ),
        )
        for item in prompts
    ]


def _serialized_inline_batch_bytes(model: str, requests) -> int:
    """Measure the installed SDK's exact wire body through an in-memory transport."""

    import httpx  # noqa: PLC0415
    from google import genai  # noqa: PLC0415
    from google.genai import types  # noqa: PLC0415

    bodies: list[bytes] = []

    def capture(request: httpx.Request) -> httpx.Response:
        bodies.append(bytes(request.content))
        return httpx.Response(
            status_code=400,
            json={"error": {"code": 400, "message": "wire-size-probe"}},
            request=request,
        )

    http_client = httpx.Client(transport=httpx.MockTransport(capture))
    client = genai.Client(
        api_key="local-wire-size-probe",
        vertexai=False,
        http_options=types.HttpOptions(httpx_client=http_client),
    )
    try:
        try:
            client.batches.create(model=model, src=requests)
        except Exception:
            if not bodies:
                raise
    finally:
        client.close()
    if len(bodies) != 1:
        raise ValueError("SDK wire-size probe did not capture exactly one request")
    return len(bodies[0])


def _require_inline_size(serialized_request_bytes: int) -> None:
    if type(serialized_request_bytes) is not int or serialized_request_bytes <= 0:
        raise ValueError("serialized recovery batch size is invalid")
    if serialized_request_bytes > INLINE_BATCH_SAFE_LIMIT_BYTES:
        raise ValueError(
            "recovery batch exceeds the conservative inline request size limit"
        )


def _canonical_state_path(args, manifest) -> Path:
    root = args.experiment_root.resolve()
    return (
        root
        / "jobs"
        / (
            f"{args.model}-recovery-a{RECOVERY_ATTEMPT}-"
            f"{manifest.manifest_sha256[:16]}.json"
        )
    )


def _require_canonical_state_path(args, manifest) -> Path:
    expected = _canonical_state_path(args, manifest)
    if args.job_state.resolve() != expected:
        raise ValueError(
            "recovery state path must be the canonical manifest/model attempt marker"
        )
    return expected


def _initial_state(
    *,
    manifest,
    prompts,
    model: str,
    base_raw: bytes,
    base_vote_count: int,
    leaves: frozenset[str],
    system: str,
    serialized_request_bytes: int,
    canonical,
) -> RecoveryState:
    response_schema_sha256 = _schema_sha256(leaves, canonical)
    guide_sha256 = _sha256(system.encode("utf-8"))
    _require_inline_size(serialized_request_bytes)
    if guide_sha256 != manifest.items[0].guide_sha256:
        raise ValueError("recovery system snapshot does not match the manifest")
    return RecoveryState(
        manifest_sha256=manifest.manifest_sha256,
        manifest_item_count=len(manifest.items),
        model=model,
        request_count=len(prompts),
        request_ids_sha256=pilot._request_ids_digest(
            prompts, RECOVERY_PROVIDER, canonical, canonical[5]
        ),
        request_payload_sha256=_request_payload_sha256(
            prompts,
            model=model,
            guide_sha256=guide_sha256,
            response_schema_sha256=response_schema_sha256,
            canonical=canonical,
        ),
        serialized_request_bytes=serialized_request_bytes,
        base_output_sha256=_sha256(base_raw),
        base_vote_count=base_vote_count,
        response_schema_sha256=response_schema_sha256,
        state="submission_started",
        taxonomy_sha256=manifest.items[0].taxonomy_sha256,
        guide_sha256=guide_sha256,
    )


def _load_state(path: Path, strict_json_loads) -> RecoveryState:
    raw = path.read_bytes()
    strict_json_loads(raw)
    return RecoveryState.model_validate_json(raw, strict=True)


def _update_state(
    path: Path, current_state: RecoveryState, **changes: object
) -> RecoveryState:
    payload = current_state.model_dump(mode="python")
    payload.update(changes)
    updated = RecoveryState.model_validate(payload, strict=True)
    allowed = {
        "submission_started": {
            "submission_started",
            "submitted",
            "submission_uncertain",
        },
        "submitted": {
            "submitted",
            "collection_uncertain",
            "collected",
            "collected_incomplete",
        },
        "collection_uncertain": {
            "collection_uncertain",
            "collected",
            "collected_incomplete",
        },
        "submission_uncertain": {"submission_uncertain"},
        "collected": {"collected"},
        "collected_incomplete": {"collected_incomplete"},
    }
    if updated.state not in allowed[current_state.state]:
        raise ValueError("illegal recovery state transition")
    pilot._write_json_atomic(path, updated.model_dump(mode="json"))
    return updated


def _validate_state_binding(
    state: RecoveryState,
    *,
    manifest,
    prompts,
    model: str,
    base_raw: bytes,
    base_vote_count: int,
    leaves: frozenset[str],
    system: str,
    serialized_request_bytes: int,
    canonical,
) -> None:
    response_schema_sha256 = _schema_sha256(leaves, canonical)
    guide_sha256 = _sha256(system.encode("utf-8"))
    _require_inline_size(serialized_request_bytes)
    if guide_sha256 != manifest.items[0].guide_sha256:
        raise ValueError("recovery system snapshot does not match the manifest")
    if (
        state.model != model
        or state.provider != RECOVERY_PROVIDER
        or state.manifest_sha256 != manifest.manifest_sha256
        or state.manifest_item_count != len(manifest.items)
        or state.request_count != len(prompts)
        or state.request_ids_sha256
        != pilot._request_ids_digest(
            prompts, RECOVERY_PROVIDER, canonical, canonical[5]
        )
        or state.request_payload_sha256
        != _request_payload_sha256(
            prompts,
            model=model,
            guide_sha256=guide_sha256,
            response_schema_sha256=response_schema_sha256,
            canonical=canonical,
        )
        or state.serialized_request_bytes != serialized_request_bytes
        or state.base_output_sha256 != _sha256(base_raw)
        or state.base_vote_count != base_vote_count
        or state.response_schema_sha256 != response_schema_sha256
        or state.taxonomy_sha256 != manifest.items[0].taxonomy_sha256
        or state.guide_sha256 != guide_sha256
    ):
        raise ValueError("recovery state does not match its immutable inputs")


def _submit(
    args,
    prompts,
    requests,
    serialized_request_bytes,
    system,
    leaves,
    manifest,
    base_raw,
    base,
    canonical,
):
    _require_canonical_state_path(args, manifest)
    _require_inline_size(serialized_request_bytes)
    if args.job_state.exists():
        raise ValueError("refusing to overwrite existing recovery state")
    state = _initial_state(
        manifest=manifest,
        prompts=prompts,
        model=args.model,
        base_raw=base_raw,
        base_vote_count=len(base.votes),
        leaves=leaves,
        system=system,
        serialized_request_bytes=serialized_request_bytes,
        canonical=canonical,
    )
    pilot._write_json(args.job_state, state.model_dump(mode="json"), exclusive=True)
    try:
        client, _ = pilot._clients(args, RECOVERY_PROVIDER)
        job = client.batches.create(
            model=args.model,
            src=requests,
        )
        provider_job_id = job.name
        if not isinstance(provider_job_id, str) or not provider_job_id.strip():
            raise ValueError("provider returned no recovery batch job ID")
    except Exception as exc:
        _update_state(
            args.job_state,
            state,
            state="submission_uncertain",
            error_code=pilot._failure_code(exc),
        )
        raise RuntimeError(
            "recovery submission uncertain; resolve provider job before retry"
        ) from exc
    _update_state(
        args.job_state,
        state,
        state="submitted",
        provider_job_id=provider_job_id,
        provider_status="submitted",
    )
    print(f"Submitted {state.request_count}-item {state.model} recovery batch.")


def _status(args, state: RecoveryState):
    client, _ = pilot._clients(args, state.provider)
    try:
        job = pilot._provider_job(state, client)
        status = pilot._job_status(state, job)
    except Exception as exc:
        raise RuntimeError(
            "recovery status read failed; no new submission is authorized"
        ) from exc
    _update_state(args.job_state, state, provider_status=status)
    print(f"{state.model} recovery batch status: {status}")


def _terminal(status: str) -> bool:
    return status in {
        "JOB_STATE_SUCCEEDED",
        "JOB_STATE_PARTIALLY_SUCCEEDED",
        "JOB_STATE_FAILED",
        "JOB_STATE_CANCELLED",
        "JOB_STATE_EXPIRED",
    }


def _write_batch_idempotently(path: Path, batch, annotation_batch, strict_json_loads):
    if path.exists():
        raw = path.read_bytes()
        strict_json_loads(raw)
        existing = annotation_batch.model_validate_json(raw, strict=True)
        if existing.model_dump(mode="json") != batch.model_dump(mode="json"):
            raise ValueError(
                "existing recovery artifact does not match provider results"
            )
        return
    pilot._write_output(path, batch)


def _collect(
    args,
    prompts,
    leaves,
    manifest,
    base_raw,
    base,
    state: RecoveryState,
    canonical,
):
    annotation_attempt, annotation_batch, annotation_vote = canonical[:3]
    strict_json_loads = canonical[6]
    client, _ = pilot._clients(args, state.provider)
    try:
        job = pilot._provider_job(state, client)
        status = pilot._job_status(state, job)
        if not _terminal(status):
            raise ValueError("provider recovery batch is not complete")
        results = pilot._gemini_results(job)
    except Exception as exc:
        _update_state(
            args.job_state,
            state,
            state="collection_uncertain",
            error_code=pilot._failure_code(exc),
        )
        raise RuntimeError(
            "recovery collection failed closed; inspect state before retry"
        ) from exc
    expected_result_ids = {prompt.item_id for prompt in prompts}
    if set(results) - expected_result_ids:
        raise ValueError("provider recovery batch returned an unknown item ID")
    votes = []
    attempts = []
    for item in prompts:
        provider_result = results.get(item.item_id)
        if provider_result is None:
            attempts.append(
                annotation_attempt(
                    item_id=item.item_id,
                    model=state.model,
                    provider=state.provider,
                    mode="batch",
                    job_id=state.provider_job_id,
                    request_id=item.item_id,
                    attempt=RECOVERY_ATTEMPT,
                    status="schema_failed",
                    item_count=1,
                    error_code="missing_batch_result",
                )
            )
            continue
        try:
            parsed = pilot._gemini_result(
                provider_result,
                state.model,
                strict_json_loads,
                item.item_id,
            )
            result, returned_model, provider_request_id, in_tok, out_tok = parsed
            vote = pilot._vote(
                item,
                result,
                model=state.model,
                returned_model=returned_model,
                attempt=RECOVERY_ATTEMPT,
                job_id=state.provider_job_id,
                request_id=provider_request_id,
                annotation_vote=annotation_vote,
            )
            if vote.status == "labelled" and vote.leaf not in leaves:
                raise ValueError("provider returned unknown taxonomy leaf")
            votes.append(vote)
            attempts.append(
                annotation_attempt(
                    item_id=item.item_id,
                    model=state.model,
                    provider=state.provider,
                    mode="batch",
                    job_id=state.provider_job_id,
                    request_id=item.item_id,
                    attempt=RECOVERY_ATTEMPT,
                    status="received",
                    item_count=1,
                    returned_model=returned_model,
                    provider_request_id=provider_request_id,
                    input_tokens=in_tok,
                    output_tokens=out_tok,
                )
            )
        except Exception as exc:
            attempts.append(
                annotation_attempt(
                    item_id=item.item_id,
                    model=state.model,
                    provider=state.provider,
                    mode="batch",
                    job_id=state.provider_job_id,
                    request_id=item.item_id,
                    attempt=RECOVERY_ATTEMPT,
                    status=pilot._failure_kind(exc),
                    item_count=1,
                    error_code=pilot._failure_code(exc),
                )
            )
    recovery = annotation_batch(
        taxonomy_sha256=state.taxonomy_sha256,
        guide_sha256=state.guide_sha256,
        manifest_sha256=manifest.manifest_sha256,
        model=state.model,
        provider=state.provider,
        mode="batch",
        votes=tuple(votes),
        attempts=tuple(attempts),
    )
    order = {item.item_id: index for index, item in enumerate(manifest.items)}
    merged = annotation_batch(
        taxonomy_sha256=state.taxonomy_sha256,
        guide_sha256=state.guide_sha256,
        manifest_sha256=manifest.manifest_sha256,
        model=state.model,
        provider=state.provider,
        mode="batch",
        votes=tuple(
            sorted((*base.votes, *recovery.votes), key=lambda row: order[row.item_id])
        ),
        attempts=tuple(
            sorted(
                (*base.attempts, *recovery.attempts),
                key=lambda row: (order[row.item_id], row.attempt),
            )
        ),
    )
    _write_batch_idempotently(
        args.output, recovery, annotation_batch, strict_json_loads
    )
    _write_batch_idempotently(
        args.merged_output, merged, annotation_batch, strict_json_loads
    )
    collection_state = pilot._collection_state(len(votes), len(prompts))
    _update_state(
        args.job_state,
        state,
        state=collection_state,
        provider_status=status,
        error_code=None,
    )
    print(
        f"Collected {len(votes)}/{len(prompts)} recovery votes; "
        f"merged batch now has {len(merged.votes)}/{len(manifest.items)} votes."
    )


def _validate_paths(args) -> None:
    pilot._validate_experiment_paths(args)
    root = args.experiment_root.resolve()
    paths = {
        "base output": args.base_output.resolve(),
        "recovery output": args.output.resolve(),
        "merged output": args.merged_output.resolve(),
        "recovery state": args.job_state.resolve(),
    }
    for name, path in paths.items():
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"{name} must stay under experiment root") from exc
        if path == root:
            raise ValueError(f"{name} must be below experiment root")
    if len(set(paths.values())) != len(paths):
        raise ValueError("recovery artifact paths must be distinct")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--monorepo-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--prompts", type=Path, required=True)
    parser.add_argument("--system", type=Path, required=True)
    parser.add_argument("--taxonomy", type=Path, required=True)
    parser.add_argument("--experiment-root", type=Path, required=True)
    parser.add_argument("--bundle-receipt", type=Path, required=True)
    parser.add_argument("--allow-reviewed-real-pilot", action="store_true")
    parser.add_argument("--model", choices=GEMINI_MODELS, required=True)
    parser.add_argument("--base-output", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--merged-output", type=Path, required=True)
    parser.add_argument("--job-state", type=Path, required=True)
    parser.add_argument(
        "--mode",
        choices=[
            "recovery-plan",
            "recovery-submit",
            "recovery-status",
            "recovery-collect",
        ],
        required=True,
    )
    parser.add_argument("--gcp-project", default="raylo-production")
    parser.add_argument("--gcp-location", default="global")
    args = parser.parse_args()

    _validate_paths(args)
    canonical = pilot._load_canonical(args.monorepo_root.resolve())
    annotation_batch, pilot_manifest, strict_json_loads = (
        canonical[1],
        canonical[3],
        canonical[6],
    )
    manifest_raw = args.manifest.read_bytes()
    prompts_raw = args.prompts.read_bytes()
    system_raw = args.system.read_bytes()
    taxonomy_raw = args.taxonomy.read_bytes()
    receipt_raw = args.bundle_receipt.read_bytes()
    manifest = pilot.parse_manifest(manifest_raw, pilot_manifest, strict_json_loads)
    pilot._validate_runner_manifest(
        manifest, allow_reviewed_real_pilot=args.allow_reviewed_real_pilot
    )
    if manifest.manifest_kind == "real_pilot":
        pilot._validate_bundle_receipt_contents(
            receipt_raw=receipt_raw,
            manifest_raw=manifest_raw,
            prompts_raw=prompts_raw,
            taxonomy_raw=taxonomy_raw,
            system_raw=system_raw,
            manifest=manifest,
            strict_json_loads=strict_json_loads,
        )
    pilot._binding_digests_bytes(manifest, taxonomy_raw, system_raw)
    prompts = pilot.parse_prompts(prompts_raw, manifest, strict_json_loads)
    leaves = pilot.taxonomy_leaves_bytes(taxonomy_raw)
    system = system_raw.decode("utf-8")
    if not system.strip():
        raise ValueError("annotation guide/system prompt is empty")
    base_raw, base = _load_base_output(
        args.base_output, annotation_batch, strict_json_loads
    )
    failed_ids = _validate_base_output(
        base, manifest=manifest, model=args.model, leaves=leaves
    )
    recovery_prompts = _select_failed_prompts(prompts, manifest, failed_ids)
    os.umask(0o077)
    _require_canonical_state_path(args, manifest)

    from google.genai import types  # noqa: PLC0415

    requests = _recovery_requests(recovery_prompts, system, leaves, types)
    serialized_bytes = _serialized_inline_batch_bytes(args.model, requests)
    _require_inline_size(serialized_bytes)

    if args.mode == "recovery-plan":
        print(
            f"Recovery plan: {len(recovery_prompts)} failed items, "
            f"{len(base.votes)} preserved votes, low thinking, "
            f"{RECOVERY_MAX_OUTPUT_TOKENS} max output tokens, "
            f"{len(leaves)} enumerated taxonomy leaves, "
            f"{serialized_bytes} serialized envelope bytes "
            f"(safe limit {INLINE_BATCH_SAFE_LIMIT_BYTES})."
        )
        return
    if args.mode == "recovery-submit":
        _submit(
            args,
            recovery_prompts,
            requests,
            serialized_bytes,
            system,
            leaves,
            manifest,
            base_raw,
            base,
            canonical,
        )
        return
    state = _load_state(args.job_state, strict_json_loads)
    _validate_state_binding(
        state,
        manifest=manifest,
        prompts=recovery_prompts,
        model=args.model,
        base_raw=base_raw,
        base_vote_count=len(base.votes),
        leaves=leaves,
        system=system,
        serialized_request_bytes=serialized_bytes,
        canonical=canonical,
    )
    if args.mode == "recovery-status":
        _status(args, state)
    else:
        _collect(
            args,
            recovery_prompts,
            leaves,
            manifest,
            base_raw,
            base,
            state,
            canonical,
        )


if __name__ == "__main__":
    try:
        main()
    except (
        OSError,
        KeyError,
        ValueError,
        RuntimeError,
    ) as exc:
        raise SystemExit(f"ERROR: {exc}") from exc

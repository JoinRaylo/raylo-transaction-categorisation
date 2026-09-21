"""Rebuild the three strict vote streams from recovered provider batch results.

The provider batch results recovered on 2026-09-21 (Anthropic results JSONL and
Gemini batch JSONs under the provider-recovery directory) are re-parsed with the
same production helpers the original runner used.  Raw JSON dicts are wrapped in
a thin ``SimpleNamespace`` attribute adapter so ``_gemini_text`` and
``_anthropic_tool_result`` can run unmodified.

Every attempt is recorded, valid or not.  The final vote for an item is its
single strict-valid attempt; an item with zero or two valid attempts is a hard
error, never filled or chosen.  No provider call is made and nothing here
authorizes consumption.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from types import SimpleNamespace

from annotation_pilot import (
    RESULT_STATUSES,
    _anthropic_tool_result,
    _gemini_text,
    _parse_json_text,
    _redact_output_rationale,
    _strict_result,
    _validate_returned_model,
    taxonomy_leaves,
)
from raylo_txncat.benchmark_annotation import AnnotationAttempt, AnnotationVote
from raylo_txncat.hashing import strict_json_loads

PILOT_ID = re.compile(r"^pilot-v1-[0-9a-f]{64}$")
ANTHROPIC_BATCH = "msgbatch_01GFrYE77BM3Rao63Ehks4GP"
GEMINI_BATCHES = {
    "gemini-3.8-flash": [
        "batches/psb1vpping57qmcslfiuumec1mf7icvijp8i",
        "batches/8tjwldfwn2d4vh9tqmuxn7wrwubhgylv7w54",
        "batches/tjy9nx474dvc280uhfirioalex6vkypkkld2",
    ],
    "gemini-3.7-flash": [
        "batches/i3qaltxah7e05rb2fgv40pqsvw0e23eb4cv8",
        "batches/idbxtixvxi69h44lunl9v9jc4q0ue139rvc8",
        "batches/u1akk1j5vpnrzc7q7z3wiazgu13rdio0cerh",
    ],
}


def _ns(value):
    """Recursive attribute adapter: raw JSON dict/list -> attribute access."""
    if isinstance(value, dict):
        return SimpleNamespace(**{key: _ns(item) for key, item in value.items()})
    if isinstance(value, list):
        return [_ns(item) for item in value]
    return value


def _attempt(
    item_id,
    model,
    provider,
    job_id,
    attempt,
    status,
    *,
    returned_model=None,
    provider_request_id=None,
    input_tokens=None,
    output_tokens=None,
    error_code=None,
):
    return AnnotationAttempt(
        item_id=item_id,
        model=model,
        provider=provider,
        mode="batch",
        job_id=job_id,
        request_id=item_id,
        attempt=attempt,
        status=status,
        item_count=1,
        returned_model=returned_model,
        provider_request_id=provider_request_id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        error_code=error_code,
    )


def _vote(item_id, model, result, returned_model, attempt, job_id, request_id):
    return AnnotationVote(
        item_id=item_id,
        model=model,
        returned_model=returned_model,
        status=result["status"],
        leaf=result["leaf"],
        confidence=result["confidence"],
        rationale=_redact_output_rationale(result["rationale"]),
        attempt=attempt,
        provider_job_id=job_id,
        provider_request_id=request_id,
    )


def _anthropic_attempts(path: Path, item_ids, leaves):
    """Parse the recovered Anthropic results JSONL into attempts and votes."""
    custom_to_item = {
        "pilot-v1-" + hashlib.sha256(item.encode("utf-8")).hexdigest()[:48]: item
        for item in item_ids
    }
    attempts, votes = [], []
    seen = set()
    for line in path.read_text().splitlines():
        row = json.loads(line)
        custom_id = row.get("custom_id", "")
        item_id = custom_to_item.get(custom_id)
        if item_id is None:
            raise ValueError("Anthropic result carries an unknown custom ID")
        if item_id in seen:
            raise ValueError("Anthropic result carries a duplicate custom ID")
        seen.add(item_id)
        job_id = ANTHROPIC_BATCH
        try:
            result = row.get("result") or {}
            if result.get("type") != "succeeded":
                raise ValueError(f"provider batch result is {result.get('type', 'unknown')}")
            message = result.get("message") or {}
            returned_model = _validate_returned_model("claude-sonnet-5", message.get("model"))
            if message.get("stop_reason") != "tool_use":
                raise ValueError("Anthropic result did not finish with tool_use")
            block = _anthropic_tool_result(_ns(message.get("content")))
            parsed = _strict_result(vars(block.input))
            if parsed["status"] == "labelled" and parsed["leaf"] not in leaves:
                raise ValueError("provider returned unknown taxonomy leaf")
            usage = message.get("usage") or {}
            provider_request_id = message.get("id") or custom_id
            votes.append(
                _vote(
                    item_id,
                    "claude-sonnet-5",
                    parsed,
                    returned_model,
                    1,
                    job_id,
                    provider_request_id,
                )
            )
            attempts.append(
                _attempt(
                    item_id,
                    "claude-sonnet-5",
                    "anthropic_api",
                    job_id,
                    1,
                    "received",
                    returned_model=returned_model,
                    provider_request_id=provider_request_id,
                    input_tokens=usage.get("input_tokens"),
                    output_tokens=usage.get("output_tokens"),
                )
            )
        except Exception as exc:
            attempts.append(
                _attempt(
                    item_id,
                    "claude-sonnet-5",
                    "anthropic_api",
                    job_id,
                    1,
                    "schema_failed",
                    error_code=type(exc).__name__[:256] or "provider_error",
                )
            )
    return attempts, votes


def _gemini_attempts(model, batch_names, recovery_dir, leaves):
    """Parse one model's recovered Gemini batches as attempts 1, 2, 3."""
    attempts, votes = [], []
    for attempt_no, name in enumerate(batch_names, start=1):
        path = recovery_dir / f"gemini-{name.replace('/', '-')}.json"
        body = json.loads(path.read_text())
        container = (body.get("response") or {}).get("inlinedResponses") or {}
        inlined = (
            container if isinstance(container, list) else container.get("inlinedResponses", [])
        )
        seen = set()
        for entry in inlined:
            item_id = (entry.get("metadata") or {}).get("item_id")
            if not isinstance(item_id, str) or not PILOT_ID.fullmatch(item_id) or item_id in seen:
                raise ValueError(f"{name}: duplicate or malformed pilot item ID")
            seen.add(item_id)
            try:
                if entry.get("error") is not None:
                    raise ValueError("Gemini batch result contains provider error")
                response = entry.get("response")
                if response is None:
                    raise ValueError("Gemini batch result has no response")
                candidates = response.get("candidates") or []
                if len(candidates) != 1:
                    raise ValueError("Gemini result does not have exactly one candidate")
                candidate = candidates[0]
                if candidate.get("finishReason") != "STOP":
                    raise ValueError("Gemini result finish reason is not STOP")
                parts = ((candidate.get("content") or {}).get("parts")) or []
                text_parts = [
                    part
                    for part in parts
                    if isinstance(part.get("text"), str) and part.get("thought") is not True
                ]
                if len(text_parts) != 1 or len(parts) != 1:
                    raise ValueError("Gemini result does not have exactly one text part")
                parsed = _parse_json_text(_gemini_text(_ns(response)), strict_json_loads)
                returned_model = _validate_returned_model(model, response.get("modelVersion"))
                if parsed["status"] == "labelled" and parsed["leaf"] not in leaves:
                    raise ValueError("provider returned unknown taxonomy leaf")
                usage = response.get("usageMetadata") or {}
                provider_request_id = response.get("responseId") or item_id
                votes.append(
                    _vote(
                        item_id,
                        model,
                        parsed,
                        returned_model,
                        attempt_no,
                        name,
                        provider_request_id,
                    )
                )
                attempts.append(
                    _attempt(
                        item_id,
                        model,
                        "gemini_api",
                        name,
                        attempt_no,
                        "received",
                        returned_model=returned_model,
                        provider_request_id=provider_request_id,
                        input_tokens=usage.get("promptTokenCount"),
                        output_tokens=usage.get("candidatesTokenCount"),
                    )
                )
            except Exception as exc:
                attempts.append(
                    _attempt(
                        item_id,
                        model,
                        "gemini_api",
                        name,
                        attempt_no,
                        "schema_failed",
                        error_code=type(exc).__name__[:256] or "provider_error",
                    )
                )
    return attempts, votes


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recovery-dir", type=Path, required=True)
    parser.add_argument("--taxonomy", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)

    leaves = taxonomy_leaves(args.taxonomy)
    args.output.mkdir(mode=0o700, parents=False, exist_ok=True)

    all_attempts: dict[str, list] = {}
    all_votes: dict[str, list] = {}
    pilot_ids: set[str] = set()

    for model, names in GEMINI_BATCHES.items():
        attempts, votes = _gemini_attempts(model, names, args.recovery_dir, leaves)
        all_attempts[model] = attempts
        all_votes[model] = votes
        pilot_ids |= {a.item_id for a in attempts}

    anthropic_attempts, anthropic_votes = _anthropic_attempts(
        args.recovery_dir / f"anthropic-{ANTHROPIC_BATCH}.results.jsonl",
        pilot_ids,
        leaves,
    )
    all_attempts["claude-sonnet-5"] = anthropic_attempts
    all_votes["claude-sonnet-5"] = anthropic_votes

    counts: dict[str, dict[str, dict[str, int]]] = {}
    hard_checks: dict[str, object] = {}
    mismatches: list[str] = []
    for model in ("claude-sonnet-5", "gemini-3.8-flash", "gemini-3.7-flash"):
        attempts = all_attempts[model]
        votes = all_votes[model]
        per_attempt: dict[str, dict[str, int]] = {}
        for attempt in attempts:
            bucket = per_attempt.setdefault(
                str(attempt.attempt), {"received": 0, "schema_failed": 0}
            )
            bucket["received" if attempt.status == "received" else "schema_failed"] += 1
        valid_items = [vote.item_id for vote in votes]
        if len(set(valid_items)) != len(valid_items):
            raise ValueError(f"{model}: an item has two valid attempts")
        missing = pilot_ids - set(valid_items)
        counts[model] = per_attempt
        hard_checks[model] = {
            "valid_votes": len(votes),
            "expected_valid_votes": len(pilot_ids),
            "missing_item_ids": sorted(missing),
            "valid_before_final_attempt": sum(
                per_attempt[str(n)]["received"] for n in range(1, max(int(k) for k in per_attempt))
            ),
        }
        if missing:
            mismatches.append(f"{model}: {len(votes)} valid votes; missing {len(missing)} item(s)")

    outputs = {}
    for model, votes in all_votes.items():
        path = args.output / f"votes-{model}.jsonl"
        lines = sorted(votes, key=lambda v: v.item_id)
        with path.open("x") as stream:
            for vote in lines:
                stream.write(json.dumps(vote.model_dump(mode="json"), sort_keys=True) + "\n")
        os.chmod(path, 0o600)
        outputs[f"votes-{model}.jsonl"] = _sha256(path)
    for model, attempts in all_attempts.items():
        path = args.output / f"attempts-{model}.jsonl"
        lines = sorted(attempts, key=lambda a: (a.item_id, a.attempt))
        with path.open("x") as stream:
            for attempt in lines:
                stream.write(json.dumps(attempt.model_dump(mode="json"), sort_keys=True) + "\n")
        os.chmod(path, 0o600)
        outputs[f"attempts-{model}.jsonl"] = _sha256(path)

    vote_by_item: dict[str, dict[str, AnnotationVote]] = {
        model: {vote.item_id: vote for vote in votes} for model, votes in all_votes.items()
    }
    comparison = {"unanimous": 0, "disagreement": 0, "incomplete": 0}
    unanimous_by_status = dict.fromkeys(RESULT_STATUSES, 0)
    review_rows = 0
    comparison_path = args.output / "comparison.jsonl"
    models = ("claude-sonnet-5", "gemini-3.8-flash", "gemini-3.7-flash")
    with comparison_path.open("x") as stream:
        for item_id in sorted(pilot_ids):
            tuples = {
                model: (
                    (vote_by_item[model][item_id].status, vote_by_item[model][item_id].leaf)
                    if item_id in vote_by_item[model]
                    else (None, None)
                )
                for model in models
            }
            if any(status is None for status, _ in tuples.values()):
                agreement = "incomplete"
            elif len({(status, leaf) for status, leaf in tuples.values()}) == 1:
                agreement = "unanimous"
                unanimous_by_status[tuples[models[0]][0]] += 1
            else:
                agreement = "disagreement"
            comparison[agreement] += 1
            if agreement != "unanimous" or tuples[models[0]][0] != "labelled":
                review_rows += 1
            stream.write(
                json.dumps(
                    {
                        "item_id": item_id,
                        "agreement": agreement,
                        "votes": {
                            model: {"status": status, "leaf": leaf}
                            for model, (status, leaf) in tuples.items()
                        },
                    },
                    sort_keys=True,
                )
                + "\n"
            )
    os.chmod(comparison_path, 0o600)
    outputs["comparison.jsonl"] = _sha256(comparison_path)

    expected = {
        "unanimous": 261,
        "unanimous_by_status": {"labelled": 237, "ambiguous": 11, "insufficient_evidence": 13},
        "disagreement": 239,
        "incomplete": 0,
        "review_rows": 263,
        "gemini-3.8-flash_attempt3_valid": 26,
        "gemini-3.7-flash_attempt3_valid": 14,
        "gemini-3.8-flash_valid_before_attempt3": 474,
        "gemini-3.7-flash_valid_before_attempt3": 486,
    }
    actual = {
        "unanimous": comparison["unanimous"],
        "unanimous_by_status": unanimous_by_status,
        "disagreement": comparison["disagreement"],
        "incomplete": comparison["incomplete"],
        "review_rows": review_rows,
        "gemini-3.8-flash_attempt3_valid": counts["gemini-3.8-flash"]
        .get("3", {})
        .get("received", 0),
        "gemini-3.7-flash_attempt3_valid": counts["gemini-3.7-flash"]
        .get("3", {})
        .get("received", 0),
        "gemini-3.8-flash_valid_before_attempt3": hard_checks["gemini-3.8-flash"][
            "valid_before_final_attempt"
        ],
        "gemini-3.7-flash_valid_before_attempt3": hard_checks["gemini-3.7-flash"][
            "valid_before_final_attempt"
        ],
    }
    milestone_match = expected == actual and not mismatches

    receipt = {
        "schema_version": "benchmark-pilot-vote-rebuild-v1",
        "authorizes_consumption": False,
        "narratives_printed": False,
        "milestone_match": milestone_match,
        "mismatches": mismatches,
        "expected_counts": expected,
        "actual_counts": actual,
        "pilot_id_count": len(pilot_ids),
        "pilot_id_set_sha256": hashlib.sha256("\n".join(sorted(pilot_ids)).encode()).hexdigest(),
        "taxonomy_sha256": _sha256(args.taxonomy),
        "counts_per_model_per_attempt": counts,
        "hard_checks": hard_checks,
        "valid_votes_per_model": {model: len(votes) for model, votes in all_votes.items()},
        "input_sha256": {
            "anthropic_results": _sha256(
                args.recovery_dir / f"anthropic-{ANTHROPIC_BATCH}.results.jsonl"
            ),
            "gemini_batches": {
                name: _sha256(args.recovery_dir / f"gemini-{name.replace('/', '-')}.json")
                for names in GEMINI_BATCHES.values()
                for name in names
            },
        },
        "output_sha256": outputs,
    }
    receipt_path = args.output / "votes-receipt.json"
    with receipt_path.open("x") as stream:
        stream.write(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    os.chmod(receipt_path, 0o600)
    print(
        json.dumps(
            {
                "counts": counts,
                "actual": actual,
                "milestone_match": milestone_match,
                "mismatches": mismatches,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

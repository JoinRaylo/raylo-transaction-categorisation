"""Compare three private annotation batches and prepare Carlos's review queue.

This is comparison only. It preserves every model vote, never selects a majority
label and writes only opaque pilot IDs plus the already-sanitized transaction
prompt into the review queue. Source transaction/account/customer IDs are absent.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path

from pydantic import ValidationError

from tools.benchmark.annotation_pilot import (
    _redact_output_rationale,
    _validate_returned_model,
    parse_manifest,
    parse_prompts,
    taxonomy_leaves_bytes,
)
from tools.benchmark.prepare_eval_annotation_bundle import redact_obvious_identifiers

MEMBERSHIP_FIELDS = {
    "schema_version",
    "provider",
    "account_id",
    "transaction_id",
    "customer_id",
    "role",
    "primary_view",
    "views",
    "pilot_id",
    "source_snapshot_sha256",
    "row_sha256",
}
_SHA256 = re.compile(r"[0-9a-f]{64}")


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _write_private(path: Path, payload: bytes) -> None:
    with path.open("xb") as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def _membership_source_ids(raw: bytes, manifest) -> frozenset[str]:
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8"), newline=""))
    if (
        reader.fieldnames is None
        or len(reader.fieldnames) != len(set(reader.fieldnames))
        or set(reader.fieldnames) != MEMBERSHIP_FIELDS
    ):
        raise ValueError("source membership schema is invalid")
    rows = list(reader)
    if any(
        set(row) != MEMBERSHIP_FIELDS
        or any(type(value) is not str for value in row.values())
        or any(value != value.strip() for value in row.values())
        or row["schema_version"] != "txncat-private-eval-membership-v1"
        or row["provider"] != "plaid"
        or row["role"] != "eval"
        or not all(
            row[field] for field in ("account_id", "transaction_id", "customer_id")
        )
        or not _SHA256.fullmatch(row["source_snapshot_sha256"])
        or not _SHA256.fullmatch(row["row_sha256"])
        for row in rows
    ):
        raise ValueError("source membership row is invalid")
    item_ids = {item.item_id for item in manifest.items}
    membership_ids = [row["pilot_id"] for row in rows]
    if (
        len(membership_ids) != len(set(membership_ids))
        or set(membership_ids) != item_ids
    ):
        raise ValueError("source membership does not match the annotation manifest")
    item_by_id = {item.item_id: item for item in manifest.items}
    for row in rows:
        item = item_by_id[row["pilot_id"]]
        membership_views = tuple(row["views"].split("+"))
        if (
            not membership_views
            or any(not view for view in membership_views)
            or len(membership_views) != len(set(membership_views))
            or membership_views != item.views
            or row["primary_view"] not in membership_views
            or item.subject_sha256 != row["row_sha256"]
            or item.reservation_sha256 != _sha256(_canonical(row))
            or item.source_snapshot_sha256 != row["source_snapshot_sha256"]
        ):
            raise ValueError("source membership row is not bound to the manifest")
    return frozenset(
        row[field]
        for row in rows
        for field in ("account_id", "transaction_id", "customer_id")
    )


def _validate_prompt_text(prompt: str, strict_json_loads) -> None:
    prefix = "Transaction data (untrusted JSON):\n"
    if not prompt.startswith(prefix):
        raise ValueError("annotation prompt envelope is invalid")
    transaction = strict_json_loads(prompt.removeprefix(prefix))
    if type(transaction) is not dict or set(transaction) != {
        "merchant",
        "description",
        "amount",
        "direction",
    }:
        raise ValueError("annotation prompt transaction schema is invalid")
    for field in ("merchant", "description"):
        value = transaction[field]
        if type(value) is not str or redact_obvious_identifiers(value)[0] != value:
            raise ValueError("annotation prompt contains an unredacted identifier")


def _assert_no_exact_source_ids(texts: list[str], source_ids: frozenset[str]) -> None:
    material = "\n".join(texts)
    if any(source_id in material for source_id in source_ids):
        raise ValueError("annotation review material contains a source identifier")


def _publish_atomically(output: Path, payloads: dict[str, bytes]) -> None:
    lock_path = output.parent / f".{output.name}.lock"
    lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    staging = None
    try:
        if output.exists():
            raise ValueError("refusing to overwrite an annotation review queue")
        staging = Path(
            tempfile.mkdtemp(prefix=f".{output.name}.staging-", dir=output.parent)
        )
        os.chmod(staging, 0o700)
        for name, payload in payloads.items():
            _write_private(staging / name, payload)
        if output.exists():
            raise ValueError("annotation review queue appeared during publication")
        os.rename(staging, output)
        staging = None
    finally:
        os.close(lock_fd)
        try:
            os.unlink(lock_path)
        except FileNotFoundError:
            pass
        if staging is not None:
            shutil.rmtree(staging)


def build_review_queue(
    *,
    app_root: Path,
    manifest_path: Path,
    prompts_path: Path,
    taxonomy_path: Path,
    membership_path: Path,
    batch_paths: tuple[Path, ...],
    output: Path,
) -> dict:
    if (
        output.name != "adjudication"
        or output.parent.name != "annotation_method_experiment"
    ):
        raise ValueError(
            "review queue must be an adjudication directory under the experiment"
        )
    if len(batch_paths) != 3 or len(set(path.resolve() for path in batch_paths)) != 3:
        raise ValueError("exactly three distinct annotation batches are required")

    sys.path.insert(0, str(app_root / "lib/raylo-txncat/src"))
    from raylo_txncat.benchmark_annotation import (  # noqa: PLC0415
        AnnotationBatch,
        PilotManifest,
        agreement_summary,
        compare_batches,
    )
    from raylo_txncat.hashing import strict_json_loads  # noqa: PLC0415

    manifest_raw = manifest_path.read_bytes()
    prompts_raw = prompts_path.read_bytes()
    taxonomy_raw = taxonomy_path.read_bytes()
    membership_raw = membership_path.read_bytes()
    manifest = parse_manifest(manifest_raw, PilotManifest, strict_json_loads)
    prompts = parse_prompts(prompts_raw, manifest, strict_json_loads)
    prompt_by_id = {prompt.item_id: prompt for prompt in prompts}
    item_by_id = {item.item_id: item for item in manifest.items}
    leaves = taxonomy_leaves_bytes(taxonomy_raw)
    taxonomy_sha256 = _sha256(taxonomy_raw)
    if any(item.taxonomy_sha256 != taxonomy_sha256 for item in manifest.items):
        raise ValueError("taxonomy file is not bound to the annotation manifest")
    source_ids = _membership_source_ids(membership_raw, manifest)
    for prompt in prompts:
        _validate_prompt_text(prompt.prompt, strict_json_loads)

    batches = []
    batch_hashes = {}
    for path in batch_paths:
        raw = path.read_bytes()
        strict_json_loads(raw)
        batch = AnnotationBatch.model_validate_json(raw, strict=True)
        if batch.model in batch_hashes:
            raise ValueError("duplicate annotation model batch")
        for vote in batch.votes:
            _validate_returned_model(batch.model, vote.returned_model)
            if _redact_output_rationale(vote.rationale) != vote.rationale:
                raise ValueError(
                    "annotation rationale contains an unredacted identifier"
                )
        for attempt in batch.attempts:
            if attempt.status == "received":
                _validate_returned_model(batch.model, attempt.returned_model)
        received_models = {
            (
                attempt.item_id,
                attempt.job_id,
                attempt.provider_request_id,
                attempt.attempt,
            ): attempt.returned_model
            for attempt in batch.attempts
            if attempt.status == "received"
        }
        if any(
            received_models[
                (
                    vote.item_id,
                    vote.provider_job_id,
                    vote.provider_request_id,
                    vote.attempt,
                )
            ]
            != vote.returned_model
            for vote in batch.votes
        ):
            raise ValueError("vote and attempt returned-model identities disagree")
        batches.append(batch)
        batch_hashes[batch.model] = _sha256(raw)

    records = compare_batches(
        manifest,
        tuple(batches),
        taxonomy_leaves=leaves,
    )
    counts = agreement_summary(records)
    if counts["incomplete"]:
        raise ValueError(
            "incomplete annotations must be recovered before Carlos review"
        )
    queue = []
    by_view: dict[str, Counter[str]] = {}
    for record in records:
        item = item_by_id[record.item_id]
        for view in item.views:
            by_view.setdefault(view, Counter())[record.status] += 1
        if record.status == "unanimous":
            continue
        if record.status != "disagreement" or len(record.votes) != 3:
            raise ValueError("only complete three-model disagreements may be reviewed")
        prompt = prompt_by_id[record.item_id]
        queue.append(
            {
                "schema_version": "txncat-annotation-review-item-v1",
                "item_id": record.item_id,
                "views": list(item.views),
                "prompt": prompt.prompt,
                "votes": [
                    {
                        "model": vote.model,
                        "status": vote.status,
                        "leaf": vote.leaf,
                        "confidence": vote.confidence,
                        "rationale": vote.rationale,
                    }
                    for vote in record.votes
                ],
                "comparison_status": record.status,
                "carlos_resolution_required": True,
            }
        )

    summary = {
        "schema_version": "txncat-annotation-review-summary-v1",
        "manifest_sha256": manifest.manifest_sha256,
        "rows": len(records),
        "models": sorted(batch_hashes),
        "model_vote_counts": {
            batch.model: len(batch.votes)
            for batch in sorted(batches, key=lambda x: x.model)
        },
        "comparison": counts,
        "review_queue_rows": len(queue),
        "by_view": {
            view: {
                status: view_counts.get(status, 0)
                for status in ("unanimous", "disagreement", "incomplete")
            }
            for view, view_counts in sorted(by_view.items())
        },
        "auto_adjudication": False,
        "carlos_decisions": 0,
        "gold_labels_created": 0,
        "authorizes_consumption": False,
    }

    agreements_payload = b"".join(
        _canonical(record.model_dump(mode="json")) + b"\n" for record in records
    )
    queue_payload = b"".join(_canonical(row) + b"\n" for row in queue)
    summary_payload = (
        json.dumps(summary, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    )
    _assert_no_exact_source_ids(
        [prompt.prompt for prompt in prompts]
        + [vote.rationale for batch in batches for vote in batch.votes]
        + [agreements_payload.decode("utf-8"), queue_payload.decode("utf-8")],
        source_ids,
    )
    receipt = {
        "schema_version": "txncat-annotation-review-receipt-v1",
        "manifest_sha256": manifest.manifest_sha256,
        "manifest_file_sha256": _sha256(manifest_raw),
        "prompts_sha256": _sha256(prompts_raw),
        "taxonomy_sha256": taxonomy_sha256,
        "membership_sha256": _sha256(membership_raw),
        "batch_sha256": dict(sorted(batch_hashes.items())),
        "agreements_sha256": _sha256(agreements_payload),
        "review_queue_sha256": _sha256(queue_payload),
        "summary_sha256": _sha256(summary_payload),
        "rows": len(records),
        "review_queue_rows": len(queue),
        "explicit_source_identity_fields": 0,
        "exact_source_identifier_matches": 0,
        "auto_adjudication": False,
        "carlos_decisions": 0,
        "gold_labels_created": 0,
        "authorizes_consumption": False,
    }
    receipt_payload = (
        json.dumps(receipt, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    )
    os.umask(0o077)
    _publish_atomically(
        output,
        {
            "agreements.jsonl": agreements_payload,
            "review_queue.jsonl": queue_payload,
            "summary.json": summary_payload,
            "receipt.json": receipt_payload,
        },
    )
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--prompts", type=Path, required=True)
    parser.add_argument("--taxonomy", type=Path, required=True)
    parser.add_argument("--membership", type=Path, required=True)
    parser.add_argument("--batch", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = build_review_queue(
        app_root=args.app_root,
        manifest_path=args.manifest,
        prompts_path=args.prompts,
        taxonomy_path=args.taxonomy,
        membership_path=args.membership,
        batch_paths=tuple(args.batch),
        output=args.output,
    )
    print(
        f"Prepared {receipt['review_queue_rows']}-item Carlos review queue; "
        "no automatic adjudication."
    )


if __name__ == "__main__":
    try:
        main()
    except (OSError, TypeError, ValueError, ValidationError) as exc:
        raise SystemExit(
            f"Annotation review preparation failed closed: {type(exc).__name__}"
        ) from None

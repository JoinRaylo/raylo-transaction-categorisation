"""Private ID-bearing membership sidecars for tuning exports.

The model JSONL stays byte-compatible with the existing training consumers.  This
module writes a separate, minimal lookup keyed by the Plaid provider identifiers
that B02 uses to derive its private observation key.  Rows from older sources that
do not carry those identifiers are reported as unresolved and are never silently
treated as absent from training.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import pathlib
import re
import tempfile
from collections import Counter
from dataclasses import dataclass
from typing import Literal, Mapping


MembershipRole = Literal["train", "selection", "eval", "excluded"]
IdentityStatus = Literal["exact", "unavailable"]
Provider = Literal["plaid", "equifax"]

_SHA256 = re.compile(r"[0-9a-f]{64}")
_SOURCE = re.compile(r"[a-z][a-z0-9_]*")


def canonical_sha256(value: object) -> str:
    """Hash a JSON-compatible source row deterministically."""

    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class SourceMembership:
    """Identity evidence attached to one effective training example."""

    source: str
    identity_status: IdentityStatus
    source_row_sha256: str
    provider: Provider | None = None
    account_id: str | None = None
    transaction_id: str | None = None
    customer_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.source, str) or not _SOURCE.fullmatch(self.source):
            raise ValueError("source must be a lowercase identifier")
        if self.identity_status not in {"exact", "unavailable"}:
            raise ValueError("unsupported identity status")
        if not isinstance(self.source_row_sha256, str) or not _SHA256.fullmatch(
            self.source_row_sha256
        ):
            raise ValueError("source row digest must be lowercase SHA-256")
        if self.provider not in {None, "plaid", "equifax"}:
            raise ValueError("unsupported provider")

        identifiers = (self.account_id, self.transaction_id, self.customer_id)
        if self.identity_status == "exact":
            if self.provider != "plaid":
                raise ValueError("exact tuning identity must be customer-linked Plaid")
            if any(not isinstance(value, str) or not value.strip() for value in identifiers):
                raise ValueError("exact identity requires account, transaction and customer IDs")
        elif any(value is not None for value in identifiers):
            raise ValueError("unavailable identity cannot assert provider identifiers")


@dataclass(frozen=True, slots=True)
class TrackedExample:
    """A model example paired with private source membership metadata."""

    messages: dict[str, list[dict[str, str]]]
    membership: SourceMembership


@dataclass(frozen=True, slots=True)
class MembershipAssignment:
    """One effective output row assigned to a permanent data role."""

    role: MembershipRole
    membership: SourceMembership

    def __post_init__(self) -> None:
        if self.role not in {"train", "selection", "eval", "excluded"}:
            raise ValueError("unsupported membership role")


def exact_plaid_membership(*, source: str, row: Mapping[str, object]) -> SourceMembership:
    """Create exact identity evidence for a newly fetched Plaid source row."""

    account_id = row.get("account_id")
    transaction_id = row.get("transaction_id")
    customer_id = row.get("customer_id")
    return SourceMembership(
        source=source,
        identity_status="exact",
        source_row_sha256=canonical_sha256(dict(row)),
        provider="plaid",
        account_id=account_id if isinstance(account_id, str) else None,
        transaction_id=transaction_id if isinstance(transaction_id, str) else None,
        customer_id=customer_id if isinstance(customer_id, str) else None,
    )


def unavailable_membership(
    *,
    source: str,
    row: Mapping[str, object],
    provider: str | None = None,
) -> SourceMembership:
    """Record a legacy row without inventing a transaction identity."""

    normalised_provider = provider.strip().lower() if isinstance(provider, str) else None
    if normalised_provider not in {"plaid", "equifax"}:
        normalised_provider = None
    return SourceMembership(
        source=source,
        identity_status="unavailable",
        source_row_sha256=canonical_sha256(dict(row)),
        provider=normalised_provider,
    )


_LOOKUP_FIELDS = [
    "schema_version",
    "provider",
    "account_id",
    "transaction_id",
    "role",
    "source",
    "source_row_sha256",
    "current_export_row_count",
]


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _read_previous_export(
    *,
    lookup_path: pathlib.Path,
    coverage_path: pathlib.Path,
    model_paths: Mapping[str, pathlib.Path],
) -> dict[tuple[str, str, str], dict[str, object]]:
    """Read and verify the last committed export before extending membership."""

    if not lookup_path.exists() and not coverage_path.exists():
        return {}
    if not lookup_path.exists() or not coverage_path.exists():
        raise ValueError("previous membership export is incomplete")

    lookup_text = lookup_path.read_text(encoding="utf-8")
    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
    if coverage.get("schema_version") != "tuning-membership-coverage-v2":
        raise ValueError("unsupported previous membership coverage")
    if coverage.get("lookup_sha256") != _sha256_text(lookup_text):
        raise ValueError("previous membership lookup digest does not match")

    previous_models = coverage.get("model_files")
    if not isinstance(previous_models, dict):
        raise ValueError("previous membership coverage has no model bindings")
    for role, path in model_paths.items():
        expected = previous_models.get(role)
        if not isinstance(expected, dict) or not path.exists():
            raise ValueError("previous membership model export is incomplete")
        expected_artifact = "train.jsonl" if role == "train" else "val.jsonl"
        if expected.get("artifact_name") != expected_artifact:
            raise ValueError("previous membership model artifact name does not match")
        if expected.get("sha256") != hashlib.sha256(path.read_bytes()).hexdigest():
            raise ValueError("previous membership model digest does not match")

    previous: dict[tuple[str, str, str], dict[str, object]] = {}
    reader = csv.DictReader(io.StringIO(lookup_text))
    if reader.fieldnames != _LOOKUP_FIELDS:
        raise ValueError("previous membership lookup schema does not match")
    for row in reader:
        if row["schema_version"] != "tuning-membership-lookup-v2":
            raise ValueError("unsupported previous membership lookup row")
        key = (row["provider"], row["account_id"], row["transaction_id"])
        if key in previous or not all(key):
            raise ValueError("previous membership lookup contains an invalid identity")
        if row["role"] not in {"train", "selection", "eval", "excluded"}:
            raise ValueError("previous membership lookup contains an invalid role")
        if not _SOURCE.fullmatch(row["source"]) or not _SHA256.fullmatch(
            row["source_row_sha256"]
        ):
            raise ValueError("previous membership lookup contains invalid provenance")
        previous[key] = {
            **row,
            "current_export_row_count": 0,
        }
    return previous


def _render_membership_artifacts(
    assignments: list[MembershipAssignment],
    *,
    previous: dict[tuple[str, str, str], dict[str, object]],
    model_texts: Mapping[str, str],
    model_paths: Mapping[str, pathlib.Path],
) -> tuple[str, str, dict[str, object]]:
    """Validate the complete export and render it without mutating output files."""

    exact = {key: dict(value) for key, value in previous.items()}
    role_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    exact_role_counts: Counter[str] = Counter()
    unresolved_role_counts: Counter[str] = Counter()
    current_exact_keys: set[tuple[str, str, str]] = set()

    for assignment in assignments:
        membership = assignment.membership
        role_counts[assignment.role] += 1
        source_counts[f"{assignment.role}:{membership.source}"] += 1
        if membership.identity_status == "unavailable":
            unresolved_role_counts[assignment.role] += 1
            continue

        exact_role_counts[assignment.role] += 1
        key = (
            membership.provider or "",
            membership.account_id or "",
            membership.transaction_id or "",
        )
        current_exact_keys.add(key)
        prior = exact.get(key)
        current = {
            "schema_version": "tuning-membership-lookup-v2",
            "provider": key[0],
            "account_id": key[1],
            "transaction_id": key[2],
            "role": assignment.role,
            "source": membership.source,
            "source_row_sha256": membership.source_row_sha256,
            "current_export_row_count": 1,
        }
        if prior is None:
            exact[key] = current
            continue
        immutable_fields = ("role", "source", "source_row_sha256")
        if any(prior[field] != current[field] for field in immutable_fields):
            raise ValueError(
                "provider identity is assigned across roles, sources, or changed payloads"
            )
        prior["current_export_row_count"] = int(prior["current_export_row_count"]) + 1

    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=_LOOKUP_FIELDS, lineterminator="\n")
    writer.writeheader()
    for key in sorted(exact):
        writer.writerow(exact[key])
    lookup_text = buffer.getvalue()

    coverage: dict[str, object] = {
        "schema_version": "tuning-membership-coverage-v2",
        "lookup_sha256": _sha256_text(lookup_text),
        "effective_output_rows": len(assignments),
        "current_unique_exact_transactions": len(current_exact_keys),
        "permanent_unique_exact_transactions": len(exact),
        "model_files": {
            role: {
                "artifact_name": "train.jsonl" if role == "train" else "val.jsonl",
                "sha256": _sha256_text(model_texts[role]),
                "rows": model_texts[role].count("\n"),
            }
            for role in ("train", "selection")
        },
        "roles": {
            role: {
                "effective_rows": role_counts[role],
                "exact_identity_rows": exact_role_counts[role],
                "unresolved_identity_rows": unresolved_role_counts[role],
            }
            for role in sorted(role_counts)
        },
        "sources": dict(sorted(source_counts.items())),
        "limitations": [
            "Only exact customer-linked Plaid provider IDs appear in the lookup.",
            "Legacy unresolved rows are counted here; lookup absence is not proof of no historical exposure.",
            "The lookup is a private membership record, not consumption authority.",
        ],
    }
    coverage_text = json.dumps(coverage, indent=2, sort_keys=True) + "\n"
    return lookup_text, coverage_text, coverage


def _write_temp(path: pathlib.Path, text: str) -> pathlib.Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: pathlib.Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as handle:
            temporary = pathlib.Path(handle.name)
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        return temporary
    except BaseException:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise


def verify_training_export(
    *,
    train_path: pathlib.Path,
    selection_path: pathlib.Path,
    lookup_path: pathlib.Path,
    coverage_path: pathlib.Path,
) -> dict[str, object]:
    """Verify the committed lookup and model hashes before any consumer use."""

    if not lookup_path.exists() or not coverage_path.exists():
        raise ValueError("training membership export is incomplete")
    _read_previous_export(
        lookup_path=lookup_path,
        coverage_path=coverage_path,
        model_paths={"train": train_path, "selection": selection_path},
    )
    return json.loads(coverage_path.read_text(encoding="utf-8"))


def publish_training_export(
    train: list[TrackedExample],
    selection: list[TrackedExample],
    *,
    train_path: pathlib.Path,
    selection_path: pathlib.Path,
    lookup_path: pathlib.Path,
    coverage_path: pathlib.Path,
) -> dict[str, object]:
    """Validate, stage and publish model files plus their permanent ID lookup.

    The coverage file is the commit marker and is replaced last. A rejected build
    performs no replacement; an interrupted replacement is detected by the hashes
    in the previous coverage file on the next invocation.
    """

    model_paths = {"train": train_path, "selection": selection_path}
    model_texts = {
        "train": "".join(json.dumps(ex.messages) + "\n" for ex in train),
        "selection": "".join(json.dumps(ex.messages) + "\n" for ex in selection),
    }
    previous = _read_previous_export(
        lookup_path=lookup_path,
        coverage_path=coverage_path,
        model_paths=model_paths,
    )
    assignments = (
        [MembershipAssignment(role="train", membership=ex.membership) for ex in train]
        + [MembershipAssignment(role="selection", membership=ex.membership) for ex in selection]
    )
    lookup_text, coverage_text, coverage = _render_membership_artifacts(
        assignments,
        previous=previous,
        model_texts=model_texts,
        model_paths=model_paths,
    )

    rendered = {
        lookup_path: lookup_text,
        train_path: model_texts["train"],
        selection_path: model_texts["selection"],
        coverage_path: coverage_text,
    }
    temporary: dict[pathlib.Path, pathlib.Path] = {}
    try:
        for path, text in rendered.items():
            temporary[path] = _write_temp(path, text)
        # Coverage is the commit marker and must be the final replacement.
        for path in (lookup_path, train_path, selection_path, coverage_path):
            os.replace(temporary[path], path)
            temporary.pop(path)
    finally:
        for path in temporary.values():
            path.unlink(missing_ok=True)
    return coverage

"""Build a private, evaluation-first 500-row annotation pilot.

The input is the existing receipt-bound customer-linked Plaid draw plus its
opaque historical-exposure profile and lineage extract.  The output is a local
private membership lookup and annotation payload; this script never calls a
provider, labels a row, trains a model or writes cloud state.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal


View = Literal["representative", "unseen_input", "unfamiliar_merchant"]
VIEW_ORDER: tuple[View, ...] = (
    "unfamiliar_merchant",
    "unseen_input",
    "representative",
)
MEMBERSHIP_FIELDS = (
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
)
_SHA256 = re.compile(r"[0-9a-f]{64}")


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _sha(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _file_sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise ValueError(f"{path} is not a JSON object")
    return value


def _load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                raise ValueError(f"{path} contains a blank row")
            row = json.loads(line)
            if type(row) is not dict:
                raise ValueError(f"{path} contains a non-object row")
            rows.append(row)
    return rows


def _write_private(path: Path, data: bytes) -> None:
    with path.open("xb") as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


@dataclass(frozen=True, slots=True)
class PilotCandidate:
    index: int
    row: dict
    opaque: dict

    @property
    def customer_block(self) -> str:
        value = self.row.get("customer_id")
        if not isinstance(value, str) or not value:
            raise ValueError("candidate customer block is invalid")
        return value

    @property
    def opaque_customer(self) -> str:
        value = self.opaque.get("customer")
        if not isinstance(value, str) or not _SHA256.fullmatch(value):
            raise ValueError("opaque candidate customer token is invalid")
        return value

    @property
    def unseen(self) -> bool:
        sources = self.opaque.get("input_sources")
        if type(sources) is not list:
            raise ValueError("opaque candidate input sources are invalid")
        return not sources

    @property
    def unfamiliar(self) -> bool:
        known = self.opaque.get("merchant_known_sources")
        present = self.opaque.get("merchant_present")
        if type(known) is not list or type(present) is not bool:
            raise ValueError("opaque candidate merchant evidence is invalid")
        return self.unseen and present and not known


def _block_eligible(rows: tuple[PilotCandidate, ...], view: View) -> bool:
    if view == "unfamiliar_merchant":
        return all(row.unfamiliar for row in rows)
    if view == "unseen_input":
        return all(row.unseen for row in rows)
    return True


def _rank(seed: str, view: View, block: str) -> str:
    return _sha(
        {
            "algorithm": "txncat-private-pilot-block-rank-v1",
            "seed": seed,
            "view": view,
            "customer_block": block,
        }
    )


def _exact_blocks(
    blocks: dict[str, tuple[PilotCandidate, ...]],
    *,
    target: int,
    seed: str,
    view: View,
    unavailable: set[str],
) -> tuple[str, ...]:
    """Choose a deterministic exact-row subset of whole customer blocks."""

    ranked = sorted(
        (
            (block, rows)
            for block, rows in blocks.items()
            if block not in unavailable and _block_eligible(rows, view)
        ),
        key=lambda item: (_rank(seed, view, item[0]), item[0]),
    )
    reachable: dict[int, tuple[str, ...]] = {0: ()}
    for block, rows in ranked:
        size = len(rows)
        for total, chosen in sorted(tuple(reachable.items()), reverse=True):
            new_total = total + size
            if new_total <= target and new_total not in reachable:
                reachable[new_total] = (*chosen, block)
        if target in reachable:
            return reachable[target]
    raise ValueError(f"{view} cannot fill exact target {target} from whole customer blocks")


def allocate_pilot(
    candidates: list[PilotCandidate],
    *,
    budgets: dict[View, int],
    seed: str,
) -> dict[int, View]:
    """Allocate strict views first, then representative rows, by whole customer."""

    if set(budgets) != set(VIEW_ORDER) or any(
        type(value) is not int or value <= 0 for value in budgets.values()
    ):
        raise ValueError("all three positive integer view budgets are required")
    if not isinstance(seed, str) or not seed.strip():
        raise ValueError("allocation seed is required")
    by_block: defaultdict[str, list[PilotCandidate]] = defaultdict(list)
    for candidate in candidates:
        by_block[candidate.customer_block].append(candidate)
    blocks = {key: tuple(rows) for key, rows in by_block.items()}

    used: set[str] = set()
    assignments: dict[int, View] = {}
    for view in VIEW_ORDER:
        selected = _exact_blocks(
            blocks,
            target=budgets[view],
            seed=seed,
            view=view,
            unavailable=used,
        )
        used.update(selected)
        for block in selected:
            for candidate in blocks[block]:
                assignments[candidate.index] = view
    if len(assignments) != sum(budgets.values()):
        raise ValueError("pilot allocation row count does not match its budgets")
    return assignments


def _validate_customer_token_mapping(candidates: Iterable[PilotCandidate]) -> None:
    customer_tokens: dict[str, str] = {}
    token_customers: dict[str, str] = {}
    for candidate in candidates:
        prior_token = customer_tokens.setdefault(
            candidate.customer_block, candidate.opaque_customer
        )
        prior_customer = token_customers.setdefault(
            candidate.opaque_customer, candidate.customer_block
        )
        if (
            prior_token != candidate.opaque_customer
            or prior_customer != candidate.customer_block
        ):
            raise ValueError("opaque customer grouping is inconsistent")


def _validate_lineage_rows(
    *,
    events: dict[tuple[str, str], str],
    lineage: Iterable[dict],
) -> None:
    current_events: Counter[tuple[str, str]] = Counter()
    for row in lineage:
        event = (row.get("account_id"), row.get("transaction_id"))
        if event not in events:
            raise ValueError("lineage contains an unexpected event")
        if row.get("source_kind") == "current_materialized":
            if row.get("linked_customer_id") != events[event]:
                raise ValueError("lineage customer does not match candidate")
            current_events[event] += 1
        else:
            historical_customer = row.get("source_customer_id")
            if historical_customer not in {None, "", events[event]}:
                raise ValueError("historical lineage contradicts the linked customer")
    if set(current_events) != set(events) or any(
        count != 1 for count in current_events.values()
    ):
        raise ValueError("current lineage does not cover every candidate event")


@dataclass(frozen=True, slots=True)
class MembershipProtection:
    """Exact identities and connected groups already assigned to a data role."""

    events: frozenset[tuple[str, str]] = frozenset()
    accounts: frozenset[str] = frozenset()
    customers: frozenset[str] = frozenset()


def filter_separated_candidates(
    candidates: list[PilotCandidate],
    *,
    protected: MembershipProtection,
) -> tuple[list[PilotCandidate], dict[str, int]]:
    """Remove whole customer blocks touched by an existing data-role assignment."""

    by_block: defaultdict[str, list[PilotCandidate]] = defaultdict(list)
    for candidate in candidates:
        by_block[candidate.customer_block].append(candidate)

    membership_blocks: set[str] = set()
    exact_event_overlaps = 0
    connected_membership_overlaps = 0
    historical_input_exposure_rows = 0
    for block, rows in by_block.items():
        for candidate in rows:
            row = candidate.row
            event = (row["account_id"], row["transaction_id"])
            event_overlap = event in protected.events
            connected_overlap = (
                row["account_id"] in protected.accounts
                or row["customer_id"] in protected.customers
            )
            if event_overlap:
                exact_event_overlaps += 1
            if connected_overlap:
                connected_membership_overlaps += 1
            if event_overlap or connected_overlap:
                membership_blocks.add(block)
            if not candidate.unseen:
                historical_input_exposure_rows += 1

    eligible = [
        candidate
        for candidate in candidates
        if candidate.customer_block not in membership_blocks
    ]
    return eligible, {
        "exact_event_overlap_rows": exact_event_overlaps,
        "connected_membership_overlap_rows": connected_membership_overlaps,
        "membership_excluded_block_rows": sum(
            len(by_block[block]) for block in membership_blocks
        ),
        "historical_input_exposure_rows": historical_input_exposure_rows,
        "historical_input_exposure_block_rows": sum(
            len(rows) for rows in by_block.values() if any(not row.unseen for row in rows)
        ),
        "eligible_after_separation": len(eligible),
    }


def _validate_inputs(
    *,
    candidates_dir: Path,
    profile_dir: Path,
    lineage_dir: Path,
) -> tuple[list[dict], list[dict], dict, dict, dict]:
    candidate_path = candidates_dir / "candidates.jsonl"
    candidate_receipt_path = candidates_dir / "receipt.json"
    profile_path = profile_dir / "profile.json"
    opaque_path = profile_dir / "opaque-candidates.jsonl"
    lineage_path = lineage_dir / "lineage.jsonl"
    lineage_receipt_path = lineage_dir / "receipt.json"

    candidate_receipt = _load_json(candidate_receipt_path)
    profile = _load_json(profile_path)
    lineage_receipt = _load_json(lineage_receipt_path)
    if (
        candidate_receipt.get("schema_version") != "benchmark-candidate-extract-v1"
        or candidate_receipt.get("purpose")
        != "private_customer_linked_plaid_candidate_draw"
        or candidate_receipt.get("executed") is not True
        or candidate_receipt.get("authorizes_consumption") is not False
        or candidate_receipt.get("source_kind")
        != "customer_linked_plaid_materialized"
        or candidate_receipt.get("anonymous_id_recovery") is not False
        or candidate_receipt.get("result_sha256") != _file_sha256(candidate_path)
    ):
        raise ValueError("candidate draw is outside the approved linked-only contract")
    if (
        profile.get("schema_version") != "benchmark-admission-profile-v1"
        or profile.get("source_snapshot_sha256")
        != candidate_receipt["result_sha256"]
        or profile.get("authorizes_consumption") is not False
        or profile.get("rows_reserved_or_labelled") != 0
        or profile.get("lineage", {}).get("candidate_receipt_sha256")
        != _file_sha256(candidate_receipt_path)
        or profile.get("lineage", {}).get("opaque_candidates_sha256")
        != _file_sha256(opaque_path)
        or profile.get("scope_contract_sha256")
        != candidate_receipt.get("scope_contract_sha256")
    ):
        raise ValueError("opaque exposure profile is not bound to the candidate draw")
    if (
        lineage_receipt.get("schema_version")
        != "benchmark-candidate-lineage-extract-v1"
        or lineage_receipt.get("purpose")
        != "private_customer_linked_candidate_lineage_evidence"
        or lineage_receipt.get("executed") is not True
        or lineage_receipt.get("authorizes_consumption") is not False
        or lineage_receipt.get("candidate_result_sha256")
        != candidate_receipt["result_sha256"]
        or lineage_receipt.get("candidate_profile_sha256") != _file_sha256(profile_path)
        or lineage_receipt.get("result_sha256") != _file_sha256(lineage_path)
    ):
        raise ValueError("candidate lineage is incomplete or references another draw")

    candidates = _load_jsonl(candidate_path)
    opaque = _load_jsonl(opaque_path)
    lineage = _load_jsonl(lineage_path)
    expected_rows = candidate_receipt.get("result_rows")
    if type(expected_rows) is not int or len(candidates) != expected_rows or len(opaque) != len(
        candidates
    ):
        raise ValueError("candidate/profile row counts do not match their receipt")
    if profile.get("candidate_rows") != len(candidates):
        raise ValueError("profile candidate count does not match")

    events: dict[tuple[str, str], str] = {}
    account_customers: dict[str, str] = {}
    for row in candidates:
        required = (
            "account_id",
            "transaction_id",
            "customer_id",
            "assessment_id",
            "checkout_id",
            "user_id",
        )
        if any(type(row.get(field)) is not str or not row[field] for field in required):
            raise ValueError("candidate row is missing linked identity")
        link_counts = (
            "assessment_checkout_count",
            "checkout_user_count",
            "user_customer_count",
            "customer_record_count",
        )
        if any(type(row.get(field)) is not int or row[field] != 1 for field in link_counts):
            raise ValueError("candidate row is not backed by unique current links")
        event = (row["account_id"], row["transaction_id"])
        if event in events:
            raise ValueError("candidate draw contains duplicate events")
        events[event] = row["customer_id"]
        previous_customer = account_customers.setdefault(row["account_id"], row["customer_id"])
        if previous_customer != row["customer_id"]:
            raise ValueError("candidate account crosses customer blocks")
    _validate_lineage_rows(events=events, lineage=lineage)
    return candidates, opaque, candidate_receipt, profile, lineage_receipt


def _existing_protection(paths: Iterable[Path]) -> MembershipProtection:
    events: set[tuple[str, str]] = set()
    accounts: set[str] = set()
    customers: set[str] = set()
    for path in paths:
        with path.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            required = {"provider", "account_id", "transaction_id", "role"}
            if reader.fieldnames is None or not required <= set(reader.fieldnames):
                raise ValueError("existing membership lookup schema is incomplete")
            for row in reader:
                if row["provider"] != "plaid" or row["role"] not in {
                    "train",
                    "selection",
                    "eval",
                    "excluded",
                }:
                    raise ValueError("existing membership row is invalid")
                event = (row["account_id"], row["transaction_id"])
                if not all(event):
                    raise ValueError("existing membership identity is blank")
                events.add(event)
                accounts.add(row["account_id"])
                customer = row.get("customer_id", "")
                if customer:
                    customers.add(customer)
    return MembershipProtection(
        events=frozenset(events),
        accounts=frozenset(accounts),
        customers=frozenset(customers),
    )


def _membership_input_receipts(paths: Iterable[Path]) -> list[dict[str, object]]:
    receipts = []
    for path in paths:
        with path.open(newline="", encoding="utf-8") as stream:
            rows = sum(1 for _ in csv.DictReader(stream))
        receipts.append({"sha256": _file_sha256(path), "rows": rows})
    return receipts


def _payload(candidate: PilotCandidate, primary: View, snapshot: str) -> tuple[dict, dict]:
    row = candidate.row
    amount = row.get("amount")
    try:
        absolute_amount = abs(float(amount))
    except (TypeError, ValueError):
        raise ValueError("candidate amount is invalid") from None
    if not math.isfinite(absolute_amount):
        raise ValueError("candidate amount is non-finite")
    direction = row.get("direction")
    if direction not in {"credit", "debit"}:
        raise ValueError("candidate direction is invalid")
    description = row.get("description")
    if description is None:
        description = row.get("transaction_name")
    if description is None:
        description = ""
    if type(description) is not str:
        raise ValueError("candidate description is invalid")
    merchant = row.get("merchant_name") or ""
    if type(merchant) is not str:
        raise ValueError("candidate merchant is invalid")

    views: list[View] = ["representative"]
    if candidate.unseen:
        views.append("unseen_input")
    if candidate.unfamiliar:
        views.append("unfamiliar_merchant")
    pilot_id = "pilot-v1-" + _sha(
        {
            "source_snapshot_sha256": snapshot,
            "account_id": row["account_id"],
            "transaction_id": row["transaction_id"],
        }
    )
    annotation = {
        "schema_version": "txncat-private-eval-pilot-item-v1",
        "pilot_id": pilot_id,
        "primary_view": primary,
        "views": views,
        "merchant": merchant,
        "description": description,
        "amount": absolute_amount,
        "direction": direction,
        "source_stratum": row.get("source_stratum", "unknown"),
    }
    membership = {
        "schema_version": "txncat-private-eval-membership-v1",
        "provider": "plaid",
        "account_id": row["account_id"],
        "transaction_id": row["transaction_id"],
        "customer_id": row["customer_id"],
        "role": "eval",
        "primary_view": primary,
        "views": "+".join(views),
        "pilot_id": pilot_id,
        "source_snapshot_sha256": snapshot,
        "row_sha256": _sha(annotation),
    }
    return annotation, membership


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--lineage", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", default="eval-pilot-v1")
    parser.add_argument("--representative", type=int, default=250)
    parser.add_argument("--unseen-input", type=int, default=150)
    parser.add_argument("--unfamiliar-merchant", type=int, default=100)
    parser.add_argument("--existing-membership", type=Path, action="append", default=[])
    args = parser.parse_args()
    os.umask(0o077)
    candidates, opaque, candidate_receipt, profile, lineage_receipt = _validate_inputs(
        candidates_dir=args.candidates,
        profile_dir=args.profile,
        lineage_dir=args.lineage,
    )
    protected = _existing_protection(args.existing_membership)
    pool = []
    for index, (row, opaque_row) in enumerate(zip(candidates, opaque, strict=True)):
        if opaque_row.get("source_snapshot_sha256") != candidate_receipt["result_sha256"]:
            raise ValueError("opaque candidate references another source snapshot")
        observation = opaque_row.get("observation")
        candidate_id = opaque_row.get("candidate_id")
        if (
            not isinstance(observation, str)
            or not _SHA256.fullmatch(observation)
            or not isinstance(candidate_id, str)
            or candidate_id
            != _sha(
                {
                    "source": candidate_receipt["result_sha256"],
                    "event": observation,
                }
            )
            or opaque_row.get("source_stratum") != row.get("source_stratum")
            or opaque_row.get("authorizes_consumption") is not False
        ):
            raise ValueError("opaque candidate is malformed or misbound")
        candidate = PilotCandidate(index=index, row=row, opaque=opaque_row)
        pool.append(candidate)
    _validate_customer_token_mapping(pool)
    eligible, separation = filter_separated_candidates(pool, protected=protected)

    budgets: dict[View, int] = {
        "representative": args.representative,
        "unseen_input": args.unseen_input,
        "unfamiliar_merchant": args.unfamiliar_merchant,
    }
    assignments = allocate_pilot(eligible, budgets=budgets, seed=args.seed)
    by_index = {candidate.index: candidate for candidate in eligible}
    annotations = []
    memberships = []
    for index, primary in sorted(assignments.items()):
        annotation, membership = _payload(
            by_index[index], primary, candidate_receipt["result_sha256"]
        )
        annotations.append(annotation)
        memberships.append(membership)

    primary_input_overlap = Counter()
    for index, primary in assignments.items():
        if not by_index[index].unseen:
            primary_input_overlap[primary] += 1
    if primary_input_overlap["unseen_input"] or primary_input_overlap["unfamiliar_merchant"]:
        raise ValueError("strict novelty view contains a historically exposed input")

    args.output.mkdir(mode=0o700, parents=False, exist_ok=False)
    prompt_path = args.output / "pilot.jsonl"
    prompt_bytes = b"".join(_canonical(row) + b"\n" for row in annotations)
    _write_private(prompt_path, prompt_bytes)
    membership_path = args.output / "membership.csv"
    with membership_path.open("x", newline="", encoding="utf-8") as stream:
        os.fchmod(stream.fileno(), 0o600)
        writer = csv.DictWriter(stream, fieldnames=MEMBERSHIP_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(memberships)
        stream.flush()
        os.fsync(stream.fileno())

    primary_counts = Counter(row["primary_view"] for row in annotations)
    tag_counts = Counter(view for row in annotations for view in row["views"])
    strata = Counter(row["source_stratum"] for row in annotations)
    customer_counts = Counter(row["customer_id"] for row in memberships)
    summary = {
        "schema_version": "txncat-private-eval-pilot-summary-v1",
        "purpose": "evaluation_annotation_pilot",
        "source_snapshot_sha256": candidate_receipt["result_sha256"],
        "candidate_rows": len(candidates),
        **separation,
        "existing_membership_files": len(args.existing_membership),
        "pilot_rows": len(annotations),
        "pilot_customers": len(customer_counts),
        "max_rows_per_customer": max(customer_counts.values()),
        "primary_views": dict(sorted(primary_counts.items())),
        "view_tags": dict(sorted(tag_counts.items())),
        "source_strata": dict(sorted(strata.items())),
        "primary_view_historical_input_overlap": {
            view: primary_input_overlap[view] for view in VIEW_ORDER
        },
        "budgets": budgets,
        "seed": args.seed,
        "authorizes_consumption": False,
        "provider_calls": 0,
        "labels_created": 0,
        "models_retrained": 0,
        "locked_sets_scored": 0,
        "limitations": [
            "Historical exact transaction IDs are unavailable, so retrospective event-level separation cannot be proven; the opaque effective-input screen defines novelty tags and strict-view eligibility.",
            "The representative primary view intentionally samples separated candidate events regardless of effective-input familiarity; unseen-input and unfamiliar-merchant primary views reject known input matches.",
            "Unfamiliar merchant means unseen normalised merchant string, not a reviewed alias-family ontology.",
            "The output is private membership and annotation input, not consumption authority.",
        ],
    }
    summary_path = args.output / "summary.json"
    _write_private(summary_path, json.dumps(summary, indent=2, sort_keys=True).encode() + b"\n")
    receipt = {
        "schema_version": "txncat-private-eval-pilot-receipt-v1",
        "purpose": "evaluation_annotation_pilot",
        "source_kind": "customer_linked_plaid_materialized",
        "anonymous_id_recovery": False,
        "candidate_receipt_sha256": _file_sha256(args.candidates / "receipt.json"),
        "candidate_result_sha256": candidate_receipt["result_sha256"],
        "profile_sha256": _file_sha256(args.profile / "profile.json"),
        "opaque_candidates_sha256": _file_sha256(args.profile / "opaque-candidates.jsonl"),
        "lineage_receipt_sha256": _file_sha256(args.lineage / "receipt.json"),
        "lineage_result_sha256": lineage_receipt["result_sha256"],
        "existing_membership_inputs": _membership_input_receipts(
            args.existing_membership
        ),
        "pilot_sha256": _file_sha256(prompt_path),
        "membership_sha256": _file_sha256(membership_path),
        "summary_sha256": _file_sha256(summary_path),
        "pilot_rows": len(annotations),
        "authorizes_consumption": False,
        "provider_calls": 0,
        "labels_created": 0,
        "cloud_changes": 0,
    }
    _write_private(
        args.output / "receipt.json",
        json.dumps(receipt, indent=2, sort_keys=True).encode() + b"\n",
    )
    print(
        f"Private eval pilot created: {len(annotations)} rows across "
        f"{len(customer_counts)} customer blocks; no provider calls or labels."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        raise SystemExit(f"Eval pilot construction failed closed: {type(exc).__name__}") from None

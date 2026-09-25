"""Resolve per-candidate admission evidence for the G3 design.

Joins the candidate frame to the account/sibling evidence extracts and the
admission manifests, then recomputes each candidate's view decisions with the
resolved evidence flags.  The declared-corpus and family-registry manifests
carry ``review_state``: while either stays ``pending_human_review`` the
corresponding history flags remain incomplete and the affected rows stay
quarantined; a signed manifest changes the flag on rerun without code edits.
The summary also reports the ``if_manifests_signed`` scenario so the remaining
human gate is visible in the evidence.

Every output is ``authorizes_consumption=false``: this is admission evidence,
not admission.
"""

from __future__ import annotations

import argparse
import hashlib
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from benchmark_account_evidence_extract import digest
from benchmark_build_index import private_key
from benchmark_profile_candidates import (
    _digest,
    _head,
    _view_decisions,
)
from benchmark_profile_candidate_frame import (
    FRAME_PURPOSE,
    PROFILE_SCHEMA,
    _load_frame,
)
from raylo_txncat.benchmark import observation_key, project_head
from raylo_txncat.hashing import canonical_json, strict_json_loads

RESOLVED_SCHEMA = "benchmark-resolved-candidates-v1"
SUMMARY_SCHEMA = "benchmark-evidence-resolution-summary-v1"
CORPUS_SCHEMA = "benchmark-declared-corpus-v1"
LEGACY_SCHEMA = "benchmark-legacy-membership-index-v1"
FAMILY_SCHEMA = "benchmark-family-registry-proposal-v1"
ACCOUNT_SUMMARY_SCHEMA = "benchmark-account-evidence-summary-v1"
SIBLING_SUMMARY_SCHEMA = "benchmark-sibling-evidence-summary-v1"


def _load_json(path: Path) -> dict[str, Any]:
    value = strict_json_loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ValueError(f"{path} is not a JSON object")
    return value


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("rb") as stream:
        for line in stream:
            row = strict_json_loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"{path} contains a malformed row")
            rows.append(row)
    return rows


def _account_state(evidence_dirs: list[Path]) -> dict[str, dict[str, Any]]:
    """Union per-account evidence across candidate and sibling extracts."""
    state: dict[str, dict[str, Any]] = {}
    for directory in evidence_dirs:
        summary = _load_json(directory / "summary.json")
        if summary.get("schema_version") not in (
            ACCOUNT_SUMMARY_SCHEMA,
            SIBLING_SUMMARY_SCHEMA,
        ) or summary.get("authorizes_consumption") is not False:
            raise ValueError(f"{directory} is not a bound evidence extract")
        for row in _load_jsonl(directory / "account-summary.jsonl"):
            entry = state.setdefault(
                row["account_id"],
                {
                    "customers": set(),
                    "unresolved_link_rows": 0,
                    "pending_ids": set(),
                    "names": set(),
                    "masks": set(),
                    "sources": set(),
                },
            )
            entry["customers"].update(row["customer_ids"])
            entry["unresolved_link_rows"] += row["unresolved_link_rows"]
            entry["pending_ids"].update(row["pending_transaction_ids"])
            entry["names"].update(row["account_names"])
            entry["masks"].update(row["account_masks"])
            entry["sources"].add(row["source_table"])
        pending_unresolved = state.setdefault("__pending_unresolved__", {"accounts": set()})
        for row in _load_jsonl(directory / "pending-resolution.jsonl"):
            if row["posted_history_rows"] == 0 and row["current_materialized_rows"] == 0:
                pending_unresolved["accounts"].add(row["account_id"])
    return state


def _load_opaque(profile: Path, expected_sha256: str) -> dict[str, dict[str, Any]]:
    profile_doc = _load_json(profile / "profile.json")
    if (
        profile_doc.get("schema_version") != PROFILE_SCHEMA
        or profile_doc.get("source_snapshot_sha256") != expected_sha256
    ):
        raise ValueError("frame profile is not bound to the candidate snapshot")
    opaque = {}
    for row in _load_jsonl(profile / "opaque-candidates.jsonl"):
        candidate_id = row.get("candidate_id")
        if type(candidate_id) is not str or candidate_id in opaque:
            raise ValueError("opaque candidates are not unique")
        opaque[candidate_id] = row
    return opaque


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "candidates",
        "profile",
        "account-evidence",
        "sibling-evidence",
        "manifests",
        "family-review",
        "index",
        "index-receipt",
        "key-file",
        "output",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument(
        "--sql", type=Path,
        default=Path(__file__).with_name("benchmark_candidate_frame_extract.sql"),
    )
    parser.add_argument(
        "--runner", type=Path,
        default=Path(__file__).with_name("benchmark_candidate_frame_extract.py"),
    )
    parser.add_argument("--purpose", default=FRAME_PURPOSE)
    parser.add_argument("--max-candidates", type=int, default=10_000)
    parser.add_argument("--derived", action="store_true")
    args = parser.parse_args()
    os.umask(0o077)
    args.output.mkdir(mode=0o700, exist_ok=False)
    if args.derived:
        candidate_receipt = _load_json(args.candidates / "receipt.json")
        if (
            candidate_receipt.get("schema_version") != "benchmark-derived-pool-v1"
            or candidate_receipt.get("authorizes_consumption") is not False
            or _digest(args.candidates / "candidates.jsonl")
            != candidate_receipt.get("result_sha256")
        ):
            raise ValueError("derived pool is outside the approved contract")
        rows = _load_jsonl(args.candidates / "candidates.jsonl")
        if len(rows) != candidate_receipt.get("roster_hit_rows"):
            raise ValueError("derived pool row count does not match its receipt")
        snapshot_sha = candidate_receipt["pool_result_sha256"]
    else:
        candidate_receipt, rows = _load_frame(
            args.candidates,
            args.sql,
            args.runner,
            purpose=args.purpose,
            max_candidates=args.max_candidates,
        )
        snapshot_sha = candidate_receipt["result_sha256"]
    opaque = _load_opaque(args.profile, snapshot_sha)

    corpus = _load_json(args.manifests / "declared-corpus.json")
    if (
        corpus.get("schema_version") != CORPUS_SCHEMA
        or corpus.get("authorizes_consumption") is not False
        or corpus.get("index", {}).get("index_receipt_sha256")
        != _digest(args.index_receipt)
    ):
        raise ValueError("declared-corpus manifest is not bound to the index")
    corpus_signed = corpus.get("review_state") == "signed"

    legacy = _load_json(args.manifests / "legacy-membership-index.json")
    if (
        legacy.get("schema_version") != LEGACY_SCHEMA
        or legacy.get("authorizes_consumption") is not False
    ):
        raise ValueError("legacy membership index is invalid")
    legacy_projections = set()
    legacy_families = set()
    member_by_projection = defaultdict(list)
    member_by_family = defaultdict(list)
    for member in legacy["members"]:
        for token in member["projection_tokens"]:
            pair = (token["version"], token["token"])
            legacy_projections.add(pair)
            member_by_projection[pair].append(member["member_id"])
        if member.get("family_token"):
            legacy_families.add(member["family_token"])
            member_by_family[member["family_token"]].append(member["member_id"])

    family = _load_json(args.family_review / "family-registry-proposal.json")
    if (
        family.get("schema_version") != FAMILY_SCHEMA
        or family.get("authorizes_consumption") is not False
    ):
        raise ValueError("family registry proposal is invalid")
    family_signed = family.get("review_state") == "signed"

    index_receipt = _load_json(args.index_receipt)
    key = private_key(args.key_file, index_receipt["key_id"])

    account_state = _account_state([args.account_evidence, args.sibling_evidence])
    pending_unresolved = account_state.pop("__pending_unresolved__")["accounts"]

    customer_accounts = defaultdict(set)
    for row in _load_jsonl(args.sibling_evidence / "customer-accounts.jsonl"):
        customer_accounts[row["customer_id"]].add(row["account_id"])
    for row in rows:
        customer_accounts[row["customer_id"]].add(row["account_id"])

    # Cross-customer attribute twins: same normalised account name+mask under
    # different resolved customers indicates a reconnect of one physical
    # account; fold twins into the sibling group so their coverage is checked.
    attribute_index = defaultdict(set)
    for account, entry in account_state.items():
        for name in entry["names"]:
            for mask in entry["masks"]:
                attribute_index[(name, mask)].add(account)
    sibling_groups: dict[str, set[str]] = {}
    for row in rows:
        account = row["account_id"]
        group = set(customer_accounts.get(row["customer_id"], set()))
        for name in account_state.get(account, {}).get("names", set()):
            for mask in account_state.get(account, {}).get("masks", set()):
                group.update(attribute_index[(name, mask)])
        group.discard(account)
        sibling_groups[account] = group

    resolved = []
    status_counts = {view: Counter() for view in ("representative", "unseen_input", "unfamiliar_merchant")}
    reason_counts = {view: Counter() for view in status_counts}
    signed_counts = {view: Counter() for view in status_counts}
    evidence_counters = Counter()
    joined = 0
    for row in rows:
        event = observation_key(
            key,
            namespace="plaid",
            account_id=row["account_id"],
            transaction_id=row["transaction_id"],
        )
        candidate_id = hashlib.sha256(
            canonical_json({"source": snapshot_sha, "event": event})
        ).hexdigest()
        entry = opaque.get(candidate_id)
        if entry is None or entry["observation"] != event:
            raise ValueError("opaque profile does not cover a candidate event")
        joined += 1
        account = row["account_id"]
        state = account_state.get(account)
        group = sibling_groups[account]
        group_states = [
            (sibling, account_state.get(sibling)) for sibling in group
        ]
        group_covered = all(state is not None for _s, state in group_states)
        group_clean = group_covered and all(
            len(state["customers"]) <= 1 and state["unresolved_link_rows"] == 0
            for _s, state in group_states
        )
        uncovered_siblings = {s for s, state in group_states if state is None}
        churned = bool(state and len(state["customers"]) > 1)
        unresolved_links = bool(state and state["unresolved_link_rows"] > 0)
        pending_ok = account not in pending_unresolved and all(
            sibling not in pending_unresolved for sibling in group
        )
        aliases_verified = (
            state is not None and pending_ok and group_covered
        )
        identity_complete = (
            aliases_verified
            and not churned
            and not unresolved_links
            and group_clean
        )
        evidence_counters["accounts_covered"] += state is not None
        evidence_counters["candidates_in_complete_groups"] += group_clean
        evidence_counters["candidates_with_uncovered_siblings"] += bool(
            uncovered_siblings
        )
        evidence_counters["candidates_churned_accounts"] += churned
        evidence_counters["candidates_unresolved_link_accounts"] += (
            unresolved_links
        )

        head = _head(row)
        projections = project_head(head, key)
        legacy_member_hits = sorted(
            {
                member_id
                for projection in projections
                for member_id in member_by_projection.get(
                    (projection.version, projection.token), ()
                )
            }
            | set(
                member_by_family.get(entry["merchant_family"], ())
                if entry.get("merchant_family")
                else ()
            )
        )
        evidence_counters["candidates_with_legacy_hits"] += bool(
            legacy_member_hits
        )
        input_sources = set(entry["input_sources"])
        if legacy_member_hits:
            input_sources.add("legacy_membership_index")

        flag_sets = {
            "as_evidence_stands": dict(
                input_history_complete=corpus_signed,
                family_reviewed=family_signed,
                family_history_complete=family_signed,
            ),
            "if_manifests_signed": dict(
                input_history_complete=True,
                family_reviewed=True,
                family_history_complete=True,
            ),
        }
        decision_sets = {}
        for scenario, flags in flag_sets.items():
            decision_sets[scenario] = _view_decisions(
                current_identity=True,
                aliases_verified=aliases_verified,
                identity_history_complete=identity_complete,
                input_sources=input_sources,
                legacy_index_complete=True,
                merchant_present=entry["merchant_present"],
                merchant_known=bool(entry["merchant_known_sources"]),
                **flags,
            )
        for view, decision in decision_sets["as_evidence_stands"].items():
            status_counts[view][decision["status"]] += 1
            reason_counts[view].update(decision["reasons"])
        for view, decision in decision_sets["if_manifests_signed"].items():
            signed_counts[view][decision["status"]] += 1

        resolved.append(
            {
                **entry,
                "views": decision_sets["as_evidence_stands"],
                "views_if_manifests_signed": decision_sets["if_manifests_signed"],
                "input_sources": tuple(sorted(input_sources)),
                "sibling_accounts": tuple(
                    sorted(
                        key.token(
                            "account",
                            {"namespace": "plaid", "account": sibling},
                        )
                        for sibling in group
                    )
                ),
                "legacy_member_hits": tuple(legacy_member_hits),
                "evidence": {
                    "account_evidence_covered": state is not None,
                    "pending_state": (
                        "account_pending_history_unknown"
                        if state is None
                        else "resolved_same_key"
                        if pending_ok
                        else "unresolved_pending_pair"
                    ),
                    "identity_churn": churned,
                    "unresolved_links": unresolved_links,
                    "reconnect_group_accounts": len(group),
                    "reconnect_group_complete": group_clean,
                    "uncovered_sibling_count": len(uncovered_siblings),
                    "alias_coverage": (
                        "pending_and_collision_complete"
                        if aliases_verified
                        else "incomplete"
                    ),
                    "corpus_review_state": corpus["review_state"],
                    "family_review_state": family["review_state"],
                },
            }
        )
    if joined != len(rows) or (not args.derived and joined != len(opaque)):
        raise ValueError("opaque/candidate join is incomplete")

    out_path = args.output / "resolved-candidates.jsonl"
    with out_path.open("xb") as stream:
        for record in resolved:
            stream.write(canonical_json(record) + b"\n")
    os.chmod(out_path, 0o600)
    summary = {
        "schema_version": SUMMARY_SCHEMA,
        "purpose": "g3_evidence_resolution_not_authority",
        "authorizes_consumption": False,
        "source_snapshot_sha256": snapshot_sha,
        "candidates": len(resolved),
        "evidence_counters": dict(sorted(evidence_counters.items())),
        "view_status_as_evidence_stands": {
            view: dict(sorted(counts.items()))
            for view, counts in status_counts.items()
        },
        "view_reasons_as_evidence_stands": {
            view: dict(sorted(counts.items()))
            for view, counts in reason_counts.items()
        },
        "view_status_if_manifests_signed": {
            view: dict(sorted(counts.items()))
            for view, counts in signed_counts.items()
        },
        "pending_human_gates": {
            "declared_corpus_review": corpus["review_state"],
            "family_registry_review": family["review_state"],
        },
        "inputs": {
            "candidate_receipt_sha256": _digest(args.candidates / "receipt.json"),
            "profile_sha256": _digest(args.profile / "profile.json"),
            "account_evidence_summary_sha256": _digest(
                args.account_evidence / "summary.json"
            ),
            "sibling_evidence_summary_sha256": _digest(
                args.sibling_evidence / "summary.json"
            ),
            "declared_corpus_sha256": _digest(
                args.manifests / "declared-corpus.json"
            ),
            "legacy_membership_index_sha256": _digest(
                args.manifests / "legacy-membership-index.json"
            ),
            "family_proposal_sha256": _digest(
                args.family_review / "family-registry-proposal.json"
            ),
            "runner_sha256": digest(Path(__file__)),
        },
    }
    (args.output / "summary.json").write_bytes(canonical_json(summary) + b"\n")
    os.chmod(args.output / "summary.json", 0o600)
    print(
        f"Resolved {len(resolved)} candidates; "
        f"eligible as evidence stands: "
        + ", ".join(
            f"{view}={status_counts[view].get('eligible_preflight', 0)}"
            for view in status_counts
        )
        + "; if manifests signed: "
        + ", ".join(
            f"{view}={signed_counts[view].get('eligible_preflight', 0)}"
            for view in signed_counts
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit(
            "Evidence resolution failed; no admission claim is valid."
        ) from None

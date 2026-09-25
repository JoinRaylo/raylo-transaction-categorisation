"""Build the G3 admission manifests: declared corpus, legacy index, family proposal.

Three artifacts resolve three of the six lineage blockers:

* ``declared-corpus.json`` binds the pinned exposure index and the complete
  screened corpus set (exact, token48, surface-fold, hinge-sparse and merchant
  sources).  It is a completeness *attestation*: ``review_state`` stays
  ``pending_human_review`` until an operator signs that the listed corpora are
  the whole retained set that could contain candidate inputs.
* ``legacy-membership-index.json`` migrates the declared legacy memberships
  into a bound input-level index.  Every member's input is projected under the
  private key and checked against the pinned exposure index, so coverage is
  measured, not asserted; members whose projections are absent from the index
  are still carried so the resolver can screen candidates against them
  directly.
* ``family-registry-proposal.json`` is the private review artifact listing
  every candidate merchant family with counts and known-source presence.  It
  contains merchant names and therefore lives only in the private store; the
  committed packet carries its digest and aggregate counts.

Nothing here reserves, labels or authorizes consumption.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

from benchmark_build_index import private_key
from benchmark_profile_candidates import (
    LEGACY_FILES,
    MERCHANT_SOURCES,
    SCOPE_CONTRACT,
    _digest,
)
from benchmark_screen_exposure import SOURCE_PATHS
from raylo_txncat.benchmark import project_head
from raylo_txncat.benchmark_exposure import ExposureIndex
from raylo_txncat.classifier_types import ClassifierInput
from raylo_txncat.dictionary import normalise_merchant
from raylo_txncat.hashing import canonical_json, strict_json_loads

SCHEMA = "benchmark-admission-manifests-v1"
CORPUS_SCHEMA = "benchmark-declared-corpus-v1"
LEGACY_SCHEMA = "benchmark-legacy-membership-index-v1"
FAMILY_SCHEMA = "benchmark-family-registry-proposal-v1"


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"{path} is not a JSON object")
    return value


def _inventory_entry(inventory: dict, relative: str) -> dict[str, Any]:
    entry = inventory.get(relative)
    if entry is None:
        raise ValueError(f"pinned inventory lacks {relative}")
    return entry


def _corpus_entries(research: Path, inventory: dict) -> list[dict[str, Any]]:
    entries = []
    for relative in sorted(set(MERCHANT_SOURCES)):
        path = research / relative
        entry = _inventory_entry(inventory, relative)
        observed = _digest(path)
        if observed != entry["sha256"]:
            raise ValueError(f"screened corpus changed: {relative}")
        entries.append(
            {
                "path": relative,
                "sha256": observed,
                "rows": entry.get("profile", {}).get("rows"),
                "input_screens": (
                    ["exact_index", "token48", "surface_fold", "hinge_sparse"]
                    if relative in SOURCE_PATHS
                    else []
                )
                + ["merchant_name"],
            }
        )
    return entries


def _legacy_members(legacy: Path) -> tuple[dict[str, str], list[dict[str, Any]]]:
    summary = _load_json(legacy / "summary.json")
    digests = {}
    members = []
    for filename, digest_key in LEGACY_FILES:
        path = legacy / filename
        if _digest(path) != summary[digest_key]:
            raise ValueError(f"legacy membership changed: {filename}")
        digests[filename] = summary[digest_key]
        with path.open("rb") as stream:
            for line in stream:
                record = strict_json_loads(line)
                if not isinstance(record, dict):
                    raise ValueError("legacy record is malformed")
                members.append(record)
    return digests, members


def _member_heads(member: dict[str, Any]) -> list[ClassifierInput]:
    source = member.get("input")
    if not isinstance(source, dict):
        raise ValueError("legacy member lacks its input payload")
    amount = source.get("amount")
    if amount in (None, "", "None"):
        return []
    direction = source.get("direction")
    if direction == "unknown":
        directions = ["debit", "credit"]
    elif direction in {"credit", "debit"}:
        directions = [direction]
    else:
        raise ValueError("legacy member direction is invalid")
    return [
        ClassifierInput.from_research(
            {
                "merchant_raw": source.get("merchant_raw"),
                "description_raw": source.get("description_raw"),
                "amount": amount,
                "direction": resolved,
            }
        )
        for resolved in directions
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "candidates",
        "research",
        "inventory",
        "index",
        "index-receipt",
        "key-file",
        "legacy",
        "output",
        "private-output",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    args.output.mkdir(mode=0o700, exist_ok=False)
    args.private_output.mkdir(mode=0o700, exist_ok=False)
    inventory = _load_json(args.inventory)["files"]
    corpus = _corpus_entries(args.research, inventory)
    index_receipt = _load_json(args.index_receipt)
    if (
        index_receipt.get("schema_version") != "benchmark-input-presence-v1"
        or index_receipt.get("authorizes_consumption") is not False
        or index_receipt.get("complete") is not True
    ):
        raise ValueError("exposure index receipt is not a complete pinned index")
    key = private_key(args.key_file, index_receipt["key_id"])
    index = ExposureIndex(
        args.index / "inputs.sqlite",
        expected_sha256=index_receipt["database_sha256"],
        key=key,
    )
    legacy_digests, members = _legacy_members(args.legacy)
    try:
        index_sources = {
            "source_count": len(index_receipt["sources"]),
            "sources": [
                {
                    "source_id": source["source_id"],
                    "rows": source["rows"],
                    "purposes": source["purposes"],
                    "projections": source["projections"],
                    "source_sha256": source["source_sha256"],
                }
                for source in index_receipt["sources"]
            ],
            "database_sha256": index_receipt["database_sha256"],
            "index_receipt_sha256": _digest(args.index_receipt),
        }
        declared_corpus = {
            "schema_version": CORPUS_SCHEMA,
            "authorizes_consumption": False,
            "purpose": "input_history_completeness_attestation_not_authority",
            "scope_contract": SCOPE_CONTRACT,
            "review_state": "pending_human_review",
            "reviewed_by": None,
            "declared_complete_over": (
                "the screened corpora below are asserted to be the complete "
                "retained corpus set that could contain candidate inputs; "
                "absent hits are certified not-found only while this holds"
            ),
            "index": index_sources,
            "screened_corpora": corpus
            + [
                {
                    "path": f"legacy/{name}",
                    "sha256": sha,
                    "rows": None,
                    "input_screens": ["merchant_name"],
                }
                for name, sha in sorted(legacy_digests.items())
            ],
            "inventory_sha256": _digest(args.inventory),
        }
        (args.output / "declared-corpus.json").write_bytes(
            canonical_json(declared_corpus) + b"\n"
        )

        legacy_entries = []
        coverage = Counter()
        for member in members:
            member_id = member.get("member_id")
            input_hash = member.get("input_hash")
            if (
                type(member_id) is not str
                or len(member_id) != 64
                or type(input_hash) is not str
                or len(input_hash) != 64
            ):
                raise ValueError("legacy member identity fields are invalid")
            source = member["input"]
            heads = _member_heads(member)
            direction_ambiguous = source.get("direction") == "unknown"
            projections = [
                projection
                for head in heads
                for projection in project_head(head, key)
            ]
            hits = {
                source_id
                for projection in projections
                for source_id in index.lookup(projection)["sources"]
            }
            merchant = normalise_merchant(source.get("merchant_raw"))
            basis = "input_projection" if heads else "merchant_name"
            covered = bool(hits) if heads else bool(merchant)
            coverage[basis] += 1
            coverage["covered" if covered else "uncovered"] += 1
            if direction_ambiguous:
                coverage["direction_ambiguous"] += 1
            legacy_entries.append(
                {
                    "member_id": member_id,
                    "input_hash": input_hash,
                    "cohort": member.get("cohort"),
                    "independent_benchmark": member.get("independent_benchmark"),
                    "screening_basis": basis,
                    "direction_ambiguous": direction_ambiguous,
                    "family_token": key.token("family", merchant)
                    if merchant
                    else None,
                    "projection_tokens": [
                        {"version": p.version, "token": p.token}
                        for p in projections
                    ],
                    "covered_by_index": bool(hits),
                    "covered_by_screen": covered,
                    "index_sources": sorted(hits),
                }
            )
        legacy_index = {
            "schema_version": LEGACY_SCHEMA,
            "authorizes_consumption": False,
            "purpose": "legacy_membership_migration_not_authority",
            "member_count": len(legacy_entries),
            "source_file_sha256": legacy_digests,
            "source_summary_sha256": _digest(args.legacy / "summary.json"),
            "event_identity": (
                "unrecovered_for_all_members; screening is input-level only"
            ),
            "index_coverage": dict(sorted(coverage.items())),
            "members": legacy_entries,
        }
        (args.output / "legacy-membership-index.json").write_bytes(
            canonical_json(legacy_index) + b"\n"
        )
    finally:
        index.close()

    families: dict[str, dict[str, Any]] = {}
    with (args.candidates / "candidates.jsonl").open("rb") as stream:
        for line in stream:
            row = strict_json_loads(line)
            merchant = normalise_merchant(row.get("merchant_name"))
            if not merchant:
                continue
            entry = families.setdefault(
                merchant,
                {
                    "merchant_normalised": merchant,
                    "candidate_rows": 0,
                    "customers": set(),
                    "accounts": set(),
                },
            )
            entry["candidate_rows"] += 1
            entry["customers"].add(row["customer_id"])
            entry["accounts"].add(row["account_id"])
    proposal_rows = []
    for merchant, entry in families.items():
        proposal_rows.append(
            {
                "merchant_normalised": merchant,
                "candidate_rows": entry["candidate_rows"],
                "distinct_customers": len(entry["customers"]),
                "distinct_accounts": len(entry["accounts"]),
            }
        )
    proposal_rows.sort(
        key=lambda row: (-row["candidate_rows"], row["merchant_normalised"])
    )
    proposal = {
        "schema_version": FAMILY_SCHEMA,
        "authorizes_consumption": False,
        "purpose": "merchant_family_review_proposal_not_authority",
        "family_definition": "normalised merchant name (normalise_merchant)",
        "candidate_families": len(proposal_rows),
        "review_state": "pending_human_review",
        "reviewed_by": None,
        "families": proposal_rows,
    }
    proposal_path = args.private_output / "family-registry-proposal.json"
    proposal_path.write_bytes(canonical_json(proposal) + b"\n")
    os.chmod(proposal_path, 0o600)
    for name in ("declared-corpus.json", "legacy-membership-index.json"):
        os.chmod(args.output / name, 0o600)
    print(
        f"Manifests written: {len(corpus)} screened corpora, "
        f"{len(legacy_entries)} legacy members "
        f"({coverage.get('uncovered', 0)} uncovered), "
        f"{len(proposal_rows)} merchant families proposed; "
        "no admission authorized."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit(
            "Admission manifest build failed; no admission claim is valid."
        ) from None

"""Assemble the G3 proposed-membership bundle for admission design review.

Builds the ``MembershipManifest`` entries for every proposed member (expansion
core plus rare-leaf supplement), the protected-key union across pilot,
expansion and supplement, and the private raw-id membership CSV that
``raylo_txncat.benchmark_enforcement.load_protected_membership`` consumes when
consumers exclude protected rows at retrain time.  Also emits the opaque
key-map so a reviewer can trace every protected key back to its evidence
chain.  Everything remains a proposal: no admission authority exists here.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
from pathlib import Path

from benchmark_build_index import private_key
from raylo_txncat.benchmark import observation_key
from raylo_txncat.hashing import canonical_json, strict_json_loads
from raylo_txncat.membership_manifest import (
    MembershipEntry,
    build_membership_manifest,
)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("rb") as stream:
        for line in stream:
            row = strict_json_loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"{path} contains a malformed row")
            rows.append(row)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "core-proposal",
        "supplement-proposal",
        "candidates",
        "hits",
        "pilot-membership",
        "index-receipt",
        "key-file",
        "output",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    args.output.mkdir(mode=0o700, exist_ok=False)

    index_receipt = strict_json_loads(args.index_receipt.read_bytes())
    key = private_key(args.key_file, index_receipt["key_id"])

    # Raw-id lookup: join opaque observation keys back to raw account /
    # transaction / customer ids across both raw extracts.
    raw_by_event = {}
    for directory in (args.candidates, args.hits):
        for row in _load_jsonl(directory / "candidates.jsonl"):
            event = observation_key(
                key,
                namespace="plaid",
                account_id=row["account_id"],
                transaction_id=row["transaction_id"],
            )
            raw_by_event[event] = row

    core_report = strict_json_loads(
        (args.core_proposal / "selection-report.json").read_bytes()
    )
    supplement_report = strict_json_loads(
        (args.supplement_proposal / "selection-report.json").read_bytes()
    )
    if (
        core_report.get("authorizes_consumption") is not False
        or supplement_report.get("authorizes_consumption") is not False
    ):
        raise ValueError("a selection proposal is outside the contract")
    core_members = _load_jsonl(args.core_proposal / "selected-expansion.jsonl")
    supplement_members = _load_jsonl(
        args.supplement_proposal / "supplement-members.jsonl"
    )
    snapshot_sha = core_report["source_snapshot_sha256"]

    manifest_entries = []
    protected_events, protected_accounts, protected_customers = (
        set(),
        set(),
        set(),
    )
    private_rows = []
    key_map = []

    def add_member(
        *,
        observation: str,
        views: tuple[str, ...],
        projections: tuple,
        family_key: str | None,
        row_sha256: str,
        reason: str,
        accounts: tuple,
        customers: tuple,
        aliases: tuple,
        raw: dict | None,
        cohort: str,
        proxy_leaf: str | None = None,
    ) -> None:
        manifest_entries.append(
            MembershipEntry(
                observation_key=observation,
                role="eval",
                views=tuple(views),
                source_snapshot_sha256=snapshot_sha,
                row_sha256=row_sha256,
                projections=tuple(
                    {"version": p["version"], "token": p["token"]}
                    for p in projections
                ),
                merchant_family_key=family_key,
                reason=reason,
            )
        )
        protected_events.update({observation, *aliases})
        protected_accounts.update(accounts)
        protected_customers.update(customers)
        if raw is not None:
            private_rows.append(
                {
                    "schema_version": "txncat-private-eval-membership-v1",
                    "provider": "plaid",
                    "account_id": raw["account_id"],
                    "transaction_id": raw["transaction_id"],
                    "customer_id": raw["customer_id"],
                    "role": "eval",
                    "primary_view": views[0],
                    "views": "+".join(views),
                    "member_id": f"{cohort}-" + observation,
                    "source_snapshot_sha256": snapshot_sha,
                    "row_sha256": row_sha256,
                    "intended_proxy_leaf": proxy_leaf or "",
                }
            )
        key_map.append(
            {
                "observation_key": observation,
                "accounts": sorted(set(accounts)),
                "customers": sorted(set(customers)),
                "event_aliases": sorted(set(aliases)),
                "cohort": cohort,
                "views": sorted(views),
                "reason": reason,
            }
        )

    for member in core_members:
        event = member["observation_key"]
        raw = raw_by_event.get(event)
        if raw is None:
            raise ValueError("core member lacks a raw candidate row")
        add_member(
            observation=event,
            views=tuple(member["view_eligibility"]),
            projections=tuple(member["projections"]),
            family_key=member.get("merchant_family"),
            row_sha256=member["content_sha256"],
            reason=f"g3-expansion-{member['primary_view'].replace('_', '-')}",
            accounts=tuple(member["accounts"]),
            customers=tuple(member["customers"]),
            aliases=tuple(member.get("event_aliases") or ()),
            raw=raw,
            cohort="core-expansion",
        )
    for member in supplement_members:
        event = member["observation_key"]
        raw = raw_by_event.get(event)
        if raw is None:
            raise ValueError("supplement member lacks a raw pool row")
        add_member(
            observation=event,
            views=tuple(member["eligible_views"]),
            projections=tuple(member.get("projections") or ()),
            family_key=member.get("merchant_family"),
            row_sha256=member["content_sha256"],
            reason=f"g3-supplement-{member['intended_proxy_leaf'].replace('_', '-')}",
            accounts=tuple(member["accounts"]),
            customers=tuple(member["customers"]),
            aliases=tuple(member.get("event_aliases") or ()),
            raw=raw,
            cohort="rare-leaf-supplement",
            proxy_leaf=member["intended_proxy_leaf"],
        )
    with args.pilot_membership.open() as stream:
        pilot_rows = list(csv.DictReader(stream))
    for row in pilot_rows:
        event = observation_key(
            key,
            namespace="plaid",
            account_id=row["account_id"],
            transaction_id=row["transaction_id"],
        )
        account = key.token(
            "account", {"namespace": "plaid", "account": row["account_id"]}
        )
        customer = key.token(
            "customer", {"namespace": "raylo", "customer": row["customer_id"]}
        )
        protected_events.add(event)
        protected_accounts.add(account)
        protected_customers.add(customer)

    manifest = build_membership_manifest(
        manifest_id="g3-proposed-eval-membership-v1", entries=manifest_entries
    )

    manifest_path = args.output / "membership-manifest.json"
    manifest_path.write_bytes(canonical_json(manifest.model_dump(mode="json")) + b"\n")
    os.chmod(manifest_path, 0o600)

    private_path = args.output / "proposed-protected-membership.csv"
    with private_path.open("x", newline="") as stream:
        fieldnames = (
            "schema_version",
            "provider",
            "account_id",
            "transaction_id",
            "customer_id",
            "role",
            "primary_view",
            "views",
            "member_id",
            "source_snapshot_sha256",
            "row_sha256",
            "intended_proxy_leaf",
        )
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for row in sorted(private_rows, key=lambda item: item["member_id"]):
            writer.writerow(row)
    os.chmod(private_path, 0o600)

    keys_path = args.output / "protected-keys.json"
    keys_path.write_bytes(
        canonical_json(
            {
                "schema_version": "benchmark-protected-keys-v1",
                "purpose": "g3_proposed_protection_union_not_authority",
                "authorizes_consumption": False,
                "events": sorted(protected_events),
                "accounts": sorted(protected_accounts),
                "customers": sorted(protected_customers),
            }
        )
        + b"\n"
    )
    os.chmod(keys_path, 0o600)

    key_map_path = args.output / "protected-key-map.jsonl"
    with key_map_path.open("xb") as stream:
        for record in sorted(key_map, key=lambda item: item["observation_key"]):
            stream.write(canonical_json(record) + b"\n")
    os.chmod(key_map_path, 0o600)

    bundle = {
        "schema_version": "benchmark-membership-bundle-v1",
        "purpose": "g3_proposed_membership_not_authority",
        "authorizes_consumption": False,
        "manifest_id": manifest.manifest_id,
        "manifest_sha256": manifest.manifest_sha256,
        "manifest_entries": len(manifest.entries),
        "proposed_rows": {
            "core_expansion": len(core_members),
            "rare_leaf_supplement": len(supplement_members),
            "pilot_protected_rows": len(pilot_rows),
        },
        "protected_key_counts": {
            "events": len(protected_events),
            "accounts": len(protected_accounts),
            "customers": len(protected_customers),
        },
        "artifacts": {
            "membership_manifest_sha256": _digest(manifest_path),
            "protected_membership_csv_sha256": _digest(private_path),
            "protected_keys_sha256": _digest(keys_path),
            "protected_key_map_sha256": _digest(key_map_path),
        },
        "inputs": {
            "core_report_sha256": _digest(
                args.core_proposal / "selection-report.json"
            ),
            "core_members_sha256": _digest(
                args.core_proposal / "selected-expansion.jsonl"
            ),
            "supplement_report_sha256": _digest(
                args.supplement_proposal / "selection-report.json"
            ),
            "supplement_members_sha256": _digest(
                args.supplement_proposal / "supplement-members.jsonl"
            ),
            "pilot_membership_sha256": _digest(args.pilot_membership),
            "index_receipt_sha256": _digest(args.index_receipt),
            "runner_sha256": _digest(Path(__file__)),
        },
    }
    (args.output / "bundle.json").write_bytes(canonical_json(bundle) + b"\n")
    os.chmod(args.output / "bundle.json", 0o600)
    print(
        f"Membership bundle: {len(manifest.entries)} manifest entries, "
        f"{len(protected_events)} protected events, "
        f"{len(private_rows)} private rows; no admission authorized."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit(
            "Membership bundle assembly failed; no admission claim is valid."
        ) from None

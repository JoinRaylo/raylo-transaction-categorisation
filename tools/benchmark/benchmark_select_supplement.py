"""Select the 500-row rare-leaf supplement proposal for G3 admission design.

Mirrors ``raylo_txncat.benchmark_cohort.select_rare_leaf_supplement`` over the
resolved roster-hit pool: the pinned proxy precedence walk binds each row to
an intended leaf, deterministic per-leaf ranking fills the prespecified quota
of 20, and customer/account/family caps apply.  Core protection keys (pilot
plus the expansion proposal, including folded sibling accounts) exclude
overlap.  Shortfalls are reported, never silently filled.  The proposal is
engineering evidence only: nothing here reserves, labels or authorizes
consumption, and the supplement never joins the production-weighted
headline denominator.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
from collections import Counter, defaultdict
from pathlib import Path

from benchmark_build_index import private_key
from raylo_txncat.benchmark import observation_key
from raylo_txncat.hashing import canonical_json, sha256, strict_json_loads

VIEW_ORDER = ("representative", "unseen_input", "unfamiliar_merchant")


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


def _rank_leaf(seed: int, leaf: str, observation_key_: str) -> str:
    return sha256(
        canonical_json(
            {
                "algorithm": "benchmark-rare-leaf-rank-v1",
                "seed": seed,
                "leaf": leaf,
                "observation_key": observation_key_,
            }
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "resolved",
        "hits",
        "spec",
        "taxonomy",
        "core-proposal",
        "pilot-membership",
        "index-receipt",
        "key-file",
        "output",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument(
        "--scenario",
        choices=("as_evidence_stands", "if_manifests_signed"),
        default="if_manifests_signed",
    )
    args = parser.parse_args()
    os.umask(0o077)
    args.output.mkdir(mode=0o700, exist_ok=False)

    spec = strict_json_loads(args.spec.read_bytes())
    if spec.get("schema_version") != "benchmark-rare-leaf-spec-v1":
        raise ValueError("rare-leaf specification is invalid")
    quotas = {quota["leaf"]: quota for quota in spec["roster"]}
    roster = set(quotas)
    precedence = sorted(spec["proxies"], key=lambda item: item["precedence"])
    caps = spec["caps"]
    seed = spec["seed"]

    taxonomy_sha = _digest(args.taxonomy)
    if taxonomy_sha != spec["taxonomy_sha256"]:
        raise ValueError("taxonomy digest does not match the frozen spec")
    import csv as _csv

    with args.taxonomy.open() as stream:
        taxonomy_leaves = {
            row["detailed_category"] for row in _csv.DictReader(stream)
        }
    missing = sorted(roster - taxonomy_leaves)
    if missing:
        raise ValueError(f"roster leaves outside the taxonomy: {missing}")

    resolved_summary = strict_json_loads(
        (args.resolved / "summary.json").read_bytes()
    )
    if resolved_summary.get("authorizes_consumption") is not False:
        raise ValueError("resolved supplement summary is invalid")
    resolved = _load_jsonl(args.resolved / "resolved-candidates.jsonl")

    hits_receipt = strict_json_loads((args.hits / "receipt.json").read_bytes())
    if (
        hits_receipt.get("schema_version") != "benchmark-derived-pool-v1"
        or hits_receipt.get("authorizes_consumption") is not False
        or _digest(args.hits / "candidates.jsonl")
        != hits_receipt.get("result_sha256")
    ):
        raise ValueError("roster-hit pool receipt is invalid")
    raw_rows = _load_jsonl(args.hits / "candidates.jsonl")

    index_receipt = strict_json_loads(args.index_receipt.read_bytes())
    key = private_key(args.key_file, index_receipt["key_id"])

    raw_by_event = {}
    for row in raw_rows:
        event = observation_key(
            key,
            namespace="plaid",
            account_id=row["account_id"],
            transaction_id=row["transaction_id"],
        )
        raw_by_event[event] = row
    if len(raw_by_event) != len(raw_rows):
        raise ValueError("roster-hit pool has duplicate events")

    # Core protected keys: pilot members plus the expansion proposal, with
    # sibling accounts folded into each side's account blocks.
    core_events, core_accounts, core_customers = set(), set(), set()
    with args.pilot_membership.open() as stream:
        for row in csv.DictReader(stream):
            core_events.add(
                observation_key(
                    key,
                    namespace="plaid",
                    account_id=row["account_id"],
                    transaction_id=row["transaction_id"],
                )
            )
            core_accounts.add(
                key.token(
                    "account", {"namespace": "plaid", "account": row["account_id"]}
                )
            )
            core_customers.add(
                key.token(
                    "customer",
                    {"namespace": "raylo", "customer": row["customer_id"]},
                )
            )
    proposal = strict_json_loads(
        (args.core_proposal / "selection-report.json").read_bytes()
    )
    if proposal.get("authorizes_consumption") is not False:
        raise ValueError("core expansion proposal is invalid")
    members = _load_jsonl(args.core_proposal / "selected-expansion.jsonl")
    for member in members:
        core_events.add(member["observation_key"])
        core_events.update(member.get("event_aliases") or ())
        core_accounts.update(member["accounts"])
        core_customers.update(member["customers"])

    decisions_key = (
        "views" if args.scenario == "as_evidence_stands" else "views_if_manifests_signed"
    )
    quarantined_ownership = 0
    quarantined_alias = 0
    excluded_overlap = 0
    no_primary_view = 0
    shared_customers = set()
    eligible = []
    for entry in resolved:
        event = entry["observation"]
        if event not in raw_by_event:
            raise ValueError("resolved row is missing from the hit pool")
        evidence = entry["evidence"]
        ownership_verified = (
            evidence["account_evidence_covered"]
            and not evidence["identity_churn"]
            and not evidence["unresolved_links"]
            and evidence["reconnect_group_complete"]
        )
        if not ownership_verified:
            quarantined_ownership += 1
            continue
        if evidence["alias_coverage"] != "pending_and_collision_complete":
            quarantined_alias += 1
            continue
        accounts = {entry["account"], *entry.get("sibling_accounts", ())}
        if {event} & core_events or accounts & core_accounts:
            excluded_overlap += 1
            continue
        views = entry.get(decisions_key) or {}
        primary = next(
            (
                view
                for view in VIEW_ORDER
                if views.get(view, {}).get("status") == "eligible_preflight"
            ),
            None,
        )
        if primary is None:
            no_primary_view += 1
            continue
        shared_customers.update({entry["customer"]} & core_customers)
        eligible.append((entry, primary, accounts))

    proxy_misses = 0
    no_signal = 0
    gap_counts = Counter()
    by_leaf = defaultdict(list)
    for entry, primary, accounts in eligible:
        signals = entry.get("proxy_signals") or {}
        intended = None
        source = None
        saw_value = False
        saw_taxonomy = False
        for proxy in precedence:
            value = signals.get(proxy["kind"])
            if value is None:
                continue
            saw_value = True
            if value in roster:
                intended = value
                source = proxy["kind"]
                break
            if value in taxonomy_leaves:
                saw_taxonomy = True
            else:
                gap_counts[(proxy["kind"], value)] += 1
        if intended is not None:
            by_leaf[intended].append((entry, primary, accounts, source))
        elif saw_taxonomy:
            proxy_misses += 1
        elif saw_value:
            no_signal += 1
        else:
            no_signal += 1

    customer_rows = Counter()
    account_rows = Counter()
    family_rows = Counter()
    cap_rejections = 0
    assignments = []
    per_leaf = []
    for quota in spec["roster"]:
        leaf = quota["leaf"]
        ranked = sorted(
            by_leaf.get(leaf, ()),
            key=lambda item: (
                _rank_leaf(seed, leaf, item[0]["observation"]),
                item[0]["observation"],
            ),
        )
        selected = []
        for entry, primary, accounts, source in ranked:
            if len(selected) >= quota["quota"]:
                break
            if (
                customer_rows[entry["customer"]] >= caps["max_rows_per_customer"]
                or any(
                    account_rows[a] >= caps["max_rows_per_account"]
                    for a in accounts
                )
                or (
                    entry.get("merchant_family")
                    and family_rows[entry["merchant_family"]]
                    >= caps["max_rows_per_family"]
                )
            ):
                cap_rejections += 1
                continue
            selected.append((entry, primary, accounts, source))
            customer_rows[entry["customer"]] += 1
            for a in accounts:
                account_rows[a] += 1
            if entry.get("merchant_family"):
                family_rows[entry["merchant_family"]] += 1
        assignments.extend(
            (leaf, entry, primary, source) for entry, primary, _a, source in selected
        )
        distinct_customers = len({entry["customer"] for entry, _p, _a, _s in selected})
        per_leaf.append(
            {
                "leaf": leaf,
                "quota": quota["quota"],
                "eligible_preflight": len(by_leaf.get(leaf, ())),
                "selected": len(selected),
                "shortfall": quota["quota"] - len(selected),
                "distinct_customers": distinct_customers,
                "distinct_customers_status": (
                    "met"
                    if distinct_customers >= quota["min_distinct_customers"]
                    else "unmet"
                ),
                "min_final_support_status": (
                    "met" if len(selected) >= quota["min_final_support"] else "unmet"
                ),
                "proxy_support_status": (
                    "met"
                    if len(selected) >= quota["min_proxy_support"]
                    else "unmet"
                ),
            }
        )

    out_path = args.output / "supplement-members.jsonl"
    private_path = args.output / "supplement-private-members.csv"
    member_rows = []
    for leaf, entry, primary, source in sorted(
        assignments, key=lambda item: (item[0], item[1]["observation"])
    ):
        member_rows.append(
            {
                "schema_version": "benchmark-proposed-member-v1",
                "cohort": "rare_leaf_supplement",
                "observation_key": entry["observation"],
                "projections": entry.get("projections") or (),
                "event_aliases": entry.get("event_aliases") or (),
                "accounts": tuple(
                    sorted({entry["account"], *entry.get("sibling_accounts", ())})
                ),
                "customers": (entry["customer"],),
                "primary_view": primary,
                "eligible_views": tuple(
                    view
                    for view in VIEW_ORDER
                    if (entry.get(decisions_key) or {})
                    .get(view, {})
                    .get("status")
                    == "eligible_preflight"
                ),
                "intended_proxy_leaf": leaf,
                "proxy_source": source,
                "proxy_value": leaf,
                "merchant_family": entry.get("merchant_family"),
                "input_sources": entry["input_sources"],
                "baseline_tier": entry.get("baseline_tier"),
                "source_stratum": entry["source_stratum"],
                "content_sha256": entry["content_sha256"],
                "authorizes_consumption": False,
            }
        )
    with out_path.open("xb") as stream:
        for record in member_rows:
            stream.write(canonical_json(record) + b"\n")
    os.chmod(out_path, 0o600)

    snapshot_sha = resolved_summary["source_snapshot_sha256"]
    with private_path.open("x", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=(
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
            ),
        )
        writer.writeheader()
        for leaf, entry, primary, _source in sorted(
            assignments, key=lambda item: (item[0], item[1]["observation"])
        ):
            raw = raw_by_event[entry["observation"]]
            writer.writerow(
                {
                    "schema_version": "txncat-private-eval-membership-v1",
                    "provider": "plaid",
                    "account_id": raw["account_id"],
                    "transaction_id": raw["transaction_id"],
                    "customer_id": raw["customer_id"],
                    "role": "eval",
                    "primary_view": primary,
                    "views": "+".join(
                        view
                        for view in VIEW_ORDER
                        if (entry.get(decisions_key) or {})
                        .get(view, {})
                        .get("status")
                        == "eligible_preflight"
                    ),
                    "member_id": "supplement-v1-" + entry["observation"],
                    "source_snapshot_sha256": snapshot_sha,
                    "row_sha256": raw["content_sha256"],
                    "intended_proxy_leaf": leaf,
                }
            )
    os.chmod(private_path, 0o600)

    report = {
        "schema_version": "benchmark-supplement-selection-v1",
        "purpose": "g3_supplement_selection_proposal_not_authority",
        "authorizes_consumption": False,
        "scenario": args.scenario,
        "cohort": "rare_leaf_supplement",
        "specification_sha256": _digest(args.spec),
        "taxonomy_sha256": spec["taxonomy_sha256"],
        "status": (
            "shortfall" if any(fill["shortfall"] for fill in per_leaf) else "complete"
        ),
        "assignments": len(assignments),
        "per_leaf": per_leaf,
        "proxy_misses": proxy_misses,
        "no_signal": no_signal,
        "taxonomy_gaps": [
            {"proxy_id": kind, "value": value, "count": count}
            for (kind, value), count in sorted(gap_counts.items())
        ],
        "excluded_core_overlap": excluded_overlap,
        "quarantined_ownership": quarantined_ownership,
        "quarantined_alias_coverage": quarantined_alias,
        "no_primary_view": no_primary_view,
        "cap_rejections": cap_rejections,
        "shared_customer_blocks": len(shared_customers),
        "headline_denominator_inclusion": False,
        "members_sha256": _digest(out_path),
        "private_members_sha256": _digest(private_path),
        "inputs": {
            "resolved_summary_sha256": _digest(args.resolved / "summary.json"),
            "hits_receipt_sha256": _digest(args.hits / "receipt.json"),
            "spec_sha256": _digest(args.spec),
            "core_proposal_sha256": _digest(
                args.core_proposal / "selection-report.json"
            ),
            "runner_sha256": _digest(Path(__file__)),
        },
    }
    (args.output / "selection-report.json").write_bytes(
        canonical_json(report) + b"\n"
    )
    os.chmod(args.output / "selection-report.json", 0o600)
    print(
        f"Supplement proposal: {len(assignments)} rows across "
        f"{sum(1 for f in per_leaf if f['selected'])} leaves; status "
        f"{report['status']}; no admission authorized."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit(
            "Supplement selection failed; no admission claim is valid."
        ) from None

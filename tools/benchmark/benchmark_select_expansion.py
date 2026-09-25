"""Select the proposed core expansion from the resolved candidate frame.

A deterministic bounded sampler: assignment blocks are customers, ordering is
``sha256(seed | customer | observation)`` ranked, and each view fills by
walking the ranked blocks.  Strict-input separation mirrors
``CohortMembership.consistent`` — a member eligible for a strict view may not
share an effective-input projection with any other member; representative-only
repeats are permitted.  Route minimums, the T6/T7 floor, the unfamiliar T6/T7
share and the per-customer cap mirror ``AllocationDesign``; pilot tier counts
are reconstructed by routing the pilot rows through the same pinned baseline.

``--scenario`` selects the resolved decision set: ``as_is`` honours the
current manifest review state; ``if_signed`` uses the decisions that apply
once the declared-corpus and family-registry manifests are signed.  Nothing
here reserves rows or authorizes consumption.
"""

from __future__ import annotations

import argparse
import hashlib
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from benchmark_build_index import private_key
from benchmark_profile_candidates import _digest, _head
from benchmark_profile_candidate_frame import (
    _init_waterfall,
    _load_frame,
    _tier_of,
)
from raylo_txncat.benchmark import project_head
from raylo_txncat.hashing import canonical_json, strict_json_loads

SELECTION_SCHEMA = "benchmark-expansion-selection-v1"
REPORT_SCHEMA = "benchmark-expansion-selection-report-v1"
RESOLVED_SCHEMA = "benchmark-resolved-candidates-v1"
SUMMARY_SCHEMA = "benchmark-evidence-resolution-summary-v1"
CUSTOMER_CAP = 4
STRICT_VIEWS = ("unseen_input", "unfamiliar_merchant")
VIEW_ORDER = ("unfamiliar_merchant", "unseen_input", "representative")
EXPANSION_TARGETS = {
    "representative": 800,
    "unseen_input": 150,
    "unfamiliar_merchant": 50,
}
MIN_ROUTE_ROWS = {"T1": 25, "T2": 25, "T5": 25, "T7": 25}
MIN_T6_T7 = 750
UNFAMILIAR_T6_T7_SHARE = (0.6, 0.8)
UNFAMILIAR_T6_T7_TARGET = 35
SOURCE_POPULATION = 38_700_000
FRAME_ROWS = 10_000
DESIGN_SEED = "benchmark-allocation-2000-v1"


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("rb") as stream:
        for line in stream:
            row = strict_json_loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"{path} contains a malformed row")
            rows.append(row)
    return rows


def _rank(seed: str, customer: str, observation: str) -> str:
    return hashlib.sha256(f"{seed}|{customer}|{observation}".encode()).hexdigest()


def _is_strict(row: dict[str, Any], view_key: str) -> bool:
    views = row[view_key]
    return any(
        views[view]["status"] == "eligible_preflight" for view in STRICT_VIEWS
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "resolved",
        "candidates",
        "pilot-membership",
        "pilot-rows",
        "research",
        "inventory",
        "key-file",
        "index-receipt",
        "output",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument(
        "--scenario",
        choices=("as_is", "if_signed"),
        default="as_is",
    )
    args = parser.parse_args()
    os.umask(0o077)
    args.output.mkdir(mode=0o700, exist_ok=False)
    summary_path = args.resolved / "summary.json"
    summary = strict_json_loads(summary_path.read_bytes())
    if (
        summary.get("schema_version") != SUMMARY_SCHEMA
        or summary.get("authorizes_consumption") is not False
    ):
        raise ValueError("resolved evidence summary is invalid")
    rows = _load_jsonl(args.resolved / "resolved-candidates.jsonl")
    sql = Path(__file__).with_name("benchmark_candidate_frame_extract.sql")
    runner = Path(__file__).with_name("benchmark_candidate_frame_extract.py")
    candidate_receipt, frame_rows = _load_frame(args.candidates, sql, runner)
    snapshot_sha = candidate_receipt["result_sha256"]
    if snapshot_sha != summary["source_snapshot_sha256"]:
        raise ValueError("resolved evidence is bound to another snapshot")
    index_receipt = strict_json_loads(args.index_receipt.read_bytes())
    key = private_key(args.key_file, index_receipt["key_id"])
    raw: dict[str, dict[str, Any]] = {}
    from raylo_txncat.benchmark import observation_key  # noqa: PLC0415

    for frame_row in frame_rows:
        event = observation_key(
            key,
            namespace="plaid",
            account_id=frame_row["account_id"],
            transaction_id=frame_row["transaction_id"],
        )
        candidate_id = hashlib.sha256(
            canonical_json({"source": snapshot_sha, "event": event})
        ).hexdigest()
        raw[candidate_id] = frame_row
    if len(raw) != len(frame_rows):
        raise ValueError("candidate frame identity is not unique")
    fe = _init_waterfall(args.research)

    pilot_rows = _load_jsonl(args.pilot_rows)
    pilot_tiers = Counter()
    for pilot in pilot_rows:
        direction = pilot["direction"]
        _leaf, route = fe.our_leaf(
            pilot.get("merchant") or "",
            direction,
            pilot.get("description") or "",
            fe.plaid_native_leaf,
            "",
            direction,
        )
        pilot_tiers[_tier_of(route)] += 1

    view_key = "views" if args.scenario == "as_is" else "views_if_manifests_signed"
    blocks: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["evidence"]["account_evidence_covered"]:
            blocks[row["customer"]].append(row)
    for block_rows in blocks.values():
        block_rows.sort(
            key=lambda row: _rank(
                DESIGN_SEED, row["customer"], row["observation"]
            )
        )
    block_order = sorted(
        blocks,
        key=lambda customer: min(
            _rank(DESIGN_SEED, customer, row["observation"])
            for row in blocks[customer]
        ),
    )

    selected: dict[str, dict[str, Any]] = {}
    customer_rows: dict[str, int] = defaultdict(int)
    view_counts: dict[str, int] = defaultdict(int)
    tier_counts: Counter = Counter()
    token_owners: dict[tuple[str, str], str] = {}
    projections_by_candidate = {}

    def projections(row: dict[str, Any]):
        candidate_id = row["candidate_id"]
        if candidate_id not in projections_by_candidate:
            if candidate_id not in raw:
                raise ValueError("resolved candidate lacks its frame row")
            projections_by_candidate[candidate_id] = project_head(
                _head(raw[candidate_id]), key
            )
        return projections_by_candidate[candidate_id]

    def try_select(row, view: str) -> bool:
        candidate_id = row["candidate_id"]
        if candidate_id in selected:
            return False
        if row[view_key][view]["status"] != "eligible_preflight":
            return False
        if customer_rows[row["customer"]] >= CUSTOMER_CAP:
            return False
        strict = _is_strict(row, view_key)
        tokens = [(p.version, p.token) for p in projections(row)]
        if strict:
            if any(token in token_owners for token in tokens):
                return False
        else:
            if any(
                token in token_owners
                and _is_strict(selected[token_owners[token]], view_key)
                for token in tokens
            ):
                return False
        selected[candidate_id] = row
        row["primary_view"] = view
        customer_rows[row["customer"]] += 1
        view_counts[view] += 1
        tier_counts[row["baseline_tier"]] += 1
        for token in tokens:
            token_owners[token] = candidate_id
        return True

    for view in VIEW_ORDER:
        target = EXPANSION_TARGETS[view]
        if view == "unfamiliar_merchant":
            # Prefer T6/T7 rows until the share target, then prefer non-T6/T7;
            # a residue pass fills honestly when either pool runs out.
            t67_selected = 0
            for customer in block_order:
                if view_counts[view] >= target:
                    break
                for row in blocks[customer]:
                    if view_counts[view] >= target:
                        break
                    is_t67 = row["baseline_tier"] in {"T6", "T7"}
                    wanted = (
                        is_t67
                        if t67_selected < UNFAMILIAR_T6_T7_TARGET
                        else not is_t67
                    )
                    if wanted and try_select(row, view):
                        t67_selected += is_t67
            for customer in block_order:
                if view_counts[view] >= target:
                    break
                for row in blocks[customer]:
                    if view_counts[view] >= target:
                        break
                    try_select(row, view)
            continue
        if view == "representative":
            # Prefer rows whose baseline tier is short of its minimum so the
            # expansion covers what the pilot cannot (reconstructed below).
            for customer in block_order:
                if view_counts[view] >= target:
                    break
                for row in blocks[customer]:
                    if view_counts[view] >= target:
                        break
                    tier = row["baseline_tier"]
                    needed = MIN_ROUTE_ROWS.get(tier)
                    if needed is not None and (
                        tier_counts[tier] + pilot_tiers.get(tier, 0) < needed
                    ):
                        try_select(row, view)
        for customer in block_order:
            if view_counts[view] >= target:
                break
            for row in blocks[customer]:
                if view_counts[view] >= target:
                    break
                try_select(row, view)

    counts = view_counts
    combined_tiers = tier_counts + pilot_tiers
    constraints = []
    for tier, required in sorted(MIN_ROUTE_ROWS.items()):
        observed = combined_tiers.get(tier, 0)
        constraints.append(
            {
                "constraint": f"min_route_rows:{tier}",
                "status": "met" if observed >= required else "unmet",
                "observed": observed,
                "required": required,
                "expansion": tier_counts.get(tier, 0),
                "pilot": pilot_tiers.get(tier, 0),
            }
        )
    t67 = sum(
        tier_counts.get(tier, 0) + pilot_tiers.get(tier, 0) for tier in ("T6", "T7")
    )
    constraints.append(
        {
            "constraint": "min_t6_t7_rows",
            "status": "met" if t67 >= MIN_T6_T7 else "unmet",
            "observed": t67,
            "required": MIN_T6_T7,
        }
    )
    unfamiliar = [row for row in selected.values() if row["primary_view"] == "unfamiliar_merchant"]
    if unfamiliar:
        share = sum(row["baseline_tier"] in {"T6", "T7"} for row in unfamiliar) / len(
            unfamiliar
        )
        low, high = UNFAMILIAR_T6_T7_SHARE
        constraints.append(
            {
                "constraint": "unfamiliar_t6_t7_share",
                "status": "met" if low <= share <= high else "unmet",
                "observed": share,
                "required": UNFAMILIAR_T6_T7_SHARE,
            }
        )
    constraints.append(
        {
            "constraint": "t3_real_rows",
            "status": "met" if tier_counts.get("T3", 0) == 0 else "unmet",
            "observed": tier_counts.get("T3", 0),
            "required": 0,
        }
    )
    constraints.append(
        {
            "constraint": "customer_cap",
            "status": "met"
            if all(rows <= CUSTOMER_CAP for rows in customer_rows.values())
            else "unmet",
            "observed": max(customer_rows.values(), default=0),
            "required": CUSTOMER_CAP,
        }
    )
    fills = {
        view: {
            "target": EXPANSION_TARGETS[view],
            "selected": counts.get(view, 0),
            "shortfall": max(0, EXPANSION_TARGETS[view] - counts.get(view, 0)),
        }
        for view in ("representative", "unseen_input", "unfamiliar_merchant")
    }
    status = (
        "complete"
        if not any(f["shortfall"] for f in fills.values())
        and all(c["status"] == "met" for c in constraints)
        else "shortfall"
    )

    members = []
    for row in sorted(selected.values(), key=lambda r: r["observation"]):
        eligible = [
            view
            for view in ("representative", "unseen_input", "unfamiliar_merchant")
            if row[view_key][view]["status"] == "eligible_preflight"
        ]
        pool_size = summary["view_status_if_manifests_signed" if args.scenario == "if_signed" else "view_status_as_evidence_stands"][row["primary_view"]].get(
            "eligible_preflight", 0
        )
        members.append(
            {
                "schema_version": SELECTION_SCHEMA,
                "authorizes_consumption": False,
                "selection_scenario": args.scenario,
                "observation_key": row["observation"],
                "event_aliases": (),
                "alias_coverage": (
                    "complete"
                    if row["evidence"]["alias_coverage"]
                    == "pending_and_collision_complete"
                    else "incomplete"
                ),
                "accounts": tuple(
                    sorted({row["account"], *row["sibling_accounts"]})
                ),
                "customers": (row["customer"],),
                "associations": (row["assignment_block"],),
                "content_sha256": row["content_sha256"],
                "projections": [
                    {"version": p.version, "token": p.token}
                    for p in projections(row)
                ],
                "merchant_family": row["merchant_family"],
                "family_status": (
                    "reviewed"
                    if row["primary_view"] == "unfamiliar_merchant"
                    and args.scenario == "if_signed"
                    else "blank"
                    if not row["merchant_present"]
                    else "unknown"
                ),
                "cohort": "core",
                "origin": "expansion",
                "primary_view": row["primary_view"],
                "view_eligibility": eligible,
                "baseline_tier": row["baseline_tier"],
                "route": row["route"],
                "baseline_leaf": row["baseline_leaf"],
                "stratum": row["source_stratum"],
                "direction": row["direction"],
                "merchant_present": row["merchant_present"],
                "inclusion_probability": min(
                    1.0,
                    (FRAME_ROWS / SOURCE_POPULATION)
                    * (
                        EXPANSION_TARGETS[row["primary_view"]]
                        / max(pool_size, 1)
                    ),
                ),
                "selection_probability_reconstructed": True,
                "evidence": row["evidence"],
                "legacy_member_hits": row["legacy_member_hits"],
                "candidate_id": row["candidate_id"],
            }
        )
    out_path = args.output / "selected-expansion.jsonl"
    with out_path.open("xb") as stream:
        for member in members:
            stream.write(canonical_json(member) + b"\n")
    os.chmod(out_path, 0o600)
    report = {
        "schema_version": REPORT_SCHEMA,
        "purpose": "g3_expansion_selection_proposal_not_authority",
        "authorizes_consumption": False,
        "scenario": args.scenario,
        "source_snapshot_sha256": summary["source_snapshot_sha256"],
        "seed": DESIGN_SEED,
        "fills": fills,
        "status": status,
        "constraints": constraints,
        "tier_counts_expansion": dict(sorted(tier_counts.items())),
        "tier_counts_pilot": dict(sorted(pilot_tiers.items())),
        "customer_blocks_touched": len({r["customer"] for r in selected.values()}),
        "selected": len(members),
        "inputs": {
            "resolved_candidates_sha256": _digest(
                args.resolved / "resolved-candidates.jsonl"
            ),
            "resolved_summary_sha256": _digest(summary_path),
            "pilot_membership_sha256": _digest(args.pilot_membership),
            "runner_sha256": _digest(Path(__file__)),
        },
    }
    (args.output / "selection-report.json").write_bytes(
        canonical_json(report) + b"\n"
    )
    os.chmod(args.output / "selection-report.json", 0o600)
    print(
        f"Selected {len(members)} expansion rows ({status}); "
        f"fills: "
        + ", ".join(
            f"{view}={fill['selected']}/{fill['target']}"
            for view, fill in fills.items()
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit(
            "Expansion selection failed; no admission claim is valid."
        ) from None

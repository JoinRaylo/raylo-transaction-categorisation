"""Profile the G2 candidate frame for the 1,500-row expansion admission review.

Extends the pilot admission profile with the candidate-frame contract fields:
the deterministic baseline route under the pinned waterfall runtime, provider
category family diagnostics, pilot-membership overlap accounting, and aggregate
pre-label proxy evidence for the rare-leaf supplement specification.  The frame
is source data, not authority state; unknown historical aliases, family lineage
and legacy coverage remain quarantine reasons, and nothing here reserves,
labels or authorizes consumption.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

from benchmark_build_index import private_key
from benchmark_profile_candidates import (
    ARTIFACTS,
    POLICY_SHA256,
    POLICY_VERSION,
    SCOPE_CONTRACT,
    SCOPE_CONTRACT_SHA256,
    SOURCE_TABLE,
    _block_stats,
    _candidate_keys,
    _digest,
    _load_artifacts,
    _screen_inputs,
    _screen_merchants,
    _view_decisions,
)
from raylo_txncat.benchmark_exposure import ExposureIndex
from raylo_txncat.dictionary import normalise_merchant
from raylo_txncat.hashing import canonical_json, strict_json_loads
from raylo_txncat.head_hinge import numeric_features

MAX_CANDIDATES = 10_000
FRAME_SCHEMA = "benchmark-candidate-frame-extract-v1"
FRAME_PURPOSE = "g2_candidate_frame_read_not_admission"
PROFILE_SCHEMA = "benchmark-admission-profile-v2"
PROFILE_POLICY_VERSION = "benchmark-admission-profile-policy-v2"
FRAME_SQL_NAME = "benchmark_candidate_frame_extract.sql"
FRAME_RUNNER_NAME = "benchmark_candidate_frame_extract.py"
RUNTIME_FILES = (
    "taxonomy/taxonomy.csv",
    "taxonomy/merchant_dictionary.csv",
    "taxonomy/rules/deterministic_rules.csv",
    "taxonomy/rules/t2_entity_collisions.csv",
    "src/final_evaluation.py",
    "src/generate_crosswalk_sql.py",
)
# Core expansion requirements after the immutable 500-row pilot.
EXPANSION_TARGETS = {
    "representative": 800,
    "unseen_input": 150,
    "unfamiliar_merchant": 50,
}
CATEGORY_FAMILY_TOP = 20
MERCHANT_LABEL_SOURCES = (
    "data/gold_merchant_labels.csv",
    "data/gold_tail_labels.csv",
    "data/production_labels_tranche4.csv",
)
MERCHANT_LEAF_FIELDS = ("final_leaf", "gold_leaf", "detailed_category", "leaf")
HISTORICAL_LABEL_SOURCE = "outputs/tuning_train.jsonl"


def _validate_frame_receipt(receipt: dict, result_path: Path, sql: Path, runner: Path) -> None:
    if (
        receipt.get("schema_version") != FRAME_SCHEMA
        or receipt.get("purpose") != FRAME_PURPOSE
        or receipt.get("project") != "raylo-production"
        or receipt.get("location") != "EU"
        or receipt.get("statement_type") != "SELECT"
        or receipt.get("source_table") != SOURCE_TABLE
        or receipt.get("source_kind") != SCOPE_CONTRACT["source_kind"]
        or receipt.get("scope_contract") != SCOPE_CONTRACT
        or receipt.get("scope_contract_sha256") != SCOPE_CONTRACT_SHA256
        or receipt.get("anonymous_id_recovery") is not False
        or receipt.get("authorizes_consumption") is not False
        or receipt.get("executed") is not True
    ):
        raise ValueError("candidate frame receipt is outside the approved source contract")
    if receipt.get("sql_sha256") != _digest(sql) or receipt.get("runner_sha256") != _digest(
        runner
    ):
        raise ValueError("candidate frame receipt is not bound to the current extractor")
    if not isinstance(receipt.get("result_sha256"), str) or _digest(
        result_path
    ) != receipt["result_sha256"]:
        raise ValueError("candidate frame result is incomplete or changed")
    if (
        type(receipt.get("candidate_limit")) is not int
        or not 0 < receipt["candidate_limit"] <= MAX_CANDIDATES
    ):
        raise ValueError("candidate limit is outside scope")
    if (
        type(receipt.get("result_rows")) is not int
        or not 0 < receipt["result_rows"] <= receipt["candidate_limit"]
    ):
        raise ValueError("candidate frame result count is outside scope")
    for field in ("dry_run_bytes", "bytes_processed", "bytes_billed"):
        if type(receipt.get(field)) is not int or receipt[field] < 0:
            raise ValueError("candidate frame byte receipt is invalid")


def _load_frame(directory: Path, sql: Path, runner: Path) -> tuple[dict, list[dict]]:
    receipt = strict_json_loads((directory / "receipt.json").read_bytes())
    path = directory / "candidates.jsonl"
    if not isinstance(receipt, dict):
        raise ValueError("candidate frame receipt is not an object")
    _validate_frame_receipt(receipt, path, sql, runner)
    rows = []
    events = set()
    with path.open("rb") as stream:
        for line in stream:
            row = strict_json_loads(line)
            if not isinstance(row, dict):
                raise ValueError("candidate frame row is not an object")
            required = (
                "account_id",
                "transaction_id",
                "customer_id",
                "assessment_id",
                "checkout_id",
                "user_id",
            )
            if any(type(row.get(field)) is not str or not row[field] for field in required):
                raise ValueError("candidate frame linkage fields are incomplete")
            link_counts = (
                "assessment_checkout_count",
                "checkout_user_count",
                "user_customer_count",
                "customer_record_count",
            )
            if any(
                type(row.get(field)) is not int or row[field] != 1 for field in link_counts
            ):
                raise ValueError("candidate frame row is not backed by unique current links")
            if not isinstance(row.get("content_sha256"), str) or len(
                row["content_sha256"]
            ) != 64:
                raise ValueError("candidate frame row lacks its content revision digest")
            if not isinstance(row.get("category"), list):
                raise ValueError("candidate frame provider category is not an array")
            event = (row["account_id"], row["transaction_id"])
            if event in events:
                raise ValueError("candidate frame contains duplicate events")
            events.add(event)
            rows.append(row)
    if len(rows) != receipt["result_rows"] or not 0 < len(rows) <= MAX_CANDIDATES:
        raise ValueError("candidate frame count is incomplete or outside scope")
    return receipt, rows


def _verify_runtime(research: Path, inventory: dict) -> dict[str, str]:
    digests = {}
    for relative in RUNTIME_FILES:
        path = research / relative
        if relative not in inventory or _digest(path) != inventory[relative]["sha256"]:
            raise ValueError(f"pinned waterfall runtime changed: {relative}")
        digests[relative] = inventory[relative]["sha256"]
    return digests


def _init_waterfall(research: Path):
    """Load the pinned waterfall runtime from the audited research checkout."""

    sys.path.insert(0, str(research / "src"))
    import final_evaluation as fe  # noqa: PLC0415

    fe.SUB_MAP, fe.PRI_MAP, fe.PLAID_MAP, _ = fe.load_crosswalk()
    fe.DICTIONARY = fe.load_dictionary()
    fe.RULES = fe.load_rules()
    return fe


def _tier_of(route_label: str) -> str:
    return route_label.split("_", 1)[0]


def _dictionary_rule_leaf(fe, merchant: str, direction: str, description: str):
    """The T4/T5 deterministic signal only; None when neither fires."""

    leaf = fe.DICTIONARY.get(merchant)
    if leaf is not None:
        return leaf
    for rule in fe.RULES:
        if fe._rule_matches(rule, merchant, description, direction):
            return rule["detailed_category"]
    return None


def _merchant_label_map(research: Path) -> dict[str, str]:
    """Approved merchant-level labels keyed by normalised merchant name."""

    import csv  # noqa: PLC0415

    mapping: dict[str, str] = {}
    for relative in MERCHANT_LABEL_SOURCES:
        path = research / relative
        if not path.exists():
            continue
        with path.open() as stream:
            for row in csv.DictReader(stream):
                merchant = normalise_merchant(
                    row.get("merchant") or row.get("merchant_raw") or ""
                )
                leaf = next(
                    (
                        row[field].strip()
                        for field in MERCHANT_LEAF_FIELDS
                        if row.get(field) and row[field].strip()
                    ),
                    "",
                )
                if merchant and leaf:
                    mapping.setdefault(merchant, leaf)
    return mapping


def _historical_label_map(research: Path) -> dict[str, str]:
    """Modal supervised leaf per normalised merchant in the tuning corpus."""

    import json  # noqa: PLC0415

    counts: dict[str, Counter] = defaultdict(Counter)
    path = research / HISTORICAL_LABEL_SOURCE
    with path.open() as stream:
        for line in stream:
            messages = json.loads(line).get("messages") or []
            user = next(
                (m.get("content", "") for m in messages if m.get("role") == "user"), ""
            )
            leaf = next(
                (m.get("content", "") for m in messages if m.get("role") == "assistant"),
                "",
            ).strip()
            merchant = ""
            for part in user.split("\n"):
                if part.startswith("merchant:"):
                    merchant = part.split(":", 1)[1]
                    break
            merchant = normalise_merchant(merchant)
            if merchant and leaf:
                counts[merchant][leaf] += 1
    return {
        merchant: tally.most_common(1)[0][0] for merchant, tally in counts.items()
    }


def _hinge_predictions(research: Path, heads) -> list[str]:
    """Pinned hinge baseline leaf for each candidate head."""

    import joblib  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415
    from scipy.sparse import csr_matrix, hstack  # noqa: PLC0415

    bundle = joblib.load(research / ARTIFACTS["hinge"])
    vectorizer, classifier = bundle["vectorizer"], bundle["clf"]
    predictions = []
    for start in range(0, len(heads), 2048):
        batch = heads[start : start + 2048]
        _, logs, directions = numeric_features(batch)
        matrix = hstack(
            [
                vectorizer.transform([head.hinge_text for head in batch]),
                csr_matrix(np.column_stack([logs, directions])),
            ],
            format="csr",
        )
        predictions.extend(classifier.predict(matrix).tolist())
    if len(predictions) != len(heads):
        raise ValueError("baseline prediction count is incomplete")
    return predictions


def _load_pilot_membership(path: Path) -> tuple[set, set, set]:
    """The immutable pilot membership: raw keys stay inside the private file."""

    import csv  # noqa: PLC0415

    events, accounts, customers = set(), set(), set()
    with path.open() as stream:
        for row in csv.DictReader(stream):
            events.add((row["account_id"], row["transaction_id"]))
            accounts.add(row["account_id"])
            customers.add(row["customer_id"])
    return events, accounts, customers


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "candidates",
        "research",
        "inventory",
        "index",
        "key-file",
        "legacy",
        "pilot-membership",
        "output",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    args.output.mkdir(mode=0o700, exist_ok=False)
    sql = Path(__file__).with_name(FRAME_SQL_NAME)
    runner = Path(__file__).with_name(FRAME_RUNNER_NAME)
    candidate_receipt, rows = _load_frame(args.candidates, sql, runner)
    inventory = strict_json_loads(args.inventory.read_bytes())["files"]
    runtime_digests = _verify_runtime(args.research, inventory)
    fe = _init_waterfall(args.research)
    merchant_labels = _merchant_label_map(args.research)
    historical_labels = _historical_label_map(args.research)
    pilot_events, pilot_accounts, pilot_customers = _load_pilot_membership(
        args.pilot_membership
    )
    index_receipt = strict_json_loads((args.index / "receipt.json").read_bytes())
    key = private_key(args.key_file, index_receipt["key_id"])
    index = ExposureIndex(
        args.index / "inputs.sqlite",
        expected_sha256=index_receipt["database_sha256"],
        key=key,
    )
    try:
        tokenizer, vectorizer = _load_artifacts(args.research, inventory)
        heads, events, projections, values = _candidate_keys(rows, key, tokenizer, vectorizer)
        input_hits, input_source_rows = _screen_inputs(
            args.research, inventory, values, tokenizer, vectorizer
        )
        merchant_hits, merchant_source_rows = _screen_merchants(
            args.research, inventory, args.legacy, rows
        )
        hinge_leafs = _hinge_predictions(args.research, heads)
        opaque = []
        reason_counts = {
            view: Counter() for view in ("representative", "unseen_input", "unfamiliar_merchant")
        }
        status_counts = {view: Counter() for view in reason_counts}
        combinations = Counter()
        strata = Counter()
        blocks = {name: [] for name in ("customer", "account", "assignment")}
        input_counts = Counter()
        merchant_known_count = 0
        merchant_present_count = 0
        tier_counts = Counter()
        route_counts = Counter()
        tier_direction = Counter()
        tier_merchant = Counter()
        family_counts = Counter()
        detailed_category_counts = Counter()
        proxy_counts = {
            name: Counter()
            for name in (
                "dictionary_rule",
                "merchant_lexicon",
                "provider_category",
                "historical_label",
                "baseline_prediction",
            )
        }
        proxy_row_coverage = Counter()
        pilot_overlap = Counter()
        view_cross_counts = {view: Counter() for view in status_counts}
        net_view_counts = {view: Counter() for view in status_counts}
        dates = []
        content_hashes = []
        for index_number, row in enumerate(rows):
            event = events[index_number]
            account = key.token("account", {"namespace": "plaid", "account": row["account_id"]})
            customer = key.token(
                "customer", {"namespace": "raylo", "customer": row["customer_id"]}
            )
            assignment = key.token(
                "customer",
                {
                    "namespace": "raylo",
                    "customer": row["customer_id"],
                    "policy": "customer-block-v1",
                },
            )
            input_sources = set()
            for projection in projections[index_number]:
                input_sources.update(index.lookup(projection)["sources"])
            for name in ("token48", "surface_fold", "hinge_sparse"):
                for source, found in input_hits[name].items():
                    if index_number in found:
                        input_sources.add(source)
                if any(index_number in found for found in input_hits[name].values()):
                    input_counts[name] += 1
            merchant = normalise_merchant(row.get("merchant_name"))
            merchant_present = bool(merchant)
            merchant_known = bool(merchant_hits[index_number])
            merchant_present_count += merchant_present
            merchant_known_count += merchant_known
            family_status = (
                "blank"
                if not merchant_present
                else "known_name"
                if merchant_known
                else "unknown_name"
            )
            decisions = _view_decisions(
                current_identity=True,
                aliases_verified=False,
                identity_history_complete=False,
                input_sources=input_sources,
                input_history_complete=False,
                merchant_present=merchant_present,
                merchant_known=merchant_known,
                family_reviewed=False,
                family_history_complete=False,
                legacy_index_complete=False,
            )
            eligible = []
            for view, decision in decisions.items():
                status_counts[view][decision["status"]] += 1
                reason_counts[view].update(decision["reasons"])
                if decision["status"] == "eligible_preflight":
                    eligible.append(view)
            combinations["+".join(eligible) or "none"] += 1
            strata[row.get("source_stratum", "unknown")] += 1
            direction = row.get("direction", "unknown")
            description = (
                row.get("description")
                if row.get("description") is not None
                else row.get("transaction_name") or ""
            )
            native = row.get("detailed_credit_category") or ""
            baseline_leaf, route = fe.our_leaf(
                row.get("merchant_name") or "",
                direction,
                description,
                fe.plaid_native_leaf,
                native,
                direction,
            )
            tier = _tier_of(route)
            tier_counts[tier] += 1
            route_counts[route] += 1
            tier_direction[f"{tier}|{direction}"] += 1
            tier_merchant[f"{tier}|{'present' if merchant_present else 'blank'}"] += 1
            family = row.get("primary_credit_category") or "absent"
            family_counts[family] += 1
            detailed_category_counts[native or "absent"] += 1
            proxy_values = {
                "dictionary_rule": _dictionary_rule_leaf(
                    fe, merchant, direction, description
                ),
                "merchant_lexicon": merchant_labels.get(merchant),
                "provider_category": fe.PLAID_MAP.get(native) if native else None,
                "historical_label": historical_labels.get(merchant),
                "baseline_prediction": hinge_leafs[index_number],
            }
            for proxy_id, value in proxy_values.items():
                if value is not None:
                    proxy_counts[proxy_id][value] += 1
                    proxy_row_coverage[proxy_id] += 1
            overlap = {
                "event": (row["account_id"], row["transaction_id"]) in pilot_events,
                "account": row["account_id"] in pilot_accounts,
                "customer": row["customer_id"] in pilot_customers,
            }
            for kind, hit in overlap.items():
                pilot_overlap[kind] += hit
            pilot_blocked = overlap["customer"] or overlap["account"] or overlap["event"]
            for view, decision in decisions.items():
                view_cross_counts[view][
                    "|".join(
                        (
                            decision["status"],
                            tier,
                            direction,
                            "present" if merchant_present else "blank",
                            family_status,
                            family,
                        )
                    )
                ] += 1
                if not pilot_blocked:
                    net_view_counts[view][decision["status"]] += 1
            dates.append(row["transaction_date"])
            content_hashes.append(row["content_sha256"])
            blocks["customer"].append(customer)
            blocks["account"].append(account)
            blocks["assignment"].append(assignment)
            opaque.append(
                {
                    "candidate_id": hashlib.sha256(
                        canonical_json(
                            {"source": candidate_receipt["result_sha256"], "event": event}
                        )
                    ).hexdigest(),
                    "source_snapshot_sha256": candidate_receipt["result_sha256"],
                    "observation": event,
                    "event_aliases": (),
                    "account": account,
                    "customer": customer,
                    "assignment_block": assignment,
                    "merchant_family": key.token(
                        "family", {"namespace": "plaid", "merchant": merchant}
                    )
                    if merchant
                    else None,
                    "input_sources": tuple(sorted(input_sources)),
                    "merchant_present": merchant_present,
                    "merchant_known_sources": tuple(sorted(merchant_hits[index_number])),
                    "views": decisions,
                    "source_stratum": row.get("source_stratum", "unknown"),
                    "direction": direction,
                    "baseline_tier": tier,
                    "route": route,
                    "baseline_leaf": baseline_leaf,
                    "category_family": family,
                    "provider_category": native or None,
                    "content_sha256": row["content_sha256"],
                    "proxy_signals": {
                        proxy_id: value
                        for proxy_id, value in proxy_values.items()
                        if value is not None
                    },
                    "pilot_overlap": overlap,
                    "authorizes_consumption": False,
                }
            )
        opaque_path = args.output / "opaque-candidates.jsonl"
        with opaque_path.open("xb") as stream:
            for record in opaque:
                stream.write(canonical_json(record) + b"\n")
        os.chmod(opaque_path, 0o600)
        family_top = dict(
            sorted(family_counts.items(), key=lambda kv: (-kv[1], kv[0]))[
                :CATEGORY_FAMILY_TOP
            ]
        )
        family_other = sum(family_counts.values()) - sum(family_top.values())
        view_cross = {}
        for view in ("representative", "unseen_input", "unfamiliar_merchant"):
            view_cross[view] = {
                "status": dict(sorted(status_counts[view].items())),
                "reasons": dict(sorted(reason_counts[view].items())),
                "status_tier_direction_merchant_family_categoryfamily": dict(
                    sorted(view_cross_counts[view].items())
                ),
            }
        capacity = {}
        for view, target in EXPANSION_TARGETS.items():
            quarantined = status_counts[view].get("quarantine", 0)
            eligible = status_counts[view].get("eligible_preflight", 0)
            net_quarantined = net_view_counts[view].get("quarantine", 0)
            net_eligible = net_view_counts[view].get("eligible_preflight", 0)
            capacity[view] = {
                "expansion_target": target,
                "eligible_preflight": eligible,
                "quarantined_pending_history": quarantined,
                "rejected": status_counts[view].get("reject", 0),
                "capacity_if_quarantine_resolves": eligible + quarantined,
                "net_of_pilot_customer_blocks": net_eligible + net_quarantined,
                "net_rejected": net_view_counts[view].get("reject", 0),
            }
        profile = {
            "schema_version": PROFILE_SCHEMA,
            "purpose": "admission_planning_not_benchmark_authority",
            "source_kind": "customer_linked_plaid_materialized_frame",
            "scope_contract": SCOPE_CONTRACT,
            "scope_contract_sha256": SCOPE_CONTRACT_SHA256,
            "policy_version": POLICY_VERSION,
            "policy_sha256": POLICY_SHA256,
            "frame_policy_version": PROFILE_POLICY_VERSION,
            "source_snapshot_sha256": candidate_receipt["result_sha256"],
            "content_sha256": hashlib.sha256(
                canonical_json(sorted(content_hashes))
            ).hexdigest(),
            "window": {
                "transaction_date_min": min(dates),
                "transaction_date_max": max(dates),
            },
            "candidate_rows": len(rows),
            "distinct_events": len(events),
            "source_strata": dict(sorted(strata.items())),
            "block_stats": _block_stats(blocks),
            "input_exposure": dict(sorted(input_counts.items())),
            "merchant": {
                "present": merchant_present_count,
                "blank": len(rows) - merchant_present_count,
                "known_name": merchant_known_count,
                "unknown_name": merchant_present_count - merchant_known_count,
                "family_reviewed": 0,
            },
            "routing": {
                "runtime_digests": runtime_digests,
                "baseline_tier_counts": dict(sorted(tier_counts.items())),
                "route_label_counts": dict(sorted(route_counts.items())),
                "tier_by_direction": dict(sorted(tier_direction.items())),
                "tier_by_merchant_presence": dict(sorted(tier_merchant.items())),
            },
            "category_family": {
                "top": family_top,
                "other": family_other,
                "detailed_category_counts": dict(
                    sorted(
                        detailed_category_counts.items(),
                        key=lambda kv: (-kv[1], kv[0]),
                    )
                ),
            },
            "proxy_evidence": {
                "row_coverage": dict(sorted(proxy_row_coverage.items())),
                "leaf_counts": {
                    proxy_id: dict(sorted(counts.items()))
                    for proxy_id, counts in sorted(proxy_counts.items())
                },
            },
            "pilot_overlap": {
                "membership_sha256": _digest(args.pilot_membership),
                "event_overlap_rows": pilot_overlap["event"],
                "account_overlap_rows": pilot_overlap["account"],
                "customer_overlap_rows": pilot_overlap["customer"],
                "note": (
                    "rows sharing a pilot customer block are unavailable to the "
                    "expansion; whole-customer allocation removes them at admission"
                ),
            },
            "views": view_cross,
            "eligible_view_combinations": dict(sorted(combinations.items())),
            "capacity": capacity,
            "lineage": {
                "candidate_receipt_sha256": _digest(args.candidates / "receipt.json"),
                "index_receipt_sha256": _digest(args.index / "receipt.json"),
                "index_database_sha256": index_receipt["database_sha256"],
                "inventory_sha256": _digest(args.inventory),
                "legacy_summary_sha256": _digest(args.legacy / "summary.json"),
                "candidate_extractor_sha256": _digest(runner),
                "candidate_sql_sha256": _digest(sql),
                "profiler_sha256": _digest(Path(__file__)),
                "policy_sha256": POLICY_SHA256,
                "input_source_rows": input_source_rows,
                "merchant_source_rows": merchant_source_rows,
                "opaque_candidates_sha256": _digest(opaque_path),
            },
            "history_flags": {
                "event_aliases_verified": False,
                "identity_history_complete": False,
                "input_history_complete": False,
                "family_history_complete": False,
                "legacy_index_complete": False,
            },
            "authorizes_consumption": False,
            "rows_reserved_or_labelled": 0,
            "risk_controls": {
                "effective_iam_isolation": "accepted_internal_benchmark_risk",
                "logical_train_selection_separation_required": True,
                "managed_runtime_authority_required": True,
            },
            "next_gate": (
                "resolve aliases, identity history, reviewed merchant families and "
                "legacy coverage, then design admission under G3"
            ),
        }
        (args.output / "profile.json").write_bytes(canonical_json(profile) + b"\n")
        os.chmod(args.output / "profile.json", 0o600)
        print(
            f"Profiled {len(rows):,} candidate frame rows; no admission authorized."
        )
    finally:
        index.close()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit(
            "Candidate frame profile failed; no eligibility or consumption claim "
            "is valid."
        ) from None

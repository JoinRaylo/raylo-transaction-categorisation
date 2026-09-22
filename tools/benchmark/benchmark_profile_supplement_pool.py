"""Profile the G3 rare-leaf supplement pool for admission design.

Reuses the frame profiler's screening internals over the supplement pool and
emits opaque per-candidate rows carrying the leaf hits, proxy signals and the
same per-view decision fields.  All five history flags stay false here — the
resolver pass resolves them from the evidence sidecars.  Nothing is reserved,
labelled or authorized for consumption.
"""

from __future__ import annotations

import argparse
import hashlib
import os
from collections import Counter
from pathlib import Path

from benchmark_build_index import private_key
from benchmark_profile_candidate_frame import (
    PROFILE_POLICY_VERSION,
    PROFILE_SCHEMA,
    SCOPE_CONTRACT,
    SCOPE_CONTRACT_SHA256,
    _digest,
    _dictionary_rule_leaf,
    _hinge_predictions,
    _historical_label_map,
    _init_waterfall,
    _load_pilot_membership,
    _merchant_label_map,
    _tier_of,
)
from benchmark_profile_candidates import (
    _candidate_keys,
    _load_artifacts,
    _screen_inputs,
    _screen_merchants,
    _view_decisions,
)
from raylo_txncat.benchmark_exposure import ExposureIndex
from raylo_txncat.dictionary import normalise_merchant
from raylo_txncat.hashing import canonical_json, strict_json_loads
from benchmark_candidate_frame_extract import _validate_row

PURPOSE = "g3_supplement_pool_read_not_admission"
MAX_POOL_ROWS = 50_000


def _load_pool(directory: Path, sql: Path, runner: Path):
    receipt = strict_json_loads((directory / "receipt.json").read_bytes())
    if (
        receipt.get("schema_version") != "benchmark-candidate-frame-extract-v1"
        or receipt.get("purpose") != PURPOSE
        or receipt.get("scope_contract") != SCOPE_CONTRACT
        or receipt.get("scope_contract_sha256") != SCOPE_CONTRACT_SHA256
        or receipt.get("authorizes_consumption") is not False
        or receipt.get("executed") is not True
        or receipt.get("sql_sha256") != _digest(sql)
        or receipt.get("runner_sha256") != _digest(runner)
        or receipt.get("result_sha256") != _digest(directory / "candidates.jsonl")
    ):
        raise ValueError("supplement pool receipt is outside the contract")
    rows = []
    seen = set()
    with (directory / "candidates.jsonl").open("rb") as stream:
        for line in stream:
            row = strict_json_loads(line)
            _validate_row(row)
            event = (row["account_id"], row["transaction_id"])
            if event in seen:
                raise ValueError("supplement pool contains a duplicate event")
            seen.add(event)
            rows.append(row)
    if len(rows) != receipt.get("result_rows") or len(rows) > MAX_POOL_ROWS:
        raise ValueError("supplement pool size is outside scope")
    return receipt, rows


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
    sql = Path(__file__).with_name("benchmark_supplement_extract.sql")
    runner = Path(__file__).with_name("benchmark_supplement_extract.py")
    receipt, rows = _load_pool(args.candidates, sql, runner)
    snapshot_sha = receipt["result_sha256"]
    inventory = strict_json_loads(args.inventory.read_bytes())["files"]
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
        heads, events, projections, values = _candidate_keys(
            rows, key, tokenizer, vectorizer
        )
        input_hits, _input_source_rows = _screen_inputs(
            args.research, inventory, values, tokenizer, vectorizer
        )
        merchant_hits, _merchant_source_rows = _screen_merchants(
            args.research, inventory, args.legacy, rows
        )
        hinge_leafs = _hinge_predictions(args.research, heads)
        opaque = []
        for index_number, row in enumerate(rows):
            event = events[index_number]
            account = key.token(
                "account", {"namespace": "plaid", "account": row["account_id"]}
            )
            customer = key.token(
                "customer", {"namespace": "raylo", "customer": row["customer_id"]}
            )
            input_sources = set()
            for projection in projections[index_number]:
                input_sources.update(index.lookup(projection)["sources"])
            for name in ("token48", "surface_fold", "hinge_sparse"):
                for source, found in input_hits[name].items():
                    if index_number in found:
                        input_sources.add(source)
            merchant = normalise_merchant(row.get("merchant_name"))
            merchant_present = bool(merchant)
            merchant_known = bool(merchant_hits[index_number])
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
            proxy_values = {
                "dictionary_rule": _dictionary_rule_leaf(
                    fe, merchant, direction, description
                ),
                "merchant_lexicon": merchant_labels.get(merchant),
                "provider_category": fe.PLAID_MAP.get(native) if native else None,
                "historical_label": historical_labels.get(merchant),
                "baseline_prediction": hinge_leafs[index_number],
            }
            overlap = {
                "event": (row["account_id"], row["transaction_id"])
                in pilot_events,
                "account": row["account_id"] in pilot_accounts,
                "customer": row["customer_id"] in pilot_customers,
            }
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
            opaque.append(
                {
                    "candidate_id": hashlib.sha256(
                        canonical_json(
                            {
                                "source": snapshot_sha,
                                "event": event,
                            }
                        )
                    ).hexdigest(),
                    "source_snapshot_sha256": snapshot_sha,
                    "observation": event,
                    "projections": tuple(
                        {"version": p.version, "token": p.token}
                        for p in projections[index_number]
                    ),
                    "event_aliases": (),
                    "account": account,
                    "customer": customer,
                    "assignment_block": key.token(
                        "customer",
                        {
                            "namespace": "raylo",
                            "customer": row["customer_id"],
                            "policy": "customer-block-v1",
                        },
                    ),
                    "merchant_family": key.token(
                        "family", {"namespace": "plaid", "merchant": merchant}
                    )
                    if merchant
                    else None,
                    "input_sources": tuple(sorted(input_sources)),
                    "merchant_present": merchant_present,
                    "merchant_known_sources": tuple(
                        sorted(merchant_hits[index_number])
                    ),
                    "views": decisions,
                    "source_stratum": row.get("source_stratum", "unknown"),
                    "direction": direction,
                    "baseline_tier": _tier_of(route),
                    "route": route,
                    "baseline_leaf": baseline_leaf,
                    "category_family": row.get("primary_credit_category")
                    or "absent",
                    "provider_category": native or None,
                    "content_sha256": row["content_sha256"],
                    "proxy_signals": {
                        proxy_id: value
                        for proxy_id, value in proxy_values.items()
                        if value is not None
                    },
                    "leaf_hits": tuple(row.get("leaf_hits") or ()),
                    "supplement_source": row.get("supplement_source", "unknown"),
                    "pilot_overlap": overlap,
                    "authorizes_consumption": False,
                }
            )
        out_path = args.output / "opaque-candidates.jsonl"
        with out_path.open("xb") as stream:
            for record in opaque:
                stream.write(canonical_json(record) + b"\n")
        os.chmod(out_path, 0o600)
        leaf_counts = Counter(
            leaf for row in opaque for leaf in row["leaf_hits"]
        )
        profile = {
            "schema_version": PROFILE_SCHEMA,
            "purpose": "supplement_pool_profile_not_authority",
            "authorizes_consumption": False,
            "scope_contract": SCOPE_CONTRACT,
            "scope_contract_sha256": SCOPE_CONTRACT_SHA256,
            "policy_version": PROFILE_POLICY_VERSION,
            "source_snapshot_sha256": snapshot_sha,
            "candidate_rows": len(opaque),
            "leaf_hit_counts": dict(sorted(leaf_counts.items())),
            "supplement_source_counts": dict(
                sorted(
                    Counter(
                        row["supplement_source"] for row in opaque
                    ).items()
                )
            ),
            "pilot_overlap_events": sum(
                row["pilot_overlap"]["event"] for row in opaque
            ),
            "inputs": {
                "candidate_receipt_sha256": _digest(
                    args.candidates / "receipt.json"
                ),
                "runner_sha256": _digest(Path(__file__)),
            },
        }
        (args.output / "profile.json").write_bytes(
            canonical_json(profile) + b"\n"
        )
        os.chmod(args.output / "profile.json", 0o600)
        print(
            f"Supplement pool profiled: {len(opaque)} rows covering "
            f"{len(leaf_counts)} roster leaves; no admission authorized."
        )
    finally:
        index.close()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit(
            "Supplement pool profiling failed; no admission claim is valid."
        ) from None

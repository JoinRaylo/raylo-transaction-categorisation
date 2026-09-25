"""Filter the supplement pool to roster-hit candidates for evidence reads.

Runs the frozen spec's proxy precedence walk over the profiled supplement
pool and emits the raw pool rows that resolve to a roster leaf, with a
derived-pool receipt binding the pool result, profile, spec and predicate
manifest.  Only roster-hit rows can ever be selected, so scoping account
evidence to their accounts bounds the warehouse reads without changing
eligibility.  Nothing here reserves, labels or authorizes consumption.
"""

from __future__ import annotations

import argparse
import hashlib
import os
from collections import Counter
from pathlib import Path

from benchmark_build_index import private_key
from benchmark_profile_supplement_pool import _load_pool
from raylo_txncat.benchmark import observation_key
from raylo_txncat.hashing import canonical_json, strict_json_loads


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()





def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "candidates",
        "profile",
        "spec",
        "index-receipt",
        "key-file",
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

    spec = strict_json_loads(args.spec.read_bytes())
    if spec.get("schema_version") != "benchmark-rare-leaf-spec-v1":
        raise ValueError("rare-leaf specification is invalid")
    roster = {quota["leaf"] for quota in spec["roster"]}
    precedence = sorted(spec["proxies"], key=lambda item: item["precedence"])

    profile = strict_json_loads((args.profile / "profile.json").read_bytes())
    if profile.get("source_snapshot_sha256") != snapshot_sha:
        raise ValueError("supplement profile is not bound to the pool")
    opaque = {}
    for line in (args.profile / "opaque-candidates.jsonl").open("rb"):
        entry = strict_json_loads(line)
        opaque[entry["observation"]] = entry
    if len(opaque) != len(rows):
        raise ValueError("opaque supplement profile does not cover the pool")

    index_receipt = strict_json_loads(args.index_receipt.read_bytes())
    key = private_key(args.key_file, index_receipt["key_id"])

    hits = []
    per_leaf = Counter()
    per_proxy = Counter()
    for row in rows:
        event = observation_key(
            key,
            namespace="plaid",
            account_id=row["account_id"],
            transaction_id=row["transaction_id"],
        )
        entry = opaque.get(event)
        if entry is None:
            raise ValueError("opaque profile does not cover a pool event")
        signals = entry.get("proxy_signals") or {}
        intended = None
        source = None
        for proxy in precedence:
            value = signals.get(proxy["kind"])
            if value is None:
                continue
            if value in roster:
                intended = value
                source = proxy["kind"]
                break
        if intended is not None:
            hits.append(row)
            per_leaf[intended] += 1
            per_proxy[source] += 1

    out_path = args.output / "candidates.jsonl"
    with out_path.open("xb") as stream:
        for row in hits:
            stream.write(canonical_json(row) + b"\n")
    os.chmod(out_path, 0o600)
    derived = {
        "schema_version": "benchmark-derived-pool-v1",
        "purpose": "g3_roster_hit_evidence_scope_not_admission",
        "authorizes_consumption": False,
        "pool_result_sha256": snapshot_sha,
        "pool_receipt_sha256": _digest(args.candidates / "receipt.json"),
        "profile_sha256": _digest(args.profile / "profile.json"),
        "spec_sha256": _digest(args.spec),
        "pool_rows": len(rows),
        "roster_hit_rows": len(hits),
        "per_leaf_hits": dict(sorted(per_leaf.items())),
        "per_proxy_hits": dict(sorted(per_proxy.items())),
        "leaves_with_hits": len(per_leaf),
        "leaves_without_hits": sorted(roster - set(per_leaf)),
        "result_sha256": _digest(out_path),
        "runner_sha256": _digest(Path(__file__)),
    }
    (args.output / "receipt.json").write_bytes(
        canonical_json(derived) + b"\n"
    )
    os.chmod(args.output / "receipt.json", 0o600)
    print(
        f"Roster-hit pool: {len(hits)} rows across {len(per_leaf)} leaves; "
        f"{len(roster) - len(per_leaf)} leaves without a hit."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit(
            "Roster-hit filtering failed; no admission claim is valid."
        ) from None

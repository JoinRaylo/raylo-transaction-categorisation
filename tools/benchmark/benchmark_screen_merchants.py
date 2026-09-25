"""Known exact merchant-name presence; never an unfamiliar-family certificate."""

import argparse
import csv
import os
from collections import defaultdict
from pathlib import Path

from benchmark_build_index import private_key
from benchmark_screen_exposure import SOURCE_PATHS
from raylo_txncat.benchmark import observation_key
from raylo_txncat.benchmark_exposure import file_sha256
from raylo_txncat.dictionary import normalise_merchant
from raylo_txncat.hashing import canonical_json, strict_json_loads
from raylo_txncat.seed_selection import parse_validation


def merchant_batches(path):
    import pyarrow.parquet as pq

    if path.suffix == ".jsonl":
        with path.open("rb") as stream:
            for line in stream:
                yield [parse_validation(line)[0]["vendor"]]
    elif path.suffix == ".csv":
        with path.open(newline="") as stream:
            reader = csv.DictReader(stream)
            field = next(
                c
                for c in ("normalised_merchant", "merchant_raw", "merchant")
                if c in reader.fieldnames
            )
            for row in reader:
                yield [row[field]]
    else:
        parquet = pq.ParquetFile(path)
        fields = parquet.schema_arrow.names
        column = next(c for c in ("merchant_raw", "merchant", "vendor") if c in fields)
        for batch in parquet.iter_batches(batch_size=65536, columns=[column]):
            yield batch.column(0).to_pylist()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "research", "inventory", "legacy", "key-file", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    args.output.mkdir(mode=0o700, exist_ok=False)
    inventory = strict_json_loads(args.inventory.read_bytes())["files"]
    source = args.source / "observations.jsonl"
    receipt = strict_json_loads((args.source / "receipt.json").read_bytes())
    if file_sha256(source) != receipt["result_sha256"]:
        raise ValueError("source changed")
    key = private_key(args.key_file, "benchmark-private-20260916-v1")
    targets, event_merchants = defaultdict(set), {}
    with source.open("rb") as stream:
        for line in stream:
            row = strict_json_loads(line)
            event = observation_key(
                key,
                namespace="plaid",
                account_id=row["account_id"],
                transaction_id=row["transaction_id"],
            )
            name = normalise_merchant(row["merchant_name"])
            if event in event_merchants and event_merchants[event] != name:
                raise ValueError("event merchant conflict")
            event_merchants[event] = name
            if name:
                targets[name].add(event)
    hits, sources = defaultdict(set), []

    def scan(name, batches):
        n, found = 0, set()
        for batch in batches:
            n += len(batch)
            for value in batch:
                merchant = normalise_merchant(value)
                if merchant and merchant in targets:
                    found.update(targets[merchant])
        for event in found:
            hits[event].add(name)
        return {"source": name, "rows": n, "matching_events": len(found)}

    for relative in (
        *SOURCE_PATHS,
        "taxonomy/merchant_dictionary.csv",
        "taxonomy/rules/t2_entity_collisions.csv",
        "data/production_labels_tranche4.csv",
        "outputs/tuning_gold_v2_split_manifest.csv",
    ):
        path = args.research / relative
        digest = inventory[relative]["sha256"]
        if file_sha256(path) != digest:
            raise ValueError("merchant source changed")
        result = scan(relative, merchant_batches(path))
        if result["rows"] != inventory[relative]["profile"]["rows"] or file_sha256(path) != digest:
            raise ValueError("merchant scan incomplete or changed")
        sources.append({**result, "sha256": digest})
        print(f"Scanned merchant field: {relative}", flush=True)
    manifest = strict_json_loads((args.legacy / "summary.json").read_bytes())
    for filename, digest_key in (
        ("members.jsonl", "member_object_sha256"),
        ("label-conflicts.jsonl", "conflict_object_sha256"),
    ):
        path = args.legacy / filename
        if file_sha256(path) != manifest[digest_key]:
            raise ValueError("historical membership changed")
        with path.open("rb") as stream:
            result = scan(
                "legacy/" + filename,
                ([strict_json_loads(line)["input"]["merchant_raw"]] for line in stream),
            )
        sources.append({**result, "sha256": manifest[digest_key]})
    path = args.output / "merchant-exposure.jsonl"
    with path.open("xb") as stream:
        for event, name in sorted(event_merchants.items()):
            stream.write(
                canonical_json(
                    {
                        "event": event,
                        "key_id": key.key_id,
                        "merchant_present": bool(name),
                        "known_name_sources": sorted(hits[event]),
                        "reviewed_family": None,
                        "authorizes_consumption": False,
                    }
                )
                + b"\n"
            )
    result = {
        "schema_version": "benchmark-known-merchant-screen-v1",
        "source_sha256": receipt["result_sha256"],
        "target_events": len(event_merchants),
        "events_with_merchant": sum(bool(n) for n in event_merchants.values()),
        "events_with_known_merchant_name": sum(bool(hits[e]) for e in event_merchants),
        "sources": sources,
        "normalization": "serving_dictionary_strip_lower_v1",
        "family_absence_certified": False,
        "name_absence_is_family_absence": False,
        "authorizes_consumption": False,
        "private_sidecar_sha256": file_sha256(path),
        "adapter_sha256": file_sha256(Path(__file__)),
    }
    (args.output / "summary.json").write_bytes(canonical_json(result) + b"\n")
    print("Known-name screening complete; reviewed merchant families remain required.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("Known merchant screening failed; no family claim is certified.") from None

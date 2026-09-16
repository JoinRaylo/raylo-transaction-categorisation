"""Index fixed B01-preserved inputs locally, without training, labels or inference.

Requires the research pyarrow environment and the shared monorepo package. Key,
database and source rows stay private. Fixed allowlist never opens locked sets.
"""

import argparse
import json
import os
import stat
from itertools import islice
from pathlib import Path

from pydantic import SecretBytes
from raylo_txncat.benchmark import IdentityKey, project_head
from raylo_txncat.benchmark_exposure import VERSIONS, ExposureBuilder, sentence_projection
from raylo_txncat.classifier_types import ClassifierInput
from raylo_txncat.hashing import strict_json_loads
from raylo_txncat.seed_selection import parse_validation

SOURCES = (
    ("mlm_full", "outputs/transformer/pretrain_corpus_full.parquet", ("domain_pretraining",), None),
    (
        "vocabulary_prefix",
        "outputs/transformer/pretrain_corpus_full.parquet",
        ("tokenizer_vectorizer_fit",),
        1_000_000,
    ),
    ("consensus", "data/distillation_labels_consensus.parquet", ("distillation",), None),
    (
        "tuning_train",
        "outputs/tuning_train.jsonl",
        ("supervised_training", "feature_mask_statistics"),
        None,
    ),
    ("tuning_validation", "outputs/tuning_val.jsonl", ("model_selection_validation",), None),
)


def private_key(path: Path, key_id: str, *, create: bool = False) -> IdentityKey:
    if create:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(os.urandom(32))
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_uid != os.getuid():
        raise ValueError("identity key must be owner-only regular file")
    raw = path.read_bytes()
    if len(raw) != 32:
        raise ValueError("invalid key length")
    return IdentityKey(key_id=key_id, secret=SecretBytes(raw))


def consensus_head(row):
    # The historical classifier adapter uses raw fields, not the companion
    # cleaned merchant/description columns. Hinge retains their whitespace.
    if row["direction"] not in {"credit", "debit"}:
        raise ValueError("invalid source direction")
    return ClassifierInput.from_research(
        {
            "merchant_raw": row["merchant_raw"],
            "description_raw": row["description_raw"],
            "amount": row["amount"] or 0,
            "direction": row["direction"],
        }
    )


def source_rows(path: Path, kind: str, key: IdentityKey):
    if kind in {"mlm_full", "vocabulary_prefix"}:
        import pyarrow.parquet as pq

        for batch in pq.ParquetFile(path).iter_batches(batch_size=65536, columns=["text"]):
            for text in batch.column(0).to_pylist():
                yield (sentence_projection(text, key),)
    elif kind == "consensus":
        import pyarrow.parquet as pq

        columns = ["merchant_raw", "description_raw", "amount", "direction"]
        for batch in pq.ParquetFile(path).iter_batches(batch_size=8192, columns=columns):
            for row in batch.to_pylist():
                yield project_head(consensus_head(row), key)
    else:
        with path.open("rb") as stream:
            for line in stream:
                row = parse_validation(line)[0]
                head = ClassifierInput.from_research(
                    {
                        "merchant_raw": row["vendor"],
                        "description_raw": row["description"],
                        "amount": row["amount"],
                        "direction": "credit" if row["is_credit"] else "debit",
                    }
                )
                yield project_head(head, key)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--research", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True, help="Immutable B01 inventory")
    parser.add_argument("--key-file", type=Path, required=True)
    parser.add_argument("--key-id", required=True)
    parser.add_argument("--create-key", action="store_true")
    parser.add_argument("--output", type=Path, required=True, help="New private directory")
    args = parser.parse_args()
    os.umask(0o077)
    args.output.mkdir(mode=0o700, exist_ok=False)
    key = private_key(args.key_file, args.key_id, create=args.create_key)
    inventory = strict_json_loads(args.inventory.read_bytes())["files"]
    builder = ExposureBuilder(args.output / "inputs.sqlite", key)
    try:
        for kind, relative, purposes, prefix in SOURCES:
            source = inventory[relative]
            rows = source_rows(args.research / relative, kind, key)
            if prefix:
                rows = islice(rows, prefix)
            print(f"Indexing {kind}: {prefix or source['profile']['rows']:,} rows", flush=True)
            builder.add_source(
                source_id=kind,
                path=args.research / relative,
                expected_sha256=source["sha256"],
                expected_rows=prefix or source["profile"]["rows"],
                purposes=purposes,
                projections=VERSIONS[:1] if kind in {"mlm_full", "vocabulary_prefix"} else VERSIONS,
                rows=rows,
                prefix_rows=prefix,
            )
            print(f"Verified {kind}", flush=True)
        print("Building lookup index", flush=True)
        receipt = builder.finish()
        from raylo_txncat.benchmark_exposure import file_sha256

        receipt["inventory_sha256"] = file_sha256(args.inventory)
        receipt["adapter_sha256"] = file_sha256(Path(__file__))
        with (args.output / "receipt.json").open("x") as stream:
            stream.write(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        print("Private input index complete; history completeness remains unknown.")
    finally:
        builder.close()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit(
            "Exposure build failed; partial output is not queryable evidence."
        ) from None

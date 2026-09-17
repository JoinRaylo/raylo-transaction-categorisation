"""Complete specified effective-input checks for one private candidate snapshot.

Streaming target-membership audit, not a global admission authority. Tokenization
and sparse feature construction use verified retained artifacts; no predictions or
fitting. Unknown manual/prompt ancestry and semantic aliases remain unverified.
"""

import argparse
import csv
import hashlib
import json
import os
import re
import struct
import unicodedata
from collections import defaultdict
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
from benchmark_build_index import consensus_head, private_key
from benchmark_profile_source import head_for_row
from raylo_txncat.benchmark import observation_key
from raylo_txncat.benchmark_exposure import file_sha256
from raylo_txncat.classifier_types import ClassifierInput
from raylo_txncat.hashing import canonical_json, strict_json_loads
from raylo_txncat.head_hinge import numeric_features
from raylo_txncat.seed_selection import parse_validation

SOURCE_PATHS = (
    "outputs/transformer/pretrain_corpus_full.parquet",
    "data/distillation_labels_consensus.parquet",
    "outputs/tuning_train.jsonl",
    "outputs/tuning_val.jsonl",
    "outputs/transformer/pretrain_corpus.parquet",
    "outputs/transformer/silver_labels.parquet",
    "outputs/distill_train.parquet",
    "outputs/tuning_train_v4.jsonl",
    "outputs/tuning_val_v4.jsonl",
    "data/tuning_credit_topup.csv",
    "data/tuning_leaf_topup.csv",
    "data/tuning_risk_topup.csv",
    "outputs/credit_tranche_labels.csv",
    "outputs/credit_tranche_sample.csv",
)


def surface_fold(text):
    """Explicit conservative lexical rule; not an exhaustive semantic-duplicate test."""
    return " ".join(re.sub(r"[^\w\s]", " ", unicodedata.normalize("NFKC", text).casefold()).split())


def sparse_keys(heads, vectorizer):
    from scipy.sparse import csr_matrix, hstack

    _, logs, directions = numeric_features(heads)
    matrix = hstack(
        [
            vectorizer.transform([h.hinge_text for h in heads]),
            csr_matrix(np.column_stack([logs, directions])),
        ],
        format="csr",
    )
    matrix.sum_duplicates()
    matrix.eliminate_zeros()
    matrix.sort_indices()
    for start, end in zip(matrix.indptr[:-1], matrix.indptr[1:], strict=True):
        data = matrix.data[start:end].astype("<f8")
        if not np.isfinite(data).all():
            raise ValueError("nonfinite sparse features")
        yield hashlib.sha256(
            struct.pack("<QQ", matrix.shape[1], end - start)
            + matrix.indices[start:end].astype("<i8").tobytes()
            + data.tobytes()
        ).digest()


def token_keys(texts, credits, tokenizer):
    for encoded, credit in zip(tokenizer.encode_batch(texts), credits, strict=True):
        if not encoded.ids or len(encoded.ids) > 48:
            raise ValueError("invalid token length")
        yield (tuple(encoded.ids), bool(credit))


def historical_batches(path, size=4096):
    """Preserve each historical source's original head adapter, including raw text."""
    if path.suffix == ".csv":
        batch = []
        with path.open(newline="") as stream:
            for row in csv.DictReader(stream):
                batch.append(consensus_head(row))
                if len(batch) == size:
                    yield batch
                    batch = []
        if batch:
            yield batch
        return
    if path.suffix == ".jsonl":
        batch = []
        with path.open("rb") as stream:
            for line in stream:
                r = parse_validation(line)[0]
                h = ClassifierInput.from_research(
                    {
                        "merchant_raw": r["vendor"],
                        "description_raw": r["description"],
                        "amount": r["amount"],
                        "direction": "credit" if r["is_credit"] else "debit",
                    }
                )
                batch.append(h)
                if len(batch) == size:
                    yield batch
                    batch = []
        if batch:
            yield batch
        return
    parquet = pq.ParquetFile(path)
    fields = set(parquet.schema_arrow.names)
    if "text" in fields:
        # Aggregated MLM/silver sources have amount buckets, not exact amounts.
        for batch in parquet.iter_batches(batch_size=size, columns=["text", "direction"]):
            rows = batch.to_pydict()
            if any(d not in {"credit", "debit"} for d in rows["direction"]):
                raise ValueError("invalid corpus direction")
            yield [(t, d == "credit") for t, d in zip(rows["text"], rows["direction"], strict=True)]
        return
    raw = "merchant_raw" in fields
    merchant = "merchant_raw" if raw else "vendor" if "vendor" in fields else "merchant"
    description = "description_raw" if "description_raw" in fields else "description"
    direction = "direction" if "direction" in fields else "is_credit"
    for batch in parquet.iter_batches(
        batch_size=size, columns=[merchant, description, direction, "amount"]
    ):
        result = []
        for r in batch.to_pylist():
            d = r[direction] if direction == "direction" else "credit" if r[direction] else "debit"
            result.append(
                consensus_head(
                    {
                        "merchant_raw": r[merchant],
                        "description_raw": r[description],
                        "amount": r["amount"],
                        "direction": d,
                    }
                )
            )
        yield result


def main():
    import joblib
    from tokenizers import Tokenizer

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--research", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--legacy", type=Path, required=True)
    parser.add_argument("--key-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    args.output.mkdir(mode=0o700, exist_ok=False)
    inventory = strict_json_loads(args.inventory.read_bytes())["files"]
    key = private_key(args.key_file, "benchmark-private-20260916-v1")
    source_receipt = strict_json_loads((args.source / "receipt.json").read_bytes())
    source = args.source / "observations.jsonl"
    if file_sha256(source) != source_receipt["result_sha256"]:
        raise ValueError("source changed")
    artifacts = {
        "tokenizer": "outputs/distill_models/txn_classifier_gold_distilled_s123/tokenizer.json",
        "mlm_tokenizer": "outputs/distill_models/txn_encoder_mlm_distilbert_full/tokenizer.json",
        "mlm_recipe": "outputs/distill_models/txn_encoder_mlm_distilbert_full/pretrain_meta.json",
        "hinge": "outputs/distill_models/tfidf_linearsvm_sgd_v8_risk.joblib",
    }
    for relative in artifacts.values():
        if file_sha256(args.research / relative) != inventory[relative]["sha256"]:
            raise ValueError("artifact changed")
    tokenizer = Tokenizer.from_file(str(args.research / artifacts["tokenizer"]))
    tokenizer.enable_truncation(max_length=48)
    tokenizer.no_padding()
    a = json.loads((args.research / artifacts["tokenizer"]).read_text())
    b = json.loads((args.research / artifacts["mlm_tokenizer"]).read_text())
    if {k: v for k, v in a.items() if k not in {"truncation", "padding"}} != {
        k: v for k, v in b.items() if k not in {"truncation", "padding"}
    }:
        raise ValueError("MLM and selected tokenizers differ semantically")
    if json.loads((args.research / artifacts["mlm_recipe"]).read_text())["max_len"] != 48:
        raise ValueError("different MLM context recipe")
    vectorizer = joblib.load(args.research / artifacts["hinge"])["vectorizer"]
    heads_by_event = {}
    with source.open("rb") as stream:
        for line in stream:
            row = strict_json_loads(line)
            event = observation_key(
                key,
                namespace="plaid",
                account_id=row["account_id"],
                transaction_id=row["transaction_id"],
            )
            head = head_for_row(row)
            if event in heads_by_event and heads_by_event[event] != head:
                raise ValueError("conflicting observed event inputs")
            heads_by_event[event] = head
    events, heads = zip(*sorted(heads_by_event.items()), strict=True)
    targets = {name: defaultdict(set) for name in ("token48", "surface_fold", "hinge_sparse")}
    for start in range(0, len(heads), 2048):
        batch = heads[start : start + 2048]
        projections = {
            "token48": token_keys(
                [h.transformer_text for h in batch], [h.is_credit for h in batch], tokenizer
            ),
            "surface_fold": (surface_fold(h.transformer_text) for h in batch),
            "hinge_sparse": sparse_keys(batch, vectorizer),
        }
        for name, values in projections.items():
            for i, value in enumerate(values, start):
                targets[name][value].add(i)
    hits = {name: defaultdict(set) for name in targets}
    receipts = []

    def scan(name, batches, expected_rows):
        count = 0
        full_inputs = None
        for batch in batches:
            full = isinstance(batch[0], ClassifierInput)
            if full_inputs is not None and full_inputs != full:
                raise ValueError("inconsistent historical source schema")
            full_inputs = full
            texts = [h.transformer_text for h in batch] if full else [h[0] for h in batch]
            credits = [h.is_credit for h in batch] if full else [h[1] for h in batch]
            for projection, values in (
                ("token48", token_keys(texts, credits, tokenizer)),
                ("surface_fold", map(surface_fold, texts)),
                ("hinge_sparse", sparse_keys(batch, vectorizer) if full else ()),
            ):
                for value in values:
                    if value in targets[projection]:
                        hits[projection][name].update(targets[projection][value])
            previous = count
            count += len(batch)
            if count // 1_000_000 != previous // 1_000_000:
                print(f"{name}: {count:,} rows screened", flush=True)
        if count != expected_rows:
            raise ValueError("source scan incomplete")
        return {
            "source": name,
            "rows": count,
            "sparse_features_applicable": full_inputs,
            "target_event_matches": {k: len(hits[k][name]) for k in targets},
        }

    for relative in SOURCE_PATHS:
        path = args.research / relative
        info = inventory[relative]
        if file_sha256(path) != info["sha256"]:
            raise ValueError("source digest mismatch")
        print(f"Screening {relative}", flush=True)
        receipt = scan(relative, historical_batches(path), info["profile"]["rows"])
        if file_sha256(path) != info["sha256"]:
            raise ValueError("source changed during scan")
        receipts.append({**receipt, "sha256": info["sha256"]})
    legacy_summary = strict_json_loads((args.legacy / "summary.json").read_bytes())
    for filename, digest_key in (
        ("members.jsonl", "member_object_sha256"),
        ("label-conflicts.jsonl", "conflict_object_sha256"),
    ):
        path = args.legacy / filename
        if file_sha256(path) != legacy_summary[digest_key]:
            raise ValueError("legacy membership changed")
        legacy_heads = []
        with path.open("rb") as stream:
            for line in stream:
                row = strict_json_loads(line)
                if row["cohort"] != "dictionary_regression":
                    legacy_heads.append(ClassifierInput.from_research(row["input"]))
        receipts.append(
            {
                **scan(
                    "legacy/" + filename,
                    (legacy_heads[i : i + 4096] for i in range(0, len(legacy_heads), 4096)),
                    len(legacy_heads),
                ),
                "sha256": file_sha256(path),
            }
        )
    with (args.output / "event-exposure.jsonl").open("xb") as stream:
        for i, event in enumerate(events):
            stream.write(
                canonical_json(
                    {
                        "event": event,
                        "key_id": key.key_id,
                        "matches": {
                            k: sorted(source for source, found in v.items() if i in found)
                            for k, v in hits.items()
                        },
                        "authorizes_consumption": False,
                    }
                )
                + b"\n"
            )
    report = {
        "schema_version": "benchmark-target-exposure-screen-v1",
        "target_events": len(events),
        "source_sha256": file_sha256(source),
        "inventory_sha256": file_sha256(args.inventory),
        "artifact_sha256": {k: inventory[p]["sha256"] for k, p in artifacts.items()},
        "sources": receipts,
        "any_source_matches": {k: len(set().union(*v.values())) for k, v in hits.items()},
        "event_exposure_sha256": file_sha256(args.output / "event-exposure.jsonl"),
        "adapter_sha256": file_sha256(Path(__file__)),
        "selected_mlm_tokenizer_semantics_and_context_verified": True,
        "named_source_scans_complete": True,
        "historical_fit_consumption_attested": False,
        "global_history_complete": False,
        "semantic_near_duplicate_absence_certified": False,
        "merchant_family_absence_certified": False,
        "authorizes_consumption": False,
        "model_predictions_or_fitting": False,
    }
    with (args.output / "summary.json").open("xb") as stream:
        stream.write(canonical_json(report) + b"\n")
    print("Effective-input screening complete for the declared targets and sources", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit(
            "Effective-input screen failed; partial evidence is not complete."
        ) from None

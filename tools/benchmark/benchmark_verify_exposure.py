"""Cross-check the private effective-input screen against the independent exact index."""

import argparse
from collections import Counter
from pathlib import Path

from benchmark_build_index import SOURCES, private_key
from benchmark_profile_source import head_for_row
from benchmark_screen_exposure import token_keys
from raylo_txncat.benchmark import observation_key, project_head
from raylo_txncat.benchmark_exposure import ExposureIndex, file_sha256
from raylo_txncat.hashing import canonical_json, strict_json_loads


def main():
    from tokenizers import Tokenizer
    from transformers import AutoTokenizer

    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "index", "screen", "research", "key-file", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    screen = strict_json_loads((args.screen / "summary.json").read_bytes())
    receipt = strict_json_loads((args.index / "receipt.json").read_bytes())
    key = private_key(args.key_file, receipt["key_id"])
    source = args.source / "observations.jsonl"
    hits_path = args.screen / "event-exposure.jsonl"
    if (
        file_sha256(source) != screen["source_sha256"]
        or file_sha256(hits_path) != screen["event_exposure_sha256"]
    ):
        raise ValueError("screen evidence changed")
    with hits_path.open("rb") as stream:
        hits = {}
        for line in stream:
            row = strict_json_loads(line)
            if row["event"] in hits or row["key_id"] != key.key_id:
                raise ValueError("duplicate or differently keyed event")
            hits[row["event"]] = row["matches"]
    heads = {}
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
            if event in heads and heads[event] != head:
                raise ValueError("conflicting event")
            heads[event] = head
    if hits.keys() != heads.keys() or len(hits) != screen["target_events"]:
        raise ValueError("incomplete exposure sidecar")
    counts, unions = Counter(), Counter()
    for projections in hits.values():
        for projection, paths in projections.items():
            if paths != sorted(set(paths)):
                raise ValueError("duplicate exposure source")
            unions[projection] += bool(paths)
            for path in paths:
                counts[(projection, path)] += 1
    for source_receipt in screen["sources"]:
        for projection, n in source_receipt["target_event_matches"].items():
            if counts[(projection, source_receipt["source"])] != n:
                raise ValueError("source exposure count mismatch")
    if dict(unions) != screen["any_source_matches"]:
        raise ValueError("exposure union count mismatch")
    index = ExposureIndex(
        args.index / "inputs.sqlite", expected_sha256=receipt["database_sha256"], key=key
    )
    source_paths = {name: path for name, path, _, _ in SOURCES if name != "vocabulary_prefix"}
    checked = Counter()
    try:
        for event, head in heads.items():
            for projection in project_head(head, key):
                method = (
                    "token48" if projection.version == "transformer-sentence-v1" else "hinge_sparse"
                )
                for name in index.lookup(projection)["sources"]:
                    if name in source_paths:
                        if source_paths[name] not in hits[event][method]:
                            raise ValueError("known exact input missing from effective screen")
                        checked[(name, method)] += 1
    finally:
        index.close()
    # Separately exercise the serving Hugging Face interface on all candidate inputs.
    directory = args.research / "outputs/distill_models/txn_classifier_gold_distilled_s123"
    if file_sha256(directory / "tokenizer.json") != screen["artifact_sha256"]["tokenizer"]:
        raise ValueError("tokenizer changed")
    hf = AutoTokenizer.from_pretrained(directory, local_files_only=True)
    rust = Tokenizer.from_file(str(directory / "tokenizer.json"))
    rust.enable_truncation(max_length=48)
    rust.no_padding()
    values = list(heads.values())
    for start in range(0, len(values), 2048):
        batch = values[start : start + 2048]
        texts = [h.transformer_text for h in batch]
        encoded = hf(
            texts, truncation=True, max_length=48, padding=False, return_attention_mask=True
        )
        actual = list(token_keys(texts, [h.is_credit for h in batch], rust))
        expected = [
            (tuple(ids), h.is_credit) for ids, h in zip(encoded["input_ids"], batch, strict=True)
        ]
        if actual != expected or any(
            any(m != 1 for m in mask) for mask in encoded["attention_mask"]
        ):
            raise ValueError("screen tokenizer differs from serving interface")
    result = {
        "schema_version": "benchmark-effective-screen-verification-v1",
        "passed": True,
        "screen_summary_sha256": file_sha256(args.screen / "summary.json"),
        "index_database_sha256": receipt["database_sha256"],
        "target_events": len(heads),
        "serving_tokenizer_matches": len(heads),
        "exact_index_subset_checks": [
            {"source": s, "projection": p, "known_matches": n}
            for (s, p), n in sorted(checked.items())
        ],
        "all_reported_exposure_counts_reconstructed": True,
        "authorizes_consumption": False,
        "adapter_sha256": file_sha256(Path(__file__)),
    }
    with args.output.open("xb") as stream:
        stream.write(canonical_json(result) + b"\n")
    print(
        f"Verified {len(heads):,} target events against exact-index and serving-tokenizer evidence."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("Exposure verification failed; no absence claim is certified.") from None

"""Read-only B01 lineage/overlap audit; emits aggregates, never raw examples.

Requires the research Python environment (pandas/pyarrow) plus app dependencies.
Does not load model weights, fit anything, or open locked/retired evaluation files.
File availability/hash matching is not a retrospective training-consumption receipt.
"""

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", type=Path, required=True, help="Monorepo checkout")
    parser.add_argument("--research", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    app, research, output = args.app.resolve(), args.research.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    sys.path[:0] = [
        str(app / "apps/ob-txn-categoriser/scripts"),
        str(app / "apps/ob-txn-categoriser/src"),
        str(app / "lib/raylo-txncat/src"),
        str(app / "lib/raylo-config/src"),
    ]
    from raylo_txncat.classifier_types import ClassifierInput
    from raylo_txncat.seed_selection import parse_validation
    from run_evaluations import adapt, inventory_sources

    def save(name, value):
        (output / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")

    provenance_path = app / "apps/ob-txn-categoriser/research/bundle-build-v1/provenance.json"
    provenance = json.loads(provenance_path.read_text())
    inventory, raw_sources, metadata = inventory_sources(
        app, research, app / "apps/ob-txn-categoriser/scripts/evaluation_inventory.json"
    )
    baseline = json.loads(
        (
            app / "apps/ob-txn-categoriser/research/waterfall-changes/"
            "baseline-2026-09-15/summary.json"
        ).read_text()
    )
    general = baseline["general_mapping"]
    eval_rows, by_text, by_hinge = {}, defaultdict(set), defaultdict(set)

    def hinge_key(head):
        # Retained numeric path: float32 log1p output, preserving float64 intermediate.
        amount32 = np.float32(abs(head.amount))
        return (head.hinge_text, float(np.float32(np.log1p(float(amount32)))), head.is_credit)

    for name, task in inventory["tasks"].items():
        if task == "merchant_dictionary":
            continue  # No transaction amount/direction: not a complete classifier input.
        rows = adapt(name, task, raw_sources[name], raw_sources, general)
        eval_rows[name] = rows
        for index, row in enumerate(rows):
            head = ClassifierInput.from_research(row)
            by_text[head.transformer_text].add((name, index))
            by_hinge[hinge_key(head)].add((name, index))

    overlap = {
        "method": (
            "Exact full transformer sentences and hinge text/numeric inputs; "
            "no tokenized or near-duplicate absence claim."
        ),
        "dataset_rows": {k: len(v) for k, v in eval_rows.items()},
        "sources": {},
    }

    def matches_summary(matches):
        counts = Counter(name for name, index in matches)
        return {
            name: {"matching_rows": counts[name], "evaluated_rows": len(rows)}
            for name, rows in eval_rows.items()
        }

    files = {}

    def register(relative, purpose, profile=None):
        assert "LOCKED" not in relative, "Locked content must not be read"
        path = research / relative
        item = {"purpose": purpose, "available": path.is_file()}
        if path.is_file():
            item.update(bytes=path.stat().st_size, sha256=digest(path))
            if relative in files and files[relative].get("sha256") != item["sha256"]:
                raise ValueError(f"Source changed during audit: {relative}")
            if profile is not None:
                item["profile"] = profile
        files[relative] = item
        return item

    bundle_matches = []
    for record in provenance["source_files"]:
        item = register(record["path"], "bundle_compilation_input")
        bundle_matches.append(
            {
                "path": record["path"],
                "expected_sha256": record["sha256"],
                "current_sha256": item.get("sha256"),
                "matches": item.get("sha256") == record["sha256"],
            }
        )
    print("Bundle source hashes checked", flush=True)

    for entry in metadata.values():
        if entry.get("status") == "excluded_confirmation":
            continue
        record = entry["registry_entry"]
        item = register(record["path"], "permitted_evaluation_snapshot")
        assert item["sha256"] == record["sha256"]

    masks = json.loads(
        (app / "apps/ob-txn-categoriser/research/seed-selection-v1/masks.json").read_text()
    )
    leaves = masks["leaves"]
    credit_ok = dict(zip(leaves, masks["credit_ok"], strict=True))
    debit_ok = dict(zip(leaves, masks["debit_ok"], strict=True))

    def head_from_training(row):
        return ClassifierInput.from_research(
            {
                "merchant_raw": row["vendor"],
                "description_raw": row["description"],
                "amount": row["amount"],
                "direction": "credit" if row["is_credit"] else "debit",
            }
        )

    for relative in [
        "outputs/tuning_train.jsonl",
        "outputs/tuning_val.jsonl",
        "outputs/tuning_train_v4.jsonl",
        "outputs/tuning_val_v4.jsonl",
    ]:
        path = research / relative
        if not path.exists():
            register(relative, "historical_chat_snapshot")
            continue
        register(relative, "historical_chat_snapshot")
        rows = parse_validation(path.read_bytes())
        tmatch, hmatch, legal_tmatch = set(), set(), set()
        counts = Counter()
        for row in rows:
            head = head_from_training(row)
            counts["credit" if row["is_credit"] else "debit"] += 1
            counts["blank_merchant"] += not row["vendor"].strip()
            legal = (credit_ok if row["is_credit"] else debit_ok).get(row["leaf"], False)
            counts["legal_under_frozen_masks"] += bool(legal)
            hit = by_text.get(head.transformer_text, ())
            tmatch.update(hit)
            if legal:
                legal_tmatch.update(hit)
            hmatch.update(by_hinge.get(hinge_key(head), ()))
        register(
            relative,
            "historical_chat_snapshot",
            {
                "rows": len(rows),
                "fields": ["messages"],
                "model_fields": ["merchant", "description", "amount", "direction", "label"],
                "source_identity_fields": [],
                "counts": dict(counts),
            },
        )
        overlap["sources"][relative] = {
            "transformer_sentence": matches_summary(tmatch),
            "hinge_logical_numeric": matches_summary(hmatch),
            "transformer_sentence_after_current_frozen_mask_filter": matches_summary(legal_tmatch),
        }
        print(f"Chat snapshot checked: {relative}, {len(rows):,} rows", flush=True)

    parquet_paths = [
        "outputs/transformer/pretrain_corpus_full.parquet",
        "outputs/transformer/pretrain_corpus.parquet",
        "outputs/transformer/silver_labels.parquet",
        "data/distillation_labels_consensus.parquet",
        "outputs/distill_train.parquet",
    ]
    for relative in parquet_paths:
        path = research / relative
        if not path.exists():
            register(relative, "historical_parquet_snapshot")
            continue
        register(relative, "historical_parquet_snapshot")
        source = pq.ParquetFile(path)
        names = source.schema_arrow.names
        columns = [
            c
            for c in [
                "text",
                "provider",
                "direction",
                "n",
                "merchant",
                "vendor",
                "description",
                "merchant_raw",
                "description_raw",
                "amount",
                "is_credit",
                "leaf",
                "final_leaf",
            ]
            if c in names
        ]
        matches, prefix_matches, hinge_matches, legal_matches = set(), set(), set(), set()
        provider_counts, direction_counts = Counter(), Counter()
        count = blank = legal_count = 0
        for batch in source.iter_batches(batch_size=65536, columns=columns):
            data = batch.to_pydict()
            size = batch.num_rows
            if "text" in names:
                texts = data["text"]
            else:
                texts = []
                for i in range(size):
                    row = {
                        "vendor": (
                            data.get("merchant_raw", data.get("vendor", data.get("merchant")))
                        )[i]
                        or "",
                        "description": (data.get("description_raw", data.get("description")))[i]
                        or "",
                        "amount": data["amount"][i] or 0,
                        "is_credit": data["is_credit"][i]
                        if "is_credit" in names
                        else data["direction"][i] == "credit",
                    }
                    head = head_from_training(row)
                    texts.append(head.transformer_text)
                    hinge_matches.update(by_hinge.get(hinge_key(head), ()))
            for i, text in enumerate(texts):
                hit = by_text.get(text, ())
                matches.update(hit)
                if count + i < 1_000_000:
                    prefix_matches.update(hit)
                if "leaf" in names or "final_leaf" in names:
                    label = data.get("leaf", data.get("final_leaf"))[i]
                    credit = (
                        data["direction"][i] == "credit"
                        if "direction" in names
                        else bool(data["is_credit"][i])
                    )
                    legal = (credit_ok if credit else debit_ok).get(label, False)
                    legal_count += bool(legal)
                    if legal:
                        legal_matches.update(hit)
            provider_counts.update(data.get("provider", ["unspecified"] * size))
            direction_counts.update(
                data.get(
                    "direction",
                    ["credit" if x else "debit" for x in data.get("is_credit", [False] * size)],
                )
            )
            blank += sum(
                not str(x or "").strip()
                for x in data.get(
                    "merchant_raw", data.get("vendor", data.get("merchant", [""] * size))
                )
            )
            count += size
        assert count == source.metadata.num_rows
        register(
            relative,
            "historical_parquet_snapshot",
            {
                "rows": count,
                "fields": names,
                "blank_merchant": blank,
                "provider": dict(provider_counts),
                "direction": dict(direction_counts),
                "source_identity_fields": [
                    c for c in names if c in {"transaction_id", "customer_id", "account_id"}
                ],
                "legal_under_frozen_masks": legal_count
                if "leaf" in names or "final_leaf" in names
                else None,
            },
        )
        result = {"transformer_sentence": matches_summary(matches)}
        if "pretrain" in relative:
            result["first_million_sentence_inputs_to_vocab_builder"] = matches_summary(
                prefix_matches
            )
        if "leaf" in names or "final_leaf" in names:
            result["transformer_sentence_after_current_frozen_mask_filter"] = matches_summary(
                legal_matches
            )
        if "text" not in names:
            result["hinge_logical_numeric"] = matches_summary(hinge_matches)
        overlap["sources"][relative] = result
        print(f"Parquet checked: {relative}, {count:,} rows", flush=True)

    csv_paths = [
        "data/production_labels_tranche4.csv",
        "data/tuning_leaf_topup.csv",
        "data/tuning_credit_topup.csv",
        "data/tuning_risk_topup.csv",
        "outputs/credit_tranche_sample.csv",
        "outputs/credit_tranche_labels.csv",
        "outputs/tuning_gold_v2_split_manifest.csv",
        "taxonomy/merchant_dictionary.csv",
        "taxonomy/rules/deterministic_rules.csv",
        "taxonomy/rules/t2_entity_collisions.csv",
    ]
    for relative in csv_paths:
        path = research / relative
        if not path.exists():
            register(relative, "training_or_enrichment_source")
            continue
        register(relative, "training_or_enrichment_source")
        with path.open() as stream:
            reader = csv.DictReader(stream)
            fields = reader.fieldnames
            rows = list(reader)
        tags = {
            col: dict(Counter(row[col] for row in rows))
            for col in ["tier", "role", "source", "review_status"]
            if col in fields
        }
        register(
            relative,
            "training_or_enrichment_source",
            {
                "rows": len(rows),
                "fields": fields,
                "provenance_counts": tags,
                "source_identity_fields": [
                    c for c in fields if c in {"transaction_id", "customer_id", "account_id"}
                ],
                "row_id_is_provider_transaction_id": False if "row_id" in fields else None,
            },
        )

    meta_paths = [
        "outputs/distill_models/txn_classifier_distilled/train_meta.json",
        "outputs/distill_models/txn_encoder_mlm_distilbert_full/pretrain_meta.json",
    ]
    for directory in ["txn_classifier_distilled", "txn_encoder_mlm_distilbert_full"]:
        for name in [
            "model.safetensors",
            "tokenizer.json",
            "tokenizer_config.json",
            "config.json",
            "heads.pt",
            "labels.json",
        ]:
            register(f"outputs/distill_models/{directory}/{name}", "ancestor_model_component")
    source_paths = [
        "src/build_tuning_dataset.py",
        "src/build_credit_tranche.py",
        "src/build_merchant_dictionary.py",
        "src/retrain_corrected_heads.py",
        "src/transformer/build_corpus.py",
        "src/transformer/pretrain_mlm.py",
        "src/transformer/train_classifier.py",
        "src/distillation_bakeoff.py",
        "outputs/transformer/build_pretrain.log",
        "outputs/transformer/gcp_stage.log",
        "outputs/transformer/stage_distilled.log",
        "outputs/transformer/stage_v6_risk.log",
        "benchmarks/tuning_system_prompt.txt",
        "outputs/tuning_system_prompt.txt",
    ]
    for relative in source_paths + meta_paths:
        register(relative, "source_or_run_metadata")
    lineage = {relative: json.loads((research / relative).read_text()) for relative in meta_paths}
    save(
        "local_inventory.json",
        {
            "audited_at": datetime.now(UTC).isoformat(),
            "audit_script_sha256": digest(Path(__file__)),
            "bundle_provenance_sha256": digest(provenance_path),
            "bundle_source_matches": bundle_matches,
            "files": files,
            "ancestor_metadata": lineage,
            "restrictions": {
                "locked_contents_read": False,
                "model_weights_deserialized": False,
                "models_scored": False,
                "new_training": False,
                "historical_consumption_hash_receipts_recovered": False,
            },
        },
    )
    save("local_overlap.json", overlap)
    print("Aggregate local inventory and exact-input overlap written", flush=True)


if __name__ == "__main__":
    main()

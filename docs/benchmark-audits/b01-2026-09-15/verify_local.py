"""Independent B01 recount and deterministic fit-input reconstruction; no inference."""

import argparse
import ast
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", type=Path, required=True)
    parser.add_argument("--research", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    args = parser.parse_args()
    app, research, audit = args.app.resolve(), args.research.resolve(), args.audit.resolve()
    inv = json.loads((audit / "local_inventory.json").read_text())
    overlaps = json.loads((audit / "local_overlap.json").read_text())

    # Load only the reviewed pure helper definitions, avoiding module import side effects.
    namespace = {"np": np, "pd": pd}
    for relative, names in {
        "src/distillation_bakeoff.py": {"_parse_tuning_jsonl"},
        "src/transformer/build_corpus.py": {"sentence", "amt_bucket_py"},
        "src/transformer/train_classifier.py": {"balanced_order"},
    }.items():
        path = research / relative
        assert sha(path) == inv["files"][relative]["sha256"]
        tree = ast.parse(path.read_text())
        functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
        assert {n.name for n in functions} == names
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(path), "exec"), namespace)
    sentence, band = namespace["sentence"], namespace["amt_bucket_py"]

    def texts(frame):
        return [
            sentence("credit" if int(c) else "debit", band(a), m, d)
            for m, d, a, c in zip(
                frame.vendor, frame.description, frame.amount, frame.is_credit, strict=True
            )
        ]

    frames = {}
    for name, relative in {
        "gold_credit_eval": "data/gold_credit_eval.csv",
        "gold_transactions_risk_t6bound": "data/gold_transactions_risk_t6bound.csv",
        "gold_v2_slm_eval_holdout": "data/gold_v2_slm_eval_holdout.csv",
        "gold_pipeline_eval": "outputs/gold_pipeline_eval.csv",
    }.items():
        with (research / relative).open(newline="") as stream:
            rows = list(csv.DictReader(stream))
        frames[name] = pd.DataFrame(
            [
                {
                    "vendor": row["merchant_raw"],
                    "description": row["description_raw"],
                    "amount": float(row["amount"] or 0),
                    "is_credit": int(row["direction"] == "credit"),
                    "leaf": row["gold_leaf"],
                }
                for row in rows
            ]
        )
    frames["tuning_validation"] = namespace["_parse_tuning_jsonl"](
        research / "outputs/tuning_val.jsonl"
    )
    expected_texts = {name: texts(frame) for name, frame in frames.items()}
    targets = pa.array(sorted({text for group in expected_texts.values() for text in group}))
    found = set()
    corpus = pq.ParquetFile(research / "outputs/transformer/pretrain_corpus_full.parquet")
    for batch in corpus.iter_batches(columns=["text"], batch_size=262144):
        column = batch.column(0)
        found.update(pc.filter(column, pc.is_in(column, value_set=targets)).to_pylist())
    independent_counts = {
        name: sum(text in found for text in group) for name, group in expected_texts.items()
    }
    for name, count in independent_counts.items():
        expected = overlaps["sources"]["outputs/transformer/pretrain_corpus_full.parquet"][
            "transformer_sentence"
        ][name]["matching_rows"]
        print(f"Independent overlap {name}: {count}; expected {expected}", flush=True)
        assert count == expected, name
    print("Independent Arrow membership recount agrees", flush=True)

    masks = json.loads(
        (app / "apps/ob-txn-categoriser/research/seed-selection-v1/masks.json").read_text()
    )
    credit_ok = dict(zip(masks["leaves"], masks["credit_ok"], strict=True))
    debit_ok = dict(zip(masks["leaves"], masks["debit_ok"], strict=True))
    stages = {}
    gold = namespace["_parse_tuning_jsonl"](research / "outputs/tuning_train.jsonl")
    distilled = pd.read_parquet(research / "data/distillation_labels_consensus.parquet")
    distilled = pd.DataFrame(
        {
            "vendor": distilled.merchant_raw.fillna(""),
            "description": distilled.description_raw.fillna(""),
            "amount": distilled.amount.fillna(0),
            "is_credit": (distilled.direction == "credit").astype(int),
            "leaf": distilled.final_leaf,
        }
    )
    for name, frame, meta_path in [
        (
            "gold_selected_seed123",
            gold,
            "outputs/distill_models/txn_classifier_gold_distilled_s123/train_meta.json",
        ),
        (
            "distillation_parent",
            distilled,
            "outputs/distill_models/txn_classifier_distilled/train_meta.json",
        ),
    ]:
        meta = json.loads((research / meta_path).read_text())
        frame = frame[frame.leaf.isin(masks["leaves"])].reset_index(drop=True)
        legal = np.array(
            [
                (credit_ok if c else debit_ok)[leaf]
                for c, leaf in zip(frame.is_credit, frame.leaf, strict=True)
            ],
            dtype=bool,
        )
        frame = frame[legal].reset_index(drop=True)
        assert len(frame) == meta["rows"]
        seen_at_best, seen_any = set(), set()
        epoch_rows = []
        for epoch in range(meta["epochs"]):
            order = namespace["balanced_order"](
                frame.leaf, meta["cap"], meta["floor"], np.random.default_rng(meta["seed"] + epoch)
            )
            assert len(order) == meta["per_epoch"]
            seen_any.update(int(x) for x in order)
            if epoch < meta["best_epoch"]:
                seen_at_best.update(int(x) for x in order)
            epoch_rows.append(
                {"epoch": epoch + 1, "draws": len(order), "distinct_row_positions": len(set(order))}
            )
        fitted = frame.iloc[sorted(seen_at_best)]
        fit_text = texts(fitted)
        fit_targets = set(fit_text)
        val_text = expected_texts["tuning_validation"]
        labels_by_text = {}
        for text, label in zip(fit_text, fitted.leaf, strict=True):
            labels_by_text.setdefault(text, set()).add(label)
        stages[name] = {
            "reconstruction_status": (
                "consistent_with_available_snapshots_code_and_run_metadata_"
                "not_consumption_attestation"
            ),
            "run_metadata_sha256": sha(research / meta_path),
            "filtered_rows_match_metadata": len(frame),
            "per_epoch_matches_metadata": meta["per_epoch"],
            "retained_best_epoch": meta["best_epoch"],
            "epochs": epoch_rows,
            "distinct_row_positions_seen_by_retained_epoch": len(seen_at_best),
            "distinct_row_positions_seen_any_epoch": len(seen_any),
            "validation_rows_matching_retained_epoch_sentence": sum(
                t in fit_targets for t in val_text
            ),
            "validation_rows_with_same_label_in_matched_fit_inputs": sum(
                leaf in labels_by_text.get(text, set())
                for text, leaf in zip(val_text, frames["tuning_validation"].leaf, strict=True)
            ),
        }
    receipt = {
        "audit_type": "independent_counts_and_fit_input_reconstruction",
        "verifier_sha256": sha(Path(__file__)),
        "local_inventory_sha256": sha(audit / "local_inventory.json"),
        "local_overlap_sha256": sha(audit / "local_overlap.json"),
        "independent_pretraining_overlap_counts": independent_counts,
        "reconstructed_stages": stages,
        "limits": {
            "models_scored": False,
            "locked_contents_read": False,
            "source_event_or_customer_identity_recovered_from_local_files": False,
            "cryptographic_fit_consumption_receipt": False,
            "full_tokenized_or_near_duplicate_overlap_audit": False,
        },
    }
    (audit / "independent_verification.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    )
    print(
        json.dumps(
            {"independent_pretraining_matches": independent_counts, "stages": stages}, indent=2
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()

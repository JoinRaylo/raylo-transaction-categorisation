"""Reproduce B01's independently checked overlap counts through the disk index.

Reads only five permitted historical development sets. No predictions, fitting,
locked evaluation reads, new-source labels, or raw transactions in the output.
"""

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from benchmark_build_index import SOURCES, private_key
from raylo_txncat.benchmark import project_head
from raylo_txncat.benchmark_exposure import ExposureIndex, file_sha256
from raylo_txncat.classifier_types import ClassifierInput
from raylo_txncat.hashing import strict_json_loads
from raylo_txncat.seed_selection import parse_validation

DATASETS = {
    "gold_v2_slm_eval_holdout": "data/gold_v2_slm_eval_holdout.csv",
    "gold_credit_eval": "data/gold_credit_eval.csv",
    "gold_transactions_risk_t6bound": "data/gold_transactions_risk_t6bound.csv",
    "gold_pipeline_eval": "outputs/gold_pipeline_eval.csv",
    "tuning_validation": "outputs/tuning_val.jsonl",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--research", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--key-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    inventory = strict_json_loads((args.audit / "local_inventory.json").read_bytes())["files"]
    expected = strict_json_loads((args.audit / "local_overlap.json").read_bytes())
    receipt = strict_json_loads((args.index / "receipt.json").read_bytes())
    key = private_key(args.key_file, receipt["key_id"])
    index = ExposureIndex(
        args.index / "inputs.sqlite", expected_sha256=receipt["database_sha256"], key=key
    )
    checks = []
    try:
        for name, relative in DATASETS.items():
            path = args.research / relative
            if file_sha256(path) != inventory[relative]["sha256"]:
                raise ValueError("development source changed")
            if name == "tuning_validation":
                rows = [
                    {
                        "merchant_raw": r["vendor"],
                        "description_raw": r["description"],
                        "amount": r["amount"],
                        "direction": "credit" if r["is_credit"] else "debit",
                    }
                    for r in parse_validation(path.read_bytes())
                ]
            else:
                # Preserve embedded CRLF exactly, as in independent B01 checks.
                with path.open(newline="") as stream:
                    rows = list(csv.DictReader(stream))
            assert len(rows) == expected["dataset_rows"][name]
            counts = Counter()
            for row in rows:
                for projection in project_head(ClassifierInput.from_research(row), key):
                    for source in index.lookup(projection)["sources"]:
                        counts[(source, projection.version)] += 1
            for source, source_path, _, _ in SOURCES:
                methods = {"transformer-sentence-v1": "transformer_sentence"}
                if source == "vocabulary_prefix":
                    methods = {
                        "transformer-sentence-v1": "first_million_sentence_inputs_to_vocab_builder"
                    }
                elif source != "mlm_full":
                    methods["hinge-numeric-v1"] = "hinge_logical_numeric"
                for projection, method in methods.items():
                    previous = expected["sources"][source_path][method][name]["matching_rows"]
                    actual = counts[(source, projection)]
                    checks.append(
                        {
                            "dataset": name,
                            "source": source,
                            "projection": projection,
                            "rows": len(rows),
                            "b01_matches": previous,
                            "indexed_matches": actual,
                            "passed": previous == actual,
                        }
                    )
            if file_sha256(path) != inventory[relative]["sha256"]:
                raise ValueError("development source changed during verification")
        result = {
            "schema_version": "benchmark-input-index-verification-v1",
            "passed": all(c["passed"] for c in checks),
            "checks": checks,
            "accuracy_evaluation": False,
            "authorizes_consumption": False,
            "database_sha256": receipt["database_sha256"],
            "audit_overlap_sha256": file_sha256(args.audit / "local_overlap.json"),
            "adapter_sha256": file_sha256(Path(__file__)),
        }
        with args.output.open("x") as stream:
            stream.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
        if not result["passed"]:
            raise ValueError("index differs from B01")
        print(f"Verified {len(checks)} historical overlap counts; no accuracy scoring.")
    finally:
        index.close()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("Index verification failed; inspect aggregate evidence only.") from None

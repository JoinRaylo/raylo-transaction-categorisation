"""Rescore frozen historical membership using a completed evaluation-run receipt.

Run the full evaluation harness first. This command neither relabels nor rebuilds
membership, and preserves the separate known-training diagnostic denominator.
"""

import argparse
import os
from pathlib import Path

from benchmark_curate_legacy import rescore, save
from raylo_txncat.benchmark_exposure import file_sha256
from raylo_txncat.hashing import strict_json_loads


def score_run(cohort, run):
    manifest = strict_json_loads((cohort / "summary.json").read_bytes())
    report = strict_json_loads((run / "summary.json").read_bytes())
    if report["status"] != "passed" or report["locked_data_scored"]:
        raise ValueError("a completed unlocked evaluation run is required")
    members_path, predictions_path = cohort / "members.jsonl", run / "rows.jsonl"
    if file_sha256(members_path) != manifest["member_object_sha256"]:
        raise ValueError("frozen membership changed")
    if file_sha256(predictions_path) != report["private_rows_sha256"]:
        raise ValueError("evaluation predictions changed")
    for dataset, digest in manifest["source_files"].items():
        if report["datasets"][dataset]["registry_entry"]["sha256"] != digest:
            raise ValueError("evaluation source differs from frozen source")
    with members_path.open("rb") as stream:
        members = [strict_json_loads(line) for line in stream]
    if len(members) != manifest["retained_cases"]:
        raise ValueError("membership incomplete")
    with predictions_path.open("rb") as stream:
        scores = rescore(
            members, (strict_json_loads(line) for line in stream), report["general_mapping"]
        )
    return {
        "schema_version": "historical-regression-scores-v1",
        "cohort_manifest_sha256": file_sha256(cohort / "summary.json"),
        "member_object_sha256": manifest["member_object_sha256"],
        "evaluation_summary_sha256": file_sha256(run / "summary.json"),
        "evaluation_predictions_sha256": report["private_rows_sha256"],
        "scores": scores,
        "independent_benchmark": False,
        "membership_or_labels_changed": False,
        "adapter_sha256": file_sha256(Path(__file__)),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    result = score_run(args.cohort, args.run)
    save(args.output, result)
    print(f"Scored {len(result['scores'])} frozen historical groups.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("Historical scoring failed; no regression result is certified.") from None

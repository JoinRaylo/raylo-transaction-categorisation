"""Version the existing labelled regression cases and rescore verified cached outputs.

No new source labelling, model execution, membership promotion or locked-set reads.
Raw cases and label disagreements remain private; reports contain aggregates only.
"""

import argparse
import os
from collections import defaultdict
from pathlib import Path

from benchmark_build_index import private_key
from evaluation_metrics import score
from raylo_txncat.benchmark_exposure import file_sha256
from raylo_txncat.benchmark_regression import curate
from raylo_txncat.hashing import canonical_json, strict_json_loads
from run_evaluations import adapt, inventory_sources


def save(path, value):
    with path.open("xb") as stream:
        stream.write(canonical_json(value) + b"\n")


def rescore(members, predictions, general):
    refs = {}
    if len({m["member_id"] for m in members}) != len(members):
        raise ValueError("duplicate curated member")
    for member in members:
        for r in member["source_references"]:
            ref = (r["dataset"], f"{r['dataset']}:{r['source_row']}")
            if ref in refs:
                raise ValueError("repeated curated source reference")
            refs[ref] = member
    grouped = {}
    seen_predictions = set()
    for prediction in predictions:
        member = refs.get((prediction["dataset"], prediction["row_id"]))
        if member is None:
            continue
        if (
            prediction["input_hash"] != member["input_hash"]
            or prediction["gold_leaf"] != member["gold_leaf"]
            or prediction["direction"] != member["input"]["direction"]
            or prediction["provider"] != member["input"]["provider"]
        ):
            raise ValueError("prediction provenance mismatch")
        source_view = tuple(prediction[k] for k in ("dataset", "row_id", "view", "head"))
        if source_view in seen_predictions:
            raise ValueError("duplicate source prediction")
        seen_predictions.add(source_view)
        key = (member["member_id"], prediction["view"], prediction["head"])
        signature = (prediction["leaf"], prediction["tier"])
        if key in grouped and grouped[key][0] != signature:
            raise ValueError("different predictions for an identical regression case")
        grouped[key] = (signature, prediction, member)
    scores = defaultdict(list)
    coverage = defaultdict(set)
    for (_, view, head), (_, prediction, member) in grouped.items():
        role = (
            "known_training_source_diagnostic"
            if member["source_role_train"]
            else "historical_regression"
        )
        scores[(member["cohort"], role, view, head)].append(prediction)
        coverage[member["member_id"]].add((view, head))
    for member in members:
        expected = {("head_only", h) for h in ("hinge", "transformer")}
        if member["cohort"] == "dictionary_regression":
            expected = {("merchant_dictionary", "dictionary")}
        elif member["cohort"] == "head_regression":
            expected |= {("legacy_head_plus_t5", h) for h in ("hinge", "transformer")}
        else:
            expected |= {("deterministic_research", "none")}
            expected |= {("research_pipeline", h) for h in ("hinge", "transformer")}
            if member["input"]["provider"] == "plaid":
                expected |= {("serving_plaid", h) for h in ("hinge", "transformer")}
        if coverage[member["member_id"]] != expected:
            raise ValueError("curated case has missing or unexpected prediction views")
    return [
        {
            "cohort": c,
            "role": r,
            "view": v,
            "head": h,
            "metrics": score(rows, general, detailed=True),
        }
        for (c, r, v, h), rows in sorted(scores.items())
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--monorepo", type=Path, required=True)
    parser.add_argument("--research", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--key-file", type=Path, required=True)
    parser.add_argument("--key-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    args.output.mkdir(mode=0o700, exist_ok=False)
    root = args.monorepo / "apps/ob-txn-categoriser"
    public_baseline = root / "research/waterfall-changes/baseline-2026-09-15/summary.json"
    if (args.baseline / "summary.json").read_bytes() != public_baseline.read_bytes():
        raise ValueError("baseline differs from retained public evidence")
    baseline = strict_json_loads(public_baseline.read_bytes())
    inventory, sources, metadata = inventory_sources(
        args.monorepo, args.research, root / "scripts/evaluation_inventory.json"
    )
    records = []
    general = baseline["general_mapping"]
    for dataset, task in inventory["tasks"].items():
        for number, (row, original) in enumerate(
            zip(
                adapt(dataset, task, sources[dataset], sources, general),
                sources[dataset],
                strict=True,
            ),
            1,
        ):
            inputs = {
                k: row[k]
                for k in (
                    "merchant_raw",
                    "description_raw",
                    "direction",
                    "amount",
                    "provider",
                    "native_category",
                )
            }
            records.append(
                {
                    "dataset": dataset,
                    "source_row": number,
                    "task": task,
                    "source_sha256": metadata[dataset]["registry_entry"]["sha256"],
                    "source_role": original.get(
                        "role", metadata[dataset]["registry_entry"]["role"]
                    ),
                    "label_provenance": row["label_provenance"],
                    "gold_leaf": row["gold_leaf"],
                    "input_hash": row["input_hash"],
                    "input": inputs,
                }
            )
    members, conflicts, report = curate(records, private_key(args.key_file, args.key_id))
    for name, rows in (("members.jsonl", members), ("label-conflicts.jsonl", conflicts)):
        with (args.output / name).open("xb") as stream:
            for row in rows:
                stream.write(canonical_json(row) + b"\n")
    predictions_path = args.baseline / "rows.jsonl"
    # Baseline carries a content receipt for its private per-view predictions.
    expected = baseline["private_rows_sha256"]
    if file_sha256(predictions_path) != expected:
        raise ValueError("cached prediction digest mismatch")
    with predictions_path.open("rb") as stream:
        scores = rescore(members, (strict_json_loads(line) for line in stream), general)
    report.update(
        member_object_sha256=file_sha256(args.output / "members.jsonl"),
        conflict_object_sha256=file_sha256(args.output / "label-conflicts.jsonl"),
        source_inventory_sha256=file_sha256(root / "scripts/evaluation_inventory.json"),
        source_registry_sha256=inventory["base_registry_sha256"],
        source_files={
            k: v["registry_entry"]["sha256"] for k, v in metadata.items() if "registry_entry" in v
        },
        baseline_summary_sha256=file_sha256(public_baseline),
        baseline_prediction_sha256=expected,
        adapter_sha256=file_sha256(Path(__file__)),
        scores=scores,
        score_interpretation="deduplicated_historical_diagnostics_not_population_or_unseen_accuracy",
        conflicts_require_independent_adjudication=True,
    )
    save(args.output / "summary.json", report)
    print(
        f"Curated {len(members):,} historical cases; {len(conflicts):,} label conflicts withheld."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("Legacy curation failed; no new evaluation cohort is certified.") from None

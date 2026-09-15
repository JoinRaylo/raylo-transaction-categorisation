"""Independent paired review for CREDIT-PAYROLL-001; reports contain no raw narratives."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_run(path):
    summary = json.loads((path / "summary.json").read_bytes())
    assert summary["status"] == "passed"
    assert digest(path / "rows.jsonl") == summary["private_rows_sha256"]
    rows = [json.loads(line) for line in (path / "rows.jsonl").read_bytes().splitlines()]
    assert len(rows) == summary["private_rows_n"]
    indexed = {(r["dataset"], r["view"], r["head"], r["row_id"]): r for r in rows}
    assert len(indexed) == len(rows)
    return summary, indexed


def review(baseline, candidate, replay):
    old, before = read_run(baseline)
    new, after = read_run(candidate)
    repeated, again = read_run(replay)
    assert old["harness_sha256"] == new["harness_sha256"] == repeated["harness_sha256"]
    assert new["general_mapping"] == old["general_mapping"]
    assert before.keys() == after.keys() == again.keys()
    assert after == again
    assert new["evaluations"] == repeated["evaluations"]
    assert new["comparison"] == repeated["comparison"]
    changed = []
    for key in before:
        a, b = before[key], after[key]
        if a == b:
            continue
        assert (
            key[0] == "synthetic_credit_regressions" and key[3] == "synthetic_credit_regressions:7"
        )
        assert key[1] in {"deterministic_research", "research_pipeline", "serving_plaid"}
        assert a["leaf"] == "groceries" and a["tier"] == "T4_dictionary"
        expected = dict(
            a,
            leaf="salary",
            tier="T2_compound_waitrose_explicit_payroll",
            rule_id="waitrose_explicit_payroll",
        )
        assert b == expected  # Includes unchanged raw model output and residual flag.
        changed.append(key)
    assert len(changed) == 5
    assert new["comparison"]["changed_rows_n"] == 5
    assert (
        digest(candidate / "changed_rows.jsonl") == new["comparison"]["private_changed_rows_sha256"]
    )

    def key(e):
        return e["dataset"], e["view"], e["head"]

    original = {key(e): e for e in old["evaluations"]}
    unchanged_real_views = 0
    for e in new["evaluations"]:
        if e["dataset"] != "synthetic_credit_regressions":
            assert e == original[key(e)]  # Every nested metric, slice and per-leaf result.
            unchanged_real_views += 1
    transitions = Counter()
    for c in new["comparison"]["comparisons"]:
        transitions.update(c["transitions"])
        assert c["fixed_baseline_residual"]["baseline"] == c["fixed_baseline_residual"]["candidate"]
    assert transitions == {"wrong_to_correct": 5}
    return {
        "status": "passed",
        "change_id": "CREDIT-PAYROLL-001",
        "baseline_summary_sha256": digest(baseline / "summary.json"),
        "candidate_summary_sha256": digest(candidate / "summary.json"),
        "research_replay_summary_sha256": digest(replay / "summary.json"),
        "reviewer_sha256": digest(Path(__file__)),
        "paired_per_view_records": len(before),
        "changed_per_view_records": len(changed),
        "unique_changed_synthetic_inputs": 1,
        "changed_non_synthetic_records": 0,
        "unchanged_non_synthetic_evaluation_views": unchanged_real_views,
        "transitions_per_view": dict(transitions),
        "correct_to_wrong": 0,
        "wrong_to_different_wrong": 0,
        "fixed_baseline_residual_metrics_identical": True,
        "residual_membership_identical": True,
        "raw_head_outputs_identical": True,
        "research_replay_identical": True,
        "candidate_rows_sha256": digest(candidate / "rows.jsonl"),
        "research_replay_rows_sha256": digest(replay / "rows.jsonl"),
        "research_replay_checks": repeated["checks"],
        "research_replay_independent_validation": repeated["independent_validation"],
        "research_replay_command": repeated["command"],
        "quality_limit": (
            "No Waitrose credits in real repeatable data; "
            "synthetic behaviour is not generalisation evidence."
        ),
        "promotion": "not deployed; retain baseline staging release",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("baseline", "candidate", "replay", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    result = review(args.baseline, args.candidate, args.replay)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if not k.startswith("research_replay_")}))

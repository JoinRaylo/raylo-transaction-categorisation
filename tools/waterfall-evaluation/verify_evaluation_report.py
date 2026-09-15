"""Independent score recount using research's analyser and sklearn's F1 metrics."""

import argparse
import ast
import math
from collections import Counter, defaultdict
from pathlib import Path

from raylo_txncat.hashing import canonical_json, sha256, strict_json_loads


def verify(report, rows, research):
    from sklearn.metrics import precision_recall_fscore_support

    path = research / "src/confusion_analysis.py"
    raw = path.read_bytes()
    if sha256(raw) != report["source_sha256"]["research"]["src/confusion_analysis.py"]:
        raise ValueError("research metric source differs from evaluated snapshot")
    tree = ast.parse(raw)
    wanted = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "analyse":
            wanted.append(node)
        elif (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id in {"CREDIT_BAR_LEAVES", "RISK_GENERAL_CATEGORIES"}
        ):
            ast.literal_eval(node.value)
            wanted.append(node)
    if len(wanted) != 3:
        raise ValueError("unexpected research analyser definitions")
    namespace = {"Counter": Counter, "defaultdict": defaultdict}
    exec(compile(ast.Module(body=wanted, type_ignores=[]), str(path), "exec"), namespace)
    general = report["general_mapping"]
    risk = {
        leaf for leaf, parent in general.items() if parent in namespace["RISK_GENERAL_CATEGORIES"]
    }
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["dataset"], row["view"], row["head"])].append(row)
    expected = {(e["dataset"], e["view"], e["head"]) for e in report["evaluations"]}
    if set(grouped) != expected or len(expected) != len(report["evaluations"]):
        raise ValueError("summary/rows coverage mismatch")
    checks = 0
    for entry in report["evaluations"]:
        subset = grouped[(entry["dataset"], entry["view"], entry["head"])]
        m = entry["metrics"]["all"]
        original = [
            {
                "gold_leaf": r["gold_leaf"],
                "pred_leaf": r["leaf"] or "unclassified_other",
                "direction": r["direction"],
            }
            for r in subset
        ]
        independent = namespace["analyse"](original, general, risk)
        for key, value in (
            ("research_exact_leaf_accuracy", independent["leaf_acc"]),
            ("research_exact_general_accuracy", independent["gen_acc"]),
            ("risk_leaf_accuracy", independent["risk_acc"]),
        ):
            if m[key] != value:
                raise ValueError(f"independent research metric mismatch: {key}")
            checks += 1
        specific = [r for r in subset if r["leaf"] and not r["leaf"].startswith("unclassified_")]
        if m["classified_n"] != len(specific) or m["correct_specific_leaf_n"] != sum(
            r["leaf"] == r["gold_leaf"] for r in specific
        ):
            raise ValueError("independent specific counts differ")
        labels = list(m["per_leaf"])
        p, r, f, supports = precision_recall_fscore_support(
            [x["gold_leaf"] for x in subset],
            [x["leaf"] or "__abstain__" for x in subset],
            labels=labels,
            zero_division=0,
        )
        for index, label in enumerate(labels):
            leaf = m["per_leaf"][label]
            if leaf["support"] != int(supports[index]):
                raise ValueError("independent support differs")
            for key, value in (("precision", p[index]), ("recall", r[index]), ("f1", f[index])):
                if leaf[key] is not None and not math.isclose(
                    leaf[key], float(value), abs_tol=1e-12
                ):
                    raise ValueError(f"independent sklearn metric mismatch: {key}")
                checks += 1
        for field in ("direction", "provider", "merchant_state", "label_provenance", "tier"):
            if sum(s["n"] for s in entry["metrics"]["by_" + field].values()) != m["n"]:
                raise ValueError("split total differs")
    return {
        "status": "passed",
        "views_recounted": len(expected),
        "metric_checks": checks,
        "research_analyser_sha256": sha256(raw),
        "verifier_sha256": sha256(Path(__file__).read_bytes()),
        "methods": [
            "original research analyse (AST-only, no module I/O)",
            "independent specific counts",
            "sklearn precision/recall/F1",
            "slice totals",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--research-root", type=Path, required=True)
    args = parser.parse_args()
    report = strict_json_loads((args.run / "summary.json").read_bytes())
    if report["status"] != "passed":
        raise ValueError("cannot validate an incomplete run")
    raw = (args.run / "rows.jsonl").read_bytes()
    if sha256(raw) != report["private_rows_sha256"]:
        raise ValueError("private prediction file changed")
    result = verify(
        report, [strict_json_loads(line) for line in raw.splitlines()], args.research_root
    )
    result["summary_sha256"] = sha256((args.run / "summary.json").read_bytes())
    (args.run / "validation.json").write_bytes(canonical_json(result) + b"\n")
    print(
        f"Independently verified {result['views_recounted']} views "
        f"and {result['metric_checks']} metrics"
    )


if __name__ == "__main__":
    main()

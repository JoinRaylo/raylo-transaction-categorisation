"""Derive CREDIT-PAYROLL-001 locally; never rebuild/reselect models or publish.

This deliberately supports one predeclared CSV append to one immutable parent.
It is not a general escape hatch from the frozen B3/B5 compiler provenance.
"""

import argparse
import csv
import io
import subprocess
import sys
from pathlib import Path

from raylo_txncat.bundle import load_local
from raylo_txncat.compile_artefacts import read_csv, write_bundle
from raylo_txncat.hashing import canonical_json, sha256

PARENT = "a2553f3462205963254b0fb1ad9dff6d64e1399abdecaab93977265908c7f23d"
CSV_PATH = "taxonomy/rules/t2_entity_collisions.csv"
RULE = {
    "rule_id": "waitrose_explicit_payroll",
    "merchant": "waitrose",
    "pattern": r"^[ \t\r\n]*waitrose[ \t]+payroll[ \t\r\n]*$",
    "detailed_category": "salary",
    "direction": "credit",
    "notes": "CREDIT-PAYROLL-001: exact explicit payroll narrative only; no amount inference.",
}


def addition_bytes():
    stream = io.StringIO(newline="")
    csv.DictWriter(stream, fieldnames=list(RULE)).writerow(RULE)
    return stream.getvalue().encode()


def verify_append(parent_raw, candidate_raw):
    if candidate_raw != parent_raw + addition_bytes():
        raise ValueError("candidate must be exactly the predeclared CSV append")


def derive(parent_path, research, output):
    parent = load_local(parent_path, expected_sha=PARENT)
    provenance = parent.json("provenance.json")
    records = provenance["source_files"]
    old_csv = next(r for r in records if r["path"] == CSV_PATH)
    frozen_csv = subprocess.check_output(
        ["git", "show", f"{provenance['research_commit']}:{CSV_PATH}"], cwd=research
    )
    if sha256(frozen_csv) != old_csv["sha256"] or len(frozen_csv) != old_csv["bytes"]:
        raise ValueError("parent CSV does not match frozen source provenance")
    new_raw = (research / CSV_PATH).read_bytes()
    verify_append(frozen_csv, new_raw)
    for record in records:
        if record["path"].startswith(("src/", "taxonomy/")) and record["path"] != CSV_PATH:
            raw = (research / record["path"]).read_bytes()
            if sha256(raw) != record["sha256"] or len(raw) != record["bytes"]:
                raise ValueError("unexpected research source drift")
    compiled = parent.json("t2_collisions.json")
    rows = read_csv(research / CSV_PATH, allow_extra_notes=True)
    if rows != compiled["csv_rows"] + [RULE]:
        raise ValueError("compiled collision diff is not exactly the declared rule")
    if RULE["detailed_category"] not in parent.json("taxonomy.json"):
        raise ValueError("candidate references an unknown leaf")
    compiled["csv_rows"] = rows
    new_record = {"path": CSV_PATH, "bytes": len(new_raw), "sha256": sha256(new_raw)}
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=research).decode().strip()
    # Keep the parent compiler/selection lineage explicit. The derived source
    # list updates just the CSV; model/train records remain inherited provenance.
    provenance["derivation"] = {
        "schema_version": "single-collision-evaluation-v1",
        "change_id": "CREDIT-PAYROLL-001",
        "purpose": "offline evaluation only; no deployment approval",
        "parent_bundle_sha": PARENT,
        "parent_provenance_sha256": sha256(parent.files["provenance.json"]),
        "parent_research_commit": provenance["research_commit"],
        "parent_compiler_sha256": provenance["compiler_sha256"],
        "source_before": old_csv,
        "source_after": new_record,
        "builder_sha256": sha256(Path(__file__).read_bytes()),
        "python": sys.version,
        "research_patch_sha256": sha256(
            subprocess.check_output(["git", "diff", "HEAD", "--binary"], cwd=research)
        ),
        "inherited_payloads": {
            name: sha256(raw)
            for name, raw in parent.files.items()
            if name not in {"t2_collisions.json", "provenance.json"}
        },
        "training_inputs_reconsumed": False,
        "selection_rerun": False,
    }
    provenance["research_commit"] = commit
    provenance["source_files"] = [new_record if r["path"] == CSV_PATH else r for r in records]
    payloads = dict(parent.files)
    payloads["t2_collisions.json"] = canonical_json(compiled) + b"\n"
    payloads["provenance.json"] = canonical_json(provenance) + b"\n"
    metadata = parent.manifest.model_dump(mode="json", exclude={"files", "bundle_sha"})
    metadata["source_commit"] = commit
    metadata["rules_version"] = sha256(
        canonical_json(
            {
                name: sha256(payloads[name])
                for name in (
                    "rules.json",
                    "t2_collisions.json",
                    "plaid_pfc_map.json",
                    "equifax_map.json",
                )
            }
        )
    )
    return write_bundle(output, payloads, metadata)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent", required=True, type=Path)
    parser.add_argument("--research-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(derive(args.parent, args.research_root.resolve(), args.output))


if __name__ == "__main__":
    main()

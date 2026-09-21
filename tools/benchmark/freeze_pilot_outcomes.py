"""Freeze the 500 pilot outcomes through the receipt-bound importer (AIE-512).

Expected digests are read from the previously written receipts (views receipt,
votes receipt, lead-review summary, decisions receipt); observed digests are
recomputed over the files on disk now.  Any drift fails the import.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
from pathlib import Path

from raylo_txncat.benchmark_import import (
    FinalOutcome,
    OutcomeBinding,
    import_outcomes,
    verify_publication,
)

B = (
    Path.home()
    / ".local/share/raylo-txncat/benchmark-eval-pilot/reconstruction-2026-09-21"
)
REAL = B / "adjudication-opus5/real"
LR = REAL / "lead-review"
TAX = Path("/private/tmp/txncat-aie510-g0-research/taxonomy/taxonomy.csv")


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> None:
    os.umask(0o077)
    views_receipt = json.loads((B / "views/receipt.json").read_text())
    votes_receipt = json.loads((B / "votes/votes-receipt.json").read_text())
    decisions_receipt = json.loads((LR / "carlos-decisions-receipt.json").read_text())
    expected = OutcomeBinding(
        membership_sha256=views_receipt["membership_sha256"],
        pilot_sha256=views_receipt["pilot_sha256"],
        comparison_sha256=views_receipt["comparison_sha256"],
        proposals_sha256=decisions_receipt["inputs_sha256"]["proposals"],
        decisions_sha256=decisions_receipt["outputs_sha256"][
            "carlos-decisions-2026-09-21.csv"
        ],
        taxonomy_sha256=votes_receipt["taxonomy_sha256"],
    )
    observed = OutcomeBinding(
        membership_sha256=sha(B / "views/membership.csv"),
        pilot_sha256=sha(B / "views/pilot.jsonl"),
        comparison_sha256=sha(B / "votes/comparison.jsonl"),
        proposals_sha256=sha(REAL / "attempt-1-proposals.jsonl"),
        decisions_sha256=sha(LR / "carlos-decisions-2026-09-21.csv"),
        taxonomy_sha256=sha(TAX),
    )

    membership_ids = frozenset(
        json.loads(line)["pilot_id"]
        for line in (B / "views/views.jsonl").read_text().splitlines()
        if line
    )
    unanimous_ids = frozenset(
        json.loads(line)["item_id"]
        for line in (B / "votes/comparison.jsonl").read_text().splitlines()
        if line
        and json.loads(line)["agreement"] == "unanimous"
        and {v["status"] for v in json.loads(line)["votes"].values()} == {"labelled"}
    )
    taxonomy_leaves = frozenset(
        r["detailed_category"] for r in csv.DictReader(TAX.open())
    )

    outcomes = tuple(
        FinalOutcome(
            item_id=o["item_id"],
            final_status=o["final_status"],
            final_leaf=o["final_leaf"],
            decision_source=o["decision_source"],
            sheet_row=o["sheet_row"],
            proposal_sha256=o.get("opus_proposal_sha256"),
        )
        for o in (
            json.loads(line)
            for line in (LR / "final-pilot-outcomes.jsonl").read_text().splitlines()
            if line
        )
    )

    publication = import_outcomes(
        membership_ids=membership_ids,
        unanimous_ids=unanimous_ids,
        taxonomy_leaves=taxonomy_leaves,
        outcomes=outcomes,
        expected_binding=expected,
        observed_binding=observed,
    )
    verify_publication(publication)

    out = LR / "final-outcome-publication.json"
    out.write_text(
        json.dumps(publication.model_dump(mode="python"), indent=2, sort_keys=True)
        + "\n"
    )
    os.chmod(out, 0o600)
    reloaded = json.loads(out.read_text())
    assert sha(out) == hashlib.sha256(out.read_bytes()).hexdigest()
    json.dump(
        {
            "publication_sha256": publication.publication_sha256,
            "outcome_count": publication.outcome_count,
            "status_counts": publication.status_counts,
            "decision_source_counts": publication.decision_source_counts,
            "distinct_final_leaves": publication.distinct_final_leaves,
            "binding_ok": True,
            "authorizes_consumption": publication.authorizes_consumption,
            "publication_file_sha256": sha(out),
            "reload_ok": reloaded["publication_sha256"]
            == publication.publication_sha256,
        },
        sys.stdout,
        indent=2,
    )
    print()


if __name__ == "__main__":
    main()

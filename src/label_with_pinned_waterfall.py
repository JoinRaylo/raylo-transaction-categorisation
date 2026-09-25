"""Label rows with a pinned research waterfall checkout (T1-T5 only).

Runs in its own process so the waterfall comes from ``--research-root``
(the staging bundle's research source) rather than whichever checkout imports
it.  Reads JSONL rows ``{"key", "merchant", "description", "direction",
"native"}`` on stdin.  Writes ``{"key", "leaf", "tier"}`` on stdout, where
``leaf`` is null unless T1-T5 decides the row.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--research-root", type=pathlib.Path, required=True)
    args = parser.parse_args()
    root = args.research_root.resolve()
    sys.path.insert(0, str(root / "src"))
    os.chdir(root)
    import final_evaluation as fe  # noqa: PLC0415

    if not pathlib.Path(fe.__file__).resolve().is_relative_to(root):
        raise SystemExit("final_evaluation was not loaded from --research-root")
    fe.SUB_MAP, fe.PRI_MAP, fe.PLAID_MAP, _ = fe.load_crosswalk()
    fe.DICTIONARY = fe.load_dictionary()
    fe.RULES = fe.load_rules()
    for line in sys.stdin:
        row = json.loads(line)
        leaf, tier = fe.our_leaf(
            row["merchant"] or "",
            row["direction"],
            row["description"] or "",
            fe.plaid_native_leaf,
            row.get("native") or "",
            row["direction"],
        )
        decided = bool(tier) and tier[:2] in {"T1", "T2", "T3", "T4", "T5"}
        print(json.dumps({"key": row["key"], "leaf": leaf if decided else None, "tier": tier}))


if __name__ == "__main__":
    main()

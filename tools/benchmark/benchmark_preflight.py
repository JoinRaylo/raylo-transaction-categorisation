"""Aggregate a private B02 candidate/index export; does not reserve or authorize it.

Research runs this identical adapter against the same hash-pinned shared package.
No raw text/IDs, identity key, labels, or model weights are required by this CLI.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

PINNED_FILES = (
    "lib/raylo-txncat/src/raylo_txncat/benchmark.py",
    "lib/raylo-txncat/src/raylo_txncat/classifier_types.py",
    "lib/raylo-txncat/src/raylo_txncat/hashing.py",
    "lib/raylo-txncat/src/raylo_txncat/head_hinge.py",
    "lib/raylo-txncat/src/raylo_txncat/types.py",
    "lib/raylo-txncat/src/raylo_txncat/__init__.py",
)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--monorepo-root", type=Path, required=True)
    parser.add_argument("--implementation", type=Path, required=True)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--candidates", type=Path, required=True, help="Private Subject JSONL")
    parser.add_argument("--output", type=Path, required=True, help="New aggregate JSON file")
    args = parser.parse_args()
    root = args.monorepo_root.resolve()
    implementation_bytes = args.implementation.read_bytes()
    # Bootstrapping reads only a fixed path allowlist, before importing the package.
    implementation = json.loads(implementation_bytes)
    if (
        set(implementation) != {"files_sha256", "policy_version"}
        or implementation["policy_version"] != "three-views-v1"
        or set(implementation["files_sha256"]) != set(PINNED_FILES)
    ):
        raise ValueError("unsupported implementation manifest")
    for relative, expected in implementation["files_sha256"].items():
        if sha((root / relative).read_bytes()) != expected:
            raise ValueError("shared implementation differs from manifest")
    sys.path.insert(0, str(root / "lib/raylo-txncat/src"))
    from raylo_txncat.benchmark import IndexSnapshot, Subject, profile_candidates
    from raylo_txncat.hashing import strict_json_loads

    # Strict duplicate-key/Unicode checking precedes JSON-mode tuple conversion.
    strict_json_loads(implementation_bytes)
    index_bytes, candidates_bytes = args.index.read_bytes(), args.candidates.read_bytes()
    strict_json_loads(index_bytes)
    index = IndexSnapshot.model_validate_json(index_bytes)

    def candidates():
        for line in candidates_bytes.splitlines():
            if not line.strip():
                raise ValueError("blank candidate record")
            strict_json_loads(line)
            yield Subject.model_validate_json(line)

    profile = profile_candidates(candidates(), index)
    profile.update(
        implementation_sha256=sha(implementation_bytes),
        index_object_sha256=sha(index_bytes),
        candidates_object_sha256=sha(candidates_bytes),
        adapter_sha256=sha(Path(__file__).read_bytes()),
    )
    # Avoid replacing a dated result or partially writing it when validation fails.
    encoded = json.dumps(profile, indent=2, sort_keys=True) + "\n"
    with args.output.open("x") as stream:
        stream.write(encoded)
    print(f"Preflight profiled {profile['rows']} rows; no reservation or consumption authorized.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError):
        # Do not print validation exceptions containing private export values/paths.
        raise SystemExit(
            "Preflight failed: invalid, incompatible or unavailable inputs/output."
        ) from None

"""Derive the Plaid-only pretraining corpus (retrain amendment 1, 2026-09-23).

Encoder variant A is pretrained on the Plaid rows of the guarded corpus only.
This script:
1. verifies every source shard's receipt and manifest digest;
2. keeps the rows of ``--provider``;
3. re-shards them and re-runs the canonical gate (``domain_pretraining``) on
   each new shard;
4. issues fresh signed receipts under the same consumer name.

``pretrain_mlm.py`` therefore reads the result exactly as it reads the full
corpus.  The manifest records which corpus it was derived from.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import sys

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src" / "transformer"))

import eval_protection  # noqa: E402
from build_pretrain_guarded import CONSUMER, PURPOSE, SHARD_ROWS  # noqa: E402


def main() -> None:
    parser = eval_protection.add_args(argparse.ArgumentParser(description=__doc__))
    parser.add_argument("--source", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    parser.add_argument("--provider", default="plaid")
    args = parser.parse_args()
    protection, _publication = eval_protection.load_release(args)
    manifest = json.loads((args.source / "MANIFEST.json").read_text())
    if manifest.get("protected_release") != eval_protection.PINNED_BINDING:
        raise RuntimeError("source corpus was guarded against a different release")
    frames = []
    for shard in manifest["shards"]:
        path = args.source / shard["path"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != shard["sha256"]:
            raise RuntimeError(f"{path.name} differs from its manifest entry")
        eval_protection.verify_artifact(
            path, expected_consumer=CONSUMER, expected_purpose=PURPOSE, protection=protection
        )
        df = pd.read_parquet(path)
        frames.append(df[df.provider == args.provider])
    df = pd.concat(frames, ignore_index=True).sample(frac=1.0, random_state=42)
    df = df.reset_index(drop=True)
    out = args.output
    out.mkdir(parents=True, exist_ok=False)
    os.chmod(out, 0o700)
    shards = []
    for index, start in enumerate(range(0, len(df), SHARD_ROWS)):
        part = df.iloc[start : start + SHARD_ROWS]
        rows = part[["provider", "account_id", "transaction_id", "customer_id"]].to_dict("records")
        guarded = eval_protection.apply(rows, args, purpose=PURPOSE)
        if len(guarded) != len(rows) or sum(guarded.guard.excluded.values()):
            raise RuntimeError("the gate excluded rows of an already-guarded corpus; stopping")
        path = out / f"pretrain-{index:03d}.parquet"
        part.to_parquet(path, index=False)
        os.chmod(path, 0o600)
        receipt = eval_protection.write_artifact_receipt(
            path, consumer=CONSUMER, purpose=PURPOSE, guard=guarded.guard
        )
        shards.append({"path": path.name, "rows": len(part),
                       "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                       "receipt": receipt.name})
    derived = {
        **{k: v for k, v in manifest.items() if k not in {"shards", "sentences", "by_provider",
                                                          "credit_share"}},
        "derived_from": {
            "manifest_sha256": hashlib.sha256(
                (args.source / "MANIFEST.json").read_bytes()).hexdigest(),
            "provider_kept": args.provider,
            "amendment": "TxCat-1 retrain amendment 1 (variant A, Plaid-only)",
        },
        "sentences": len(df),
        "by_provider": {args.provider: len(df)},
        "credit_share": round(float((df.direction == "credit").mean()), 4),
        "shards": shards,
    }
    (out / "MANIFEST.json").write_text(json.dumps(derived, indent=2, sort_keys=True) + "\n")
    os.chmod(out / "MANIFEST.json", 0o600)
    print(json.dumps({k: derived[k] for k in ("sentences", "by_provider", "credit_share")}))


if __name__ == "__main__":
    main()

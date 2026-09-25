"""Run one synthetic B03-A race through the canonical app authority module."""

import argparse
import json
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--monorepo-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.monorepo_root.resolve()
    sys.path.insert(0, str(root / "lib/raylo-txncat/src"))

    from pydantic import SecretBytes
    from raylo_txncat.benchmark import IdentityKey, IndexSnapshot, Membership, Projection, Subject
    from raylo_txncat.benchmark_authority import (
        ClaimIntent,
        ClaimManifest,
        InMemoryAuthorityStore,
        LocalAuthority,
        ProvenanceRefs,
    )
    from raylo_txncat.hashing import canonical_json, sha256

    key = IdentityKey(
        key_id="synthetic-cli-key-v1",
        secret=SecretBytes(b"synthetic-cli-authority-key-32-bytes!!"),
    )
    legacy_body = b"synthetic legacy exclusion bytes"
    index = IndexSnapshot(
        key_id=key.key_id,
        epoch=0,
        lineage_manifest_sha256=sha256(b"synthetic lineage"),
        identity_history_complete=True,
        input_history_complete=True,
        family_history_complete=True,
        legacy_manifest_sha256=sha256(legacy_body),
        required_projections=("transformer-sentence-v1",),
    )
    store = InMemoryAuthorityStore(index)
    authority = LocalAuthority(store)
    legacy = store.upload_immutable("evidence/legacy", legacy_body, role="legacy_exclusion")

    def make_subject(name: str, *, observation=None):
        source_body = f"synthetic source {name}".encode()
        identity_body = f"synthetic identity {name}".encode()
        source = store.upload_immutable(
            f"evidence/source/{name}", source_body, role="source_snapshot"
        )
        identity = store.upload_immutable(
            f"evidence/identity/{name}", identity_body, role="identity_evidence"
        )
        subject = Subject(
            key_id=key.key_id,
            source_snapshot_sha256=source.sha256,
            identity_evidence_sha256=identity.sha256,
            identity_status="verified",
            observation=observation or sha256(f"{name} event".encode()),
            event_aliases=(),
            accounts=(sha256(f"{name} account".encode()),),
            customers=(sha256(f"{name} customer".encode()),),
            merchant=sha256(f"{name} merchant".encode()),
            family=sha256(f"{name} family".encode()),
            family_status="reviewed",
            projections=(
                Projection(
                    version="transformer-sentence-v1",
                    token=sha256(f"{name} input".encode()),
                ),
            ),
            legacy_transaction_key=sha256(f"{name} legacy event".encode()),
            legacy_merchant_key=sha256(b"synthetic legacy merchant"),
            legacy_family_key=sha256(b"synthetic legacy family"),
            near_duplicate_status="clear",
        )
        return subject, source, identity

    reserve_subject, reserve_source, reserve_identity = make_subject("reserve")
    train_subject, train_source, train_identity = make_subject(
        "train", observation=reserve_subject.observation
    )

    def make_intent(operation_id, subject, source, identity, claim_kind):
        if claim_kind == "reservation":
            membership = Membership(
                subject=subject,
                purpose="benchmark",
                views=("representative",),
                partition="core",
                lifecycle="reserved",
            )
            purpose = "benchmark"
        else:
            membership = Membership(
                subject=subject,
                purpose="supervised_training",
                lifecycle="exposed",
            )
            purpose = "supervised_training"
        data = store.upload_immutable(
            f"claims/{operation_id}/data",
            f"synthetic data {operation_id}".encode(),
            role="claim_data",
        )
        manifest = ClaimManifest(
            claim_kind=claim_kind,
            purpose=purpose,
            key_id=subject.key_id,
            subject_sha256=sha256(canonical_json(subject)),
            data_sha256=data.sha256,
        )
        manifest_ref = store.upload_immutable(
            f"claims/{operation_id}/manifest.json",
            canonical_json(manifest),
            role="claim_manifest",
        )
        return ClaimIntent(
            operation_id=operation_id,
            claim_kind=claim_kind,
            membership=membership,
            key_id=subject.key_id,
            data_object=data,
            manifest_object=manifest_ref,
            provenance=ProvenanceRefs(
                source_snapshot=source,
                identity_evidence=identity,
                legacy_exclusions=legacy,
            ),
        )

    reservation = make_intent(
        "cli-reservation", reserve_subject, reserve_source, reserve_identity, "reservation"
    )
    learning = make_intent("cli-learning", train_subject, train_source, train_identity, "learning")
    prepared_reservation = authority.prepare(reservation)
    prepared_learning = authority.prepare(learning)
    first = authority.commit(prepared_reservation)
    second = authority.commit(prepared_learning)
    result = {
        "schema_version": "benchmark-authority-simulation-v1",
        "scope": "synthetic_only",
        "authorizes_consumption": False,
        "prepared_epochs": [
            prepared_reservation.snapshot_epoch,
            prepared_learning.snapshot_epoch,
        ],
        "commit_statuses": [first.status, second.status],
        "final_epoch": store.read_snapshot().epoch,
        "committed_operations": sum(
            store.lookup_operation(operation_id) is not None
            for operation_id in (reservation.operation_id, learning.operation_id)
        ),
    }
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print("Synthetic authority simulation complete; no consumption authorized.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, TypeError, ValueError, KeyError):
        raise SystemExit(
            "Synthetic authority simulation failed: invalid or unavailable inputs."
        ) from None

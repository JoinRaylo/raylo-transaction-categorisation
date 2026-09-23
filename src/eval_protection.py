"""B04 boundary adapter (AIE-513): pin the frozen pilot release at consumer seams.

Every consumer that fetches or ingests customer-linked rows must call
``apply`` on the fetched batch before it writes or learns from them.  The
adapter imports the canonical ``raylo_txncat.benchmark_enforcement`` module —
the exclusion semantics live there, never forked here — and binds it to the
frozen pilot release digests (membership ``0afb4155…``, publication
``2b3c2f64…``).  A fetch whose rows lack B02 linkage identity fails closed, so
a consumer cannot run its linked-pool leg until its query carries
``account_id``/``transaction_id``/``customer_id``.

The private membership and publication paths are supplied per run; only their
pinned digests are committed.  ``RAYLO_TXNCAT_SRC`` or ``--txncat-src`` points
at the monorepo ``lib/raylo-txncat/src`` checkout.
"""

from __future__ import annotations

import os
import pathlib
import sys

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

# The only approved protected release (mirrors the monorepo PINNED_RELEASE).
# v2, 2026-09-23: protect the combined 3,295-event membership (the 2,000-row
# benchmark plus the 1,295 expansion rows being labelled to join it), a
# superset of the AIE-512 pilot, whose frozen publication is still verified.
PINNED_BINDING = {
    "schema_version": "benchmark-release-binding-v2",
    "membership_sha256": "675490115bd07c96d9102118cd8ca27924b88b896bc518f17da53f55e76ddf56",
    "pilot_sha256": "fc5c626cdc0966d46dd1a1a9c04f04f2f9c515cecfedb0587019c16a7f684248",
    "publication_sha256": "2b3c2f6443c99f30272f50075b2f7cf4647b04fb5ccdf1926467a24d3d4e8436",
    "publication_file_sha256": "eaf5a8bba13a60e007fa7d92c9df8729c80e7e7b13a8b830c4c0642458c44f22",
    "publication_membership_sha256": (
        "0afb4155c750808e332ef2bf1cfb17866d152b3b374771ad77d2399a62d43068"
    ),
}


def _enforcement(txncat_src):
    """Import the canonical module; fail closed when the library is absent."""

    try:
        from raylo_txncat import benchmark_enforcement

        return benchmark_enforcement
    except ImportError:
        pass
    src = pathlib.Path(txncat_src or os.environ.get("RAYLO_TXNCAT_SRC", ""))
    if not (src / "raylo_txncat" / "benchmark_enforcement.py").exists():
        raise RuntimeError(
            "raylo_txncat.benchmark_enforcement not found; pass --txncat-src or "
            "set RAYLO_TXNCAT_SRC to the monorepo lib/raylo-txncat/src checkout"
        )
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    try:
        from raylo_txncat import benchmark_enforcement
    except ImportError as error:
        raise RuntimeError(
            f"raylo_txncat is already imported from a checkout lacking "
            f"benchmark_enforcement ({sys.modules.get('raylo_txncat')}); fix the "
            "environment rather than mixing checkouts"
        ) from error

    return benchmark_enforcement


def add_args(parser):
    """Attach the required protection arguments to a consumer's CLI."""

    parser.add_argument(
        "--protected-membership",
        required=True,
        type=pathlib.Path,
        help="Private eval-membership CSV; digest must equal the pinned release",
    )
    parser.add_argument(
        "--protected-publication",
        required=True,
        type=pathlib.Path,
        help="Frozen outcome publication JSON; digest must equal the pinned release",
    )
    parser.add_argument(
        "--txncat-src",
        type=pathlib.Path,
        default=None,
        help="Monorepo lib/raylo-txncat/src checkout (default: RAYLO_TXNCAT_SRC)",
    )
    return parser


def load_release(args):
    """Verify the private artifacts against the pinned binding and return the guard."""

    enforcement = _enforcement(getattr(args, "txncat_src", None))
    binding = enforcement.ReleaseBinding(**PINNED_BINDING)
    return enforcement.verify_release(
        membership_path=args.protected_membership,
        publication_path=args.protected_publication,
        binding=binding,
    )


class Guarded(list):
    """Rows retained by the protected-release guard, carrying its proof.

    Behaves exactly like ``list`` at existing call sites; the ``guard``
    attribute is the ``GuardResult`` ``issue_artifact_receipt`` requires to
    mint a bound receipt for the persisted batch.
    """

    def __init__(self, rows, guard):
        super().__init__(rows)
        self.guard = guard


def apply(rows, args, *, purpose=None):
    """Guard one fetched batch: verify the release, then exclude protected rows.

    Rows lacking linkage identity raise ``ProtectedMembershipError`` — the
    fetch is gated off until its query carries the identity columns.  Returns
    ``Guarded`` rows so the persisted artifact can be receipted against the
    exact guard run that produced it.
    """

    protection, publication = load_release(args)
    enforcement = _enforcement(getattr(args, "txncat_src", None))
    retained, guard = enforcement.guard_batch(
        protection, publication, rows, purpose=purpose
    )
    counts = dict(guard.excluded)
    print(
        f"B04 eval protection excluded {sum(counts.values())} rows ({counts})",
        file=sys.stderr,
    )
    return Guarded(retained, guard)


class _EnvArgs:
    def __init__(self):
        self.protected_membership = os.environ.get("EVAL_MEMBERSHIP")
        self.protected_publication = os.environ.get("EVAL_PUBLICATION")
        self.txncat_src = os.environ.get("RAYLO_TXNCAT_SRC")


def apply_env(rows, *, purpose=None):
    """``apply`` for consumers without argparse: paths come from the environment.

    ``EVAL_MEMBERSHIP`` and ``EVAL_PUBLICATION`` must point at the pinned
    private artifacts; ``RAYLO_TXNCAT_SRC`` at the lib checkout.  Any missing
    input fails closed.
    """

    args = _EnvArgs()
    if not args.protected_membership or not args.protected_publication:
        raise RuntimeError(
            "EVAL_MEMBERSHIP and EVAL_PUBLICATION must name the pinned private "
            "release artifacts before this consumer may touch the linked pool"
        )
    return apply(rows, args, purpose=purpose)


def assert_bound(membership_paths, args):
    """Verify supplied membership file(s) plus the publication = the pinned release."""

    enforcement = _enforcement(getattr(args, "txncat_src", None))
    paths = [pathlib.Path(p) for p in membership_paths]
    if len(paths) != 1:
        raise ValueError("the pinned release has exactly one protected membership")
    protection, publication = enforcement.verify_release(
        membership_path=paths[0],
        publication_path=args.protected_publication,
        binding=enforcement.ReleaseBinding(**PINNED_BINDING),
    )
    return protection, publication


def verify_fetch_receipt(receipt, *, txncat_src=None):
    """Check a committed fetch receipt binds the pinned protected membership."""

    enforcement = _enforcement(txncat_src)
    enforcement.verify_fetch_receipt(
        receipt, enforcement.ReleaseBinding(**PINNED_BINDING)
    )


def row_content_sha256(row, *, txncat_src=None):
    """Canonical per-row digest used by bound row manifests."""

    enforcement = _enforcement(txncat_src)
    return enforcement.sha256(enforcement.canonical_json(dict(row)))


def row_identity(row):
    """The row's exact Plaid linkage identity as a manifest claim, or None.

    Producers that transform guarded rows propagate the identity they
    received; a row without the linkage columns yields ``None`` — it cannot
    claim an identity it does not carry.
    """

    provider = str(row.get("provider") or "plaid")
    if provider != "plaid":
        return None
    ids = {
        key: row.get(key)
        for key in ("account_id", "transaction_id", "customer_id")
    }
    if not all(isinstance(value, str) and value.strip() for value in ids.values()):
        return None
    return {"provider": "plaid", **ids}


def verify_fetch_file(path, receipt, *, txncat_src=None):
    """Re-run exclusion over a fetched file against its signed receipt.

    The receipt's embedded guard token attests an exclusion run; this
    proves the bytes on disk are exactly that run's retained output —
    every row carries linkage identity, the sorted identity digest equals
    the guard's retained set and no protected member survives.
    """

    import json

    enforcement = _enforcement(txncat_src)
    if isinstance(receipt, (str, pathlib.Path)):
        receipt = json.loads(pathlib.Path(receipt).read_text(encoding="utf-8"))
    protection = _env_protection(enforcement)
    if protection is None:
        raise RuntimeError(
            "EVAL_MEMBERSHIP and EVAL_PUBLICATION must name the pinned release "
            "to re-run exclusion over a fetched artifact"
        )
    enforcement.verify_fetch_file(
        pathlib.Path(path),
        receipt,
        enforcement.ReleaseBinding(**PINNED_BINDING),
        protection=protection,
    )


def gate(consumer: str, reason: str):
    """Hard block for a consumer that cannot satisfy the protected-release guard."""

    raise RuntimeError(f"B04 gated off: {consumer} — {reason}")


def write_artifact_receipt(
    path,
    *,
    consumer: str,
    purpose: str,
    guard=None,
    input_receipts=(),
    manifest_identities=None,
    txncat_src=None,
):
    """Persist a release-bound receipt beside a guarded artifact.

    Issuance requires either ``guard`` — the ``GuardResult`` returned inside
    ``apply``/``apply_env``'s ``Guarded`` rows — or a non-empty
    ``input_receipts`` chain of already-verified receipts (derived merges).
    A file that neither passed the guard nor descends from verified inputs
    cannot be receipted.  ``manifest_identities`` binds per-row identity
    claims to the artifact's exact rows, in order.
    """

    import json

    enforcement = _enforcement(txncat_src)
    binding = enforcement.ReleaseBinding(**PINNED_BINDING)
    path = pathlib.Path(path)
    receipt = enforcement.issue_artifact_receipt(
        consumer=consumer,
        purpose=purpose,
        output_path=path,
        binding=binding,
        guard=guard,
        input_receipts=input_receipts,
        manifest_identities=manifest_identities,
    )
    receipt_path = path.with_name(path.name + ".b04-receipt.json")
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt_path


def _env_protection(enforcement):
    """Load the pinned release protection from the environment, if supplied."""

    args = _EnvArgs()
    if not args.protected_membership or not args.protected_publication:
        return None
    binding = enforcement.ReleaseBinding(**PINNED_BINDING)
    protection, _publication = enforcement.verify_release(
        membership_path=args.protected_membership,
        publication_path=args.protected_publication,
        binding=binding,
    )
    return protection


def verify_artifact(
    path, *, expected_consumer=None, expected_purpose=None, txncat_src=None,
    protection=None,
):
    """Fail closed unless ``path`` carries a bound receipt matching its bytes.

    Validates every receipt field strictly — including the recorded output
    path, the embedded guard block and the input chain — then re-hashes the
    artifact.  CSVs carrying linkage identity are re-checked against the
    protected membership itself, so a forged receipt cannot bless protected
    content.
    """

    import json

    enforcement = _enforcement(txncat_src)
    path = pathlib.Path(path)
    receipt_path = path.with_name(path.name + ".b04-receipt.json")
    if not receipt_path.is_file():
        raise RuntimeError(
            f"B04: {path} has no bound artifact receipt; refetch it under the "
            "protected-release guard before consuming it"
        )
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    enforcement.verify_artifact_receipt(
        receipt,
        enforcement.ReleaseBinding(**PINNED_BINDING),
        artifact_path=path,
        expected_consumer=expected_consumer,
        expected_purpose=expected_purpose,
        protection=(
            protection if protection is not None else _env_protection(enforcement)
        ),
    )
    return receipt


def verify_tuning_export(*, txncat_src=None, out_dir=None):
    """Fit boundary for the supervised export: bound receipts + manifests.

    ``tuning_train.jsonl``/``tuning_val.jsonl`` may only be consumed when
    their bound artifact receipts verify — each binds the exact bytes, a
    per-row identity manifest and the complete verified input chain (tier-B
    fetch, tier-A gold, top-ups).  The unsigned membership coverage is then
    checked for internal consistency only; it is not the trust anchor, and
    regenerating it cannot substitute for a missing or forged receipt.
    """

    from training_membership import verify_training_export

    out_dir = pathlib.Path(out_dir) if out_dir else pathlib.Path("outputs")
    verify_artifact(out_dir / "tuning_train.jsonl", txncat_src=txncat_src)
    verify_artifact(out_dir / "tuning_val.jsonl", txncat_src=txncat_src)
    coverage = verify_training_export(
        train_path=out_dir / "tuning_train.jsonl",
        selection_path=out_dir / "tuning_val.jsonl",
        lookup_path=out_dir / "tuning_membership_lookup.csv",
        coverage_path=out_dir / "tuning_membership_coverage.json",
    )
    import json

    receipt = json.loads((out_dir / "tuning_txns_receipt.json").read_text())
    verify_fetch_receipt(receipt, txncat_src=txncat_src)
    verify_fetch_file(
        out_dir / "tuning_txns.json", receipt, txncat_src=txncat_src
    )
    return coverage


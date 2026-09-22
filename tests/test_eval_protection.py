"""Synthetic B04 adapter tests (AIE-513).

Every fixture is fabricated; no real membership bytes leave this file.  The
end-to-end paths need ``raylo_txncat`` importable — ambient install or
``RAYLO_TXNCAT_SRC`` pointing at the monorepo lib checkout.
"""

import hashlib
import json
import os
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import eval_protection  # noqa: E402


def _enforcement_or_skip():
    try:
        return eval_protection._enforcement(os.environ.get("RAYLO_TXNCAT_SRC"))
    except (ImportError, RuntimeError) as error:
        pytest.skip(f"raylo_txncat.benchmark_enforcement unavailable: {error}")


MEMBERSHIP_HEADER = (
    "schema_version,provider,account_id,transaction_id,customer_id,role,"
    "primary_view,views,pilot_id,source_snapshot_sha256,row_sha256\n"
)


def _member(account: str, txn: str, customer: str, view: str = "representative") -> str:
    return (
        f"txncat-private-eval-membership-v1,plaid,{account},{txn},{customer},eval,"
        f"{view},{view},pilot-v1-{'0' * 64},{'a' * 64},{'b' * 64}\n"
    )


@pytest.fixture(autouse=True)
def receipt_signing(monkeypatch):
    """Ephemeral Ed25519 pair standing in for the pinned receipt key."""

    pytest.importorskip("cryptography")
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
    )
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        NoEncryption,
        PrivateFormat,
        PublicFormat,
    )

    key = Ed25519PrivateKey.generate()
    seed = key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    public = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    monkeypatch.setenv("B04_RECEIPT_SIGNING_KEY", seed.hex())
    enforcement = _enforcement_or_skip()
    monkeypatch.setattr(enforcement, "RECEIPT_PUBLIC_KEY_HEX", public.hex())
    return key


@pytest.fixture
def synthetic_release(tmp_path, monkeypatch):
    """A fabricated membership+publication pair pinned through PINNED_BINDING."""

    enforcement = _enforcement_or_skip()
    from raylo_txncat.benchmark_import import (
        FinalOutcome,
        OutcomeBinding,
        import_outcomes,
    )

    membership_path = tmp_path / "membership.csv"
    membership_path.write_text(
        MEMBERSHIP_HEADER
        + _member("acc-1", "txn-1", "cust-1")
        + _member("acc-1", "txn-2", "cust-1")
        + _member("acc-2", "txn-3", "cust-2", "unseen_input")
    )
    membership_sha = hashlib.sha256(membership_path.read_bytes()).hexdigest()

    items = frozenset(f"pilot-v1-{i:064x}" for i in range(1, 4))
    binding = OutcomeBinding(
        membership_sha256=membership_sha,
        pilot_sha256="b" * 64,
        comparison_sha256="c" * 64,
        proposals_sha256="d" * 64,
        decisions_sha256="e" * 64,
        taxonomy_sha256="f" * 64,
    )
    publication = import_outcomes(
        membership_ids=items,
        unanimous_ids=items,
        taxonomy_leaves=frozenset({"groceries"}),
        outcomes=tuple(
            FinalOutcome(
                item_id=i,
                final_status="labelled",
                final_leaf="groceries",
                decision_source="unanimous_votes",
            )
            for i in sorted(items)
        ),
        expected_binding=binding,
        observed_binding=binding,
    )
    publication_path = tmp_path / "publication.json"
    publication_path.write_text(publication.model_dump_json(indent=2))

    pinned = {
        "membership_sha256": membership_sha,
        "pilot_sha256": "b" * 64,
        "publication_sha256": publication.publication_sha256,
        "publication_file_sha256": hashlib.sha256(
            publication_path.read_bytes()
        ).hexdigest(),
    }
    monkeypatch.setattr(eval_protection, "PINNED_BINDING", pinned)
    return enforcement, membership_path, publication_path


class _Args:
    def __init__(self, membership, publication, txncat_src=None):
        self.protected_membership = membership
        self.protected_publication = publication
        self.txncat_src = txncat_src


def test_gate_is_terminal():
    with pytest.raises(RuntimeError, match="B04 gated off"):
        eval_protection.gate("synthetic.consumer", "synthetic reason")


def test_apply_env_requires_artifacts(monkeypatch):
    monkeypatch.delenv("EVAL_MEMBERSHIP", raising=False)
    monkeypatch.delenv("EVAL_PUBLICATION", raising=False)
    with pytest.raises(RuntimeError, match="EVAL_MEMBERSHIP"):
        eval_protection.apply_env([{"account_id": "a"}], purpose="supervised_training")


def test_apply_env_rejects_wrong_bytes(tmp_path, monkeypatch):
    """Env paths that are not the pinned release fail before any row is read."""

    _enforcement_or_skip()
    fake = tmp_path / "fake.csv"
    fake.write_text(MEMBERSHIP_HEADER + _member("acc-9", "txn-9", "cust-9"))
    fake_pub = tmp_path / "pub.json"
    fake_pub.write_text("{}")
    monkeypatch.setenv("EVAL_MEMBERSHIP", str(fake))
    monkeypatch.setenv("EVAL_PUBLICATION", str(fake_pub))
    with pytest.raises(Exception, match="differ|pinned"):
        eval_protection.apply_env(
            [{"account_id": "a"}], purpose="supervised_training"
        )


def test_apply_end_to_end(synthetic_release):
    enforcement, membership_path, publication_path = synthetic_release
    args = _Args(
        membership_path,
        publication_path,
        txncat_src=os.environ.get("RAYLO_TXNCAT_SRC"),
    )
    rows = [
        {"account_id": "acc-1", "transaction_id": "txn-1", "customer_id": "cust-1"},
        {"account_id": "acc-1", "transaction_id": "txn-9", "customer_id": "cust-1"},
        {"account_id": "acc-7", "transaction_id": "txn-7", "customer_id": "cust-2"},
        {"account_id": "acc-8", "transaction_id": "txn-8", "customer_id": "cust-8"},
    ]
    retained = eval_protection.apply(
        rows, args, purpose="supervised_training"
    )
    assert retained == [
        {"account_id": "acc-8", "transaction_id": "txn-8", "customer_id": "cust-8"}
    ]
    with pytest.raises(enforcement.ProtectedMembershipError):
        eval_protection.apply(
            [{"account_id": "", "transaction_id": "t", "customer_id": "c"}],
            args,
        )


def test_apply_rejects_relabelled_protected_rows(synthetic_release):
    _, membership_path, publication_path = synthetic_release
    args = _Args(
        membership_path,
        publication_path,
        txncat_src=os.environ.get("RAYLO_TXNCAT_SRC"),
    )
    relabelled = {
        "account_id": "acc-1",
        "transaction_id": "txn-1",
        "customer_id": "cust-1",
        "leaf": "groceries",
        "source": "relabelled-v9",
    }
    retained = eval_protection.apply([relabelled], args)
    assert retained == []


def test_assert_bound_rejects_multiple_memberships(synthetic_release, tmp_path):
    _, membership_path, publication_path = synthetic_release
    extra = tmp_path / "extra.csv"
    extra.write_text(membership_path.read_text())
    args = _Args(None, publication_path)
    with pytest.raises(ValueError, match="exactly one"):
        eval_protection.assert_bound([membership_path, extra], args)


def test_assert_bound_rejects_unpinned_membership(synthetic_release, tmp_path):
    _, _membership_path, publication_path = synthetic_release
    other = tmp_path / "other.csv"
    other.write_text(
        MEMBERSHIP_HEADER + _member("acc-9", "txn-9", "cust-9")
    )
    with pytest.raises(Exception, match="differ|pinned"):
        eval_protection.assert_bound(
            [other], _Args(None, publication_path)
        )


def test_verify_tuning_export_fails_closed(tmp_path):
    """No coverage or receipt -> the fit boundary refuses."""

    with pytest.raises(Exception):
        eval_protection.verify_tuning_export(out_dir=tmp_path)


def _guarded_fetch(synthetic_release, tmp_path, rows, monkeypatch):
    """Guard rows through the canonical guard and issue a real fetch receipt."""

    enforcement, membership_path, publication_path = synthetic_release
    binding = enforcement.ReleaseBinding(**eval_protection.PINNED_BINDING)
    monkeypatch.setattr(enforcement, "PINNED_RELEASE", binding)
    protection, publication = enforcement.verify_release(
        membership_path=membership_path,
        publication_path=publication_path,
        binding=binding,
    )
    retained, guard = enforcement.guard_batch(
        protection, publication, rows, purpose="supervised_training"
    )
    path = tmp_path / "txns.json"
    path.write_text(json.dumps(retained))
    receipt = enforcement.issue_fetch_receipt(
        result_path=path,
        rows=len(retained),
        binding=binding,
        guard=guard,
    )
    return path, receipt, protection


def _resign(enforcement, document):
    """Re-sign a tampered receipt so field-level checks (not signature) fire."""

    doc = dict(document)
    doc["signature"] = enforcement._sign_fields(
        {k: v for k, v in doc.items() if k != "signature"}
    )
    return doc


def test_verify_fetch_receipt_binding(synthetic_release, tmp_path, monkeypatch):
    enforcement, membership_path, _ = synthetic_release
    rows = [
        {"provider": "plaid", "account_id": "acc-8", "transaction_id": "txn-8",
         "customer_id": "cust-8", "merchant": "synthetic"}
    ]
    _path, good, _protection = _guarded_fetch(
        synthetic_release, tmp_path, rows, monkeypatch
    )
    eval_protection.verify_fetch_receipt(
        good, txncat_src=os.environ.get("RAYLO_TXNCAT_SRC")
    )
    # A minimal fabricated receipt — schema + membership digest only — fails.
    minimal = {
        "schema_version": "tuning-tier-b-fetch-receipt-v3",
        "anonymous_id_recovery": False,
        "eval_membership_inputs": [
            {"sha256": eval_protection.PINNED_BINDING["membership_sha256"]}
        ],
    }
    with pytest.raises(enforcement.ProtectedMembershipError):
        eval_protection.verify_fetch_receipt(
            minimal, txncat_src=os.environ.get("RAYLO_TXNCAT_SRC")
        )
    # Re-signed field tampering still fails strict validation.
    stale = _resign(
        enforcement,
        {**good, "eval_membership_inputs": [{"sha256": "1" * 64}]},
    )
    with pytest.raises(enforcement.ProtectedMembershipError):
        eval_protection.verify_fetch_receipt(
            stale, txncat_src=os.environ.get("RAYLO_TXNCAT_SRC")
        )
    # A caller-supplied alternate release binding is rejected outright.
    other = _resign(
        enforcement,
        {
            **good,
            "protected_release": {
                **good["protected_release"],
                "membership_sha256": "2" * 64,
            },
        },
    )
    with pytest.raises(enforcement.ProtectedMembershipError):
        eval_protection.verify_fetch_receipt(
            other, txncat_src=os.environ.get("RAYLO_TXNCAT_SRC")
        )


def _import(name):
    import importlib

    return importlib.import_module(name)


# Every gated-off consumer must raise the B04 block before touching data.
GATED_CALLS = [
    ("build_tail_eval", "fetch", ()),
    ("production_labelling", "fetch", (5,)),
    ("experiment3_xgb_pipeline", "fetch", ()),
    ("experiment3_xgb_pipeline", "train_capped", ()),
    ("experiment3_xgb_pipeline", "train_month12", ()),
    ("experiment3_xgb_pipeline", "train_live_analog", ()),
    ("experiment3_taxonomy_iv", "fetch", ()),
    ("experiment3_granularity_ladder", "aggregate", ()),
    ("experiment3_granularity_ladder", "train", ()),
    ("experiment3_subleaf_pilot", "aggregate", ()),
    ("experiment3_champion_model", "build_features", ()),
    ("experiment3_champion_model", "run_search", ()),
    ("experiment3_champion_model", "validate_artifacts", ()),
    ("experiment3_champion_capped", "run", ([],)),
    ("experiment3_champion_granularity", "build_all_rung_features", ()),
    ("audit_experiment3_granularity", "run", ([], 0)),
    ("audit_experiment3_granularity", "audit_same20", ([], 0)),
    # Identity-discarding and mixed-source fetches: gated off until rebuilt
    # against the customer-linked Plaid source.
    ("build_final_gold_v2", "fetch", ()),
    ("build_final_gold_v2_batch2", "fetch", ()),
    ("build_gold_v3_volume", "fetch", ()),
    ("build_gold_v4_slm_volume", "fetch", ()),
    ("build_gold_v5_locked", "fetch", ()),
    ("build_gold_v6_locked", "fetch", ()),
    ("build_tuning_leaf_topup", "fetch", ()),
    ("build_tuning_leaf_topup", "fetch_gap_fill", ([],)),
    ("build_equifax_fee_topup", "main", ()),
    ("ml_baseline", "fetch_train", ()),
    ("rent_iv_analysis", "fetch", ()),
    ("build_credit_tranche", "fetch_distil", ()),
    # Retired narrative-egress paths: inputs are unreceiptable pre-B04
    # artifacts, so these must terminate before any read or API call.
    ("build_tail_eval", "label", ("sonnet",)),
    ("gating_experiment", "fetch_ground_truth", ()),
    ("gating_experiment", "label_all", ("sonnet",)),
    ("score_frontier_vs_classifier", "main", ()),
]


@pytest.mark.parametrize(
    "module_name,func_name,call_args",
    GATED_CALLS,
    ids=[f"{m}.{f}" for m, f, _ in GATED_CALLS],
)
def test_gated_consumer_fails_closed(module_name, func_name, call_args):
    pytest.importorskip("pandas")
    module = _import(module_name)
    with pytest.raises(RuntimeError, match="B04 gated off"):
        getattr(module, func_name)(*call_args)


def test_transformer_corpus_gated():
    pytest.importorskip("pandas")
    sys.path.insert(0, str(ROOT / "src" / "transformer"))
    build_corpus = _import("build_corpus")
    with pytest.raises(RuntimeError, match="B04 gated off"):
        build_corpus.build_pretrain(1)
    with pytest.raises(RuntimeError, match="B04 gated off"):
        build_corpus.build_silver(1)


def test_distill_fit_boundaries_gated():
    pytest.importorskip("pandas")
    bakeoff = _import("distillation_bakeoff")
    # The distill parquet predates bound provenance: no artifact receipt
    # exists, so the fit boundary fails closed before .fit can run.
    with pytest.raises(RuntimeError, match="no bound artifact receipt"):
        bakeoff.train()
    with pytest.raises(RuntimeError, match="no bound artifact receipt"):
        bakeoff.retrain_lightgbm()


def test_pretrain_mlm_gated():
    pytest.importorskip("pandas")
    pytest.importorskip("torch")
    sys.path.insert(0, str(ROOT / "src" / "transformer"))
    pretrain_mlm = _import("pretrain_mlm")
    with pytest.raises(RuntimeError, match="B04 gated off"):
        pretrain_mlm.train(argparse_namespace())


def argparse_namespace():
    import argparse

    return argparse.Namespace(base="x", max_sentences=None)


def test_qwen_launchers_terminally_gated():
    """Every Qwen LoRA launcher must exit before doing any work."""

    import subprocess

    for name in (
        "qwen3_8b_cont.sh",
        "qwen3_8b_long.sh",
        "qwen3_after_4b.sh",
        "qwen3_score_then_8b.sh",
    ):
        script = ROOT / "scripts" / name
        assert "B04 RETIRED" in script.read_text()
        result = subprocess.run(
            ["bash", str(script)], capture_output=True, text=True, timeout=30
        )
        assert result.returncode == 1, name
        assert "RETIRED" in result.stderr, name


def test_unverified_llm_egress_fails_closed(tmp_path, monkeypatch):
    """label() must verify the sample's bound receipt before any API call."""

    module = _import("build_risk_leaf_topup")
    sample = tmp_path / "risk_leaf_topup_sample.csv"
    sample.write_text("row_id,merchant_raw\n1,synthetic\n")
    monkeypatch.setattr(module, "SAMPLE_CSV", sample)
    with pytest.raises(RuntimeError, match="no bound artifact receipt"):
        module.label("gemini")


def test_unverified_gap_fill_input_fails_closed(tmp_path, monkeypatch):
    """gap_fill must verify the existing merged artifact before reading it."""

    module = _import("build_risk_leaf_topup")
    final = tmp_path / "risk_leaf_topup.csv"
    final.write_text("merchant_raw,gold_leaf\nsynthetic,groceries\n")
    monkeypatch.setattr(module, "FINAL_CSV", final)
    with pytest.raises(RuntimeError, match="no bound artifact receipt"):
        module.gap_fill()


def test_apply_env_rejects_identity_less_rows(synthetic_release, monkeypatch):
    """A fetched row without linkage identity can never pass the guard."""

    _, membership_path, publication_path = synthetic_release
    monkeypatch.setenv("EVAL_MEMBERSHIP", str(membership_path))
    monkeypatch.setenv("EVAL_PUBLICATION", str(publication_path))
    enforcement = _enforcement_or_skip()
    with pytest.raises(
        enforcement.ProtectedMembershipError, match="missing linked identity"
    ):
        eval_protection.apply_env(
            [{"provider": "plaid", "account_id": "a",
              "transaction_id": "t", "customer_id": ""}],
            purpose="supervised_training",
        )


def test_verify_artifact_rejects_forged_sidecar(tmp_path, monkeypatch):
    """A hand-written sidecar beside an arbitrary file fails strict checks."""

    _enforcement_or_skip()
    artifact = tmp_path / "artifact.csv"
    artifact.write_text("merchant_raw\nsynthetic\n")
    forged = {
        "schema_version": "b04-artifact-receipt-v2",
        "consumer": "attacker",
        "purpose": "supervised_training",
        "anonymous_id_recovery": False,
        "eval_membership_inputs": [{"sha256": "0" * 64}],
        "protected_release": {},
        "output": str(artifact),
        "output_sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
        "guard": {},
        "input_receipts": [],
    }
    artifact.with_name(artifact.name + ".b04-receipt.json").write_text(
        json.dumps(forged)
    )
    with pytest.raises(Exception, match="receipt"):
        eval_protection.verify_artifact(artifact)


def test_locked_confirmation_set_refusal(tmp_path):
    """Locked sets refuse by name AND by bytes (a renamed copy stays locked)."""

    eval_sets = _import("eval_sets")
    fake_locked = tmp_path / "gold_transactions_v6_LOCKED.csv"
    fake_locked.write_text("merchant,leaf\nsynthetic,groceries\n")
    with pytest.raises(SystemExit, match="Refusing"):
        eval_sets.refuse_confirmation_eval(fake_locked)
    renamed = tmp_path / "totally_innocent.csv"
    renamed.write_bytes(fake_locked.read_bytes())
    import unittest.mock as mock

    with mock.patch.object(eval_sets, "V6_LOCKED", fake_locked), mock.patch.object(
        eval_sets, "V5_LOCKED", tmp_path / "missing.csv"
    ):
        with pytest.raises(SystemExit, match="Renaming does not unlock"):
            eval_sets.refuse_confirmation_eval(renamed)


def test_score_gold_v4_module_gate():
    """The retired v4 scorer must terminate at import, before any data read."""

    pytest.importorskip("pandas")
    with pytest.raises(RuntimeError, match="B04 gated off"):
        _import("score_gold_v4")


@pytest.mark.parametrize(
    "tool",
    [
        "annotation_pilot",
        "adjudicate_pilot_opus",
        "recover_gemini_annotation_batch",
    ],
)
def test_frozen_release_producer_tools_gated(tool):
    """The frozen pilot's annotation producers must not re-egress narratives."""

    import importlib.util

    sys.path.insert(0, str(ROOT / "tools" / "benchmark"))
    try:
        spec = importlib.util.spec_from_file_location(
            tool, ROOT / "tools" / "benchmark" / f"{tool}.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with pytest.raises(RuntimeError, match="B04 gated off"):
            module.main()
    finally:
        sys.path.remove(str(ROOT / "tools" / "benchmark"))


def test_verify_tuning_export_rejects_unsigned_coverage_substitute(
    synthetic_release, tmp_path, monkeypatch
):
    """R3 regression: a regenerated unsigned membership-coverage file can no
    longer authorise fit — bound train/val receipts are the trust anchor."""

    enforcement, membership_path, publication_path = synthetic_release
    binding = enforcement.ReleaseBinding(**eval_protection.PINNED_BINDING)
    monkeypatch.setattr(enforcement, "PINNED_RELEASE", binding)
    monkeypatch.setenv("EVAL_MEMBERSHIP", str(membership_path))
    monkeypatch.setenv("EVAL_PUBLICATION", str(publication_path))
    txncat_src = os.environ.get("RAYLO_TXNCAT_SRC")

    from training_membership import (
        TrackedExample,
        exact_plaid_membership,
        publish_training_export,
    )

    out_dir = tmp_path / "outputs"
    out_dir.mkdir()

    # Tier-B fetch: real guarded fetch receipts, one row per role so the
    # permanent identities never span train/selection.
    txn_train = {
        "provider": "plaid",
        "account_id": "acc-8",
        "transaction_id": "txn-8",
        "customer_id": "cust-8",
        "merchant": "synthetic",
        "target": "groceries",
    }
    txn_val = {
        "provider": "plaid",
        "account_id": "acc-9",
        "transaction_id": "txn-9",
        "customer_id": "cust-9",
        "merchant": "synthetic",
        "target": "groceries",
    }
    protection, publication = enforcement.verify_release(
        membership_path=membership_path,
        publication_path=publication_path,
        binding=binding,
    )
    retained, guard = enforcement.guard_batch(
        protection, publication, [txn_train, txn_val], purpose="supervised_training"
    )
    txns_path = out_dir / "tuning_txns.json"
    txns_path.write_text(json.dumps(retained))
    fetch_receipt = enforcement.issue_fetch_receipt(
        result_path=txns_path,
        rows=len(retained),
        binding=binding,
        guard=guard,
    )
    (out_dir / "tuning_txns_receipt.json").write_text(
        json.dumps(fetch_receipt, indent=2)
    )

    # train/val exports via the real publisher → real coverage+lookup.
    train_example = TrackedExample(
        messages={"messages": [{"role": "user", "content": "x"}]},
        membership=exact_plaid_membership(
            source="tier_b_customer_linked_plaid", row=txn_train
        ),
    )
    val_example = TrackedExample(
        messages={"messages": [{"role": "user", "content": "y"}]},
        membership=exact_plaid_membership(
            source="tier_b_customer_linked_plaid", row=txn_val
        ),
    )
    publish_training_export(
        [train_example],
        [val_example],
        train_path=out_dir / "tuning_train.jsonl",
        selection_path=out_dir / "tuning_val.jsonl",
        lookup_path=out_dir / "tuning_membership_lookup.csv",
        coverage_path=out_dir / "tuning_membership_coverage.json",
    )

    # Unsigned coverage alone cannot authorise the export — the receipts
    # are missing, so the boundary fails closed.
    with pytest.raises(RuntimeError, match="no bound artifact receipt"):
        eval_protection.verify_tuning_export(
            out_dir=out_dir, txncat_src=txncat_src
        )

    # Bound receipts + manifests complete the chain; fit verifies.
    def _manifest(txn):
        return [
            {
                "identity": {
                    "provider": "plaid",
                    "account_id": txn["account_id"],
                    "transaction_id": txn["transaction_id"],
                    "customer_id": txn["customer_id"],
                },
                "provenance": {
                    "source": "tier_b_customer_linked_plaid",
                    "source_row_sha256": enforcement.sha256(
                        enforcement.canonical_json(dict(txn))
                    ),
                },
            }
        ]

    for name, txn, purpose in (
        ("tuning_train.jsonl", txn_train, "supervised_training"),
        ("tuning_val.jsonl", txn_val, "model_selection_validation"),
    ):
        eval_protection.write_artifact_receipt(
            out_dir / name,
            consumer="build_tuning_dataset",
            purpose=purpose,
            input_receipts=[fetch_receipt],
            manifest_identities=_manifest(txn),
        )
    coverage = eval_protection.verify_tuning_export(
        out_dir=out_dir, txncat_src=txncat_src
    )
    assert coverage["model_files"]["train"]["rows"] == 1


def test_transformer_export_build_to_promotion_chain(
    synthetic_release, tmp_path, monkeypatch
):
    """R3 regression: the supported transformer export's bound receipts pass
    both the fit boundary and the promotion boundary end to end."""

    enforcement, membership_path, publication_path = synthetic_release
    binding = enforcement.ReleaseBinding(**eval_protection.PINNED_BINDING)
    monkeypatch.setattr(enforcement, "PINNED_RELEASE", binding)
    monkeypatch.setenv("EVAL_MEMBERSHIP", str(membership_path))
    monkeypatch.setenv("EVAL_PUBLICATION", str(publication_path))
    txncat_src = os.environ.get("RAYLO_TXNCAT_SRC")

    from training_membership import (
        TrackedExample,
        exact_plaid_membership,
        publish_training_export,
        unavailable_membership,
    )

    out_dir = tmp_path / "outputs"
    out_dir.mkdir()
    protection, publication = enforcement.verify_release(
        membership_path=membership_path,
        publication_path=publication_path,
        binding=binding,
    )

    # ---- Tier-B fetch: guarded rows + bound fetch receipt ----
    txn = {
        "provider": "plaid",
        "account_id": "acc-8",
        "transaction_id": "txn-8",
        "customer_id": "cust-8",
        "merchant": "synthetic",
        "target": "groceries",
    }
    retained, guard = enforcement.guard_batch(
        protection, publication, [txn], purpose="supervised_training"
    )
    txns_path = out_dir / "tuning_txns.json"
    txns_path.write_text(json.dumps(retained))
    fetch_receipt = enforcement.issue_fetch_receipt(
        result_path=txns_path,
        rows=len(retained),
        binding=binding,
        guard=guard,
    )
    (out_dir / "tuning_txns_receipt.json").write_text(
        json.dumps(fetch_receipt, indent=2)
    )

    # ---- Tier-A gold: a derived artifact resolving to the fetch ----
    gold_row = {
        "source": "v2",
        "role": "train",
        "merchant_raw": "synthetic",
        "description_raw": "coffee",
        "amount": "3.50",
        "direction": "debit",
        "provider": "",
        "native_category": "",
        "gold_leaf": "groceries",
        "notes": "",
    }
    gold_path = out_dir / "gold_transactions.csv"
    import csv as _csv

    with gold_path.open("w", newline="") as stream:
        writer = _csv.DictWriter(stream, fieldnames=list(gold_row))
        writer.writeheader()
        writer.writerow(gold_row)
    eval_protection.write_artifact_receipt(
        gold_path,
        consumer="build_gold_transactions_unified",
        purpose="model_selection_validation",
        input_receipts=[fetch_receipt],
        manifest_identities=[
            {
                "identity": None,
                "provenance": {
                    "source": "v2",
                    "source_row_sha256": enforcement.sha256(
                        enforcement.canonical_json(dict(txn))
                    ),
                },
            }
        ],
    )
    gold_receipt = json.loads(
        (out_dir / "gold_transactions.csv.b04-receipt.json").read_text()
    )

    # ---- Final exports: bound receipts + manifests over both inputs ----
    train_example = TrackedExample(
        messages={"messages": [{"role": "user", "content": "x"}]},
        membership=exact_plaid_membership(
            source="tier_b_customer_linked_plaid", row=txn
        ),
    )
    val_example = TrackedExample(
        messages={"messages": [{"role": "user", "content": "y"}]},
        membership=unavailable_membership(
            source="tier_a_gold_transactions", row=gold_row, provider="plaid"
        ),
    )
    publish_training_export(
        [train_example],
        [val_example],
        train_path=out_dir / "tuning_train.jsonl",
        selection_path=out_dir / "tuning_val.jsonl",
        lookup_path=out_dir / "tuning_membership_lookup.csv",
        coverage_path=out_dir / "tuning_membership_coverage.json",
    )
    input_receipts = [fetch_receipt, gold_receipt]
    for name, example, purpose in (
        ("tuning_train.jsonl", train_example, "supervised_training"),
        ("tuning_val.jsonl", val_example, "model_selection_validation"),
    ):
        membership = example.membership
        identity = None
        if membership.identity_status == "exact":
            identity = {
                "provider": membership.provider,
                "account_id": membership.account_id,
                "transaction_id": membership.transaction_id,
                "customer_id": membership.customer_id,
            }
        source_row = txn if membership.identity_status == "exact" else gold_row
        eval_protection.write_artifact_receipt(
            out_dir / name,
            consumer="build_tuning_dataset",
            purpose=purpose,
            input_receipts=input_receipts,
            manifest_identities=[
                {
                    "identity": identity,
                    "provenance": {
                        "source": membership.source,
                        "source_row_sha256": enforcement.sha256(
                            enforcement.canonical_json(dict(source_row))
                        ),
                    },
                }
            ],
        )

    # ---- Fit boundary ----
    coverage = eval_protection.verify_tuning_export(
        out_dir=out_dir, txncat_src=txncat_src
    )
    assert coverage["model_files"]["train"]["rows"] == 1

    # ---- Promotion boundary: the same receipts must satisfy exact-set
    # coverage, manifest order/identity checks and provenance resolution.
    train_path = out_dir / "tuning_train.jsonl"
    val_path = out_dir / "tuning_val.jsonl"
    train_receipt = json.loads(
        (out_dir / "tuning_train.jsonl.b04-receipt.json").read_text()
    )
    val_receipt = json.loads(
        (out_dir / "tuning_val.jsonl.b04-receipt.json").read_text()
    )
    result = enforcement.require_promotion_provenance(
        membership_path=membership_path,
        publication_path=publication_path,
        learning_inputs=[train_path, val_path],
        artifact_receipts=[train_receipt, val_receipt],
        bundle_provenance={
            "training_inputs": [
                {
                    "path": "outputs/tuning_train.jsonl",
                    "sha256": hashlib.sha256(train_path.read_bytes()).hexdigest(),
                },
                {
                    "path": "outputs/tuning_val.jsonl",
                    "sha256": hashlib.sha256(val_path.read_bytes()).hexdigest(),
                },
            ]
        },
        binding=binding,
    )
    assert result == {"learning_inputs": 2, "covered_digests": 2}

    # A re-signed-but-misbound manifest (reordered claims) fails promotion.
    tampered_manifest = out_dir / "tuning_train.jsonl.b04-manifest.json"
    document = json.loads(tampered_manifest.read_text())
    document["rows"][0]["identity"]["customer_id"] = "cust-9"
    tampered_manifest.write_text(json.dumps(document))
    with pytest.raises(enforcement.ProtectedMembershipError):
        enforcement.require_promotion_provenance(
            membership_path=membership_path,
            publication_path=publication_path,
            learning_inputs=[train_path, val_path],
            artifact_receipts=[train_receipt, val_receipt],
            binding=binding,
        )

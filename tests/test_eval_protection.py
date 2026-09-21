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


def test_verify_fetch_receipt_binding(synthetic_release):
    enforcement, membership_path, _ = synthetic_release
    membership_sha = eval_protection.PINNED_BINDING["membership_sha256"]
    good = {
        "schema_version": "tuning-tier-b-fetch-receipt-v1",
        "anonymous_id_recovery": False,
        "eval_membership_inputs": [{"sha256": membership_sha, "rows": 3}],
    }
    eval_protection.verify_fetch_receipt(
        good, txncat_src=os.environ.get("RAYLO_TXNCAT_SRC")
    )
    stale = {**good, "eval_membership_inputs": [{"sha256": "1" * 64, "rows": 3}]}
    with pytest.raises(enforcement.ProtectedMembershipError):
        eval_protection.verify_fetch_receipt(
            stale, txncat_src=os.environ.get("RAYLO_TXNCAT_SRC")
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

"""TxCat-1 retrain guards (2026-09-23): identity recovery and stage-1 consumption.

Synthetic rows only.
"""

import csv
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src" / "transformer"))

pd = pytest.importorskip("pandas")
pytest.importorskip("google.cloud.bigquery")
import recover_training_identity as rti  # noqa: E402

FIELDS = ["merchant_raw", "description_raw", "amount", "direction", "transaction_date",
          "gold_leaf"]


def _index(rows):
    df = pd.DataFrame(
        rows,
        columns=["account_id", "transaction_id", "customer_id", "merchant_raw",
                 "description_raw", "amount", "transaction_date", "drop_reason"],
    )
    df["amount_2dp"] = [rti._money(a) for a in df["amount"]]
    df["abs_2dp"] = [rti._money(abs(float(a))) for a in df["amount"]]
    df["direction"] = ["credit" if float(a) < 0 else "debit" for a in df["amount"]]
    return df


def _labels(tmp_path, rows):
    path = tmp_path / "labels.csv"
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _row(merchant, amount="-10.00", date="2026-01-02"):
    return {"merchant_raw": merchant, "description_raw": "PAYMENT", "amount": amount,
            "direction": "credit", "transaction_date": date, "gold_leaf": "refund_received"}


def test_recovery_keeps_unique_clean_matches_and_same_customer_repeats(tmp_path):
    index = _index(
        [
            ("acc-1", "t-1", "cust-1", "Alpha", "PAYMENT", -10.0, "2026-01-02", None),
            # the same transaction in two reports for one customer
            ("acc-2", "t-2", "cust-2", "Beta", "PAYMENT", -10.0, "2026-01-02", None),
            ("acc-3", "t-3", "cust-2", "Beta", "PAYMENT", -10.0, "2026-01-02", None),
        ]
    )
    recovered, outcomes, total = rti.recover(
        "tuning_credit_topup", _labels(tmp_path, [_row("Alpha"), _row("Beta")]), index
    )
    assert total == 2
    assert outcomes == {"recovered": 2, "recovered_repeated_same_customer": 1}
    assert [(r["account_id"], r["customer_id"]) for r in recovered] == [
        ("acc-1", "cust-1"),
        ("acc-2", "cust-2"),
    ]


@pytest.mark.parametrize(
    ("index_rows", "reason"),
    [
        ([("a", "t", None, "Alpha", "PAYMENT", -10.0, "2026-01-02", "unlinked_customer")],
         "dropped_unlinked_customer"),
        ([("a", "t", "c", "Alpha", "PAYMENT", -10.0, "2026-01-02", "protected_customer")],
         "dropped_protected_customer"),
        ([("a", "t", "c1", "Alpha", "PAYMENT", -10.0, "2026-01-02", None),
          ("b", "u", "c2", "Alpha", "PAYMENT", -10.0, "2026-01-02", None)], "ambiguous_match"),
        ([("a", "t", "c1", "Alpha", "PAYMENT", -10.0, "2026-01-02", None),
          ("b", "u", "c1", "Alpha", "PAYMENT", -10.0, "2026-01-02", "protected_account")],
         "ambiguous_match"),
        ([("a", "t", "c1", "Alpha", "PAYMENT", -10.0, "2026-01-03", None)], "unmatched"),
    ],
)
def test_recovery_fails_closed(tmp_path, index_rows, reason):
    recovered, outcomes, _ = rti.recover(
        "tuning_credit_topup", _labels(tmp_path, [_row("Alpha")]), _index(index_rows)
    )
    assert recovered == []
    assert outcomes == {reason: 1}


def test_stage_one_refuses_an_unreceipted_consensus_parquet(tmp_path):
    pytest.importorskip("torch")
    import train_classifier  # noqa: PLC0415

    path = tmp_path / "distillation_labels_consensus.parquet"
    pd.DataFrame({"merchant_raw": ["a"], "description_raw": ["b"], "direction": ["debit"],
                  "amount": [1.0], "final_leaf": ["groceries"]}).to_parquet(path)
    with pytest.raises(RuntimeError, match="no bound artifact receipt"):
        train_classifier.silver_frame(path)

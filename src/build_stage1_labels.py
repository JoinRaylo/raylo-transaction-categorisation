"""Stage-1 labels for the TxCat-1 retrain: consensus plus rule-labelled texts.

Carlos's decision (2026-09-23): the stage-1 set should be topped up with rows
labelled for free by the staging bundle's rules, so it is no smaller than
before.  This builds one guarded stage-1 parquet from two sources:

- **Consensus labels.**  The ID-recovered consensus labels from
  ``recover_identity_linked.py`` (v2 inputs).
- **Rule-labelled texts.**  Distinct (merchant, description, direction) texts
  from clean rows in the 39M-row customer-linked Plaid source, which carry the
  same protected-release flags as the guarded pretraining corpus.  They are
  labelled by the pinned staging waterfall, and only texts T1-T5 decides are
  kept, at most ``--per-leaf-cap`` per leaf.

The excluded texts mirror the original consensus fetch:
- texts already carrying a consensus label;
- protected benchmark texts;
- frozen-holdout and risk-gold merchants;
- the exact texts of every gold evaluation file.

The combined rows pass the canonical gate (``distillation``) and are
receipted; ``train_classifier.silver_frame`` verifies that receipt.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import pathlib
import sys
from collections import Counter

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src" / "transformer"))

import eval_protection  # noqa: E402
from build_corpus import _run  # noqa: E402
from build_pretrain_guarded import PLAID_LINKED_FLAGGED, protected_texts, verify_protected_table  # noqa: E402

CONSUMER = "build_stage1_labels"
PURPOSE = "distillation"
INPUTS = ROOT / "outputs" / "retrain_inputs_v2"
_NATIVE = "  SELECT TRIM(i.account_id) AS account_id, TRIM(i.transaction_id) AS transaction_id,"
if PLAID_LINKED_FLAGGED.count(_NATIVE) != 1:
    raise RuntimeError("linked Plaid SQL shape changed; refusing to patch it blindly")
# A local copy that also carries the provider category the waterfall uses.  The
# shared constant is unchanged, because its hash is in the pretraining manifest.
_LINKED_WITH_NATIVE = PLAID_LINKED_FLAGGED.replace(
    _NATIVE, _NATIVE + "\n         i.detailed_credit_category AS native,"
)
TEXTS_SQL = _LINKED_WITH_NATIVE + """
SELECT merchant, description, direction,
       ANY_VALUE(native) AS native_category, APPROX_QUANTILES(a, 2)[OFFSET(1)] AS amount,
       COUNT(*) AS n,
       ARRAY_AGG(STRUCT(account_id, transaction_id, customer_id)
                 ORDER BY FARM_FINGERPRINT(CONCAT(account_id, ':', transaction_id)) LIMIT 1
                )[OFFSET(0)] AS rep
FROM (SELECT * FROM flagged WHERE drop_reason IS NULL)
GROUP BY 1, 2, 3
HAVING MOD(ABS(FARM_FINGERPRINT(CONCAT(merchant, '|', description, '|', direction))), 1000)
       < __KEEP_PER_THOUSAND__
"""


def _norm(s) -> str:
    return (s or "").strip().lower()


def eval_exclusions() -> tuple[set[str], set[str]]:
    import build_tuning_dataset as btd  # noqa: PLC0415
    from eval_sets import _V6_GOLD_FILES  # noqa: PLC0415

    merchants = btd.frozen_holdout_merchants() | btd.load_risk_merchants()
    texts = set()
    for name in [*_V6_GOLD_FILES, "gold_v2_slm_eval_holdout.csv",
                 "gold_transactions_risk_categories.csv"]:
        path = ROOT / "data" / name
        if not path.exists():
            continue
        with path.open(newline="", encoding="utf-8") as stream:
            for row in csv.DictReader(stream):
                if "description_raw" in row:
                    texts.add(_norm(row.get("merchant_raw")) + "||" + _norm(row["description_raw"]))
    return merchants, texts


def main() -> None:
    parser = eval_protection.add_args(argparse.ArgumentParser(description=__doc__))
    parser.add_argument("--rules-root", type=pathlib.Path, required=True)
    parser.add_argument("--per-leaf-cap", type=int, default=10_000)
    parser.add_argument("--keep-per-thousand", type=int, default=250)
    parser.add_argument("--output", type=pathlib.Path, default=INPUTS / "stage1_labels.parquet")
    args = parser.parse_args()
    protection, _publication = eval_protection.load_release(args)
    table_check = verify_protected_table(protection)
    from build_tuning_dataset_retrain import label  # noqa: PLC0415

    consensus = pd.read_parquet(INPUTS / "distillation_labels_consensus.parquet")
    eval_protection.verify_artifact(
        INPUTS / "distillation_labels_consensus.parquet",
        expected_consumer="recover_training_identity",
        expected_purpose=PURPOSE,
        protection=protection,
    )
    consensus["label_source"] = "consensus"
    have = set(zip(consensus.direction, consensus.merchant, consensus.description))
    blocked_texts = protected_texts()
    eval_merchants, eval_texts = eval_exclusions()

    candidates = _run(TEXTS_SQL.replace("__KEEP_PER_THOUSAND__", str(int(args.keep_per_thousand))),
                      "stage1/linked-texts")
    outcomes = Counter()
    pool = []
    for row in candidates.to_dict("records"):
        key = (row["direction"], row["merchant"], row["description"])
        if key in have:
            outcomes["already_consensus"] += 1
        elif key in blocked_texts:
            outcomes["protected_text"] += 1
        elif row["merchant"] in eval_merchants:
            outcomes["eval_merchant"] += 1
        elif row["merchant"] + "||" + row["description"] in eval_texts:
            outcomes["eval_text"] += 1
        else:
            pool.append(row)
    labels = label(
        [{"merchant": r["merchant"], "description": r["description"],
          "is_credit": 1 if r["direction"] == "credit" else 0,
          "native_category": r["native_category"]} for r in pool],
        args.rules_root,
    )
    per_leaf: Counter = Counter()
    ranked = sorted(
        zip(pool, labels, strict=True),
        key=lambda pair: hashlib.sha256(
            "|".join((pair[0]["direction"], pair[0]["merchant"], pair[0]["description"])).encode()
        ).hexdigest(),
    )
    rule_rows = []
    for row, lab in ranked:
        if lab["leaf"] is None:
            outcomes["not_rule_decided"] += 1
            continue
        if per_leaf[lab["leaf"]] >= args.per_leaf_cap:
            outcomes["over_leaf_cap"] += 1
            continue
        per_leaf[lab["leaf"]] += 1
        rep = row["rep"]
        rule_rows.append({
            "merchant": row["merchant"], "description": row["description"],
            "direction": row["direction"], "merchant_raw": row["merchant"],
            "description_raw": row["description"], "amount": float(row["amount"]),
            "native_category": row["native_category"], "n": int(row["n"]),
            "provider": "plaid", "final_leaf": lab["leaf"], "tier": lab["tier"],
            "label_source": "staging_rules", "account_id": rep["account_id"],
            "transaction_id": rep["transaction_id"], "customer_id": rep["customer_id"],
        })
    outcomes["rule_labelled_kept"] = len(rule_rows)
    columns = ["merchant", "description", "direction", "merchant_raw", "description_raw",
               "amount", "native_category", "n", "provider", "final_leaf", "tier",
               "label_source", "account_id", "transaction_id", "customer_id"]
    combined = pd.concat([consensus.reindex(columns=columns), pd.DataFrame(rule_rows, columns=columns)],
                         ignore_index=True)
    seen, rows = set(), []
    for row in combined.to_dict("records"):
        event = (row["account_id"], row["transaction_id"])
        if event in seen:
            outcomes["duplicate_representative_dropped"] += 1
            continue
        seen.add(event)
        rows.append(row)
    customers: dict[str, set] = {}
    for row in rows:
        customers.setdefault(row["account_id"], set()).add(row["customer_id"])
    ambiguous = {a for a, c in customers.items() if len(c) > 1}
    outcomes["ambiguous_account_rows_dropped"] = sum(r["account_id"] in ambiguous for r in rows)
    rows = [r for r in rows if r["account_id"] not in ambiguous]
    guarded = eval_protection.apply(rows, args, purpose=PURPOSE)
    if len(guarded) != len(rows):
        raise RuntimeError("stage 1: the gate excluded rows the linked flags kept; stopping")
    out = args.output
    pd.DataFrame(list(guarded)).to_parquet(out, index=False)
    os.chmod(out, 0o600)
    receipt = eval_protection.write_artifact_receipt(
        out, consumer=CONSUMER, purpose=PURPOSE, guard=guarded.guard
    )
    final = pd.read_parquet(out)
    summary = {
        "schema_version": "retrain-stage1-labels-v1",
        "protected_table_check": table_check,
        "outcomes": dict(outcomes),
        "rows": len(final),
        "by_label_source": final.label_source.value_counts().to_dict(),
        "credit_rows": int((final.direction == "credit").sum()),
        "distinct_leaves": int(final.final_leaf.nunique()),
        "per_leaf_cap": args.per_leaf_cap,
        "keep_per_thousand": args.keep_per_thousand,
        "receipt": receipt.name,
    }
    (out.parent / "stage1_labels_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()

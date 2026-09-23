"""TxCat-1 retrain (2026-09): guarded Tier-B fetch labelled by the pinned rules.

This implements the frozen acceptance plan
(``docs/txncat1-retrain-2026-09/ACCEPTANCE_PLAN.md``).

- **Eligible merchants.**  Tier-B merchants are the T4-eligible dictionary
  merchants.  Gold-set, Tier-A, risk-gold and frozen-holdout merchants are
  excluded, so the registered sets stay merchant-disjoint evaluations.
- **Fetch.**  Transactions come from the approved customer-linked Plaid chain
  with provider IDs.  Protected rows are excluded, and the rows are written
  through the canonical guard with a signed fetch receipt
  (``write_tier_b_fetch``).
- **Labels.**  Each row is labelled by the staging bundle's own waterfall
  (``--rules-root``, research ``f0afb9f``).  Only rows T1-T5 decides are kept,
  and they take the rule's leaf (decision 2).  The old merchant-label file
  cannot be receipted, and the serving dictionary was derived from it anyway.
"""

from __future__ import annotations

import argparse
import csv
import json
import pathlib
import subprocess
import sys
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import build_tuning_dataset as btd  # noqa: E402
import eval_protection  # noqa: E402

OUT = ROOT / "outputs" / "retrain_inputs"
TXNS = OUT / "tier_b_txns.json"
TXNS_RECEIPT = OUT / "tier_b_txns_receipt.json"
CHUNK = 1500


def tier_b_query(merchants: list[str], cap: int) -> str:
    """The approved linked chain, plus the provider category the waterfall needs."""

    base = btd.build_linked_tier_b_query(merchants, cap)
    base = base.replace(
        "    ROUND(ABS(amount), 2) AS amount,\n    CAST(amount < 0 AS INT64) AS is_credit,\n"
        "    TO_HEX(",
        "    ROUND(ABS(amount), 2) AS amount,\n    CAST(amount < 0 AS INT64) AS is_credit,\n"
        "    detailed_credit_category AS native_category,\n    TO_HEX(",
        1,
    )
    base = base.replace(
        "STRUCT(customer_id, merchant, description, amount, is_credit, payload_sha256)",
        "STRUCT(customer_id, merchant, description, amount, is_credit, native_category, "
        "payload_sha256)",
        1,
    )
    base = base.replace(
        "  chosen.is_credit AS is_credit,\n",
        "  chosen.is_credit AS is_credit,\n  chosen.native_category AS native_category,\n",
        1,
    )
    if base.count("native_category") != 4:
        raise RuntimeError("linked Tier-B query shape changed; refusing to patch it blindly")
    return base


def excluded_merchants() -> set[str]:
    out = set()
    for path in [*btd.GOLD_V1_FILES, btd.GOLD_TXN_FILE]:
        key = "merchant" if path in btd.GOLD_V1_FILES else "merchant_raw"
        with open(path, newline="", encoding="utf-8") as stream:
            out |= {btd._norm(r[key]) for r in csv.DictReader(stream)}
    return out | btd.load_risk_merchants() | btd.frozen_holdout_merchants()


def label(rows: list[dict], rules_root: pathlib.Path) -> list[dict]:
    payload = "".join(
        json.dumps(
            {
                "key": i,
                "merchant": r["merchant"],
                "description": r["description"],
                "direction": "credit" if int(r["is_credit"]) else "debit",
                "native": r.get("native_category"),
            }
        )
        + "\n"
        for i, r in enumerate(rows)
    )
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "src" / "label_with_pinned_waterfall.py"),
            "--research-root",
            str(rules_root),
        ],
        input=payload,
        capture_output=True,
        text=True,
        check=True,
    )
    return [json.loads(line) for line in result.stdout.splitlines()]


def fetch(args) -> None:
    if len(args.protected_membership) != 1:
        raise SystemExit("pass exactly the pinned protected membership")
    eval_protection.assert_bound(args.protected_membership, args)
    protection = btd.load_eval_protection(args.protected_membership)
    sys.path.insert(0, str(ROOT / "src"))
    from final_evaluation import load_dictionary  # noqa: PLC0415

    dictionary = load_dictionary()
    blocked = excluded_merchants()
    merchants = sorted(m for m in dictionary if m and m not in blocked)
    print(
        f"{len(dictionary):,} dictionary merchants -> {len(merchants):,} eligible "
        f"after {len(blocked):,} gold/risk/holdout merchant exclusions",
        file=sys.stderr,
    )
    rows = []
    for i in range(0, len(merchants), CHUNK):
        rows += btd.bq_json(tier_b_query(merchants[i : i + CHUNK], args.cap))
        print(f"chunk {i // CHUNK + 1}: {len(rows):,} rows so far", file=sys.stderr)
    labels = label(rows, args.rules_root)
    tiers = Counter((lab["tier"] or "none").split("_")[0] for lab in labels)
    kept = []
    for row, lab in zip(rows, labels, strict=True):
        if lab["leaf"] is None:
            continue
        kept.append({**row, "target": lab["leaf"], "rule_tier": lab["tier"]})
    kept, excluded = btd.exclude_eval_membership(kept, protection)
    OUT.mkdir(parents=True, exist_ok=True)
    guard_args = argparse.Namespace(
        protected_membership=args.protected_membership[0],
        protected_publication=args.protected_publication,
        txncat_src=args.txncat_src,
    )
    btd.write_tier_b_fetch(
        kept, protection, args=guard_args, data_path=TXNS, receipt_path=TXNS_RECEIPT
    )
    summary = {
        "schema_version": "retrain-tier-b-fetch-v1",
        "rules_root": str(args.rules_root),
        "eligible_merchants": len(merchants),
        "fetched_rows": len(rows),
        "rule_tier_counts": dict(tiers),
        "kept_rule_decided_rows": len(kept),
        "eval_protection_excluded": dict(excluded),
        "cap_per_merchant": args.cap,
    }
    (OUT / "tier_b_fetch_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=1))


EXPORT = ROOT / "outputs" / "retrain_export"
TOPUPS = {
    "tuning_leaf_topup": OUT / "tuning_leaf_topup.csv",
    "tuning_credit_topup": OUT / "tuning_credit_topup.csv",
    "tuning_risk_topup": OUT / "tuning_risk_topup.csv",
}


def _set_inputs(inputs: pathlib.Path | None) -> None:
    """Point fetch/build at another inputs directory (and a matching export)."""

    global OUT, TXNS, TXNS_RECEIPT, EXPORT, TOPUPS, RULE_CREDITS_PATH
    if inputs is None:
        return
    OUT = inputs.resolve()
    TXNS, TXNS_RECEIPT = OUT / "tier_b_txns.json", OUT / "tier_b_txns_receipt.json"
    EXPORT = OUT.parent / (OUT.name.replace("retrain_inputs", "retrain_export") or "export")
    TOPUPS = {name: OUT / f"{name}.csv" for name in TOPUPS}
    RULE_CREDITS_PATH = OUT / "rule_credit_topup.csv"
    if RULE_CREDITS_PATH.exists():
        TOPUPS["rule_credit_topup"] = RULE_CREDITS_PATH


RULE_CREDITS_PATH = OUT / "rule_credit_topup.csv"


def credits(args) -> None:
    """Free rule-labelled credit top-up (Carlos, 2026-09-23: credits >= 5% of stage 2).

    Row-level credit transactions from clean rows of the 39M-row customer-linked
    Plaid source.  The rows carry the same protected-release flags as the
    guarded pretraining corpus.  They are labelled by the pinned staging
    waterfall; only rows T1-T5 decides are kept, at most ``--per-leaf-cap`` per
    leaf and ``--target`` in total, ranked by a deterministic hash.  The gate
    guards and receipts them, and ``build`` applies the same merchant and
    evaluation-text screens as for every other source.
    """

    sys.path.insert(0, str(ROOT / "src" / "transformer"))
    from build_corpus import _run  # noqa: PLC0415
    from build_stage1_labels import _LINKED_WITH_NATIVE  # noqa: PLC0415
    from build_pretrain_guarded import verify_protected_table  # noqa: PLC0415

    guard_args = argparse.Namespace(
        protected_membership=args.protected_membership[0],
        protected_publication=args.protected_publication,
        txncat_src=args.txncat_src,
    )
    protection, _publication = eval_protection.load_release(guard_args)
    verify_protected_table(protection)
    sql = _LINKED_WITH_NATIVE + f"""
SELECT account_id, transaction_id, customer_id, merchant AS merchant_raw,
       description AS description_raw, -a AS amount, 'credit' AS direction,
       native AS native_category
FROM flagged
WHERE drop_reason IS NULL AND direction = 'credit'
  AND MOD(ABS(FARM_FINGERPRINT(CONCAT(account_id, ':', transaction_id))), 1000)
      < {int(args.keep_per_thousand)}
"""
    rows = _run(sql, "rule-credits/linked").to_dict("records")
    labels = label(
        [{"merchant": r["merchant_raw"], "description": r["description_raw"], "is_credit": 1,
          "native_category": r["native_category"]} for r in rows],
        args.rules_root,
    )
    import hashlib  # noqa: PLC0415

    ranked = sorted(
        zip(rows, labels, strict=True),
        key=lambda pair: hashlib.sha256(
            f"{pair[0]['account_id']}:{pair[0]['transaction_id']}".encode()
        ).hexdigest(),
    )
    per_leaf, kept, outcomes, accounts = Counter(), [], Counter(), {}
    for row, lab in ranked:
        if lab["leaf"] is None:
            outcomes["not_rule_decided"] += 1
            continue
        if per_leaf[lab["leaf"]] >= args.per_leaf_cap:
            outcomes["over_leaf_cap"] += 1
            continue
        if accounts.setdefault(row["account_id"], row["customer_id"]) != row["customer_id"]:
            outcomes["account_customer_conflict"] += 1
            continue
        per_leaf[lab["leaf"]] += 1
        kept.append({**{k: ("" if v is None else str(v)) for k, v in row.items()},
                     "provider": "plaid", "gold_leaf": lab["leaf"], "rule_tier": lab["tier"],
                     "resolution_source": "staging_rules"})
        if len(kept) >= args.target:
            break
    guarded = eval_protection.apply(kept, guard_args, purpose="supervised_training")
    if len(guarded) != len(kept):
        raise RuntimeError("rule credits: the gate excluded rows the linked flags kept; stopping")
    with RULE_CREDITS_PATH.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(kept[0].keys()))
        writer.writeheader()
        writer.writerows(guarded)
    RULE_CREDITS_PATH.chmod(0o600)
    receipt = eval_protection.write_artifact_receipt(
        RULE_CREDITS_PATH, consumer="build_tuning_dataset_retrain.credits",
        purpose="supervised_training", guard=guarded.guard,
    )
    summary = {"sampled_credit_rows": len(rows), "kept": len(guarded),
               "distinct_leaves": len(per_leaf), "outcomes": dict(outcomes),
               "per_leaf_cap": args.per_leaf_cap, "target": args.target,
               "receipt": receipt.name}
    (OUT / "rule_credit_topup_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=1))


def _human(row: dict) -> bool:
    """Carlos's own labels and remaps are human; LLM/agent consensus is not."""

    source = (row.get("resolution_source") or "").lower()
    return source.startswith("carlos") or bool((row.get("reviewer_id") or "").strip())


def build(args) -> None:
    """Assemble the retrain export under the frozen acceptance plan.

    - Tier B: the guarded fetch.  Targets are already the pinned rules' leaves.
    - Tier A: dropped (decision 1).
    - Top-ups: the ID-recovered files.  Conventions apply to every row.  Where
      T1-T5 decides, a non-human label takes the rule's leaf; a human label is
      kept and the conflict is listed (decision 2).
    - Oversampling, the merchant-disjoint split and the export format follow
      ``build_tuning_dataset.build``.  Every final row resolves to an exact
      identity through the signed manifests.
    """

    from raylo_txncat import label_conventions as conventions  # noqa: PLC0415
    from training_membership import (  # noqa: PLC0415
        TrackedExample,
        canonical_sha256,
        exact_plaid_membership,
        publish_training_export,
    )

    if len(args.protected_membership) != 1:
        raise SystemExit("pass exactly the pinned protected membership")
    eval_protection.assert_bound(args.protected_membership, args)
    guard_args = argparse.Namespace(
        protected_membership=args.protected_membership[0],
        protected_publication=args.protected_publication,
        txncat_src=args.txncat_src,
    )
    protection, _publication = eval_protection.load_release(guard_args)
    _, _, leaves, _, _ = btd.load_crosswalk()
    system_prompt = btd.build_system_prompt(leaves)
    EXPORT.mkdir(parents=True, exist_ok=False)

    def example(merchant, description, amount, direction, target, membership):
        user = (
            f"merchant: {merchant}\ndescription: {description}\n"
            f"amount: {amount}\ndirection: {direction}"
        )
        return TrackedExample(
            messages={
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user},
                    {"role": "assistant", "content": target},
                ]
            },
            membership=membership,
        )

    stats: Counter = Counter()
    conflicts: Counter = Counter()

    def convention(merchant, description, direction, leaf, human):
        hit = conventions.general_rule(merchant, description, direction, "labelled", leaf)
        if hit and hit[1] == "labelled" and hit[2] and hit[2] != leaf:
            stats[f"convention_{hit[0]}"] += 1
            return hit[2]
        return leaf

    # Tier B (guarded fetch; rule-labelled at fetch time).
    fetch_receipt = json.loads(TXNS_RECEIPT.read_text(encoding="utf-8"))
    eval_protection.verify_fetch_receipt(fetch_receipt, txncat_src=args.txncat_src)
    txns = json.loads(TXNS.read_text(encoding="utf-8"))
    if fetch_receipt.get("result_sha256") != btd._file_sha256(TXNS):
        raise RuntimeError("Tier-B fetch bytes differ from its receipt")
    # verify_tuning_export expects the fetch beside the export, and receipts
    # bind their exact path: re-run the canonical guard over the verified rows
    # into the export directory, and chain the export to that receipt.
    fetch_receipt = btd.write_tier_b_fetch(
        txns,
        protection,
        args=guard_args,
        data_path=EXPORT / "tuning_txns.json",
        receipt_path=EXPORT / "tuning_txns_receipt.json",
    )
    txns = json.loads((EXPORT / "tuning_txns.json").read_text(encoding="utf-8"))
    source_rows = {canonical_sha256(dict(t)): t for t in txns}
    # One transaction, one label and role: a row-level top-up label is more
    # specific (and may be human), so its Tier-B copy is skipped.
    topup_ids = set()
    account_customers: dict[str, set] = {}
    for t in txns:
        account_customers.setdefault(t["account_id"], set()).add(t["customer_id"])
    for path in TOPUPS.values():
        with path.open(newline="", encoding="utf-8") as stream:
            for r in csv.DictReader(stream):
                topup_ids.add((r["account_id"], r["transaction_id"]))
                account_customers.setdefault(r["account_id"], set()).add(r["customer_id"])
    # Sources resolve customers by different routes.  An account linked to
    # more than one customer across them cannot prove its customer is
    # unprotected, so every row on it fails closed.
    ambiguous_accounts = {a for a, c in account_customers.items() if len(c) > 1}
    stats["ambiguous_accounts_dropped"] = len(ambiguous_accounts)
    train, val = [], []
    for t in txns:
        if t["account_id"] in ambiguous_accounts:
            stats["tier_b_ambiguous_account_rows"] += 1
            continue
        if (t["account_id"], t["transaction_id"]) in topup_ids:
            stats["tier_b_skipped_in_topup"] += 1
            continue
        direction = "credit" if int(t["is_credit"]) else "debit"
        target = convention(t["merchant"], t["description"], direction, t["target"], False)
        ex = example(
            t["merchant"],
            t["description"],
            t["amount"],
            direction,
            target,
            exact_plaid_membership(source="tier_b_customer_linked_plaid", row=t),
        )
        (val if btd.tier_b_role(t["merchant"]) == "selection" else train).append(ex)
        stats["tier_b"] += 1

    # Top-ups (ID-recovered, receipted).
    input_receipts = [fetch_receipt]
    topup_rows = []
    for name, path in TOPUPS.items():
        input_receipts.append(eval_protection.verify_artifact(path, protection=protection))
        with path.open(newline="", encoding="utf-8") as stream:
            for row in csv.DictReader(stream):
                topup_rows.append((name, row))
                source_rows[canonical_sha256(dict(row))] = row
    labels = label(
        [
            {
                "merchant": r.get("merchant_raw") or "",
                "description": r.get("description_raw") or "",
                "is_credit": 1 if r["direction"] == "credit" else 0,
                "native_category": r.get("native_category"),
            }
            for _, r in topup_rows
        ],
        args.rules_root,
    )
    blocked = btd.load_risk_merchants() | btd.frozen_holdout_merchants()
    starved = {leaf: [] for leaf in btd.STARVED_TOPUP_LEAVES}
    topup_seen = set()
    for (name, row), lab in zip(topup_rows, labels, strict=True):
        if row["account_id"] in ambiguous_accounts:
            stats[f"{name}_ambiguous_account_rows"] += 1
            continue
        # One label per transaction: sources are read in TOPUPS order, so the
        # rule-labelled credits (last) never displace an LLM or human label.
        event = (row["account_id"], row["transaction_id"])
        if event in topup_seen:
            stats[f"{name}_duplicate_of_earlier_topup"] += 1
            continue
        topup_seen.add(event)
        leaf = row.get("gold_leaf")
        if not leaf or leaf not in leaves:
            stats[f"{name}_invalid_leaf"] += 1
            continue
        merchant = btd._norm(row.get("merchant_raw") or "")
        if merchant in blocked and leaf not in btd.STARVED_TOPUP_LEAVES:
            stats[f"{name}_blocked_merchant"] += 1
            continue
        human = _human(row)
        rule_leaf = lab["leaf"]
        if rule_leaf and rule_leaf != leaf:
            if human:
                conflicts[(name, (lab["tier"] or "").split("_")[0], leaf, rule_leaf)] += 1
            else:
                stats[f"{name}_rule_override"] += 1
                leaf = rule_leaf
        leaf = convention(row.get("merchant_raw"), row.get("description_raw"), row["direction"],
                          leaf, human)
        ex = example(
            row.get("merchant_raw") or "",
            row.get("description_raw") or "",
            abs(float(row["amount"])),
            row["direction"],
            leaf,
            exact_plaid_membership(source=name, row=row),
        )
        train.append(ex)
        stats[name] += 1
        if name == "tuning_leaf_topup" and leaf in starved:
            starved[leaf].append(ex)

    # Evaluation-text screen (added 2026-09-23 after the independent
    # disjointness check).  Drop supervised rows whose exact text, or input
    # fingerprint, equals a benchmark transaction's, or whose text equals a gold
    # evaluation row's.  These are other customers' identical narratives, but
    # the benchmark's unseen-input view and the registry both exclude them.
    sys.path.insert(0, str(ROOT / "src" / "transformer"))
    from build_pretrain_guarded import gold_eval_texts, protected_texts  # noqa: PLC0415

    bench_texts, gold_texts = protected_texts(), gold_eval_texts()

    def screened(ex):
        user = ex.messages["messages"][1]["content"]
        fields = dict(
            part.split(": ", 1) for part in user.split("\ndescription: ", 1)[0].split("\n")
        )
        merchant = fields.get("merchant", "")
        description = user.split("\ndescription: ", 1)[1].rsplit("\namount: ", 1)[0]
        direction = user.rsplit("\ndirection: ", 1)[1]
        m, d = merchant.strip().lower(), description.strip().lower()
        if (direction, m, d) in bench_texts:
            stats["dropped_benchmark_text"] += 1
            return False
        if (m, d) in gold_texts:
            stats["dropped_gold_eval_text"] += 1
            return False
        return True

    train = [ex for ex in train if screened(ex)]
    val = [ex for ex in val if screened(ex)]
    kept = {id(ex) for ex in train}
    starved = {leaf: [ex for ex in pool if id(ex) in kept] for leaf, pool in starved.items()}

    def leaf_of(ex):
        return ex.messages["messages"][2]["content"]

    def merchant_of(ex):
        for part in ex.messages["messages"][1]["content"].split("\n"):
            if part.startswith("merchant: "):
                return btd._norm(part[len("merchant: "):])
        return ""

    counts = Counter(leaf_of(ex) for ex in train)
    extra = []
    for leaf in sorted(btd.STARVED_TOPUP_LEAVES):
        have, pool = counts.get(leaf, 0), starved.get(leaf) or []
        if have < btd.MIN_STARVED_EFFECTIVE and pool:
            extra += [pool[i % len(pool)] for i in range(btd.MIN_STARVED_EFFECTIVE - have)]
    train += extra
    stats["starved_oversample_copies"] = len(extra)
    guard_extra = []
    for leaf in sorted(btd.RISK_GUARD_LEAVES):
        pool = [ex for ex in train if leaf_of(ex) == leaf and merchant_of(ex) not in blocked]
        if pool and len(pool) < btd.MIN_RISK_GUARD_CLEAN:
            guard_extra += [
                pool[i % len(pool)] for i in range(btd.MIN_RISK_GUARD_CLEAN - len(pool))
            ]
    train += guard_extra
    stats["risk_guard_oversample_copies"] = len(guard_extra)

    import random  # noqa: PLC0415

    rng = random.Random(btd.SEED)
    rng.shuffle(train)
    rng.shuffle(val)
    val = val[: btd.MAX_VAL_ROWS]
    train_path, val_path = EXPORT / "tuning_train.jsonl", EXPORT / "tuning_val.jsonl"
    coverage = publish_training_export(
        train,
        val,
        train_path=train_path,
        selection_path=val_path,
        lookup_path=EXPORT / "tuning_membership_lookup.csv",
        coverage_path=EXPORT / "tuning_membership_coverage.json",
    )
    for path, rows, purpose in (
        (train_path, train, "supervised_training"),
        (val_path, val, "model_selection_validation"),
    ):
        eval_protection.write_artifact_receipt(
            path,
            consumer="build_tuning_dataset",
            purpose=purpose,
            input_receipts=input_receipts,
            manifest_identities=[btd._export_manifest_entry(ex, source_rows) for ex in rows],
        )
    (EXPORT / "tuning_system_prompt.txt").write_text(system_prompt)
    summary = {
        "schema_version": "retrain-tuning-export-v1",
        "conventions_version": conventions.VERSION,
        "rules_root": str(args.rules_root),
        "train_rows": len(train),
        "val_rows": len(val),
        "distinct_train_leaves": len(Counter(leaf_of(ex) for ex in train)),
        "sources": dict(stats),
        "human_label_rule_conflicts": [
            {"source": k[0], "rule_tier": k[1], "human_leaf": k[2], "rule_leaf": k[3], "rows": v}
            for k, v in conflicts.most_common()
        ],
        "membership_coverage": {
            k: coverage[k] for k in coverage if isinstance(coverage[k], (int, float, str))
        },
        "tier_a": "dropped (decision 1)",
    }
    (EXPORT / "RETRAIN_EXPORT.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "human_label_rule_conflicts"},
                     indent=1))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    cr = sub.add_parser("credits")
    cr.add_argument("--inputs", type=pathlib.Path, default=None)
    cr.add_argument("--rules-root", type=pathlib.Path, required=True)
    cr.add_argument("--target", type=int, default=22_000)
    cr.add_argument("--per-leaf-cap", type=int, default=1_500)
    cr.add_argument("--keep-per-thousand", type=int, default=20)
    cr.add_argument("--protected-membership", action="append", type=pathlib.Path, required=True)
    cr.add_argument("--protected-publication", type=pathlib.Path, required=True)
    cr.add_argument("--txncat-src", type=pathlib.Path, default=None)
    b = sub.add_parser("build")
    b.add_argument("--inputs", type=pathlib.Path, default=None)
    b.add_argument("--rules-root", type=pathlib.Path, required=True)
    b.add_argument("--protected-membership", action="append", type=pathlib.Path, required=True)
    b.add_argument("--protected-publication", type=pathlib.Path, required=True)
    b.add_argument("--txncat-src", type=pathlib.Path, default=None)
    f = sub.add_parser("fetch")
    f.add_argument("--inputs", type=pathlib.Path, default=None)
    f.add_argument("--cap", type=int, default=btd.DEFAULT_CAP)
    f.add_argument("--rules-root", type=pathlib.Path, required=True)
    f.add_argument("--protected-membership", action="append", type=pathlib.Path, required=True)
    f.add_argument("--protected-publication", type=pathlib.Path, required=True)
    f.add_argument("--txncat-src", type=pathlib.Path, default=None)
    args = parser.parse_args()
    _set_inputs(args.inputs)
    if args.command == "fetch":
        fetch(args)
    elif args.command == "build":
        build(args)
    elif args.command == "credits":
        credits(args)


if __name__ == "__main__":
    main()

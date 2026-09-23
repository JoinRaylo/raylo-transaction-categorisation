"""Independent check: nothing the TxCat-1 retrain trains on is benchmark or eval data.

Carlos asked for a double-check before training (2026-09-23).  This script
deliberately does not use the training-data protection gate's code
(``eval_protection``, ``benchmark_enforcement``).  It reads the final training
artifacts and the private benchmark files directly and counts overlaps.  It
prints aggregates only.

Training artifacts:
- the stage-2 export (train/validation JSONL, membership lookup), its Tier-B
  fetch and the ID-recovered top-ups;
- the stage-1 labels (consensus plus rule-labelled texts);
- every guarded pretraining shard.

Checked against:
1. **Benchmark identity** (3,295 protected rows): exact transaction, account,
   customer.
2. **Benchmark inputs**: the exact text (direction, merchant, description) and
   the input fingerprint (merchant, description, abs amount, direction) of
   every benchmark transaction.
3. **Gold evaluation sets**: the exact (merchant, description) texts of each
   registered gold file.  The locked v5/v6 sets are never opened.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import pathlib
import re
import sys
from collections import Counter

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
PRIVATE = pathlib.Path.home() / ".local/share/raylo-txncat"
GOLD = [
    "gold_credit_eval.csv", "gold_merchant_labels.csv", "gold_tail_labels.csv",
    "gold_transactions.csv", "gold_transactions_risk_categories.csv",
    "gold_transactions_risk_t6bound.csv", "gold_transactions_v2.csv",
    "gold_transactions_v2_batch2.csv", "gold_transactions_v3_volume.csv",
    "gold_transactions_v4_slm_volume.csv", "gold_v2_slm_eval_holdout.csv",
    "gold_v3_eyeball.csv", "gold_v4_eyeball.csv",
]
USER = re.compile(
    r"\Amerchant: (?P<merchant>.*?)\ndescription: (?P<description>.*)\n"
    r"amount: (?P<amount>[^\n]*)\ndirection: (?P<direction>[^\n]*)\Z",
    re.DOTALL,
)


def norm(s) -> str:
    return (s or "").strip().lower()


def fingerprint(merchant, description, amount, direction) -> tuple:
    return (norm(merchant), norm(description), f"{abs(float(amount or 0)):.2f}", direction)


def benchmark():
    ids = {"events": set(), "accounts": set(), "customers": set()}
    with open(PRIVATE / "benchmark-protected-3295-2026-09-23/protected-membership.csv",
              newline="") as stream:
        for r in csv.DictReader(stream):
            ids["events"].add((r["account_id"], r["transaction_id"]))
            ids["accounts"].add(r["account_id"])
            ids["customers"].add(r["customer_id"])
    texts, prints, rows = set(), set(), 0
    base = PRIVATE / "benchmark-2000-candidate-2026-09-22"
    for path, merchant_key in ((base / "release/benchmark-candidate.jsonl", "merchant"),
                               (base / "expansion/expansion-selection.jsonl", "merchant_name")):
        for line in open(path, encoding="utf-8"):
            r = json.loads(line)
            rows += 1
            description = r.get("description")
            if description is None:
                description = r.get("transaction_name")
            texts.add((r["direction"], norm(r.get(merchant_key)), norm(description)))
            prints.add(fingerprint(r.get(merchant_key), description, r["amount"], r["direction"]))
    assert rows == 3295 and len(ids["events"]) == 3295, "benchmark files incomplete"
    return ids, texts, prints


def gold_texts() -> dict[str, set]:
    out = {}
    for name in GOLD:
        path = ROOT / "data" / name
        if not path.exists():
            continue
        with open(path, newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            if "description_raw" not in (reader.fieldnames or []):
                continue
            out[name] = {(norm(r.get("merchant_raw")), norm(r["description_raw"])) for r in reader}
    return out


def check_rows(name, rows, ids, texts, prints, gold, report):
    c = Counter()
    for r in rows:
        c["rows"] += 1
        if r.get("account_id"):
            c["benchmark_event"] += (r["account_id"], r["transaction_id"]) in ids["events"]
            c["benchmark_account"] += r["account_id"] in ids["accounts"]
        if r.get("customer_id"):
            c["benchmark_customer"] += r["customer_id"] in ids["customers"]
        key = (r["direction"], norm(r["merchant"]), norm(r["description"]))
        c["benchmark_exact_text"] += key in texts
        if r.get("amount") is not None:
            c["benchmark_input_fingerprint"] += fingerprint(
                r["merchant"], r["description"], r["amount"], r["direction"]) in prints
        for gname, gset in gold.items():
            if (key[1], key[2]) in gset:
                c[f"gold_text:{gname}"] += 1
    report[name] = dict(c)
    print(name, dict(c), file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=pathlib.Path, default=ROOT / "outputs/retrain_inputs_v2")
    parser.add_argument("--export", type=pathlib.Path, default=ROOT / "outputs/retrain_export_v2")
    parser.add_argument("--pretrain", type=pathlib.Path,
                        default=ROOT / "outputs/transformer/pretrain_guarded_v2")
    parser.add_argument("--stage1", type=pathlib.Path, default=None)
    args = parser.parse_args()
    ids, texts, prints = benchmark()
    gold = gold_texts()
    report = {"schema_version": "training-disjointness-check-v1",
              "benchmark_rows": 3295, "gold_files_checked": sorted(gold),
              "locked_sets_opened": False, "artifacts": {}}
    art = report["artifacts"]

    # Stage 2: export rows (texts), plus identities from the lookup and sources.
    for split in ("tuning_train.jsonl", "tuning_val.jsonl"):
        rows = []
        for line in open(args.export / split, encoding="utf-8"):
            m = json.loads(line)["messages"]
            f = USER.match(m[1]["content"]).groupdict()
            rows.append({"merchant": f["merchant"], "description": f["description"],
                         "amount": f["amount"], "direction": f["direction"]})
        check_rows(f"stage2:{split}", rows, ids, texts, prints, gold, art)
    source_ids = {}
    for t in json.load(open(args.export / "tuning_txns.json", encoding="utf-8")):
        source_ids[(t["account_id"], t["transaction_id"])] = t["customer_id"]
    for name in ("tuning_leaf_topup", "tuning_credit_topup", "tuning_risk_topup"):
        for r in csv.DictReader(open(args.inputs / f"{name}.csv", newline="", encoding="utf-8")):
            source_ids[(r["account_id"], r["transaction_id"])] = r["customer_id"]
    lookup = list(csv.DictReader(open(args.export / "tuning_membership_lookup.csv", newline="")))
    c = Counter(rows=len(lookup))
    for r in lookup:
        event = (r["account_id"], r["transaction_id"])
        c["not_from_a_source_file"] += event not in source_ids
        c["benchmark_event"] += event in ids["events"]
        c["benchmark_account"] += r["account_id"] in ids["accounts"]
        c["benchmark_customer"] += source_ids.get(event) in ids["customers"]
    art["stage2:identities"] = dict(c)
    print("stage2:identities", dict(c), file=sys.stderr)

    stage1 = args.stage1 or (args.inputs / "stage1_labels.parquet")
    if not stage1.exists():
        stage1 = args.inputs / "distillation_labels_consensus.parquet"
    s1 = pd.read_parquet(stage1)
    check_rows(f"stage1:{stage1.name}", s1.to_dict("records"), ids, texts, prints, gold, art)

    manifest = json.load(open(args.pretrain / "MANIFEST.json"))
    total = Counter()
    for shard in manifest["shards"]:
        df = pd.read_parquet(args.pretrain / shard["path"],
                             columns=["provider", "merchant", "description", "direction",
                                      "account_id", "transaction_id", "customer_id"])
        part = {}
        check_rows(shard["path"], df.to_dict("records"), ids, texts, prints, gold, part)
        total.update(part[shard["path"]])
    art["pretraining:all_shards"] = dict(total)
    print("pretraining:all_shards", dict(total), file=sys.stderr)
    out = ROOT / "outputs" / "training_disjointness_check.json"
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    os.chmod(out, 0o600)
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()

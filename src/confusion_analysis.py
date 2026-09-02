"""Standing confusion-matrix + risk-category minimum-bar tool (CLAUDE.md sec 12).

Institutionalises a lesson we've re-learned by hand every time: an aggregate
leaf-accuracy number can look fine while quietly failing on the categories
that actually matter for credit risk (gambling subtypes, priority debt,
BNPL/high-cost credit). Run this against ANY {gold_leaf, pred_leaf} prediction
CSV -- a benchmark run, a production tranche, a re-score after a dictionary
change -- to get both the full confusion picture and an explicit risk-category
pass/fail, instead of a one-off manual read of the error rows.

Usage:
    python src/confusion_analysis.py <predictions.csv> [--min-risk-accuracy 0.70]

Expects columns: gold_leaf, pred_leaf (general-category columns optional --
recomputed from taxonomy.csv if absent).
"""
import csv
import pathlib
import sys
from collections import Counter, defaultdict

from eval_sets import refuse_confirmation_eval

ROOT = pathlib.Path(__file__).resolve().parent.parent
TAXONOMY_CSV = ROOT / "taxonomy" / "taxonomy.csv"

# The categories a good aggregate score can hide a bad one behind. Kept
# explicit and separate from "priority debt" (housing/utilities -- already
# well-covered by volume-weighted sampling) -- this is specifically the
# low-volume, high-consequence family that volume-weighted gold sets
# systematically under-sample (v4 got only 21 gambling_betting rows despite
# it being the single highest-IV feature found in the whole project).
RISK_GENERAL_CATEGORIES = {"gambling", "credit_loan_repayments", "high_cost_distress_credit"}

# Credit-side minimum bar (2026-09-02). Credits are 24.7% of live Plaid rows and
# half the money, but 0.65% of the training jsonl; the pipeline scored 53% on
# credits vs 83% on debits. These are the income / transfer leaves the
# affordability and risk features depend on. Reported whenever the prediction
# CSV carries a `direction` column.
CREDIT_BAR_LEAVES = {
    "salary", "salary_gig", "income_agency_work", "benefits_state", "pension_received",
    "refund_received", "returned_payment", "transfer_own_account", "transfer_p2p",
    "loan_disbursement", "income_other_unspecified", "tax_refund", "cashback",
}
CREDIT_BAR = 0.70


def load_taxonomy():
    rows = list(csv.DictReader(open(TAXONOMY_CSV)))
    gen_of = {r["detailed_category"]: r["general_category"] for r in rows}
    risk_leaves = {r["detailed_category"] for r in rows if r["general_category"] in RISK_GENERAL_CATEGORIES}
    return gen_of, risk_leaves


def analyse(rows, gen_of, risk_leaves):
    n = len(rows)
    leaf_correct = sum(1 for r in rows if r["gold_leaf"] == r["pred_leaf"])
    gen_correct = sum(1 for r in rows
                       if gen_of.get(r["pred_leaf"]) == gen_of.get(r["gold_leaf"]))

    confusion = Counter()
    for r in rows:
        if r["gold_leaf"] != r["pred_leaf"]:
            confusion[(r["gold_leaf"], r["pred_leaf"])] += 1

    per_leaf_errors = defaultdict(lambda: [0, 0])  # leaf -> [wrong, total]
    for r in rows:
        g = r["gold_leaf"]
        per_leaf_errors[g][1] += 1
        if g != r["pred_leaf"]:
            per_leaf_errors[g][0] += 1

    by_direction = {}
    if rows and "direction" in rows[0]:
        for d in ("debit", "credit"):
            sub = [r for r in rows if str(r.get("direction", "")).lower() == d]
            if sub:
                by_direction[d] = {
                    "n": len(sub),
                    "leaf_acc": sum(1 for r in sub if r["gold_leaf"] == r["pred_leaf"]) / len(sub),
                    "gen_acc": sum(1 for r in sub
                                   if gen_of.get(r["pred_leaf"]) == gen_of.get(r["gold_leaf"])) / len(sub),
                }
        credit_bar_rows = [r for r in rows
                           if str(r.get("direction", "")).lower() == "credit"
                           and r["gold_leaf"] in CREDIT_BAR_LEAVES]
        by_direction["credit_bar_n"] = len(credit_bar_rows)
        by_direction["credit_bar_acc"] = (
            sum(1 for r in credit_bar_rows if r["gold_leaf"] == r["pred_leaf"]) / len(credit_bar_rows)
            if credit_bar_rows else None)
        cb_conf = Counter()
        for r in credit_bar_rows:
            if r["gold_leaf"] != r["pred_leaf"]:
                cb_conf[(r["gold_leaf"], r["pred_leaf"])] += 1
        by_direction["credit_bar_confusion"] = cb_conf

    risk_rows = [r for r in rows if r["gold_leaf"] in risk_leaves]
    risk_n = len(risk_rows)
    risk_correct = sum(1 for r in risk_rows if r["gold_leaf"] == r["pred_leaf"])
    risk_confusion = Counter()
    for r in risk_rows:
        if r["gold_leaf"] != r["pred_leaf"]:
            risk_confusion[(r["gold_leaf"], r["pred_leaf"])] += 1

    return {
        "n": n, "leaf_acc": leaf_correct / n if n else 0.0,
        "gen_acc": gen_correct / n if n else 0.0,
        "confusion": confusion, "per_leaf_errors": per_leaf_errors,
        "risk_n": risk_n, "risk_acc": (risk_correct / risk_n) if risk_n else None,
        "risk_confusion": risk_confusion,
        "by_direction": by_direction,
    }


def report(path, min_risk_accuracy):
    refuse_confirmation_eval(path)
    rows = list(csv.DictReader(open(path)))
    if not rows or "gold_leaf" not in rows[0] or "pred_leaf" not in rows[0]:
        sys.exit(f"{path}: expected columns gold_leaf, pred_leaf")
    gen_of, risk_leaves = load_taxonomy()
    a = analyse(rows, gen_of, risk_leaves)

    print(f"=== {path} ({a['n']} rows) ===")
    print(f"Overall:  leaf {a['leaf_acc']:.1%} / general {a['gen_acc']:.1%}")

    bd = a.get("by_direction") or {}
    if bd:
        print("\n--- By direction ---")
        for d in ("debit", "credit"):
            if d in bd:
                print(f"  {d:6} n={bd[d]['n']:5} | leaf {bd[d]['leaf_acc']:.1%} / general {bd[d]['gen_acc']:.1%}")
        if bd.get("credit_bar_acc") is not None:
            status = "OK" if bd["credit_bar_acc"] >= CREDIT_BAR else "BELOW BAR"
            print(f"  credit-side bar ({len(CREDIT_BAR_LEAVES)} income/transfer leaves): "
                  f"n={bd['credit_bar_n']} | accuracy {bd['credit_bar_acc']:.1%} | "
                  f"bar {CREDIT_BAR:.0%} | {status}")
            for (g, pr), c in bd["credit_bar_confusion"].most_common(8):
                print(f"    {g} -> {pr}: {c}")
        else:
            print("  credit-side bar: n=0 credit rows on bar leaves")
    else:
        print("\n--- By direction: prediction CSV has no `direction` column (add it) ---")

    print(f"\n--- Risk-category minimum bar (gambling / credit_loan_repayments / "
          f"high_cost_distress_credit, {len(risk_leaves)} leaves) ---")
    if a["risk_n"] == 0:
        print("  n=0 rows in this population -- no risk-category coverage in this eval, "
              "cannot assess (this is itself a finding: sample a dedicated risk-category set).")
    else:
        status = "OK" if a["risk_acc"] >= min_risk_accuracy else "BELOW BAR"
        print(f"  n={a['risk_n']} | accuracy {a['risk_acc']:.1%} | "
              f"bar {min_risk_accuracy:.0%} | {status}")
        if a["risk_acc"] < min_risk_accuracy:
            print(f"  *** aggregate leaf accuracy ({a['leaf_acc']:.1%}) does NOT reflect this. ***")
        print("  Worst risk-category confusions:")
        for (g, p), c in a["risk_confusion"].most_common(10):
            print(f"    {g} -> {p}: {c}")

    print(f"\n--- Per-leaf error rate (worst 15 of {len(a['per_leaf_errors'])} leaves seen, min 3 rows) ---")
    ranked = sorted(
        ((leaf, wrong, total) for leaf, (wrong, total) in a["per_leaf_errors"].items() if total >= 3),
        key=lambda x: -(x[1] / x[2]),
    )
    for leaf, wrong, total in ranked[:15]:
        flag = " [RISK]" if leaf in risk_leaves else ""
        print(f"    {leaf}{flag}: {wrong}/{total} wrong ({wrong/total:.0%})")

    print(f"\n--- Top confusion pairs overall ---")
    for (g, p), c in a["confusion"].most_common(15):
        print(f"    {g} -> {p}: {c}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    path = pathlib.Path(args[0])
    min_risk = 0.70
    if "--min-risk-accuracy" in args:
        min_risk = float(args[args.index("--min-risk-accuracy") + 1])
    report(path, min_risk)

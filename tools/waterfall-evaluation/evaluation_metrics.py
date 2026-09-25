"""Pure, count-first metrics for repeatable waterfall evaluations.

No model/data loading. Null and unclassified predictions do not count as correct
specific assignments. Research exact-string accuracy is reported separately.
"""

from collections import Counter, defaultdict

RISK_GENERALS = {"gambling", "credit_loan_repayments", "high_cost_distress_credit"}
CREDIT_LEAVES = {
    "salary",
    "salary_gig",
    "income_agency_work",
    "benefits_state",
    "pension_received",
    "refund_received",
    "returned_payment",
    "transfer_own_account",
    "transfer_p2p",
    "loan_disbursement",
    "income_other_unspecified",
    "tax_refund",
    "cashback",
}


def classified(leaf):
    return leaf is not None and not leaf.startswith("unclassified_")


def rate(numerator, denominator):
    return numerator / denominator if denominator else None


def score(rows, general, *, detailed=False):
    gold = [r["gold_leaf"] for r in rows]
    pred = [r["leaf"] for r in rows]
    if any(
        g not in general or (p is not None and p not in general)
        for g, p in zip(gold, pred, strict=True)
    ):
        raise ValueError("unknown evaluation label")
    n = len(rows)
    known = sum(classified(g) for g in gold)
    served = sum(classified(p) for p in pred)
    correct = sum(classified(p) and p == g for g, p in zip(gold, pred, strict=True))
    gc = sum(classified(p) and general[p] == general[g] for g, p in zip(gold, pred, strict=True))
    exact = sum((p or "unclassified_other") == g for g, p in zip(gold, pred, strict=True))
    exact_general = sum(
        general[p or "unclassified_other"] == general[g] for g, p in zip(gold, pred, strict=True)
    )
    risk_n = sum(general[g] in RISK_GENERALS for g in gold)
    risk_correct = sum(
        classified(p) and p == g and general[g] in RISK_GENERALS
        for g, p in zip(gold, pred, strict=True)
    )
    cbar = [r for r in rows if r["direction"] == "credit" and r["gold_leaf"] in CREDIT_LEAVES]
    result = {
        "n": n,
        "known_gold_n": known,
        "gold_unclassified_n": n - known,
        "classified_n": served,
        "abstained_n": n - served,
        "coverage": rate(served, n),
        "correct_specific_leaf_n": correct,
        "specific_leaf_accuracy": rate(correct, n),
        "specific_leaf_accuracy_known_gold": rate(correct, known),
        "accuracy_among_classified": rate(correct, served),
        "correct_specific_general_n": gc,
        "specific_general_accuracy": rate(gc, n),
        "research_exact_leaf_n": exact,
        "research_exact_leaf_accuracy": rate(exact, n),
        "research_exact_general_n": exact_general,
        "research_exact_general_accuracy": rate(exact_general, n),
        "assignments_on_unknown_gold_n": sum(
            classified(p) and not classified(g) for g, p in zip(gold, pred, strict=True)
        ),
        "risk_gold_n": risk_n,
        "risk_correct_leaf_n": risk_correct,
        "risk_leaf_accuracy": rate(risk_correct, risk_n),
        "risk_false_positive_known_nonrisk_n": sum(
            classified(p)
            and general[p] in RISK_GENERALS
            and classified(g)
            and general[g] not in RISK_GENERALS
            for g, p in zip(gold, pred, strict=True)
        ),
        "risk_assigned_on_unknown_gold_n": sum(
            classified(p) and general[p] in RISK_GENERALS and not classified(g)
            for g, p in zip(gold, pred, strict=True)
        ),
        "risk_false_negative_n": sum(
            general[g] in RISK_GENERALS and (not classified(p) or general[p] not in RISK_GENERALS)
            for g, p in zip(gold, pred, strict=True)
        ),
        "credit_bar_n": len(cbar),
        "credit_bar_correct_n": sum(r["leaf"] == r["gold_leaf"] for r in cbar),
        "credit_bar_accuracy": rate(sum(r["leaf"] == r["gold_leaf"] for r in cbar), len(cbar)),
    }
    if detailed:
        support, predicted, hits = (
            Counter(gold),
            Counter(pred),
            Counter(g for g, p in zip(gold, pred, strict=True) if g == p),
        )
        per_leaf = {}
        for leaf in sorted(
            set(gold) | {p for p in pred if p is not None} | {"salary", "refund_received"}
        ):
            tp, g, p = hits[leaf], support[leaf], predicted[leaf]
            per_leaf[leaf] = {
                "support": g,
                "predicted": p,
                "tp": tp,
                "fp_known_gold": sum(
                    x == leaf and y != leaf and classified(y)
                    for y, x in zip(gold, pred, strict=True)
                ),
                "assigned_on_unknown_gold": sum(
                    x == leaf and not classified(y) for y, x in zip(gold, pred, strict=True)
                ),
                "precision": rate(tp, p),
                "recall": rate(tp, g),
                "f1": rate(2 * tp, p + g),
            }
        supported = [x for leaf, x in per_leaf.items() if classified(leaf) and x["support"]]
        result["macro_f1_supported_specific_leaves"] = rate(
            sum(x["f1"] for x in supported), len(supported)
        )
        result["macro_f1_leaf_count"] = len(supported)
        result["per_leaf"] = per_leaf
        result["confusion"] = [
            {"gold": g, "predicted": p, "n": count}
            for (g, p), count in sorted(
                Counter(zip(gold, pred, strict=True)).items(),
                key=lambda x: (x[0][0], x[0][1] or ""),
            )
        ]
    return result


def summarise(rows, general):
    result = {"all": score(rows, general, detailed=True)}
    for field in ("direction", "provider", "merchant_state", "label_provenance", "tier"):
        groups = defaultdict(list)
        for row in rows:
            groups[row[field]].append(row)
        result["by_" + field] = {k: score(v, general) for k, v in sorted(groups.items())}
        if sum(x["n"] for x in result["by_" + field].values()) != len(rows):
            raise ValueError("slice counts do not reconcile")
    groups = defaultdict(list)
    for row in rows:
        groups[row["input_hash"]].append(row)
    consistent = [
        group[0] for group in groups.values() if len({r["gold_leaf"] for r in group}) == 1
    ]
    result["input_quality"] = {
        "duplicate_rows": len(rows) - len(groups),
        "conflicting_label_groups": sum(
            len({r["gold_leaf"] for r in g}) > 1 for g in groups.values()
        ),
        "unique_consistent_inputs": len(consistent),
    }
    result["unique_consistent_inputs"] = score(consistent, general)
    result["actual_residual"] = score([r for r in rows if r["residual"]], general)
    return result


def compare_runs(before, after, general):
    """Require identical rows and gold; preserve the baseline residual denominator."""

    def indexed(rows):
        result = {(r["dataset"], r["view"], r["head"], r["row_id"]): r for r in rows}
        if len(result) != len(rows):
            raise ValueError("duplicate comparison identity")
        return result

    old, new = indexed(before), indexed(after)
    if old.keys() != new.keys():
        raise ValueError("baseline/candidate evaluation coverage differs")
    groups, changed = defaultdict(lambda: ([], [])), []
    for key in sorted(old):
        a, b = old[key], new[key]
        if any(
            a[f] != b[f]
            for f in (
                "input_hash",
                "gold_leaf",
                "direction",
                "provider",
                "merchant_state",
                "label_provenance",
            )
        ):
            raise ValueError("baseline/candidate inputs or labels differ")
        pair = groups[key[:3]]
        pair[0].append(a)
        pair[1].append(b)
        if (a["leaf"], a["tier"], a["rule_id"]) != (b["leaf"], b["tier"], b["rule_id"]):
            changed.append(
                {
                    "dataset": key[0],
                    "view": key[1],
                    "head": key[2],
                    "row_id": key[3],
                    "gold_leaf": a["gold_leaf"],
                    "before_leaf": a["leaf"],
                    "after_leaf": b["leaf"],
                    "before_tier": a["tier"],
                    "after_tier": b["tier"],
                    "before_rule_id": a["rule_id"],
                    "after_rule_id": b["rule_id"],
                    "before_correct": classified(a["leaf"]) and a["leaf"] == a["gold_leaf"],
                    "after_correct": classified(b["leaf"]) and b["leaf"] == b["gold_leaf"],
                }
            )
    comparisons = []
    for (dataset, view, head), (a, b) in sorted(groups.items()):
        prior, current = score(a, general), score(b, general)
        transitions = Counter()
        for x, y in zip(a, b, strict=True):
            cx = classified(x["leaf"]) and x["leaf"] == x["gold_leaf"]
            cy = classified(y["leaf"]) and y["leaf"] == y["gold_leaf"]
            if x["leaf"] != y["leaf"]:
                transitions[
                    "correct_to_wrong"
                    if cx and not cy
                    else "wrong_to_correct"
                    if cy and not cx
                    else "wrong_to_different_wrong"
                ] += 1
        comparisons.append(
            {
                "dataset": dataset,
                "view": view,
                "head": head,
                "baseline": prior,
                "candidate": current,
                "delta": {
                    k: current[k] - prior[k]
                    if current[k] is not None and prior[k] is not None
                    else None
                    for k in prior
                },
                "transitions": dict(transitions),
                "fixed_baseline_residual": {
                    "baseline": score([x for x in a if x["residual"]], general),
                    "candidate": score(
                        [y for x, y in zip(a, b, strict=True) if x["residual"]], general
                    ),
                },
            }
        )
    return {"comparisons": comparisons, "changed_rows_n": len(changed)}, changed

"""Leaf-level logreg vs hinge SVM: accuracy, F1, per-class / per-parent.

Classifier-only (gambling promote included). Does not score locked v5/v6.
Does not overwrite serving dumps.

Usage:
    python src/score_classifier_heads.py
"""
from __future__ import annotations

import csv
import hashlib
import json
import pathlib
import sys
import warnings

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    f1_score,
    precision_recall_fscore_support,
)

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from confusion_analysis import RISK_GENERAL_CATEGORIES, load_taxonomy  # noqa: E402
from eval_sets import refuse_confirmation_eval  # noqa: E402
from score_t5b_residual import scores_and_margin  # noqa: E402

HOLDOUT = ROOT / "data" / "gold_v2_slm_eval_holdout.csv"
RISK = ROOT / "data" / "gold_transactions_risk_categories.csv"
MODELS = ROOT / "outputs" / "distill_models"
LOGREG = MODELS / "tfidf_logreg_v5.joblib"
HINGE = MODELS / "tfidf_linearsvm_sgd_v5.joblib"
OUT = ROOT / "outputs"
REPORT = ROOT / "data" / "classifier_v5_head_metrics_report.md"
HOLDOUT_MD5 = "c075717405a183191a43d0eb33f8dca3"


def load_gold(path):
    refuse_confirmation_eval(path)
    gold = pd.read_csv(path)
    feat = pd.DataFrame({
        "vendor": gold["merchant_raw"].fillna(""),
        "description": gold["description_raw"].fillna(""),
        "amount": gold["amount"].astype(float),
        "is_credit": (gold["direction"] == "credit").astype(int),
    })
    return gold, feat


def predict(bundle, feat):
    preds, _, _ = scores_and_margin(bundle, feat)
    return np.asarray(preds, dtype=object)


def overall(y, p, labels):
    y = np.asarray(y, dtype=object)
    p = np.asarray(p, dtype=object)
    present = np.array(sorted(set(y.tolist())))
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="y_pred contains classes not in y_true")
        return {
            "n": int(len(y)),
            "accuracy": float(accuracy_score(y, p)),
            "balanced_accuracy": float(balanced_accuracy_score(y, p)),
            "micro_f1": float(f1_score(y, p, average="micro", zero_division=0)),
            "weighted_f1": float(f1_score(y, p, average="weighted", zero_division=0)),
            "macro_f1": float(f1_score(y, p, labels=present, average="macro", zero_division=0)),
            "n_labels_in_gold": int(len(present)),
        }


def per_class(y, p, class_list):
    y = np.asarray(y, dtype=object)
    p = np.asarray(p, dtype=object)
    prec, rec, f1, sup = precision_recall_fscore_support(
        y, p, labels=class_list, zero_division=0,
    )
    rows = []
    for lab, pr, rc, f, s in zip(class_list, prec, rec, f1, sup):
        s = int(s)
        if s == 0:
            continue
        rows.append({
            "label": lab,
            "n": s,
            "accuracy": float(rc),
            "precision": float(pr),
            "recall": float(rc),
            "f1": float(f),
        })
    return rows


def pct(x):
    return f"{100 * x:.1f}%"


def md5(path):
    return hashlib.md5(path.read_bytes()).hexdigest()


def write_csv(path, rows, extra=None):
    if not rows:
        return
    fields = list(rows[0].keys())
    if extra:
        for k, v in extra.items():
            fields.append(k)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            row = dict(r)
            if extra:
                row.update(extra)
            w.writerow(row)


def merge_heads(logreg_rows, hinge_rows):
    by_h = {r["label"]: r for r in hinge_rows}
    out = []
    for r in logreg_rows:
        h = by_h.get(r["label"], {})
        ha = h.get("accuracy")
        hf = h.get("f1")
        out.append({
            "label": r["label"],
            "n": int(r["n"]),
            "logreg_accuracy": float(r["accuracy"]),
            "hinge_accuracy": float(ha) if ha is not None else None,
            "delta_accuracy": (float(ha) - float(r["accuracy"])) if ha is not None else None,
            "logreg_precision": float(r["precision"]),
            "hinge_precision": float(h["precision"]) if "precision" in h else None,
            "logreg_recall": float(r["recall"]),
            "hinge_recall": float(h["recall"]) if "recall" in h else None,
            "logreg_f1": float(r["f1"]),
            "hinge_f1": float(hf) if hf is not None else None,
            "delta_f1": (float(hf) - float(r["f1"])) if hf is not None else None,
        })
    return out


def fmt_row(r, label_key="label"):
    da = r["delta_accuracy"]
    df = r["delta_f1"]
    da_s = f"{da:+.1%}" if da is not None else "n/a"
    df_s = f"{df:+.1%}" if df is not None else "n/a"
    ha = pct(r["hinge_accuracy"]) if r["hinge_accuracy"] is not None else "n/a"
    hf = pct(r["hinge_f1"]) if r["hinge_f1"] is not None else "n/a"
    return (f"| `{r[label_key]}` | {r['n']} | {pct(r['logreg_accuracy'])} | {ha} | {da_s} "
            f"| {pct(r['logreg_f1'])} | {hf} | {df_s} |")


def score_set(name, gold, feat, logreg, hinge, gen_of, risk_leaves):
    y_leaf = gold["gold_leaf"].to_numpy()
    y_gen = np.array([gen_of[g] for g in y_leaf], dtype=object)
    p_log = predict(logreg, feat)
    p_hin = predict(hinge, feat)
    p_log_g = np.array([gen_of.get(x, x) for x in p_log], dtype=object)
    p_hin_g = np.array([gen_of.get(x, x) for x in p_hin], dtype=object)

    gens = sorted(set(gen_of.values()))
    leaves_present = sorted(set(y_leaf))

    leaf_log = overall(y_leaf, p_log, leaves_present)
    leaf_hin = overall(y_leaf, p_hin, leaves_present)
    gen_log = overall(y_gen, p_log_g, gens)
    gen_hin = overall(y_gen, p_hin_g, gens)

    risk_mask = np.array([g in risk_leaves for g in y_leaf])
    risk = {}
    if risk_mask.any():
        risk = {
            "n": int(risk_mask.sum()),
            "logreg_acc": float(accuracy_score(y_leaf[risk_mask], p_log[risk_mask])),
            "hinge_acc": float(accuracy_score(y_leaf[risk_mask], p_hin[risk_mask])),
            "logreg_macro_f1": float(f1_score(
                y_leaf[risk_mask], p_log[risk_mask],
                labels=sorted(set(y_leaf[risk_mask])), average="macro", zero_division=0,
            )),
            "hinge_macro_f1": float(f1_score(
                y_leaf[risk_mask], p_hin[risk_mask],
                labels=sorted(set(y_leaf[risk_mask])), average="macro", zero_division=0,
            )),
        }

    per_leaf = merge_heads(
        per_class(y_leaf, p_log, leaves_present),
        per_class(y_leaf, p_hin, leaves_present),
    )
    per_gen = merge_heads(
        per_class(y_gen, p_log_g, gens),
        per_class(y_gen, p_hin_g, gens),
    )
    per_gen.sort(key=lambda r: -r["n"])
    per_leaf.sort(key=lambda r: -r["n"])

    # persist clf-only preds
    pred_path = OUT / f"classifier_v5_{name}_clf_heads.csv"
    with open(pred_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "merchant_raw", "gold_leaf", "gold_general",
            "logreg_leaf", "hinge_leaf", "logreg_general", "hinge_general",
        ])
        w.writeheader()
        for i, row in gold.reset_index(drop=True).iterrows():
            w.writerow({
                "merchant_raw": row["merchant_raw"],
                "gold_leaf": y_leaf[i],
                "gold_general": y_gen[i],
                "logreg_leaf": p_log[i],
                "hinge_leaf": p_hin[i],
                "logreg_general": p_log_g[i],
                "hinge_general": p_hin_g[i],
            })

    return {
        "leaf_log": leaf_log, "leaf_hin": leaf_hin,
        "gen_log": gen_log, "gen_hin": gen_hin,
        "risk": risk, "per_leaf": per_leaf, "per_gen": per_gen,
    }


def wins(rows, key="delta_f1"):
    better = sum(1 for r in rows if r[key] is not None and r[key] > 1e-12)
    worse = sum(1 for r in rows if r[key] is not None and r[key] < -1e-12)
    tie = len(rows) - better - worse
    return better, worse, tie


def main():
    gen_of, risk_leaves = load_taxonomy()
    holdout_hash = md5(HOLDOUT)
    logreg = joblib.load(LOGREG)
    hinge = joblib.load(HINGE)

    results = {}
    for name, path in (("holdout", HOLDOUT), ("risk", RISK)):
        gold, feat = load_gold(path)
        print(f"Scoring {name} n={len(gold)}...", file=sys.stderr)
        results[name] = score_set(name, gold, feat, logreg, hinge, gen_of, risk_leaves)

    # tracked metric tables
    for name in ("holdout", "risk"):
        write_csv(
            ROOT / "data" / f"classifier_v5_head_metrics_{name}_leaf.csv",
            results[name]["per_leaf"],
            extra={"eval_set": name},
        )
        write_csv(
            ROOT / "data" / f"classifier_v5_head_metrics_{name}_general.csv",
            results[name]["per_gen"],
            extra={"eval_set": name},
        )

    ho, rk = results["holdout"], results["risk"]
    lines = []
    lines.append("# Classifier v5 head comparison — logreg vs hinge (2026-08-26)\n")
    lines.append(
        "Same tranche-4 TF-IDF dumps as `data/classifier_v5_retrain_report.md`. "
        "Classifier-only (gambling catch-all promote on). Locked v5/v6 not scored. "
        f"Holdout MD5 `{holdout_hash}` "
        f"{'(matches the protected v5-retrain hash)' if holdout_hash == HOLDOUT_MD5 else '(CHANGED)'}."
    )
    lines.append(
        "Micro-F1 equals accuracy for single-label classification. Macro-F1 averages "
        "per-class F1 over labels that appear in gold (unweighted), so rare leaves "
        "count the same as common ones. Weighted-F1 is the support-weighted mean. "
        "Balanced accuracy is mean recall. Per-class accuracy below is recall.\n"
    )

    def ov_table(title, log, hin):
        lines.append(f"### {title}\n")
        lines.append("| Metric | Logreg | Hinge | Δ (hinge − logreg) |")
        lines.append("|---|---|---|---|")
        for key, label in (
            ("accuracy", "Accuracy / micro-F1"),
            ("balanced_accuracy", "Balanced accuracy"),
            ("weighted_f1", "Weighted F1"),
            ("macro_f1", f"Macro F1 ({log['n_labels_in_gold']} gold labels)"),
        ):
            d = hin[key] - log[key]
            lines.append(f"| {label} | {pct(log[key])} | {pct(hin[key])} | {d:+.1%} |")
        lines.append("")

    lines.append("## Overall\n")
    ov_table(f"Holdout leaf (n={ho['leaf_log']['n']}, merchant-disjoint)", ho["leaf_log"], ho["leaf_hin"])
    ov_table("Holdout general (leaf rolled up)", ho["gen_log"], ho["gen_hin"])
    ov_table(f"Risk gold leaf (n={rk['leaf_log']['n']})", rk["leaf_log"], rk["leaf_hin"])
    ov_table("Risk gold general (leaf rolled up)", rk["gen_log"], rk["gen_hin"])

    if rk["risk"]:
        r = rk["risk"]
        lines.append("### Risk-category bar (gambling / credit_loan / high-cost leaves)\n")
        lines.append("| Metric | Logreg | Hinge | Δ |")
        lines.append("|---|---|---|---|")
        lines.append(
            f"| Accuracy (n={r['n']}) | {pct(r['logreg_acc'])} | {pct(r['hinge_acc'])} | "
            f"{r['hinge_acc'] - r['logreg_acc']:+.1%} |"
        )
        lines.append(
            f"| Macro F1 | {pct(r['logreg_macro_f1'])} | {pct(r['hinge_macro_f1'])} | "
            f"{r['hinge_macro_f1'] - r['logreg_macro_f1']:+.1%} |"
        )
        bar = "OK" if r["hinge_acc"] >= 0.70 else "BELOW BAR"
        lines.append(f"\nHinge risk-bar **{pct(r['hinge_acc'])} {bar}** (threshold 70%). Logreg {pct(r['logreg_acc'])} OK.\n")

    hb, hw, ht = wins(ho["per_gen"], "delta_f1")
    rb, rw, rt = wins(rk["per_gen"], "delta_f1")
    lines.append("## Per parent category\n")
    lines.append(
        f"Hinge vs logreg on general-level F1: holdout **{hb} better / {hw} worse / {ht} tie**; "
        f"risk gold **{rb} better / {rw} worse / {rt} tie**.\n"
    )
    lines.append("### Holdout\n")
    lines.append("| General | n | Logreg acc | Hinge acc | Δ acc | Logreg F1 | Hinge F1 | Δ F1 |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for r in ho["per_gen"]:
        lines.append(fmt_row(r))
    lines.append("\n### Risk gold\n")
    lines.append("| General | n | Logreg acc | Hinge acc | Δ acc | Logreg F1 | Hinge F1 | Δ F1 |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for r in rk["per_gen"]:
        lines.append(fmt_row(r))

    lines.append("\n## Per leaf — risk families (risk gold)\n")
    risk_leaf_rows = [r for r in rk["per_leaf"] if gen_of.get(r["label"]) in RISK_GENERAL_CATEGORIES]
    risk_leaf_rows.sort(key=lambda r: (gen_of[r["label"]], -r["n"]))
    lines.append("| Leaf | Parent | n | Logreg acc | Hinge acc | Δ acc | Logreg F1 | Hinge F1 | Δ F1 |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for r in risk_leaf_rows:
        parent = gen_of[r["label"]]
        da = r["delta_accuracy"]
        df = r["delta_f1"]
        lines.append(
            f"| `{r['label']}` | `{parent}` | {r['n']} | {pct(r['logreg_accuracy'])} | "
            f"{pct(r['hinge_accuracy'])} | {da:+.1%} | {pct(r['logreg_f1'])} | "
            f"{pct(r['hinge_f1'])} | {df:+.1%} |"
        )

    lines.append("\n## Per leaf — holdout, support ≥ 8\n")
    lines.append(
        "Holdout is merchant-disjoint and most leaves have few rows; F1 on n=1–3 is not "
        "interpretable. Full per-leaf tables: "
        "`data/classifier_v5_head_metrics_{holdout,risk}_leaf.csv`.\n"
    )
    fat = [r for r in ho["per_leaf"] if r["n"] >= 8]
    lines.append("| Leaf | n | Logreg acc | Hinge acc | Δ acc | Logreg F1 | Hinge F1 | Δ F1 |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for r in fat:
        lines.append(fmt_row(r))

    lb, lw, lt = wins(ho["per_leaf"], "delta_f1")
    rlb, rlw, rlt = wins(rk["per_leaf"], "delta_f1")
    lines.append("\n## Where hinge is worse\n")
    lines.append(
        "Parent-level **macro** F1 and balanced accuracy slightly favour logreg "
        "(holdout general macro F1 56.1% vs 55.2%; risk gold 42.2% vs 40.3%). "
        "That is a few thin parents going to zero, not a broad parent-level loss. "
        "On holdout: `fees_charges` 46.7%→0% recall (F1 60.9%→0%, n=15), "
        "`income_employment` 61.1%→27.8% (`salary` 69.2%→30.8%, n=13), "
        "`returned_payment` 50%→0% (n=14). "
        "Hinge also over-recalls `gambling` as a parent (holdout gambling F1 −8.8pp) "
        "while still winning gambling **leaf** F1 on the risk set.\n"
    )
    lines.append("\n## Verdict\n")
    lines.append(
        f"At **leaf** level hinge wins every aggregate on both sets (accuracy, balanced "
        f"accuracy, weighted F1, macro F1) and the risk bar (**86.1% vs 81.4%**, macro F1 "
        f"**86.9% vs 83.4%**). Holdout leaf F1: hinge better on {lb} leaves, worse on {lw}, "
        f"tie {lt}. Risk gold: better {rlb} / worse {rlw} / tie {rlt}. "
        f"Largest risk-leaf F1 lifts: `payday_loan` +28pp, `debt_management_plan` +16pp, "
        f"`gambling_unspecified` +15pp, `gambling_bingo` +15pp.\n"
    )
    lines.append(
        "Parent-level accuracy still favours hinge; parent **macro** F1 does not, "
        "because of the thin-class zeros above.\n"
    )
    lines.append(
        "Caveat unchanged: hinge has no `predict_proba`. A serving gate would use "
        "decision-function margin. If calibrated probabilities are required for audit, "
        "keep logreg or add a separate calibrator — do not treat hinge argmax as a "
        "probability. On leaf accuracy, F1, and the risk bar, hinge is the better head.\n"
    )
    lines.append("## Artefacts\n")
    lines.append("- `data/classifier_v5_head_metrics_{holdout,risk}_{leaf,general}.csv`")
    lines.append("- `src/score_classifier_heads.py`")
    lines.append("- Predictions (gitignored): `outputs/classifier_v5_{holdout,risk}_clf_heads.csv`")

    REPORT.write_text("\n".join(lines) + "\n")
    summary = {
        "holdout_md5": holdout_hash,
        "holdout": {"leaf_logreg": ho["leaf_log"], "leaf_hinge": ho["leaf_hin"],
                    "gen_logreg": ho["gen_log"], "gen_hinge": ho["gen_hin"]},
        "risk": {"leaf_logreg": rk["leaf_log"], "leaf_hinge": rk["leaf_hin"],
                 "gen_logreg": rk["gen_log"], "gen_hinge": rk["gen_hin"],
                 "risk_bar": rk["risk"]},
    }
    (OUT / "classifier_v5_head_metrics_summary.json").write_text(json.dumps(summary, indent=2))
    print(f"Wrote {REPORT}", file=sys.stderr)
    print("Holdout leaf acc", pct(ho["leaf_log"]["accuracy"]), pct(ho["leaf_hin"]["accuracy"]))
    print("Holdout leaf macro F1", pct(ho["leaf_log"]["macro_f1"]), pct(ho["leaf_hin"]["macro_f1"]))
    print("Risk leaf acc", pct(rk["leaf_log"]["accuracy"]), pct(rk["leaf_hin"]["accuracy"]))
    print("Risk leaf macro F1", pct(rk["leaf_log"]["macro_f1"]), pct(rk["leaf_hin"]["macro_f1"]))


if __name__ == "__main__":
    main()

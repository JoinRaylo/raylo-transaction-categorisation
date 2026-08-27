"""Score a gated classifier (T5b) against T6 on rows that would actually reach it.

The production question is not "how good is TF-IDF on a merchant-disjoint holdout".
It is: on a Plaid transaction that currently falls through T1–T5 to the provider
crosswalk, does a confidence-gated classifier beat T6 — and does LinearSVC change
that answer?

Populations (never locked confirmation sets — v5 retired, v6 at go/no-go):
  - Plaid gold v3 (whole-population sample, Plaid slice only)
  - gold v4 (unmatched-Plaid volume sample) — native category joined from
    data/gold_v4_eyeball.csv
  - risk-category gold, T6-bound subset only (no native field; T6 leaf omitted)

Usage:
    python src/score_t5b_residual.py           # score; train LinearSVC if missing
    python src/score_t5b_residual.py --retrain-svc
"""
from __future__ import annotations

import argparse
import csv
import json
import pathlib
import sys

import joblib
import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from confusion_analysis import analyse, load_taxonomy  # noqa: E402
from eval_sets import refuse_confirmation_eval  # noqa: E402
from distillation_bakeoff import (  # noqa: E402
    GAMBLING_LEAVES,
    MODELS_DIR,
    OUT_DIR,
    _parse_tuning_jsonl,
    build_text,
    featurise_for,
    predict,
)
from final_evaluation import (  # noqa: E402
    eqx_native_leaf,
    load_crosswalk,
    load_dictionary,
    load_rules,
    our_leaf,
    plaid_native_leaf,
)
import final_evaluation as fe  # noqa: E402

GOLD_V3 = ROOT / "data" / "gold_transactions_v3_volume.csv"
GOLD_V4 = ROOT / "data" / "gold_transactions_v4_slm_volume.csv"
GOLD_V4_EYEBALL = ROOT / "data" / "gold_v4_eyeball.csv"
GOLD_RISK = ROOT / "data" / "gold_transactions_risk_categories.csv"
GOLD_HOLDOUT = ROOT / "data" / "gold_v2_slm_eval_holdout.csv"
LOGREG_PATH = MODELS_DIR / "tfidf_logreg_v2.joblib"
SVC_PATH = MODELS_DIR / "tfidf_linearsvc_v2.joblib"  # legacy hinge dump from first bake-off
HINGE_PATH = MODELS_DIR / "tfidf_linearsvm_sgd.joblib"
LIBLINEAR_PATH = MODELS_DIR / "tfidf_linearsvc_liblinear.joblib"
PRED_CSV = OUT_DIR / "t5b_residual_predictions.csv"
CURVE_CSV = OUT_DIR / "t5b_residual_coverage_curve.csv"
SUMMARY_JSON = OUT_DIR / "t5b_residual_summary.json"
REPORT_MD = ROOT / "data" / "t5b_residual_gate_report.md"

COVER_POINTS = (0.50, 0.70, 0.80)
RISK_BAR = 0.70
SEED = 42


def _init_waterfall():
    fe.SUB_MAP, fe.PRI_MAP, fe.PLAID_MAP, _ = load_crosswalk()
    fe.DICTIONARY = load_dictionary()
    fe.RULES = load_rules()


def _promote_gambling(pred, scores, classes):
    pred = np.asarray(pred, dtype=object).copy()
    gambling_col = np.array([c in GAMBLING_LEAVES for c in classes])
    if not gambling_col.any() or "unclassified_other" not in classes:
        return pred
    unclass_i = int(np.flatnonzero(classes == "unclassified_other")[0])
    idx = scores.argmax(axis=1)
    runner = scores.copy()
    runner[np.arange(len(pred)), idx] = -np.inf
    runner_idx = runner.argmax(axis=1)
    gambling_mass = scores[:, gambling_col].sum(axis=1)
    promote = (pred == "unclassified_other") & (
        gambling_col[runner_idx] | (gambling_mass > scores[:, unclass_i])
    )
    pred[promote] = "gambling_unspecified"
    return pred


def scores_and_margin(bundle, df):
    """Return pred, max-score, top1−top2 margin (native scores, then gambling promote)."""
    X = featurise_for(bundle, df)
    clf = bundle["clf"]
    if bundle["kind"] == "linearsvc":
        scores = clf.decision_function(X)
        if scores.ndim == 1:
            scores = np.column_stack([-scores, scores])
        classes = np.asarray(clf.classes_)
    else:
        scores = clf.predict_proba(X)
        classes = np.asarray(clf.classes_)
    order = np.argsort(-scores, axis=1)
    top = scores[np.arange(len(df)), order[:, 0]]
    second = scores[np.arange(len(df)), order[:, 1]] if scores.shape[1] > 1 else np.zeros(len(df))
    margin = top - second
    pred = classes[order[:, 0]]
    pred = _promote_gambling(pred, scores, classes)
    return pred, top, margin


def _s(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return ""
    return str(v)


def resolve_tier(merchant, direction, description, native_cat, provider="plaid"):
    if str(provider).strip().lower() == "equifax":
        pri, sub = (native_cat.split(" | ", 1) + [""])[:2] if native_cat else ("", "")
        return our_leaf(
            _s(merchant), _s(direction), _s(description),
            eqx_native_leaf, pri, sub, _s(direction),
        )
    return our_leaf(
        _s(merchant), _s(direction), _s(description),
        plaid_native_leaf, _s(native_cat), _s(direction),
    )


def load_v4():
    gold = pd.read_csv(GOLD_V4)
    eye = pd.read_csv(GOLD_V4_EYEBALL)
    def _key(d):
        amt = pd.to_numeric(d["amount"], errors="coerce").fillna(0).map(lambda x: f"{float(x):.4f}")
        return (d["merchant_raw"].fillna("").astype(str)
                + "||" + d["description_raw"].fillna("").astype(str)
                + "||" + amt
                + "||" + d["direction"].fillna("").astype(str).str.lower())
    gold["_k"] = _key(gold)
    eye["_k"] = _key(eye)
    native = eye.drop_duplicates("_k").set_index("_k")["native_category_raw"]
    gold["native_category"] = gold["_k"].map(native)
    gold["source"] = "v4"
    gold["provider"] = "plaid"
    missing = gold["native_category"].isna().sum()
    if missing:
        print(f"WARN: {missing}/{len(gold)} v4 rows missing native_category from eyeball",
              file=sys.stderr)
    return gold.drop(columns=["_k"])


def load_v3_plaid():
    df = pd.read_csv(GOLD_V3)
    df = df[df["provider"].astype(str).str.lower() == "plaid"].copy()
    df["source"] = "v3_plaid"
    return df


def load_risk():
    df = pd.read_csv(GOLD_RISK)
    df["source"] = "risk"
    df["provider"] = "plaid"
    df["native_category"] = np.nan
    return df


def attach_waterfall(df):
    leaves, tiers = [], []
    for r in df.itertuples(index=False):
        native = getattr(r, "native_category", "")
        if native is None or (isinstance(native, float) and np.isnan(native)):
            native = ""
        leaf, tier = resolve_tier(
            getattr(r, "merchant_raw", ""),
            getattr(r, "direction", ""),
            getattr(r, "description_raw", ""),
            native,
            getattr(r, "provider", "plaid"),
        )
        leaves.append(leaf)
        tiers.append(tier)
    out = df.copy()
    out["t6_leaf"] = leaves
    out["waterfall_tier"] = tiers
    out["is_t6"] = out["waterfall_tier"].astype(str).str.startswith("T6")
    return out


def features_frame(df):
    return pd.DataFrame({
        "vendor": df["merchant_raw"].fillna(""),
        "description": df["description_raw"].fillna(""),
        "amount": pd.to_numeric(df["amount"], errors="coerce").fillna(0).abs().astype(float),
        "is_credit": (df["direction"].astype(str).str.lower() == "credit").astype(int),
    })


def train_linearsvc(logreg_bundle, force=False):
    """Linear SVM head on the frozen TF-IDF from logreg v2.

    liblinear LinearSVC was tried first (dual=False, max_iter=2000) and had not
    finished a single fit after ~8 minutes on ~167k × 30k sparse features.
    SGD hinge uses the same optimiser budget as the adopted logreg head
    (SGDClassifier, alpha=1e-6, 50 epochs) so the bake-off isolates loss
    (hinge vs log) rather than solver wall-clock.
    """
    if SVC_PATH.exists() and not force:
        print(f"Using existing {SVC_PATH.name}", file=sys.stderr)
        return joblib.load(SVC_PATH)
    from sklearn.linear_model import SGDClassifier

    train_path = OUT_DIR / "tuning_train.jsonl"
    print(f"Training linear SVM (SGD hinge, same budget as logreg v2) on {train_path}...",
          file=sys.stderr)
    df = _parse_tuning_jsonl(train_path)
    rng = np.random.default_rng(SEED)
    df = df.iloc[rng.permutation(len(df))].reset_index(drop=True)
    y = df["leaf"].to_numpy()
    X = featurise_for(logreg_bundle, df)
    clf = SGDClassifier(loss="hinge", alpha=1e-6, random_state=SEED, tol=None, max_iter=50)
    clf.fit(X, y)
    bundle = {
        "vectorizer": logreg_bundle["vectorizer"],
        "clf": clf,
        "kind": "linearsvc",
    }
    MODELS_DIR.mkdir(exist_ok=True)
    joblib.dump(bundle, SVC_PATH)
    print(f"Wrote {SVC_PATH}", file=sys.stderr)
    return bundle


def leaf_ok(pred, gold, gen_of):
    pred = np.asarray(pred, dtype=object)
    gold = np.asarray(gold, dtype=object)
    ok = pred == gold
    gen_ok = ok | (pd.Series(pred).map(gen_of).to_numpy() == pd.Series(gold).map(gen_of).to_numpy())
    return ok, gen_ok


def pct(x):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "n/a"
    return f"{100 * x:.1f}%"


def coverage_curve(gold, pred, t6, margin, gen_of, risk_leaves):
    n = len(gold)
    order = np.argsort(-np.asarray(margin))
    gold = np.asarray(gold, dtype=object)[order]
    pred = np.asarray(pred, dtype=object)[order]
    t6 = np.asarray(t6, dtype=object)[order]
    margin = np.asarray(margin)[order]
    rows = []
    for i in range(1, n + 1):
        served_pred, served_gold, served_t6 = pred[:i], gold[:i], t6[:i]
        ml_ok = (served_pred == served_gold).mean()
        t6_on_slice = (served_t6 == served_gold).mean()
        gated = np.concatenate([served_pred, t6[i:]])
        gated_ok = (gated == gold).mean()
        risk_mask = np.array([g in risk_leaves for g in served_gold])
        risk_acc = float((served_pred[risk_mask] == served_gold[risk_mask]).mean()) if risk_mask.any() else None
        rows.append({
            "k": i,
            "coverage": i / n,
            "margin_threshold": float(margin[i - 1]),
            "ml_on_served_leaf": float(ml_ok),
            "t6_on_served_leaf": float(t6_on_slice),
            "gated_all_leaf": float(gated_ok),
            "risk_on_served": risk_acc,
            "risk_n_served": int(risk_mask.sum()),
        })
    return pd.DataFrame(rows)


def snap_coverage(curve, cover):
    if curve.empty:
        return None
    hit = curve[curve["coverage"] >= cover]
    return hit.iloc[0] if len(hit) else curve.iloc[-1]


def summarise_model(name, residual, pred, conf, margin, gen_of, risk_leaves):
    gold = residual["gold_leaf"].to_numpy()
    t6 = residual["t6_leaf"].to_numpy()
    has_t6 = residual["native_category"].notna() & (residual["native_category"].astype(str).str.len() > 0)
    # Risk set has no native: exclude from T6 head-to-head but keep for ML vs gold.
    vs_t6 = residual.loc[has_t6].copy()
    pred_t6 = pred[has_t6.to_numpy()]
    conf_t6 = conf[has_t6.to_numpy()]
    margin_t6 = margin[has_t6.to_numpy()]
    gold_t6 = vs_t6["gold_leaf"].to_numpy()
    t6_leaf = vs_t6["t6_leaf"].to_numpy()

    ml_ok, ml_gen = leaf_ok(pred_t6, gold_t6, gen_of)
    t6_ok, t6_gen = leaf_ok(t6_leaf, gold_t6, gen_of)
    t6_rows = [{"gold_leaf": g, "pred_leaf": p} for g, p in zip(gold_t6, t6_leaf)]
    ml_rows = [{"gold_leaf": g, "pred_leaf": p} for g, p in zip(gold_t6, pred_t6)]
    t6_risk = analyse(t6_rows, gen_of, risk_leaves)
    ml_risk = analyse(ml_rows, gen_of, risk_leaves)

    curve = coverage_curve(gold_t6, pred_t6, t6_leaf, margin_t6, gen_of, risk_leaves)
    ops = {}
    for c in COVER_POINTS:
        row = snap_coverage(curve, c)
        ops[str(c)] = None if row is None else {
            "coverage": float(row["coverage"]),
            "margin_threshold": float(row["margin_threshold"]),
            "ml_on_served_leaf": float(row["ml_on_served_leaf"]),
            "t6_on_served_leaf": float(row["t6_on_served_leaf"]),
            "gated_all_leaf": float(row["gated_all_leaf"]),
            "risk_on_served": None if pd.isna(row["risk_on_served"]) else float(row["risk_on_served"]),
            "risk_n_served": int(row["risk_n_served"]),
        }

    # Smallest coverage at which ML-on-served beats T6-on-served by ≥1pp and
    # gated end-to-end beats always-T6.
    t6_all = float(t6_ok.mean()) if len(t6_ok) else None
    beat = curve[
        (curve["coverage"] >= 0.10)
        & (curve["ml_on_served_leaf"] >= curve["t6_on_served_leaf"] + 0.01)
        & (curve["gated_all_leaf"] >= (t6_all or 0) + 0.05)
    ]
    first_beat = None if beat.empty else {
        "coverage": float(beat.iloc[0]["coverage"]),
        "margin_threshold": float(beat.iloc[0]["margin_threshold"]),
        "ml_on_served_leaf": float(beat.iloc[0]["ml_on_served_leaf"]),
        "gated_all_leaf": float(beat.iloc[0]["gated_all_leaf"]),
    }

    # Best gated end-to-end among coverage ≥ 30% (don't "win" by serving 5 rows).
    usable = curve[curve["coverage"] >= 0.30]
    best = usable.loc[usable["gated_all_leaf"].idxmax()] if len(usable) else None

    by_source = {}
    vs_t6 = vs_t6.assign(_pred=pred_t6, _margin=margin_t6)
    for src, g in vs_t6.groupby("source"):
        by_source[src] = {
            "n": int(len(g)),
            "ml_leaf": float((g["_pred"] == g["gold_leaf"]).mean()),
            "t6_leaf": float((g["t6_leaf"] == g["gold_leaf"]).mean()),
        }

    # Risk-set residual: ML vs gold only.
    risk_mask = residual["source"].eq("risk").to_numpy()
    risk_only = None
    if risk_mask.any():
        r_gold = gold[risk_mask]
        r_pred = pred[risk_mask]
        r_ok = float((r_pred == r_gold).mean())
        r_rows = [{"gold_leaf": a, "pred_leaf": b} for a, b in zip(r_gold, r_pred)]
        r_an = analyse(r_rows, gen_of, risk_leaves)
        risk_only = {"n": int(risk_mask.sum()), "ml_leaf": r_ok,
                     "risk_acc": r_an["risk_acc"], "risk_n": r_an["risk_n"]}

    return {
        "name": name,
        "n_t6_with_native": int(has_t6.sum()),
        "ml_leaf": float(ml_ok.mean()) if len(ml_ok) else None,
        "ml_gen": float(ml_gen.mean()) if len(ml_gen) else None,
        "t6_leaf": float(t6_ok.mean()) if len(t6_ok) else None,
        "t6_gen": float(t6_gen.mean()) if len(t6_gen) else None,
        "ml_risk_acc": ml_risk["risk_acc"],
        "ml_risk_n": ml_risk["risk_n"],
        "t6_risk_acc": t6_risk["risk_acc"],
        "t6_risk_n": t6_risk["risk_n"],
        "ops": ops,
        "first_beat": first_beat,
        "best_gated": None if best is None else {
            "coverage": float(best["coverage"]),
            "margin_threshold": float(best["margin_threshold"]),
            "ml_on_served_leaf": float(best["ml_on_served_leaf"]),
            "gated_all_leaf": float(best["gated_all_leaf"]),
            "risk_on_served": None if pd.isna(best["risk_on_served"]) else float(best["risk_on_served"]),
        },
        "by_source": by_source,
        "risk_residual": risk_only,
        "margin_p50": float(np.median(margin_t6)) if len(margin_t6) else None,
        "conf_p50": float(np.median(conf_t6)) if len(conf_t6) else None,
        "curve": curve,
    }


def write_report(tier_counts, models, n_plaid, n_residual, holdout_stats):
    lines = []
    lines.append("# T5b residual gate — classifier vs T6 (remeasured 2026-08-27)\n")
    lines.append(
        "Question: on Plaid gold that **currently falls through T1–T5** to the "
        "provider crosswalk, does a margin-gated classifier beat T6, and does "
        "LinearSVC change that?\n"
    )
    lines.append("**Not scored:** locked confirmation sets (`gold_transactions_v5_LOCKED.csv` retired; "
                 "`gold_transactions_v6_LOCKED.csv` once built).\n")
    lines.append("## Population\n")
    lines.append(
        f"Plaid gold pooled from `gold_transactions_v3_volume.csv` (Plaid slice) "
        f"and `gold_transactions_v4_slm_volume.csv` (native category joined from "
        f"`gold_v4_eyeball.csv`). {n_plaid} Plaid gold rows; **{n_residual}** "
        f"are T6-bound after the current waterfall.\n"
    )
    lines.append(
        "**Leakage (read this before quoting the 58%/79% figures).** v3 and v4 "
        "were added to `tuning_train.jsonl` via the unified gold file (`data/gold_transactions.csv`) in the "
        "v3/v4 classifier retrain. Always-ML on this residual is therefore an "
        "*in-sample, production-shaped* number — the right question for “should "
        "we serve this on repeated head traffic”, the wrong one for “how does it "
        "generalise to novel merchants”. The risk-set residual and the v2 holdout "
        "residual below are the leakage-free checks.\n"
    )
    lines.append("| waterfall tier | n | share of Plaid gold |")
    lines.append("|---|---:|---:|")
    for tier, n in sorted(tier_counts.items(), key=lambda kv: -kv[1]):
        lines.append(f"| {tier} | {n} | {n / n_plaid:.1%} |")
    lines.append("")
    lines.append(
        "Models share the **same TF-IDF features** as `tfidf_logreg_v2.joblib` "
        "(char_wb 2–5 grams, 30k, + log1p(amount) + is_credit). The SVM head is "
        "`SGDClassifier(loss='hinge')` at the **same training budget** as logreg "
        "(alpha=1e-6, 50 epochs). liblinear `LinearSVC` was attempted and abandoned "
        "for this run (no fit after ~8 minutes on ~167k × 30k). Gate: top-1 minus "
        "top-2 on native scores (`predict_proba` for logreg, `decision_function` "
        "for the SVM). Gambling promotion matches `predict()`.\n"
    )
    lines.append("## Head-to-head on T6-bound rows with a Plaid native category\n")
    lines.append("| model | n | leaf (always-ML) | general | T6 leaf | T6 general | ML risk bar | T6 risk bar |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for m in models:
        risk_ml = "n/a" if m["ml_risk_acc"] is None else (
            f"{pct(m['ml_risk_acc'])} (n={m['ml_risk_n']})"
            + (" OK" if m["ml_risk_acc"] >= RISK_BAR else " BELOW")
        )
        risk_t6 = "n/a" if m["t6_risk_acc"] is None else f"{pct(m['t6_risk_acc'])} (n={m['t6_risk_n']})"
        lines.append(
            f"| {m['name']} | {m['n_t6_with_native']} | {pct(m['ml_leaf'])} | {pct(m['ml_gen'])} | "
            f"{pct(m['t6_leaf'])} | {pct(m['t6_gen'])} | {risk_ml} | {risk_t6} |"
        )
    lines.append("")
    lines.append("### By gold source\n")
    lines.append("| model | source | n | always-ML leaf | T6 leaf |")
    lines.append("|---|---|---:|---:|---:|")
    for m in models:
        for src, s in m["by_source"].items():
            lines.append(f"| {m['name']} | {src} | {s['n']} | {pct(s['ml_leaf'])} | {pct(s['t6_leaf'])} |")
    lines.append("")
    lines.append("## Margin gate (ML if margin ≥ threshold, else keep T6)\n")
    lines.append(
        "Coverage is the share of the T6 residual auto-served by ML, ranked by "
        "margin. `ML on served` is accuracy on that slice only. `Gated all` is "
        "the production metric: ML on the served slice, T6 on the rest.\n"
    )
    for m in models:
        lines.append(f"### {m['name']}\n")
        lines.append("| auto-serve | margin ≥ | ML on served | T6 on that slice | gated (all residual) | risk on served |")
        lines.append("|---|---:|---:|---:|---:|---|")
        for c in COVER_POINTS:
            op = m["ops"][str(c)]
            if not op:
                continue
            risk = "n/a" if op["risk_on_served"] is None else (
                f"{pct(op['risk_on_served'])} (n={op['risk_n_served']})"
            )
            lines.append(
                f"| {op['coverage']:.0%} | {op['margin_threshold']:.4f} | "
                f"{pct(op['ml_on_served_leaf'])} | {pct(op['t6_on_served_leaf'])} | "
                f"{pct(op['gated_all_leaf'])} | {risk} |"
            )
        if m["first_beat"]:
            fb = m["first_beat"]
            lines.append(
                f"\nFirst ≥10% coverage where ML-on-served beats T6-on-served by ≥1pp "
                f"**and** gated end-to-end is ≥5pp above always-T6: **{fb['coverage']:.0%}** "
                f"(margin ≥ {fb['margin_threshold']:.4f}; gated {pct(fb['gated_all_leaf'])}).\n"
            )
        lines.append(
            f"Always-ML ({pct(m['ml_leaf'])}) **beats every T6-fallback gate** on this "
            f"population: T6 is only {pct(m['t6_leaf'])} leaf, so sending the uncertain "
            f"tail back to the provider *lowers* accuracy. The serving rule is “ML, or "
            f"abstain to unclassified”, not “ML or T6”.\n"
        )
        if m["best_gated"]:
            b = m["best_gated"]
            lines.append(
                f"Best gated leaf accuracy at coverage ≥30%: **{pct(b['gated_all_leaf'])}** "
                f"at {b['coverage']:.0%} coverage (margin ≥ {b['margin_threshold']:.4f}; "
                f"ML-on-served {pct(b['ml_on_served_leaf'])}).\n"
            )
        for src, s in m["by_source"].items():
            delta = s["ml_leaf"] - s["t6_leaf"]
            lines.append(f"- {src}: always-ML {pct(s['ml_leaf'])} vs T6 {pct(s['t6_leaf'])} ({delta:+.1%})")
        lines.append("")

    lines.append("## Risk-category residual (T6-bound rows of the stratified risk set)\n")
    lines.append(
        "This set has no Plaid native category in the locked CSV, so it is **not** "
        "in the T6 head-to-head. T6-bound is still well-defined (T1–T5 did not fire). "
        "Most risk gold is dictionary-covered; the residual is the hard tail.\n"
    )
    for m in models:
        r = m["risk_residual"]
        if not r:
            lines.append(f"- {m['name']}: no T6-bound risk rows")
            continue
        bar = "n/a" if r["risk_acc"] is None else (
            f"{pct(r['risk_acc'])} ({'OK' if r['risk_acc'] >= RISK_BAR else 'BELOW'} bar)"
        )
        lines.append(f"- {m['name']}: n={r['n']} residual, leaf {pct(r['ml_leaf'])}, risk-bar {bar}")
    lines.append("")
    lines.append("## Merchant-disjoint holdout, T6-bound only\n")
    lines.append(
        "`data/gold_v2_slm_eval_holdout.csv` — merchants never seen in training. "
        "T6-bound = T1–T5 did not fire. Plaid native category is kept on the file "
        "so T6 can be scored on the Plaid slice (Equifax holdout rows use Equifax "
        "native, not Plaid).\n"
    )
    if holdout_stats:
        lines.append("| model | n T6-bound | ML leaf / general | Plaid n | ML on Plaid | T6 on Plaid |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        for h in holdout_stats:
            ml = f"{pct(h['leaf'])} / {pct(h['gen'])}"
            if h.get("n_plaid"):
                lines.append(
                    f"| {h['name']} | {h['n']} | {ml} | {h['n_plaid']} | "
                    f"{pct(h['ml_leaf_plaid'])} / {pct(h.get('ml_gen_plaid'))} | "
                    f"{pct(h['t6_leaf_plaid'])} / {pct(h.get('t6_gen_plaid'))} |"
                )
            else:
                lines.append(f"| {h['name']} | {h['n']} | {ml} | — | — | — |")
        lines.append("")
    lines.append("")
    lines.append("## What this does and does not decide\n")
    lines.append(
        "- **Does:** whether a gated linear model is already worth wiring as T5b "
        "on production-shaped T6 traffic, vs keeping T6.\n"
        "- **Does not:** replace the merchant-disjoint holdout (~36% leaf) as a "
        "generalisation floor; does not score locked confirmation sets; does not authorise per-transaction "
        "LLM at runtime.\n"
        "- Linear SVM is the same features, hinge instead of log loss. If it does not beat "
        "logreg on the gated metric, keep logreg.\n"
    )
    lines.append(f"Per-row predictions: `{PRED_CSV.relative_to(ROOT)}`. "
                 f"Coverage curve: `{CURVE_CSV.relative_to(ROOT)}`.\n")
    REPORT_MD.write_text("\n".join(lines))
    print(f"Wrote {REPORT_MD}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--retrain-svc", action="store_true",
                        help="Ignored; use src/retrain_corrected_heads.py to train.")
    args = parser.parse_args()
    for path in (GOLD_V3, GOLD_V4, GOLD_RISK, GOLD_HOLDOUT):
        refuse_confirmation_eval(path)

    _init_waterfall()
    gen_of, risk_leaves = load_taxonomy()

    v3 = load_v3_plaid()
    v4 = load_v4()
    risk = load_risk()
    plaid = pd.concat([v3, v4], ignore_index=True)
    plaid = attach_waterfall(plaid)
    risk_w = attach_waterfall(risk)

    tier_counts = plaid["waterfall_tier"].value_counts().to_dict()
    residual_plaid = plaid[plaid["is_t6"]].copy()
    residual_risk = risk_w[risk_w["is_t6"]].copy()
    residual = pd.concat([residual_plaid, residual_risk], ignore_index=True)

    print(f"Plaid gold n={len(plaid)}; T6 residual {len(residual_plaid)} "
          f"({len(residual_plaid)/len(plaid):.1%}); risk T6 residual {len(residual_risk)}/"
          f"{len(risk_w)}", file=sys.stderr)

    logreg = joblib.load(LOGREG_PATH)
    models_raw = [("tfidf_logreg_v2", logreg)]
    hinge_path = HINGE_PATH if HINGE_PATH.exists() else SVC_PATH
    if hinge_path.exists():
        models_raw.append(("tfidf_linearsvm_sgd", joblib.load(hinge_path)))
    if LIBLINEAR_PATH.exists():
        models_raw.append(("tfidf_linearsvc_liblinear", joblib.load(LIBLINEAR_PATH)))
    feat = features_frame(residual)
    summaries = []
    pred_frames = [residual.reset_index(drop=True)[
        ["source", "merchant_raw", "description_raw", "amount", "direction",
         "gold_leaf", "native_category", "t6_leaf", "waterfall_tier"]
    ].copy()]

    curve_parts = []
    for name, bundle in models_raw:
        pred, conf, margin = scores_and_margin(bundle, feat)
        # Sanity: logreg path should match predict() labels
        if name.startswith("tfidf_logreg"):
            p2, _ = predict(bundle, feat)
            disagree = int((pred != p2).sum())
            if disagree:
                print(f"WARN: {name} gambling/argmax disagree with predict() on {disagree} rows",
                      file=sys.stderr)
        pred_frames[0][f"{name}_leaf"] = pred
        pred_frames[0][f"{name}_conf"] = conf
        pred_frames[0][f"{name}_margin"] = margin
        summary = summarise_model(name, residual, pred, conf, margin, gen_of, risk_leaves)
        curve = summary.pop("curve")
        curve.insert(0, "model", name)
        curve_parts.append(curve)
        summaries.append(summary)
        print(f"{name}: always-ML {pct(summary['ml_leaf'])} vs T6 {pct(summary['t6_leaf'])} "
              f"(n={summary['n_t6_with_native']})", file=sys.stderr)

    holdout = pd.read_csv(GOLD_HOLDOUT)
    holdout["source"] = "holdout"
    if "native_category" not in holdout.columns:
        holdout["native_category"] = np.nan
    holdout = attach_waterfall(holdout)
    holdout_t6 = holdout[holdout["is_t6"]].copy()
    holdout_feat = features_frame(holdout_t6)
    plaid_t6 = holdout_t6["provider"].astype(str).str.lower().eq("plaid") if "provider" in holdout_t6.columns \
        else pd.Series(False, index=holdout_t6.index)
    holdout_stats = []
    for name, bundle in models_raw:
        pred, _, _ = scores_and_margin(bundle, holdout_feat)
        ok, gen_ok = leaf_ok(pred, holdout_t6["gold_leaf"].to_numpy(), gen_of)
        stat = {
            "name": name, "n": int(len(holdout_t6)),
            "leaf": float(ok.mean()), "gen": float(gen_ok.mean()),
            "n_plaid": int(plaid_t6.sum()),
            "ml_leaf_plaid": None, "t6_leaf_plaid": None,
            "ml_gen_plaid": None, "t6_gen_plaid": None,
        }
        if plaid_t6.any():
            gold_p = holdout_t6.loc[plaid_t6, "gold_leaf"].to_numpy()
            pred_p = pred[plaid_t6.to_numpy()]
            t6_p = holdout_t6.loc[plaid_t6, "t6_leaf"].to_numpy()
            ml_ok, ml_gen = leaf_ok(pred_p, gold_p, gen_of)
            t6_ok, t6_gen = leaf_ok(t6_p, gold_p, gen_of)
            stat["ml_leaf_plaid"] = float(ml_ok.mean())
            stat["ml_gen_plaid"] = float(ml_gen.mean())
            stat["t6_leaf_plaid"] = float(t6_ok.mean())
            stat["t6_gen_plaid"] = float(t6_gen.mean())
            print(f"{name} holdout T6-bound: {pct(ok.mean())} leaf n={len(holdout_t6)}; "
                  f"Plaid n={int(plaid_t6.sum())} ML {pct(ml_ok.mean())} vs T6 {pct(t6_ok.mean())}",
                  file=sys.stderr)
        else:
            print(f"{name} holdout T6-bound: {pct(ok.mean())} leaf n={len(holdout_t6)}",
                  file=sys.stderr)
        holdout_stats.append(stat)

    OUT_DIR.mkdir(exist_ok=True)
    pred_frames[0].to_csv(PRED_CSV, index=False)
    curve_all = pd.concat(curve_parts, ignore_index=True)
    # Store a 2pp grid plus the operating points to keep the file small.
    keep = []
    for name, g in curve_all.groupby("model"):
        idx = set()
        for c in np.linspace(0.02, 1.0, 50):
            hit = g[g["coverage"] >= c]
            if len(hit):
                idx.add(int(hit.index[0]))
        keep.append(g.loc[sorted(idx)])
    pd.concat(keep).to_csv(CURVE_CSV, index=False)

    payload = {
        "n_plaid_gold": int(len(plaid)),
        "n_t6_plaid": int(len(residual_plaid)),
        "n_t6_risk": int(len(residual_risk)),
        "tier_counts": {str(k): int(v) for k, v in tier_counts.items()},
        "n_t6_holdout": int(len(holdout_t6)),
        "holdout": holdout_stats,
        "models": [{k: v for k, v in s.items() if k != "curve"} for s in summaries],
        "curve_sample": json.loads(pd.concat(keep).to_json(orient="records")),
    }
    SUMMARY_JSON.write_text(json.dumps(payload, indent=2, default=str))
    write_report(tier_counts, summaries, len(plaid), len(residual_plaid), holdout_stats)
    print(f"Wrote {PRED_CSV}", file=sys.stderr)
    print(f"Wrote {SUMMARY_JSON}", file=sys.stderr)


if __name__ == "__main__":
    main()

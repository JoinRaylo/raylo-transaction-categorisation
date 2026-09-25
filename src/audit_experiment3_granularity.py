"""Stress-test the Experiment 3 category-granularity ladder.

This is deliberately separate from ``experiment3_granularity_ladder.py`` so
the published point-estimate artefacts are not overwritten.  It uses the same
local proposal-feature and long-format ladder artefacts, then adds the checks
that are needed before treating the curve as decision-grade evidence:

* repeated XGBoost seeds;
* applicant-level stratified bootstrap intervals;
* paired intervals for differences between rungs;
* a like-for-like live-feature comparator refitted on the full train window;
* the existing inner-train-only live comparator for reconciliation.

The audit still inherits the original experiment's important limitation: the
275-leaf transaction categoriser is held fixed and its outputs are rolled up.
It does not simulate retraining the categoriser at each rung, nor can it undo
the post-OOT merchant/taxonomy freeze issue from the saved aggregate data.

Usage:
    python src/audit_experiment3_granularity.py
    python src/audit_experiment3_granularity.py --seeds 0,17,42,73,101 \
        --bootstraps 2000
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import experiment3_granularity_ladder as ladder  # noqa: E402
import experiment3_xgb_pipeline as x3  # noqa: E402
from credit_metrics import signed_gini  # noqa: E402
import eval_protection  # noqa: E402

OUT_JSON = x3.OUT_DIR / "experiment3_granularity_stress_test.json"
OUT_PREDICTIONS = x3.OUT_DIR / "experiment3_granularity_stress_predictions.parquet"

TARGETS = [
    ("month3", x3.M3_Y, x3.M3_TRAIN_START, x3.M3_TRAIN_END, x3.M3_OOT_END),
    ("month6", x3.M6_Y, x3.M6_TRAIN_START, x3.M6_TRAIN_END, x3.M6_OOT_END),
]


@dataclass
class Prepared:
    train: pd.DataFrame
    oot: pd.DataFrame
    inner_train: pd.DataFrame
    inner_valid: pd.DataFrame
    kept: list[str]


def _x(frame: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    return frame[cols].apply(pd.to_numeric, errors="coerce")


def _xgb(seed: int, n_estimators: int = 500, early_stopping: bool = False):
    import xgboost as xgb

    kwargs = dict(
        n_estimators=n_estimators,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.85,
        colsample_bytree=0.7,
        min_child_weight=15,
        reg_lambda=2.0,
        objective="binary:logistic",
        eval_metric="auc",
        tree_method="hist",
        n_jobs=-1,
        random_state=seed,
    )
    if early_stopping:
        kwargs["early_stopping_rounds"] = 40
    return xgb.XGBClassifier(**kwargs)


def _fit_early(
    prepared: Prepared,
    ycol: str,
    cols: list[str],
    seed: int,
):
    y_tr = prepared.inner_train[ycol].astype(int)
    y_va = prepared.inner_valid[ycol].astype(int)
    pos = max(int(y_tr.sum()), 1)
    neg = max(int((y_tr == 0).sum()), 1)
    model = _xgb(seed, early_stopping=True)
    model.set_params(scale_pos_weight=neg / pos)
    model.fit(
        _x(prepared.inner_train, cols),
        y_tr,
        eval_set=[(_x(prepared.inner_valid, cols), y_va)],
        verbose=False,
    )
    return model


def _refit_predict(
    prepared: Prepared,
    ycol: str,
    cols: list[str],
    best_iteration: int,
    seed: int,
) -> np.ndarray:
    y = prepared.train[ycol].astype(int)
    pos = max(int(y.sum()), 1)
    neg = max(int((y == 0).sum()), 1)
    model = _xgb(seed, n_estimators=max(best_iteration, 50))
    model.set_params(scale_pos_weight=neg / pos)
    model.fit(_x(prepared.train, cols), y)
    return model.predict_proba(_x(prepared.oot, cols))[:, 1]


def _prepare(
    df: pd.DataFrame,
    ycol: str,
    train_start: str,
    train_end: str,
    oot_end: str,
    cols: list[str],
) -> Prepared:
    train = x3._drop_immature_months(
        x3._window(df, train_start, train_end, ycol), ycol)
    oot = x3._drop_immature_months(
        x3._window(df, train_end, oot_end, ycol), ycol)
    inner_train, inner_valid, _ = x3._inner_cut(train)
    _, kept = ladder._screen_simple(inner_train, ycol, cols)
    if len(kept) < 3:
        raise RuntimeError(f"Only {len(kept)} features survived for {ycol}")
    return Prepared(train, oot, inner_train, inner_valid, kept)


def _fit_rung_seed(
    prepared: Prepared,
    ycol: str,
    seed: int,
    cap: int | None,
) -> tuple[np.ndarray, list[str]]:
    first = _fit_early(prepared, ycol, prepared.kept, seed)
    if cap is None:
        selected = prepared.kept
        early = first
    else:
        selected, _ = x3._gain_prune(first, prepared.kept, max_keep=cap)
        early = _fit_early(prepared, ycol, selected, seed)
    best = int(getattr(early, "best_iteration", None) or early.n_estimators)
    return _refit_predict(prepared, ycol, selected, best, seed), selected


def _prepare_live(
    df: pd.DataFrame,
    ycol: str,
    train_start: str,
    train_end: str,
    oot_end: str,
) -> tuple[Prepared, list[str]]:
    live_cols = [f"live_{c}" for c in x3.LIVE_FEATURES if f"live_{c}" in df.columns]
    train = x3._drop_immature_months(
        x3._window(df, train_start, train_end, ycol), ycol)
    oot = x3._drop_immature_months(
        x3._window(df, train_end, oot_end, ycol), ycol)
    train = train[train["is_plaid"] == 1].copy()
    oot = oot[oot["is_plaid"] == 1].copy()
    inner_train, inner_valid, _ = x3._inner_cut(train)
    return Prepared(train, oot, inner_train, inner_valid, live_cols), live_cols


def _fit_live_seed(
    prepared: Prepared,
    ycol: str,
    cols: list[str],
    seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Return full-refit and published inner-train-only predictions."""
    early = _fit_early(prepared, ycol, cols, seed)
    inner_only = early.predict_proba(_x(prepared.oot, cols))[:, 1]
    best = int(getattr(early, "best_iteration", None) or early.n_estimators)
    full = _refit_predict(prepared, ycol, cols, best, seed)
    return full, inner_only


def _seed_summary(values: list[float]) -> dict:
    a = np.asarray(values, dtype=float)
    return {
        "mean": round(float(a.mean()), 4),
        "sd": round(float(a.std(ddof=1)), 4) if len(a) > 1 else 0.0,
        "min": round(float(a.min()), 4),
        "max": round(float(a.max()), 4),
    }


def _bootstrap_indices(y: np.ndarray, n_boot: int, seed: int):
    rng = np.random.default_rng(seed)
    pos = np.flatnonzero(y == 1)
    neg = np.flatnonzero(y == 0)
    for _ in range(n_boot):
        yield np.concatenate([
            rng.choice(pos, size=len(pos), replace=True),
            rng.choice(neg, size=len(neg), replace=True),
        ])


def _bootstrap_gini(
    y: np.ndarray,
    pred: np.ndarray,
    indices: list[np.ndarray],
) -> dict:
    vals = np.asarray([
        2.0 * roc_auc_score(y[idx], pred[idx]) - 1.0 for idx in indices
    ])
    lo, hi = np.quantile(vals, [0.025, 0.975])
    return {
        "estimate": round(float(signed_gini(pred, y)), 4),
        "ci95": [round(float(lo), 4), round(float(hi), 4)],
    }


def _bootstrap_delta(
    y: np.ndarray,
    pred_a: np.ndarray,
    pred_b: np.ndarray,
    indices: list[np.ndarray],
) -> dict:
    vals = []
    for idx in indices:
        ga = 2.0 * roc_auc_score(y[idx], pred_a[idx]) - 1.0
        gb = 2.0 * roc_auc_score(y[idx], pred_b[idx]) - 1.0
        vals.append(ga - gb)
    vals = np.asarray(vals)
    lo, hi = np.quantile(vals, [0.025, 0.975])
    estimate = signed_gini(pred_a, y) - signed_gini(pred_b, y)
    return {
        "estimate": round(float(estimate), 4),
        "ci95": [round(float(lo), 4), round(float(hi), 4)],
        "p_boot_two_sided": round(
            float(2 * min((vals <= 0).mean(), (vals >= 0).mean())), 4),
    }


def _validate_inputs(base: pd.DataFrame, long_df: pd.DataFrame) -> dict:
    taxonomy = pd.read_csv(x3.TAXONOMY_PATH)
    mapping = pd.read_csv(ladder.LADDER_PATH)
    joined = taxonomy[["detailed_category", "general_category", "cash_flow_type"]].merge(
        mapping, on="detailed_category", how="outer", indicator=True)
    return {
        "taxonomy_rows": int(len(taxonomy)),
        "ladder_rows": int(len(mapping)),
        "ladder_duplicate_leaves": int(mapping["detailed_category"].duplicated().sum()),
        "ladder_join_not_both": int((joined["_merge"] != "both").sum()),
        "general_mapping_mismatches": int(
            (joined["general_category"] != joined["l1_general_29"]).sum()),
        "cashflow_mapping_mismatches": int(
            (joined["cash_flow_type"] != joined["l4_cashflow_7"]).sum()),
        "base_rows": int(len(base)),
        "base_duplicate_proposal_provider": int(
            base.duplicated(["financial_proposal_id", "provider"]).sum()),
        "long_rows": int(len(long_df)),
        "long_duplicate_grain": int(long_df.duplicated(
            ["financial_proposal_id", "provider", "rung", "grp"]).sum()),
        "long_null_debit_amounts": int(long_df["g_debit_amt"].isna().sum()),
        "possible_current_groups": int(
            mapping.assign(current=mapping.apply(
                lambda r: r["detailed_category"]
                if r["detailed_category"] in x3.KEY_LEAVES
                else r["l1_general_29"], axis=1))["current"].nunique()),
        "key_leaves": int(len(x3.KEY_LEAVES)),
    }


def run(seeds: list[int], n_boot: int) -> dict:
    started = time.time()
    # B04 gated off: the parquet feature stores predate bound provenance.
    eval_protection.gate(
        "audit_experiment3_granularity.run",
        "unbound feature store; rebuild under the protected-release guard",
    )
    long_df = pd.read_parquet(ladder.LONG_PARQUET)
    base = pd.read_parquet(x3.FEAT_PARQUET)
    base["financial_proposal_id"] = base["financial_proposal_id"].astype(str)
    base = x3._prepare(base)

    keep_base = ladder.META + ["created"] + ladder.SPINE + ladder.DIMS + [
        c for c in base.columns if c.startswith("live_")]
    spine = base[[c for c in dict.fromkeys(keep_base) if c in base.columns]].copy()

    result: dict = {
        "seeds": seeds,
        "bootstraps": n_boot,
        "limitations": [
            "The 275-leaf transaction categoriser is fixed; rungs are post-hoc rollups.",
            "Saved aggregates cannot enforce an as-of taxonomy/dictionary freeze before OOT.",
            "Only one hand-designed merge hierarchy is tested.",
            "Applicant bootstrap intervals and seed dispersion are reported separately; neither covers taxonomy-label uncertainty.",
        ],
        "input_validation": _validate_inputs(base, long_df),
        "targets": {},
    }
    prediction_frames = []

    # Build each wide rung once; training windows are then sliced per target.
    rung_frames: dict[str, tuple[pd.DataFrame, list[str]]] = {}
    for rung, _ in ladder.RUNGS:
        wide = ladder._pivot_rung(long_df, rung)
        frame = spine.merge(wide, on=["financial_proposal_id", "provider"], how="left")
        block = [c for c in wide.columns if c.startswith(f"{rung}__")]
        frame[block] = frame[block].fillna(0)
        rung_frames[rung] = (x3._prepare(frame), block)

    for target_i, (target, ycol, train_start, train_end, oot_end) in enumerate(TARGETS):
        print(f"\n{target}", file=sys.stderr)
        live_prepared, live_cols = _prepare_live(
            spine, ycol, train_start, train_end, oot_end)
        y_oot = live_prepared.oot[ycol].astype(int).to_numpy()
        ids = live_prepared.oot["financial_proposal_id"].astype(str).to_numpy()
        target_out = {
            "oot_n": int(len(y_oot)),
            "oot_bads": int(y_oot.sum()),
            "live": {},
            "rungs": {},
            "comparisons": [],
        }
        all_predictions: dict[str, np.ndarray] = {}

        full_seed_preds, inner_seed_preds = [], []
        for seed in seeds:
            full, inner = _fit_live_seed(live_prepared, ycol, live_cols, seed)
            full_seed_preds.append(full)
            inner_seed_preds.append(inner)
        full_ens = np.mean(full_seed_preds, axis=0)
        inner_ens = np.mean(inner_seed_preds, axis=0)
        all_predictions["live_full_refit"] = full_ens
        all_predictions["live_inner_only"] = inner_ens
        target_out["live"] = {
            "full_refit_seed_gini": _seed_summary([
                signed_gini(p, y_oot) for p in full_seed_preds]),
            "inner_only_seed_gini": _seed_summary([
                signed_gini(p, y_oot) for p in inner_seed_preds]),
        }

        for rung, _ in ladder.RUNGS:
            frame, block = rung_frames[rung]
            cols = [c for c in block + ladder.SPINE + ladder.DIMS if c in frame.columns]
            prepared = _prepare(
                frame, ycol, train_start, train_end, oot_end, cols)
            if not np.array_equal(
                prepared.oot["financial_proposal_id"].astype(str).to_numpy(), ids):
                raise RuntimeError(f"OOT alignment differs for {target}/{rung}")
            target_out["rungs"][rung] = {}
            for cap_name, cap in [("cap50", 50), ("uncapped", None)]:
                seed_preds, selected_by_seed = [], []
                for seed in seeds:
                    pred, selected = _fit_rung_seed(prepared, ycol, seed, cap)
                    seed_preds.append(pred)
                    selected_by_seed.append(selected)
                ensemble = np.mean(seed_preds, axis=0)
                key = f"{rung}|{cap_name}"
                all_predictions[key] = ensemble
                ginis = [signed_gini(p, y_oot) for p in seed_preds]
                selected_sets = [set(x) for x in selected_by_seed]
                union = set().union(*selected_sets)
                intersection = set.intersection(*selected_sets)
                target_out["rungs"][rung][cap_name] = {
                    "seed_gini": _seed_summary(ginis),
                    "ensemble_gini": round(float(signed_gini(ensemble, y_oot)), 4),
                    "selected_count": [len(x) for x in selected_by_seed],
                    "selection_union": len(union),
                    "selection_intersection": len(intersection),
                }
                print(
                    f"  {rung:>14} {cap_name:>8}: "
                    f"{target_out['rungs'][rung][cap_name]['seed_gini']} "
                    f"ensemble={target_out['rungs'][rung][cap_name]['ensemble_gini']}",
                    file=sys.stderr,
                )

        boot_idx = list(_bootstrap_indices(y_oot, n_boot, 20260901 + target_i))
        target_out["live"]["full_refit_bootstrap"] = _bootstrap_gini(
            y_oot, full_ens, boot_idx)
        target_out["live"]["inner_only_bootstrap"] = _bootstrap_gini(
            y_oot, inner_ens, boot_idx)

        for rung, _ in ladder.RUNGS:
            for cap_name in ("cap50", "uncapped"):
                key = f"{rung}|{cap_name}"
                target_out["rungs"][rung][cap_name]["bootstrap"] = _bootstrap_gini(
                    y_oot, all_predictions[key], boot_idx)
                target_out["comparisons"].append({
                    "a": key,
                    "b": "live_full_refit",
                    "delta": _bootstrap_delta(
                        y_oot, all_predictions[key], full_ens, boot_idx),
                })

        # These are the claims made in the existing report: flat through 17,
        # then degradation below 9.  Paired intervals make the claims testable.
        for cap_name in ("cap50", "uncapped"):
            for rung in ("l0_leaf_275", "l1_general_29", "l2_budget_17"):
                a = f"{rung}|{cap_name}"
                b = f"l0_current_69|{cap_name}"
                target_out["comparisons"].append({
                    "a": a,
                    "b": b,
                    "delta": _bootstrap_delta(
                        y_oot, all_predictions[a], all_predictions[b], boot_idx),
                })
            for rung in ("l3_macro_9", "l4_cashflow_7", "l5_minimal_4"):
                a = f"{rung}|{cap_name}"
                b = f"l2_budget_17|{cap_name}"
                target_out["comparisons"].append({
                    "a": a,
                    "b": b,
                    "delta": _bootstrap_delta(
                        y_oot, all_predictions[a], all_predictions[b], boot_idx),
                })

        pred_frame = pd.DataFrame({
            "financial_proposal_id": ids,
            "target": target,
            "y": y_oot,
            **all_predictions,
        })
        prediction_frames.append(pred_frame)
        result["targets"][target] = target_out

    result["elapsed_seconds"] = round(time.time() - started, 1)
    x3.OUT_DIR.mkdir(exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, indent=2))
    pd.concat(prediction_frames, ignore_index=True).to_parquet(
        OUT_PREDICTIONS, index=False)
    print(f"\nwrote {OUT_JSON}", file=sys.stderr)
    print(f"wrote {OUT_PREDICTIONS}", file=sys.stderr)
    return result


def audit_same20(seeds: list[int], n_boot: int) -> dict:
    """Closest available categorisation-only comparison.

    Both models use Plaid-only training, the same 20 business definitions and
    the same XGBoost procedure.  One side uses the saved Plaid-native features;
    the other rebuilds those definitions from the taxonomy leaves.
    """
    # B04 gated off: the parquet feature stores predate bound provenance.
    eval_protection.gate(
        "audit_experiment3_granularity.audit_same20",
        "unbound feature store; rebuild under the protected-release guard",
    )
    base = x3._prepare(pd.read_parquet(x3.FEAT_PARQUET))
    live_cols = [f"live_{c}" for c in x3.LIVE_FEATURES]
    our_cols = [x3.LIVE_ANALOG[c] for c in x3.LIVE_FEATURES]
    missing = [c for c in live_cols + our_cols if c not in base.columns]
    if missing:
        raise RuntimeError(f"Missing same-20 columns: {missing}")

    out: dict = {}
    for target_i, (target, ycol, train_start, train_end, oot_end) in enumerate(TARGETS):
        train = x3._drop_immature_months(
            x3._window(base, train_start, train_end, ycol), ycol)
        oot = x3._drop_immature_months(
            x3._window(base, train_end, oot_end, ycol), ycol)
        train = train[train["is_plaid"] == 1].copy()
        oot = oot[oot["is_plaid"] == 1].copy()
        inner_train, inner_valid, _ = x3._inner_cut(train)
        y = oot[ycol].astype(int).to_numpy()

        predictions: dict[str, list[np.ndarray]] = {"live20": [], "taxonomy20": []}
        selected = {"live20": live_cols, "taxonomy20": our_cols}
        for name, cols in selected.items():
            prepared = Prepared(train, oot, inner_train, inner_valid, cols)
            for seed in seeds:
                early = _fit_early(prepared, ycol, cols, seed)
                best = int(getattr(early, "best_iteration", None) or early.n_estimators)
                predictions[name].append(
                    _refit_predict(prepared, ycol, cols, best, seed))

        live_ensemble = np.mean(predictions["live20"], axis=0)
        taxonomy_ensemble = np.mean(predictions["taxonomy20"], axis=0)
        indices = list(_bootstrap_indices(y, n_boot, 20260911 + target_i))
        out[target] = {
            "oot_n": int(len(oot)),
            "oot_bads": int(y.sum()),
            "live20_seed_gini": _seed_summary([
                signed_gini(p, y) for p in predictions["live20"]]),
            "taxonomy20_seed_gini": _seed_summary([
                signed_gini(p, y) for p in predictions["taxonomy20"]]),
            "live20_bootstrap": _bootstrap_gini(y, live_ensemble, indices),
            "taxonomy20_bootstrap": _bootstrap_gini(y, taxonomy_ensemble, indices),
            "taxonomy_minus_live": _bootstrap_delta(
                y, taxonomy_ensemble, live_ensemble, indices),
        }
        print(f"same20 {target}: {out[target]}", file=sys.stderr)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", default="0,17,42")
    parser.add_argument("--bootstraps", type=int, default=1000)
    parser.add_argument("--same20-only", action="store_true")
    args = parser.parse_args()
    seeds = [int(x.strip()) for x in args.seeds.split(",") if x.strip()]
    if not seeds:
        raise SystemExit("At least one seed is required")
    if args.bootstraps < 100:
        raise SystemExit("Use at least 100 bootstrap replicates")
    if args.same20_only:
        current = json.loads(OUT_JSON.read_text()) if OUT_JSON.exists() else {}
        current["same20"] = audit_same20(seeds, args.bootstraps)
        OUT_JSON.write_text(json.dumps(current, indent=2))
        print(f"wrote {OUT_JSON}", file=sys.stderr)
    else:
        result = run(seeds, args.bootstraps)
        result["same20"] = audit_same20(seeds, args.bootstraps)
        OUT_JSON.write_text(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

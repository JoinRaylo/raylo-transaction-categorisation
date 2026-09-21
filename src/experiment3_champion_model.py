"""Experiment 3 development champion search.

This is a deliberately stricter follow-up to ``experiment3_xgb_pipeline.py``.
It searches on rolling, pre-OOT Plaid windows and touches the published OOT
window only once, after the model recipe and blend have been selected.  It does
not score the locked v5/v6 evaluation sets.

The search adds every observed 275-leaf aggregate, leaf-normalised features,
provider/recency weighting, two gradient-boosting implementations, repeated
seeds and an OOF-selected blend.

Usage:
    uv run python src/experiment3_champion_model.py features
    uv run python src/experiment3_champion_model.py search
    uv run python src/experiment3_champion_model.py all
"""
from __future__ import annotations

import argparse
import itertools
import json
import pathlib
import sys
import time
from dataclasses import asdict, dataclass

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import experiment3_granularity_ladder as ladder  # noqa: E402
import experiment3_xgb_pipeline as x3  # noqa: E402
from credit_metrics import signed_gini  # noqa: E402
import eval_protection  # noqa: E402

FEATURES_PARQUET = x3.OUT_DIR / "experiment3_champion_features.parquet"
SEARCH_JSON = x3.OUT_DIR / "experiment3_champion_search.json"
OOF_PARQUET = x3.OUT_DIR / "experiment3_champion_oof_predictions.parquet"
FINAL_PARQUET = x3.OUT_DIR / "experiment3_champion_oot_predictions.parquet"
VALIDATION_JSON = x3.OUT_DIR / "experiment3_champion_validation.json"
MODEL_M3 = x3.OUT_DIR / "experiment3_champion_month3.joblib"
MODEL_M6 = x3.OUT_DIR / "experiment3_champion_month6.joblib"
REPORT = ROOT / "data" / "experiment3_champion_model_report.md"

SEEDS = (0, 17, 42)
META = [
    "proposal_id",
    "financial_proposal_id",
    "financial_proposal_created_at",
    "provider",
    x3.M3_Y,
    x3.M6_Y,
]

TARGETS = {
    "month3": {
        "ycol": x3.M3_Y,
        "train_start": x3.M3_TRAIN_START,
        "train_end": x3.M3_TRAIN_END,
        "oot_end": x3.M3_OOT_END,
        "folds": [
            ("2025-08-01", "2025-11-01"),
            ("2025-11-01", "2026-01-01"),
            ("2026-01-01", "2026-03-01"),
        ],
    },
    "month6": {
        "ycol": x3.M6_Y,
        "train_start": x3.M6_TRAIN_START,
        "train_end": x3.M6_TRAIN_END,
        "oot_end": x3.M6_OOT_END,
        "folds": [
            ("2025-08-01", "2025-09-01"),
            ("2025-09-01", "2025-10-01"),
            ("2025-10-01", "2025-11-01"),
        ],
    },
}


@dataclass(frozen=True)
class Config:
    name: str
    family: str
    depth: int
    learning_rate: float
    min_child: float
    subsample: float
    colsample: float
    reg_lambda: float
    reg_alpha: float
    class_power: float
    equifax_weight: float
    recency_half_life: float | None
    num_leaves: int | None = None


CONFIGS = [
    Config("xgb_incumbent", "xgb", 4, .05, 15, .85, .70, 2, 0, 1, 1, None),
    Config("xgb_d3_balanced", "xgb", 3, .03, 20, .90, .75, 10, .1, .5, .5, 24),
    Config("xgb_d2_recent", "xgb", 2, .03, 10, .90, .85, 10, .1, 0, .35, 12),
    Config("xgb_d5_regularised", "xgb", 5, .025, 30, .80, .60, 20, .5, .5, .5, 24),
    Config("lgb_d3_balanced", "lgb", 3, .03, 100, .90, .75, 10, .1, .5, .5, 24, 7),
    Config("lgb_d4_balanced", "lgb", 4, .03, 100, .90, .75, 10, .1, .5, .5, 24, 15),
    Config("lgb_d5_weighted", "lgb", 5, .025, 100, .85, .65, 20, .5, 1, .5, 12, 31),
    Config("lgb_d4_recent", "lgb", 4, .03, 200, .90, .80, 20, .2, 0, .25, 12, 15),
]


def _safe_divide(num: np.ndarray, den: np.ndarray) -> np.ndarray:
    out = np.zeros_like(num, dtype=np.float32)
    np.divide(num, den, out=out, where=np.isfinite(den) & (den != 0))
    out[~np.isfinite(out)] = 0
    return out


def build_features() -> pd.DataFrame:
    """Build a local, proposal-level feature matrix from the saved long data."""
    print("Building champion feature matrix...", file=sys.stderr)
    # B04 gated off: the parquet feature stores predate bound provenance.
    eval_protection.gate(
        "experiment3_champion_model.build_features",
        "unbound feature store; rebuild under the protected-release guard",
    )
    base = x3._prepare(pd.read_parquet(x3.FEAT_PARQUET))
    base["financial_proposal_id"] = base["financial_proposal_id"].astype(str)
    base_cols = x3._candidate_cols(base)
    base[base_cols] = base[base_cols].apply(pd.to_numeric, errors="coerce").astype("float32")

    long_df = pd.read_parquet(ladder.LONG_PARQUET)
    leaf = long_df[long_df["rung"].eq("l0_leaf_275")].copy()
    leaf["financial_proposal_id"] = leaf["financial_proposal_id"].astype(str)
    idx = ["financial_proposal_id", "provider"]
    raw_frames: dict[str, pd.DataFrame] = {}
    suffixes = {
        "g_months": "months",
        "g_n": "n",
        "g_debit_n": "debit_n",
        "g_debit_amt": "debit_amt",
        "g_credit_amt": "credit_amt",
    }
    for source, suffix in suffixes.items():
        wide = leaf.pivot_table(
            index=idx, columns="grp", values=source, aggfunc="sum", fill_value=0)
        wide = wide.sort_index(axis=1).astype("float32")
        wide.columns = [f"leaf__{c}__{suffix}" for c in wide.columns]
        raw_frames[suffix] = wide
    raw = pd.concat(raw_frames.values(), axis=1).reset_index()
    del long_df, leaf

    out = base.merge(raw, on=idx, how="left")
    raw_cols = [c for c in raw.columns if c.startswith("leaf__")]
    out[raw_cols] = out[raw_cols].fillna(0).astype("float32")

    leaves = sorted({c.split("__")[1] for c in raw_cols})
    arrays = {
        suffix: out[[f"leaf__{leaf}__{suffix}" for leaf in leaves]].to_numpy(
            dtype=np.float32, copy=False)
        for suffix in suffixes.values()
    }
    denominators = {
        "month_share": out["total_months"].to_numpy(np.float32)[:, None],
        "txn_share": out["n_txns"].to_numpy(np.float32)[:, None],
        "debit_txn_share": out["n_debits"].to_numpy(np.float32)[:, None],
        "debit_amt_share": out["total_debit_amt"].to_numpy(np.float32)[:, None],
        "credit_amt_share": out["total_credit_amt"].to_numpy(np.float32)[:, None],
    }
    numerators = {
        "month_share": arrays["months"],
        "txn_share": arrays["n"],
        "debit_txn_share": arrays["debit_n"],
        "debit_amt_share": arrays["debit_amt"],
        "credit_amt_share": arrays["credit_amt"],
    }
    derived = []
    for suffix in denominators:
        values = _safe_divide(numerators[suffix], denominators[suffix])
        derived.append(pd.DataFrame(
            values,
            columns=[f"leaf__{leaf}__{suffix}" for leaf in leaves],
            index=out.index,
        ))

    tax = pd.read_csv(x3.TAXONOMY_PATH)
    risk_mask = (
        tax["detailed_category"].isin(x3.KEY_LEAVES)
        | tax["is_debt_related"].astype(bool)
        | tax["is_priority_debt"].astype(bool)
        | tax["is_age_restricted"].astype(bool)
        | ~tax["risk_flag"].fillna("none").isin(["none", ""])
    )
    risk_leaves = sorted(set(tax.loc[risk_mask, "detailed_category"]) & set(leaves))
    risk_idx = [leaves.index(leaf) for leaf in risk_leaves]
    credit_n = arrays["n"][:, risk_idx] - arrays["debit_n"][:, risk_idx]
    for suffix, values in [
        ("avg_debit", _safe_divide(
            arrays["debit_amt"][:, risk_idx], arrays["debit_n"][:, risk_idx])),
        ("avg_credit", _safe_divide(
            arrays["credit_amt"][:, risk_idx], credit_n)),
    ]:
        derived.append(pd.DataFrame(
            values,
            columns=[f"leaf__{leaf}__{suffix}" for leaf in risk_leaves],
            index=out.index,
        ))
    out = pd.concat([out] + derived, axis=1)
    del raw, derived, arrays

    out.replace([np.inf, -np.inf], np.nan, inplace=True)
    x3.OUT_DIR.mkdir(exist_ok=True)
    out.to_parquet(FEATURES_PARQUET, index=False, compression="zstd")
    n_raw = sum(c.endswith(tuple(f"__{s}" for s in suffixes.values())) for c in out.columns)
    n_derived = sum(c.startswith("leaf__") for c in out.columns) - n_raw
    print(
        f"  {len(out):,} proposals, {len(base_cols):,} current candidates, "
        f"{n_raw:,} raw leaf and {n_derived:,} normalised leaf features -> "
        f"{FEATURES_PARQUET}", file=sys.stderr)
    return out


def _feature_sets(df: pd.DataFrame) -> dict[str, list[str]]:
    base = [c for c in x3._candidate_cols(df) if not c.startswith("leaf__")]
    raw_suffixes = ("__months", "__n", "__debit_n", "__debit_amt", "__credit_amt")
    raw = [c for c in df.columns if c.startswith("leaf__") and c.endswith(raw_suffixes)]
    rich = [c for c in df.columns if c.startswith("leaf__")]
    return {
        "current": base,
        "leaf_raw": list(dict.fromkeys(base + raw)),
        "leaf_rich": list(dict.fromkeys(base + rich)),
    }


def _x(frame: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    return frame[cols]


def _sample_weight(frame: pd.DataFrame, y: pd.Series, cfg: Config) -> np.ndarray:
    w = np.ones(len(frame), dtype=np.float64)
    w[frame["provider"].to_numpy() == "equifax"] *= cfg.equifax_weight
    if cfg.recency_half_life:
        age_days = (frame["created"].max() - frame["created"]).dt.total_seconds() / 86400
        w *= np.power(0.5, age_days.to_numpy() / (30.4375 * cfg.recency_half_life))
    pos = max(float(y.sum()), 1.0)
    neg = max(float((y == 0).sum()), 1.0)
    w[y.to_numpy(dtype=int) == 1] *= (neg / pos) ** cfg.class_power
    return w


def _new_model(cfg: Config, seed: int, n_estimators: int, early: bool):
    if cfg.family == "xgb":
        import xgboost as xgb

        return xgb.XGBClassifier(
            n_estimators=n_estimators,
            max_depth=cfg.depth,
            learning_rate=cfg.learning_rate,
            min_child_weight=cfg.min_child,
            subsample=cfg.subsample,
            colsample_bytree=cfg.colsample,
            reg_lambda=cfg.reg_lambda,
            reg_alpha=cfg.reg_alpha,
            objective="binary:logistic",
            eval_metric="auc",
            tree_method="hist",
            n_jobs=-1,
            random_state=seed,
            early_stopping_rounds=60 if early else None,
        )

    import lightgbm as lgb

    return lgb.LGBMClassifier(
        n_estimators=n_estimators,
        num_leaves=cfg.num_leaves,
        max_depth=cfg.depth,
        learning_rate=cfg.learning_rate,
        min_child_samples=int(cfg.min_child),
        subsample=cfg.subsample,
        subsample_freq=1,
        colsample_bytree=cfg.colsample,
        reg_lambda=cfg.reg_lambda,
        reg_alpha=cfg.reg_alpha,
        objective="binary",
        n_jobs=-1,
        random_state=seed,
        verbosity=-1,
    )


def _fit_early(
    train: pd.DataFrame,
    valid: pd.DataFrame,
    ycol: str,
    cols: list[str],
    cfg: Config,
    seed: int,
) -> tuple[object, int]:
    model = _new_model(cfg, seed, 1600, early=cfg.family == "xgb")
    y_train = train[ycol].astype(int)
    y_valid = valid[ycol].astype(int)
    kwargs = {
        "sample_weight": _sample_weight(train, y_train, cfg),
        "eval_set": [(_x(valid, cols), y_valid)],
    }
    if cfg.family == "xgb":
        kwargs["verbose"] = False
    else:
        import lightgbm as lgb

        kwargs["callbacks"] = [lgb.early_stopping(60, verbose=False), lgb.log_evaluation(0)]
    model.fit(_x(train, cols), y_train, **kwargs)
    best = getattr(model, "best_iteration_", None)
    if best is None:
        xgb_best = getattr(model, "best_iteration", None)
        best = int(xgb_best) + 1 if xgb_best is not None else 400
    return model, max(int(best), 25)


def _fit_refit(
    train: pd.DataFrame,
    ycol: str,
    cols: list[str],
    cfg: Config,
    seed: int,
    n_estimators: int,
):
    model = _new_model(cfg, seed, n_estimators, early=False)
    y = train[ycol].astype(int)
    model.fit(_x(train, cols), y, sample_weight=_sample_weight(train, y, cfg))
    return model


def _inner_split(train: pd.DataFrame, ycol: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    cut = train["created"].quantile(.85)
    inner = train[train["created"] < cut]
    stop = train[train["created"] >= cut]
    if inner.empty or stop.empty or stop[ycol].nunique() < 2:
        raise RuntimeError("Invalid chronological early-stopping split")
    return inner, stop


def _cv_candidate(
    df: pd.DataFrame,
    target: str,
    cols: list[str],
    feature_set: str,
    cfg: Config,
    seed: int = 0,
) -> tuple[dict, pd.DataFrame]:
    spec = TARGETS[target]
    ycol = spec["ycol"]
    rows = []
    fold_metrics = []
    best_iterations = []
    for fold_no, (val_start, val_end) in enumerate(spec["folds"], 1):
        train = x3._window(df, spec["train_start"], val_start, ycol)
        valid = x3._window(df, val_start, val_end, ycol)
        valid = valid[valid["provider"].eq("plaid")].copy()
        if len(valid) < 100 or valid[ycol].nunique() < 2:
            raise RuntimeError(f"{target} fold {fold_no} has an invalid validation sample")
        inner, stop = _inner_split(train, ycol)
        _, best = _fit_early(inner, stop, ycol, cols, cfg, seed)
        model = _fit_refit(train, ycol, cols, cfg, seed, best)
        pred = model.predict_proba(_x(valid, cols))[:, 1]
        gini = float(signed_gini(pred, valid[ycol].astype(int)))
        fold_metrics.append({
            "fold": fold_no,
            "train_end": val_start,
            "valid_end": val_end,
            "train_n": len(train),
            "valid_n": len(valid),
            "valid_bads": int(valid[ycol].sum()),
            "best_iteration": best,
            "gini": round(gini, 4),
        })
        best_iterations.append(best)
        rows.append(pd.DataFrame({
            "financial_proposal_id": valid["financial_proposal_id"].astype(str),
            "target": target,
            "fold": fold_no,
            "y": valid[ycol].astype(int).to_numpy(),
            "prediction": pred,
        }))
    ginis = np.asarray([r["gini"] for r in fold_metrics])
    oof = pd.concat(rows, ignore_index=True)
    pooled = float(signed_gini(oof["prediction"], oof["y"]))
    result = {
        "candidate": f"{cfg.name}|{feature_set}",
        "config": cfg.name,
        "family": cfg.family,
        "feature_set": feature_set,
        "n_features": len(cols),
        "folds": fold_metrics,
        "mean_gini": round(float(ginis.mean()), 4),
        "sd_gini": round(float(ginis.std(ddof=1)), 4),
        "min_gini": round(float(ginis.min()), 4),
        "pooled_gini": round(pooled, 4),
        "selection_score": round(float(ginis.mean() - .25 * ginis.std(ddof=1)), 4),
        "median_best_iteration": int(np.median(best_iterations)),
    }
    oof["candidate"] = result["candidate"]
    return result, oof


def _blend_result(
    name: str,
    oof_a: pd.DataFrame,
    oof_b: pd.DataFrame,
    weight_a: float,
) -> tuple[dict, pd.DataFrame]:
    keys = ["financial_proposal_id", "target", "fold", "y"]
    a = oof_a[keys + ["prediction"]].rename(columns={"prediction": "a"})
    b = oof_b[keys + ["prediction"]].rename(columns={"prediction": "b"})
    out = a.merge(b, on=keys, validate="one_to_one")
    out["prediction"] = weight_a * out["a"] + (1 - weight_a) * out["b"]
    folds = []
    for fold, g in out.groupby("fold"):
        folds.append({"fold": int(fold), "gini": round(float(signed_gini(g.prediction, g.y)), 4)})
    ginis = np.asarray([r["gini"] for r in folds])
    result = {
        "candidate": name,
        "component_a_weight": round(weight_a, 2),
        "folds": folds,
        "mean_gini": round(float(ginis.mean()), 4),
        "sd_gini": round(float(ginis.std(ddof=1)), 4),
        "min_gini": round(float(ginis.min()), 4),
        "pooled_gini": round(float(signed_gini(out.prediction, out.y)), 4),
        "selection_score": round(float(ginis.mean() - .25 * ginis.std(ddof=1)), 4),
    }
    out["candidate"] = name
    return result, out[keys + ["prediction", "candidate"]]


def _choose_blend(
    oof_a: pd.DataFrame,
    oof_b: pd.DataFrame,
    name_a: str,
    name_b: str,
) -> tuple[dict, pd.DataFrame]:
    options = []
    for weight in np.linspace(0, 1, 11):
        name = f"blend[{weight:.1f}*{name_a}+{1-weight:.1f}*{name_b}]"
        options.append(_blend_result(name, oof_a, oof_b, float(weight)))
    return max(options, key=lambda x: x[0]["selection_score"])


def _final_fit_predict(
    df: pd.DataFrame,
    target: str,
    cols: list[str],
    cfg: Config,
) -> tuple[list[object], np.ndarray, pd.DataFrame, list[int]]:
    spec = TARGETS[target]
    ycol = spec["ycol"]
    train = x3._window(df, spec["train_start"], spec["train_end"], ycol)
    oot = x3._window(df, spec["train_end"], spec["oot_end"], ycol)
    inner, stop = _inner_split(train, ycol)
    models, predictions, iterations = [], [], []
    for seed in SEEDS:
        _, best = _fit_early(inner, stop, ycol, cols, cfg, seed)
        model = _fit_refit(train, ycol, cols, cfg, seed, best)
        models.append(model)
        predictions.append(model.predict_proba(_x(oot, cols))[:, 1])
        iterations.append(best)
    return models, np.mean(predictions, axis=0), oot, iterations


def _bootstrap_delta(
    y: np.ndarray,
    challenger: np.ndarray,
    reference: np.ndarray,
    n_boot: int = 2000,
    seed: int = 20260901,
) -> dict:
    rng = np.random.default_rng(seed)
    pos = np.flatnonzero(y == 1)
    neg = np.flatnonzero(y == 0)
    values = []
    for _ in range(n_boot):
        idx = np.concatenate([
            rng.choice(pos, len(pos), replace=True),
            rng.choice(neg, len(neg), replace=True),
        ])
        values.append(
            2 * roc_auc_score(y[idx], challenger[idx])
            - 2 * roc_auc_score(y[idx], reference[idx]))
    lo, hi = np.quantile(values, [.025, .975])
    delta = signed_gini(challenger, y) - signed_gini(reference, y)
    return {
        "delta": round(float(delta), 4),
        "ci95": [round(float(lo), 4), round(float(hi), 4)],
        "positive_probability": round(float(np.mean(np.asarray(values) > 0)), 4),
    }


def _published_predictions(target: str, oot: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    model_path = x3.MODEL_M3_50 if target == "month3" else x3.MODEL_M6_50
    incumbent = joblib.load(model_path)
    incumbent_pred = incumbent["model"].predict_proba(_x(oot, incumbent["features"]))[:, 1]

    stress = pd.read_parquet(
        x3.OUT_DIR / "experiment3_granularity_stress_predictions.parquet")
    live = stress[stress["target"].eq(target)][
        ["financial_proposal_id", "live_full_refit"]].copy()
    live["financial_proposal_id"] = live["financial_proposal_id"].astype(str)
    joined = oot[["financial_proposal_id"]].copy()
    joined["financial_proposal_id"] = joined["financial_proposal_id"].astype(str)
    joined = joined.merge(live, on="financial_proposal_id", how="left", validate="one_to_one")
    if joined["live_full_refit"].isna().any():
        raise RuntimeError("Live reference predictions do not cover the final OOT")
    return incumbent_pred, joined["live_full_refit"].to_numpy()


def run_search(df: pd.DataFrame | None = None) -> dict:
    if df is None:
        # B04 gated off: the parquet feature stores predate bound provenance.
        eval_protection.gate(
            "experiment3_champion_model.run_search",
            "unbound feature store; rebuild under the protected-release guard",
        )
        df = x3._prepare(pd.read_parquet(FEATURES_PARQUET))
    elif "created" not in df:
        df = x3._prepare(df)
    feature_sets = _feature_sets(df)
    cfg_by_name = {c.name: c for c in CONFIGS}
    print("Feature sets: " + ", ".join(
        f"{name}={len(cols):,}" for name, cols in feature_sets.items()), file=sys.stderr)
    output = {
        "method": {
            "selection": "rolling pre-OOT Plaid validation; mean GINI - 0.25*fold SD",
            "folds": {k: v["folds"] for k, v in TARGETS.items()},
            "seeds_final": list(SEEDS),
            "locked_v5_v6_scored": False,
        },
        "feature_counts": {k: len(v) for k, v in feature_sets.items()},
        "configs": {c.name: asdict(c) for c in CONFIGS},
        "targets": {},
    }
    all_oof = []

    for target in TARGETS:
        print(f"\n{target}: stage 1 — tune model recipe on current features", file=sys.stderr)
        stage1, oof_map = [], {}
        for cfg in CONFIGS:
            t0 = time.time()
            result, oof = _cv_candidate(
                df, target, feature_sets["current"], "current", cfg)
            stage1.append(result)
            oof_map[result["candidate"]] = oof
            print(
                f"  {result['candidate']:<36} mean={result['mean_gini']:+.4f} "
                f"sd={result['sd_gini']:.4f} score={result['selection_score']:+.4f} "
                f"[{time.time()-t0:.0f}s]", file=sys.stderr)

        selected_cfgs = []
        for family in ("xgb", "lgb"):
            ranked = sorted(
                [r for r in stage1 if r["family"] == family],
                key=lambda r: r["selection_score"], reverse=True)
            selected_cfgs.extend(cfg_by_name[r["config"]] for r in ranked[:2])

        print(f"{target}: stage 2 — test all-leaf feature families", file=sys.stderr)
        stage2 = list(stage1)
        for cfg, feature_set in itertools.product(selected_cfgs, ("leaf_raw", "leaf_rich")):
            t0 = time.time()
            result, oof = _cv_candidate(df, target, feature_sets[feature_set], feature_set, cfg)
            stage2.append(result)
            oof_map[result["candidate"]] = oof
            print(
                f"  {result['candidate']:<36} mean={result['mean_gini']:+.4f} "
                f"sd={result['sd_gini']:.4f} score={result['selection_score']:+.4f} "
                f"[{time.time()-t0:.0f}s]", file=sys.stderr)

        best_by_family = {}
        for family in ("xgb", "lgb"):
            best_by_family[family] = max(
                [r for r in stage2 if r["family"] == family],
                key=lambda r: r["selection_score"])
        a, b = best_by_family["xgb"], best_by_family["lgb"]
        blend, blend_oof = _choose_blend(
            oof_map[a["candidate"]], oof_map[b["candidate"]],
            a["candidate"], b["candidate"])
        all_oof.extend(oof_map.values())
        all_oof.append(blend_oof)

        print(
            f"{target}: blend winner {blend['component_a_weight']:.1f} XGB / "
            f"{1-blend['component_a_weight']:.1f} LGB, "
            f"CV score={blend['selection_score']:+.4f}", file=sys.stderr)

        final_components = []
        final_predictions = []
        final_oot = None
        for family, candidate in best_by_family.items():
            cfg = cfg_by_name[candidate["config"]]
            cols = feature_sets[candidate["feature_set"]]
            models, pred, oot, iterations = _final_fit_predict(df, target, cols, cfg)
            final_oot = oot
            final_predictions.append(pred)
            final_components.append({
                "family": family,
                "candidate": candidate["candidate"],
                "config": asdict(cfg),
                "features": cols,
                "models": models,
                "iterations": iterations,
            })
        weight_xgb = blend["component_a_weight"]
        champion_pred = weight_xgb * final_predictions[0] + (1 - weight_xgb) * final_predictions[1]
        y = final_oot[TARGETS[target]["ycol"]].astype(int).to_numpy()
        incumbent_pred, live_pred = _published_predictions(target, final_oot)
        oot_metrics = {
            "n": len(y),
            "bads": int(y.sum()),
            "champion_gini": round(float(signed_gini(champion_pred, y)), 4),
            "best_xgb_gini": round(float(signed_gini(final_predictions[0], y)), 4),
            "best_lgb_gini": round(float(signed_gini(final_predictions[1], y)), 4),
            "published_capped_gini": round(float(signed_gini(incumbent_pred, y)), 4),
            "live_reconstruction_gini": round(float(signed_gini(live_pred, y)), 4),
            "champion_vs_published": _bootstrap_delta(y, champion_pred, incumbent_pred),
            "champion_vs_live": _bootstrap_delta(y, champion_pred, live_pred),
        }
        model_path = MODEL_M3 if target == "month3" else MODEL_M6
        joblib.dump({
            "target": TARGETS[target]["ycol"],
            "components": final_components,
            "xgb_weight": weight_xgb,
            "seeds": list(SEEDS),
            "selection": blend,
            "development_only": True,
        }, model_path, compress=3)

        pred_frame = pd.DataFrame({
            "financial_proposal_id": final_oot["financial_proposal_id"].astype(str),
            "target": target,
            "y": y,
            "champion": champion_pred,
            "best_xgb": final_predictions[0],
            "best_lgb": final_predictions[1],
            "published_capped": incumbent_pred,
            "live_full_refit": live_pred,
        })
        output["targets"][target] = {
            "stage1": stage1,
            "stage2": stage2,
            "best_by_family": best_by_family,
            "blend": blend,
            "oot": oot_metrics,
            "model_path": str(model_path.relative_to(ROOT)),
        }
        output["targets"][target]["_predictions"] = pred_frame

    oof_all = pd.concat(all_oof, ignore_index=True)
    oof_all.to_parquet(OOF_PARQUET, index=False, compression="zstd")
    final_all = pd.concat(
        [output["targets"][t].pop("_predictions") for t in TARGETS],
        ignore_index=True)
    final_all.to_parquet(FINAL_PARQUET, index=False, compression="zstd")
    SEARCH_JSON.write_text(json.dumps(output, indent=2))
    _write_report(output)
    return output


def _fmt_ci(comp: dict) -> str:
    lo, hi = comp["ci95"]
    return f"{comp['delta']:+.3f} ({lo:+.3f} to {hi:+.3f})"


def _logit(values: np.ndarray) -> np.ndarray:
    p = np.clip(np.asarray(values, dtype=float), 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p)).reshape(-1, 1)


def predict_artifact(
    artifact: dict,
    frame: pd.DataFrame,
    calibrated: bool = True,
) -> np.ndarray:
    """Score a saved champion artifact; apply its pre-OOT calibration by default."""
    component_predictions = []
    for component in artifact["components"]:
        seed_predictions = [
            model.predict_proba(_x(frame, component["features"]))[:, 1]
            for model in component["models"]
        ]
        component_predictions.append(np.mean(seed_predictions, axis=0))
    raw = (
        artifact["xgb_weight"] * component_predictions[0]
        + (1 - artifact["xgb_weight"]) * component_predictions[1]
    )
    calibration = artifact.get("calibration")
    if not calibrated or not calibration:
        return raw
    linear = calibration["intercept"] + calibration["slope"] * _logit(raw).ravel()
    return 1 / (1 + np.exp(-linear))


def validate_artifacts(result: dict | None = None) -> dict:
    """Re-score serialised models, add OOF Platt scaling and robustness checks."""
    # B04 gated off: the parquet feature stores predate bound provenance.
    eval_protection.gate(
        "experiment3_champion_model.validate_artifacts",
        "unbound feature store; rebuild under the protected-release guard",
    )
    if result is None:
        result = json.loads(SEARCH_JSON.read_text())
    df = x3._prepare(pd.read_parquet(FEATURES_PARQUET))
    oof = pd.read_parquet(OOF_PARQUET)
    saved = pd.read_parquet(FINAL_PARQUET)
    validated_frames = []
    validation = {"targets": {}, "locked_v5_v6_scored": False}

    for target, spec in TARGETS.items():
        ycol = spec["ycol"]
        oot = x3._window(df, spec["train_end"], spec["oot_end"], ycol)
        target_saved = saved[saved["target"].eq(target)].copy().reset_index(drop=True)
        if not np.array_equal(
            oot["financial_proposal_id"].astype(str).to_numpy(),
            target_saved["financial_proposal_id"].astype(str).to_numpy(),
        ):
            raise RuntimeError(f"{target}: saved predictions are not row-aligned")
        y = oot[ycol].astype(int).to_numpy()
        model_path = MODEL_M3 if target == "month3" else MODEL_M6
        artifact = joblib.load(model_path)
        component_predictions = []
        component_audits = []
        for component in artifact["components"]:
            seed_predictions = []
            seed_ginis = []
            importance = []
            for seed, model in zip(artifact["seeds"], component["models"]):
                pred = model.predict_proba(_x(oot, component["features"]))[:, 1]
                seed_predictions.append(pred)
                seed_ginis.append({
                    "seed": int(seed),
                    "gini": round(float(signed_gini(pred, y)), 4),
                })
                if component["family"] == "lgb":
                    gain = model.booster_.feature_importance(importance_type="gain")
                else:
                    gain = model.feature_importances_
                gain = np.asarray(gain, dtype=float)
                importance.append(gain / gain.sum() if gain.sum() else gain)
            mean_pred = np.mean(seed_predictions, axis=0)
            mean_gain = np.mean(importance, axis=0)
            order = np.argsort(-mean_gain)[:20]
            component_predictions.append(mean_pred)
            component_audits.append({
                "family": component["family"],
                "candidate": component["candidate"],
                "seed_ginis": seed_ginis,
                "ensemble_gini": round(float(signed_gini(mean_pred, y)), 4),
                "top_importance": [
                    {
                        "feature": component["features"][i],
                        "normalised_gain": round(float(mean_gain[i]), 6),
                    }
                    for i in order
                ],
            })
        raw = (
            artifact["xgb_weight"] * component_predictions[0]
            + (1 - artifact["xgb_weight"]) * component_predictions[1]
        )
        max_diff = float(np.max(np.abs(raw - target_saved["champion"].to_numpy())))
        if max_diff > 1e-10:
            raise RuntimeError(f"{target}: serialised model mismatch {max_diff}")

        blend_name = result["targets"][target]["blend"]["candidate"]
        calibration_rows = oof[
            oof["target"].eq(target) & oof["candidate"].eq(blend_name)]
        calibrator = LogisticRegression(C=1e6, solver="lbfgs")
        calibrator.fit(_logit(calibration_rows["prediction"].to_numpy()),
                       calibration_rows["y"].astype(int))
        calibrated = calibrator.predict_proba(_logit(raw))[:, 1]
        artifact["calibration"] = {
            "method": "Platt scaling on rolling pre-OOT blend predictions",
            "intercept": float(calibrator.intercept_[0]),
            "slope": float(calibrator.coef_[0, 0]),
            "oof_n": int(len(calibration_rows)),
            "oof_bad_rate": float(calibration_rows["y"].mean()),
        }
        joblib.dump(artifact, model_path, compress=3)
        target_saved["champion_calibrated"] = calibrated
        validated_frames.append(target_saved)

        probability_metrics = {}
        for name, pred in {
            "champion_raw": raw,
            "champion_calibrated": calibrated,
            "published_capped": target_saved["published_capped"].to_numpy(),
            "live_full_refit": target_saved["live_full_refit"].to_numpy(),
        }.items():
            probability_metrics[name] = {
                "gini": round(float(signed_gini(pred, y)), 4),
                "mean_prediction": round(float(np.mean(pred)), 4),
                "brier": round(float(brier_score_loss(y, pred)), 4),
                "log_loss": round(float(log_loss(y, pred)), 4),
            }
        monthly = []
        months = oot["created"].dt.strftime("%Y-%m").to_numpy()
        for month in sorted(set(months)):
            mask = months == month
            monthly.append({
                "month": month,
                "n": int(mask.sum()),
                "bads": int(y[mask].sum()),
                "bad_rate": round(float(y[mask].mean()), 4),
                "gini": round(float(signed_gini(raw[mask], y[mask])), 4),
            })
        validation["targets"][target] = {
            "event_rate": round(float(y.mean()), 4),
            "serialised_prediction_max_abs_difference": max_diff,
            "components": component_audits,
            "probability_metrics": probability_metrics,
            "monthly": monthly,
            "calibration": artifact["calibration"],
        }

    pd.concat(validated_frames, ignore_index=True).to_parquet(
        FINAL_PARQUET, index=False, compression="zstd")
    VALIDATION_JSON.write_text(json.dumps(validation, indent=2))
    _write_report(result, validation)
    print(f"Validated artefacts -> {VALIDATION_JSON}", file=sys.stderr)
    return validation


def _write_report(result: dict, validation: dict | None = None) -> None:
    lines = [
        "# Experiment 3 — development champion model search",
        "",
        "## Executive read",
        "",
    ]
    for target in TARGETS:
        t = result["targets"][target]
        o = t["oot"]
        lines.extend([
            f"- **{target}:** champion **{o['champion_gini']:.3f}** GINI "
            f"vs published capped taxonomy model **{o['published_capped_gini']:.3f}** "
            f"and reconstructed live model **{o['live_reconstruction_gini']:.3f}**. "
            f"Paired uplift vs published: {_fmt_ci(o['champion_vs_published'])}; "
            f"vs live: {_fmt_ci(o['champion_vs_live'])}.",
        ])
    lines.extend([
        "",
        "This is the strongest **development** recipe found in the saved data. It is",
        "not a promotion result: the historical OOT windows have already been used",
        "in earlier Experiment 3 work. Locked v5/v6 were not scored.",
        "",
        "## What was searched",
        "",
        f"- Feature views: current **{result['feature_counts']['current']:,}**, "
        f"all-leaf raw **{result['feature_counts']['leaf_raw']:,}**, and all-leaf "
        f"normalised **{result['feature_counts']['leaf_rich']:,}** candidates.",
        "- Eight initial XGBoost/LightGBM recipes varied depth, leaf size,",
        "regularisation, class weighting, Equifax down-weighting and recency decay.",
        "- Selection used three rolling Plaid-only validation windows before the",
        "published OOT. Every fold used a separate chronological early-stopping",
        "slice, then refit on all data available before that validation window.",
        "- The final two-family blend and its weight were selected from OOF results.",
        "Final estimates average seeds 0, 17 and 42.",
        "",
        "## Pre-OOT model selection",
        "",
    ])
    for target in TARGETS:
        t = result["targets"][target]
        lines.extend([
            f"### {target}",
            "",
            "| Candidate | Features | Mean GINI | Fold SD | Worst fold | Selection score |",
            "|---|---:|---:|---:|---:|---:|",
        ])
        top = sorted(t["stage2"], key=lambda r: r["selection_score"], reverse=True)[:10]
        for r in top:
            lines.append(
                f"| `{r['candidate']}` | {r['n_features']} | {r['mean_gini']:.3f} | "
                f"{r['sd_gini']:.3f} | {r['min_gini']:.3f} | {r['selection_score']:.3f} |")
        b = t["blend"]
        lines.extend([
            "",
            f"Chosen blend: **{b['component_a_weight']:.1f} XGBoost / "
            f"{1-b['component_a_weight']:.1f} LightGBM**, mean fold GINI "
            f"**{b['mean_gini']:.3f}**, fold SD **{b['sd_gini']:.3f}**.",
            "",
        ])
    lines.extend([
        "## Final saved-window confirmation",
        "",
        "| Target | n / bads | Champion | Best XGB | Best LGB | Published capped | Live reconstruction |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ])
    for target in TARGETS:
        o = result["targets"][target]["oot"]
        lines.append(
            f"| {target} | {o['n']:,} / {o['bads']:,} | **{o['champion_gini']:.3f}** | "
            f"{o['best_xgb_gini']:.3f} | {o['best_lgb_gini']:.3f} | "
            f"{o['published_capped_gini']:.3f} | {o['live_reconstruction_gini']:.3f} |")
    lines.extend([
        "",
        "The paired intervals above are applicant-stratified 2,000-sample bootstrap",
        "intervals on the saved OOT. They quantify retrospective uncertainty, not",
        "future-drift or categoriser-freeze uncertainty.",
        "",
    ])
    if validation:
        lines.extend([
            "## Reproducibility, time stability and calibration",
            "",
            "The saved model objects reproduce every saved champion prediction to",
            "floating-point precision. GINI by final-window calendar month:",
            "",
            "| Target | Month | n / bads | GINI |",
            "|---|---|---:|---:|",
        ])
        for target in TARGETS:
            for row in validation["targets"][target]["monthly"]:
                lines.append(
                    f"| {target} | {row['month']} | {row['n']:,} / {row['bads']:,} | "
                    f"{row['gini']:.3f} |")
        lines.extend([
            "",
            "| Target | Component | Seed GINI range | Ensemble GINI |",
            "|---|---|---:|---:|",
        ])
        for target in TARGETS:
            for component in validation["targets"][target]["components"]:
                seed_values = [r["gini"] for r in component["seed_ginis"]]
                lines.append(
                    f"| {target} | {component['family']} | {min(seed_values):.3f}–"
                    f"{max(seed_values):.3f} | {component['ensemble_gini']:.3f} |")
        lines.extend([
            "",
            "Class/provider weighting improves rank ordering but inflates raw scores.",
            "The saved artefacts therefore include Platt scaling fitted only on the",
            "rolling pre-OOT blend predictions. It leaves GINI unchanged and improves",
            "the saved-window probability metrics:",
            "",
            "| Target | Event rate | Mean raw | Mean calibrated | Brier raw | Brier calibrated |",
            "|---|---:|---:|---:|---:|---:|",
        ])
        for target in TARGETS:
            v = validation["targets"][target]
            raw = v["probability_metrics"]["champion_raw"]
            cal = v["probability_metrics"]["champion_calibrated"]
            lines.append(
                f"| {target} | {v['event_rate']:.3f} | {raw['mean_prediction']:.3f} | "
                f"{cal['mean_prediction']:.3f} | {raw['brier']:.4f} | {cal['brier']:.4f} |")
        lines.extend(["", "## Promotion gate"])
    else:
        lines.extend(["## Promotion gate"])
    lines.extend([
        "",
        "Freeze the taxonomy, merchant dictionary, residual classifier, feature SQL",
        "and selected recipe before a new outcome window. Promote only if that single",
        "prospective test clears the pre-agreed GINI/non-inferiority bars, calibration",
        "checks and category-level risk recall checks. Do not tune again on that window.",
        "",
        "## Artefacts",
        "",
        f"- `{FEATURES_PARQUET.relative_to(ROOT)}`",
        f"- `{SEARCH_JSON.relative_to(ROOT)}`",
        f"- `{OOF_PARQUET.relative_to(ROOT)}`",
        f"- `{FINAL_PARQUET.relative_to(ROOT)}`",
        f"- `{VALIDATION_JSON.relative_to(ROOT)}`",
        f"- `{MODEL_M3.relative_to(ROOT)}`",
        f"- `{MODEL_M6.relative_to(ROOT)}`",
        "",
        "Reproduce with `uv run python src/experiment3_champion_model.py all`.",
    ])
    REPORT.write_text("\n".join(lines) + "\n")
    print(f"Wrote {REPORT}", file=sys.stderr)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["features", "search", "audit", "report", "all"],
                        nargs="?", default="all")
    args = parser.parse_args(argv)
    if args.stage in ("features", "all"):
        build_features()
    if args.stage in ("search", "all"):
        run_search()
        validate_artifacts()
    if args.stage == "audit":
        validate_artifacts()
    if args.stage == "report":
        validation = json.loads(VALIDATION_JSON.read_text()) if VALIDATION_JSON.exists() else None
        _write_report(json.loads(SEARCH_JSON.read_text()), validation)


if __name__ == "__main__":
    main()

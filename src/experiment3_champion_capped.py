"""Experiment 3 champion, feature-capped.

Question (Carlos, 7 Sep 2026): the development champion uses 1,654 to 3,150 input
features (690 to 1,449 with non-zero gain). How much of its +0.054 GINI over the
published 50-feature model survives a hard cap of 50 features?

Method, per target:
  1. Take the champion's chosen recipe per family and its blend weight from
     ``experiment3_champion_search.json`` (nothing re-tuned here).
  2. Rank features on the pre-OOT training window only: fit each family's recipe
     (inner-split early stopping, seeds 0/17/42) on its champion feature set, take
     gain importance normalised to sum 1 per fit, average across seeds and
     families.  Both components then share the same top-K columns, so "K features"
     means K columns end to end.
  3. For each cap K: rolling pre-OOT validation (same folds as the champion search)
     for information, then the final 3-seed fit on the full training window and a
     single score on the saved OOT window.  Deltas vs the saved champion, the
     published 50-feature model and the live full refit are paired bootstraps on
     the identical rows.

Does not score the locked v5/v6 sets.  Writes
``data/experiment3_champion_capped_report.md`` and
``outputs/experiment3_champion_capped_{month3,month6}_50.joblib``.

    uv run python src/experiment3_champion_capped.py --caps 50 100 200
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict

import joblib
import numpy as np
import pandas as pd

import experiment3_champion_model as ch
import experiment3_xgb_pipeline as x3
from credit_metrics import signed_gini

ROOT = ch.ROOT
REPORT = ROOT / "data" / "experiment3_champion_capped_report.md"
RESULT_JSON = x3.OUT_DIR / "experiment3_champion_capped.json"


def _gain(model, cols: list[str]) -> np.ndarray:
    """Normalised gain per column (sums to 1), zeros for unused columns."""
    if hasattr(model, "get_booster"):
        booster = model.get_booster()
        names = booster.feature_names or [f"f{i}" for i in range(len(cols))]
        score = booster.get_score(importance_type="gain")
        g = np.array([score.get(n, 0.0) for n in names], dtype=float)
    else:
        g = np.asarray(model.booster_.feature_importance("gain"), dtype=float)
    if g.shape[0] != len(cols):
        raise RuntimeError(f"gain length {g.shape[0]} != cols {len(cols)}")
    total = g.sum()
    return g / total if total > 0 else g


def rank_features(df: pd.DataFrame, target: str, components: dict) -> pd.Series:
    """Average normalised gain over seeds and families, pre-OOT training window only."""
    spec = ch.TARGETS[target]
    ycol = spec["ycol"]
    train = x3._window(df, spec["train_start"], spec["train_end"], ycol)
    inner, stop = ch._inner_split(train, ycol)
    scores: dict[str, list[float]] = {}
    for family, comp in components.items():
        cfg = comp["cfg"]
        cols = comp["cols"]
        for seed in ch.SEEDS:
            t0 = time.time()
            _, best = ch._fit_early(inner, stop, ycol, cols, cfg, seed)
            model = ch._fit_refit(train, ycol, cols, cfg, seed, best)
            g = _gain(model, cols)
            for c, v in zip(cols, g):
                scores.setdefault(c, []).append(float(v))
            print(f"  rank {target} {family} seed={seed} trees={best} "
                  f"nonzero={(g > 0).sum()} [{time.time()-t0:.0f}s]", file=sys.stderr)
    n_fits = len(components) * len(ch.SEEDS)
    # A column absent from a family's set counts as zero gain for that family.
    ranked = pd.Series({c: sum(v) / n_fits for c, v in scores.items()}).sort_values(ascending=False)
    return ranked


def run(caps: list[int]) -> dict:
    search = json.loads(ch.SEARCH_JSON.read_text())
    saved = pd.read_parquet(ch.FINAL_PARQUET)
    saved["financial_proposal_id"] = saved["financial_proposal_id"].astype(str)
    df = x3._prepare(pd.read_parquet(ch.FEATURES_PARQUET))
    df["financial_proposal_id"] = df["financial_proposal_id"].astype(str)
    feature_sets = ch._feature_sets(df)
    cfg_by_name = {c.name: c for c in ch.CONFIGS}
    out = {"caps": caps, "method": __doc__.split("Method, per target:")[1].split("Does not")[0].strip(),
           "targets": {}}

    for target, tspec in search["targets"].items():
        print(f"\n== {target}", file=sys.stderr)
        components = {}
        for family, cand in tspec["best_by_family"].items():
            components[family] = {
                "cfg": cfg_by_name[cand["config"]],
                "cols": feature_sets[cand["feature_set"]],
                "candidate": cand["candidate"],
            }
        w_xgb = float(tspec["blend"]["component_a_weight"])
        ranked = rank_features(df, target, components)
        ycol = ch.TARGETS[target]["ycol"]

        ref = saved[saved["target"].eq(target)].set_index("financial_proposal_id")
        results = []
        for K in caps:
            cols = ranked.index[:K].tolist()
            t0 = time.time()
            cv = {}
            oof = {}
            for family, comp in components.items():
                r, o = ch._cv_candidate(df, target, cols, f"cap{K}", comp["cfg"])
                cv[family] = r
                oof[family] = o
            blend_cv, _ = ch._blend_result(f"cap{K}", oof["xgb"], oof["lgb"], w_xgb)
            rechosen, _ = ch._choose_blend(oof["xgb"], oof["lgb"], "xgb", "lgb")

            preds = {}
            models = {}
            iters = {}
            oot = None
            for family, comp in components.items():
                m, p, oot, it = ch._final_fit_predict(df, target, cols, comp["cfg"])
                preds[family] = p
                models[family] = m
                iters[family] = it
            capped = w_xgb * preds["xgb"] + (1 - w_xgb) * preds["lgb"]
            ids = oot["financial_proposal_id"].astype(str).to_numpy()
            y = oot[ycol].astype(int).to_numpy()
            aligned = ref.loc[ids]
            if not (aligned["y"].to_numpy() == y).all():
                raise RuntimeError("OOT rows do not align with the saved champion predictions")
            row = {
                "cap": K,
                "n_features": len(cols),
                "features": cols,
                "cv": {f: {k: v for k, v in r.items() if k != "folds"} for f, r in cv.items()},
                "cv_blend_champion_weight": {k: v for k, v in blend_cv.items() if k != "folds"},
                "cv_blend_rechosen_weight": rechosen["component_a_weight"],
                "iterations": iters,
                "oot": {
                    "n": int(len(y)),
                    "bads": int(y.sum()),
                    "capped_gini": round(float(signed_gini(capped, y)), 4),
                    "capped_xgb_gini": round(float(signed_gini(preds["xgb"], y)), 4),
                    "capped_lgb_gini": round(float(signed_gini(preds["lgb"], y)), 4),
                    "champion_gini": round(float(signed_gini(aligned["champion"].to_numpy(), y)), 4),
                    "published_capped_gini": round(float(signed_gini(aligned["published_capped"].to_numpy(), y)), 4),
                    "live_gini": round(float(signed_gini(aligned["live_full_refit"].to_numpy(), y)), 4),
                    "vs_champion": ch._bootstrap_delta(y, capped, aligned["champion"].to_numpy()),
                    "vs_published": ch._bootstrap_delta(y, capped, aligned["published_capped"].to_numpy()),
                    "vs_live": ch._bootstrap_delta(y, capped, aligned["live_full_refit"].to_numpy()),
                },
            }
            results.append(row)
            print(f"  cap={K:<4} OOT capped={row['oot']['capped_gini']:.4f} "
                  f"champion={row['oot']['champion_gini']:.4f} published50={row['oot']['published_capped_gini']:.4f} "
                  f"vs champion {ch._fmt_ci(row['oot']['vs_champion'])} [{time.time()-t0:.0f}s]", file=sys.stderr)
            if K == 50:
                path = x3.OUT_DIR / f"experiment3_champion_capped_{target}_50.joblib"
                joblib.dump({
                    "target": ycol, "features": cols, "xgb_weight": w_xgb,
                    "components": [{"family": f, "config": asdict(components[f]["cfg"]),
                                    "models": models[f], "iterations": iters[f]} for f in ("xgb", "lgb")],
                    "seeds": list(ch.SEEDS), "development_only": True,
                    "selection": "top-50 mean normalised gain, pre-OOT training window, both families, seeds 0/17/42",
                }, path, compress=3)
        out["targets"][target] = {
            "components": {f: {"candidate": c["candidate"], "config": asdict(c["cfg"]), "n_features": len(c["cols"])}
                           for f, c in components.items()},
            "xgb_weight": w_xgb,
            "ranking_top_60": ranked.head(60).round(5).to_dict(),
            "results": results,
        }
    RESULT_JSON.write_text(json.dumps(out, indent=2))
    _write_report(out)
    return out


def _write_report(out: dict) -> None:
    lines = ["# Experiment 3 champion under a hard feature cap (2026-09-07)", "",
             "Question: the development champion uses 1,654–3,150 input features. How much of its uplift "
             "over the published 50-feature model survives a cap? Recipe and blend weight are the champion's; "
             "only the column set changes. Features ranked by mean normalised gain on the **pre-OOT training "
             "window only** (both families, seeds 0/17/42); both components share the same top-K columns. "
             "Same OOT windows and rows as the champion report; paired bootstrap CIs on identical rows. "
             "Locked v5/v6 not scored.", ""]
    for target, t in out["targets"].items():
        r0 = t["results"][0]["oot"]
        lines += [f"## {target} (OOT n={r0['n']:,} / bads {r0['bads']})", "",
                  f"Components: " + "; ".join(f"{f} = `{c['candidate']}`" for f, c in t["components"].items())
                  + f"; blend {t['xgb_weight']:.1f} XGB / {1-t['xgb_weight']:.1f} LGB.", "",
                  "| Model | Features | Rolling CV mean GINI | OOT GINI | Δ vs champion (95% CI) | Δ vs published 50 (95% CI) | Δ vs live (95% CI) |",
                  "|---|---:|---:|---:|---:|---:|---:|",
                  f"| Live model, full refit | — | — | {r0['live_gini']:.3f} | | | |",
                  f"| Published 50-feature XGB (Aug) | 50 | — | {r0['published_capped_gini']:.3f} | | | |"]
        for r in t["results"]:
            o = r["oot"]
            lines.append(f"| Capped champion | **{r['n_features']}** | {r['cv_blend_champion_weight']['mean_gini']:.3f} | "
                         f"**{o['capped_gini']:.3f}** | {ch._fmt_ci(o['vs_champion'])} | {ch._fmt_ci(o['vs_published'])} | {ch._fmt_ci(o['vs_live'])} |")
        lines.append(f"| Champion, uncapped | {'/'.join(str(c['n_features']) for c in t['components'].values())} | — | {r0['champion_gini']:.3f} | | | |")
        lines += ["", "Component OOT GINI per cap: " + "; ".join(
            f"cap {r['cap']}: XGB {r['oot']['capped_xgb_gini']:.3f} / LGB {r['oot']['capped_lgb_gini']:.3f} "
            f"(CV re-chosen XGB weight {r['cv_blend_rechosen_weight']:.1f})" for r in t["results"]), "",
            "Top 50 features by pre-OOT gain:", ""]
        top = list(t["ranking_top_60"].items())[:50]
        lines += [f"{i+1}. `{k}` ({v:.4f})" for i, (k, v) in enumerate(top)]
        lines.append("")
    REPORT.write_text("\n".join(lines))
    print(f"Wrote {REPORT}", file=sys.stderr)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--caps", type=int, nargs="+", default=[50, 100, 200])
    args = ap.parse_args(argv)
    run(args.caps)


if __name__ == "__main__":
    main()

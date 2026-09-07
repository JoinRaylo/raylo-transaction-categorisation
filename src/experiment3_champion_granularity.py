"""Re-run the granularity ladder using the champion's recipe (7 Sep 2026 follow-up).

The compaction ladder (``experiment3_granularity_ladder.py``) held the model
recipe fixed (a single plain XGBoost on rung-level months/count/amount
features) and varied only the taxonomy rollup. Separately, the champion
search (``experiment3_champion_model.py``) found that swapping the "current"
(69-rung) feature view for a richer one built at the full 275-leaf level
(transaction share, per-leaf averages, coefficient of variation) gains real
GINI at a fixed algorithm. Nobody had combined the two: does the champion's
richer feature *engineering* still plateau across coarser taxonomy rollups,
the way the plain months/count/amount features did?

This script holds the champion's chosen recipe and blend weight fixed
(nothing re-tuned — read straight from ``experiment3_champion_search.json``)
and rebuilds its style of rich per-group features (raw stats, transaction/
month/amount share, and avg debit/credit for risk-adjacent groups) at every
rung of the ladder: 275 leaves, today's 69, 29 generals, 17 budget groups,
9 macro groups, 7 cash-flow types, 4 minimal groups. The category-derived
base is replaced with a recipe-agnostic spine + the orthogonal dimensions
(same ``SPINE``/``DIMS`` used in the original ladder's "dims_held" variant),
so the only thing that changes between rungs is the granularity of the
category features — an apples-to-apples extension of the original ladder,
now on the stronger recipe.

Every rung is capped at 50 features (mean normalised gain, pre-OOT training
window only, both families, seeds 0/17/42 — identical method to
``experiment3_champion_capped.py``), matching the reference the champion
itself carries forward. No new BigQuery work: reuses the already-computed
long-format aggregate (``outputs/experiment3_ladder_long.parquet``, all 7
rungs) and the champion's already-selected recipe/blend. Locked v5/v6 not
scored.

Usage:
    uv run python src/experiment3_champion_granularity.py
"""
from __future__ import annotations

import json
import sys
import time
from dataclasses import asdict

import joblib
import numpy as np
import pandas as pd

import experiment3_champion_capped as capped
import experiment3_champion_model as ch
import experiment3_granularity_ladder as ladder
import experiment3_xgb_pipeline as x3
from credit_metrics import signed_gini

ROOT = ch.ROOT
REPORT = ROOT / "data" / "experiment3_champion_granularity_report.md"
RESULT_JSON = x3.OUT_DIR / "experiment3_champion_granularity.json"
CAP = 50

RUNGS = ladder.RUNGS  # [(key, desc), ...] 275 -> 4, same order as the original ladder


def _safe_divide(num: np.ndarray, den: np.ndarray) -> np.ndarray:
    return ch._safe_divide(num, den)


def _risk_groups(rung: str) -> list[str]:
    """Groups at this rung containing >=1 leaf the champion treats as risk-adjacent."""
    tax = pd.read_csv(x3.TAXONOMY_PATH)
    lad = pd.read_csv(ROOT / "taxonomy" / "granularity_ladder.csv")
    risk_mask = (
        tax["detailed_category"].isin(x3.KEY_LEAVES)
        | tax["is_debt_related"].astype(bool)
        | tax["is_priority_debt"].astype(bool)
        | tax["is_age_restricted"].astype(bool)
        | ~tax["risk_flag"].fillna("none").isin(["none", ""])
    )
    risk_leaves = set(tax.loc[risk_mask, "detailed_category"])
    if rung == "l0_leaf_275":
        return sorted(risk_leaves)
    if rung == "l0_current_69":
        return sorted({leaf if leaf in x3.KEY_LEAVES else grp
                        for leaf, grp in zip(lad["detailed_category"], lad["l1_general_29"])
                        if leaf in risk_leaves})
    col = {"l1_general_29": "l1_general_29", "l2_budget_17": "l2_budget_17",
           "l3_macro_9": "l3_macro_9", "l4_cashflow_7": "l4_cashflow_7",
           "l5_minimal_4": "l5_minimal_4"}[rung]
    return sorted({grp for leaf, grp in zip(lad["detailed_category"], lad[col])
                   if leaf in risk_leaves})


def build_rung_features(rung: str, long_df: pd.DataFrame, base: pd.DataFrame) -> pd.DataFrame:
    """Champion-style rich features (raw + share + risk avg_debit/avg_credit) at one rung."""
    sub = long_df[long_df["rung"].eq(rung)].copy()
    sub["financial_proposal_id"] = sub["financial_proposal_id"].astype(str)
    idx = ["financial_proposal_id", "provider"]
    suffixes = {"g_months": "months", "g_n": "n", "g_debit_n": "debit_n",
                "g_debit_amt": "debit_amt", "g_credit_amt": "credit_amt"}
    raw_frames: dict[str, pd.DataFrame] = {}
    for source, suffix in suffixes.items():
        wide = sub.pivot_table(index=idx, columns="grp", values=source, aggfunc="sum", fill_value=0)
        wide = wide.sort_index(axis=1).astype("float32")
        wide.columns = [f"{rung}__{c}__{suffix}" for c in wide.columns]
        raw_frames[suffix] = wide
    raw = pd.concat(raw_frames.values(), axis=1).reset_index()

    out = base[["financial_proposal_id", "provider", "total_months", "n_txns", "n_debits",
                "total_debit_amt", "total_credit_amt"]].merge(raw, on=idx, how="left")
    raw_cols = [c for c in raw.columns if c.startswith(f"{rung}__")]
    out[raw_cols] = out[raw_cols].fillna(0).astype("float32")
    groups = sorted({c.split("__")[1] for c in raw_cols})

    arrays = {suffix: out[[f"{rung}__{g}__{suffix}" for g in groups]].to_numpy(np.float32, copy=False)
              for suffix in suffixes.values()}
    denominators = {
        "month_share": out["total_months"].to_numpy(np.float32)[:, None],
        "txn_share": out["n_txns"].to_numpy(np.float32)[:, None],
        "debit_txn_share": out["n_debits"].to_numpy(np.float32)[:, None],
        "debit_amt_share": out["total_debit_amt"].to_numpy(np.float32)[:, None],
        "credit_amt_share": out["total_credit_amt"].to_numpy(np.float32)[:, None],
    }
    numerators = {
        "month_share": arrays["months"], "txn_share": arrays["n"],
        "debit_txn_share": arrays["debit_n"], "debit_amt_share": arrays["debit_amt"],
        "credit_amt_share": arrays["credit_amt"],
    }
    derived = []
    for suffix in denominators:
        values = _safe_divide(numerators[suffix], denominators[suffix])
        derived.append(pd.DataFrame(values, columns=[f"{rung}__{g}__{suffix}" for g in groups],
                                     index=out.index))

    risk_groups = sorted(set(_risk_groups(rung)) & set(groups))
    if risk_groups:
        risk_idx = [groups.index(g) for g in risk_groups]
        credit_n = arrays["n"][:, risk_idx] - arrays["debit_n"][:, risk_idx]
        for suffix, values in [
            ("avg_debit", _safe_divide(arrays["debit_amt"][:, risk_idx], arrays["debit_n"][:, risk_idx])),
            ("avg_credit", _safe_divide(arrays["credit_amt"][:, risk_idx], credit_n)),
        ]:
            derived.append(pd.DataFrame(values, columns=[f"{rung}__{g}__{suffix}" for g in risk_groups],
                                         index=out.index))

    result = pd.concat([out[["financial_proposal_id", "provider"] + raw_cols]] + derived, axis=1)
    result.replace([np.inf, -np.inf], np.nan, inplace=True)
    return result


def build_all_rung_features() -> pd.DataFrame:
    print("Building recipe-agnostic base (spine + dims) + per-rung rich features...",
          file=sys.stderr)
    base = x3._prepare(pd.read_parquet(x3.FEAT_PARQUET))
    base["financial_proposal_id"] = base["financial_proposal_id"].astype(str)
    keep = list(dict.fromkeys(ladder.META + ladder.SPINE + ladder.DIMS))
    keep = [c for c in keep if c in base.columns]
    spine_df = base[keep].copy()
    spine_df[ladder.SPINE + ladder.DIMS] = (
        spine_df[ladder.SPINE + ladder.DIMS].apply(pd.to_numeric, errors="coerce").astype("float32"))

    long_df = pd.read_parquet(ladder.LONG_PARQUET)
    frames = {}
    for rung, desc in RUNGS:
        t0 = time.time()
        frames[rung] = build_rung_features(rung, long_df, base)
        n_cols = len(frames[rung].columns) - 2
        print(f"  {rung:>14} ({desc}): {n_cols:,} rich columns [{time.time()-t0:.0f}s]",
              file=sys.stderr)
    del long_df
    return spine_df, frames


def _cap_and_score(spine_df: pd.DataFrame, rung_frame: pd.DataFrame, rung: str,
                    target: str, components: dict, w_xgb: float) -> dict:
    df = spine_df.merge(rung_frame, on=["financial_proposal_id", "provider"], how="left")
    rich_cols = [c for c in rung_frame.columns if c not in ("financial_proposal_id", "provider")]
    df[rich_cols] = df[rich_cols].fillna(0).astype("float32")
    df = x3._prepare(df)
    all_cols = list(dict.fromkeys(ladder.SPINE + ladder.DIMS + rich_cols))

    comp_cols = {}
    for family, comp in components.items():
        cfg = comp["cfg"]
        cols = all_cols
        scores: dict[str, list[float]] = {}
        spec = ch.TARGETS[target]
        ycol = spec["ycol"]
        train = x3._window(df, spec["train_start"], spec["train_end"], ycol)
        inner, stop = ch._inner_split(train, ycol)
        for seed in ch.SEEDS:
            _, best = ch._fit_early(inner, stop, ycol, cols, cfg, seed)
            model = ch._fit_refit(train, ycol, cols, cfg, seed, best)
            g = capped._gain(model, cols)
            for c, v in zip(cols, g):
                scores.setdefault(c, []).append(float(v))
        ranked = pd.Series({c: sum(v) / len(ch.SEEDS) for c, v in scores.items()}).sort_values(
            ascending=False)
        comp_cols[family] = ranked.index[:CAP].tolist()

    capped_cols = sorted(set(comp_cols["xgb"]) | set(comp_cols["lgb"]))
    if len(capped_cols) > CAP:
        pooled = pd.concat([pd.Series(comp_cols[f]) for f in comp_cols]).value_counts()
        capped_cols = pooled.index[:CAP].tolist()

    preds = {}
    oot = None
    for family, comp in components.items():
        m, p, oot, it = ch._final_fit_predict(df, target, capped_cols, comp["cfg"])
        preds[family] = p
    y = oot[ch.TARGETS[target]["ycol"]].astype(int).to_numpy()
    blended = w_xgb * preds["xgb"] + (1 - w_xgb) * preds["lgb"]
    return {
        "rung": rung, "target": target, "n_features": len(capped_cols),
        "features": capped_cols, "oot_n": int(len(y)), "oot_bads": int(y.sum()),
        "gini": round(float(signed_gini(blended, y)), 4),
        "xgb_gini": round(float(signed_gini(preds["xgb"], y)), 4),
        "lgb_gini": round(float(signed_gini(preds["lgb"], y)), 4),
    }


def _uncapped_score(spine_df: pd.DataFrame, rung_frame: pd.DataFrame, rung: str,
                     target: str, components: dict, w_xgb: float) -> dict:
    """Same as _cap_and_score but with no gain-ranking/cap step: every candidate
    column at this rung (spine + dims + all rich features) goes straight into
    the final fit. Isolates whether the champion's richer feature types help
    at genuinely uncapped granularity, without the cap-instability confound."""
    df = spine_df.merge(rung_frame, on=["financial_proposal_id", "provider"], how="left")
    rich_cols = [c for c in rung_frame.columns if c not in ("financial_proposal_id", "provider")]
    df[rich_cols] = df[rich_cols].fillna(0).astype("float32")
    df = x3._prepare(df)
    all_cols = list(dict.fromkeys(ladder.SPINE + ladder.DIMS + rich_cols))

    preds = {}
    oot = None
    for family, comp in components.items():
        m, p, oot, it = ch._final_fit_predict(df, target, all_cols, comp["cfg"])
        preds[family] = p
    y = oot[ch.TARGETS[target]["ycol"]].astype(int).to_numpy()
    blended = w_xgb * preds["xgb"] + (1 - w_xgb) * preds["lgb"]
    return {
        "rung": rung, "target": target, "n_features": len(all_cols),
        "oot_n": int(len(y)), "oot_bads": int(y.sum()),
        "gini": round(float(signed_gini(blended, y)), 4),
        "xgb_gini": round(float(signed_gini(preds["xgb"], y)), 4),
        "lgb_gini": round(float(signed_gini(preds["lgb"], y)), 4),
    }


def run_uncapped() -> dict:
    search = json.loads(ch.SEARCH_JSON.read_text())
    spine_df, rung_frames = build_all_rung_features()

    out = {"cap": None, "recipe": "champion's chosen config + blend per target, nothing re-tuned; "
                                   "no gain-ranking or feature cap — every candidate column at "
                                   "each rung goes into the fit", "targets": {}}
    for target, tspec in search["targets"].items():
        cfg_by_name = {c.name: c for c in ch.CONFIGS}
        components = {family: {"cfg": cfg_by_name[cand["config"]], "candidate": cand["candidate"]}
                      for family, cand in tspec["best_by_family"].items()}
        w_xgb = float(tspec["blend"]["component_a_weight"])
        print(f"\n== {target} (uncapped)  (blend {w_xgb:.1f} XGB / {1-w_xgb:.1f} LGB; "
              f"{components['xgb']['candidate']} + {components['lgb']['candidate']})",
              file=sys.stderr)

        rung_results = []
        for rung, desc in RUNGS:
            t0 = time.time()
            r = _uncapped_score(spine_df, rung_frames[rung], rung, target, components, w_xgb)
            rung_results.append(r)
            print(f"  {rung:>14} uncapped ({r['n_features']:,} feats): gini {r['gini']:+.4f} "
                  f"(xgb {r['xgb_gini']:.4f} / lgb {r['lgb_gini']:.4f}) "
                  f"n_oot={r['oot_n']} [{time.time()-t0:.0f}s]", file=sys.stderr)
        out["targets"][target] = {
            "blend": w_xgb,
            "components": {f: c["candidate"] for f, c in components.items()},
            "rungs": rung_results,
        }

    x3.OUT_DIR.mkdir(exist_ok=True)
    result_path = x3.OUT_DIR / "experiment3_champion_granularity_uncapped.json"
    result_path.write_text(json.dumps(out, indent=2))
    print(f"\nwrote {result_path}", file=sys.stderr)
    _write_uncapped_report(out)
    return out


def _write_uncapped_report(out: dict) -> None:
    report = ROOT / "data" / "experiment3_champion_granularity_uncapped_report.md"
    capped_result = json.loads(RESULT_JSON.read_text()) if RESULT_JSON.exists() else None
    lines = [
        "# Granularity ladder on the champion recipe, uncapped (2026-09-07)",
        "",
        "Follow-up to the capped rung sweep. Same champion recipe and blend weight (nothing "
        "re-tuned), same rich per-group feature engineering, rebuilt at every rung — but with "
        "**no gain-ranking or 50-feature cap**: every candidate column at a rung (recipe-agnostic "
        "spine + dimensions, plus every raw/share/risk-avg feature computed at that rung) goes "
        "straight into the final fit. Isolates whether the champion's richer feature *types* "
        "help once the cap-instability confound found in the capped run is removed. Locked v5/v6 "
        "not scored.",
        "",
    ]
    for target, t in out["targets"].items():
        lines += [f"## {target}", "",
                  f"Components: xgb = `{t['components']['xgb']}`; lgb = `{t['components']['lgb']}`; "
                  f"blend {t['blend']:.1f} XGB / {1-t['blend']:.1f} LGB.", "",
                  "| Rung | Categories | Uncapped GINI | XGB | LGB | Features |",
                  "|---|---:|---:|---:|---:|---:|"]
        cap_rows = {r["rung"]: r for r in capped_result["targets"][target]["rungs"]} if capped_result else {}
        for r in t["rungs"]:
            desc = dict(RUNGS)[r["rung"]]
            cap_gini = cap_rows.get(r["rung"], {}).get("gini")
            delta = f" (Δ vs cap-50 {r['gini']-cap_gini:+.3f})" if cap_gini is not None else ""
            lines.append(f"| `{r['rung']}` — {desc} | {r['n_features']:,} feats | "
                         f"**{r['gini']:.3f}**{delta} | {r['xgb_gini']:.3f} | {r['lgb_gini']:.3f} | "
                         f"{r['n_features']:,} |")
        lines.append("")
    lines += [
        "## Reading this alongside the capped run",
        "",
        "The capped run (`data/experiment3_champion_granularity_report.md`) found 275 leaves the "
        "*worst* rung at a fixed 50-feature budget, because the gain-ranking step crowds the "
        "strongest existing features (`priority_debt_breadth`, `credit_product_months`) out of a "
        "small cap. This run removes the cap entirely, so any remaining shape is attributable to "
        "the feature engineering and algorithm themselves, not to selection instability.",
    ]
    report.write_text("\n".join(lines) + "\n")
    print(f"wrote {report}", file=sys.stderr)


def run() -> dict:
    search = json.loads(ch.SEARCH_JSON.read_text())
    spine_df, rung_frames = build_all_rung_features()

    out = {"cap": CAP, "recipe": "champion's chosen config + blend per target, nothing re-tuned",
           "targets": {}}
    for target, tspec in search["targets"].items():
        cfg_by_name = {c.name: c for c in ch.CONFIGS}
        components = {family: {"cfg": cfg_by_name[cand["config"]], "candidate": cand["candidate"]}
                      for family, cand in tspec["best_by_family"].items()}
        w_xgb = float(tspec["blend"]["component_a_weight"])
        print(f"\n== {target}  (blend {w_xgb:.1f} XGB / {1-w_xgb:.1f} LGB; "
              f"{components['xgb']['candidate']} + {components['lgb']['candidate']})",
              file=sys.stderr)

        rung_results = []
        for rung, desc in RUNGS:
            t0 = time.time()
            r = _cap_and_score(spine_df, rung_frames[rung], rung, target, components, w_xgb)
            rung_results.append(r)
            print(f"  {rung:>14} cap{CAP}: gini {r['gini']:+.4f} "
                  f"(xgb {r['xgb_gini']:.4f} / lgb {r['lgb_gini']:.4f}) "
                  f"n_oot={r['oot_n']} [{time.time()-t0:.0f}s]", file=sys.stderr)
        out["targets"][target] = {
            "blend": w_xgb,
            "components": {f: c["candidate"] for f, c in components.items()},
            "rungs": rung_results,
        }

    x3.OUT_DIR.mkdir(exist_ok=True)
    RESULT_JSON.write_text(json.dumps(out, indent=2))
    print(f"\nwrote {RESULT_JSON}", file=sys.stderr)
    _write_report(out)
    return out


def _write_report(out: dict) -> None:
    search = json.loads(ch.SEARCH_JSON.read_text())
    lines = [
        "# Granularity ladder on the champion recipe (2026-09-07)",
        "",
        "Open question from the 7 Sep cross-check: the compaction ladder held a plain-XGBoost "
        "recipe fixed and swept taxonomy granularity; separately, the champion found that richer "
        "leaf-level features (share-of-total, per-leaf averages) beat the 69-rung view by "
        "+0.02–+0.04 GINI at a fixed algorithm. This combines the two — same champion recipe "
        "and blend weight (nothing re-tuned, read from `experiment3_champion_search.json`), same "
        "rich feature engineering (raw stats, transaction/month/amount share, risk-group avg "
        "debit/credit), rebuilt at every rung from 275 leaves down to 4 minimal groups. "
        f"Capped at {CAP} features throughout (mean normalised gain, pre-OOT training window, "
        "both families, seeds 0/17/42 — same method as `experiment3_champion_capped.py`). The "
        "category-derived base is replaced by the recipe-agnostic spine + orthogonal dimensions "
        "(`experiment3_granularity_ladder.py`'s `dims_held` variant), so only rung granularity "
        "changes between rows. Locked v5/v6 not scored.",
        "",
    ]
    for target, t in out["targets"].items():
        lines += [f"## {target}", "",
                  f"Components: xgb = `{t['components']['xgb']}`; lgb = `{t['components']['lgb']}`; "
                  f"blend {t['blend']:.1f} XGB / {1-t['blend']:.1f} LGB.", "",
                  "| Rung | Categories | Cap-50 GINI | XGB | LGB |",
                  "|---|---:|---:|---:|---:|"]
        for r in t["rungs"]:
            desc = dict(RUNGS)[r["rung"]]
            lines.append(f"| `{r['rung']}` — {desc} | {r['n_features']} feats | "
                         f"**{r['gini']:.3f}** | {r['xgb_gini']:.3f} | {r['lgb_gini']:.3f} |")
        lines.append("")
    lines += [
        "## Reference points (from the champion work, not re-derived here)",
        "",
        f"- Live reconstruction: month3 {search['targets']['month3']['oot']['live_reconstruction_gini']:.3f}, "
        f"month6 {search['targets']['month6']['oot']['live_reconstruction_gini']:.3f}.",
        f"- Published August 50-feature XGB: month3 {search['targets']['month3']['oot']['published_capped_gini']:.3f}, "
        f"month6 {search['targets']['month6']['oot']['published_capped_gini']:.3f}.",
        f"- Champion, capped at 50 on its actual feature set (base includes the 69-rung blocks; "
        "see `experiment3_champion_capped_report.md`): month3 0.508, month6 0.583.",
        "",
        "The capped-champion number above is not directly comparable row-for-row to this report's "
        "rungs, because its base retains the existing 69-rung blocks (spine + KEY_LEAVES + general "
        "blocks) alongside the rich leaf features, whereas every rung here uses a purely "
        "recipe-agnostic base (spine + dimensions only) so that granularity is the *only* thing "
        "varying. This report isolates the granularity effect; the champion capped report isolates "
        "the feature-cap effect on the full recipe.",
    ]
    REPORT.write_text("\n".join(lines) + "\n")
    print(f"wrote {REPORT}", file=sys.stderr)


if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else "capped"
    if stage == "capped":
        run()
    elif stage == "uncapped":
        run_uncapped()
    else:
        raise SystemExit(f"unknown stage {stage!r}; use 'capped' or 'uncapped'")

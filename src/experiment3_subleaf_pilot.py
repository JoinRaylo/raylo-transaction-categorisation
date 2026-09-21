"""Experiment 3 shadow-taxonomy pilot above the current 275 leaves.

This is deliberately an overlay, not a taxonomy migration.  Three broad parent
leaves are split by frozen merchant/description rules while the production leaf
remains unchanged.  The model comparison separates two questions:

1. ``current`` -> ``parent_control``: does exposing the three existing parent
   leaves add information beyond the current feature set?
2. ``parent_control`` -> ``subleaf_overlay``: does composition *within* those
   parents add information?  This is the clean test of going beyond 275.

The rules are defined in ``taxonomy/experimental_subleaf_pilot.csv`` and were
frozen before any outcome rate or model result was inspected.  Only the three
affected parents are aggregated.  Locked classifier v5/v6 sets are never read.

Usage:
    uv run python src/experiment3_subleaf_pilot.py aggregate
    uv run python src/experiment3_subleaf_pilot.py features
    uv run python src/experiment3_subleaf_pilot.py train
    uv run python src/experiment3_subleaf_pilot.py all
"""
from __future__ import annotations

import argparse
import csv
import json
import pathlib
import sys
import time
from collections import defaultdict

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import experiment3_champion_model as champion  # noqa: E402
import experiment3_xgb_pipeline as x3  # noqa: E402
from credit_metrics import signed_gini  # noqa: E402
import eval_protection  # noqa: E402

SPEC_PATH = ROOT / "taxonomy" / "experimental_subleaf_pilot.csv"
AGG_PARQUET = x3.OUT_DIR / "experiment3_subleaf_aggregate.parquet"
FEATURE_PARQUET = x3.OUT_DIR / "experiment3_subleaf_features.parquet"
RESULTS_JSON = x3.OUT_DIR / "experiment3_subleaf_results.json"
PREDICTIONS_PARQUET = x3.OUT_DIR / "experiment3_subleaf_predictions.parquet"
REPORT = ROOT / "data" / "experiment3_subleaf_pilot_report.md"

PILOT_CONFIG = "xgb_d5_regularised"
CV_SEED = 0
FINAL_SEEDS = champion.SEEDS
STATS = ("months", "n", "debit_n", "debit_amt", "credit_amt")


def _rules() -> list[dict]:
    with SPEC_PATH.open(newline="") as fh:
        rows = list(csv.DictReader(fh))
    for row in rows:
        row["priority"] = int(row["priority"])
        row["tokens"] = [x.strip().lower() for x in row["contains_any"].split("|") if x.strip()]
    parents = defaultdict(list)
    for row in rows:
        parents[row["parent_leaf"]].append(row)
    for parent, group in parents.items():
        fallbacks = [r for r in group if not r["tokens"]]
        if len(fallbacks) != 1:
            raise ValueError(f"{parent}: expected exactly one fallback, found {len(fallbacks)}")
        if fallbacks[0]["priority"] != max(r["priority"] for r in group):
            raise ValueError(f"{parent}: fallback must have last priority")
    children = [r["experimental_subleaf"] for r in rows]
    if len(children) != len(set(children)):
        raise ValueError("Experimental subleaf names must be globally unique")
    return sorted(rows, key=lambda r: (r["parent_leaf"], r["priority"]))


def _bq_quote(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _case_sql() -> str:
    text = "LOWER(CONCAT(COALESCE(merchant, ''), ' ', COALESCE(description, '')))"
    rows = _rules()
    lines = ["CASE"]
    for row in rows:
        if not row["tokens"]:
            continue
        clauses = " OR ".join(
            f"STRPOS({text}, '{_bq_quote(token)}') > 0" for token in row["tokens"])
        lines.append(
            f"  WHEN leaf = '{row['parent_leaf']}' AND ({clauses}) "
            f"THEN '{row['experimental_subleaf']}'")
    for row in rows:
        if not row["tokens"]:
            lines.append(
                f"  WHEN leaf = '{row['parent_leaf']}' THEN '{row['experimental_subleaf']}'")
    lines.append("END")
    return "\n".join(lines)


def _aggregate_sql() -> str:
    parents = sorted({r["parent_leaf"] for r in _rules()})
    parent_list = ", ".join(f"'{p}'" for p in parents)
    return f"""
WITH override_plaid AS (
  SELECT merchant, description, direction, hinge_leaf FROM `{x3.OVERRIDE_PLAID}`
),
override_eqx AS (
  SELECT merchant, direction, hinge_leaf FROM `{x3.OVERRIDE_EQX}`
),
eqx AS (SELECT {x3._TXN_COLS} FROM `{x3.EQX_TXN_TABLE}`),
plaid AS (SELECT {x3._TXN_COLS} FROM `{x3.PLAID_TXN_TABLE}`),
unioned AS (SELECT * FROM eqx UNION ALL SELECT * FROM plaid),
resolved AS (
  SELECT
    u.* EXCEPT (leaf, resolution_tier),
    CASE
      WHEN (STARTS_WITH(u.resolution_tier, 'T6') OR STARTS_WITH(u.resolution_tier, 'T7'))
           AND u.provider = 'plaid' AND op.hinge_leaf IS NOT NULL THEN op.hinge_leaf
      WHEN (STARTS_WITH(u.resolution_tier, 'T6') OR STARTS_WITH(u.resolution_tier, 'T7'))
           AND u.provider = 'equifax' AND oe.hinge_leaf IS NOT NULL THEN oe.hinge_leaf
      ELSE u.leaf
    END AS leaf,
    CASE
      WHEN (STARTS_WITH(u.resolution_tier, 'T6') OR STARTS_WITH(u.resolution_tier, 'T7'))
           AND u.provider = 'plaid' AND op.hinge_leaf IS NOT NULL THEN 'T5b_classifier'
      WHEN (STARTS_WITH(u.resolution_tier, 'T6') OR STARTS_WITH(u.resolution_tier, 'T7'))
           AND u.provider = 'equifax' AND oe.hinge_leaf IS NOT NULL THEN 'T5b_classifier'
      ELSE u.resolution_tier
    END AS resolution_tier
  FROM unioned u
  LEFT JOIN override_plaid op
    ON u.provider = 'plaid' AND u.merchant = op.merchant
   AND u.description = op.description AND u.direction = op.direction
  LEFT JOIN override_eqx oe
    ON u.provider = 'equifax' AND u.merchant = oe.merchant
   AND u.direction = oe.direction
),
tagged AS (
  SELECT *, leaf AS parent_leaf, {_case_sql()} AS experimental_subleaf
  FROM resolved
  WHERE leaf IN ({parent_list})
),
child AS (
  SELECT
    CAST(financial_proposal_id AS STRING) AS financial_proposal_id,
    provider, parent_leaf, experimental_subleaf,
    COUNT(DISTINCT month) AS months,
    COUNT(*) AS n,
    COUNTIF(direction = 'debit') AS debit_n,
    SUM(IF(direction = 'debit', abs_amt, 0)) AS debit_amt,
    SUM(IF(direction = 'credit', abs_amt, 0)) AS credit_amt
  FROM tagged
  GROUP BY 1, 2, 3, 4
),
parent AS (
  SELECT
    CAST(financial_proposal_id AS STRING) AS financial_proposal_id,
    provider, parent_leaf,
    COUNT(DISTINCT month) AS parent_months,
    COUNT(*) AS parent_n,
    COUNTIF(direction = 'debit') AS parent_debit_n,
    SUM(IF(direction = 'debit', abs_amt, 0)) AS parent_debit_amt,
    SUM(IF(direction = 'credit', abs_amt, 0)) AS parent_credit_amt
  FROM tagged
  GROUP BY 1, 2, 3
)
SELECT c.*, p.parent_months, p.parent_n, p.parent_debit_n,
       p.parent_debit_amt, p.parent_credit_amt
FROM child c
JOIN parent p USING (financial_proposal_id, provider, parent_leaf)
"""


def aggregate() -> pd.DataFrame:
    # B04 gated off: proposal/provider aggregates carry no customer identity,
    # so connected-customer exclusion cannot be proven.
    eval_protection.gate(
        "experiment3_subleaf_pilot.aggregate",
        "proposal-level aggregates carry no linked customer identity",
    )
    from google.cloud import bigquery

    client = x3._client()
    sql = _aggregate_sql()
    dry = client.query(
        sql,
        location=x3.LOCATION,
        job_config=bigquery.QueryJobConfig(dry_run=True, use_query_cache=False),
    )
    print(f"Read-only aggregate will scan {dry.total_bytes_processed / 2**30:.2f} GiB", file=sys.stderr)
    t0 = time.time()
    df = client.query(sql, location=x3.LOCATION).result().to_dataframe()
    x3.OUT_DIR.mkdir(exist_ok=True)
    df.to_parquet(AGG_PARQUET, index=False, compression="zstd")
    print(f"{len(df):,} proposal/provider/child rows -> {AGG_PARQUET} [{time.time()-t0:.0f}s]",
          file=sys.stderr)
    return df


def _safe_div(num: pd.Series, den: pd.Series) -> pd.Series:
    out = pd.to_numeric(num, errors="coerce").astype(float).div(
        pd.to_numeric(den, errors="coerce").astype(float).replace(0, np.nan))
    return out.replace([np.inf, -np.inf], np.nan).fillna(0).astype("float32")


def _reconciliation(agg: pd.DataFrame) -> dict:
    keys = ["financial_proposal_id", "provider", "parent_leaf"]
    summed = agg.groupby(keys, as_index=False).agg(
        n=("n", "sum"), debit_n=("debit_n", "sum"),
        debit_amt=("debit_amt", "sum"), credit_amt=("credit_amt", "sum"),
        parent_n=("parent_n", "first"), parent_debit_n=("parent_debit_n", "first"),
        parent_debit_amt=("parent_debit_amt", "first"),
        parent_credit_amt=("parent_credit_amt", "first"),
    )
    checks = {}
    for child, parent in [
        ("n", "parent_n"), ("debit_n", "parent_debit_n"),
        ("debit_amt", "parent_debit_amt"), ("credit_amt", "parent_credit_amt"),
    ]:
        diff = (summed[child].astype(float) - summed[parent].astype(float)).abs()
        checks[f"max_abs_{child}_difference"] = float(diff.max())
    checks["max_child_months_over_parent"] = int(
        (agg["months"].astype(int) - agg["parent_months"].astype(int)).max())
    checks["passed"] = (
        checks["max_abs_n_difference"] == 0
        and checks["max_abs_debit_n_difference"] == 0
        and checks["max_abs_debit_amt_difference"] < 0.01
        and checks["max_abs_credit_amt_difference"] < 0.01
        and checks["max_child_months_over_parent"] <= 0
    )
    return checks


def build_features(agg: pd.DataFrame | None = None) -> pd.DataFrame:
    if agg is None:
        # B04 gated off: the parquet aggregates predate bound provenance.
        eval_protection.gate(
            "experiment3_subleaf_pilot.build_features",
            "unbound feature store; rebuild under the protected-release guard",
        )
        agg = pd.read_parquet(AGG_PARQUET)
    agg = agg.copy()
    agg["financial_proposal_id"] = agg["financial_proposal_id"].astype(str)
    recon = _reconciliation(agg)
    if not recon["passed"]:
        raise RuntimeError(f"Child aggregates do not reconcile: {recon}")

    base = x3._prepare(pd.read_parquet(x3.FEAT_PARQUET))
    base["financial_proposal_id"] = base["financial_proposal_id"].astype(str)
    idx = ["financial_proposal_id", "provider"]
    parent = agg.drop_duplicates(idx + ["parent_leaf"])
    parent_frames = []
    for stat in STATS:
        source = f"parent_{stat}"
        wide = parent.pivot(index=idx, columns="parent_leaf", values=source).fillna(0)
        wide.columns = [f"pilot_parent__{c}__{stat}" for c in wide.columns]
        parent_frames.append(wide.astype("float32"))
    child_frames = []
    for stat in STATS:
        wide = agg.pivot_table(index=idx, columns="experimental_subleaf", values=stat,
                               aggfunc="sum", fill_value=0)
        wide.columns = [f"pilot_child__{c}__{stat}" for c in wide.columns]
        child_frames.append(wide.astype("float32"))
    pilot = pd.concat(parent_frames + child_frames, axis=1).reset_index()
    out = base.merge(pilot, on=idx, how="left", validate="one_to_one")
    pilot_raw = [c for c in out if c.startswith(("pilot_parent__", "pilot_child__"))]
    out[pilot_raw] = out[pilot_raw].fillna(0).astype("float32")

    child_to_parent = {r["experimental_subleaf"]: r["parent_leaf"] for r in _rules()}
    derived = {}
    for child, parent_leaf in child_to_parent.items():
        for stat in STATS:
            num = out[f"pilot_child__{child}__{stat}"]
            den = out[f"pilot_parent__{parent_leaf}__{stat}"]
            derived[f"pilot_split__{child}__{stat}_share"] = _safe_div(num, den)
    for parent_leaf in sorted(set(child_to_parent.values())):
        children = [c for c, p in child_to_parent.items() if p == parent_leaf]
        ncols = [f"pilot_child__{c}__n" for c in children]
        spend_cols = [f"pilot_child__{c}__debit_amt" for c in children]
        derived[f"pilot_split__{parent_leaf}__breadth"] = (
            (out[ncols] > 0).sum(axis=1).astype("float32"))
        shares = out[spend_cols].div(out[spend_cols].sum(axis=1).replace(0, np.nan), axis=0)
        derived[f"pilot_split__{parent_leaf}__spend_hhi"] = (
            shares.pow(2).sum(axis=1).fillna(0).astype("float32"))
    out = pd.concat([out, pd.DataFrame(derived, index=out.index)], axis=1)
    out.to_parquet(FEATURE_PARQUET, index=False, compression="zstd")

    merged_keys = set(map(tuple, pilot[idx].astype(str).to_numpy()))
    base_keys = set(map(tuple, out[idx].astype(str).to_numpy()))
    qa = {
        "base_rows_after_provider_deduplication": len(out),
        "base_key_duplicates": int(out.duplicated(idx).sum()),
        "rows_with_any_pilot_parent": int((out[[c for c in out if c.startswith("pilot_parent__")]] > 0).any(axis=1).sum()),
        "aggregate_keys_not_in_model_base": len(merged_keys - base_keys),
        "reconciliation": recon,
    }
    (x3.OUT_DIR / "experiment3_subleaf_feature_qa.json").write_text(json.dumps(qa, indent=2))
    print(f"{len(out):,} rows, {len(out.columns):,} columns -> {FEATURE_PARQUET}", file=sys.stderr)
    return out


def _feature_sets(df: pd.DataFrame) -> dict[str, list[str]]:
    candidates = x3._candidate_cols(df)
    current = [c for c in candidates if not c.startswith("pilot_")]
    parents = [c for c in candidates if c.startswith("pilot_parent__")]
    children = [c for c in candidates if c.startswith(("pilot_child__", "pilot_split__"))]
    # Sensitivity after the frozen rich overlay: use only within-parent
    # composition, avoiding the many correlated raw child features.  The
    # one-parent sets show whether a useful split is being cancelled by a weak
    # split elsewhere.  They are exploratory, not promotion candidates.
    lean_suffixes = ("__n_share", "__months_share", "__debit_amt_share")
    lean = [
        c for c in children
        if c.startswith("pilot_split__")
        and (c.endswith(lean_suffixes) or c.endswith(("__breadth", "__spend_hhi")))
    ]
    child_parent = {r["experimental_subleaf"]: r["parent_leaf"] for r in _rules()}

    def belongs(col: str, parent: str) -> bool:
        stem = col.split("__")[1]
        return stem == parent or child_parent.get(stem) == parent

    out = {
        "current": current,
        "parent_control": current + parents,
        "subleaf_lean": current + parents + lean,
        "subleaf_overlay": current + parents + children,
    }
    for parent in sorted(set(child_parent.values())):
        out[f"split_{parent}"] = current + parents + [c for c in lean if belongs(c, parent)]
    return out


def _score_frame(frame: pd.DataFrame, ycol: str, pred: np.ndarray) -> dict:
    y = frame[ycol].astype(int).to_numpy()
    return {"n": len(y), "bads": int(y.sum()), "gini": round(float(signed_gini(pred, y)), 4)}


def _cv_variant(df: pd.DataFrame, target: str, variant: str, cols: list[str], cfg) -> tuple[dict, pd.DataFrame]:
    spec = champion.TARGETS[target]
    ycol = spec["ycol"]
    folds, frames = [], []
    for fold, (valid_start, valid_end) in enumerate(spec["folds"], 1):
        train = x3._window(df, spec["train_start"], valid_start, ycol)
        valid = x3._window(df, valid_start, valid_end, ycol)
        valid = valid[valid["provider"].eq("plaid")].copy()
        inner, stop = champion._inner_split(train, ycol)
        _, best = champion._fit_early(inner, stop, ycol, cols, cfg, CV_SEED)
        model = champion._fit_refit(train, ycol, cols, cfg, CV_SEED, best)
        pred = model.predict_proba(valid[cols])[:, 1]
        metric = _score_frame(valid, ycol, pred)
        metric.update({"fold": fold, "valid_start": valid_start, "valid_end": valid_end,
                       "train_n": len(train), "best_iteration": best})
        folds.append(metric)
        frames.append(pd.DataFrame({
            "financial_proposal_id": valid["financial_proposal_id"].astype(str),
            "provider": valid["provider"].astype(str), "target": target, "fold": fold,
            "y": valid[ycol].astype(int).to_numpy(), variant: pred,
        }))
        print(f"  {target} {variant} fold {fold}: GINI {metric['gini']:+.4f}", file=sys.stderr)
    pred_frame = pd.concat(frames, ignore_index=True)
    pooled = _score_frame(pred_frame.rename(columns={"y": ycol}), ycol, pred_frame[variant].to_numpy())
    return {"folds": folds, "pooled": pooled}, pred_frame


def _final_variant(df: pd.DataFrame, target: str, variant: str, cols: list[str], cfg):
    spec = champion.TARGETS[target]
    ycol = spec["ycol"]
    train = x3._window(df, spec["train_start"], spec["train_end"], ycol)
    oot = x3._window(df, spec["train_end"], spec["oot_end"], ycol)
    inner, stop = champion._inner_split(train, ycol)
    models, predictions, iterations = [], [], []
    for seed in FINAL_SEEDS:
        _, best = champion._fit_early(inner, stop, ycol, cols, cfg, seed)
        model = champion._fit_refit(train, ycol, cols, cfg, seed, best)
        models.append(model)
        predictions.append(model.predict_proba(oot[cols])[:, 1])
        iterations.append(best)
    pred = np.mean(predictions, axis=0)
    metrics = {"all": _score_frame(oot, ycol, pred), "iterations": iterations, "seed_ginis": []}
    for seed, values in zip(FINAL_SEEDS, predictions):
        metrics["seed_ginis"].append({"seed": seed, "gini": _score_frame(oot, ycol, values)["gini"]})
    plaid = oot["provider"].eq("plaid").to_numpy()
    metrics["plaid_only"] = _score_frame(oot.loc[plaid], ycol, pred[plaid])
    frame = pd.DataFrame({
        "financial_proposal_id": oot["financial_proposal_id"].astype(str),
        "provider": oot["provider"].astype(str), "target": target,
        "y": oot[ycol].astype(int).to_numpy(), variant: pred,
    })
    importance = np.mean([m.feature_importances_ for m in models], axis=0)
    return metrics, frame, models, importance


def _comparison(frame: pd.DataFrame, challenger: str, reference: str) -> dict:
    y = frame["y"].astype(int).to_numpy()
    out = champion._bootstrap_delta(
        y, frame[challenger].to_numpy(), frame[reference].to_numpy(), n_boot=2000)
    out["challenger"] = challenger
    out["reference"] = reference
    return out


def _coverage(agg: pd.DataFrame) -> dict:
    rows = []
    for (parent, child), group in agg.groupby(["parent_leaf", "experimental_subleaf"]):
        rows.append({
            "parent_leaf": parent, "experimental_subleaf": child,
            "transactions": int(group["n"].sum()),
            "proposal_provider_rows": int(len(group)),
            "debit_amount": round(float(group["debit_amt"].sum()), 2),
        })
    table = pd.DataFrame(rows)
    table["transaction_share_within_parent"] = table["transactions"] / table.groupby(
        "parent_leaf")["transactions"].transform("sum")
    return {"children": table.to_dict(orient="records")}


def _write_report(result: dict) -> None:
    rich = [result["targets"][t]["cv_comparisons"]["rich_vs_parent"] for t in champion.TARGETS]
    lean = [result["targets"][t]["cv_comparisons"]["lean_vs_parent"] for t in champion.TARGETS]
    clear_wins = sum(x["ci95"][0] > 0 for x in rich + lean)
    clear_losses = sum(x["ci95"][1] < 0 for x in rich + lean)
    if clear_wins >= len(champion.TARGETS):
        verdict = "The targeted expansion is supported on both risk horizons; proceed to human-labelled child validation before production adoption."
    elif clear_losses >= len(champion.TARGETS):
        verdict = "The targeted expansion is not supported: at least one risk horizon shows a statistically clear loss. Keep the 275-leaf taxonomy."
    else:
        verdict = "The pilot is inconclusive rather than evidence that more leaves are automatically better. Keep 275 as the production taxonomy and retain these children only as a shadow experiment."

    lines = [
        "# Experiment 3 shadow-subleaf pilot", "", f"**Decision:** {verdict}", "",
        "## What was tested", "",
        "Three existing parents were split into 15 mutually exclusive shadow buckets (12 net additional leaves, so 275 would become 287 if all were adopted). The production categorisation was not changed. Rules use only merchant and description text, were frozen before outcomes were inspected, and always fall back to the existing parent.", "",
        "The clean expansion test is **subleaf overlay vs parent control**. Both models receive exact totals for the three existing parents; only the challenger receives the within-parent child composition. This prevents a gain from being misattributed to splitting when it really came from merely exposing the parent leaf. The frozen rich overlay was followed by a lean composition-only sensitivity and one-parent-at-a-time ablations, explicitly marked exploratory.", "",
        "## Results", "",
        "### Rolling pre-OOT Plaid validation (primary)", "",
        "| target | current | + parent controls | + lean split | + rich split | lean delta (95% paired CI) | rich delta (95% paired CI) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for target, block in result["targets"].items():
        cv = block["cv"]
        lean_comp = block["cv_comparisons"]["lean_vs_parent"]
        rich_comp = block["cv_comparisons"]["rich_vs_parent"]
        lines.append(
            f"| {target} | {cv['current']['pooled']['gini']:.3f} | "
            f"{cv['parent_control']['pooled']['gini']:.3f} | "
            f"{cv['subleaf_lean']['pooled']['gini']:.3f} | "
            f"{cv['subleaf_overlay']['pooled']['gini']:.3f} | "
            f"{lean_comp['delta']:+.3f} ({lean_comp['ci95'][0]:+.3f} to {lean_comp['ci95'][1]:+.3f}) | "
            f"{rich_comp['delta']:+.3f} ({rich_comp['ci95'][0]:+.3f} to {rich_comp['ci95'][1]:+.3f}) |")
    lines += ["", "### One-parent-at-a-time rolling sensitivity (exploratory)", "",
              "| target | streaming delta | marketplace delta | payment-intermediary delta |",
              "|---|---:|---:|---:|"]
    for target, block in result["targets"].items():
        c = block["cv_comparisons"]
        lines.append(
            f"| {target} | {c['streaming_vs_parent']['delta']:+.3f} | "
            f"{c['marketplace_vs_parent']['delta']:+.3f} | "
            f"{c['payment_vs_parent']['delta']:+.3f} |")
    lines += ["", "### Existing development OOT (secondary confirmation)", "",
              "This window has been used by earlier Experiment 3 work, so it is confirmation evidence, not a fresh promotion test.", "",
              "| target | current | + parent controls | + lean split | + rich split | lean delta (95% CI) | rich delta (95% CI) |",
              "|---|---:|---:|---:|---:|---:|---:|"]
    for target, block in result["targets"].items():
        final = block["oot"]
        lean_comp = block["oot_comparisons"]["lean_vs_parent"]
        rich_comp = block["oot_comparisons"]["rich_vs_parent"]
        lines.append(
            f"| {target} | {final['current']['all']['gini']:.3f} | "
            f"{final['parent_control']['all']['gini']:.3f} | "
            f"{final['subleaf_lean']['all']['gini']:.3f} | "
            f"{final['subleaf_overlay']['all']['gini']:.3f} | "
            f"{lean_comp['delta']:+.3f} ({lean_comp['ci95'][0]:+.3f} to {lean_comp['ci95'][1]:+.3f}) | "
            f"{rich_comp['delta']:+.3f} ({rich_comp['ci95'][0]:+.3f} to {rich_comp['ci95'][1]:+.3f}) |")
    lines += ["", "## Coverage of the frozen rules", "",
              "| parent | shadow child | transactions | share within parent | proposal/provider rows |",
              "|---|---|---:|---:|---:|"]
    for row in sorted(result["coverage"]["children"], key=lambda r: (r["parent_leaf"], -r["transactions"])):
        lines.append(f"| {row['parent_leaf']} | {row['experimental_subleaf']} | {row['transactions']:,} | {row['transaction_share_within_parent']:.1%} | {row['proposal_provider_rows']:,} |")
    lines += ["", "## Guardrails and interpretation", "",
              "- Corrected as-of Experiment 3 transaction tables and current proposal features were used.",
              "- The same fixed regularised XGBoost recipe and chronological folds were used for every feature set; no split rule was selected on the OOT result. The lean and single-parent runs are post-primary sensitivity checks and are not presented as fresh confirmatory tests.",
              "- The primary comparison is paired on identical applicants. Final OOT predictions average seeds 0, 17 and 42.",
              "- Aggregate child counts and amounts reconcile exactly to their parent totals; every unmatched row falls back to its current parent.",
              "- No locked classifier v5/v6 evaluation set was read or scored.",
              "- A positive risk-model result would establish predictive utility, not semantic correctness. Before adding real leaves, sample and human-label each child, set minimum support/accuracy bars, and run fairness/stability checks on a fresh outcome vintage.", "",
              f"Machine-readable results: `{RESULTS_JSON.relative_to(ROOT)}`. Frozen rules: `{SPEC_PATH.relative_to(ROOT)}`."]
    REPORT.write_text("\n".join(lines) + "\n")


def train(df: pd.DataFrame | None = None, agg: pd.DataFrame | None = None) -> dict:
    if df is None:
        # B04 gated off: the parquet feature stores predate bound provenance.
        eval_protection.gate(
            "experiment3_subleaf_pilot.train",
            "unbound feature store; rebuild under the protected-release guard",
        )
        df = x3._prepare(pd.read_parquet(FEATURE_PARQUET))
    elif "created" not in df:
        df = x3._prepare(df)
    if agg is None:
        agg = pd.read_parquet(AGG_PARQUET)
    sets = _feature_sets(df)
    cfg = next(c for c in champion.CONFIGS if c.name == PILOT_CONFIG)
    result = {
        "method": {
            "primary_contrast": "subleaf_overlay vs parent_control",
            "model_config": PILOT_CONFIG,
            "cv_seed": CV_SEED, "final_seeds": list(FINAL_SEEDS),
            "rules_frozen_before_outcome_inspection": True,
            "locked_v5_v6_scored": False,
            "feature_source": str(x3.FEAT_PARQUET.relative_to(ROOT)),
            "feature_source_mtime_utc": pd.Timestamp(x3.FEAT_PARQUET.stat().st_mtime, unit="s", tz="UTC").isoformat(),
        },
        "feature_counts": {k: len(v) for k, v in sets.items()},
        "coverage": _coverage(agg),
        "reconciliation": _reconciliation(agg),
        "targets": {},
    }
    all_predictions = []
    for target in champion.TARGETS:
        print(f"\n{target}: rolling comparison", file=sys.stderr)
        cv_results, cv_frames = {}, []
        for variant, cols in sets.items():
            metrics, frame = _cv_variant(df, target, variant, cols, cfg)
            cv_results[variant] = metrics
            cv_frames.append(frame)
        cv = cv_frames[0]
        for frame in cv_frames[1:]:
            col = [c for c in sets if c in frame.columns][0]
            cv = cv.merge(frame[["financial_proposal_id", "provider", "target", "fold", "y", col]],
                          on=["financial_proposal_id", "provider", "target", "fold", "y"],
                          validate="one_to_one")
        cv_comps = {
            "rich_vs_parent": _comparison(cv, "subleaf_overlay", "parent_control"),
            "lean_vs_parent": _comparison(cv, "subleaf_lean", "parent_control"),
            "streaming_vs_parent": _comparison(cv, "split_streaming", "parent_control"),
            "marketplace_vs_parent": _comparison(cv, "split_marketplace_general", "parent_control"),
            "payment_vs_parent": _comparison(cv, "split_payment_intermediary", "parent_control"),
            "parent_vs_current": _comparison(cv, "parent_control", "current"),
        }

        print(f"{target}: development OOT comparison", file=sys.stderr)
        final_results, final_frames, final_models, importance = {}, [], {}, {}
        final_variants = ("current", "parent_control", "subleaf_lean", "subleaf_overlay")
        for variant in final_variants:
            cols = sets[variant]
            metrics, frame, models, imp = _final_variant(df, target, variant, cols, cfg)
            final_results[variant] = metrics
            final_frames.append(frame)
            final_models[variant] = models
            importance[variant] = imp
        final = final_frames[0]
        for frame in final_frames[1:]:
            col = [c for c in sets if c in frame.columns][0]
            final = final.merge(frame[["financial_proposal_id", "provider", "target", "y", col]],
                                on=["financial_proposal_id", "provider", "target", "y"],
                                validate="one_to_one")
        oot_comps = {
            "rich_vs_parent": _comparison(final, "subleaf_overlay", "parent_control"),
            "lean_vs_parent": _comparison(final, "subleaf_lean", "parent_control"),
            "parent_vs_current": _comparison(final, "parent_control", "current"),
        }
        child_cols = [c for c in sets["subleaf_overlay"] if c.startswith(("pilot_child__", "pilot_split__"))]
        imp = pd.Series(importance["subleaf_overlay"], index=sets["subleaf_overlay"])
        top = imp.loc[child_cols].sort_values(ascending=False).head(20)
        result["targets"][target] = {
            "cv": cv_results, "cv_comparisons": cv_comps,
            "oot": final_results, "oot_comparisons": oot_comps,
            "top_shadow_feature_importance": [
                {"feature": name, "importance": round(float(value), 6)} for name, value in top.items()],
        }
        cv["sample"] = "rolling_cv"
        final["sample"] = "development_oot"
        all_predictions.extend([cv, final])
    pd.concat(all_predictions, ignore_index=True, sort=False).to_parquet(
        PREDICTIONS_PARQUET, index=False, compression="zstd")
    RESULTS_JSON.write_text(json.dumps(result, indent=2))
    _write_report(result)
    print(f"Results -> {RESULTS_JSON}\nReport -> {REPORT}", file=sys.stderr)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("aggregate", "features", "train", "all"), nargs="?", default="all")
    args = parser.parse_args()
    if args.stage == "aggregate":
        aggregate()
    elif args.stage == "features":
        build_features()
    elif args.stage == "train":
        train()
    else:
        agg = aggregate()
        df = build_features(agg)
        train(df, agg)


if __name__ == "__main__":
    main()

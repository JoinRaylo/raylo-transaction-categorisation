"""Assert the Python eval waterfall equals the generated BigQuery waterfall.

Runs the SAME CASE bodies that `generate_crosswalk_sql.generate()` writes into
`sql/apply_crosswalk.sql` over the pipeline-eval rows (inlined via UNNEST, T4
via the loaded `credit_risk_research.merchant_dictionary_t4` table), and
compares leaf + tier with `final_evaluation.our_leaf()` row by row.

Why: on 2026-09-02 the Python mirror ran T4 before Equifax T1/T3 while the SQL
did the opposite, so `Identified Salary | General Groceries` @ `tesco` scored
`groceries` in Python and `salary` in BigQuery. Every pipeline headline is
measured in Python; this script is the guard that it is the SQL's number.

Usage:
    python src/check_waterfall_parity.py            # outputs/gold_pipeline_eval.csv
    python src/check_waterfall_parity.py path.csv   # any csv with the same columns
Exit code 1 on any leaf mismatch.
"""
from __future__ import annotations

import pathlib
import sys

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import generate_crosswalk_sql as gxw  # noqa: E402
import json  # noqa: E402
import subprocess  # noqa: E402
from eval_sets import refuse_confirmation_eval  # noqa: E402
from score_t5b_residual import _init_waterfall, attach_waterfall  # noqa: E402

EVAL_CSV = ROOT / "outputs" / "gold_pipeline_eval.csv"
OUT_CSV = ROOT / "outputs" / "waterfall_parity_mismatches.csv"

# Python mirror tier names -> SQL tier names (only where they legitimately differ).
TIER_ALIASES = {
    "T4_dictionary": "T4_merchant_dictionary",
    "T6_native_fallback": "T6_provider_crosswalk",
}


def _q(s) -> str:
    if s is None or (isinstance(s, float) and pd.isna(s)):
        s = ""
    s = str(s).replace("\\", "\\\\").replace("'", "\\'").replace("\n", " ").replace("\r", " ")
    return f"'{s}'"


def _split_native(provider, native):
    native = "" if native is None or (isinstance(native, float) and pd.isna(native)) else str(native)
    if str(provider).strip().lower() == "equifax":
        pri, sub = (native.split(" | ", 1) + [""])[:2] if native else ("", "")
        return pri, sub, ""
    return "", "", native


def build_query(df: pd.DataFrame) -> str:
    rows = []
    for i, r in enumerate(df.itertuples(index=False)):
        pri, sub, cat = _split_native(r.provider, getattr(r, "native_category", ""))
        rows.append(
            f"STRUCT({i} AS idx, {_q(str(r.provider).strip().lower())} AS provider, "
            f"{_q(r.merchant_raw)} AS merchant_raw, {_q(r.description_raw)} AS description_raw, "
            f"{_q(str(r.direction).strip().lower())} AS direction, "
            f"{_q(pri)} AS pri, {_q(sub)} AS sub, {_q(cat)} AS cat)"
        )
    return f"""
WITH sub_xw AS (SELECT * FROM UNNEST([STRUCT<eqx_sub STRING, leaf STRING>
{gxw.vals(gxw.sub_map)}
])),
pri_xw AS (SELECT * FROM UNNEST([STRUCT<eqx_pri STRING, leaf STRING>
{gxw.vals(gxw.pri_map)}
])),
plaid_xw AS (SELECT * FROM UNNEST([STRUCT<plaid_cat STRING, leaf STRING>
{gxw.vals(gxw.plaid_map)}
])),
{gxw.dict_xw_sql()},
eval_rows AS (SELECT * FROM UNNEST([
{",\n".join(rows)}
])),
eqx_raw AS (
  SELECT idx, pri, sub, merchant_raw AS vendor, description_raw, direction
  FROM eval_rows WHERE provider = 'equifax'
),
eqx_resolved AS (
  SELECT r.idx,
{gxw.eqx_leaf_case()}    END AS leaf,
{gxw.eqx_tier_case()}    END AS resolution_tier
  FROM eqx_raw r
  LEFT JOIN sub_xw s ON r.sub = s.eqx_sub
  LEFT JOIN pri_xw p ON r.pri = p.eqx_pri
  LEFT JOIN dict_xw d ON LOWER(TRIM(r.vendor)) = d.merchant
),
plaid_raw AS (
  SELECT idx, cat, merchant_raw, description_raw, direction
  FROM eval_rows WHERE provider != 'equifax'
),
plaid_resolved AS (
  SELECT r.idx,
{gxw.plaid_leaf_case()}    END AS leaf,
{gxw.plaid_tier_case()}    END AS resolution_tier
  FROM plaid_raw r
  LEFT JOIN plaid_xw x ON r.cat = x.plaid_cat
  LEFT JOIN dict_xw d ON LOWER(TRIM(r.merchant_raw)) = d.merchant
)
SELECT idx, leaf, resolution_tier FROM eqx_resolved
UNION ALL
SELECT idx, leaf, resolution_tier FROM plaid_resolved
ORDER BY idx
"""


def _bq_json_stdin(query: str):
    """Like build_tail_eval.bq_json but streams the query on stdin (a 500 KB
    query overflows the argv limit)."""
    proc = subprocess.run(
        ["bq", "query", "--use_legacy_sql=false", "--format=json", "--max_rows=1000000"],
        input=query, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        # bq writes query errors to stdout.
        sys.exit(f"bq failed (rc={proc.returncode}):\n{proc.stdout[-3000:]}\n{proc.stderr[-3000:]}")
    return json.loads(proc.stdout)


def normalise_tier(t: str) -> str:
    t = str(t)
    if t in TIER_ALIASES:
        return TIER_ALIASES[t]
    if t.startswith("T5_") and not t.startswith("T5_rule_"):
        return "T5_rule_" + t[3:]
    return t


def main(path: pathlib.Path = EVAL_CSV) -> int:
    refuse_confirmation_eval(path)
    df = pd.read_csv(path)
    need = {"provider", "merchant_raw", "description_raw", "direction", "native_category"}
    missing = need - set(df.columns)
    if missing:
        sys.exit(f"{path}: missing columns {sorted(missing)}")

    _init_waterfall()
    py = attach_waterfall(df).reset_index(drop=True)

    sql = build_query(df)
    if len(sql.encode("utf-8")) > 950_000:
        sys.exit(f"query too large for BigQuery ({len(sql):,} chars) — sample fewer rows")
    print(f"BigQuery: {len(df):,} rows, {len(sql):,} chars", file=sys.stderr)
    res = pd.DataFrame(_bq_json_stdin(sql))
    res["idx"] = res["idx"].astype(int)
    res = res.set_index("idx").reindex(range(len(df)))

    py_leaf = py["t6_leaf"].astype(str).to_numpy()
    py_tier = py["waterfall_tier"].astype(str).map(normalise_tier).to_numpy()
    sql_leaf = res["leaf"].astype(str).to_numpy()
    sql_tier = res["resolution_tier"].astype(str).to_numpy()

    leaf_mismatch = py_leaf != sql_leaf
    tier_mismatch = (py_tier != sql_tier) & ~leaf_mismatch
    n = len(df)
    print(f"leaf agreement: {n - int(leaf_mismatch.sum())}/{n} "
          f"({100 * (1 - leaf_mismatch.mean()):.2f}%)")
    print(f"tier-name disagreement with same leaf: {int(tier_mismatch.sum())}")

    out = df.copy()
    out["py_leaf"], out["py_tier"] = py_leaf, py_tier
    out["sql_leaf"], out["sql_tier"] = sql_leaf, sql_tier
    bad = out[leaf_mismatch | tier_mismatch]
    OUT_CSV.parent.mkdir(exist_ok=True)
    bad.to_csv(OUT_CSV, index=False)
    if len(bad):
        cols = ["provider", "merchant_raw", "direction", "native_category",
                "py_leaf", "py_tier", "sql_leaf", "sql_tier"]
        print(bad[cols].head(25).to_string(index=False))
        print(f"\n{len(bad)} rows written to {OUT_CSV}")
    return 1 if leaf_mismatch.any() else 0


if __name__ == "__main__":
    arg = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else EVAL_CSV
    sys.exit(main(arg))

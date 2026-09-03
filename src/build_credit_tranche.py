"""Credit labelling tranche (Week 2 of the 2 Sep review) — row-level, live Plaid.

Why: credits are 24.7% of live Plaid rows and half the money, 90% have a blank
merchant, but they are 0.6% of the classifier's training file; the pipeline scores
58% on credits vs 84% on debits. Merchant-level labelling cannot reach them.

What this builds (all under outputs/ until `apply`):
  fetch     30,000 live Plaid CREDIT rows, stratified by Plaid's own category ×
            amount band × blank-merchant, at most MAX_PER_TEXT rows per normalised
            (merchant, description) so "Faster Payment" does not fill the file,
            plus ~400 DEBIT rows that fall through T1–T5 (T6/T7-bound, computed with
            the shipped SQL CASE bodies) and look like risk leaves (Plaid category or
            narrative keyword) — the future T6-bound risk gold.
            Excludes every merchant in an eval set (holdout, risk gold, v5, v6,
            unified gold) and every exact row already in tuning_train.jsonl.
            The dictionary and tranches 1–4 are NOT excluded: a bookmaker credit or
            a retailer refund on a T4 merchant is exactly the direction-blind case we
            need labelled.
  label     Gemini 3.7 Flash and Sonnet 5 on the sample (row-level prompt shared
            with gold v6, via build_gold_v6_locked.label).
  tiebreak  Opus 5 on the disagreements.
  gate      consensus → agent_consensus; tiebreak agrees with one → agent_tiebreak;
            else needs_review. Writes outputs/credit_tranche_labels.csv.
  sheet     review workbook for Carlos: flagged rows + a BLIND 300-row slice.
  apply     after review: data/production_labels_credit_tranche.csv, a merchant-
            disjoint 2,000-row credit eval, the T6-bound risk gold, and the training
            top-up file build_tuning_dataset.py reads. Reads Flagged, Blind_300,
            and Accepted_remaps (Carlos-approved bulk retargets of agent labels).

Usage:
    python src/build_credit_tranche.py fetch
    python src/build_credit_tranche.py label gemini
    python src/build_credit_tranche.py label sonnet
    python src/build_credit_tranche.py tiebreak
    python src/build_credit_tranche.py gate
    python src/build_credit_tranche.py sheet
    python src/build_credit_tranche.py apply [completed.xlsx]
"""
from __future__ import annotations

import csv
import json
import pathlib
import sys
from collections import Counter, defaultdict

import pandas as pd
from dotenv import load_dotenv

load_dotenv()
ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "outputs"
sys.path.insert(0, str(ROOT / "src"))

import generate_crosswalk_sql as gxw  # noqa: E402
from build_gold_risk_categories import KEYWORD_FALLBACK  # noqa: E402
from build_tuning_dataset import frozen_holdout_merchants, load_risk_merchants  # noqa: E402
from eval_sets import _V6_GOLD_FILES  # noqa: E402

import os
TRANCHE = os.environ.get("TRANCHE", "credit")   # "credit" (2 Sep) or "risk" (3 Sep T6-bound risk debits)
N_CREDIT = 30_000
N_RISK_DEBIT = 400
N_RISK_TRANCHE = 5_000          # TRANCHE=risk: T6-bound risk-looking debits for TRAINING
RISK_FLOOR = 300                # per proxy bucket (gambling / debt collection / high-cost / savings / cards / overdraft)
MAX_PER_TEXT = 5          # rows per normalised (merchant, description)
OVERSAMPLE = 3            # rows fetched per stratum quota before dedupe/exclusion
SEED = 20260902

_P = f"{TRANCHE}_tranche"
SAMPLE_CSV = OUT_DIR / f"{_P}_sample.csv"
PRED = {k: OUT_DIR / f"{_P}_predictions_{k}.csv" for k in ("gemini", "sonnet", "opus")}
TIEBREAK_SAMPLE = OUT_DIR / f"{_P}_tiebreak_sample.csv"
LABELS_CSV = OUT_DIR / f"{_P}_labels.csv"
NEEDS_REVIEW_CSV = OUT_DIR / f"{_P}_needs_review.csv"
AGENT_ADJ_CSV = OUT_DIR / f"{_P}_agent_adjudication.csv"  # tier=agent_review, from the adjudication agent
REVIEW_XLSX = OUT_DIR / f"{_P}_review.xlsx"
REVIEW_COMPLETED_XLSX = OUT_DIR / f"{_P}_review_completed.xlsx"

FINAL_LABELS = ROOT / "data" / f"production_labels_{_P}.csv"
CREDIT_EVAL = ROOT / "data" / "gold_credit_eval.csv"
RISK_T6_GOLD = ROOT / "data" / "gold_transactions_risk_t6bound.csv"
CREDIT_TOPUP = ROOT / "data" / "tuning_credit_topup.csv"
RISK_TOPUP = ROOT / "data" / "tuning_risk_topup.csv"    # TRANCHE=risk output (training only; gold is the 400-row set)
N_CREDIT_EVAL = 2_000
N_BLIND = 300

PLAID = "`raylo-production.dbt_production.credit_plaid_open_banking_transactions`"
AMT_BAND = """CASE WHEN ABS(amount) < 50 THEN 'lt50' WHEN ABS(amount) < 500 THEN '50_500'
              WHEN ABS(amount) < 2500 THEN '500_2500' ELSE '2500_plus' END"""
RISK_PLAID_CATS = ("ENTERTAINMENT_CASINOS_AND_GAMBLING", "LOAN_PAYMENTS_CREDIT_CARD_PAYMENT",
                   "LOAN_PAYMENTS_PERSONAL_LOAN_PAYMENT", "LOAN_PAYMENTS_OTHER_PAYMENT",
                   "LOAN_PAYMENTS_CAR_PAYMENT", "LOAN_PAYMENTS_MORTGAGE_PAYMENT",
                   "LOAN_PAYMENTS_STUDENT_LOAN_PAYMENT", "BANK_FEES_OVERDRAFT_FEES",
                   "BANK_FEES_INTEREST_CHARGE", "BANK_FEES_OTHER_BANK_FEES")


def _norm(s):
    return (s or "").strip().lower() if isinstance(s, str) else ""


def eval_merchants() -> set[str]:
    """Merchants in ANY eval set (not the dictionary / tranches — those are fine to label)."""
    seen = frozen_holdout_merchants() | load_risk_merchants()
    for fname in _V6_GOLD_FILES:
        p = ROOT / "data" / fname
        if p.exists():
            for r in csv.DictReader(open(p)):
                seen.add(_norm(r.get("merchant_raw") or r.get("merchant") or ""))
    seen.discard("")
    return seen


def train_keys() -> set[tuple]:
    from score_waterfall_pipeline import load_train_jsonl
    keys, _ = load_train_jsonl()
    return keys


# ------------------------------------------------------------------ fetch
def _credit_sql() -> str:
    return f"""
WITH r AS (
  SELECT merchant_name AS merchant_raw,
         COALESCE(original_description, transaction_name) AS description_raw,
         amount, 'credit' AS direction, credit_category_detailed AS native_category,
         IFNULL(credit_category_detailed, 'NULL') AS cat,
         {AMT_BAND} AS amt_band,
         IF(merchant_name IS NULL OR TRIM(merchant_name) = '', 'blank', 'filled') AS merchant_state,
         transaction_date
  FROM {PLAID}
  WHERE amount < 0
),
strata AS (
  SELECT cat, amt_band, merchant_state, COUNT(*) AS n FROM r GROUP BY 1, 2, 3
),
quota AS (
  -- 60% of the budget proportional to volume, 40% spread equally across strata
  -- (floor 40), so small-but-important strata (gambling, loan disbursements,
  -- tax refunds) get labelled too. Oversampled x{OVERSAMPLE} before dedupe.
  SELECT cat, amt_band, merchant_state, n,
         CAST(CEIL(({N_CREDIT} * 0.6 * n / SUM(n) OVER () + {N_CREDIT} * 0.4 / COUNT(*) OVER ()) * {OVERSAMPLE}) AS INT64) AS q
  FROM strata
),
picked AS (
  SELECT r.*, q.q,
         ROW_NUMBER() OVER (PARTITION BY r.cat, r.amt_band, r.merchant_state ORDER BY RAND()) AS rn
  FROM r JOIN quota q USING (cat, amt_band, merchant_state)
)
SELECT merchant_raw, description_raw, amount, direction, native_category, cat, amt_band,
       merchant_state, transaction_date
FROM picked WHERE rn <= GREATEST(q, 40)
"""


def _risk_debit_sql() -> str:
    kw = "|".join(f"(?:{p})" for p in KEYWORD_FALLBACK.values()) + \
         r"|\bbet\b|betting|casino|bingo|lottery|payday|loan|overdraft|klarna|clearpay|bnpl|credit card"
    kw_sql = kw.replace("\\", "\\\\")
    cats = ", ".join(f"'{c}'" for c in RISK_PLAID_CATS)
    return f"""
WITH plaid_xw AS (SELECT * FROM UNNEST([STRUCT<plaid_cat STRING, leaf STRING>
{gxw.vals(gxw.plaid_map)}
])),
{gxw.dict_xw_sql()},
plaid_raw AS (
  SELECT credit_category_detailed AS cat, merchant_name AS merchant_raw,
         COALESCE(original_description, transaction_name) AS description_raw,
         'debit' AS direction, amount AS Amount, transaction_date
  FROM {PLAID}
  WHERE amount > 0
    AND (credit_category_detailed IN ({cats})
         OR REGEXP_CONTAINS(LOWER(COALESCE(original_description, transaction_name, '')), r'{kw_sql}'))
),
resolved AS (
  SELECT r.*,
{gxw.plaid_tier_case()}    END AS resolution_tier
  FROM plaid_raw r
  LEFT JOIN plaid_xw x ON r.cat = x.plaid_cat
  LEFT JOIN dict_xw d ON LOWER(TRIM(r.merchant_raw)) = d.merchant
)
SELECT merchant_raw, description_raw, Amount AS amount, direction, cat AS native_category,
       cat, 'debit' AS amt_band,
       IF(merchant_raw IS NULL OR TRIM(merchant_raw) = '', 'blank', 'filled') AS merchant_state,
       transaction_date, resolution_tier
FROM resolved
WHERE NOT REGEXP_CONTAINS(resolution_tier, r'^T[1-5]_')
ORDER BY RAND()
LIMIT {N_RISK_DEBIT * OVERSAMPLE}
"""


RISK_BUCKETS = {
    "gambling": r"\bbet\b|betting|casino|bingo|lottery|lotto|poker|slots|gambl",
    "debt_collection": r"debt|collection|recover|enforcement|bailiff|arrears|lowell|cabot|moorcroft|pra group|intrum|zinc",
    "high_cost_credit": r"payday|wonga|lending\s*stream|quickquid|cashfloat|moneyboat|dot\s*dot|creditspring|fund\s*ourselves|pawn|cash\s*converters|loan",
    "cards": r"credit\s*card|\*{3,}\d{3,}|amex|american\s*exp|barclaycard|mbna|capital\s*one|aqua|vanquis|newday|marbles",
    "overdraft_fees": r"overdraft|unarranged|unpaid\s*item|returned\s*item|account\s*fee|monthly\s*fee|maintaining\s*the\s*account",
    "bnpl_savings": r"klarna|clearpay|zilch|laybuy|bnpl|pay\s*in\s*3|saver|savings|\bpot\b|round\s*up",
}


def _bucket(desc: str) -> str:
    import re as _re
    d = (desc or "").lower()
    for b, pat in RISK_BUCKETS.items():
        if _re.search(pat, d):
            return b
    return "other"


def fetch_risk_tranche():
    """TRANCHE=risk: N_RISK_TRANCHE T6-bound risk-looking debits for TRAINING, with a floor per
    proxy bucket so gambling / debt collection / high-cost credit / savings are not starved.
    Excludes eval-set merchants (incl. the 400-row T6-bound gold) and training rows."""
    from google.cloud import bigquery
    client = bigquery.Client(project="raylo-production")
    excluded = eval_merchants()
    tkeys = train_keys()
    gold_texts = set()
    if RISK_T6_GOLD.exists():
        g = pd.read_csv(RISK_T6_GOLD, dtype=str).fillna("")
        gold_texts = set(g["merchant_raw"].map(_norm) + "||" + g["description_raw"].map(_norm))
    sql = _risk_debit_sql().replace(f"LIMIT {N_RISK_DEBIT * OVERSAMPLE}", f"LIMIT {N_RISK_TRANCHE * OVERSAMPLE * 2}")
    df = client.query(sql).to_dataframe(create_bqstorage_client=True)
    m = df["merchant_raw"].fillna("").map(_norm); d = df["description_raw"].fillna("").map(_norm)
    before = len(df)
    df = df[~m.isin(excluded) & ~(m + "||" + d).isin(gold_texts)].copy()
    from score_waterfall_pipeline import row_key
    keys = [row_key(a, b, c, e) for a, b, c, e in
            zip(df["merchant_raw"].fillna(""), df["description_raw"].fillna(""), df["amount"], df["direction"])]
    df = df[[k not in tkeys for k in keys]].copy()
    df["_text"] = df["merchant_raw"].fillna("").map(_norm) + "||" + df["description_raw"].fillna("").map(_norm)
    df = df.sample(frac=1.0, random_state=SEED)
    df = df[df.groupby("_text").cumcount() < MAX_PER_TEXT]
    df["bucket"] = df["description_raw"].fillna("").map(_bucket)
    print(f"  fetched {before:,} → {len(df):,} after exclusions/cap; buckets: {df.bucket.value_counts().to_dict()}", file=sys.stderr)
    parts = []
    remaining = N_RISK_TRANCHE
    for b, g in df.groupby("bucket"):
        take = min(len(g), RISK_FLOOR); parts.append(g.head(take)); remaining -= take
    taken = pd.concat(parts)
    rest = df.drop(taken.index)
    out = pd.concat([taken, rest.head(max(remaining, 0))]).sample(frac=1.0, random_state=SEED).reset_index(drop=True)
    out = out.drop(columns=["_text"])
    out["stratum"] = "risk_t6bound_debit"
    out["provider"] = "plaid"
    out.insert(0, "row_id", range(len(out)))
    OUT_DIR.mkdir(exist_ok=True)
    out.to_csv(SAMPLE_CSV, index=False)
    print(f"Wrote {SAMPLE_CSV}: {len(out):,} rows; buckets {out.bucket.value_counts().to_dict()}; "
          f"blank merchant {(out.merchant_raw.fillna('') == '').mean():.0%}; distinct texts "
          f"{(out.merchant_raw.fillna('').map(_norm) + '||' + out.description_raw.fillna('').map(_norm)).nunique():,}",
          file=sys.stderr)


def fetch():
    from google.cloud import bigquery
    client = bigquery.Client(project="raylo-production")
    excluded = eval_merchants()
    tkeys = train_keys()
    print(f"excluding {len(excluded):,} eval-set merchants and {len(tkeys):,} training row keys", file=sys.stderr)

    def clean(df, label):
        m = df["merchant_raw"].fillna("").map(_norm)
        d = df["description_raw"].fillna("").map(_norm)
        before = len(df)
        keep = ~m.isin(excluded)
        df = df[keep].copy(); m = m[keep]; d = d[keep]
        n_excl = before - len(df)
        from score_waterfall_pipeline import row_key
        keys = [row_key(a, b, c, e) for a, b, c, e in
                zip(df["merchant_raw"].fillna(""), df["description_raw"].fillna(""), df["amount"], df["direction"])]
        df = df[[k not in tkeys for k in keys]].copy()
        n_train = before - n_excl - len(df)
        df["_text"] = (df["merchant_raw"].fillna("").map(_norm) + "||" + df["description_raw"].fillna("").map(_norm))
        df = df.sample(frac=1.0, random_state=SEED)
        df["_rank"] = df.groupby("_text").cumcount()
        n_before_cap = len(df)
        df = df[df["_rank"] < MAX_PER_TEXT].drop(columns=["_rank"])
        print(f"  [{label}] {before:,} fetched → −{n_excl:,} eval merchants → −{n_train:,} training rows "
              f"→ −{n_before_cap - len(df):,} over the {MAX_PER_TEXT}-per-text cap → {len(df):,}", file=sys.stderr)
        return df

    print("Fetching stratified credits...", file=sys.stderr)
    cred = client.query(_credit_sql()).to_dataframe(create_bqstorage_client=True)
    cred = clean(cred, "credits")
    # Trim to N_CREDIT respecting the stratum quotas (proportional to what survived).
    quota = cred.groupby(["cat", "amt_band", "merchant_state"]).size()
    target = (quota / quota.sum() * N_CREDIT).round().astype(int).clip(lower=1)
    parts = []
    for key, g in cred.groupby(["cat", "amt_band", "merchant_state"]):
        parts.append(g.head(int(target.get(key, 0))))
    cred = pd.concat(parts).sample(frac=1.0, random_state=SEED).head(N_CREDIT)
    cred["stratum"] = "credit"

    print("Fetching T6-bound risk-looking debits...", file=sys.stderr)
    risk = client.query(_risk_debit_sql()).to_dataframe(create_bqstorage_client=True)
    risk = clean(risk, "risk debits").head(N_RISK_DEBIT)
    risk["stratum"] = "risk_t6bound_debit"

    df = pd.concat([cred, risk], ignore_index=True).drop(columns=["_text"])
    df["provider"] = "plaid"
    df.insert(1, "merchant", df["merchant_raw"].fillna("").map(_norm))  # v6.label expects it
    df.insert(0, "row_id", range(len(df)))
    OUT_DIR.mkdir(exist_ok=True)
    df.to_csv(SAMPLE_CSV, index=False)
    print(f"\nWrote {SAMPLE_CSV}: {len(df):,} rows "
          f"({int((df.stratum == 'credit').sum()):,} credits, {int((df.stratum != 'credit').sum())} risk debits)",
          file=sys.stderr)
    c = df[df.stratum == "credit"]
    print("credit strata (native category):", c["cat"].value_counts().head(12).to_dict(), file=sys.stderr)
    print("credit blank-merchant share:", f"{(c.merchant_state == 'blank').mean():.1%}",
          "| amount bands:", c["amt_band"].value_counts().to_dict(), file=sys.stderr)
    print("distinct texts:", c[["merchant_raw", "description_raw"]].fillna("").astype(str).agg("||".join, axis=1).nunique(),
          file=sys.stderr)


# ------------------------------------------------------------------ label
def _v6_with(sample_csv, preds):
    import build_gold_v6_locked as v6
    v6.SAMPLE_CSV = sample_csv
    v6.PREDICTIONS = preds
    v6.GEMINI_THINKING_BUDGET = 0
    v6.V6_MODELS["opus"] = {"backend": "anthropic", "id": "claude-opus-5", "max_tokens": 16000, "extra": {}}
    return v6


def label(model_key):
    v6 = _v6_with(SAMPLE_CSV, PRED)
    v6.label(model_key)


def tiebreak():
    rows = list(csv.DictReader(open(SAMPLE_CSV)))
    g = {r["row_id"]: r["llm_leaf"] for r in csv.DictReader(open(PRED["gemini"]))}
    s = {r["row_id"]: r["llm_leaf"] for r in csv.DictReader(open(PRED["sonnet"]))}
    dis = [r for r in rows if g.get(r["row_id"]) and s.get(r["row_id"]) and g[r["row_id"]] != s[r["row_id"]]]
    with open(TIEBREAK_SAMPLE, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(dis)
    print(f"{len(dis):,} disagreements of {len(rows):,} → Opus tiebreak", file=sys.stderr)
    v6 = _v6_with(TIEBREAK_SAMPLE, PRED)
    v6.label("opus")


def gate():
    from confusion_analysis import load_taxonomy
    gen_of, risk_leaves = load_taxonomy()
    rows = list(csv.DictReader(open(SAMPLE_CSV)))
    g = {r["row_id"]: r for r in csv.DictReader(open(PRED["gemini"]))}
    s = {r["row_id"]: r for r in csv.DictReader(open(PRED["sonnet"]))}
    o = {r["row_id"]: r for r in csv.DictReader(open(PRED["opus"]))} if PRED["opus"].exists() else {}
    out, tiers = [], Counter()
    for r in rows:
        gl = g.get(r["row_id"], {}).get("llm_leaf", ""); sl = s.get(r["row_id"], {}).get("llm_leaf", "")
        ol = o.get(r["row_id"], {}).get("llm_leaf", "")
        if gl and gl == sl:
            final, tier, src = gl, "agent_consensus", "gemini==sonnet"
        elif ol and ol in (gl, sl):
            final, tier, src = ol, "agent_tiebreak", "opus==" + ("gemini" if ol == gl else "sonnet")
        elif gl and sl:
            final, tier, src = "", "needs_review", "three-way split" if ol else "no tiebreak"
        else:
            final, tier, src = "", "needs_review", "missing prediction"
        # Risk-family and income leaves on the T6-bound debit stratum always go to review.
        if TRANCHE == "credit" and r["stratum"] != "credit" and tier != "needs_review":
            tier = "agent_" + tier.split("_", 1)[1] + "_review_required"
        tiers[tier] += 1
        out.append({**r, "gemini_leaf": gl, "sonnet_leaf": sl, "opus_leaf": ol,
                    "final_leaf": final, "tier": tier, "resolution_source": src,
                    "general_category": gen_of.get(final, "")})
    # Agent adjudication of the three-way splits (same role as the v6 agent pass):
    # sets final_leaf with tier=agent_review; rows it left blank stay needs_review.
    if AGENT_ADJ_CSV.exists():
        adj = {r["row_id"]: r for r in csv.DictReader(open(AGENT_ADJ_CSV))}
        n_adj = 0
        for r in out:
            a = adj.get(r["row_id"])
            if a and a.get("final_leaf") and r["tier"] == "needs_review":
                if a["final_leaf"] not in gen_of:
                    sys.exit(f"adjudication row {r['row_id']}: {a['final_leaf']!r} not a taxonomy leaf")
                r.update(final_leaf=a["final_leaf"], tier="agent_review",
                         resolution_source=f"agent_review: {a.get('note', '')[:120]}",
                         general_category=gen_of[a["final_leaf"]])
                tiers["needs_review"] -= 1; tiers["agent_review"] += 1; n_adj += 1
        print(f"agent adjudication applied to {n_adj} rows", file=sys.stderr)
    with open(LABELS_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader(); w.writerows(out)
    print(f"Wrote {LABELS_CSV}: {dict(tiers)}", file=sys.stderr)
    fin = Counter(r["final_leaf"] for r in out if r["final_leaf"])
    print("top final leaves:", fin.most_common(12), file=sys.stderr)


# ------------------------------------------------------------------ sheet / apply
def sheet():
    rows = list(csv.DictReader(open(LABELS_CSV)))
    import random
    rng = random.Random(SEED)
    flagged = [r for r in rows if r["tier"] == "needs_review" or r["tier"].endswith("review_required")]
    accepted = [r for r in rows if r["tier"] in ("agent_consensus", "agent_tiebreak", "agent_review")]
    blind = rng.sample(accepted, min(N_BLIND, len(accepted)))
    cols = ["row_id", "stratum", "merchant_raw", "description_raw", "amount", "direction", "native_category",
            "gemini_leaf", "sonnet_leaf", "opus_leaf", "final_leaf", "tier", "resolution_source"]
    with pd.ExcelWriter(REVIEW_XLSX) as xw:
        f = pd.DataFrame(flagged)[cols].copy(); f["carlos_leaf"] = ""; f["carlos_note"] = ""
        f.to_excel(xw, sheet_name="Flagged", index=False)
        b = pd.DataFrame(blind)[["row_id", "stratum", "merchant_raw", "description_raw", "amount",
                                 "direction", "native_category"]].copy()
        b["carlos_leaf"] = ""; b["carlos_note"] = ""
        b.to_excel(xw, sheet_name="Blind_300", index=False)  # labels deliberately withheld
        pd.DataFrame(blind)[["row_id", "final_leaf", "tier"]].to_excel(xw, sheet_name="Blind_300_key", index=False)
        pd.DataFrame([
            {"sheet": "Flagged", "rows": len(f), "what": "fill carlos_leaf (taxonomy leaf) or leave blank to drop the row"},
            {"sheet": "Blind_300", "rows": len(b), "what": "label WITHOUT looking at Blind_300_key; measures the label-noise ceiling"},
        ]).to_excel(xw, sheet_name="README", index=False)
    print(f"Wrote {REVIEW_XLSX}: {len(flagged)} flagged + {len(blind)} blind", file=sys.stderr)


def apply_review(path=None):
    path = pathlib.Path(path) if path else REVIEW_COMPLETED_XLSX
    rows = {r["row_id"]: r for r in csv.DictReader(open(LABELS_CSV))}
    from confusion_analysis import load_taxonomy
    gen_of, _ = load_taxonomy()
    if path.exists():
        flagged = pd.read_excel(path, sheet_name="Flagged", dtype=str).fillna("")
        n_set = 0
        n_drop = 0
        for _, r in flagged.iterrows():
            rid = str(r["row_id"]).strip()
            if rid not in rows:
                sys.exit(f"row {rid}: not in {LABELS_CSV}")
            leaf = r["carlos_leaf"].strip()
            if leaf:
                if leaf not in gen_of:
                    sys.exit(f"row {rid}: {leaf!r} is not a taxonomy leaf")
                rows[rid].update(final_leaf=leaf, tier="human_reviewed", resolution_source="carlos",
                                 reviewer_id="carlos", general_category=gen_of[leaf]); n_set += 1
            else:
                rows[rid].update(final_leaf="", tier="dropped", resolution_source="carlos_drop")
                n_drop += 1
        blind = pd.read_excel(path, sheet_name="Blind_300", dtype=str).fillna("")
        key = pd.read_excel(path, sheet_name="Blind_300_key", dtype=str).fillna("")
        merged = blind.merge(key, on="row_id")
        done = merged[merged["carlos_leaf"].str.strip() != ""]
        if len(done):
            agree = (done["carlos_leaf"].str.strip() == done["final_leaf"]).mean()
            print(f"BLIND SLICE: Carlos vs agent final agreement {agree:.1%} on {len(done)} rows "
                  f"(label-noise ceiling for this tranche)", file=sys.stderr)
            for _, r in done.iterrows():
                rid = str(r["row_id"]).strip()
                leaf = r["carlos_leaf"].strip()
                if leaf not in gen_of:
                    sys.exit(f"Blind_300 row {rid}: {leaf!r} is not a taxonomy leaf")
                rows[rid].update(final_leaf=leaf, tier="human_reviewed",
                                 resolution_source="carlos", reviewer_id="carlos",
                                 general_category=gen_of[leaf])
        print(f"applied {n_set} flagged labels from {path.name} (dropped {n_drop})", file=sys.stderr)
        # Carlos-approved retargets of agent labels (conventions A/E/G/T1 etc.).
        # Does not overwrite human_reviewed rows from Flagged / Blind_300.
        try:
            remaps = pd.read_excel(path, sheet_name="Accepted_remaps", dtype=str).fillna("")
        except ValueError:
            remaps = pd.DataFrame()
        n_remap = 0
        for _, r in remaps.iterrows():
            rid = str(r.get("row_id", "")).strip()
            leaf = str(r.get("new_leaf", "")).strip()
            if not rid or not leaf or rid not in rows:
                continue
            if rows[rid].get("tier") in ("human_reviewed", "dropped"):
                continue
            if leaf not in gen_of:
                sys.exit(f"Accepted_remaps row {rid}: {leaf!r} is not a taxonomy leaf")
            rows[rid].update(final_leaf=leaf, tier="agent_review",
                             resolution_source=f"carlos_remap: {str(r.get('reason', ''))[:120]}",
                             general_category=gen_of[leaf])
            n_remap += 1
        if n_remap:
            print(f"applied {n_remap} accepted-row remaps from {path.name}", file=sys.stderr)
    else:
        print(f"no completed workbook at {path}; applying agent labels only", file=sys.stderr)

    keep = [r for r in rows.values() if r["final_leaf"] and r["tier"] in
            ("agent_consensus", "agent_tiebreak", "agent_review", "human_reviewed")]
    df = pd.DataFrame(keep)
    for c in ("reviewer_id",):
        if c not in df.columns:
            df[c] = ""
    df.to_csv(FINAL_LABELS, index=False)
    print(f"Wrote {FINAL_LABELS}: {len(df):,} labelled rows", file=sys.stderr)

    if TRANCHE == "risk":
        tr = df.rename(columns={"final_leaf": "gold_leaf"})
        tr.to_csv(RISK_TOPUP, index=False)
        print(f"risk training top-up {len(tr):,} rows → {RISK_TOPUP} (gold stays the 400-row T6-bound set)", file=sys.stderr)
        return
    # Splits. Credit eval is merchant-disjoint from everything else in this tranche:
    # pick whole merchant groups (blank merchants split by description text) until 2,000.
    cred = df[df["stratum"] == "credit"].copy()
    cred["_grp"] = cred["merchant_raw"].fillna("").map(_norm)
    blank = cred["_grp"] == ""
    cred.loc[blank, "_grp"] = "desc::" + cred.loc[blank, "description_raw"].fillna("").map(_norm)
    groups = cred["_grp"].drop_duplicates().sample(frac=1.0, random_state=SEED).tolist()
    ev_groups, n = set(), 0
    for gname in groups:
        if n >= N_CREDIT_EVAL:
            break
        ev_groups.add(gname); n += int((cred["_grp"] == gname).sum())
    ev = cred[cred["_grp"].isin(ev_groups)].drop(columns=["_grp"])
    tr = cred[~cred["_grp"].isin(ev_groups)].drop(columns=["_grp"])
    ev.rename(columns={"final_leaf": "gold_leaf"}).to_csv(CREDIT_EVAL, index=False)
    tr.rename(columns={"final_leaf": "gold_leaf"}).to_csv(CREDIT_TOPUP, index=False)
    rk = df[df["stratum"] != "credit"].rename(columns={"final_leaf": "gold_leaf"})
    rk.to_csv(RISK_T6_GOLD, index=False)
    print(f"credit eval {len(ev):,} rows ({len(ev_groups)} merchant/text groups) → {CREDIT_EVAL}\n"
          f"credit training top-up {len(tr):,} rows → {CREDIT_TOPUP}\n"
          f"T6-bound risk gold {len(rk)} rows → {RISK_T6_GOLD}", file=sys.stderr)


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    cmd = args[0]
    if cmd == "fetch":
        fetch_risk_tranche() if TRANCHE == "risk" else fetch()
    elif cmd == "label":
        label(args[1])
    elif cmd == "tiebreak":
        tiebreak()
    elif cmd == "gate":
        gate()
    elif cmd == "sheet":
        sheet()
    elif cmd == "apply":
        apply_review(args[1] if len(args) > 1 else None)
    else:
        sys.exit(__doc__)

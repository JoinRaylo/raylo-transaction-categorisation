"""Measure the real IV impact of the R13 rent-detection fix (2026-08-21).

Compares the `rent` feature (persistence form -- COUNT DISTINCT months with a
rent transaction, the feature form CLAUDE.md's own findings show beats
spend-share by up to 20x) computed two ways: OLD (R13 disabled, matching the
crosswalk before today's fix) vs NEW (R13 enabled, with the exclude_pattern).

Reuses the exact tested waterfall logic from final_evaluation.py
(our_leaf/eqx_native_leaf) rather than re-deriving it, run twice with
different RULES lists (with/without R13) -- everything else in the waterfall
is identical between old and new, so this isolates R13's effect precisely.

Candidate set (not the full 73M-row dump -- only transactions that could
possibly resolve to `rent` under EITHER old or new logic need fetching;
everything else is unaffected and doesn't need recomputing):
  - SubCategoryDescription = 'Property Rental' (native T6 match, same both ways)
  - VendorDescription is a dictionary landlord/agent match (T4, same both ways)
  - description contains rent/landlord as a whole word (only this is new -- R13)

Excludes final_matched_on = 'name_time' (fuzzy, untrustworthy) per CLAUDE.md.

Usage: python src/rent_iv_analysis.py
"""
import sys
import pathlib
from collections import defaultdict

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import final_evaluation as fe  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
REPORT_MD = ROOT / "data" / "rent_iv_report.md"

OUTCOMES = ["month3_1plus_pia", "month12_1plus_pia", "month12_3plus_pia"]


def fetch():
    from google.cloud import bigquery
    client = bigquery.Client(project="raylo-production")

    fe.SUB_MAP, fe.PRI_MAP, fe.PLAID_MAP, gen_of = fe.load_crosswalk()
    fe.DICTIONARY = fe.load_dictionary()
    dict_landlord_merchants = [m for m, leaf in fe.DICTIONARY.items() if leaf == "rent"]
    print(f"{len(dict_landlord_merchants)} dictionary merchants map to rent", file=sys.stderr)

    print("Pulling rent-candidate transactions (Equifax, matched to proposals, "
          "excluding name_time matches)...", file=sys.stderr)
    sql = """
    SELECT financial_proposal_id, DATE_TRUNC(PostDate, MONTH) AS month,
           VendorDescription AS vendor, Description AS description,
           SubCategoryDescription AS sub, PrimaryCategoryDescription AS pri,
           IF(TransactionTypeId=1,'credit','debit') AS direction
    FROM `raylo-production.equifax_data.open_banking_transactions_with_matches`
    WHERE final_matched_on != 'name_time'
      AND financial_proposal_id IS NOT NULL
      AND (
        SubCategoryDescription = 'Property Rental'
        OR REGEXP_CONTAINS(LOWER(Description), r'\\b(rent|landlord)\\b')
        OR LOWER(TRIM(VendorDescription)) IN UNNEST(@landlords)
      )
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ArrayQueryParameter("landlords", "STRING", dict_landlord_merchants)]
    )
    df = client.query(sql, job_config=job_config).result().to_dataframe()
    print(f"Fetched {len(df)} candidate transactions across {df['financial_proposal_id'].nunique()} proposals",
          file=sys.stderr)
    df.to_parquet(ROOT / "outputs" / "rent_candidates.parquet", index=False)

    print("Pulling outcome cohort restricted to proposals with matched Equifax data "
          "(per CLAUDE.md's documented ~37k-proposal cohort)...", file=sys.stderr)
    cols = ", ".join(["m." + c for c in ["financial_proposal_id"] + OUTCOMES])
    outcomes = client.query(f"""
        SELECT {cols}
        FROM `raylo-production.dbt_production.ds_first_order_proposal_pia_metrics` m
        WHERE m.financial_proposal_id IN (
            SELECT DISTINCT financial_proposal_id
            FROM `raylo-production.equifax_data.open_banking_transactions_with_matches`
            WHERE final_matched_on != 'name_time' AND financial_proposal_id IS NOT NULL
        )
    """).result().to_dataframe()
    print(f"Outcome cohort: {len(outcomes)} proposals", file=sys.stderr)
    outcomes.to_parquet(ROOT / "outputs" / "rent_outcomes.parquet", index=False)


def _iv(x, y):
    """Manual WoE/IV: bin 0 vs 1 vs 2+ months of rent persistence (optbinning has a
    scikit-learn incompatibility in this env -- check_array's force_all_finite arg
    was renamed -- so compute the standard formula directly instead of chasing that)."""
    import numpy as np
    bins = np.where(x == 0, "0", np.where(x == 1, "1", "2+"))
    total_good = (y == 0).sum()
    total_bad = (y == 1).sum()
    iv = 0.0
    for b in sorted(set(bins)):
        mask = bins == b
        good = (y[mask] == 0).sum()
        bad = (y[mask] == 1).sum()
        good_pct = max(good, 0.5) / total_good
        bad_pct = max(bad, 0.5) / total_bad
        woe = np.log(bad_pct / good_pct)
        iv += (bad_pct - good_pct) * woe
    return iv


def compute():
    fe.SUB_MAP, fe.PRI_MAP, fe.PLAID_MAP, gen_of = fe.load_crosswalk()
    fe.DICTIONARY = fe.load_dictionary()
    all_rules = fe.load_rules()
    rules_with_r13 = all_rules
    rules_without_r13 = [r for r in all_rules if r["rule_id"] != "R13"]

    df = pd.read_parquet(ROOT / "outputs" / "rent_candidates.parquet")
    outcomes = pd.read_parquet(ROOT / "outputs" / "rent_outcomes.parquet")
    for col in ("vendor", "description", "sub", "pri"):
        df[col] = df[col].fillna("")

    def leaf_for(row, rules):
        fe.RULES = rules
        return fe.our_leaf(row["vendor"], row["direction"], row["description"],
                            fe.eqx_native_leaf, row["pri"], row["sub"], row["direction"])[0]

    print("Computing OLD (R13 disabled) leaf per candidate transaction...", file=sys.stderr)
    df["old_leaf"] = df.apply(lambda r: leaf_for(r, rules_without_r13), axis=1)
    print("Computing NEW (R13 enabled) leaf per candidate transaction...", file=sys.stderr)
    df["new_leaf"] = df.apply(lambda r: leaf_for(r, rules_with_r13), axis=1)

    changed = (df["old_leaf"] != df["new_leaf"]).sum()
    print(f"{changed} of {len(df)} candidate transactions changed leaf due to R13 "
          f"({(df['new_leaf']=='rent').sum()} now rent vs {(df['old_leaf']=='rent').sum()} before)",
          file=sys.stderr)

    old_persist = (df[df["old_leaf"] == "rent"].groupby("financial_proposal_id")["month"]
                   .nunique().rename("rent_persistence_old"))
    new_persist = (df[df["new_leaf"] == "rent"].groupby("financial_proposal_id")["month"]
                   .nunique().rename("rent_persistence_new"))

    feat = outcomes.set_index("financial_proposal_id").join([old_persist, new_persist], how="left")
    feat["rent_persistence_old"] = feat["rent_persistence_old"].fillna(0)
    feat["rent_persistence_new"] = feat["rent_persistence_new"].fillna(0)

    lines = ["# Rent feature IV: before vs after the R13 fix\n",
             f"Persistence feature (COUNT DISTINCT months with a rent transaction), computed two ways "
             f"on the same {len(feat)}-proposal outcome cohort: OLD = crosswalk as it stood before "
             f"today's R13 fix, NEW = with R13 (targeted rent-keyword rule) enabled. "
             f"{changed} of {len(df)} candidate transactions changed leaf assignment.\n",
             "| Outcome | Old IV | New IV | Change |", "|---|---|---|---|"]

    for outcome in OUTCOMES:
        sub = feat.dropna(subset=[outcome])
        y = sub[outcome].astype(int).to_numpy()
        ivs = {}
        for col in ("rent_persistence_old", "rent_persistence_new"):
            ivs[col] = _iv(sub[col].to_numpy(), y)
        delta = ivs["rent_persistence_new"] - ivs["rent_persistence_old"]
        lines.append(f"| {outcome} | {ivs['rent_persistence_old']:.4f} | "
                      f"{ivs['rent_persistence_new']:.4f} | {delta:+.4f} |")
        print(f"{outcome}: old IV={ivs['rent_persistence_old']:.4f} "
              f"new IV={ivs['rent_persistence_new']:.4f} (n={len(sub)}, bads={y.sum()})", file=sys.stderr)

    lines.append(f"\nFor reference, mortgage's persistence IV (existing, unaffected by this fix) "
                 f"is documented at 0.0653 -- the original comparison point for the 'rent gap'.\n")

    report = "\n".join(lines)
    REPORT_MD.write_text(report)
    print(report)
    print(f"\nWrote {REPORT_MD}", file=sys.stderr)


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] not in {"fetch", "compute", "run"}:
        sys.exit(__doc__)
    if args[0] in ("fetch", "run"):
        fetch()
    if args[0] in ("compute", "run"):
        compute()

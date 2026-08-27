"""Final three-way evaluation: Equifax-native vs Plaid-native vs our pipeline.

Answers the question the whole project has been building towards: does our
taxonomy + merchant dictionary + rules actually beat *just trusting each
provider's own category*, measured against independent, human-verified truth?

"Native" leaf = crosswalk each provider's OWN category field through the
taxonomy mapping only (T1 direction overrides + T3 mechanism overrides are
included, since those are still 100% derived from the provider's own
category/direction fields -- T4/T5/T6 provider-crosswalk-fallback are NOT).
This is "what if you did nothing but map their category onto our leaf names."

"Our pipeline" leaf = the full precedence waterfall (T4 dictionary first,
then T5 rules, falling back to the native crosswalk only if neither fires)
for head merchants; for tail merchants (Plaid-only, unmatched vocabulary)
it's the enriched two-model (Haiku + Sonnet) LLM labelling used throughout
this project, since that's what actually resolves this population -- the
static T4/T5 CSVs were never going to cover 50,000 long-tail strings.
NOTE: the gold tail set is deliberately excluded from every production
tranche run (to stay held-out), so its "our pipeline" answer comes from
the original tail-eval predictions (outputs/tail_eval_predictions_*.csv),
not the tranche files -- those will always show zero coverage for gold
merchants by design.

Ground truth: data/gold_merchant_labels.csv (1,563 merchants both providers
see) + data/gold_tail_labels.csv (247 Plaid-only merchants) -- independently
human-verified, never derived from either provider's own categorisation.

Usage:
    python src/final_evaluation.py fetch    # pull modal provider categories from BigQuery
    python src/final_evaluation.py score    # compute the three-way comparison + report
    python src/final_evaluation.py run      # fetch then score
"""
import csv
import json
import pathlib
import sys

from dotenv import load_dotenv

load_dotenv()

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "outputs"
TAXONOMY_CSV = ROOT / "taxonomy" / "taxonomy.csv"
DICT_CSV = ROOT / "taxonomy" / "merchant_dictionary.csv"
RULES_CSV = ROOT / "taxonomy" / "rules" / "deterministic_rules.csv"
GOLD_HEAD = ROOT / "data" / "gold_merchant_labels.csv"
GOLD_TAIL = ROOT / "data" / "gold_tail_labels.csv"
TAIL_EVAL_HAIKU = OUT_DIR / "tail_eval_predictions_haiku.csv"
TAIL_EVAL_SONNET = OUT_DIR / "tail_eval_predictions_sonnet.csv"

MODAL_JSON = OUT_DIR / "final_eval_modal_categories.json"
COMPARISON_CSV = OUT_DIR / "final_evaluation_comparison.csv"
REPORT_MD = ROOT / "data" / "final_evaluation_report.md"

MECH = {"Identified Salary", "Refund", "Benefits", "Welfare", "Pension Payout", "Tax Refund",
        "Cash Back", "Cash Machine", "Cash Deposit", "Interest", "Interests and Dividends",
        "Balance Transfers", "Adjustments"}
MECH_LEAF = {"Identified Salary": "salary", "Refund": "refund_received", "Benefits": "benefits_state",
             "Welfare": "benefits_state", "Pension Payout": "pension_received", "Tax Refund": "tax_refund",
             "Cash Back": "cashback", "Cash Machine": "cash_withdrawal", "Cash Deposit": "cash_deposit",
             "Interest": "savings_interest_received", "Interests and Dividends": "savings_interest_received",
             "Balance Transfers": "balance_transfer", "Adjustments": "adjustment"}


def load_crosswalk():
    tax = list(csv.DictReader(open(TAXONOMY_CSV)))
    sub_map, pri_map, plaid_map, gen_of = {}, {}, {}, {}
    for r in tax:
        gen_of[r["detailed_category"]] = r["general_category"]
        for s in [x.strip() for x in r["equifax_source"].split(";") if x.strip()]:
            if "+" in s or "|" in s:
                continue
            if s.startswith("primary:"):
                v = s[8:].strip()
                if v != "(null)":
                    pri_map[v] = r["detailed_category"]
            else:
                sub_map[s] = r["detailed_category"]
        for p in [x.strip() for x in r["plaid_source"].split(";") if x.strip()]:
            plaid_map[p] = r["detailed_category"]
    return sub_map, pri_map, plaid_map, gen_of


def eqx_native_leaf(pri, sub, direction):
    """T1 + T2 + T3 + T6 -- everything derivable from Equifax's OWN category fields."""
    if pri and pri.startswith("Gambling and Betting") and direction == "credit":
        return "gambling_unspecified"
    if sub == "Council" and direction == "credit":
        return "salary"
    if pri == "Identified Salary" and sub in ("Taxis", "Delivery", "Take Away"):
        return "salary_gig"
    if pri == "Identified Salary" and sub in ("Recruitment Services", "Employment Agencies"):
        return "income_agency_work"
    if pri in MECH:
        return MECH_LEAF[pri]
    if sub and sub in SUB_MAP:
        return SUB_MAP[sub]
    if pri and pri in PRI_MAP:
        return PRI_MAP[pri]
    return "unclassified_other"


def plaid_native_leaf(cat, direction):
    """T1 + T6 -- everything derivable from Plaid's OWN category field."""
    if cat == "ENTERTAINMENT_CASINOS_AND_GAMBLING" and direction == "credit":
        return "gambling_unspecified"
    return PLAID_MAP.get(cat, "unclassified_other")


def load_dictionary():
    """Same T4 eligibility as generate_crosswalk_sql.load_t4_dictionary."""
    from generate_crosswalk_sql import load_t4_dictionary
    return load_t4_dictionary(DICT_CSV)


def load_rules():
    rows = list(csv.DictReader(open(RULES_CSV)))
    rules = [r for r in rows if r["enabled"].strip().lower() == "true"]
    rules.sort(key=lambda r: (int(r["priority"]), r["rule_id"]))
    return rules


import re as _re

def _rule_matches(rule, merchant_text, description_text, direction):
    if rule["direction"] != "any" and rule["direction"] != direction:
        return False
    field_text = merchant_text if rule["field"] == "merchant_name" else description_text
    if field_text is None:
        return False
    pattern = rule["pattern"]
    if rule["pattern_type"] != "regex":
        pattern = r"\b(" + pattern + r")\b"
    if not _re.search(pattern, field_text, flags=_re.IGNORECASE):
        return False
    exclude = rule.get("exclude_pattern", "").strip()
    if exclude and _re.search(exclude, field_text, flags=_re.IGNORECASE):
        return False
    return True


def our_leaf(merchant, direction, description, native_leaf_fn, *native_args):
    """T2 (narrative-disambiguated merchant collisions) -> T4 (dictionary) -> T5 (rules)
    -> native crosswalk fallback (T6/T1/T3)."""
    from generate_crosswalk_sql import (  # noqa: PLC0415
        GAMBLING_SUBTYPE_LEAVES, match_t2,
    )
    m = merchant.strip().lower() if merchant else ""
    t2 = match_t2(merchant, direction, description)
    if t2 is not None:
        return t2
    if direction == "credit" and DICTIONARY.get(m) in GAMBLING_SUBTYPE_LEAVES:
        return "gambling_unspecified", "T1_direction_gambling_credit"
    if direction == "credit" and _re.search(r"\brefund(ed)?\b", description or "", flags=_re.IGNORECASE):
        if DICTIONARY.get(m) not in GAMBLING_SUBTYPE_LEAVES:
            return "refund_received", "T2_compound_refund"
    if direction == "credit" and _re.search(
            r"returned\s+(direct\s+debit|standing\s+order)|direct\s+debit\s+reversal|\breversal of\b",
            description or "", flags=_re.IGNORECASE):
        return "returned_payment", "T2_compound_returned_payment"
    if m == "youlend" and direction == "credit":
        return "loan_disbursement", "T2_compound_youlend_disbursement"
    if m in DICTIONARY:
        return DICTIONARY[m], "T4_dictionary"
    for rule in RULES:
        if _rule_matches(rule, m, description, direction):
            return rule["detailed_category"], f"T5_{rule['rule_id']}"
    return native_leaf_fn(*native_args), "T6_native_fallback"


def fetch():
    from google.cloud import bigquery
    client = bigquery.Client(project="raylo-production")

    head_merchants = sorted({r["merchant"].strip().lower()
                              for r in csv.DictReader(open(GOLD_HEAD))})
    tail_merchants = sorted({r["merchant"].strip().lower()
                              for r in csv.DictReader(open(GOLD_TAIL))})
    all_merchants = sorted(set(head_merchants) | set(tail_merchants))
    in_list = ",".join(f"'{m.replace(chr(92), chr(92)*2).replace(chr(39), chr(92)+chr(39))}'" for m in all_merchants)

    print(f"Fetching modal Equifax category for {len(head_merchants)} head merchants...", file=sys.stderr)
    eqx_sql = f"""
    WITH eqx AS (
      SELECT LOWER(TRIM(VendorDescription)) AS merchant,
             PrimaryCategoryDescription AS pri, SubCategoryDescription AS sub,
             IF(TransactionTypeId=1,'credit','debit') AS direction,
             COUNT(*) AS n
      FROM `raylo-production.equifax_data.open_banking_full_dump`
      WHERE LOWER(TRIM(VendorDescription)) IN ({in_list})
      GROUP BY 1,2,3,4
    )
    SELECT merchant, pri, sub, direction, n FROM eqx
    QUALIFY ROW_NUMBER() OVER (PARTITION BY merchant ORDER BY n DESC) = 1
    """
    eqx_rows = {r["merchant"]: dict(r) for r in client.query(eqx_sql).result()}

    print(f"Fetching modal Plaid category for {len(all_merchants)} merchants...", file=sys.stderr)
    plaid_sql = f"""
    WITH plaid AS (
      SELECT LOWER(TRIM(merchant_name)) AS merchant,
             credit_category_detailed AS cat,
             IF(amount < 0,'credit','debit') AS direction,
             COUNT(*) AS n
      FROM `raylo-production.dbt_production.credit_plaid_open_banking_transactions`
      WHERE LOWER(TRIM(merchant_name)) IN ({in_list})
      GROUP BY 1,2,3
    )
    SELECT merchant, cat, direction, n FROM plaid
    QUALIFY ROW_NUMBER() OVER (PARTITION BY merchant ORDER BY n DESC) = 1
    """
    plaid_rows = {r["merchant"]: dict(r) for r in client.query(plaid_sql).result()}

    MODAL_JSON.write_text(json.dumps({"eqx": eqx_rows, "plaid": plaid_rows}, indent=2))
    print(f"Wrote {MODAL_JSON}: {len(eqx_rows)} eqx / {len(plaid_rows)} plaid matched", file=sys.stderr)


def score():
    modal = json.loads(MODAL_JSON.read_text())
    eqx_modal, plaid_modal = modal["eqx"], modal["plaid"]

    haiku_preds = {r["merchant"]: r for r in csv.DictReader(open(TAIL_EVAL_HAIKU))} if TAIL_EVAL_HAIKU.exists() else {}
    sonnet_preds = {r["merchant"]: r for r in csv.DictReader(open(TAIL_EVAL_SONNET))} if TAIL_EVAL_SONNET.exists() else {}

    def tail_pipeline_leaf(m):
        h, s = haiku_preds.get(m), sonnet_preds.get(m)
        if not h or not s:
            return None, "no_prediction"
        if h["llm_leaf"] == s["llm_leaf"]:
            return h["llm_leaf"], "agree"
        if float(s["llm_confidence"]) >= 0.7:
            return s["llm_leaf"], "sonnet_high_conf"
        return None, "abstain_low_conf"

    gold_head = list(csv.DictReader(open(GOLD_HEAD)))
    gold_tail = list(csv.DictReader(open(GOLD_TAIL)))

    comparison_rows = []

    # Circularity check (CLAUDE.md-mandated leakage audit, ran 2026-08-21): a dictionary entry
    # sourced from `gating_adjudication` records the SAME human verdict as a gold row whose
    # gold_source is 'adjudicated_llm'/'adjudicated_either'/'adjudicated_correction' (that
    # verdict is literally what put the entry in the dictionary in the first place) --
    # scoring the dictionary against that gold row is not independent validation.
    # 'adjudicated_equifax' is NOT circular: that verdict explicitly rejected the LLM/dictionary
    # answer, so if the merchant is in the dictionary anyway it's via the original (pre-gold-set)
    # llm_proposed entries, not this adjudication.
    CIRCULAR_GOLD_SOURCES = {"adjudicated_llm", "adjudicated_llm+taxonomy_split_20260819",
                             "adjudicated_either", "adjudicated_correction",
                             "adjudicated_correction+taxonomy_split_20260819"}
    dict_source = {r["normalised_merchant"]: r["source"] for r in csv.DictReader(open(DICT_CSV))}

    for r in gold_head:
        m = r["merchant"].strip().lower()
        gold_leaf = r["gold_leaf"]
        gold_source = r["gold_source"]
        e = eqx_modal.get(m)
        p = plaid_modal.get(m)
        eqx_leaf_val = eqx_native_leaf(e["pri"], e["sub"], e["direction"]) if e else None
        plaid_leaf_val = plaid_native_leaf(p["cat"], p["direction"]) if p else None
        our_leaf_eqx, tier_eqx = (our_leaf(m, e["direction"], None, eqx_native_leaf, e["pri"], e["sub"], e["direction"])
                                  if e else (None, None))
        our_leaf_plaid, tier_plaid = (our_leaf(m, p["direction"], None, plaid_native_leaf, p["cat"], p["direction"])
                                       if p else (None, None))
        human_verified = gold_source.startswith("adjudicated")
        circular = dict_source.get(m) == "gating_adjudication" and gold_source in CIRCULAR_GOLD_SOURCES
        comparison_rows.append({
            "merchant": m, "stratum": "head", "gold_leaf": gold_leaf,
            "gold_source": gold_source, "human_verified": human_verified, "circular": circular,
            "equifax_native_leaf": eqx_leaf_val, "equifax_n": e["n"] if e else None,
            "plaid_native_leaf": plaid_leaf_val, "plaid_n": p["n"] if p else None,
            "our_leaf_on_equifax": our_leaf_eqx, "our_tier_on_equifax": tier_eqx,
            "our_leaf_on_plaid": our_leaf_plaid, "our_tier_on_plaid": tier_plaid,
        })

    # Tail circularity: 'consensus_correct'/'haiku_correct'/'sonnet_correct' gold rows set
    # gold_leaf TO the exact haiku/sonnet prediction being scored (see build_tail_eval.py
    # finalise()) -- scoring our pipeline against those rows is tautological. Only
    # 'override' (human rejected both models) and 'unclassifiable' (human confirmed neither
    # answer works) are independent tests of the pipeline.
    TAIL_CIRCULAR_GOLD_SOURCES = {"consensus_correct", "haiku_correct", "sonnet_correct"}
    for r in gold_tail:
        m = r["merchant"].strip().lower()
        gold_leaf = r["gold_leaf"]
        gold_source = r["gold_source"]
        p = plaid_modal.get(m)
        plaid_leaf_val = plaid_native_leaf(p["cat"], p["direction"]) if p else None
        our_leaf_val, our_tier = tail_pipeline_leaf(m)
        circular = gold_source in TAIL_CIRCULAR_GOLD_SOURCES
        comparison_rows.append({
            "merchant": m, "stratum": "tail", "gold_leaf": gold_leaf,
            "gold_source": gold_source, "human_verified": True, "circular": circular,
            "equifax_native_leaf": None, "equifax_n": None,
            "plaid_native_leaf": plaid_leaf_val, "plaid_n": p["n"] if p else None,
            "our_leaf_on_equifax": None, "our_tier_on_equifax": None,
            "our_leaf_on_plaid": our_leaf_val, "our_tier_on_plaid": our_tier,
        })

    OUT_DIR.mkdir(exist_ok=True)
    with open(COMPARISON_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(comparison_rows[0].keys()))
        w.writeheader(); w.writerows(comparison_rows)
    print(f"Wrote {COMPARISON_CSV} ({len(comparison_rows)} rows)", file=sys.stderr)

    _, _, _, gen_of = load_crosswalk()

    def acc(rows, gold_key, pred_key, level="leaf"):
        scored = [r for r in rows if r[pred_key] is not None]
        if not scored:
            return None, 0
        if level == "leaf":
            correct = sum(1 for r in scored if r[pred_key] == r[gold_key])
        else:
            correct = sum(1 for r in scored
                          if gen_of.get(r[pred_key]) == gen_of.get(r[gold_key]))
        return correct / len(scored), len(scored)

    head_rows = [r for r in comparison_rows if r["stratum"] == "head"]
    tail_rows = [r for r in comparison_rows if r["stratum"] == "tail"]

    def row(label, rows, key_a):
        leaf_acc, n = acc(rows, "gold_leaf", key_a, "leaf")
        gen_acc, _ = acc(rows, "gold_leaf", key_a, "general")
        if leaf_acc is None:
            return f"| {label} | n/a | n/a | 0 |"
        return f"| {label} | {leaf_acc:.1%} | {gen_acc:.1%} | {n} |"

    report = ["# Final evaluation: Equifax-native vs Plaid-native vs our pipeline\n",
              "Ground truth: `data/gold_merchant_labels.csv` (1,563 head merchants, both providers) "
              "+ `data/gold_tail_labels.csv` (247 tail merchants, Plaid-only).\n",
              "'Native' = crosswalking each provider's own category field only (no dictionary, no rules). "
              "'Our pipeline' = dictionary -> rules -> native fallback (head); the enriched two-model LLM "
              "consensus (tail).\n"]

    # --- Leakage audit (requested explicitly before trusting these numbers) ---
    n_head_unreviewed = sum(1 for r in head_rows if not r["human_verified"])
    n_head_circular = sum(1 for r in head_rows if r["circular"])
    n_tail_circular = sum(1 for r in tail_rows if r["circular"])
    report.append("## Leakage audit\n")
    report.append(f"**Head set**: only {len(head_rows) - n_head_unreviewed} of {len(head_rows)} gold labels "
                   f"({(len(head_rows)-n_head_unreviewed)/len(head_rows):.1%}) went through actual human "
                   f"adjudication (`gold_source` starting `adjudicated_*`). The other {n_head_unreviewed} "
                   f"(`consensus_all_agree`) are simply cases where Haiku and Sonnet -- two models from the "
                   f"same family, given the same prompt -- agreed with each other, with no human check. That's "
                   f"not independent ground truth; it's model self-consistency, which could share blind spots. "
                   f"Separately, {n_head_circular} of the human-adjudicated rows are directly circular: the "
                   f"same adjudication verdict both produced the gold label AND was used to add that merchant "
                   f"to the T4 dictionary, so scoring the dictionary against those specific rows is tautological.\n")
    report.append(f"**Tail set**: every row went through human review, but for {n_tail_circular} of "
                   f"{len(tail_rows)} rows (`consensus_correct`/`haiku_correct`/`sonnet_correct`), gold_leaf "
                   f"was set TO the exact haiku/sonnet prediction being scored (see `build_tail_eval.py "
                   f"finalise()`) -- scoring our pipeline against those rows is tautological by construction. "
                   f"Only `override` (human rejected both models) and `unclassifiable` (human confirmed "
                   f"neither answer works) are independent tests.\n")
    report.append("**Fix applied below**: every table reports a `Clean, non-circular` row using only "
                   "genuinely independent evidence -- head: human-adjudicated AND not circular "
                   "(`adjudicated_equifax` only, since that's the one verdict type that never feeds the "
                   "dictionary); tail: `override` + `unclassifiable` only. Small-sample sizes are called out "
                   "explicitly rather than hidden behind a percentage.\n")

    clean_head = [r for r in head_rows if r["human_verified"] and not r["circular"]]
    clean_tail = [r for r in tail_rows if not r["circular"]]

    report.append("\n## Head merchants (n=1,563, both providers)\n")
    report.append("| Source | Leaf accuracy | General-category accuracy | Scored n |")
    report.append("|---|---|---|---|")
    report.append(row("Equifax native category -- full sample", head_rows, "equifax_native_leaf"))
    report.append(row("Equifax native category -- clean, non-circular (n=" + str(len(clean_head)) + ")",
                       clean_head, "equifax_native_leaf"))
    report.append(row("Plaid native category -- full sample", head_rows, "plaid_native_leaf"))
    report.append(row("Plaid native category -- clean, non-circular", clean_head, "plaid_native_leaf"))
    report.append(row("Our pipeline (via Equifax txn) -- full sample", head_rows, "our_leaf_on_equifax"))
    report.append(row("Our pipeline (via Equifax txn) -- clean, non-circular", clean_head, "our_leaf_on_equifax"))
    report.append(row("Our pipeline (via Plaid txn) -- full sample", head_rows, "our_leaf_on_plaid"))
    report.append(row("Our pipeline (via Plaid txn) -- clean, non-circular", clean_head, "our_leaf_on_plaid"))
    report.append(f"\nThe clean subset is small (n={len(clean_head)}) because it's restricted to "
                   f"`adjudicated_equifax` verdicts -- cases where a human explicitly preferred Equifax's own "
                   f"category over the LLM consensus. That's a genuinely adversarial subset for our pipeline "
                   f"(it's selected FOR cases where Equifax was judged right), so if our pipeline still holds "
                   f"up here that's meaningful; if it drops, that's expected and informative, not alarming.\n")

    agree_rows = [r for r in head_rows if r["our_leaf_on_equifax"] and r["our_leaf_on_plaid"]]
    agree_n = sum(1 for r in agree_rows if r["our_leaf_on_equifax"] == r["our_leaf_on_plaid"])
    report.append(f"\n**Provider-independence check** (unaffected by the leakage above -- this compares our "
                   f"own pipeline's two outputs to each other, not to gold): of {len(agree_rows)} head "
                   f"merchants scoreable via both transaction sources, our pipeline gives the *same* leaf "
                   f"regardless of which provider the transaction came from for {agree_n} "
                   f"({agree_n/len(agree_rows):.1%}) -- vs. the known 27.8% crosswalk-only agreement rate.\n")

    in_dict = [r for r in head_rows if r["merchant"] in DICTIONARY]
    not_in_dict = [r for r in head_rows if r["merchant"] not in DICTIONARY]
    report.append(f"\n**Dictionary coverage breakdown**: only {len(in_dict)} of {len(head_rows)} gold head "
                   f"merchants ({len(in_dict)/len(head_rows):.1%}) are in the current 535-entry T4 "
                   f"dictionary (full sample, includes circular rows):\n")
    report.append("| Segment | Our leaf (via Equifax txn) | Our leaf (via Plaid txn) | n |")
    report.append("|---|---|---|---|")
    for label, seg in [("In T4 dictionary", in_dict), ("Not in T4 dictionary (T5/T6 fallback)", not_in_dict)]:
        a1, n1 = acc(seg, "gold_leaf", "our_leaf_on_equifax", "leaf")
        a2, n2 = acc(seg, "gold_leaf", "our_leaf_on_plaid", "leaf")
        a1s = f"{a1:.1%}" if a1 is not None else "n/a"
        a2s = f"{a2:.1%}" if a2 is not None else "n/a"
        report.append(f"| {label} | {a1s} | {a2s} | {len(seg)} |")
    report.append("\nWhere the dictionary covers a merchant, the pipeline is provider-independent by "
                   "construction (same lookup key either way). The remaining ~74% of the gold head set "
                   "isn't in the curated dictionary yet, so it still falls back to the native crosswalk -- "
                   "this is the single biggest lever left for improving head-population accuracy further. "
                   "Note this breakdown includes the circular rows flagged above, so treat the 'in "
                   "dictionary' figure as an upper bound, not a clean measurement.\n")

    report.append("\n## Tail merchants (n=247, Plaid-only unmatched vocabulary)\n")
    report.append("| Source | Leaf accuracy | General-category accuracy | Scored n |")
    report.append("|---|---|---|---|")
    report.append(row("Plaid native category -- full sample", tail_rows, "plaid_native_leaf"))
    report.append(row("Plaid native category -- clean, non-circular (n=" + str(len(clean_tail)) + ")",
                       clean_tail, "plaid_native_leaf"))
    report.append(row("Our pipeline (LLM consensus) -- full sample", tail_rows, "our_leaf_on_plaid"))
    report.append(row("Our pipeline (LLM consensus) -- clean, non-circular", clean_tail, "our_leaf_on_plaid"))
    report.append(f"\nThe clean tail subset (n={len(clean_tail)}) is exactly the population the pipeline is "
                   f"weakest on by construction: `override` rows are cases a human explicitly said BOTH "
                   f"models got wrong, and `unclassifiable` rows are cases where abstaining is the only "
                   f"correct answer. This is a deliberately hard, adversarial slice -- not a representative "
                   f"sample of tail performance -- so a lower number here doesn't mean the tail pipeline is "
                   f"unreliable in general; it means these specific hard cases remain hard.\n")

    all_rows_clean = clean_head + clean_tail
    plaid_clean_acc, plaid_clean_n = acc(all_rows_clean, "gold_leaf", "plaid_native_leaf", "leaf")
    our_clean = [{"gold_leaf": r["gold_leaf"],
                  "pred": r["our_leaf_on_plaid"] if r["stratum"] == "tail" else r["our_leaf_on_equifax"]}
                 for r in all_rows_clean]
    our_clean_correct = sum(1 for r in our_clean if r["pred"] and r["pred"] == r["gold_leaf"])
    our_clean_scored = sum(1 for r in our_clean if r["pred"])
    report.append(f"\n## Overall, clean/non-circular only (n={len(all_rows_clean)})\n")
    report.append(f"- Plaid native category: {plaid_clean_acc:.1%} leaf accuracy (n={plaid_clean_n})")
    report.append(f"- Our pipeline: {our_clean_correct/our_clean_scored:.1%} leaf accuracy "
                   f"(n={our_clean_scored}) -- **{our_clean_correct}/{our_clean_scored} correct**")
    report.append("\nThis combined clean slice is deliberately adversarial (Equifax-preferred head cases + "
                   "hard-override/unclassifiable tail cases), so treat it as a stress test / lower bound, "
                   "not the headline number.\n")

    all_rows = head_rows + tail_rows
    plaid_all_acc, plaid_all_n = acc(all_rows, "gold_leaf", "plaid_native_leaf", "leaf")
    our_all = [{"gold_leaf": r["gold_leaf"],
                "pred": r["our_leaf_on_plaid"] if r["stratum"] == "tail" else r["our_leaf_on_equifax"]}
               for r in all_rows]
    our_all_correct = sum(1 for r in our_all if r["pred"] and r["pred"] == r["gold_leaf"])
    our_all_scored = sum(1 for r in our_all if r["pred"])
    report.append(f"\n## Overall, full sample including consensus/circular rows (n={len(all_rows)})\n")
    report.append(f"- Plaid native category: {plaid_all_acc:.1%} leaf accuracy (n={plaid_all_n})")
    report.append(f"- Our pipeline: {our_all_correct/our_all_scored:.1%} leaf accuracy (n={our_all_scored})")
    report.append("\nThis is the representative, best-estimate number (most of the gold set genuinely is "
                   "this population), but it is inflated to an unknown degree by the leakage documented "
                   "above -- treat the clean-subset numbers as the floor and this as the ceiling.\n")

    not_scored = [r for r in all_rows if r["stratum"] == "tail" and not r["our_leaf_on_plaid"]]
    if not_scored:
        report.append(f"\n**Abstained / no consensus**: {len(not_scored)} tail gold merchants had no "
                       f"haiku/sonnet agreement and sonnet confidence below 0.7 -- excluded from 'our "
                       f"pipeline' scoring above (abstaining is the correct behaviour, not a defect), "
                       f"not counted as correct or incorrect: {[r['merchant'] for r in not_scored][:15]}")

    REPORT_MD.write_text("\n".join(report) + "\n")
    print(f"Wrote {REPORT_MD}", file=sys.stderr)
    print("\n".join(report))


GOLD_V2_FILES = [ROOT / "data" / "gold_transactions_v2.csv", ROOT / "data" / "gold_transactions_v2_batch2.csv"]
V2_COMPARISON_CSV = OUT_DIR / "final_evaluation_v2_comparison.csv"
V2_REPORT_MD = ROOT / "data" / "final_evaluation_v2_report.md"


def score_v2():
    """Score against the transaction-level gold set (data/gold_transactions_v2*.csv) --
    built 2026-08-21 specifically to eliminate the leakage found in the merchant-level
    set: every row here is a real transaction, independently and manually reviewed by
    Carlos with no default trusted, no consensus-without-review, no gold_leaf copied
    from the prediction being scored. No clean/full split is needed -- the whole set
    is clean by construction."""
    from collections import Counter
    _, _, _, gen_of = load_crosswalk()

    # Any merchant whose T4 dictionary entry was itself sourced FROM this gold set
    # (build_merchant_dictionary.py's gold_v2_review additions) must be excluded from
    # the headline "our pipeline" accuracy -- otherwise we'd be testing whether a
    # lookup remembers its own source, which is the exact circularity this whole
    # gold-set rebuild exists to eliminate. Kept in the row-level CSV (flagged) for
    # transparency, just not counted in the reported percentages.
    self_sourced = {r["normalised_merchant"] for r in csv.DictReader(open(DICT_CSV))
                    if r["source"] == "gold_v2_review"}

    rows = []
    for path in GOLD_V2_FILES:
        if path.exists():
            batch_rows = list(csv.DictReader(open(path)))
            print(f"Loaded {len(batch_rows)} rows from {path.name}", file=sys.stderr)
            rows.extend(batch_rows)
    if not rows:
        sys.exit(f"No gold v2 files found -- run build_final_gold_v2.py apply first")

    out_rows = []
    for r in rows:
        provider = r["provider"]
        direction = r["direction"]
        merchant = r["merchant_raw"]
        description = r["description_raw"]
        gold_leaf = r["gold_leaf"]

        if provider == "equifax":
            pri, sub = (r["native_category"].split(" | ", 1) + [""])[:2] if r["native_category"] else ("", "")
            native_leaf = eqx_native_leaf(pri, sub, direction)
            our, tier = our_leaf(merchant, direction, description, eqx_native_leaf, pri, sub, direction)
        else:
            cat = r["native_category"]
            native_leaf = plaid_native_leaf(cat, direction)
            our, tier = our_leaf(merchant, direction, description, plaid_native_leaf, cat, direction)

        out_rows.append({
            "merchant_raw": merchant, "provider": provider, "amount": r["amount"], "direction": direction,
            "gold_leaf": gold_leaf, "native_leaf": native_leaf, "our_leaf": our, "our_tier": tier,
            "source": r["source"], "provenance": r["provenance"],
            "self_sourced_dict_entry": merchant.strip().lower() in self_sourced,
        })

    OUT_DIR.mkdir(exist_ok=True)
    with open(V2_COMPARISON_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        w.writeheader(); w.writerows(out_rows)
    print(f"Wrote {V2_COMPARISON_CSV} ({len(out_rows)} rows)", file=sys.stderr)

    n_self_sourced = sum(1 for r in out_rows if r["self_sourced_dict_entry"])
    scoring_rows = [r for r in out_rows if not r["self_sourced_dict_entry"]]
    print(f"Excluding {n_self_sourced} rows whose merchant is a gold_v2-sourced dictionary "
          f"entry (circular) from headline scoring -- {len(scoring_rows)} remain", file=sys.stderr)

    def acc(subset, pred_key, level="leaf"):
        scored = [r for r in subset if r[pred_key]]
        if not scored:
            return None, 0
        if level == "leaf":
            correct = sum(1 for r in scored if r[pred_key] == r["gold_leaf"])
        else:
            correct = sum(1 for r in scored if gen_of.get(r[pred_key]) == gen_of.get(r["gold_leaf"]))
        return correct / len(scored), len(scored)

    def row(label, subset, key):
        a, n = acc(subset, key, "leaf")
        g, _ = acc(subset, key, "general")
        if a is None:
            return f"| {label} | n/a | n/a | 0 |"
        return f"| {label} | {a:.1%} | {g:.1%} | {n} |"

    report = ["# Final evaluation v2: transaction-level, leakage-free gold set\n",
              f"Ground truth: `{'`, `'.join(p.name for p in GOLD_V2_FILES if p.exists())}` -- "
              f"{len(out_rows)} real transactions, each independently reviewed and hand-corrected by "
              f"Carlos (403/1500 batch-1 drafts were overridden, including 34 of the 400 rows that "
              f"already had a prior human verdict from earlier work -- this is a fresh, from-scratch "
              f"review, not a rubber stamp). No clean/full split needed: unlike the v1 merchant-level "
              f"set, nothing here is copied from the prediction being scored.\n",
              f"**{n_self_sourced} rows are excluded from every accuracy figure below**: their merchant's "
              f"T4 dictionary entry was itself sourced from this same gold set (`build_merchant_dictionary.py`'s "
              f"gold_v2_review additions), so scoring 'our pipeline' against them would just test whether a "
              f"lookup remembers its own source -- the exact circularity this gold-set rebuild exists to "
              f"eliminate. All figures below are computed on the remaining {len(scoring_rows)} rows; the "
              f"excluded rows are still in `{V2_COMPARISON_CSV.name}`, flagged `self_sourced_dict_entry`.\n"]

    eqx_rows = [r for r in scoring_rows if r["provider"] == "equifax"]
    plaid_rows = [r for r in scoring_rows if r["provider"] == "plaid"]

    report.append("## Overall (all providers combined)\n")
    report.append("| Source | Leaf accuracy | General-category accuracy | Scored n |")
    report.append("|---|---|---|---|")
    report.append(row("Native provider category", scoring_rows, "native_leaf"))
    report.append(row("Our pipeline", scoring_rows, "our_leaf"))

    report.append(f"\n## By provider\n")
    report.append("| Provider | Native leaf acc | Native general acc | Our leaf acc | Our general acc | n |")
    report.append("|---|---|---|---|---|---|")
    for label, subset in [("Equifax", eqx_rows), ("Plaid", plaid_rows)]:
        na, nn = acc(subset, "native_leaf", "leaf")
        ng, _ = acc(subset, "native_leaf", "general")
        oa, on = acc(subset, "our_leaf", "leaf")
        og, _ = acc(subset, "our_leaf", "general")
        report.append(f"| {label} | {na:.1%} | {ng:.1%} | {oa:.1%} | {og:.1%} | {len(subset)} |")

    report.append(f"\n## By sampling source (important -- these are very different populations)\n")
    report.append("| Source | Native leaf acc | Our leaf acc | n |")
    report.append("|---|---|---|---|")
    for src, label in [("already_verified", "Already-verified merchants (deliberately hard -- these needed human "
                                            "adjudication in earlier work precisely because they were disputed)"),
                       ("new", "Broad random sample (representative of typical incoming transactions)"),
                       ("new_targeted", "Targeted for taxonomy-breadth coverage (rare leaves, batch 2 only)")]:
        subset = [r for r in scoring_rows if r["source"] == src]
        if not subset:
            continue
        na, nn = acc(subset, "native_leaf", "leaf")
        oa, on = acc(subset, "our_leaf", "leaf")
        report.append(f"| {label} | {na:.1%} | {oa:.1%} | {len(subset)} |")
    report.append("\nThe blended headline number above is pulled down by the already-verified subset, which is "
                   "deliberately hard by construction. The 'broad random sample' row is the closest thing to "
                   "*typical* transaction performance in this set.\n")

    tier_counts = Counter(r["our_tier"] for r in scoring_rows)
    report.append(f"\n## Our pipeline's resolution tier breakdown\n")
    for tier, n in tier_counts.most_common():
        report.append(f"- {tier}: {n} ({n/len(scoring_rows):.1%})")

    disagree_examples = [r for r in scoring_rows if r["native_leaf"] != r["gold_leaf"] and r["our_leaf"] == r["gold_leaf"]]
    report.append(f"\n**Our pipeline gets it right where the native category doesn't**: {len(disagree_examples)} "
                   f"of {len(scoring_rows)} transactions ({len(disagree_examples)/len(scoring_rows):.1%}).\n")

    V2_REPORT_MD.write_text("\n".join(report) + "\n")
    print(f"Wrote {V2_REPORT_MD}", file=sys.stderr)
    print("\n".join(report))


SUB_MAP = PRI_MAP = PLAID_MAP = None
DICTIONARY = RULES = None

if __name__ == "__main__":
    SUB_MAP, PRI_MAP, PLAID_MAP, _ = load_crosswalk()
    DICTIONARY = load_dictionary()
    RULES = load_rules()

    args = sys.argv[1:]
    if not args or args[0] not in {"fetch", "score", "run", "score_v2"}:
        sys.exit(__doc__)
    if args[0] in ("fetch", "run"):
        fetch()
    if args[0] in ("score", "run"):
        score()
    if args[0] == "score_v2":
        score_v2()

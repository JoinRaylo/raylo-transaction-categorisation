"""Before/after comparison: the OLD production_labelling.py system prompt
(taxonomy + buggy TAIL_ADDENDUM + raw 375-note verbatim dump, ~86KB) vs. the
NEW synthesized prompt (taxonomy + trimmed TAIL_ADDENDUM + 7 generalized
reasoning principles, ~29KB) -- same model, same 1,055-row gold set, same
batching/enforcement, only the addendum differs.

Usage: python compare_prompt_versions.py {haiku,sonnet,opus} {old,new}
"""
import csv
import pathlib
import sys
import time

from dotenv import load_dotenv

load_dotenv()

ROOT = pathlib.Path("/Users/carlosnoblejesus/Repos/raylo-transaction-categorisation")
sys.path.insert(0, str(ROOT / "src"))
from gating_experiment import load_crosswalk, load_example_merchants, load_example_notes, build_system_prompt, build_notes_addendum  # noqa: E402
from build_tail_eval import SYNTHESIZED_LEARNINGS_ADDENDUM  # noqa: E402

GOLD_CSV = ROOT / "data/gold_v2_slm_eval_holdout.csv"
MODEL_IDS = {"haiku": "claude-haiku-4-5", "sonnet": "claude-sonnet-5", "opus": "claude-opus-5"}
BATCH = 25
MAX_RETRIES = 3

backend = sys.argv[1] if len(sys.argv) > 1 else sys.exit("usage: compare_prompt_versions.py {haiku,sonnet,opus} {old,new,mid,full,fixed}")
variant = sys.argv[2] if len(sys.argv) > 2 else sys.exit("usage: compare_prompt_versions.py {haiku,sonnet,opus} {old,new,mid,full,fixed}")
if backend not in MODEL_IDS or variant not in ("old", "new", "mid", "full", "fixed"):
    sys.exit("bad args")
LOG = f"[{backend}][{variant}]"
OUT_CSV = ROOT / f"outputs/mlx_full_run/compare_{backend}_{variant}_predictions.csv"

_, _, leaves, gen_of, notes_of = load_crosswalk()
leaf_to_general = dict(gen_of)
leaf_list = sorted(leaves) + ["unclassified_other"]
base_taxonomy = build_system_prompt(leaves, gen_of, notes_of, load_example_merchants())

# Reconstructed verbatim -- this is the EXACT text as it stood before today's
# fixes (the transfer_p2p/loan-keyword bug included), for a genuine before/after.
OLD_TAIL_ADDENDUM = (
    "\n## Additional context for this task\n"
    "Each merchant below comes with evidence aggregated from its real transactions: "
    "Plaid's native category guesses, the share of transactions that are money IN "
    "(pct_credit; 0.0 = all spending), the median amount, and the most frequent raw "
    "bank narratives. Use all of it. Direction matters: a 'merchant' whose "
    "transactions are mostly credits is usually a transfer counterparty or income "
    "source, not spending. For lenders, debt collectors and credit providers, "
    "classify by the FINANCIAL PRODUCT being paid (loan repayment, catalogue credit, "
    "debt collection), never by the merchant's trade description (a debt-litigation "
    "solicitor is debt_collection, not legal_services). Personal names and bare "
    "transfer references are transfer_p2p when the evidence supports a person-to-person "
    "payment; use unclassified_other only when the evidence is genuinely uninformative."
)

from build_tail_eval import TAIL_ADDENDUM, CURATED_EXAMPLES_ADDENDUM  # noqa: E402

# The CURRENT TAIL_ADDENDUM was trimmed down to a one-liner once the loan-
# keyword bugfix moved into SYNTHESIZED_LEARNINGS_ADDENDUM's principle #2 --
# so it no longer carries the fix on its own. Reconstructing the minimal
# "OLD content, just that one sentence corrected" version to isolate the
# bugfix's effect without the other 6 principles.
FIXED_TAIL_ADDENDUM_ONLY = (
    "\n## Additional context for this task\n"
    "Each merchant below comes with evidence aggregated from its real transactions: "
    "Plaid's native category guesses, the share of transactions that are money IN "
    "(pct_credit; 0.0 = all spending), the median amount, and the most frequent raw "
    "bank narratives. Use all of it. Direction matters: a 'merchant' whose "
    "transactions are mostly credits is usually a transfer counterparty or income "
    "source, not spending. For lenders, debt collectors and credit providers, "
    "classify by the FINANCIAL PRODUCT being paid (loan repayment, catalogue credit, "
    "debt collection), never by the merchant's trade description (a debt-litigation "
    "solicitor is debt_collection, not legal_services). Personal names and bare "
    "transfer references are transfer_p2p ONLY when nothing else in the narrative "
    "identifies a purpose -- if the raw narrative contains an explicit debt keyword "
    "(LOAN, LEND, OWE, DEBT, IOU) even alongside a personal name, classify as "
    "loan_repayment_manual instead, never transfer_p2p or personal_loan_repayment. "
    "Use unclassified_other only when the evidence is genuinely uninformative."
)

if variant == "old":
    SYSTEM_PROMPT = base_taxonomy + OLD_TAIL_ADDENDUM + build_notes_addendum(load_example_notes())
elif variant == "mid":
    SYSTEM_PROMPT = base_taxonomy + TAIL_ADDENDUM + SYNTHESIZED_LEARNINGS_ADDENDUM + CURATED_EXAMPLES_ADDENDUM
elif variant == "full":
    # principles (incl. the loan-keyword bugfix) PLUS the complete 375-note
    # corpus -- tests whether the principles add anything on top of full breadth
    SYSTEM_PROMPT = base_taxonomy + TAIL_ADDENDUM + SYNTHESIZED_LEARNINGS_ADDENDUM + build_notes_addendum(load_example_notes())
elif variant == "fixed":
    # ONLY the loan-keyword bugfix (no broader 7-principle text) PLUS the
    # complete 375-note corpus -- isolates whether the bugfix alone, without
    # the principles text that measured net-negative in "full", beats plain
    # OLD (which has the same bug the fix addresses).
    SYSTEM_PROMPT = base_taxonomy + FIXED_TAIL_ADDENDUM_ONLY + build_notes_addendum(load_example_notes())
else:
    SYSTEM_PROMPT = base_taxonomy + TAIL_ADDENDUM + SYNTHESIZED_LEARNINGS_ADDENDUM

print(f"{LOG} system prompt: {len(SYSTEM_PROMPT)} chars", file=sys.stderr)

rows = list(csv.DictReader(open(GOLD_CSV)))


def txn_text(i, r):
    merchant = r["merchant_raw"].strip().lower()
    return (f"{i}. merchant: {merchant} | description: {r['description_raw']} | "
            f"amount: {r['amount']} | direction: {r['direction'].strip().lower()}")


def score_batch(client, batch, tag):
    tool = {
        "name": "submit_classifications",
        "description": "Submit categories for a batch of transactions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "results": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "index": {"type": "integer"},
                            "detailed_category": {"type": "string", "enum": leaf_list},
                        },
                        "required": ["index", "detailed_category"],
                    },
                }
            },
            "required": ["results"],
        },
    }
    user_msg = "Classify each transaction:\n" + "\n".join(txn_text(i + 1, r) for i, r in enumerate(batch))
    resp = client.messages.create(
        model=MODEL_IDS[backend], max_tokens=4000, system=SYSTEM_PROMPT,
        tools=[tool], tool_choice={"type": "tool", "name": "submit_classifications"},
        messages=[{"role": "user", "content": user_msg}],
    )
    tool_use = next((b for b in resp.content if b.type == "tool_use"), None)
    if tool_use is None:
        print(f"{LOG} [{tag}] no tool_use, stop_reason={resp.stop_reason}", file=sys.stderr)
        return {}
    return {r["index"]: r["detailed_category"] for r in tool_use.input.get("results", [])
            if isinstance(r.get("index"), int)}


import anthropic
client = anthropic.Anthropic()

predictions = {}
start = time.monotonic()
n_batches = (len(rows) + BATCH - 1) // BATCH
for b in range(n_batches):
    batch = rows[b * BATCH:(b + 1) * BATCH]
    to_do = list(range(len(batch)))
    got = {}
    for attempt in range(MAX_RETRIES):
        sub_batch = [batch[i] for i in to_do]
        try:
            result = score_batch(client, sub_batch, f"batch{b}try{attempt}")
        except Exception as e:
            print(f"{LOG} batch {b} attempt {attempt} exception: {e}", file=sys.stderr)
            time.sleep(2 * (attempt + 1))
            continue
        for local_idx, leaf in result.items():
            orig_idx = to_do[local_idx - 1] if 1 <= local_idx <= len(to_do) else None
            if orig_idx is not None:
                got[orig_idx] = leaf
        to_do = [i for i in to_do if i not in got]
        if not to_do:
            break
    for i in to_do:
        got[i] = "unclassified_other"
    for local_i, leaf in got.items():
        predictions[b * BATCH + local_i] = leaf
    done = min((b + 1) * BATCH, len(rows))
    if done % 100 < BATCH or b == n_batches - 1:
        elapsed = time.monotonic() - start
        print(f"{LOG} {done}/{len(rows)} done in {elapsed:.0f}s ({done/elapsed:.2f} rows/sec)", file=sys.stderr)

total_elapsed = time.monotonic() - start
results = []
for i, r in enumerate(rows):
    pred = predictions.get(i, "unclassified_other")
    gold_leaf = r["gold_leaf"].strip()
    leaf_correct = pred == gold_leaf
    pred_general = leaf_to_general.get(pred)
    gold_general = leaf_to_general.get(gold_leaf)
    general_correct = pred_general is not None and pred_general == gold_general
    results.append({**r, "pred_leaf": pred, "leaf_correct": leaf_correct,
                     "pred_general": pred_general, "gold_general": gold_general,
                     "general_correct": general_correct})

n = len(results)
leaf_acc = sum(r["leaf_correct"] for r in results) / n
general_acc = sum(r["general_correct"] for r in results) / n

print(f"\n{LOG} === RESULTS ({n} rows, prompt={len(SYSTEM_PROMPT)} chars) ===")
print(f"{LOG} Leaf accuracy:    {leaf_acc:.1%}")
print(f"{LOG} General accuracy: {general_acc:.1%}")
print(f"{LOG} Total time: {total_elapsed:.0f}s ({total_elapsed/60:.1f} min) = {n/total_elapsed:.2f} rows/sec")

with open(OUT_CSV, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
    w.writeheader()
    w.writerows(results)
print(f"{LOG} Per-row predictions written to {OUT_CSV}")

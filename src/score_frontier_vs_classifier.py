"""Score Gemini 3.7 Flash and Sonnet 5 on the same eval sets as serving hinge.

Framing only — not a production runtime. Uses the finalized labelling prompt
(taxonomy + TAIL_ADDENDUM loan-keyword bugfix + full worked-example notes),
same harness as `src/score_gold_v4.py` / CLAUDE.md §6a.

Sets (never locked v5/v6): merchant-disjoint holdout, risk-category gold,
and the row-disjoint pipeline eval. Unique fingerprints are labelled once
(~2,004 rows) then joined back.

Usage:
    python src/score_frontier_vs_classifier.py              # label missing + score
    python src/score_frontier_vs_classifier.py --score-only
    python src/score_frontier_vs_classifier.py --models gemini
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import pathlib
import sys
import time

import joblib
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from build_tail_eval import TAIL_ADDENDUM  # noqa: E402
from confusion_analysis import analyse, load_taxonomy  # noqa: E402
from eval_sets import refuse_confirmation_eval  # noqa: E402
from gating_experiment import (  # noqa: E402
    build_notes_addendum,
    build_system_prompt,
    load_crosswalk,
    load_example_merchants,
    load_example_notes,
)
from score_t5b_residual import (  # noqa: E402
    HINGE_PATH,
    _init_waterfall,
    attach_waterfall,
    features_frame,
    scores_and_margin,
)

HOLDOUT = ROOT / "data" / "gold_v2_slm_eval_holdout.csv"
RISK = ROOT / "data" / "gold_transactions_risk_categories.csv"
PIPELINE = ROOT / "outputs" / "gold_pipeline_eval.csv"
CACHE = ROOT / "outputs" / "frontier_vs_clf_unique.csv"
REPORT = ROOT / "data" / "frontier_vs_classifier_report.md"
BATCH = 25
MAX_RETRIES = 3
MODEL_IDS = {
    "gemini": "gemini-3.7-flash",
    "sonnet": "claude-sonnet-5",
}


def fingerprint(merchant, description, amount, direction):
    try:
        amt = round(abs(float(amount)), 4)
    except (TypeError, ValueError):
        amt = 0.0
    return json.dumps([
        (merchant or "").strip().lower(),
        (description or "").strip().lower(),
        amt,
        (direction or "").strip().lower(),
    ], ensure_ascii=False)


def txn_text(i, r):
    merchant = (r.get("merchant_raw") or "").strip().lower()
    return (f"{i}. merchant: {merchant} | description: {r['description_raw']} | "
            f"amount: {r['amount']} | direction: {(r.get('direction') or '').strip().lower()}")


def load_set(path, source, extra_cols=None):
    refuse_confirmation_eval(path)
    rows = []
    for r in csv.DictReader(open(path)):
        row = dict(r)
        row["source"] = source
        row["fp"] = fingerprint(
            r.get("merchant_raw"), r.get("description_raw"),
            r.get("amount"), r.get("direction"),
        )
        if extra_cols:
            for k, v in extra_cols.items():
                row.setdefault(k, v)
        rows.append(row)
    return rows


def load_cache():
    if not CACHE.exists():
        return {}
    out = {}
    for r in csv.DictReader(open(CACHE)):
        out[r["fp"]] = r
    return out


def write_cache(cache):
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    fields = ["fp", "merchant_raw", "description_raw", "amount", "direction",
              "pred_gemini", "pred_sonnet"]
    with open(CACHE, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for fp in sorted(cache):
            row = cache[fp]
            w.writerow({k: row.get(k, "") for k in fields})


def build_prompt():
    _, _, leaves, gen_of, notes_of = load_crosswalk()
    examples_of = load_example_merchants()
    example_notes = load_example_notes()
    system_prompt = (
        build_system_prompt(leaves, gen_of, notes_of, examples_of)
        + TAIL_ADDENDUM
        + build_notes_addendum(example_notes)
    )
    leaf_list = sorted(leaves) + ["unclassified_other"]
    return system_prompt, leaf_list, dict(gen_of)


def score_batch_gemini(client, system_prompt, leaf_list, batch, tag):
    from google.genai import types

    schema = {
        "type": "object",
        "properties": {
            "results": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "index": {"type": "integer"},
                        "category_index": {"type": "integer", "minimum": 1,
                                           "maximum": len(leaf_list)},
                    },
                    "required": ["index", "category_index"],
                },
            }
        },
        "required": ["results"],
    }
    index_addendum = "\n\n## Category index (output this number, not the name)\n" + "\n".join(
        f"{i + 1}. {leaf}" for i, leaf in enumerate(leaf_list))
    user_msg = "Classify each transaction:\n" + "\n".join(
        txn_text(i + 1, r) for i, r in enumerate(batch))
    resp = client.models.generate_content(
        model=MODEL_IDS["gemini"], contents=user_msg,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt + index_addendum,
            response_mime_type="application/json",
            response_schema=schema,
            temperature=0.0,
        ),
    )
    try:
        data = json.loads(resp.text)
    except Exception as e:
        print(f"[gemini] [{tag}] JSON parse failed: {e}", file=sys.stderr)
        return {}
    out = {}
    for r in data.get("results", []):
        idx, cat_idx = r.get("index"), r.get("category_index")
        if isinstance(idx, int) and isinstance(cat_idx, int) and 1 <= cat_idx <= len(leaf_list):
            out[idx] = leaf_list[cat_idx - 1]
    return out


def score_batch_sonnet(client, system_prompt, leaf_list, batch, tag):
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
    user_msg = "Classify each transaction:\n" + "\n".join(
        txn_text(i + 1, r) for i, r in enumerate(batch))
    resp = client.messages.create(
        model=MODEL_IDS["sonnet"], max_tokens=4000,
        system=[{"type": "text", "text": system_prompt,
                 "cache_control": {"type": "ephemeral", "ttl": "1h"}}],
        tools=[tool], tool_choice={"type": "tool", "name": "submit_classifications"},
        messages=[{"role": "user", "content": user_msg}],
        timeout=120.0,
    )
    tool_use = next((b for b in resp.content if b.type == "tool_use"), None)
    if tool_use is None:
        print(f"[sonnet] [{tag}] no tool_use, stop_reason={resp.stop_reason}", file=sys.stderr)
        return {}
    return {r["index"]: r["detailed_category"] for r in tool_use.input.get("results", [])
            if isinstance(r.get("index"), int)}


def label_model(model, unique_rows, cache, system_prompt, leaf_list):
    col = f"pred_{model}"
    todo = [r for r in unique_rows if not (cache.get(r["fp"]) or {}).get(col)]
    print(f"[{model}] {len(todo)}/{len(unique_rows)} rows need labels "
          f"(prompt {len(system_prompt)} chars)", file=sys.stderr)
    if not todo:
        return
    if model == "gemini":
        from google import genai
        client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"], vertexai=False)

        def call(batch, tag):
            return score_batch_gemini(client, system_prompt, leaf_list, batch, tag)
    else:
        import anthropic
        client = anthropic.Anthropic()

        def call(batch, tag):
            return score_batch_sonnet(client, system_prompt, leaf_list, batch, tag)

    start = time.monotonic()
    n_batches = (len(todo) + BATCH - 1) // BATCH
    for b in range(n_batches):
        batch = todo[b * BATCH:(b + 1) * BATCH]
        to_do = list(range(len(batch)))
        got = {}
        for attempt in range(MAX_RETRIES):
            sub_batch = [batch[i] for i in to_do]
            try:
                result = call(sub_batch, f"batch{b}try{attempt}")
            except Exception as e:
                print(f"[{model}] batch {b} attempt {attempt} exception: {e}", file=sys.stderr)
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
            row = batch[local_i]
            rec = cache.setdefault(row["fp"], {
                "fp": row["fp"],
                "merchant_raw": row["merchant_raw"],
                "description_raw": row["description_raw"],
                "amount": row["amount"],
                "direction": row["direction"],
            })
            rec[col] = leaf
        write_cache(cache)
        done = min((b + 1) * BATCH, len(todo))
        elapsed = time.monotonic() - start
        if done % 100 < BATCH or b == n_batches - 1:
            rate = done / elapsed if elapsed else 0
            print(f"[{model}] {done}/{len(todo)} labelled in {elapsed:.0f}s "
                  f"({rate:.2f} rows/sec)", file=sys.stderr)


def hinge_preds(rows):
    bundle = joblib.load(HINGE_PATH)
    df = pd.DataFrame(rows)
    pred, _, _ = scores_and_margin(bundle, features_frame(df))
    return {r["fp"]: p for r, p in zip(rows, pred)}


def as_analyse(rows, gold_key, pred_key, gen_of, risk_leaves):
    packed = [{"gold_leaf": r[gold_key], "pred_leaf": r[pred_key]} for r in rows]
    return analyse(packed, gen_of, risk_leaves)


def fmt(a):
    risk = f"{a['risk_acc']:.1%}" if a["risk_acc"] is not None else "n/a"
    return (f"leaf {a['leaf_acc']:.1%} / general {a['gen_acc']:.1%} "
            f"/ risk bar {risk} (n={a['risk_n']})  n={a['n']}")


def pipeline_then(rows, model_pred):
    out = []
    for r in rows:
        if str(r.get("waterfall_tier", "")).startswith(("T1_", "T2_", "T3_", "T4_", "T5_")):
            pred = r["waterfall_leaf"]
        else:
            pred = model_pred[r["fp"]]
        out.append({**r, "pred_leaf": pred})
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--score-only", action="store_true")
    parser.add_argument("--models", nargs="+", default=["gemini", "sonnet"],
                        choices=list(MODEL_IDS))
    args = parser.parse_args()

    for path in (HOLDOUT, RISK, PIPELINE):
        if not path.exists():
            sys.exit(f"missing {path}")
        refuse_confirmation_eval(path)

    holdout = load_set(HOLDOUT, "holdout")
    risk = load_set(RISK, "risk", extra_cols={"provider": "plaid", "native_category": ""})
    pipeline = load_set(PIPELINE, "pipeline")

    unique = {}
    for r in holdout + risk + pipeline:
        unique.setdefault(r["fp"], {
            "fp": r["fp"],
            "merchant_raw": r["merchant_raw"],
            "description_raw": r["description_raw"],
            "amount": r["amount"],
            "direction": r["direction"],
            "provider": r.get("provider") or "plaid",
            "native_category": r.get("native_category") or "",
        })
    unique_rows = list(unique.values())
    print(f"unique fingerprints: {len(unique_rows)} "
          f"(holdout {len(holdout)}, risk {len(risk)}, pipeline {len(pipeline)})",
          file=sys.stderr)

    cache = load_cache()
    system_prompt, leaf_list, gen_of = build_prompt()
    gen_of_tax, risk_leaves = load_taxonomy()
    gen_of = {**gen_of, **gen_of_tax}

    if not args.score_only:
        for model in args.models:
            label_model(model, unique_rows, cache, system_prompt, leaf_list)
        cache = load_cache()

    missing = []
    for model in args.models:
        col = f"pred_{model}"
        missing.extend(r["fp"] for r in unique_rows if not cache.get(r["fp"], {}).get(col))
    if missing:
        sys.exit(f"still missing {len(set(missing))} labels — re-run without --score-only")

    _init_waterfall()
    hinge_map = hinge_preds(unique_rows)

    pipe_df = pd.DataFrame(pipeline)
    pipe_df = attach_waterfall(pipe_df)
    leftover_fps = set(pipe_df.loc[pipe_df["is_t6"], "fp"])
    waterfall_leaf = dict(zip(pipe_df["fp"], pipe_df["t6_leaf"]))
    waterfall_tier = dict(zip(pipe_df["fp"], pipe_df["waterfall_tier"]))
    for r in pipeline:
        r["waterfall_leaf"] = waterfall_leaf[r["fp"]]
        r["waterfall_tier"] = waterfall_tier[r["fp"]]

    hold_df = pd.DataFrame(holdout)
    hold_df = attach_waterfall(hold_df)
    holdout_t6 = set(hold_df.loc[hold_df["is_t6"], "fp"])

    def attach_preds(rows):
        out = []
        for r in rows:
            rec = cache[r["fp"]]
            out.append({
                **r,
                "gold_leaf": r["gold_leaf"].strip(),
                "pred_hinge": hinge_map[r["fp"]],
                "pred_gemini": rec["pred_gemini"],
                "pred_sonnet": rec["pred_sonnet"],
            })
        return out

    holdout_s = attach_preds(holdout)
    risk_s = attach_preds(risk)
    pipeline_s = attach_preds(pipeline)
    leftover_s = [r for r in pipeline_s if r["fp"] in leftover_fps]
    holdout_t6_s = [r for r in holdout_s if r["fp"] in holdout_t6]

    slices = [
        ("Holdout (merchant-disjoint, n=1,055) — iteration suite", holdout_s),
        ("Holdout T6-bound (T1–T5 miss)", holdout_t6_s),
        ("Risk gold — iteration suite (Gemini/Sonnet drafted some of these; mildly favours them)",
         risk_s),
        ("Pipeline eval (row-disjoint, n=1,884) — 4-field model vs gold, no T1–T5",
         pipeline_s),
        ("Pipeline leftover (T1–T5 miss) — where a runtime classifier would serve", leftover_s),
    ]

    lines = [
        "# Frontier LLMs vs serving hinge (v5)",
        "",
        "Scored 2026-08-27. **Framing only** — Gemini 3.7 Flash and Sonnet 5 are not",
        "candidates for per-transaction runtime. Same finalized prompt as CLAUDE.md §6a",
        f"({len(system_prompt):,} chars: taxonomy + TAIL_ADDENDUM + full worked-example notes).",
        "Unique fingerprints labelled once, then joined to holdout / risk / pipeline.",
        "Serving hinge is `outputs/distill_models/tfidf_linearsvm_sgd.joblib` (v5).",
        "Locked v5/v6 were not scored.",
        "",
        "## Headline",
        "",
    ]

    print("\n=== Frontier vs serving hinge (clf-only, 4-field) ===")
    table_rows = []
    for title, rows in slices:
        print(f"\n--- {title} n={len(rows)} ---")
        lines.append(f"### {title}")
        lines.append("")
        lines.append(f"n={len(rows)}")
        lines.append("")
        for name, key in (("hinge v5", "pred_hinge"),
                          ("Gemini 3.7 Flash", "pred_gemini"),
                          ("Sonnet 5", "pred_sonnet")):
            a = as_analyse(rows, "gold_leaf", key, gen_of, risk_leaves)
            line = f"- **{name}:** {fmt(a)}"
            print(line)
            lines.append(line)
            table_rows.append((title, name, a))
        lines.append("")

    print("\n=== Pipeline: T1–T5 then model (production-shaped) ===")
    lines += [
        "## Pipeline: T1–T5 then model",
        "",
        "Same 1,884 rows as `data/waterfall_pipeline_report.md`. Deterministic tiers",
        "keep the waterfall leaf; leftover rows take the model prediction.",
        "",
    ]
    for name, pred_map in (
        ("hinge v5", {r["fp"]: r["pred_hinge"] for r in pipeline_s}),
        ("Gemini 3.7 Flash", {r["fp"]: r["pred_gemini"] for r in pipeline_s}),
        ("Sonnet 5", {r["fp"]: r["pred_sonnet"] for r in pipeline_s}),
    ):
        combined = pipeline_then(pipeline_s, pred_map)
        a = as_analyse(combined, "gold_leaf", "pred_leaf", gen_of, risk_leaves)
        line = f"- **T1–T5 then {name}:** {fmt(a)}"
        print(line)
        lines.append(line)
    lines += [
        "",
        "## Caveats",
        "",
        "- Risk gold was drafted by Gemini+Sonnet before human review, so those two",
        "  models are mildly favoured on that set. Holdout is the clean comparison.",
        "- Gemini temperature=0 is not fully deterministic; this is a single run.",
        "- Do not serve either LLM at runtime. The gap is the cost of a local linear",
        "  head vs a frontier call, not a reason to put Gemini/Sonnet in the waterfall.",
        "",
        f"Predictions cache: `{CACHE.relative_to(ROOT)}`.",
        "",
    ]
    REPORT.write_text("\n".join(lines) + "\n")
    print(f"\nWrote {REPORT}", file=sys.stderr)


if __name__ == "__main__":
    main()

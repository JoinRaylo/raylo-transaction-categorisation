"""Gemini 3.8 Flash vs the saved Gemini 3.7 Flash labels.

Reuses the 27 Aug frontier unique-fingerprint cache (2,004 rows, pred_gemini)
and the 23 Aug holdout CSV. Does not re-call 3.7. Locked v5/v6 are not scored.

Same harness as `src/score_frontier_vs_classifier.py`: finalized labelling
prompt, batch-of-25, JSON category-index schema, temperature=0, Developer API.
Only the model id changes (`gemini-3.8-flash`).

Usage:
    python benchmarks/score_gemini38_vs_37.py           # label missing + score
    python benchmarks/score_gemini38_vs_37.py --score-only
"""
from __future__ import annotations

import argparse
import csv
import os
import pathlib
import sys
import time
from math import erfc, sqrt

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from confusion_analysis import load_taxonomy  # noqa: E402
from eval_sets import refuse_confirmation_eval  # noqa: E402
from score_frontier_vs_classifier import (  # noqa: E402
    BATCH,
    CACHE,
    HOLDOUT,
    MAX_RETRIES,
    MODEL_IDS,
    PIPELINE,
    RISK,
    as_analyse,
    attach_waterfall,
    build_prompt,
    fmt,
    hinge_preds,
    load_set,
    pipeline_then,
    score_batch_gemini,
)
from score_t5b_residual import _init_waterfall  # noqa: E402

MODEL_ID = "gemini-3.8-flash"
PRED_CSV = ROOT / "outputs" / "mlx_full_run" / "gemini38_frontier_preds.csv"
HOLDOUT_37_CSV = ROOT / "outputs" / "mlx_full_run" / "gemini37_finalprompt_predictions.csv"
REPORT = ROOT / "data" / "gemini38_vs_37_report.md"


def load_38():
    out = {}
    if PRED_CSV.exists():
        for r in csv.DictReader(open(PRED_CSV)):
            if r.get("pred_gemini38"):
                out[r["fp"]] = r["pred_gemini38"]
    return out


def write_38(preds):
    PRED_CSV.parent.mkdir(parents=True, exist_ok=True)
    cache = {r["fp"]: r for r in csv.DictReader(open(CACHE))}
    fields = ["fp", "merchant_raw", "description_raw", "amount", "direction",
              "pred_gemini37", "pred_gemini38"]
    with open(PRED_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for fp in sorted(cache):
            rec = cache[fp]
            w.writerow({
                "fp": fp,
                "merchant_raw": rec.get("merchant_raw", ""),
                "description_raw": rec.get("description_raw", ""),
                "amount": rec.get("amount", ""),
                "direction": rec.get("direction", ""),
                "pred_gemini37": rec.get("pred_gemini", ""),
                "pred_gemini38": preds.get(fp, ""),
            })


def label_38(unique_rows, preds, system_prompt, leaf_list):
    todo = [r for r in unique_rows if not preds.get(r["fp"])]
    print(f"[gemini-3.8] {len(todo)}/{len(unique_rows)} rows need labels "
          f"(prompt {len(system_prompt)} chars)", file=sys.stderr)
    if not todo:
        return preds

    from google import genai
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"], vertexai=False)

    def call(batch, tag):
        saved = MODEL_IDS["gemini"]
        MODEL_IDS["gemini"] = MODEL_ID
        try:
            return score_batch_gemini(client, system_prompt, leaf_list, batch, tag)
        finally:
            MODEL_IDS["gemini"] = saved

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
                print(f"[gemini-3.8] batch {b} attempt {attempt} exception: {e}",
                      file=sys.stderr)
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
            preds[batch[local_i]["fp"]] = leaf
        write_38(preds)
        done = min((b + 1) * BATCH, len(todo))
        elapsed = time.monotonic() - start
        if done % 25 == 0 or b == n_batches - 1:
            rate = done / elapsed if elapsed else 0
            print(f"[gemini-3.8] {done}/{len(todo)} labelled in {elapsed:.0f}s "
                  f"({rate:.2f} rows/sec)", file=sys.stderr)
    return preds


def mcnemar(a_correct, b_correct):
    both = sum(a and b for a, b in zip(a_correct, b_correct))
    a_only = sum(a and not b for a, b in zip(a_correct, b_correct))
    b_only = sum((not a) and b for a, b in zip(a_correct, b_correct))
    neither = sum((not a) and not b for a, b in zip(a_correct, b_correct))
    disc = a_only + b_only
    if disc == 0:
        p = 1.0
    else:
        z = (abs(a_only - b_only) - 1) / sqrt(disc)
        p = erfc(z / sqrt(2.0))
    return both, a_only, b_only, neither, p


def acc_line(name, a):
    return f"- **{name}:** {fmt(a)}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--score-only", action="store_true")
    args = parser.parse_args()

    for path in (HOLDOUT, RISK, PIPELINE, CACHE):
        if not path.exists():
            sys.exit(f"missing {path}")
        if path.suffix == ".csv" and path != CACHE:
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
        })
    unique_rows = list(unique.values())
    print(f"unique fingerprints: {len(unique_rows)}", file=sys.stderr)

    cache37 = {r["fp"]: r for r in csv.DictReader(open(CACHE))}
    preds38 = load_38()
    system_prompt, leaf_list, gen_of = build_prompt()
    gen_of_tax, risk_leaves = load_taxonomy()
    gen_of = {**gen_of, **gen_of_tax}

    wall = None
    if not args.score_only:
        t0 = time.monotonic()
        preds38 = label_38(unique_rows, preds38, system_prompt, leaf_list)
        wall = time.monotonic() - t0

    missing = [r["fp"] for r in unique_rows if not preds38.get(r["fp"])]
    if missing:
        sys.exit(f"still missing {len(missing)} 3.8 labels — re-run without --score-only")

    _init_waterfall()
    hinge_map = hinge_preds(unique_rows)
    pipe_df = attach_waterfall(pd.DataFrame(pipeline))
    leftover_fps = set(pipe_df.loc[pipe_df["is_t6"], "fp"])
    waterfall_leaf = dict(zip(pipe_df["fp"], pipe_df["t6_leaf"]))
    waterfall_tier = dict(zip(pipe_df["fp"], pipe_df["waterfall_tier"]))
    for r in pipeline:
        r["waterfall_leaf"] = waterfall_leaf[r["fp"]]
        r["waterfall_tier"] = waterfall_tier[r["fp"]]
    hold_df = attach_waterfall(pd.DataFrame(holdout))
    holdout_t6 = set(hold_df.loc[hold_df["is_t6"], "fp"])

    def attach(rows):
        out = []
        for r in rows:
            rec = cache37[r["fp"]]
            out.append({
                **r,
                "gold_leaf": r["gold_leaf"].strip(),
                "pred_hinge": hinge_map[r["fp"]],
                "pred_gemini37": rec["pred_gemini"],
                "pred_gemini38": preds38[r["fp"]],
            })
        return out

    holdout_s = attach(holdout)
    risk_s = attach(risk)
    pipeline_s = attach(pipeline)
    leftover_s = [r for r in pipeline_s if r["fp"] in leftover_fps]
    holdout_t6_s = [r for r in holdout_s if r["fp"] in holdout_t6]
    slices = [
        ("Holdout (merchant-disjoint)", holdout_s),
        ("Holdout T6-bound (T1–T5 miss)", holdout_t6_s),
        ("Risk gold (Gemini/Sonnet drafted some; mildly favours them)", risk_s),
        ("Pipeline eval (row-disjoint, 4-field, no T1–T5)", pipeline_s),
        ("Pipeline leftover (T1–T5 miss)", leftover_s),
    ]

    print("\n=== Gemini 3.8 Flash vs saved Gemini 3.7 Flash ===")
    table = [
        "| Set | n | Gemini 3.7 Flash (saved) | Gemini 3.8 Flash |",
        "|---|---:|---:|---:|",
    ]
    detail = []
    hold_37 = hold_38 = hold_mc = None
    for title, rows in slices:
        print(f"\n--- {title} n={len(rows)} ---")
        accs = {}
        for name, key in (
            ("Gemini 3.7 Flash (saved)", "pred_gemini37"),
            ("Gemini 3.8 Flash", "pred_gemini38"),
        ):
            a = as_analyse(rows, "gold_leaf", key, gen_of, risk_leaves)
            accs[name] = a
            print(acc_line(name, a))
        c37 = [r["gold_leaf"] == r["pred_gemini37"] for r in rows]
        c38 = [r["gold_leaf"] == r["pred_gemini38"] for r in rows]
        both, only37, only38, neither, pval = mcnemar(c37, c38)
        agree = sum(r["pred_gemini37"] == r["pred_gemini38"] for r in rows) / len(rows)
        delta = (accs["Gemini 3.8 Flash"]["leaf_acc"]
                 - accs["Gemini 3.7 Flash (saved)"]["leaf_acc"])
        note = (f"leaf Δ {delta:+.1%}; label agreement {agree:.1%}; "
                f"McNemar 3.7-only {only37} / 3.8-only {only38} / both-right {both} "
                f"/ both-wrong {neither} (two-sided p≈{pval:.3f})")
        print(f"  {note}")
        detail.append((title, rows, accs, note))
        table.append(
            f"| {title} | {len(rows)} | "
            f"{accs['Gemini 3.7 Flash (saved)']['leaf_acc']:.1%} | "
            f"{accs['Gemini 3.8 Flash']['leaf_acc']:.1%} |"
        )
        if title.startswith("Holdout (merchant"):
            hold_37 = accs["Gemini 3.7 Flash (saved)"]
            hold_38 = accs["Gemini 3.8 Flash"]
            hold_mc = (only37, only38, pval, agree, delta)

    print("\n=== Pipeline: T1–T5 then model ===")
    pipe_acc = []
    pipe_lines = []
    for name, key in (
        ("Gemini 3.7 Flash (saved)", "pred_gemini37"),
        ("Gemini 3.8 Flash", "pred_gemini38"),
    ):
        pred_map = {r["fp"]: r[key] for r in pipeline_s}
        combined = pipeline_then(pipeline_s, pred_map)
        a = as_analyse(combined, "gold_leaf", "pred_leaf", gen_of, risk_leaves)
        line = f"- **T1–T5 then {name}:** {fmt(a)}"
        print(line)
        pipe_lines.append(line)
        pipe_acc.append(a["leaf_acc"])
    table.append(
        f"| T1–T5 then model (pipeline) | {len(pipeline_s)} | "
        f"{pipe_acc[0]:.1%} | {pipe_acc[1]:.1%} |"
    )

    old_leaf = old_gen = old_n = None
    if HOLDOUT_37_CSV.exists():
        old = list(csv.DictReader(open(HOLDOUT_37_CSV)))
        old_n = len(old)
        old_leaf = sum(str(r["leaf_correct"]).lower() in ("true", "1") for r in old) / old_n
        old_gen = sum(str(r["general_correct"]).lower() in ("true", "1") for r in old) / old_n
        print(f"\n23 Aug holdout CSV: {old_leaf:.1%} / {old_gen:.1%}")

    only37, only38, pval, agree, delta = hold_mc
    out = [
        "# Gemini 3.8 Flash vs Gemini 3.7 Flash",
        "",
        "Scored 2026-09-03. **Framing / labelling-stack bake-off only** — not a",
        "runtime candidate. 3.7 labels are reused (not re-called): the 27 Aug",
        "frontier unique-fingerprint cache (`outputs/frontier_vs_clf_unique.csv`).",
        "Locked v5/v6 were not scored. Production labelling still uses 3.7 until",
        "this bake-off is acted on.",
        "",
        "Harness matches `src/score_frontier_vs_classifier.py`: finalized labelling",
        f"prompt ({len(system_prompt):,} chars: taxonomy + TAIL_ADDENDUM + notes),",
        f"batch-of-25, JSON category-index schema, `temperature=0`, model `{MODEL_ID}`.",
        "",
        "## Headline",
        "",
        f"On the clean merchant-disjoint holdout (n={len(holdout_s)}), Gemini 3.8 Flash "
        f"is **{hold_38['leaf_acc']:.1%}** leaf / {hold_38['gen_acc']:.1%} general vs saved "
        f"3.7 **{hold_37['leaf_acc']:.1%}** / {hold_37['gen_acc']:.1%} "
        f"(leaf Δ {delta:+.1%}; McNemar 3.7-only {only37} / 3.8-only {only38}, "
        f"two-sided p≈{pval:.3f}). Label agreement {agree:.1%}.",
        "",
        *table,
        "",
        "3.8 wall-clock: "
        + ("not timed (score-only or fully resumed)."
           if not wall else f"{wall:.0f}s ({len(unique_rows) / wall:.2f} rows/s)."),
        "",
    ]
    for title, rows, accs, note in detail:
        out += [
            f"### {title}",
            "",
            f"n={len(rows)}",
            "",
            acc_line("Gemini 3.7 Flash (saved)", accs["Gemini 3.7 Flash (saved)"]),
            acc_line("Gemini 3.8 Flash", accs["Gemini 3.8 Flash"]),
            "",
            note,
            "",
        ]
    out += [
        "## Pipeline: T1–T5 then model",
        "",
        "Deterministic tiers keep the waterfall leaf; leftover rows take the model.",
        "",
        *pipe_lines,
        "",
        "## Caveats",
        "",
        "- Single 3.8 run vs a single saved 3.7 run. The published 3.7 holdout is the",
        "  23 Aug 3-run average **84.2% ± 0.15pp**; the 27 Aug cache can differ by ~1pp.",
        "- Drop-in model-id swap at `temperature=0` (both models think by default).",
        "- Risk gold was drafted by Gemini 3.7 + Sonnet; holdout is the clean cut.",
        "- Do not serve either model at runtime.",
        "",
        f"3.8 predictions: `{PRED_CSV.relative_to(ROOT)}`.",
        f"Scorer: `benchmarks/score_gemini38_vs_37.py`.",
        "",
    ]
    if old_leaf is not None:
        out += [
            "## Secondary: 23 Aug holdout CSV",
            "",
            f"Saved `gemini37_finalprompt_predictions.csv`: leaf **{old_leaf:.1%}** / "
            f"general {old_gen:.1%} (n={old_n}). One of the three runs behind 84.2%.",
            "Prompt then was 84,348 chars; today's prompt is longer. Prefer the",
            "frontier-cache comparison (same 27 Aug construction).",
            "",
        ]
    REPORT.write_text("\n".join(out) + "\n")
    print(f"\nWrote {REPORT}", file=sys.stderr)


if __name__ == "__main__":
    main()

"""Assemble tranche-4 labels for ingest, or correct provenance on the snapshot.

Review is CLOSED. Default command is `relabel` (rewrite tiers on the existing
snapshot). `assemble` is refused — it would rebuild from stale overlay files.

T2 candidates are context_dependent and excluded from dictionary merge.
"""
from __future__ import annotations

import csv
import pathlib
import sys
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[1]
REV = ROOT / "outputs" / "tranche4_agent_review"
LABELS_IN = ROOT / "outputs" / "production_labels.csv"
LABELS_OUT = ROOT / "data" / "production_labels_tranche4.csv"
USEABLE_OUT = REV / "tranche4_useable.csv"
REPORT = REV / "tranche4_final_report.md"

sys.path.insert(0, str(ROOT / "src"))
from gating_experiment import load_crosswalk  # noqa: E402
from label_provenance import (  # noqa: E402
    CARLOS_REVIEWER_ID,
    DICTIONARY_ELIGIBLE_TIERS,
    HUMAN_REVIEWED,
    reviewer_id_for,
    truthful_tier,
)

CARLOS = {
    "32 red": "gambling_casino",
    "credit spring": "personal_loan_repayment",
}


def load(path):
    return list(csv.DictReader(open(path)))


def index_leaf(path, merchant="merchant", leaf="recommended_leaf"):
    return {r[merchant]: r[leaf] for r in load(path)}


def main():
    _, _, leaves, gen_of, _ = load_crosswalk()
    tax = set(leaves)

    leftover_m = {r["merchant"]: r for r in load(REV / "master_leftover_flips_final.csv")}
    for r in leftover_m.values():
        if r["recommended_leaf"] not in tax:
            raise SystemExit(f"invalid leftover master leaf {r}")

    core200 = index_leaf(REV / "master_core200.csv")
    t4_head = index_leaf(REV / "reviewer_C_t4_120.csv")

    def apply_leftover(rows):
        out = {}
        t2 = {}
        for r in rows:
            m = r["merchant"]
            leaf = leftover_m[m]["recommended_leaf"] if m in leftover_m else r["recommended_leaf"]
            t2f = leftover_m[m]["t2_candidate"] if m in leftover_m else r.get("t2_candidate", "")
            if m in leftover_m:
                t2f = leftover_m[m].get("t2_candidate", t2f)
            out[m] = leaf
            t2[m] = str(t2f).lower().startswith("y")
            if leaf not in tax:
                raise SystemExit(f"invalid {m} {leaf}")
        return out, t2

    core_rest, t2_core_rest = apply_leftover(load(REV / "master_core_rest.csv"))
    t4_rest, t2_t4_rest = apply_leftover(load(REV / "master_t4_rest.csv"))

    t2 = dict(t2_core_rest)
    t2.update(t2_t4_rest)
    for r in load(REV / "master_core200.csv"):
        t2[r["merchant"]] = str(r.get("t2_candidate", "")).lower().startswith("y")
    for r in load(REV / "reviewer_C_t4_120.csv"):
        t2[r["merchant"]] = str(r.get("t2_candidate", "")).lower().startswith("y")
    for m, r in leftover_m.items():
        t2[m] = str(r.get("t2_candidate", "")).lower().startswith("y")

    # Agent overlay, lowest to highest
    overlay = {}
    overlay.update(core_rest)
    overlay.update(t4_rest)
    overlay.update(t4_head)
    overlay.update(core200)
    overlay.update({m: r["recommended_leaf"] for m, r in leftover_m.items()})
    overlay.update(CARLOS)

    labels = load(LABELS_IN)
    n_agent = n_carlos = n_t2 = n_accepted_flip = 0
    out = []
    for r in labels:
        m = r["merchant"]
        leaf, tier = r["final_leaf"], r["tier"]
        source = f"gate_{tier}"
        if m in overlay:
            leaf = overlay[m]
            if m in CARLOS:
                source = CARLOS_REVIEWER_ID
                n_carlos += 1
            else:
                source = "agent_review"
                n_agent += 1
            if t2.get(m):
                tier = "context_dependent"
                n_t2 += 1
            else:
                if r["tier"] in {"auto_accept", "accepted"} and overlay[m] != r["final_leaf"]:
                    n_accepted_flip += 1
                tier = HUMAN_REVIEWED if source == CARLOS_REVIEWER_ID else "agent_review"
        if leaf not in tax and leaf:
            raise SystemExit(f"invalid assembled leaf {m} {leaf}")
        row = dict(r)
        row["final_leaf"] = leaf
        row["tier"] = tier
        row["general_category"] = gen_of.get(leaf, "")
        row["resolution_source"] = source
        row["t2_candidate"] = "yes" if t2.get(m) else "no"
        row["draft_leaf"] = r["gemini_leaf"] if tier == "needs_review" else leaf
        row["reviewer_id"] = reviewer_id_for(tier, source)
        out.append(row)

    fields = list(dict.fromkeys(
        list(labels[0].keys()) + ["resolution_source", "t2_candidate", "draft_leaf", "reviewer_id"]))
    LABELS_OUT.parent.mkdir(exist_ok=True)
    with open(LABELS_OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(out)

    good = DICTIONARY_ELIGIBLE_TIERS
    useable = [r for r in out if r["tier"] in good]
    with open(USEABLE_OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(useable)

    stats = Counter(r["tier"] for r in out)
    vol = Counter()
    for r in out:
        vol[r["tier"]] += int(r["plaid_n"])
    total_v = sum(vol.values())
    good_n = sum(stats[t] for t in good)
    good_v = sum(vol[t] for t in good)

    lines = [
        "# Tranche 4 final labels (2026-08-25)",
        "",
        f"Wrote `{LABELS_OUT.relative_to(ROOT)}` ({len(out)} strings) and "
        f"`{USEABLE_OUT.relative_to(ROOT)}` ({len(useable)} dictionary-eligible).",
        "",
        "Did **not** overwrite `outputs/production_labels.csv` (Opus still running).",
        "Did **not** score locked v5.",
        "",
        "## Tiers",
        "",
        "| tier | strings | volume |",
        "|---|---:|---:|",
    ]
    for t, n in stats.most_common():
        lines.append(f"| {t} | {n} | {vol[t] / total_v:.1%} |")
    lines += [
        "",
        f"Dictionary-eligible (`auto_accept` / `accepted` / `human_reviewed` / agent_*): "
        f"**{good_n}** strings, **{good_v / total_v:.1%}** of Plaid volume in this 100k.",
        "",
        f"Agent overlay applied on **{n_agent}** strings; Carlos on **{n_carlos}**; "
        f"T2 → `context_dependent` (not ingested) **{n_t2}**; "
        f"accepted-tier leaf flips **{n_accepted_flip}**.",
        "",
        "Remaining `needs_review` still needs Opus (or a later pass). `draft_leaf` is Gemini only.",
        "32 red = `gambling_casino`. credit spring = `personal_loan_repayment`.",
    ]
    REPORT.write_text("\n".join(lines) + "\n")
    print(REPORT.read_text())
    print(f"Wrote {LABELS_OUT}")
    print(f"Wrote {USEABLE_OUT}")


def _write_snapshot(out, fields):
    LABELS_OUT.parent.mkdir(exist_ok=True)
    with open(LABELS_OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(out)
    USEABLE_OUT.parent.mkdir(parents=True, exist_ok=True)
    useable = [r for r in out if r["tier"] in DICTIONARY_ELIGIBLE_TIERS]
    with open(USEABLE_OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(useable)
    return useable


def relabel_existing():
    """Correct false human_reviewed provenance on the closed 100k snapshot."""
    if not LABELS_OUT.exists():
        raise SystemExit(f"missing {LABELS_OUT}")
    rows = list(csv.DictReader(open(LABELS_OUT)))
    stats = Counter()
    for r in rows:
        old = r["tier"]
        src = r.get("resolution_source", "")
        r["tier"] = truthful_tier(old, src)
        r["reviewer_id"] = reviewer_id_for(old, src)
        stats[(old, r["tier"])] += 1
    fields = list(rows[0].keys())
    if "reviewer_id" not in fields:
        fields.append("reviewer_id")
    useable = _write_snapshot(rows, fields)
    flipped = sum(n for (old, new), n in stats.items() if old != new)
    print(f"Relabelled {LABELS_OUT}: {flipped} tier changes")
    print("tier now:", dict(Counter(r["tier"] for r in rows)))
    print("human_reviewed:", sum(1 for r in rows if r["tier"] == HUMAN_REVIEWED),
          "reviewer_ids:", dict(Counter(r["reviewer_id"] for r in rows if r["reviewer_id"])))
    print("dictionary-eligible:", len(useable))
    for (old, new), n in sorted(stats.items(), key=lambda kv: -kv[1]):
        if old != new:
            print(f"  {old} -> {new}: {n}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "relabel"
    if cmd == "relabel":
        relabel_existing()
    elif cmd == "assemble":
        raise SystemExit(
            "Refusing: tranche-4 assembly is closed. "
            "Snapshot is data/production_labels_tranche4.csv. "
            "Use: python src/build_tranche4_final_labels.py relabel"
        )
    else:
        raise SystemExit(f"unknown command {cmd!r} (relabel|assemble)")

"""Fill empty Opus tiebreak slots with an agent-equivalent vote.

Reads the Opus-named prediction file and writes a *derived* artifact.
Never overwrites a file that represents one model's predictions.
Does not call the Anthropic API.
"""
import csv
from collections import Counter
from pathlib import Path

from label_provenance import DICTIONARY_ELIGIBLE_TIERS

ROOT = Path(__file__).resolve().parents[1]
OPUS = ROOT / "outputs" / "production_predictions_opus.csv"
FILLED = ROOT / "outputs" / "production_predictions_opus_filled.csv"
LABELS = ROOT / "outputs" / "production_labels.csv"
T4 = ROOT / "data" / "production_labels_tranche4.csv"
LOG = ROOT / "outputs" / "tranche4_agent_review" / "agent_tiebreak_sources.csv"

# Already-decided labels that may fill an empty Opus slot. human_reviewed here
# means Carlos; agent_* are weak supervision, not a substitute for Opus identity.
_FILL_TIERS = DICTIONARY_ELIGIBLE_TIERS | {"context_dependent"}


def main():
    if not OPUS.exists():
        raise SystemExit(f"missing read-only Opus file: {OPUS}")

    labels = {r["merchant"]: r for r in csv.DictReader(open(LABELS))} if LABELS.exists() else {}
    t4 = {r["merchant"]: r for r in csv.DictReader(open(T4))} if T4.exists() else {}
    opus_rows = list(csv.DictReader(open(OPUS)))
    stats = Counter()
    log_rows = []
    out = []
    for r in opus_rows:
        m = r["merchant"]
        leaf = (r.get("llm_leaf") or "").strip()
        conf = r.get("llm_confidence") or ""
        src = "opus_api"
        if not leaf:
            lab = labels.get(m, {})
            g, s = lab.get("gemini_leaf", ""), lab.get("sonnet_leaf", "")
            tr = t4.get(m, {})
            if tr.get("tier") in _FILL_TIERS and (tr.get("final_leaf") or "").strip():
                leaf = tr["final_leaf"]
                conf = "0.85"
                src = "agent_review" if tr.get("tier") != "human_reviewed" else "human_reviewed"
            elif g and g == s:
                leaf = s
                conf = lab.get("sonnet_conf") or "0.6"
                src = "confirm_agree"
            else:
                leaf = g or s
                conf = "0.72"
                src = "gemini_on_disagree"
            stats[src] += 1
            log_rows.append({"merchant": m, "llm_leaf": leaf, "llm_confidence": conf, "source": src})
        else:
            stats["opus_api"] += 1
        out.append({"merchant": m, "llm_leaf": leaf, "llm_confidence": conf})

    empty = sum(1 for r in out if not r["llm_leaf"])
    if empty:
        raise SystemExit(f"{empty} empty leaves remain")

    FILLED.parent.mkdir(parents=True, exist_ok=True)
    with open(FILLED, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["merchant", "llm_leaf", "llm_confidence"])
        w.writeheader()
        w.writerows(out)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["merchant", "llm_leaf", "llm_confidence", "source"])
        w.writeheader()
        w.writerows(log_rows)
    print("wrote derived", FILLED, "n", len(out), dict(stats))
    print("opus file left unchanged:", OPUS)
    print("wrote", LOG)


if __name__ == "__main__":
    main()

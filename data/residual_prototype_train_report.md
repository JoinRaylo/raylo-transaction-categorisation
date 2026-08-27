# Residual + prototype hinge — cheap train/serve test (2026-08-27)

Question: does dropping the ~95% of `tuning_train.jsonl` that T1–T5 already resolve, and keeping a small per-leaf prototype from that head, improve the hinge on the slice the classifier actually serves?

Same architecture as v5 hinge (char-wb TF-IDF 2–5, 30k features, SGD `loss='hinge'`, alpha=1e-6, 50 epochs). **Fresh** vocabulary on the slice. Prototype = up to **20** T1–T5-caught rows per leaf (seed 42). Serving dumps were not overwritten.

## Training mix

| Slice | rows | classes |
|---|---:|---:|
| Full jsonl | 382,739 | 268 |
| T1–T5 caught (dropped, except prototypes) | 364,252 | — |
| T6 residual (kept) | 18,487 | 221 |
| Head prototypes (kept) | 5,033 | 262 |
| **Train (residual + proto)** | **23,520** | **268** |

Fit wall-clock **44s**. Dump: `outputs/distill_models/tfidf_linearsvm_sgd_residual_proto.joblib`. Slice jsonl: `outputs/tuning_train_residual_proto.jsonl` (gitignored).

Leaves only in the prototype (zero residual examples): **47**. Leaves only in residual (no head proto): **6**.

## Scores vs serving v5 hinge

Both heads scored with the same `scores_and_margin` path (gambling promote). Locked v5/v6 not scored.

| Cut | n | v5 leaf | residual+proto leaf | Δ leaf | v5 gen | residual+proto gen | v5 risk | Δ risk |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Holdout (all, merchant-disjoint) | 1055 | 53.8% | 32.7% | -21.1% | 61.0% | 39.5% | 57.7% | -16.3% |
| Holdout T6-bound | 428 | 57.7% | 36.0% | -21.7% | 64.5% | 42.5% | 60.6% | -18.2% |
| Risk gold (all) | 711 | 80.6% | 54.7% | -25.9% | 85.5% | 60.9% | 86.1% | -27.0% |
| Risk gold T6-bound | 88 | 73.9% | 58.0% | -15.9% | 78.4% | 61.4% | 88.4% | -18.6% |
| Pipeline eval residual (row-disjoint) | 516 | 60.1% | 38.0% | -22.1% | 66.9% | 44.0% | 72.3% | -20.0% |
| Pipeline eval (all) | 1884 | 63.2% | 36.3% | -26.9% | 70.0% | 43.4% | 76.7% | -23.8% |

## Verdict

**Hurts** the serving residual relative to the head-heavy v5 hinge. The T4-covered rows are carrying transferable signal; do not throw them away. A 100k fall-through tranche is not justified on this test.

Money metrics are **holdout T6-bound** (novel merchants, leakage-free) and **pipeline residual** (row-disjoint gold that misses T1–T5). Full holdout / full risk / pipeline-all are **classifier-only** on those files, including rows T4 would catch — not the 80.4% T1–T5-then-hinge pipeline number.

v5 holdout leaf here is **53.8%** vs the published 52.8% on an earlier gold_leaf snapshot; both heads in this table used the current files.

Do not switch serving dumps on this experiment. The next classifier change, if any, is still a retrain on the **full** jsonl (including the +556 T6 packs), not this slice.


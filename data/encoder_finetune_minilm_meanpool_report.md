# Mean-pool MiniLM vs hinge (pooling fix, 2026-08-27)

The first MiniLM run used `BertForSequenceClassification` (`[CLS]` pooling). `sentence-transformers/all-MiniLM-L6-v2` is a **mean-pool** sentence encoder. This retry: frozen encoder + linear head (lr=0.001), then unfreeze (encoder lr=2e-05, head lr=0.0001), one epoch each, batch 64. Train `tuning_train.jsonl` (this run loaded **382,739** rows). Hinge is serving v5 `outputs/distill_models/tfidf_linearsvm_sgd.joblib`. Weights: `outputs/distill_models/minilm_ft_meanpool`. CLS run kept at `outputs/distill_models/minilm_ft_jsonl` (`data/encoder_finetune_minilm_report.md`). Locked v5/v6 not scored.

Frozen MiniLM + logreg (mean pool, 164k jsonl) was **27.6%** holdout leaf. CLS-pool fine-tune was **13.1%** holdout / **17.5%** leftover.

| Cut | n | hinge leaf | mean-pool MiniLM | Δ leaf | hinge gen | MiniLM gen | hinge risk | Δ risk |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Holdout (all, merchant-disjoint) | 1055 | 53.8% | 52.1% | -1.7% | 61.0% | 61.2% | 57.7% | -15.4% |
| Holdout T6-bound | 428 | 57.7% | 53.0% | -4.7% | 64.5% | 63.3% | 60.6% | -18.2% |
| Risk gold (all) | 711 | 80.6% | 62.4% | -18.1% | 85.5% | 70.2% | 86.1% | -17.4% |
| Risk gold T6-bound | 88 | 73.9% | 40.9% | -33.0% | 78.4% | 43.2% | 88.4% | -16.3% |
| Pipeline eval residual (row-disjoint) | 516 | 60.1% | 50.4% | -9.7% | 66.9% | 59.7% | 72.3% | -20.0% |
| Pipeline eval (all, classifier-only) | 1884 | 63.2% | 56.7% | -6.5% | 70.0% | 65.1% | 76.7% | -16.7% |

## Verdict

**Hinge still wins the leftover** after the pooling fix. Char TF-IDF remains the runtime family. Do not serve MiniLM. Proceed to the leftover top-up on hinge.

Money metrics: holdout T6-bound and pipeline residual. Pipeline-all is classifier-only (T4 would catch most of those rows).

Probe val **61.3%**, unfreeze val **72.9%** (head-like val merchants, not the holdout). Train wall-clock **734s**.

Pooling was the bug in the first run: mean-pool holdout **52.1%** vs CLS-pool **13.1%**. Hinge still wins leftover and the risk bar (thin leaves). Do not serve MiniLM.


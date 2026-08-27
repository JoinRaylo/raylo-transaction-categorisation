# Fine-tuned MiniLM vs hinge on the current jsonl (2026-08-27)

Encoder: `sentence-transformers/all-MiniLM-L6-v2` sequence-classification head, **1** epoch, lr=2e-05, batch=64, max length 128. Text is `merchant | description | amt= | direction` (four fields). Train file `tuning_train.jsonl` (**382,739** rows). Hinge dump is `outputs/distill_models/tfidf_linearsvm_sgd.joblib` (**serving v5**, restored after the v5b T6-top-up retrain; this comparison is not vs v5b). Encoder weights: `outputs/distill_models/minilm_ft_jsonl`. Locked v5/v6 not scored. Gambling promote matches the hinge scorer.

Frozen MiniLM + logreg on the old 164k jsonl was **27.6%** holdout leaf. This run fine-tunes the encoder.

| Cut | n | hinge leaf | MiniLM FT leaf | Δ leaf | hinge gen | MiniLM FT gen | hinge risk | Δ risk |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Holdout (all, merchant-disjoint) | 1055 | 53.8% | 13.1% | -40.8% | 61.0% | 22.7% | 57.7% | -55.8% |
| Holdout T6-bound | 428 | 57.7% | 17.5% | -40.2% | 64.5% | 27.6% | 60.6% | -54.5% |
| Risk gold (all) | 711 | 80.6% | 3.0% | -77.6% | 85.5% | 12.5% | 86.1% | -84.2% |
| Risk gold T6-bound | 88 | 73.9% | 6.8% | -67.0% | 78.4% | 6.8% | 88.4% | -83.7% |
| Pipeline eval residual (row-disjoint) | 516 | 60.1% | 17.2% | -42.8% | 66.9% | 25.8% | 72.3% | -66.2% |
| Pipeline eval (all, classifier-only) | 1884 | 63.2% | 11.1% | -52.1% | 70.0% | 22.7% | 76.7% | -74.9% |

## Verdict

**Hinge still wins the leftover.** Char TF-IDF is the right runtime family for this text. Do not switch serving to MiniLM. Proceed to the leftover top-up on hinge.

Money metrics: holdout T6-bound and pipeline residual. Pipeline-all is classifier-only (T4 would catch most of those rows).

Sanity check (not a label-map bug): MiniLM is **53.8%** on the first 400 jsonl rows and **56.0%** on `tuning_val.jsonl` (same merchant-head distribution as training). Holdout / leftover collapse is generalisation, not a wiring error. Frozen MiniLM + logreg (27.6% holdout on the old 164k file) generalised better than this 1-epoch fine-tune.

Risk gold **3%** is the thin-leaf failure: the encoder defaults to `transfer_p2p` / `unclassified_other`. Hinge still clears the 70% risk bar.

Do not overwrite serving dumps with the encoder. One epoch is a caveat; a second epoch would likely raise in-sample accuracy further without fixing novel-merchant leftover (the val set is not merchant-disjoint). A larger encoder (DeBERTa) is not the next step — leftover labels are.


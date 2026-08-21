# TF-IDF classifier v2 -- scored on the clean gold_v2 eval holdout

Retrained on the new tiered training set (`outputs/tuning_train.jsonl`, 164445 rows), scored per-transaction against `data/gold_v2_slm_eval_holdout.csv` (1055 real transactions, zero training overlap) -- the same set the SLM fine-tune will be judged on, for a fair comparison.

**Leaf accuracy: 32.0%**
**General-category accuracy: 37.6%**

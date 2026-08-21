# Sentence-embedding classifier -- scored on the clean gold_v2 eval holdout

Same training data and same linear-model family as the TF-IDF v2 classifier (164445 rows) -- only the text representation changes: `all-MiniLM-L6-v2` (22M params, 384-dim) sentence embeddings instead of TF-IDF character n-grams. Scored per-transaction against `data/gold_v2_slm_eval_holdout.csv` (1055 real transactions, zero training overlap) -- identical to how the TF-IDF classifier and the SLM fine-tune are both judged.

**Leaf accuracy: 27.6%**
**General-category accuracy: 32.5%**

For comparison: TF-IDF classifier v2 scored 32.0% leaf / 37.6% general on the same holdout (`data/distillation_v2_holdout_report.md`).

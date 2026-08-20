# Distillation model bake-off -- trained on accepted production labels

Training data: `production_labels_tranche2.csv` accepted-tier merchants, per-transaction Plaid text (merchant_name + original_description), capped at 150/merchant.

## A_control (hashed ngrams)
- **Head gold set** (1563 merchants): leaf 53.2%, general 59.2%
    - adjudicated_correction: n=4, leaf 0.0%
    - adjudicated_correction+taxonomy_split_20260819: n=1, leaf 0.0%
    - adjudicated_either: n=47, leaf 46.8%
    - adjudicated_equifax: n=56, leaf 25.0%
    - adjudicated_llm: n=211, leaf 39.8%
    - adjudicated_llm+taxonomy_split_20260819: n=5, leaf 80.0%
    - consensus_all_agree: n=1239, leaf 57.1%
- **Tail gold set** (247 merchants): leaf 56.3%, general 63.6%
    - person_like: n=19, leaf 89.5%
    - short_token: n=19, leaf 36.8%
    - top_volume: n=58, leaf 69.0%
    - two_word: n=37, leaf 48.6%
    - uniform_tail: n=57, leaf 52.6%
    - volume_weighted: n=57, leaf 47.4%

## B_tfidf_logreg (bounded vocab)
- **Head gold set** (1563 merchants): leaf 53.4%, general 59.4%
    - adjudicated_correction: n=4, leaf 0.0%
    - adjudicated_correction+taxonomy_split_20260819: n=1, leaf 0.0%
    - adjudicated_either: n=47, leaf 48.9%
    - adjudicated_equifax: n=56, leaf 26.8%
    - adjudicated_llm: n=211, leaf 40.3%
    - adjudicated_llm+taxonomy_split_20260819: n=5, leaf 80.0%
    - consensus_all_agree: n=1239, leaf 57.1%
- **Tail gold set** (247 merchants): leaf 57.5%, general 65.6%
    - person_like: n=19, leaf 94.7%
    - short_token: n=19, leaf 47.4%
    - top_volume: n=58, leaf 69.0%
    - two_word: n=37, leaf 48.6%
    - uniform_tail: n=57, leaf 50.9%
    - volume_weighted: n=57, leaf 49.1%

## C_lightgbm (tfidf + trees)
- **Head gold set** (1563 merchants): leaf 51.6%, general 58.4%
    - adjudicated_correction: n=4, leaf 25.0%
    - adjudicated_correction+taxonomy_split_20260819: n=1, leaf 0.0%
    - adjudicated_either: n=47, leaf 48.9%
    - adjudicated_equifax: n=56, leaf 21.4%
    - adjudicated_llm: n=211, leaf 38.4%
    - adjudicated_llm+taxonomy_split_20260819: n=5, leaf 40.0%
    - consensus_all_agree: n=1239, leaf 55.5%
- **Tail gold set** (247 merchants): leaf 57.1%, general 65.2%
    - person_like: n=19, leaf 94.7%
    - short_token: n=19, leaf 36.8%
    - top_volume: n=58, leaf 67.2%
    - two_word: n=37, leaf 51.4%
    - uniform_tail: n=57, leaf 56.1%
    - volume_weighted: n=57, leaf 45.6%

## Summary
| model | head leaf | head general | tail leaf | tail general |
|---|---|---|---|---|
| A_control (hashed ngrams) | 53.2% | 59.2% | 56.3% | 63.6% |
| B_tfidf_logreg (bounded vocab) | 53.4% | 59.4% | 57.5% | 65.6% |
| C_lightgbm (tfidf + trees) | 51.6% | 58.4% | 57.1% | 65.2% |

## Reference points
- Equifax-trained baseline (ml_baseline.py, wrong label source): 69% head leaf / 30% tail leaf
- Enriched LLM (Sonnet 5): 96.1% head leaf (adjudicated) / 76% tail leaf

**Best on tail (the harder, more representative population): B_tfidf_logreg (bounded vocab)**
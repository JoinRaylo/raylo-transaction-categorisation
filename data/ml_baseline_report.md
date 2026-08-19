# Four-field ML baseline -- evaluation against the gold strata

Trained on 12000-per-subcategory Equifax sample; evaluated on Plaid transactions (35024 txns), modal-voted per merchant.

## Head gold set (shared merchants) (1563 merchants with Plaid transactions found)
| group | n | leaf | general |
|---|---|---|---|
| ALL | 1563 | 69% | 78% |
| adjudicated_correction | 4 | 0% | 50% |
| adjudicated_correction+taxonomy_split_20260819 | 1 | 0% | 100% |
| adjudicated_either | 47 | 77% | 79% |
| adjudicated_equifax | 56 | 61% | 73% |
| adjudicated_llm | 211 | 10% | 51% |
| adjudicated_llm+taxonomy_split_20260819 | 5 | 0% | 20% |
| consensus_all_agree | 1239 | 79% | 83% |

## Tail gold set (unmatched population) (247 merchants with Plaid transactions found)
| group | n | leaf | general |
|---|---|---|---|
| ALL | 247 | 30% | 45% |
| person_like | 19 | 5% | 37% |
| short_token | 19 | 11% | 32% |
| top_volume | 58 | 62% | 78% |
| two_word | 37 | 22% | 30% |
| uniform_tail | 57 | 21% | 35% |
| volume_weighted | 57 | 28% | 40% |

## Reference: enriched-LLM numbers on the same sets
Sonnet 5 head consensus subset: 96.1% leaf (adjudication-corrected). Sonnet 5 tail: 76% leaf / 83% general overall, 90% leaf on top_volume.
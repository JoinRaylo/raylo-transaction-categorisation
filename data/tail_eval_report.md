# Tail evaluation set -- adjudicated gold labels and first model readout

Sampled strings: 260 | gold-labelled: 247 | excluded: context_dependent=9, unsure=4

## Enriched-LLM accuracy against the tail gold set
These are the models' own suggestions scored against the human verdicts on those suggestions, so consensus/haiku/sonnet-verdict rows are correct for the named model by construction -- the informative signal is the override/unclassifiable rate and the per-stratum breakdown.

| stratum | n | haiku leaf | sonnet leaf | haiku general | sonnet general |
|---|---|---|---|---|---|
| person_like | 19 | 84% | 84% | 84% | 89% |
| short_token | 19 | 79% | 68% | 79% | 84% |
| top_volume | 58 | 84% | 90% | 90% | 93% |
| two_word | 37 | 51% | 68% | 70% | 76% |
| uniform_tail | 57 | 56% | 75% | 67% | 81% |
| volume_weighted | 57 | 56% | 68% | 70% | 75% |
| ALL | 247 | 66% | 76% | 76% | 83% |

## Verdict breakdown
consensus_correct=143, context_dependent=9, haiku_correct=9, override=45, sonnet_correct=33, unclassifiable=17, unsure=4

## Context-dependent strings (transaction-level rule candidates)
- u.s. post office
- wise
- sunderland
- hollister co.
- beacon garage
- cheshirewestandche
- chigwell golf club
- cd the bolton wanderers
- bfi
# T6 residual top-up fetch (2026-08-27)

Plaid rows that miss T1–T5 (`our_leaf` tier starts with T6). Labelled in `outputs/t6_residual_topup_sample_reviewed.csv` and ingested 27 Aug with pack 2.

Wrote `outputs/t6_residual_topup_sample.csv` — **414** rows.

| target_leaf | n |
|---|---:|
| salary | 60 |
| benefits_state | 60 |
| refund_received | 60 |
| loan_disbursement | 60 |
| utility_other | 54 |
| investment_trading | 60 |
| gambling_bingo | 0 |
| account_charge | 60 |

`gambling_bingo` returned **zero** T4-miss rows on `\bbingo\b` — remaining bingo volume is already in the dictionary. Keyword nets for `refund_received` / `investment_trading` are noisy vs Plaid native (labelling is the filter). Do not treat `target_leaf` as gold.

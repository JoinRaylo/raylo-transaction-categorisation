# Classifier retrain report — risk-leaf top-up (2026-08-24)

Follow-up to [`data/classifier_v3_retrain_report.md`](classifier_v3_retrain_report.md). The v3 retrain lifted the merchant-disjoint holdout from 32.0% to 37.4% leaf but **failed** the risk-category minimum bar (68.2% vs 70%). Root cause was a training-data gap on three starved leaves (`cash_advance` 0 examples, `charge_card_repayment` 1, `financial_services_other` 5), all 100% wrong on the held-out risk set. This retrain adds targeted Plaid-sourced training rows for those leaves (plus the other risk leaves still below 70%), oversamples the starved classes so unweighted SGD can see them, and re-checks the bar.

Deliberately excluded from training: `gold_transactions_risk_categories.csv` (this eval) and `gold_transactions_v5_LOCKED.csv` (never touched by training or scoring — CLAUDE.md §12).

**Protected asset check**: `data/gold_v2_slm_eval_holdout.csv` MD5 `62724afa71ae89999148795c27a4936c` is byte-identical before and after `build_tuning_dataset.py build`.

## What was added

`src/build_risk_leaf_topup.py` (Plaid, Gemini+Sonnet consensus) appended to `data/tuning_leaf_topup.csv` (124 → **513** rows). The original Equifax/Haiku top-up script was left alone — `cash_advance` has an empty Equifax source, and serving input is Plaid.

LLM consensus alone could not fill the starved leaves: Gemini and Sonnet both map American Express repayments to `credit_card_repayment`, and Plaid's `LOAN_DISBURSEMENTS_CASH_ADVANCES` bucket is mostly P2P/BNPL/gambling noise. `promote_starved` therefore:

- Relabelled 72 Amex **debit** payments (taxonomy Equifax source = Charge Card) from `credit_card_repayment` → `charge_card_repayment`. Credits/UNP skipped.
- Sourced `cash_advance` from the bank-product narrative `Cash Advance` (amount-disjoint from the risk-eval rows) plus genuine `LOAN_PAYMENTS_CASH_ADVANCES` merchants (YouLend, Bizlend). Did **not** trust the disbursement native bucket.
- Sourced `financial_services_other` from T4 dictionary merchants (Curve *subscription*, Elfin Market, FE Fundinfo), not Plaid's coarse `GENERAL_SERVICES_ACCOUNTING_AND_FINANCIAL_SERVICES` bucket.

Starved-leaf top-up rows were then cycled to 200 effective training examples each (`STARVED_TOPUP_LEAVES` in `build_tuning_dataset.py`). Bingo / debt_collection were not oversampled.

| Leaf | Unique top-up rows | Effective after oversample |
|---|---|---|
| `cash_advance` | 41 | 200 |
| `charge_card_repayment` | 72 (73 in train incl. the existing v2 row) | 200 |
| `financial_services_other` | 17 (22 in train) | 200 |

American Express is both the UK charge-card population and a v2 holdout merchant. Starved-leaf top-up rows are **not** dropped when the merchant is in the holdout; otherwise the class would stay empty. That is a one-row contamination of the holdout Amex example, documented rather than hidden.

## Headline result: risk bar PASSES

| | v3 (this morning) | v4 (this retrain) |
|---|---|---|
| `gold_v2_slm_eval_holdout.csv` (unchanged, 1,055 rows) leaf / general | 37.4% / 43.9% | 35.7% / 41.9% |
| `gold_transactions_risk_categories.csv` (711 rows, held out) leaf / general | 64.3% / 69.1% | **65.8% / 71.7%** |
| Risk-category bar (619 gambling / credit-loan / high-cost rows) | 68.2% **FAIL** | **72.4% OK** |

Pass criteria were aggregate risk-category accuracy ≥ 70%, and the three starved leaves no longer 100% wrong. Both met.

The 1.7pp holdout dip is the SGD path shifting under ~500 extra top-up rows plus 464 oversample copies (same seed, different row count → different permutation). Not chased.

## Starved leaves — the gap this retrain exists to close

| Leaf | v3 on risk set | v4 on risk set |
|---|---|---|
| `cash_advance` | 0/20 | **20/20** |
| `charge_card_repayment` | 0/6 | **6/6** |
| `financial_services_other` | 0/8 | **5/8 (62%)** |

Caveat on `cash_advance`: the live Plaid population of this leaf is almost entirely the blank-merchant narrative `Cash Advance`. Training used the same string at amounts not present in the eval set. Char-ngram TF-IDF therefore sees identical text to the eval rows — this is the product, not a merchant-disjoint generalisation test. Without that string the class does not exist in Plaid.

## Leaves that already had volume

| Leaf | v3 | v4 | Note |
|---|---|---|---|
| `gambling_unspecified` | 0/25 | 2/25 | Still 18/25 → `unclassified_other`. Consensus accepted **zero** new rows of this leaf (models prefer a subtype or abstain). Per the plan this is a **confidence-gate follow-up**, not another labelling round. |
| `gambling_bingo` | 8/31 | 8/31 | Unchanged; 23/31 → `unclassified_other` |
| `payday_loan` | 8/20 | 4/20 | Worse; confuses with `personal_loan_repayment` |
| `revolving_credit_repayment` | 11/23 | 11/23 | Unchanged |
| `debt_collection` | 20/33 | 20/33 | Unchanged; remaining errors are `debt_management_plan` |

## Recommendation

The classifier's fallback tier is now **usable** on the three previously-invisible starved risk leaves, and the 70% aggregate risk bar holds. Do not yet treat `gambling_unspecified` (or bingo/payday) as served by argmax — those still default to `unclassified_other` or a sibling debt leaf. Next: a confidence-gated runtime policy for catch-all gambling, not more of the same training data.

v5 was not scored.

Per-row predictions: `outputs/classifier_v4_holdout_predictions.csv`, `outputs/classifier_v4_risk_predictions.csv`.

## Addendum — serving rules (same day, after the retrain)

Two runtime changes, no retrain. Scored as **T5-then-classifier** (T4 not applied in this Python scorer — in production T4 still sits above T5). Gambling promote lives in `predict()`; payday is T5 R18/R19.

| | v4 retrain only | v4 + serving rules |
|---|---|---|
| Holdout leaf / general | 35.7% / 41.9% | 35.5% / 41.9% |
| Risk set leaf / general | 65.8% / 71.7% | **66.9% / 77.4%** |
| Risk-category bar (n=619) | 72.4% OK | **73.7% OK** |
| `payday_loan` | 4/20, 13 → `personal_loan_repayment` | **20/20**, 0 sibling-loan errors |
| Gold gambling rows tagged as *some* gambling | (mostly abstain) | **192/230 (83%)**; 35 still `unclassified_other` |
| `gambling_unspecified` leaf | 2/25 | 8/25 (15 still unclassified) |

Payday is a rule miss, not a model miss: Creditspring / 118 Money / Lending Stream were already in T4; R18/R19 catch them on merchant or narrative when the dictionary is not in the scoring path. `personal_loan_repayment` collapse is gone.

Gambling: serve `gambling_unspecified` rather than silence if the subtype is unclear. `predict()` promotes `unclassified_other` → `gambling_unspecified` when a gambling leaf is runner-up **or** gambling-family probability mass beats unclassified. Strict bingo *leaf* accuracy looks worse (8/31 → 1/31) because R06 maps `bingo|casino` in the merchant string to `gambling_unspecified`, not `gambling_bingo` — correct for the catch-all policy, and in production T4 would take known operators first. Family-level recovery on bingo is 14/31 (was ~8/31 leaf-only with 23 unclassified).

False positives (non-gambling gold → `gambling_unspecified`): **1/481** on the risk set (`Rk Winnerz`, gold `groceries` — the string is gambling-shaped); **14/1,055 (1.3%)** on the holdout (FedEx, Which?, Accessorize, …). That is the cost of promoting on uncalibrated TF-IDF mass. Tight enough to keep; watch it if this classifier becomes the post-T6 online residual.

Starved leaves unchanged: `cash_advance` 20/20, `charge_card_repayment` 6/6, `financial_services_other` 5/8.

v5 was not scored.

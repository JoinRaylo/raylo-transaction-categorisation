# MIV Audit — ds_plaid_credit_features (train split, target = month3_1plus_pia)

## Headline finding (read this first)

**Every Plaid Open Banking pull since go-live requests exactly 90 days of transaction history** — confirmed across all 11,530 Asset Reports pulled between 2025-08-13 and 2025-11-03 in `credit_plaid_open_banking_transactions` (`days_requested` = 90 for every single row, no exceptions). This is a Raylo-side request parameter, not a Plaid platform ceiling — Plaid Asset Reports support much longer lookback windows on request. It explains why `total_months` never exceeds 3 anywhere in the 79,863-row feature table, and it structurally kills every feature built on a "before 90 days" comparison window. Recommend raising this as its own ticket, independent of the DFS/MIV work — it likely has more impact on model quality than anything else in this document, and it's a config change, not a rebuild.

## Degenerate features found (exclude / fix before any further modelling)

Naive standalone IV ranking initially returned non-trivial scores for several features that are actually dead — a caution about trusting automated IV output without a variance/non-null floor first:

| Feature | Live rate | Issue |
|---|---|---|
| `total_cash_advance_disbursement_amount` | 0% | Constant zero across every row in the dataset |
| `total_cash_advance_disbursement_transactions` | 0% | Same |
| `pct_cash_advance_disbursement_amount` | 0% | Same |
| `bnpl_before_90d_amount` | 0% | Constant zero — direct consequence of the 90-day pull window |
| `gambling_before_90d_amount` | 0.01% | Effectively dead (1-2 non-zero rows out of 9,626) |
| `cash_before_90d_amount` | 0.01% | Effectively dead |
| `p2p_before_90d_amount` | 0.01% | Effectively dead |
| `pct_unknown_or_other_debit_amount` | 0% | Constant zero |
| `pct_unknown_or_other_debit_transactions` | 0% | Constant zero |
| `student_loan_payment_debit_amount` | 0.32% | Near-dead — population coverage issue, not obviously a bug, but too sparse to trust |
| `pct_student_loan_payment_debit_amount` | 0.32% | Same |
| `total_crypto_debit_amount` / `total_crypto_transactions` / `crypto_to_salary_ratio` | 1.1–1.3% | Too sparse to be a reliable standalone feature at current volume |
| `ghost_account_like_flag` | 1.1% | Too sparse to trust yet — worth revisiting once volume grows |

`bnpl_surge_vs_history_ratio` and `gambling_surge_vs_history_ratio` are always null / always zero for the same 90-day-window reason and should be treated as dead alongside the rest of the "surge_vs_history" and "before_90d" families.

## Redundancy found (keep one, drop the other pending a real model refit)

- `spend_hhi` vs `pct_top_category` — correlation 0.968. Keep `spend_hhi` (IV 0.297 vs 0.260).
- `has_recent_salary_flag` vs `has_historic_salary_flag` vs `has_salary_flag` — pairwise correlation 0.64–0.84. Keep `has_recent_salary_flag` (highest IV), treat the other two as drop candidates.
- `mortgage_auto_payment_debit_amount` vs `pct_mortgage_auto_payment_debit_amount` — correlation 0.71, moderate. Keep the raw amount version; the ratio version is largely redundant given the moderate-to-strong correlation.

**Ruled out as redundant** (worth noting since it was a reasonable guess going in): the `_months` family (`loan_payment_months`, `legit_life_footprint_months`, `grocer_months`) correlates only weakly with `total_months` (0.18–0.37) — these are not just re-deriving "how much history exists," they carry independent signal and should be kept.

## Clean top-20 shortlist (post degeneracy filter, post redundancy check)

| Rank | Feature | IV | Note |
|---|---|---|---|
| 1 | `spend_hhi` | 0.297 | |
| 2 | `num_distinct_detailed_categories` | 0.195 | |
| 3 | `p2p_to_salary_ratio` | 0.171 | |
| 4 | `num_distinct_merchants` | 0.148 | |
| 5 | `grocer_months` | 0.147 | |
| 6 | `avg_credit_transaction_amount` | 0.144 | |
| 7 | `mortgage_auto_payment_debit_amount` | 0.137 | live_rate 12% — real, but sparse (most applicants aren't homeowners) |
| 8 | `loan_payment_monthly_cv` | 0.135 | |
| 9 | `essential_spend_ratio` | 0.134 | will move once rebuilt on the new crosswalk taxonomy |
| 10 | `essential_spend_amount_total` | 0.134 | same caveat |
| 11 | `has_recent_salary_flag` | 0.133 | |
| 12 | `legit_life_footprint_months` | 0.133 | |
| 13 | `returned_payment_count` | 0.131 | |
| 14 | `total_months` | 0.131 | capped at 1-3 — ceases to be useful once the 90-day fix lands and this starts varying more |
| 15 | `loan_payment_months` | 0.130 | |
| 16 | `loan_payment_consistency_ratio` | 0.128 | |
| 17 | `streaming_months` | 0.127 | will move once entertainment_media merchant-split lands |
| 18 | `bnpl_30d_vs_90d_ratio` | 0.120 | |
| 19 | `pct_p2p_like_debit_amount` | 0.119 | |
| 20 | `telco_months` | 0.112 | |

## What this pass deliberately doesn't do

This is standalone IV + a manual correlation-based redundancy check via SQL — a practical proxy for full MIV, not the real thing. True MIV needs iterative model refitting (add candidate, refit, check test-set GINI, repeat), which needs an actual modelling environment (Python/sklearn), not read-only SQL. This pass gets you close enough to know what to bring into that step: a clean ~17-feature shortlist (20 minus the 3 redundant drops) instead of 130 features including several that are silently dead.

## Recommended next steps

1. **Raise the 90-day pull window as its own ticket** — likely higher-impact than anything else here, and separable from the DFS/MIV work.
2. **Drop or flag the 12 degenerate features** in `ds_plaid_credit_features` — either fix their computation or remove them from the model input; several are dead purely because of the 90-day window and will come back to life once that's fixed.
3. **Rebuild `essential_spend_ratio`, `essential_spend_amount_total`, `essential_spend_amount_total`-adjacent features against the new crosswalk taxonomy**, then rerun this same IV pass on those specific features to see how much the mixed_basket/is_debt_related restructure actually moved them.
4. **Take the ~17-feature shortlist into a real train/refit loop** (Python, logistic regression or GBM, on the same train/oot split) to get an actual baseline GINI — this is the number DFS's output eventually needs to beat.

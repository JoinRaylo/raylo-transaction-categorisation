# Thin risk-category leaves — live volume (2026-08-24)

The risk-category gold set left 7 leaves with fewer than 5 human-accepted rows. Question: sourcing gap, or genuinely rare in the live population?

**Rare in Plaid, not a taxonomy mistake.** Keep the leaves (low volume is not a prune criterion — `overdraft_unarranged` is the genuine Equifax distress marker at 126 transactions). Do **not** chase another Plaid LLM labelling round, and do **not** put Equifax rows into the Plaid gold eval.

Equifax dump volume **is** usable as **categoriser training** where the raw `Description` is the same kind of bank-narrative text the runtime model will see on Plaid. Sampled 2026-08-24:

| Leaf | Gold rows after review | Equifax dump | Equifax narrative usable for training? | Plaid T6 path |
|---|---:|---:|---|---|
| `balance_transfer` | 2 | 51 (T3 primary `Balance Transfers`) | **Yes, with a filter** — some rows are literally `BALANCE TRANSFER REQUEST`; others are empty/`GB` | none |
| `loan_repayment_dd` | 0 | 1,814 (`Direct Debit Repayments`) | **No** — 100% credits, text `DIRECT DEBIT PAYMENT - THANK YOU` under primary `Repayments`. That is the *lender's* view of a DD arriving, not a current-account debit to a loan. Copying these would teach the wrong pattern. | none |
| `loan_disbursement` | 0 | no Equifax mapping | n/a — Plaid-only, and `LOAN_DISBURSEMENTS_*` is noisy | `LOAN_DISBURSEMENTS_*` ~10k, noisy |
| `cash_advance_fee` | 0 | 562 (`Cash Advance Fees`) | **Yes** — `CASH ADVANCE FEE` / `CASH FEE` | none (Plaid's fee bucket maps to `overdraft_arranged`) |
| `overdraft_unarranged` | 0 | 126 (`Unarranged Overdraft`) | **Yes** — `UNARRANGED OVERDRAFT CHARGES {dates}` | none (2 keyword hits) |
| `account_misuse` | 0 | 86 (`Account Misuse`) | **Mostly no** — debit descriptions are empty/`GB`; Equifax's subcategory is the only signal. A handful of credit "admin fee" narratives are not this leaf's intent. | none |
| `money_management_service` | 1 | 123 (`Money Management`) | Weak — modal vendor is Safecharge (a processor). Gold review already mapped similar StepChange hits to `debt_management_plan`. | none |

## Two different jobs

1. **Categoriser (TF-IDF / waterfall)** — Equifax `Description` → our leaf, for the rows above marked yes. That is how Plaid ever gets these mechanism/fee leaves at runtime; Plaid does not emit Equifax's fee/misuse subcategories, and T4 cannot invent them from a merchant string.
2. **Experiment 3 risk model** — Equifax *and* Plaid *transactions* both mapped through the taxonomy, then persistence/ratio features → PIA. That uses the Equifax volume even when the categoriser never sees those fee leaves on Plaid, because Equifax history still moves `priority_debt_*` / distress features for Equifax-era training rows.

`loan_disbursement` remains the Plaid-only gap.

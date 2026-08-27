# T6 residual top-up fetch 2 (2026-08-27)

Keyword/entity nets only (no Plaid native as the recall net). Previewed in BQ, then filtered in Python so the *source* has to look like the target leaf. Labelled, patched, and appended 27 Aug. Classifier dumps not retrained.

Wrote `outputs/t6_residual_topup2_sample.csv` — **142** rows. Labelled in `outputs/t6_residual_topup2_sample_reviewed.csv`. Three patches after review: row 9 `KARIM A M` FPS → `transfer_p2p`; rows 67–68 Schneefangsysteme invoice/credit-note inflows → `income_other_unspecified`. Appended with pack 1 on 27 Aug (`src/append_t6_residual_topup.py`).

## Why not Plaid natives

Pack 1 used Plaid detailed category (e.g. `INCOME_SALARY`, `OTHER_UTILITIES`) as the fetch net. After labelling, most of those nets were the wrong leaf (personal FPS as salary, waste as utility, cashback as refund). Pack 2 requires a narrative/entity token first; Plaid native is stored only as evidence.

## Nets and post-filters

| target_leaf | n | include | dropped before keep |
|---|---:|---|---|
| salary | 40 | `\b(salary\|payroll)\b` credits, T4-miss | Salary Finance / SF advance; payroll/salary advance products; `no salary`; expenses memos; \|amount\| < £50 |
| salary_gig | 24 | Roofoods Limited / Stuart Delivery credits ≥ £15 | tiny credits; entity cap 12 each |
| refund_received | 6 | rebate / credit note / overpayment | tax rebate; UNP; Slack/FX `VRATE` savings rebates; personal-name overpayments |
| loan_disbursement | 38 | Moneyboat / Lending Stream / Salad Money / Creditspring advance / NatWest Boxed loan | savings withdrawal; entity caps |
| utility_other | 4 | Homebox / Leep / Glide student / heat network | Ourtaap / waste (none hit) |
| account_charge | 30 | Tide fee / SERVICE CHARGES / TOTAL CHARGES | unpaid / N-S TRN / Non-GBP; entity caps |

BigQuery `REGEXP_CONTAINS` uses the pattern as a GoogleSQL raw string — do **not** double-escape `\b` / `\s` or salary/payroll matches nothing (measured: quoted `\\b` → 0 rows; unquoted `\b` → thousands).

## Spot-check (not gold)

**Likely on-target:** Roofoods/Stuart gig credits; Moneyboat / Lending Stream / Salad / Creditspring advance / NatWest Boxed £15k; Tide per-txn fees and bank SERVICE/TOTAL CHARGES; most `SALARY`/`PAYROLL` BACS from named employers (Wincanton, Caretech, Home Office, Parasol umbrella, Citizens Advice, …).

**Worth a second look when labelling:**

- Salary memos that are a **person’s name** + SALARY (`MR RAVITHAS`, `KARIM A M`, `JOSEPH EATON TRADI`, `NICKY SALARY`) — could be PAYE or a labelled FPS.
- `BLACKTAX RADIO TAX PAYROLL` — taxi radio circuit; still payroll-shaped.
- Refunds are **scarce** after the personal/FX drops. Kept: EDF energy rebate, Vivisol/Dolby medical rebate, Notion Mastercard rebate, Stable Vehicle rebate (£1,360), two Schneefangsysteme **credit notes** (B2B; only keep if this applicant is that customer).
- `Glide Student & Reside` £25 — T6 native is `rent`; gold v2 labelled a same-merchant different-month row `utility_other`. Bills-inclusive student housing; confirm leaf.
- Leep Networks — T6 says `energy` or even `personal_loan_repayment`; they are a heat/utility network. Homebox T6 is `business_services`.

## Still thin after this pull

True `refund_received` off T2 (`refund`/`refunded` never stay T6-bound). `utility_other` that is not waste and not already T4. Isolated `account_charge` that is not Tide/service-charge boilerplate.

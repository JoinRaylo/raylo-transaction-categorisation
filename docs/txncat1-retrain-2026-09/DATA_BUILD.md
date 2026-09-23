# TxCat-1 retrain: protected training data (2026-09-23)

Built under the frozen [acceptance plan](ACCEPTANCE_PLAN.md) and the v2 protected
release: the 3,295-row benchmark membership. The aggregates are in
[`data-build.json`](data-build.json). The rows themselves, with their IDs, stay in
ignored `outputs/`.

| Input | Old | Rebuilt | How |
|---|---:|---:|---|
| MLM pretraining corpus | 21.5M sentences, unscreened | 20,961,713 | [protected corpus](../benchmark-implementation/pretrain-guarded-2026-09-23/README.md) |
| Stage-1 consensus labels | 404,982 texts | 262,041 | clean-witness recovery; staging rules override 12,370 LLM labels; conventions change about 540 |
| Tier B (merchant-level) | ~381k rows from tranche-4 labels | 441,761 rows | fresh fetch through the linked chain (88,102 merchants); labelled by the staging bundle's rules, T1–T5 only; 38,276 protected rows excluded |
| Tier A (gold_transactions train rows) | 3,956 | **0** | dropped (decision 1) |
| Credit top-up | 27,979 | 15,164 | exactly-one-transaction recovery; about 8,000 rows have no traceable customer |
| Risk top-up | 4,998 | 2,955 | same |
| Leaf top-up | 1,426 | 549 | same; the Equifax-sourced rows cannot be matched |
| **Stage-2 train / validation** | 414,400 / 5,000 | **393,353 / 5,000** | 266 leaves, 397,954 distinct transactions |

## Decisions applied

- **Rules override LLM labels, not human ones.** Where the staging rules decide
  a row, LLM and merchant-level labels take the rule's leaf. That changed 12,370
  consensus rows and 202 top-up rows. Carlos's own labels are kept; the 8 rows
  where they conflict with a rule are listed in `data-build.json`.
- **The shared conventions** (`txncat-label-conventions-2026-09-23-v1`) apply to
  every source.
- **Fail closed on identity.** A row is dropped when:
  - it has no traceable customer;
  - its key matches several customers' transactions;
  - it belongs to a protected event, account or customer;
  - its account links to more than one customer across sources (1 account,
    19 rows).

  A transaction present in both Tier B and a top-up keeps the top-up label
  (23 rows).

## Verification

- `verify_tuning_export` passed on the export. That check covers the signed
  receipts, the row manifests, membership coverage and the Tier-B fetch receipt.
  The training scripts run it before any fit.
- The consensus parquet verified for `distillation`.
- The encoder corpus verified on all 21 shards.
- 286 research tests pass.

## What this does not do

No model has been trained. Training (encoder, then both stages, three seeds) is
the next step. It is followed by the acceptance plan's evaluation once the
3,295-row benchmark labels are final.

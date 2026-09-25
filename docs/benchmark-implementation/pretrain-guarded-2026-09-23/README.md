# Protected pretraining corpus for the TxCat-1 encoder (2026-09-23)

Carlos asked for the MLM encoder to be rebuilt so it never sees benchmark
customers. The old corpus (`pretrain_corpus_full.parquet`, 21.5M sentences) had no
exclusions at all. This rebuild keeps its sources, sentence format and amount
buckets, and protects the pinned release: the 3,295-row benchmark membership.

| | Old corpus | Protected corpus |
|---|---:|---:|
| Sentences | 21,524,807 | **20,961,713** |
| Plaid / Equifax | 1.6M / 20.0M | 1,014,626 / 19,947,087 |
| Credit share | 23.7% | 24.0% |

## How rows were excluded

- **Plaid.** BigQuery excludes rows before aggregation. Customers missing from a
  row are resolved through checkout → user → customer.

  | Reason | Rows |
  |---|---:|
  | Protected transaction | 423 |
  | Protected account | 167,945 |
  | Protected customer | 48,781 |
  | No resolvable customer (fails closed) | 1,625,348 |
  | Kept | 2,437,210 |

- **Equifax.** 142 rows whose reference is a protected user's checkout are
  excluded; 73.2M rows are kept before sampling. The Equifax dump does not link to
  Raylo customers: 0 of its 99,164 references match any Raylo user or customer,
  and 94 match a checkout. So for this source only those linked references and
  exact text can be excluded (see limitations).
- **Exact-text screen.** 2,710 sentences whose (direction, merchant, description)
  equals a protected transaction's were dropped: 1,585 Plaid and 1,125 Equifax.
- **Training-data protection gate.** Each of the 21 shards' representative rows
  passed `eval_protection.apply` (`domain_pretraining`) with zero further
  exclusions, then received a signed artifact receipt.
  `pretrain_mlm.py` now verifies every shard's receipt and manifest digest before
  reading, and never reads the old corpus. It passed on all 21 shards.
- **Pre-flight table check.** Before any query ran, the BigQuery table
  `txncat_eval_protected.benchmark_protected_3295_v1` was checked against the
  pinned membership: rows, accounts, customers and the sorted event-key digest.

`manifest-aggregate.json` holds the aggregate manifest (counts, digests, SQL
hashes; no rows). The shards themselves stay in ignored `outputs/`.

## Limitations

- Equifax customer IDs are a separate namespace, so customer-level protection
  for Equifax is limited to the linked references plus exact text.
- Plaid rows without a resolvable customer are dropped rather than trusted. That
  reduces Plaid coverage by about 40%.
- The encoder has not been retrained yet. That is the first step of the retrain,
  under the predeclared acceptance plan.

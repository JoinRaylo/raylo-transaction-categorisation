# B01 audit evidence and reproduction

Start with [REPORT.md](REPORT.md). This is the initial historical-exposure/source-ID
audit supporting master-v1. It does not create or certify a new benchmark.

| Evidence | Contents |
|---|---|
| [lineage_status.json](lineage_status.json) | Stage-by-stage evidence status, recorded dependencies and explicit unknown history |
| [validation.json](validation.json) | Evidence hashes, query receipts, count reconciliation and documentation checks |
| [local_inventory.json](local_inventory.json) | 95 available/missing-file records, hashes, schemas, counts, bundle-source comparisons and parent metadata |
| [local_overlap.json](local_overlap.json) | Exact sentence and hinge-input overlap for all transaction-capable permitted evaluation tasks; two merchant-only tasks are excluded from head-input claims |
| [independent_verification.json](independent_verification.json) | Independent Arrow recount and reconstruction of capped/oversampled inputs through retained epochs |
| [corpus_gcs_verification.json](corpus_gcs_verification.json) | Preserved full-corpus GCS generation, size and CRC32C comparison |
| [warehouse_profile.json](warehouse_profile.json) | Seven aggregate query outputs; counts are serialized as returned by `bq` |
| [warehouse_receipts.json](warehouse_receipts.json) | Query/result hashes, job IDs, timestamps and bounded scan statistics; full query plans remain in the private working audit |
| [source_metadata.json](source_metadata.json) | Live warehouse schemas, sizes, modification times and corpus object metadata |
| [source_code_provenance.json](source_code_provenance.json) | App/dbt/OB-transformer source hashes, manifest provenance and official identifier-semantics references |

No raw narratives, customer/account IDs or per-example fingerprints are published.
Counts are over input signatures or rows as identified in the report; they are not
all counts of unique economic events. The local audit opens only the existing
permitted evaluation inventory and never locked/retired evaluation files.

## Local reproduction

Use the research Python environment, which already contains NumPy and PyArrow.
The independent verifier also uses pandas. From the app monorepo root:

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/carlosnoblejesus/Repos/raylo-transaction-categorisation/.venv/bin/python \
  apps/ob-txn-categoriser/research/benchmark-audits/b01-2026-09-15/audit_local.py \
  --app "$PWD" \
  --research /Users/carlosnoblejesus/Repos/raylo-transaction-categorisation \
  --output /private/tmp/txncat-b01-replay

PYTHONDONTWRITEBYTECODE=1 /Users/carlosnoblejesus/Repos/raylo-transaction-categorisation/.venv/bin/python \
  apps/ob-txn-categoriser/research/benchmark-audits/b01-2026-09-15/verify_local.py \
  --app "$PWD" \
  --research /Users/carlosnoblejesus/Repos/raylo-transaction-categorisation \
  --audit /private/tmp/txncat-b01-replay
```

The helper loads reviewed parsing/sampling function definitions from pinned research
source without importing the training modules or their side effects. It preserves
CSV embedded line endings and compares mask-filtered counts with retained metadata.
It does not fit or load model weights. Full-corpus scanning needs the preserved local
Parquet files; no new download or extraction is performed by the local scripts.

## Warehouse reproduction

`run_warehouse.py` uses existing `bq` authentication, project `raylo-production`,
location EU and the fixed SELECTs in `sql/`. Its default is validation/dry-run only:

```sh
python3 apps/ob-txn-categoriser/research/benchmark-audits/b01-2026-09-15/run_warehouse.py \
  --output /private/tmp/txncat-b01-replay/warehouse
```

Add `--execute` to run the aggregate queries, or `--only <query_name>` to narrow the
run. Each query must validate as SELECT and remain within the 20 GB cap. This uses
ordinary temporary BigQuery query results; it does not build or update dbt tables.

Re-running against live tables is a **new dated profile**, not exact reconstruction
of the old warehouse state. Preserve this report and its archived outputs; do not
overwrite their timestamps or scores. Source dates, business scope and recent-window
bounds are explicit in the SQL. Final benchmark extraction needs its own immutable
snapshot and reservation controls.

The app and research copies of this directory are mirrored byte-for-byte. The
app's root README and the research README/CLAUDE context link to the audit.

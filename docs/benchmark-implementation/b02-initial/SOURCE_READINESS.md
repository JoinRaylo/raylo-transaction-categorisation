# Source readiness before curation

This is an interpretation of the immutable [15 September B01 profile](../../benchmark-audits/b01-2026-09-15/REPORT.md),
not a new live extract or an eligible benchmark count.

| Item | Evidence | Remaining work |
|---|---|---|
| Current Plaid source | 35,553,295 rows | Freeze source/event/as-of bounds and consumer/business eligibility |
| Existing-ID user/customer linkage | 20,084,276 rows linked (56.49%); 15,469,019 unresolved (43.51%) | Resolve or explicitly restrict population; do not invent customer IDs |
| Report identity | 428,949/428,949 stored report IDs null | Parser source fix implemented/tested; deployment and reconciled historical repair still required |
| Repeat observations | 906,111 transaction IDs appear in multiple recent requests | Preserve staged request observations and deduplicate by governed event/alias identities |
| Historical input proxy | 14,470,951 current rows match the old Plaid projection | Useful exposure flag, not proof of the same event or full ancestry coverage |
| Historical event/customer lineage | Missing from many learning files | Scoped prospective proof or conservative identity reconstruction; unresolved stays unknown |
| Currency/pending/Item/alias fields | Incomplete flattened transaction schema | Design source export that preserves original transaction context and provenance |
| Actual per-view eligible counts | **Not yet computed** | Identity evidence + complete scoped indexes + immutable source snapshot required |

Do not multiply percentages to estimate eligibility. Do not report unknown counts
as zero, and do not treat the linked 56.49% as a representative sample of everyone.
No raw customer rows, fresh benchmark memberships or labels were exported in this
increment. Synthetic fixture counts demonstrate policy behaviour only.

## Report-ID correction

`apps/payload-extractor/src/payload_extractor/parsers.py` now reads
`report.asset_report_id`, alongside the existing report-level metadata, and emits
one report record before iterating Items. Empty reports retain their identity;
multiple Items do not multiply report rows; malformed report bodies are ignored.
There is no fallback to the incorrect item-level field. Account and transaction
parsing and the report table schema/merge keys remain unchanged.

Official response shape: [Plaid Assets API](https://plaid.com/docs/api/products/assets/).
Tests use synthetic standard-shaped responses and the existing parser suite; no new
raw customer payload was retrieved for this fix. Deployment has not occurred.

Replaying old files will create report-ID-bearing rows alongside existing null-key
rows unless migration reconciles them. Plan that repair by external request and
verified report ID; preserve legitimate multiple reports per request. Do not blindly
append a backfill and count both versions. Validate representative payload shapes,
coverage, counts, duplicate keys and downstream consumers before deploying/backfilling.

## Next deliverable

Build a private, immutable candidate-source export retaining observation/event,
account/customer, report/request/as-of provenance and original API-visible fields.
Import the B01 exposure sources into indexed snapshots with truthful coverage flags;
complete missing projections and legacy memberships without opening locked labels.
Then implement B03 durable reservations, alias/key migration and signed receipts,
and B04 checks in every consumer and promotion path. Only after those gates should
the separate 500-row annotation pilot be reserved and sent for independent labelling.

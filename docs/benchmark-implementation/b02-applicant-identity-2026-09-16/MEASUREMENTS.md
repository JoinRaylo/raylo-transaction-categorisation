# Bounded applicant identity measurements

This is an aggregate-only result for the fixed 49-checkout cohort. The retained links extract contains 99 assessments/checkouts. Its 49 rows without user linkage define this frozen cohort; the current query does not resample or drop absent source records.

| Measure | Count |
| --- | ---: |
| Selected checkouts / checkout_customer_info records | 49 / 49 |
| Checkouts with nonblank persisted `canonical_email` | 49 |
| Checkouts without `user_id` | 49 |
| Direct user/customer matches | 0 |
| Canonical-email matches to known customers | 0 |
| Email matches with exactly one candidate / multiple candidates | 0 / 0 |
| Missing / repeated checkout source rows | 0 / 0 |
| Missing / repeated checkout-customer-info source rows | 0 / 0 |
| Checkouts with zero customer candidates | 49 |
| Agreement/conflict between direct and email identity | 0 / 0 (no direct matches; this is not a validation agreement result) |

The query read four raw Airbyte tables with latest-per-primary-key selection using `updated_at`, `_airbyte_extracted_at`, raw ID, and deletion filtering. It returned aggregates only and compared exact persisted canonical email values; no owner normalization was applied. Approximately 1.327 GB was billed.

These results are scoped to the fixed cohort and are not a population estimate. The latest-row ordering is a current ingestion-state approximation, not a reconstruction at the original assessment time or an attestation of deployed backend code. Conflicting source versions and the full CDC lifecycle have not been certified. No other anonymous checkouts were email-joined. The known-customers query only tests the available customer set, so zero matches does not prove an email is unique or never exposed elsewhere. The original 38,498 distinct account/transaction events across 39,110 observations remain unresolved in the broader audit. Alias, ancestry, reviewed-family, B03 and B04 gates remain pending.

The exact query, runner hashes, execution time, bytes processed/billed and source metadata before/after execution are retained in [executed_receipt.json](executed_receipt.json). The metadata was unchanged during the final query. See [RUNNING.md](RUNNING.md) for reproduction and [verification.json](verification.json) for independent checks.

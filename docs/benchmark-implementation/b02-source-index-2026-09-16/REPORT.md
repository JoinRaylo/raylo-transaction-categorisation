# Source preservation and indexed exposure, 16 September 2026

The raw Taktile/Plaid source can provide the fields missing from the current
flattened tables. A private engineering extract now preserves those fields and
their source identity. This substantially improves source readiness; historical
customer separation and complete exposure coverage are still unresolved.

## Source snapshot

The SELECT reads `raylo-production.airbyte_raylo_prod_no_cdc.external_requests`
with **both ingestion and request creation bounded to 15 September 2026 UTC**.
It chooses the latest observed row per request within those bounds, selects up to
100 requests by a fixed salted SHA256 ordering, and retains all their Plaid report
transaction observations. Existing assessment → checkout → user → customer joins
are grouped before use and only unambiguous IDs are returned. Those joins reflect
the query-time warehouse state, not a reconstructed historical as-of customer map.

The query projects only relevant Plaid fields and existing linkage IDs in BigQuery;
it does not export complete applicant/credit payloads or customer-name, address and
balance fields. Transaction narratives remain sensitive and private.
The SELECT dry run estimated 11,511,988,946 bytes, below the enforced 20 GB cap;
execution processed the same amount. No warehouse/GCS tables or objects were written
apart from BigQuery's normal temporary query result. Before/after source metadata
etags agree. Private outputs have owner-only directories/files and content hashes.

| Measure | Observed count |
|---|---:|
| Request observations selected | 100 |
| Distinct report IDs | 99 |
| Transaction observations | 78,537 |
| Distinct `(Plaid, account_id, transaction_id)` events | 77,925 |
| Additional repeated observations | 612 |
| Accounts | 124 |
| Linked users / customers | 48 / 48 |
| Observations with unique user and customer | 39,164 |
| Observations lacking that linkage | 39,373 |
| Business-checkout observations | 5,736 |
| Observations with unknown business scope | 379 |
| Pending observations | 377 |
| Blank-merchant observations | 29,948 |

Every extracted observation has original report ID, report-generation timestamp,
Item/institution ID, account/event ID, amount, transaction currency and a boolean
pending field. Account/transaction currencies agree throughout this sample.
`pending_transaction_id` is present but null for all 78,537 observations; this
does **not** prove pending/posted alias history is complete. No account is linked
to multiple users/customers within this sample, but reconnect/person-wide aliases
are not resolved by that check.

The event-count view selects the latest report/request observation deterministically
and reports content conflicts rather than treating retries as fresh transactions.
No conflicting contents were found for repeated events. All original observations
remain in the private snapshot. Event dates span **16 March–15 September 2026**:
a newly retrieved report is not automatically a set of new economic events.
Distinct events include 21,474 credits, 56,451 debits and 29,643 blank merchants.

These are **engineering-sample counts**, not population estimates or eligible
benchmark sizes. Sampling requests weights frequent assessments differently from
sampling customers or transactions. No category labels or model predictions were
created; category coverage and benchmark accuracy are not assessed here.

## Input-presence index

The private SQLite index stores versioned HMAC fingerprints with source provenance.
It hashes each preserved source before and after a bounded-memory build and checks
the declared row count before publishing the completed database. Publication is
exclusive, partial builds are rejected, and reads verify the expected database
digest and HMAC key. A different key with the same key ID is rejected.

| Preserved input source | Indexed rows | Projections |
|---|---:|---|
| Full MLM corpus | 21,524,807 | Full transformer sentence |
| Vocabulary-extension prefix of that same corpus | 1,000,000 | Full transformer sentence |
| Consensus distillation source | 404,982 | Sentence and hinge text/numeric input |
| Current tuning source | 414,400 | Sentence and hinge text/numeric input |
| Selection-validation source | 5,000 | Sentence and hinge text/numeric input |

The vocabulary prefix overlaps the full corpus; these counts must not be summed as
distinct transactions. The consensus/tuning sources are conservatively indexed in
full, including rows a particular classifier recipe might filter or sample out.
Their presence establishes preserved input exposure evidence, not that every row
was consumed by the selected model. Tuning also records feature-mask/statistics use.

The index uses the existing versioned B02 head projections, including the retained
float32 amount → float64 `log1p` → float32 numeric path. For source transactions,
null description falls back to transaction name exactly as serving does; an empty
description remains empty. Missing currency or pending values are never invented
to construct an API row. This is input fingerprinting, not API invocation.

Full sentences alone match the MLM snapshot for **21,367 of 77,925 distinct sampled
events (27.42%)**. That is allowed evidence in the representative view, subject to
event/group separation. It disqualifies these exact inputs from a strict unseen-input
view. The remaining 56,558 are **not proven unseen**. See `source-profile.json` for
all per-source projection counts; matches across sources overlap.

Verification rechecks 40 historical overlap counts against the B01 audit, covering
five permitted development sets and all indexed source/projection combinations.
The first build revealed ten validation/consensus hinge mismatches because an
adapter selected cleaned rather than retained raw text. That private build was
discarded as evidence, the adapter was corrected and regression-tested, and the
index was rebuilt. Final evidence refers only to the corrected build.

## Limits and next work

The full 48-token transformer projection, effective sparse-vector collisions,
near-duplicates, complete historical dictionaries/rules/prompt evidence, reviewed
merchant-family mappings, legacy protected membership and historical event/customer
identity are **not fully indexed**. Neither missing history nor unmatched input is
converted into a claim of no exposure. Public-base merchant knowledge is outside
the controlled-lineage novelty claim. The aggregate profile therefore returns
`certified_benchmark_rows: null` and `authorizes_consumption: false`.

1. Reconcile customer/account/event identities across the retained historical
   sources, including pending/posted and reconnected-account aliases. Document
   irrecoverable linkage explicitly and define the admissible source population;
   do not quietly present the linked half as representative of all applicants.
2. Complete the remaining effective-input and controlled-family exposure indexes,
   with immutable, scoped coverage evidence and protected legacy membership exports
   that do not expose locked labels. Re-profile the three views on a frozen source
   window before deciding final allocation and sample weights.
3. Implement B03 durable reservations/receipts and B04 checks on every learning,
   dictionary, rule, retrieval, prompt and model-promotion path. Then reserve the
   separate annotation pilot and commission independent labels.

The report-ID parser source fix remains undeployed. This SELECT proves that raw
source preservation can proceed without waiting for the flattened-table repair;
it does not perform that deployment or backfill. No waterfall, model, mask, training,
accuracy score or staging behaviour changed. Existing accuracy evidence is unchanged
and is not re-described as clean confirmation evidence.

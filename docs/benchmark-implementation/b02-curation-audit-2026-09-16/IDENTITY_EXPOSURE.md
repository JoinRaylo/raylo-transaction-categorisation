# Customer/event identity and exposure investigation

This audit reuses the immutable private engineering sample from B02: 78,537
observations, 77,925 account/transaction event keys, 100 requests and 124 accounts.
It is not a population sample and does not establish eligible benchmark size.

## Customer linkage

Three bounded, dry-run-checked BigQuery SELECTs inspected existing relational
identifiers: assessment → checkout → user → customer (and orders); raw Plaid
client-report/user/account identifiers; and repeated accounts across current and
retained historical assessments. Each query stayed below its enforced 20 GB cap.
Receipts pin SQL, source snapshot, result bytes, job IDs and query-time metadata.
Only necessary identifiers were projected; no contact fields or fuzzy identity
matching were used. Raw IDs and transaction narratives remain private.

| Linkage status | Observations | Distinct event keys |
|---|---:|---:|
| Direct customer link already in original snapshot | 39,164 | 39,164 |
| Direct link recovered in current checkout/user tables | 263 | 263 |
| Customer identity still unresolved | 39,110 | 38,498 |

Verification distinguished the recovered 263 from a merely indirect account match:
their own checkout now has a unique user/customer link, corroborated by the account
group. This was absent in the earlier source extract. The new sidecar records the
query-time evidence without rewriting the original snapshot or claiming that link
was known at the original event/request time. Across the 124 accounts, 62 have one
known customer/user and 62 have none; none has multiple known customers in this
bounded investigation. This does not prove ownership or global account uniqueness.

The 49 assessments still lacking a user reach a unique checkout: 37 are cancelled,
10 abandoned and two submitted. They have checkout-customer-info records, but those
IDs identify checkout records rather than a verified person across checkouts.
Orders do not recover the missing customers. The audit therefore does not invent
a customer ID or exclude anonymous applicants without recording a population change.

All 130 projected report-account rows have a `client_report_id` matching the known
checkout (including accounts with no sampled transactions). The 24 rows with
`client_user_id` corroborate an existing user. Neither field adds a missing customer.
No projected `persistent_account_id` is populated. The original sample's pending
alias field is present but null throughout; pending/posted and reconnect aliases
remain unverified. Report IDs, account IDs and transaction IDs are available, but
they do not by themselves certify complete economic-event or person separation.

`identity-summary.json` contains all receipts and aggregate reconciliations.
The private HMAC sidecar distinguishes direct links, recovered links, indirect
blocking groups and unresolved identities, rejects conflicting/fanout evidence,
and never sets admission or historical-separation authority to true.

## Effective-input and merchant checks

The full audit streams the 14 declared preserved input sources (full and earlier
MLM corpora, consensus/silver/distillation data, current/earlier tuning and selection
files, and credit/leaf/risk top-ups and credit-tranche snapshots), plus the permitted
historical regression inputs and withheld label-conflict inputs. It verifies file
hashes before/after scanning and complete row counts. These overlapping sources
must not be summed as distinct transactions or asserted to be original fit receipts.

Three projections are checked: the actual truncated 48-token input with direction,
the retained hinge v8's exact sparse TF-IDF plus numeric features, and an explicit
Unicode/case/punctuation/whitespace lexical fold. Aggregated MLM/silver sources lack
exact amounts, so sparse checks are **not applicable**, rather than evidence of no
sparse overlap. Surface-fold mismatches do not certify semantic novelty.

| Projection | Distinct target events matching any declared source |
|---|---:|
| Effective 48-token model input plus direction | 23,733 (30.46%) |
| Exact hinge v8 sparse/numeric features, where applicable | 2,622 (3.36%) |
| Explicit lexical fold | 24,138 (30.98%) |

For the full MLM corpus alone, effective tokens match 23,704 events, compared with
21,367 full-sentence matches in the preceding audit. The additional 2,337 illustrate
why full-string deduplication alone misses effective model-input exposure. These
projections and source matches overlap; their counts must not be added together.
The repeated scans reproduce all earlier per-source counts, and the additional
top-up/tranche checks add no new events to those union counts for this sample.

The retained selected and MLM tokenizer JSONs differ in saved padding/truncation
settings but otherwise have identical tokenizer semantics. The MLM recipe records
48 tokens. The screen explicitly sets that context and includes special tokens;
the independent verification compares all 77,925 candidate tokenizations with the
serving Hugging Face interface. It also requires every known sentence/hinge-input
match in the previous disk index to appear in the corresponding effective screen.

Exact dictionary-style merchant normalization (`strip().lower()`) is screened
against these sources, the 100k merchant-label tranche, split manifest, retained
90,264-entry dictionary, 126 T2 collision rows and historical cohorts. Of 48,282
events with a merchant, **36,473** have a known name in at least one preserved source;
32,929 match dictionary keys. The 29,643 blank-merchant events cannot be declared
unfamiliar merchant families. Nor are the remaining 11,809 filled-merchant names
certified unfamiliar families: reviewed aliases, parent brands and historical
enrichment/prompt evidence are still required.

The two preserved tuning system prompts were inspected: they give task/field
instructions and contain no merchant exemplars. This says nothing about missing
historical prompts or interactive research/review sessions. Existing deterministic
rule provenance includes rules derived from evaluation findings; B01 remains the
source for that development exposure. No exhaustive family/history absence claim
can be made from the current rule pack or exact merchant-name matches.

See `effective-exposure.json`, `exposure-verification.json` and
`merchant-exposure.json` for complete counts and scoped claims. None authorizes
benchmark consumption. Known historical input recurrence may be acceptable in
the representative view, subject to verified event/customer separation; it fails
the strict unseen-input criterion. Unmatched inputs remain candidates for further
checks, not admitted rows. Model predictions, labels and accuracy were not generated
for these new source transactions.

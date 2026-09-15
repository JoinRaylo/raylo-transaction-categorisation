# B01 — historical exposure and source identity audit

Audit date: **15 September 2026**. Status: **initial audit delivered; clean benchmark
admission is not yet established**. This is evidence for the master-v1 design, not
a new training run, benchmark collection or change to the serving waterfall.

## Findings that change the next step

1. **The main transformer evaluations are not unseen by the pretraining corpus.**
   The preserved full corpus contains exact transformer sentences for all 2,000
   credit-evaluation rows and all 400 targeted-risk rows. Their exact sentences are
   absent from the current supervised fine-tuning file. These are different claims.
2. **Selection validation overlaps supervised distillation.** The 5,000-row
   validation set has 2,280 sentence matches in the consensus source; reconstructing
   the recorded capped sampling through the retained parent epoch gives 1,885
   matching rows, 1,741 with matching labels. It cannot certify independent selection.
3. **Fresh traffic exists, but identity coverage is incomplete.** The current Plaid
   table has 35,553,295 transactions. A direct existing-ID join resolves a user and
   customer for 20,084,276 rows (56.49%); 15,469,019 (43.51%) remain unresolved.
4. **The current ingestion path loses useful identity/context fields.** All 428,949
   asset-report records have null `asset_report_id`. Transaction currency, pending
   status, pending-to-posted links and Item/institution IDs are absent from the
   flattened transaction schema. Account currency/subtype can be joined back.
5. **Strict input novelty changes the population substantially.** A Plaid-source
   screening join matches 14,470,951 current rows (40.70%) to historical sentence
   projections. The remaining 21,082,344 are not automatically eligible: other
   ancestry, customer/alias, tokenized-input and labelling checks still apply.

The data volume is promising. The next constraint is trustworthy identity and
exposure controls, not finding another large CSV. Preserve the existing scores as
development evidence; this audit does not measure how much any accuracy is inflated.

## Scope and strength of evidence

Inventoried 95 local paths (93 available files and two absent classifier-only
files in the MLM encoder directory), including the 42 source records pinned by
the compiled bundle's provenance. **41 match their recorded hashes**. The sole difference is
the already documented, evaluated-only CREDIT-PAYROLL-001 T2 CSV amendment.
All model artefacts and the 414,400-row tuning file match the bundle provenance.

The audited reference is bundle
`a2553f3462205963254b0fb1ad9dff6d64e1399abdecaab93977265908c7f23d`, selected
transformer seed 123 and hinge v8, as retained in the app's verification record.
This audit identifies those artefacts; it is not a fresh Cloud Run deployment check.

Three evidence levels are kept separate:

| Level | What it establishes | Limit |
|---|---|---|
| Hash-verified artefact | Exact available bytes match the bundle/compiler record | Compilation provenance does not prove historical fitting consumed those bytes |
| Corroborated historical input | Available files, run metadata, logs, row counts and deterministic reconstruction agree | No complete immutable fit-input/parent receipt was recorded at training time |
| Documented or unknown | Code/report describes a dependency, or required evidence is missing | No clean non-exposure certificate follows |

The 1,477,138,874-byte full MLM corpus matches the CRC32C of its preserved GCS
object, generation `1788511628342952`, created and last updated on 4 September 2026.
Its 21,524,807 rows agree with the encoder's pretraining metadata. The local SHA256
is retained as well. This strongly corroborates the preserved corpus; an object
checksum is still not an end-to-end training-consumption attestation.

The recorded transformer chain is public `distilbert-base-uncased` → full-corpus
MLM encoder → consensus-distilled parent → gold-fine-tuned seeds. The public base's
exact original revision/consumption manifest is not recorded. The OB-transformer
repo's sequence/risk models are not referenced by this bundle's recorded ancestry;
introducing one later requires auditing that ancestry too. This is not a certificate
for every model or experiment across Raylo. The [stage inventory](lineage_status.json)
also records incomplete teacher-prompt, vectorizer, mask and manual-rule lineage.

## What the model inputs overlap

Counts below are **rows in the evaluation set whose exact full transformer sentence
is present in the source**, not accuracy, unique economic events or proof of matching
training labels. Sentence comparison includes direction, amount band, normalized
merchant and narrative. Token truncation/near-duplicate matches could add exposure.

| Evaluation asset | Rows | Current tuning JSONL | Consensus distillation source | Full MLM corpus |
|---|---:|---:|---:|---:|
| Merchant-disjoint holdout | 1,055 | 0 | 0 | 1,030 |
| Credit evaluation | 2,000 | 0 | 0 | 2,000 |
| Targeted T6-bound risk | 400 | 0 | 0 | 400 |
| Pipeline evaluation | 2,000 | 12 | 0 | 1,970 |
| Tuning validation | 5,000 | 8 | 2,280 | 4,999 |

The first million corpus sentences supplied to vocabulary extension also include
64 holdout, 103 credit, 14 targeted-risk, 97 pipeline and 215 validation row inputs.
This is source exposure for vocabulary construction, not a claim that every token
in those rows was added to the vocabulary.

Independent Arrow membership checks on the five sets above reproduce the MLM counts.
The verifier preserves embedded CSV line endings: changing CRLF while reading would
change the fingerprint and comparison. Input encodings must be explicit in B02.

### Reconstructing the actual selection recipe

The current tuning file contains 414,400 examples; the frozen direction masks admit
414,196 to classifier fitting, exactly matching all three gold-stage metadata files.
The selected seed's best epoch is 1: 439,204 draws cover all 414,196 eligible row
positions. Eight validation rows match those sentences, three with matching labels.
The full tuning file also supplies mask statistics and the hinge training source;
filtering classifier rows does not erase other exposure purposes.

The consensus source contains 404,982 rows. Filtering gives 404,264, matching the
parent's metadata. The recorded two epochs each draw 327,509 rows after class caps
and repetition. Their union covers 328,227 distinct row positions; the retained
best epoch is 2. The reconstructed union matches **1,885/5,000 validation inputs
(37.70%)**, including **1,741/5,000 with the same label (34.82%)**.

This reconstruction agrees with the available source, code and metadata. It cannot
replace the missing historical consumption receipt. Even the conservative evidence
is sufficient to reject the claim that selection validation is untouched.

The 1,895,276-row T1–T5 silver file and 519,626-row earlier distillation-training
file also overlap evaluation inputs. They remain historical exposure sources to
register. **Do not attribute their overlaps to the selected model automatically**:
the selected parent is documented as using consensus labels via the generic
`silver` training stage, not the old T1–T5 silver file.

### Rules and dictionary are also part of exposure

The 90,264-row dictionary records 239 entries with `source=gold_v2_review`; its
builder explicitly uses gold review and holdout error evidence. Research history
also records card-issuer/overdraft rules R33–R37 arising from the 400-row risk set.
These are known development dependencies of the engine, independently of model
training overlap. Merchant-based exclusion helpers do not make those historic
engine evaluations independent again. Manual rule/dictionary evidence needs lineage
alongside classifier inputs.

## Source identities: what survives and what does not

### Historical Plaid source

`raylo-production.dbt_production.credit_plaid_open_banking_transactions` is a retained
4,279,707-row table, last modified **3 November 2025**. Its dbt model is disabled in
the inspected manifest/code. Transaction dates span 16 May–3 November 2025.

It has non-null transaction, account and report IDs throughout, but 1,835,573 rows
have no `customer_id`. There are 4,277,873 distinct transaction IDs and row PKs:
1,834 transaction groups are repeated. Those repeated groups have no observed
cross-account, cross-customer or cross-report conflict. This does not prove all
reconnections/pending-to-posted aliases share an ID.

Most derived learning files discarded those fields. The chat JSONL retains only
merchant, description, amount, direction and label. The corpus retains aggregated
text, provider, direction, amount band and frequency. Credit/risk top-ups retain
dates but their `row_id` is a generated batch ordinal, not a Plaid transaction ID.
The old split manifest contains only merchant, split and conflict flags.

Some source lineage could therefore be reconstructed conservatively by matching
historical projections back to source observations. Such a match may identify
multiple events/customers; never choose an arbitrary one and call the identity
recovered. Learning date and extraction date are not transaction occurrence date.

### Current Plaid source and population

The current materialization is
`raylo-production.dbt_production.intermediate_credit_plaid_transactions`, with
35,553,295 rows and transaction dates from May 2025 into September 2026. It contains:

- 9,001,121 credits (25.32%); 26,552,072 positive debits; 102 zero amounts.
- 13,428,307 blank merchants (37.77%); 8,134,475 of the credits have blank merchants
  (90.37% of credits).
- No observed missing transaction/account/assessment IDs, missing/non-finite amounts,
  invalid transaction dates, empty effective descriptions or missing detailed provider
  categories in this profile. Presence does not establish correctness.

The exact current table is already deduplicated globally by transaction ID. Start
the benchmark lineage extract from the staged observations that retain
`external_request_id`, then join account/report context at that observation scope.
The table is useful for profiling; it is not the complete immutable source contract.

The existing customer bridge links through orders and resolves 18,513,295 rows
(52.07%). The direct path
`assessment → checkout → user → customer`, using only existing database IDs,
improves this to 20,084,276 (56.49%), covering 45,617 users/customers. No conflicting
checkout/user/customer link or account linked to multiple resolved users was observed.
The remaining 15,469,019 rows (43.51%) lack this user linkage. Do not use checkout
or assessment ID as an invented permanent person ID, or silently discard this group
and call the sample representative of all applicants.

The direct join identifies 1,984,235 rows on business checkouts (5.58%). Launch
population eligibility, including business vs consumer scope, must be frozen before
sampling; it cannot be inferred from the old research evaluation distribution.

As an **illustrative prospective screen**, 1,118 users created since 7 September
2026 have 862,570 transaction-history rows; 24,215 rows also have transaction dates
on/after that date. This is not a clean eligible pool count: alias, full-ancestry,
projection and sampling checks have not been applied jointly, and no rows are reserved.

### Repeated observations and missing context

For raw requests dated 16 August–15 September 2026, the audit counts 40,037,151
ingested rows, 7,159,678 distinct request/account/transaction/assessment observations,
and 6,208,842 transaction IDs. **906,111 IDs occur in multiple requests**. No payload
change within an observation, or cross-account/assessment ID collision, was observed
in this window. These are bounded-window observations, not an all-time stability guarantee.

All 20,168 request/account pairs represented in that window join to account records
with a single non-missing currency and subtype. This recovers account context;
it does not justify substituting account currency for missing transaction currency.

All **428,949** rows in the report table have null `asset_report_id`, while report
generation dates and requested days are present. The inspected extractor reads
`item.asset_report_id`, whereas the standard Assets response puts it at
`report.asset_report_id`. Validate the correction against representative source
payloads and add a regression case before changing the extractor. The standard
shape mismatch is concrete; this audit did not retrieve new raw customer payloads.

Plaid identifiers are case-sensitive. Account IDs can change when an Item is recreated,
and a posted transaction can link to a separate pending ID. The flattened source
currently drops Item/institution IDs, pending status and `pending_transaction_id`,
so it cannot prove these aliases. `persistent_account_id` is not a universal UK
solution; the documented support is limited. See the official
[Assets reference](https://plaid.com/docs/api/products/assets/),
[Accounts reference](https://plaid.com/docs/api/accounts/) and
[transaction-state documentation](https://plaid.com/docs/transactions/transactions-data/).

### Historical Equifax source

The preserved Equifax table contains 73,246,476 source rows and includes
`TransactionId`, `ItemAccountId`, `CustomerId`, `ExternalReference`, `CreatedDate`
and `PostDate`. Its last modification is 15 October 2025. The local full corpus
contains 19,928,599 Equifax sentences and 1,596,208 Plaid sentences.

Those source IDs are absent from the aggregated local corpus. This audit inspected
the Equifax schema and local corpus, but did not certify a cross-provider Raylo
customer mapping. The OB-transformer repo has separate matched-population rules;
they cannot be adopted as a universally valid identity join without checking their
weak/ambiguous-match exclusions and intended population.

## Implications for master-v1 and B02

The design remains appropriate, with these implementation priorities:

1. **Preserve source identity before labelling.** Version a lineage extract carrying
   original case-sensitive transaction/account/Item IDs, request/report IDs and
   timestamps, verified user/customer links, pending/posted aliases and original
   input fields. Keep each observation and explicit aliases; deduplicate deliberately.
2. **Resolve population gaps explicitly.** Investigate a governed identity for the
   unresolved applicant cohort. A restricted identified-customer benchmark is possible
   only with its narrower target population and bias stated. Repair report ID extraction
   and retain missing prediction-time fields before final collection.
3. **Seed exposure indexes from preserved evidence.** Hash-pin the full MLM, vocabulary
   input prefix, consensus source, tuning snapshots, masks, dictionaries, rule evidence
   and historical model inputs. Keep uncertain/legacy exposure as conservative exclusions.
   Do not rebuild training files and present the reconstruction as original history.
4. **Enforce both training and selection admission.** Close distillation/pretraining/
   preprocessing gaps, including selection validation, before a new campaign starts.
   Missing identity or ancestry blocks clean admission; it is not a fallback-to-train case.
5. **Then profile the jointly eligible population.** The 40.70% source-proxy overlap,
   43.51% identity gap and other exclusions overlap; do not multiply their percentages
   to estimate eligible volume. Full tokenized-input/near-duplicate and alias checks,
   source snapshot reservation, coverage quotas and power remain to be completed.

Do not recycle existing gold as the unseen master. Keep it as a documented regression
suite and create a new separate tuning-validation asset with ancestry-wide exclusions.
Repeated master development feedback still needs a fresh sealed confirmation cohort.

## Verification and remaining limits

Seven aggregate-only BigQuery SELECTs were validated before execution, each capped
at 20 GB billed; total reported bytes processed are **35,432,445,006**. The source
tables were not modified. Live profiles are separate job snapshots, not the future
immutable benchmark extract. Raw ingestion and identity tables can change between runs.

Independent verification reproduces the five principal MLM overlap counts and both
recorded fine-tuning sampling recipes. Source-file hashes, query/result receipts,
taxonomy references, count reconciliation and mirrored documents are retained alongside
this report. No model inference, retraining, relabelling, benchmark reservation,
locked v5/v6 content read, pipeline change or deployment was performed.

Unresolved: original fit-input/parent hashes at execution; complete historical source
event/customer linkage; third-party base revision/provenance; full tokenized/near-duplicate
overlap; reconnect and pending aliases; identity for unlinked applicants; a full API-shaped
fresh source extract; jointly eligible population and category/power measurements.
These are explicit boundaries of the audit, not evidence that the missing checks pass.

# B03-B fresh linked-only admission profile

Status: **aggregate source-readiness evidence; no candidate admission**.

This dated profile reruns the pinned B02 aggregate-only `SELECT` against the
live `raylo-production` Plaid materialization after Carlos accepted the
internal-benchmark IAM risk. It checks the existing assessment → checkout →
user → customer admission rule and returns aggregate counts only. It does not
return transaction payloads or identifiers, reserve rows, create labels,
authorize consumption or change cloud state.

## Executed evidence

- Project/location: `raylo-production`, EU.
- Statement: `SELECT`; no dbt build, source mutation or destination table.
- Dry-run bytes: `10,555,501,251`, below the `20,000,000,000`-byte cap.
- Executed bytes processed: `10,555,501,251`.
- Executed bytes billed: `10,556,014,592`.
- BigQuery job: `4f1bad6b-6af7-4499-8366-2bdcda5d4e26`.
- Captured: `2026-09-17T20:05:43.800274+00:00`.
- SQL SHA-256: `97ea75dbe9015bfe5075ce483e39cf9eafa52f0ce0b922609f3e52a0c73e50bf`.
- Runner SHA-256: `58a7c7506190acc6d9af390ff303116cd7bf21d727df4e3a0460bd139370f635`.
- Result SHA-256: `6755d16fd44a7d35ebaaa4b5fe69b69ab710fb4cd2f2b604de55eebbf2d51f29`.

The exact dry-run and execution receipts, aggregate result and source SQL are
retained beside this README.

## Current aggregate frame

The live materialization contains `36,706,094` rows and `36,706,094` distinct
transaction IDs. The existing customer-linked rule admits `20,653,747`
observations across `46,273` users/customers, `50,828` checkouts and `71,423`
account/customer pairs. `16,052,347` rows are excluded because the existing
link is missing or conflicting. The linked date range is 16 May 2025 to 16
September 2026.

The linked frame contains `4,718,193` credits, `15,935,510` positive debits
and 44 zero-amount observations. Merchant text is blank on `7,272,730` rows
and present on `13,381,017`; checkout scope is business on `1,070,537` rows,
consumer on `19,456,927` and unknown on `126,283`.

The materialized relation reported zero repeated provider/account/transaction
keys and zero changed-content variants in this snapshot. That is not proof of
raw report, pending/posted, reconnect-alias or historical ancestry completeness;
the candidate admission query must retain those source-side protections.

## What this does and does not establish

This is a fresh linked-pool frame, not a clean evaluation frame. It does not
measure full exposure against the hinge, transformer, distillation, dictionary,
prompt or selection ancestry; it does not prove unfamiliar merchant families;
and it does not produce whole identity/projection sampling blocks. Provider
categories remain search proxies rather than independent labels. No row has
been reserved, labelled, placed in training or scored by this increment.

The next bounded step is an admission-specific lineage extract that joins the
linked pool to the preserved training/selection exposure evidence, reports
event/account/customer/effective-input/family exclusions and block sizes, and
only then proposes the permanently quarantined 500-row pilot. The existing
three-view separation, novelty/group protections, customer-linked Plaid-only
scope and closed anonymous-ID boundary remain mandatory.

## Independent review

The Astra subagent review (Hooke, 17 September 2026) agrees that this profile is
sufficient to plan candidate collection but not to admit the pilot. It confirmed
the receipt/result/source consistency and identified the remaining candidate-level
requirements: pending/posted/reconnect and report-history aliases, legacy and
historical exposure exclusions, view-specific input/family novelty, connected
group/block sizes and sampling weights, plus managed reservation and competing-
consumer protection. The review made no edits, warehouse queries or customer
payload/locked-set accesses.

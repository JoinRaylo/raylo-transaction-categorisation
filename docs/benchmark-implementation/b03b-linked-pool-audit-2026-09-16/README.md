# B03-B linked Plaid pool audit

Status: **read-only aggregate source audit; no admission**. This is a new live
warehouse snapshot after the approved B03-A protocol review. It does not reserve,
label, export, train on, score or certify any transaction.

## Scope and execution

The existing pinned runner executed one aggregate-only `SELECT` against the known
`raylo-production` EU relations. It used the existing assessment → checkout → user
→ customer linkage, retained only unambiguous existing customer IDs, performed no
anonymous-ID recovery, and returned one aggregate row with no raw IDs, narratives
or transaction payloads. The query processed 10,448,039,166 bytes and was billed
10,449,059,840 bytes under the 20,000,000,000-byte cap. Table metadata was unchanged
before and after the query.

The exact external result was written to
`/private/tmp/txncat-b03b-linked-pool-audit-20260916-escalated/` and is identified
by result SHA-256
`c5c93f9eb2633020f2ac3e99a0ca73273ac2e61abc963a0683aca4fdcc358e6a`.
The checked-in [aggregate](aggregate.json) is the same row, and
[receipt-summary.json](receipt-summary.json) records the bounded execution and
source pins without copying table metadata or private payloads.

## Current aggregate

| Measurement | Result |
| --- | ---: |
| Materialized source observations | 36,312,899 |
| Unambiguous customer-linked observations | 20,474,043 (56.38%) |
| Missing/conflicting identity rows excluded | 15,838,856 |
| Linked customers / users / checkouts | 46,051 / 46,051 / 50,584 |
| Linked account-customer pairs | 71,105 |
| Credits / positive debits / zero amounts | 4,677,449 / 15,796,550 / 44 |
| Blank merchant among linked rows | 7,211,707 (35.23%) |
| Business / consumer / unknown checkout scope | 1,067,471 / 19,280,289 / 126,283 |
| Linked transaction dates | 16 May 2025–15 September 2026 |

No ambiguous join cardinalities, missing usable event keys or invalid linked dates
were observed in this materialized snapshot. The materialized table reports zero
repeated provider/account/transaction keys and zero changed-content variants; that
cannot establish uniqueness in raw reports or absence of pending/posted transitions,
reconnect aliases or corrections. The legacy category array is missing on 656,041
linked observations; primary and detailed provider categories are present for all
linked rows. These are sampling proxies, not verified labels.

## Interpretation and next gate

This is a source-readiness profile, not a candidate frame. It does not prove complete
event/customer/account history, pending/posted/reconnect alias coverage, legacy
exclusions, effective-input history, merchant-family novelty or benchmark eligibility.
The next implementation is a scoped production object/transaction adapter and IAM
plan. It must be reviewed before any cloud resource or permission change. Only after
that gate may a separately controlled, linked-only candidate admission job be
designed; the 500-row annotation-method pilot remains separately quarantined.

The current profile contains no labels, model artefacts, locked-set access or training
inputs, and it authorizes no consumption.

# Linked-pool profile and joint data plan

16 September 2026. **The linked Plaid population is large enough to proceed with
curation planning, and the training audit identifies useful improvements for both
heads.** Clean benchmark eligibility and category coverage still need admission
evidence and independent labels. No examples were reserved, labelled or trained on
in this increment. Read [PLAN.md](PLAN.md) for allocation and the final retraining path.

## Measured source population

One aggregate-only `SELECT` profiled the full current production materialization,
with reduced assessment → checkout → user → customer joins to prevent row
multiplication. Only unambiguous existing-ID links with a valid customer record
enter the linked strata. No anonymous recovery, contact matching or row export ran.

| Measurement | Result |
|---|---:|
| Current materialized source rows | 36,312,899 |
| Linked rows / share of source | 20,473,397 / 56.38% |
| Linked customers and users | 46,049 each |
| Linked checkouts / accounts | 50,582 / 71,103 |
| Identity-excluded rows | 15,839,502 (all missing checkout → user link) |
| Credits | 4,677,348 / 22.85% of linked rows |
| Positive debits / zero amounts | 15,796,005 / 44 |
| Blank merchant | 7,211,560 / 35.22% of linked rows |
| Blank merchant among credits | 4,221,721 / 90.26% of credits |
| Business / consumer / unknown checkout scope | 1,067,471 / 19,279,643 / 126,283 |
| Linked transaction dates | 16 May 2025–15 September 2026 (17 months) |

No source account/transaction/assessment IDs were missing, no ambiguous join
cardinalities were observed, and no linked account mapped to multiple customers
in this current snapshot. All linked rows have primary and detailed provider
categories; these are **sampling proxies, not verified labels**. The legacy category
array is absent on 656,034 linked rows. Full month, amount, direction × merchant
and customer account-breadth counts are in [the aggregate](population/linked_pool_profile_result.json).

The previous B01 snapshot had 35,553,295 source rows and 20,084,276 linked rows
covering 45,617 customers. The current source grew by 759,604 rows, including
389,121 linked rows and 432 linked customers. These are dated snapshot differences,
not an estimate of ingestion or new economic-event volume.

**Count clarification:** this dbt table already keeps one row per `transaction_id`,
ordered by latest `external_request_created_at` after its 1 August 2025 source
filter. Earlier references to these counts as raw rows “before deduplication” were
imprecise. They are materialized, transaction-ID-deduplicated rows, not proven
unique economic events and not admitted benchmark examples. Zero repeated
provider/account/transaction keys or changed-content variants here cannot establish
that raw reports contain no repeats, corrections, pending/posted transitions or
reconnect aliases. Preserve B01's separate bounded raw-repeat findings; candidate
lineage must use the staged/raw report observations.

The profile measures the whole current linked materialization, not the eventual
eligible or prospective sampling frame. Its 5.21% business and 0.62% unknown-scope
rows remain visible. Currency, institution/account type, pending state and aliases
need report-sidecar coverage before final sampling. Dates at the ends are partial
months. Do not copy these raw proportions into future-frame weights without
reprofiling that admitted frame.

## Existing training evidence

See [the training audit](training/TRAINING_AUGMENTATION.md) and
[aggregate counts](training/aggregate_profile.json) for inputs, uniqueness
definitions, per-leaf support, provenance limitations and actual saved recipes.

The current 414,400-row supervised file contains 30,286 credits (7.31%) and
32,783 blank-merchant rows (7.91%). It has 342,268 distinct exact user messages,
342,405 distinct input/label pairs and 71,995 copies above those pairs. **133
exact-input groups have conflicting labels.** This does not prove which labels are
wrong; review source provenance and model-input ambiguity before the next fit.

271 of the 275 taxonomy leaves appear in that file. `account_misuse`,
`balance_transfer_fee`, `interest_charged` and `loan_repayment_dd` are absent.
Among represented leaves, 21 have fewer than 20 distinct input/label examples,
48 fewer than 50 and 85 fewer than 100. Examples include `housing_benefit` (4),
`credit_card_fee` (5) and `money_transfer_fee` (8). These are input support counts,
not verified unique customer/event counts or measures of label correctness.

The old 5,000-row selection file has nine credits and no blank merchants, plus
119 repeated input/label rows. Its historical distillation overlap was already
documented in B01. A new, separately protected selection set should cover credits,
blank merchants and critical classes; the master confirmation set cannot serve
this purpose.

The transformer also inherits a 404,982-text consensus stage: 87,610 credits
(21.63%) and 119,262 blank-merchant rows (29.45%). Therefore the supervised-file
imbalance is not a description of its entire ancestry. Consensus is training
signal, not independent gold. Retain the common new labelled additions for both
heads while recording their different existing ancestry.

## Scoped reuse of the earlier exposure audit

Reaggregated the existing private 100-request engineering sample for its linked
portion only, with pinned sidecar/source hashes. This is **not a full-pool exposure
screen, a random sample or an admission decision**.

| Linked sample measurement | Distinct event keys |
|---|---:|
| Existing direct links / subsequently recovered direct links | 39,164 / 263 |
| Total linked sample | 39,427 |
| Known transformer token-48 input | 10,271 |
| Known hinge sparse input | 1,369 |
| Known folded-surface input | 10,518 |
| Union of the three known-input matches | 10,527 |
| Blank / known-name / unmatched-name merchant | 12,838 / 21,087 / 5,502 |

The 28,900 events without one of those known-input matches are not proved unseen.
Likewise 5,502 unmatched merchant names do not prove new merchant families. The
three views retain their separate requirements; historical customer/event ancestry,
aliases, legacy restrictions and durable consumer enforcement remain relevant for
the linked population. See [the aggregate](sample/aggregate.json) and the existing
[curation audit](../b02-curation-audit-2026-09-16/README.md).

## Evidence and reproduction

- [Population SQL](population/linked_pool_profile.sql),
  [executed runner snapshot](population/executed_runner.py.txt),
  [dry-run receipt](population/dry_run_receipt.json) and
  [executed receipt](population/executed_receipt.json).
  `raylo-production`, EU, SELECT only; 10,447,908,871 bytes processed and
  10,448,011,264 billed under a 20,000,000,000-byte cap. Source metadata was
  unchanged before/after the query. Root dbt `manifest.json` and model code are
  hash-pinned; the development `target/manifest.json` was not used as authority.
- [Training profiler](training/profile_training_inputs.py), aggregate source hashes
  and saved iteration-8 metadata. No builder, model fit, prediction, remote labeller,
  protected v5/v6 dataset or signing key was invoked/read.
- [Cached-sample adapter](sample/aggregate_linked.py) reads the preserved private
  identity/exposure sidecars, checks matching coverage, identity consistency,
  non-authorizing status and hashes before/after loading, and outputs aggregates only.
- [Verification receipt](verification.json) binds the delivered evidence and records
  parent review/reconciliations. Public evidence is mirrored byte-for-byte in the
  app and research repositories; private memberships, narratives and labels are not
  included. The scripts are dated audit adapters, not B03/B04 enforcement.

To reproduce, use an environment with `google-cloud-bigquery` for the population
adapter and `pyarrow` for training profiles. Run the preserved population snapshot
with `python population/executed_runner.py.txt`; it is exact executed source saved
as text so formatters cannot change its receipt-bound bytes. The runner defaults to a
dry run and validates the pinned local dbt sources. `--execute` performs its
bounded SELECT. Its input tables are live: later runs are new dated evidence, not
byte-identical reconstructions of this snapshot. Use a new `--output-dir` to retain
this evidence. The training runner accepts `--research` and a new `--output`
directory; the sample adapter accepts `--archive` and a new `--output` JSON path.
Private source snapshots must be supplied through their existing controlled access.

The next deliverable is protected reservation plus consumer admission, followed by
the separate 500-row annotation pilot. The [joint plan](PLAN.md) proposes a bounded
10,000-example training addition and a refreshed 5,000-row selection set alongside
the existing 20,000-row master envelope. These remain planning budgets until
admission and pilot label yields establish feasible quotas. Accuracy was not
measured or changed by this profiling work.

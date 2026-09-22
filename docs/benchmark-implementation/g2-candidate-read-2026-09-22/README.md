# G2 — bounded candidate read for the 1,500-row core expansion (2026-09-22)

AIE-510 gate G2. This directory records the phase-ledger evidence, the
receipt-bound candidate frame read and the frozen rare-leaf supplement
specification. **Nothing here admits, reserves, labels, trains, scores or
releases benchmark rows.** Every artifact carries `authorizes_consumption=false`.

## Phase position

`phase-ledger.json` is the canonical `PhaseLedger` (`benchmark_id =
txncat-master-benchmark-v1`) advanced through two human-approval transitions:

1. `synthetic-only → pilot-gates-accepted`, bound to
   `g1-pilot-gates-evidence.json` — the AIE-511 adjudication acceptance,
   AIE-512 immutable outcome freeze and AIE-513 B04 consumer-enforcement
   remediation (R1–R5 approved). All pilot digests re-verified from the private
   store: membership `0afb4155…`, payload `fc5c626c…`, outcomes `a7cbc51b…`,
   publication `eaf5a8bb…`, binding `2b3c2f64…`, enforcement receipt
   `464bbef5…` (canonical `65325b0d…`), coverage matrix `5177f983…`.
2. `pilot-gates-accepted → candidate-read-authorised`, bound to
   `g2-candidate-read-scope.json` — the G2 scope contract (linked-only pool,
   `anonymous_id_recovery=false`, 10k/500k row bounds, 20 GB byte budget,
   permitted/forbidden actions, stop conditions).

Ledger state: `candidate-read-authorised`, not halted.

## Candidate frame draw

`tools/benchmark/benchmark_candidate_frame_extract.{py,sql}` executed a single
hash-ranked SELECT over
`raylo-production.dbt_production.intermediate_credit_plaid_transactions`
(location `EU`, dry-run then execute, `maximum_bytes_billed=20 GB`, seed
`g2-candidate-frame-2026-09-22-v1`). Source table metadata was captured before
and after and is identical (etag `DeEMFqeK9pDTYWnfHfsXHg==`, modified
2026-09-22T01:38:01Z).

Private output `~/.local/share/raylo-txncat/benchmark-expansion-2026-09-22/candidates/`:

- `candidates.jsonl` — 10,000 rows, sha256
  `746ff97680ee623732b0b679b9bec4997eb2ff66c0807833d3157942be4c6319`
- `receipt.json` — schema `benchmark-candidate-frame-extract-v1`, purpose
  `g2_candidate_frame_read_not_admission`, job `txncat_frame_b1873af1-f3f9-475e-802e-7781707c97f0`,
  11,686,362,878 bytes processed / 11,686,379,520 billed, both under budget.

The frame is the customer-linked Plaid pool only: each row carries an
unambiguous assessment → checkout → user → customer link; ambiguous or
anonymous rows are excluded, never repaired.

## Frame profile

`tools/benchmark/benchmark_profile_candidate_frame.py` profiles the frame
locally against the pinned exposure index, inventory (`bb0c02de…`), waterfall
runtime and pilot membership. Output `…/benchmark-expansion-2026-09-22/profile/`:

- `profile.json` — schema `benchmark-admission-profile-v2`: routed-tier and
  route-label counts, provider category-family distribution, source strata,
  customer/account/assignment block stats, input-exposure screens
  (token48/surface-fold/hinge-sparse), merchant lexicon coverage, per-view
  eligibility × status cross-tabs, capacity vs expansion targets
  (representative 800 / unseen_input 150 / unfamiliar_merchant 50), pilot
  overlap, proxy evidence per pinned proxy, and the full artifact lineage.
- `candidates.opaque.jsonl` — keyed pseudonyms only (no raw identifiers).

All five history flags remain `false`; unknown identity, alias, input-history,
family and legacy evidence is quarantined, never promoted to eligibility.
`rows_reserved_or_labelled = 0`.

## Rare-leaf supplement specification (frozen)

`rare-leaf-specification.json` is the canonical `RareLeafSpecification`
(`benchmark-rare-leaf-spec-v1`), sha `d1d95878b538da77376ee6f4aa05aee374cba7ab96db6680f39154d2a226d8dd`:

- taxonomy `taxonomy-275-leaf-v1`, sha `67df2395…`; all 25 roster leaves
  validated against the pinned taxonomy.
- roster = the 25 lowest-support leaves in the pinned supervised tuning corpus
  (train+val): three absent (`account_misuse`, `balance_transfer_fee`,
  `interest_charged`), the rest with ≤20 distinct inputs, ranked by
  `(distinct_inputs, leaf)`; uniform quota 20 → exactly 500.
- proxies by precedence: `dictionary_rule` (dictionary+rules manifest) →
  `merchant_lexicon` (three approved merchant-label files) →
  `provider_category` (taxonomy `plaid_source` crosswalk) → `historical_label`
  (modal tuning leaf per merchant) → `baseline_prediction` (hinge v8 joblib).
  Baseline alone is rejected by contract.
- caps: 4 rows/customer, 4/account, 40/family; per-leaf floors
  `min_proxy_support=4`, `min_final_support=10`, `min_distinct_customers=5`.
- seed `20260922`; window `2025-05-27 … 2026-09-20` (frame-observed range);
  `source_sha256` binds the population-defining extract SQL (`9102edfc…`);
  `runtime_sha256` binds the audited bundle provenance (`8c42dc9a…`);
  `configuration_sha256` binds `rare-leaf-spec-configuration.json`.
- the supplement is excluded from the production-weighted headline; candidates
  structurally forbid final-label fields; shortfalls are reported, never filled.

## Receipt chain

`receipt-chain.json` — canonical `ReceiptChain` through `candidate_frame`:

| seq | kind | binds |
| --- | --- | --- |
| 0 | `root_configuration` | taxonomy, allocation design (`c9245bcd…`), rare-leaf spec, conflict matrix, code manifest (`40edba85…`), runtime bundle, pilot parent |
| 1 | `source_materialization` | source snapshot (`9ee53d0f…` = canonical table metadata), frame content, `logical-transaction-v2` projection manifest, declared null family registry (`111e7b01…`) |
| 2 | `candidate_frame` | source snapshot, frame digest `746ff976…`, member_count 10,000 |

Chain head: `00e6d63769ba08e7ea424f573f7aebd704a8394030c97ee13f711b61353846ed`.
Stable digests are chain-pinned; a later admission receipt must rebind them
unchanged.

## Boundaries

- The frame, profile and spec are **read/planning evidence only** — no
  admission, reservation, annotation, release, training or locked-set scoring
  is authorized by any artifact here.
- Admission (G3) requires a separate approved authority; unresolved aliases,
  identity history, merchant families and legacy coverage remain quarantine
  reasons until then.
- Private artifacts live under `~/.local/share/raylo-txncat/`; only digests and
  aggregates are committed.

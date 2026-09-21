# B04 consumer enforcement (AIE-513)

Protected eval-membership enforcement across every learning, selection,
evidence and promotion consumer seam, bound to the frozen AIE-512 pilot
release.

## Release binding

The only approved protected release is pinned in `src/eval_protection.py`
(`PINNED_BINDING`) and mirrored in `raylo_txncat.benchmark_enforcement`:

| artifact | sha256 |
|---|---|
| membership | `0afb4155…d43068` |
| pilot | `fc5c626c…f684248` |
| publication | `2b3c2f64…d4e8436` |
| publication file | `eaf5a8bb…8c44f22` |

## Architecture

1. **Canonical module** — `lib/raylo-txncat/src/raylo_txncat/benchmark_enforcement.py`
   owns `ReleaseBinding`, `ProtectionSet`, `load_protected_membership`,
   `verify_release`, `exclude_protected`, `verify_fetch_receipt`,
   `artifact_receipt`/`verify_artifact_receipt`, `require_promotion_provenance`,
   `ConsumerCoverage`, `CoverageMatrix`, `EnforcementReceipt`.  All semantics
   live here; nothing is forked.
2. **Research adapter** — `src/eval_protection.py` imports the canonical
   module (`RAYLO_TXNCAT_SRC`/`--txncat-src`), pins the release, and exposes
   `add_args`, `load_release`, `apply`, `apply_env`, `assert_bound`,
   `verify_fetch_receipt`, `verify_tuning_export`, `verify_artifact`,
   `write_artifact_receipt`, `gate`.

## Enforcement semantics

- Every fetch of customer-linked rows runs `apply_env`/`apply` (which wraps
  `verify_release` + `exclude_protected`) before persisting.  Rows lacking
  `account_id`/`transaction_id`/`customer_id` fail closed.
- Exact protected events plus connected account and customer groups are
  excluded; contradictory linkage and duplicate events are rejected.
- Every persisted artifact gets a bound `*.b04-receipt.json` (output digest +
  input digests + release binding).  Downstream consumers call
  `verify_artifact`, which fails on a missing receipt, a stale release, or
  digest drift (relabelled/changed artifacts).
- `.fit` boundaries call `verify_tuning_export` (committed membership coverage
  + bound fetch receipt) before any model consumes `tuning_train.jsonl` /
  `tuning_val.jsonl` — including the `mlx_lm.lora` shell scripts.
- Promotion (`raylo_txncat.publish_bundle`) requires
  `require_promotion_provenance` over declared fetch receipts before upload.
- Identity-losing consumers (GROUP BY text-frequency corpora, narrative-egress
  evidence queries, the unbound experiment3 feature store) are hard-gated via
  `eval_protection.gate` — they cannot prove disjointness, so they fail closed
  before any query or read.
- `eval_sets.refuse_confirmation_eval` refuses locked v5/v6 by filename *and*
  by content hash (renaming does not unlock).

## Coverage

`coverage-matrix.json` — 103 consumer entries (62 enforced, 25 gated_off,
16 bound_read), sorted and unique, digested by `matrix_sha256`.

`enforcement-receipt.json` — the aggregate `EnforcementReceipt`: release
binding + matrix digest + 17 validation checks + limitations.
`authorizes_consumption=false`.

Regenerate with:

```
RAYLO_TXNCAT_SRC=<monorepo>/lib/raylo-txncat/src \
  python tools/benchmark/build_enforcement_matrix.py
```

## Limitations (also in the receipt)

- Prospective protection only — historical non-use is not certified.
- Pre-B04 artifacts without receipts fail closed until a guarded rebuild
  emits them (this is deliberate).
- The experiment3 / AIE-503 risk-refresh feature store is gated off pending
  a guarded rebuild.
- The receipt binds artifact bytes; it does not attest the human review step
  between a fetched sample and its reviewed derivative.

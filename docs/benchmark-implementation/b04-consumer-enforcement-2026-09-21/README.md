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
   owns `ReleaseBinding`, `PINNED_RELEASE`, `ProtectionSet`,
   `load_protected_membership`, `verify_release`, `exclude_protected`,
   `verify_fetch_receipt`, `issue_fetch_receipt`,
   `issue_artifact_receipt`/`verify_artifact_receipt`,
   `require_promotion_provenance`, `ConsumerCoverage`, `CoverageMatrix`,
   `EnforcementReceipt`.  All semantics live here; nothing is forked.
2. **Research adapter** — `src/eval_protection.py` imports the canonical
   module (`RAYLO_TXNCAT_SRC`/`--txncat-src`), pins the release, and exposes
   `add_args`, `load_release`, `apply`, `apply_env`, `assert_bound`,
   `verify_fetch_receipt`, `verify_tuning_export`, `verify_artifact`,
   `write_artifact_receipt`, `gate`.

## Supported paths

- **Labelling**: Gemini/Sonnet are used for labelling egress only.  Every
  label/sheet/tiebreak/resolve seam calls `verify_artifact` on the receipted
  sample before a narrative may leave the boundary.
- **Categorisation model**: the winning transformer is the sole TxCat-1
  model trained and promoted.  Its corpus (`tuning_train.jsonl` /
  `tuning_val.jsonl`) passes `verify_tuning_export`, and its bundle passes
  `require_promotion_provenance` before upload.
- **Retired**: all four Qwen LoRA launchers (`scripts/qwen3_*.sh`) carry an
  explicit terminal gate immediately after `set -euo pipefail`.  Qwen is not
  part of the intended production path; the launchers are classified
  `gated_off` and excluded from the enforced count.

## Enforcement semantics

- **Authenticated issuance.**  Every fetch receipt, artifact receipt and
  guard token is Ed25519-signed by the pinned B04 key: the private key is
  held outside Git (`B04_RECEIPT_SIGNING_KEY` or `B04_RECEIPT_SIGNING_KEY_FILE`,
  currently `~/.config/raylo/b04-receipt-signing-key`); verification needs
  only the public key pinned in the module.  A hand-written receipt, a
  caller-constructed `GuardResult` without the signed token, or a document
  signed by any other key all fail closed.
- Every fetch of customer-linked rows runs `apply_env`/`apply` (which wraps
  `verify_release` + `exclude_protected`) before persisting.  Rows lacking
  `account_id`/`transaction_id`/`customer_id` fail closed.
- Exact protected events plus connected account and customer groups are
  excluded; contradictory linkage and duplicate events are rejected.
- Every persisted artifact gets a signed `*.b04-receipt.json`
  (`b04-artifact-receipt-v3`): schema, release binding, purpose, consumer,
  output path and output byte digest are all validated, and issuance requires
  a verified `GuardResult` or a non-empty chain of already-verified input
  receipts — a caller-provided digest alone cannot mint a sidecar.
  Downstream consumers call `verify_artifact`, which fails on a missing
  receipt, a stale release, digest drift (relabelled/changed artifacts), a
  renamed or substituted sidecar, or protected content inside an
  identity-bearing CSV.
- `.fit` boundaries call `verify_tuning_export` (committed membership coverage
  + bound fetch receipt) before any model consumes `tuning_train.jsonl` /
  `tuning_val.jsonl` — including the `mlx_lm.lora` shell scripts.
- Promotion (`raylo_txncat.publish_bundle`) pins `PINNED_RELEASE` itself —
  no caller-supplied binding is accepted — and requires
  `require_promotion_provenance` over the bundle's declared learning inputs:
  every input must be covered by exactly one signed, strictly-validated
  fetch or artifact receipt, and the bundle's explicit
  `provenance.training_inputs` collection must equal the declared and
  receipted input digest sets exactly.  Model outputs recorded in
  `source_files` (`.safetensors`, `.joblib`) are provenance records, not
  learning inputs.
- Identity-losing consumers (GROUP BY text-frequency corpora, narrative-egress
  evidence queries, the unbound experiment3 feature store) are hard-gated via
  `eval_protection.gate` — they cannot prove disjointness, so they fail closed
  before any query or read.
- `eval_sets.refuse_confirmation_eval` refuses locked v5/v6 by filename *and*
  by content hash (renaming does not unlock).

## Coverage

`coverage-matrix.json` — 126 consumer entries (68 enforced, 44 gated_off,
14 bound_read), sorted and unique, digested by `matrix_sha256`.

`enforcement-receipt.json` — the aggregate `EnforcementReceipt`: release
binding + matrix digest + 29 validation checks + limitations.
`authorizes_consumption=false`.

Regenerate with:

```
RAYLO_TXNCAT_SRC=<monorepo>/lib/raylo-txncat/src \
  python tools/benchmark/build_enforcement_matrix.py
```

## Limitations (also in the receipt)

- Qwen LoRA is retired, not repaired — the launchers terminate before any
  data access and are outside the enforced count.
- Issuance machines need the private signing key via
  `B04_RECEIPT_SIGNING_KEY[_FILE]`; verification needs nothing beyond the
  pinned public key.
- Prospective protection only — historical non-use is not certified.
- Pre-B04 artifacts without receipts fail closed until a guarded rebuild
  emits them (this is deliberate).
- The experiment3 / AIE-503 risk-refresh feature store is gated off pending
  a guarded rebuild.
- The receipt binds artifact bytes; it does not attest the human review step
  between a fetched sample and its reviewed derivative.

# B03-B authenticated receipt boundary hardening

Status: **implemented and synthetic-tested; live resource/IAM proof pending**.

This local milestone hardens the canonical receipt and worker adapter without
accessing BigQuery, Plaid, customer data or cloud authority resources. It does
not authorize benchmark admission, locked-set access, retraining, scoring or
B04 integration.

## Implemented controls

- Signed receipts carry an explicit `authority_id` and `environment`, and the
  verifier checks both against its configured binding before granting a read.
- Learning and selection receipts require configured, immutable object-prefix
  mappings; the claim kind is checked independently of IAM metadata.
- `GoogleIDTokenWorkerIdentity` verifies the exact Cloud Run audience through a
  Google OIDC verifier and maps the verified token `sub` to an immutable,
  numeric service-account unique-ID allowlist. Token email is not an authority
  key.
- `ProductionAuthorityVerifier` is a separate verify-only worker boundary. It
  accepts a verify-only port and has no receipt-issuance method.
- KMS receipt verification reads the referenced CryptoKeyVersion and requires
  its state to be `ENABLED` before trusting the public key.

## Evidence

- `uv run pytest -q lib/raylo-txncat/tests/test_benchmark_authority.py lib/raylo-txncat/tests/test_benchmark_authority_cloud.py`
  → **53 passed**.
- The handover startup command → **115 passed**.
- `uv run ruff check` over the four changed source/test files → **all checks
  passed**.
- Exact-config `ruff format --check` over the four changed files → **4 files
  already formatted**.
- Tests include forged authority/environment receipts, crossed claim prefixes,
  wrong audience and unknown unique IDs, immutable mapping mutation, verify-
  only capability inspection, and disabled KMS-version rejection.

## Remaining gates

The code uses injected ports and synthetic fakes; it has not validated a live
Google token, Cloud Run request extraction, service-account unique IDs, KMS
permissions or cross-process IAM denies. Retention/cleanup ownership and
audit-log scope remain unresolved. The exact binding packet must still be
security-approved, and live adapter proofs must use an empty authority project
with no customer-derived fixtures.

The next safe step is a security review of the exact binding/resource packet,
followed by separately approved empty-resource creation and read-back checks.
No real authority data may be admitted until those checks and B04 gates pass.

The repository-wide `pytest -q` was also attempted, but collection is blocked by
pre-existing duplicate flat test-module names across unrelated apps (14 import
mismatch/collection errors); it does not reach this package’s tests.

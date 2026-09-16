# B02 initial implementation — three-view preflight

Status: **verified local foundation; B02 is not fully complete and B03/B04 are not
implemented**. No clean benchmark has been admitted, reserved or labelled.

Read the [three-view contract amendment](CONTRACT_AMENDMENT.md) and
[source readiness report](SOURCE_READINESS.md). They apply the approved distinction
between representative new events, unseen inputs and unfamiliar merchant families
without weakening the existing v1 registry or changing categorisation behaviour.

## Implemented

- One canonical module, `lib/raylo-txncat/src/raylo_txncat/benchmark.py`, imported by
  both app and research adapters. Strict versioned private subject/index types;
  case-sensitive, domain-separated HMAC identities; actual head projections.
- View-specific decisions for event/group/input/family overlap; all nine learning
  purposes plus model-selection validation; permanent reservation lifecycle handling;
  explicit unknown-history and legacy-exclusion checks. Reasons are deterministic.
- Aggregate profiling with per-view statuses, overlapping rejection reasons,
  input-exposure flags and joint eligible-view combinations. Duplicate observations
  and known event aliases fail the candidate batch rather than silently changing it.
- The narrow payload-extractor report-ID source fix and regression tests.

A decision binds exact subject/index content and epoch, but is explicitly **not an
authority receipt**. Code does not sign/commit claims, resolve aliases or validate
warehouse provenance by itself. Private index exports must contain the complete
verified aliases; unknown keys/history remain quarantined. The initial in-memory
comparator is for bounded exports and fixtures, not loading the 21.5M corpus into
JSON; scalable index joins belong to the next source/authority increment.

## Reproduce the synthetic profile

From the app monorepo root, using its Python test environment:

```sh
python apps/ob-txn-categoriser/scripts/benchmark_preflight.py \
  --monorepo-root "$PWD" \
  --implementation apps/ob-txn-categoriser/research/benchmark-implementation/b02-initial/implementation-v2.json \
  --index apps/ob-txn-categoriser/research/benchmark-implementation/b02-initial/fixtures/index.json \
  --candidates apps/ob-txn-categoriser/research/benchmark-implementation/b02-initial/fixtures/candidates.jsonl \
  --output /private/tmp/txncat-b02-new-profile-v2.json
```

The output must be new. Only synthetic opaque identifiers occur in these fixtures.
The app's ordinary environment suffices for profiling; projection construction needs
its existing NumPy/model extras and a verified tokenizer for encoded projections.
The checked-in [synthetic profile](synthetic-profile.json) is not a real-data count.

The historical `implementation.json` and `synthetic-profile.json` remain immutable.
The B03-A correction to selection/input protection is recorded separately in
`implementation-v2.json` and `synthetic-profile-v2.json`; use that pair for the
current checkout.

Research uses the byte-identical adapter at `tools/benchmark/benchmark_preflight.py`
with the same explicit monorepo root and the mirrored current `implementation-v2.json`.
That
manifest pins the canonical source files; a different implementation refuses to run.
No second exclusion algorithm is maintained in research.

## Validation and limits

[Verification](verification.json) records tests, synthetic replay, implementation
hashes and parser checks. Relevant master-v1 scenarios are exercised locally; race,
IAM, confirmation, worker/promotion and source-provenance scenarios remain pending.
The original 42 scenarios are still specifications, not a blanket completion claim.

Next: the private source export, complete exposure/projection indexes and durable
reservation service. Sampling/weights, the pilot, independent adjudication, sealed
access and the first real benchmark baseline follow those controls. The old 20,000-row
allocation must be revisited for three views after eligibility and pilot measurements.

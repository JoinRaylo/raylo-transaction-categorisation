# B03-C minimal membership manifest — 18 September 2026

Status: implemented locally with synthetic inputs only. This is a simplification
of the dataset-construction lookup, not a claim that the real benchmark is
admitted or historically independent.

The canonical implementation is:

- `lib/raylo-txncat/src/raylo_txncat/membership_manifest.py`
- `lib/raylo-txncat/tests/test_membership_manifest.py`

The helper sorts and validates one immutable manifest and returns `train`,
`selection`, `eval`, `excluded`, or `neither` for a canonical observation key. It
reuses the B02 HMAC observation identity and projection types.

## Evidence

- 10 focused synthetic manifest tests passed.
- The focused B02 benchmark and manifest tests passed: 101 tests.
- The startup set passed: 125 tests.
- The full canonical library suite passed: 1,138 tests.
- The app suite passed: 327 tests, 1 existing skip, and 1 existing dependency warning.
- Ruff check, Ruff format check, Python compilation, and `git diff --check` passed.
- Real rows exported: 0.
- Real rows reserved or labelled: 0.
- Provider/API calls, retraining, locked-set scoring, and cloud writes: none.
- `authorizes_consumption`: false.

## Limitation carried forward

The old training JSONL does not retain provider observation IDs. Therefore this
lookup is the correct mechanism for new datasets, but its absence result is not a
retroactive historical exposure proof. Future training and selection exporters
must carry the key; current legacy exposure remains separately qualified.

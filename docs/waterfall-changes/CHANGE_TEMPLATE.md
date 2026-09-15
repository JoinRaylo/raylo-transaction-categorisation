# CHANGE-ID — short description

Status: proposed / evaluated / rejected / accepted / staging-verified.
Created / evaluated: ISO timestamps. Owner / reviewer: names.

## Change and predeclared acceptance

- Observed failure and evidence; affected tier and exact proposed behaviour.
- Positive, negative, ambiguous and precedence cases; expected unchanged scope.
- One isolated hypothesis; baseline rollback identity; acceptance criteria.

## Reproduction and identities

- Baseline and candidate commits in both repositories; dirty patch hashes if any.
- Bundle/config/image/release and model/seed/mask/taxonomy/dictionary/rule hashes.
- Registry/dataset/adapter/harness hashes; environment lock, runtime and commands.
- Input selection, missing fields, label provenance, overlap and known limitations.

## Complete evaluation inventory

List every group and dataset in POLICY.md with its task, baseline/candidate row
counts, status, command and result path. Explain unsupported full-waterfall inputs
and retain their applicable legacy evaluations. Never silently drop a dataset.
Record that locked/retired confirmation sets were excluded from development.

| Dataset / head / slice / metric | Numerator / denominator | Baseline | Candidate | Delta |
|---|---|---|---|---|---|
| Populate from machine-readable results | | | | | |

Include all required accuracy, precision/recall/F1, coverage, risk, tier, direction,
merchant-availability and fixed-residual metrics. Report sample populations
separately. Link private row-level transitions and explain every regression.

## Verification and decision

- App/library and research tests, old/new goldens, cross-repository parity and SQL.
- Runtime/deadline impact, especially changed T5b residual volume.
- Acceptance outcome; unresolved failures; reviewer; accepted trade-offs, if any.
- Mirrored implementation revisions, aggregate files and byte/hash comparison.
- Append-only score-history entry and research current-score pointer updated.
- If promoted: staging release/rollback pins and signed API verification receipt.

An incomplete evaluation remains incomplete; do not use the template as evidence
that its checks have run.

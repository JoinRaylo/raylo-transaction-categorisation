# B03-C ID-bearing training membership — 18 September 2026

This milestone implements the small train/selection/eval/neither lookup agreed
with Carlos while preserving the source and split protections needed for the next
candidate draw.

## Changed files

- `src/training_membership.py`
- `src/build_tuning_dataset.py`
- `tests/test_training_membership.py`
- `docs/benchmark-implementation/b03-c-id-bearing-training-membership-2026-09-18/`
- current-state entries in `README.md`, `CLAUDE.md` and `docs/project-summary.md`

## Result

- Future Tier-B fetches retain Plaid `account_id` and `transaction_id`.
- The fetch uses only the reviewed unambiguous customer-linked Plaid chain.
- Model JSONL remains the existing `messages`-only format.
- A separate private CSV maps exact provider IDs to `train` or `selection` and is
  ready to carry `eval`/`excluded` rows in later construction.
- A coverage JSON reports every legacy effective row whose identity is unavailable.
- Cross-role reuse and changed-payload reuse of an exact provider identity fail.
- Prior exact assignments are retained and verified across rebuilds; model and
  lookup hashes are committed together through a coverage marker.
- Repeated assessment rows are accepted only when their model payload agrees;
  changed variants are excluded before deterministic sampling.
- Existing pre-ID Tier-B extracts fail closed and must be fetched again.

## Verification

- Research test suite: **89 passed**.
- Focused synthetic sidecar tests: **15 passed**.
- Canonical B02/B03 membership regression: **101 passed**.
- Python compilation: passed.
- `git diff --check`: passed.
- BigQuery dry run: passed, EU, SELECT only, zero rows returned,
  7,657,197,083 bytes processed upper bound.
- Independent Astra review: **approved with no remaining findings** after three
  correction rounds covering publication order, source-payload provenance,
  rebuild permanence, upload verification, temporary-file cleanup and portable
  artifact names.

## Non-actions and limits

No real transaction row was returned, downloaded, reserved or labelled. No
provider annotation call, cloud mutation, model fit, model selection, locked-set
access or score occurred. The lookup does not repair missing IDs in historical
curated CSVs and does not make lookup absence proof of historical non-exposure.
Publication is intentionally single-writer, and every consumer must verify the
coverage hashes. GCS upload behaviour was exercised with synthetic mocks, not a
live upload.

The next bounded operation is the private candidate export and allocation, with
evaluation assigned before any new training rows.

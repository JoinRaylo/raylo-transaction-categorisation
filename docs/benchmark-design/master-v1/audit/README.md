# Supporting audit provenance

These four files are byte-for-byte copies of the read-only dataset review completed
on 15 September 2026, before the benchmark design. They provide evidence about the
**existing** evaluation suite, not a new benchmark or fresh model accuracy scores.

- [REPORT.md](REPORT.md): findings, limitations and initial size recommendations.
- [coverage.json](coverage.json): source hashes, aggregate counts and per-label support.
- [validation.json](validation.json): independent count checks and source-code hashes.
- [audit.py](audit.py): exact historical audit script; it performs no model inference.

The script records the local app/research paths used for that audit. Reproduction
requires those permitted source snapshots and the app's evaluation dependencies:

```sh
PYTHONPATH=/private/tmp/txncat-d2-worktree/apps/ob-txn-categoriser/src:/private/tmp/txncat-d2-worktree/lib/raylo-txncat/src \
  /private/tmp/txncat-c2-env/bin/python \
  /private/tmp/txncat-d2-worktree/apps/ob-txn-categoriser/research/benchmark-design/master-v1/audit/audit.py
```

It writes `/private/tmp/txncat-dataset-audit-20260915.json`; the timestamp changes.
Check the pinned source hashes before comparing counts. If local paths differ, use
a separately saved adapted script and record its new digest; do not change the
historical script and claim the old script hash. B01 should provide a portable
inventory command as implementation work.

No raw transaction examples, customer linkage or locked-set contents are present
in these audit reports. The original permitted-source hashes and coverage digest
remain unchanged. The parent [design](../DESIGN.md) refines the original audit's
planning recommendations, including the explicit 200-row critical-leaf target.

# Reproduction and private objects

Use the source versions in `implementation.json`. The shared curation and identity
primitives live in the monorepo; research mirrors the executable adapters under
`tools/benchmark/`, importing the same package. For research replay, include
`tools/waterfall-evaluation/` on `PYTHONPATH` for the existing evaluation adapter
and metrics. Do not fork the scoring or projection rules between repos.

The audit environment needs numpy, scipy, sklearn/joblib, tokenizers, transformers
and pyarrow, plus the existing shared package. Only warehouse queries need the
BigQuery client and the existing read-only credentials. Artifact paths and hashes
are fixed by B01; model/tokenizer/vectorizer loading is local and digest-checked.
No model inference, fitting or labelling is performed by these audit commands.

## Historical cohort

The initial curation reads only the permitted fixed registry/inventory and the
verified cached 15 September baseline. Use new output paths; overwriting a v1
membership object or adjudicating its labels in place is not supported.

```sh
python benchmark_curate_legacy.py \
  --monorepo /path/to/monorepo --research /path/to/research \
  --baseline /private/path/baseline \
  --key-file /private/path/source/identity.key \
  --key-id benchmark-private-20260916-v1 \
  --output /private/path/historical-regression-v1

# After each complete permitted evaluation run, score the SAME frozen cases:
python benchmark_score_legacy.py \
  --cohort /private/path/historical-regression-v1 \
  --run /private/path/completed-evaluation-run \
  --output /private/path/new-historical-scores.json
```

The second command needs neither the identity key nor the original datasets; it
validates the frozen member file and the completed run's source/prediction receipt.
It does not replace the full evaluation harness or existing paired comparison.
Keep original dataset-level scores alongside the curated diagnostic views.

## Identity and exposure

The existing B02 source snapshot remains immutable. Each SQL query is SELECT-only,
parameterized with its retained identifiers, bounded to the configured source where
applicable, dry-run-checked and capped at 20 billion billed bytes. Rerunning queries
later creates new time-specific evidence; offline replay uses retained result files.

```sh
python benchmark_identity_query.py --source /private/path/source \
  --sql benchmark_identity_links.sql --output /private/path/links
python benchmark_identity_query.py --source /private/path/source \
  --sql benchmark_identity_report_ids.sql --output /private/path/report-ids
python benchmark_identity_query.py --source /private/path/source \
  --sql benchmark_identity_accounts.sql --output /private/path/accounts
python benchmark_reconcile_identity.py --source /private/path/source \
  --links /private/path/links --reports /private/path/report-ids \
  --accounts /private/path/accounts --key-file /private/path/source/identity.key \
  --output /private/path/identity
python benchmark_screen_exposure.py --source /private/path/source \
  --research /path/to/research --inventory /path/to/b01/local_inventory.json \
  --legacy /private/path/historical-regression-v1 \
  --key-file /private/path/source/identity.key --output /private/path/effective
python benchmark_verify_exposure.py --source /private/path/source \
  --index /private/path/b02-index --screen /private/path/effective \
  --research /path/to/research --key-file /private/path/source/identity.key \
  --output /private/path/effective/verification.json
python benchmark_screen_merchants.py --source /private/path/source \
  --research /path/to/research --inventory /path/to/b01/local_inventory.json \
  --legacy /private/path/historical-regression-v1 \
  --key-file /private/path/source/identity.key --output /private/path/merchants
```

The 32-byte HMAC key is local, owner-only and never printed. Its key ID is a version
label, not permission to create a different key with that same label. An index
reader verifies the key as well as the index digest. Keep raw rows, narratives,
identity maps, member IDs and conflict queues outside Git and public evidence.
The private objects are engineering evidence, not permission for any learning or
benchmark consumer to ingest them. Hashes provide integrity, not access control.

Successful final artifacts are retained locally outside the repos in an owner-only
archive under `~/.local/share/raylo-txncat/benchmark-engineering/2026-09-16/`.
This removes dependency on temporary working copies; it is **not** the managed
encrypted storage, retention, access controls or atomic membership service required
by B03. Original research/model files remain at their pinned source paths. The
large B02 exact index is reproducible with its existing builder/receipt and remains
in its earlier private location. The local archive includes its receipt and all
new evidence, source snapshot/key, frozen cohort and cached baseline predictions.

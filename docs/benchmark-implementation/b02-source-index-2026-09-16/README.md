# B02 private source and input-presence index

This increment establishes a real, private engineering source snapshot and a
disk-backed index of preserved learning/selection inputs. It does **not** create,
reserve, label or certify the master benchmark. The three approved views remain
as defined in [B02 initial](../b02-initial/CONTRACT_AMENDMENT.md).

Read [REPORT.md](REPORT.md) for findings, limits and next work.
`source-receipt.json` binds the bounded warehouse SELECT; `source-profile.json`
contains aggregates only. `index-receipt.json` records the preserved source hashes
and projections; `overlap-verification.json` checks the index against B01.
`implementation.json` pins the shared code and adapters used for reproduction.
`verification.json` records tests, replay and evidence checks.

Raw observations, the HMAC key and the SQLite index remain outside both repos.
They are sensitive local engineering artifacts, not distributable evaluation sets.
Public receipt hashes bind their private bytes without publishing their contents.

## Reproduction

Use the trusted monorepo checkout matching `implementation.json`. The research
repo mirrors the five `benchmark_*` source/index adapters (including SQL) in
`tools/benchmark/`; all import the same canonical `raylo_txncat` implementation
from the monorepo. Do not fork the projection or index code in research.

The extract needs the existing BigQuery Python client and read-only credentials.
The index build needs pyarrow, numpy and the shared package. Set `PYTHONPATH` to
`<monorepo>/lib/raylo-txncat/src` and the adapter directory. No model weights,
tokenizer fitting or model inference are involved.

```sh
# New output directories only. Dates/limits are engineering scope, not admission.
python benchmark_extract.py --source-day 2026-09-15 --request-limit 100 \
  --output /private/path/source --execute
python benchmark_build_index.py --research /path/to/research \
  --inventory /path/to/b01-2026-09-15/local_inventory.json \
  --key-file /private/path/source/identity.key --key-id your-private-key-version \
  --create-key --output /private/path/index
python benchmark_profile_source.py --source /private/path/source \
  --index /private/path/index --key-file /private/path/source/identity.key \
  --output /private/path/profile.json
python benchmark_verify_index.py --research /path/to/research \
  --audit /path/to/b01-2026-09-15 --index /private/path/index \
  --key-file /private/path/source/identity.key --output /private/path/checks.json
```

Rerunning the warehouse query later creates a **new snapshot**, even with the same
parameters. Reuse the retained private extract for byte-identical profiling.
Never paste the key or private row content into tickets, prompts or PRs. Before
moving this beyond engineering, define durable encrypted storage, access and
retention for the key/data; the `/private/tmp` copies are not a managed archive.

This offline tool reports evidence of presence. Its `complete` flag means the
declared index build finished, **not** that ancestry is complete. All three history
completeness flags and `authorizes_consumption` remain false. `not_found` applies
only to that indexed projection and those named sources.

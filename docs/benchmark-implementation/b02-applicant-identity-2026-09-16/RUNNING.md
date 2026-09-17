# Reproducing the bounded identity probe

The SQL and runner beside this file are the exact sources pinned in
`executed_receipt.json`. Python 3.12+ and `google-cloud-bigquery` are required
for a warehouse rerun, with existing read-only credentials for
`raylo-production` in `EU`. No service key or cohort identifier belongs here.

Run the offline checks from this directory without cloud credentials:

```sh
python verify_runner_offline.py
```

The private input directory must contain `links/rows.jsonl` and
`links/receipt.json` from the retained 16 September engineering archive.
The runner validates the fixed file SHA, 99 assessment/checkout rows, and
49 unique missing-user checkouts. Supply the directory explicitly:

```sh
python run_applicant_identity_coverage.py --links-dir /path/to/private/archive --output-dir /path/to/private/identity-probe
```

That command performs a dry-run only. Add `--execute` to rerun the aggregate:

```sh
python run_applicant_identity_coverage.py --links-dir /path/to/private/archive --output-dir /path/to/private/identity-probe --execute
```

Every execution first checks a SELECT-only dry-run and its estimate, then
applies the 20,000,000,000-byte billing limit to the data query. It binds the
49 checkout IDs privately as a query parameter; only integer aggregates and
source/job metadata are saved. Do not print the parameters or raw input.
A future query reads then-current warehouse data and may legitimately differ;
preserve a new receipt rather than replacing this dated evidence.

The seven standalone checks use synthetic rows and a fake BigQuery client.
They cover the fixed denominator, file tampering, malformed/duplicate IDs,
non-SELECT input and query jobs, the dry-run budget and invalid result counts.
They do not establish SQL semantic correctness; that was checked separately
by source review, a live dry-run and the bounded aggregate result.

Raw rows, identity keys and any candidate/contact values remain outside Git.
This audit does not authorize benchmark admission or replace the pending
historical linkage, alias, family, B03 reservation and B04 consumer controls.

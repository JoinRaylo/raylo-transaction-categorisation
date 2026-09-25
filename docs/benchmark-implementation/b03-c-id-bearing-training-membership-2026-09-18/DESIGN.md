# B03-C ID-bearing training membership

## Decision

Keep the existing model JSONL schema unchanged and write one separate private
lookup keyed by the exact Plaid `account_id` and `transaction_id`:

```text
provider + account_id + transaction_id -> train | selection | eval | excluded
```

`src/build_tuning_dataset.py build` currently emits the `train` and `selection`
memberships. Future evaluation construction uses the same four-role vocabulary.
An ID absent from the lookup is `neither` only within an ID-complete export. It is
not proof that a legacy row was never used.

## Source boundary

Future Tier-B fetches no longer read eligible merchants from the broad Plaid table
alone. The query first applies the approved existing assessment -> checkout ->
user -> customer chain and requires exactly one link at each stage. Those verified
assessment rows are also the source of the model payload. Repeated
`(account_id, transaction_id)` rows are collapsed only when every linked
assessment has the same model-visible payload; changed-payload variants are
excluded before sampling. The query returns no customer ID and performs no
anonymous recovery.

The source query now returns both provider IDs and uses a stable hash ordering
instead of `RAND()`. BigQuery compiled the query successfully in a dry run. The
dry run returned no rows and reported a 7,657,197,083-byte upper-bound scan for one
merchant chunk.

## Sidecar contract

`src/training_membership.py` keeps one strict source record beside each in-memory
model example. It writes:

- `outputs/tuning_membership_lookup.csv`: one row per unique exact Plaid identity,
  with its permanent role, source-row digest and current-export oversampling count;
- `outputs/tuning_membership_coverage.json`: exact and unresolved effective-row
  counts by role/source, plus the lookup digest and explicit limitations.

The model JSONL writer serialises only the existing `messages` object. Raw provider
IDs never enter the model input. Reusing one exact ID across roles, sources or
changed source payloads fails closed. Repeated copies of the same source row in the
same role collapse to one lookup row with an explicit count.

Publication validates the complete export before replacing any output. Existing
lookup/model hashes and permanent assignments are checked on every rebuild;
previous exact identities stay in the lookup even when absent from the current
model file. Four staged files are then replaced with the coverage JSON last as the
commit marker. Its hashes bind the lookup and both model JSONL files, so an
interrupted multi-file replacement is detected rather than consumed. Merchant
train/selection assignment is a stable hash, not a reshuffle of the current pool.

## Historical limit

Most older curated files do not contain provider transaction IDs. Their rows keep
their real source/provider and a deterministic source-row digest, but have
`identity_status=unavailable` and do not enter the exact-ID lookup. In particular,
an existing `outputs/tuning_txns.json` made by the old fetcher cannot be rebuilt
under this contract; it must be fetched again to obtain exact IDs.

This is intentionally not a retrospective identity-recovery project. It does not
claim complete historical exposure, and it does not read the retired or locked
confirmation sets.

## Relationship to the canonical app contract

The lookup preserves the exact provider/account/transaction tuple consumed by the
canonical B02 `observation_key` function. The private raw-ID table is the simple
operational join requested for dataset construction; a keyed canonical B03
membership manifest can be derived from it without changing model files. Neither
artifact is consumption authority.

## Next step

Use the lookup as the exclusion input for a fresh private customer-linked Plaid
candidate export. Assign evaluation rows before training additions, retain the
customer/account/input/family block fields needed by the existing allocator, and
only then send the 500-row pilot for independent annotation. No provider call,
real label, retrain or locked-set score occurred in this milestone.

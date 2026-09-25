# B03-C minimal membership manifest

## Decision

Use one small, immutable membership manifest as the operational lookup for dataset
construction. It answers only:

```text
canonical Plaid observation key -> train | selection | eval | excluded | neither
```

An absent key is `neither`. Evaluation view tags (`representative`, `unseen_input`,
and `unfamiliar_merchant`) live on an `eval` entry rather than in three separate
tables. This is the simpler representation Carlos requested and is sufficient for
keeping newly constructed rows out of the wrong data role.

## Entry contract

Each entry contains:

- `observation_key`: the existing B02 HMAC identity of the provider namespace,
  account ID, and transaction ID. A bare `transaction_id` is not sufficient because
  provider IDs are account-scoped.
- `role`: exactly one of `train`, `selection`, `eval`, or `excluded`.
- `views`: zero or more evaluation views; only `eval` entries may have them.
- `source_snapshot_sha256`: the pinned source snapshot for this entry. Train and
  evaluation rows may come from different snapshots.
- `row_sha256`: the canonical row/payload hash, used to detect changed content
  without changing the observation identity.
- B02 input projections and, where needed, a reviewed merchant-family key.
- a short reason code.

The manifest is sorted by observation key, rejects duplicate keys, and has a
content digest. Assignment happens before labels are requested. A changed row
payload is a content mismatch; it is not silently treated as a new member.

## Storage and use

The table/object holding the manifest is private and versioned. A BigQuery or
immutable object representation is appropriate for the data volume; Firestore is
not needed for one document per transaction. The application join is a simple
lookup/left join against the pinned manifest. The local implementation is a typed
serializer/lookup helper and never authorizes consumption.

The existing B03 authority protocol remains the future concurrency boundary if
multiple writers or training workers need to update membership at once. It is not
required for the first synthetic manifest or for ordinary read-only joins.

## Deliberate limits

This manifest proves membership in the manifest, not historical completeness. The
existing supervised JSONL exports do not retain provider observation IDs, so absence
from this new manifest cannot retrospectively prove that an old training row was
never seen. Until training exports carry the same observation key (or a documented
prospective cutoff is frozen), the unseen-input/customer claims remain qualified.
Pending/posted and reconnect aliases also need explicit source evidence before they
can be collapsed into one event family. No real row, label, provider call, retrain,
or locked-set score is part of this milestone.

## Next concrete dataset step

1. Freeze the training/selection snapshot and make future training exports carry
   `observation_key` plus `row_sha256`.
2. Extract a private customer-linked Plaid candidate pool with the same key.
3. Assign the pilot/evaluation rows in one versioned manifest before sending any
   annotation prompts; keep the remaining candidate pool as `neither`.
4. Annotate only the manifest's `eval` rows with the three independent providers,
   and route disagreements to Carlos. The pilot remains excluded from training.

# B03-B candidate event-lineage evidence

Status: **candidate lineage evidence captured; no candidate admitted**.

This packet records a bounded, private evidence pass over the customer-linked
Plaid candidate draw. It is an admission input, not an admission decision. The
runner and summary always report `authorizes_consumption=false` and
`rows_reserved_or_labelled=0`. No provider, human, training, selection,
locked-set, scoring or retraining operation was started.

## Exact inputs and execution

- Candidate source: `raylo-production`, EU, customer-linked Plaid materialization
  only; anonymous-ID recovery was not attempted.
- Candidate draw: seed `b05-pilot-source-v1`, 5,000 distinct
  `(account_id, transaction_id)` events, result SHA-256
  `f9c549ee7a8a6bbfaec8999d3edaf2dca22f0d4f4fa463a486dcc3fd5a8f32ef`.
- Bound candidate profile SHA-256:
  `04efff789eadd9bbae635109bd15be80e34164bf8132e1d78f7bacbce2eb7ec5`.
  The profile itself is non-authorizing and has no complete-history claim.
- Query: SELECT-only, parameterised by the exact candidate account and
  transaction key sets, with assessment → checkout → user → customer linkage
  checks on the current materialization. The older materialized Plaid history
  is joined only for the selected keys.
- BigQuery job:
  `txncat_lineage_8ce6f2bc-eaf9-420d-8e91-53bfde392e69`.
- Estimated/processed bytes: `10,033,362,010`; billed:
  `10,033,823,744`; maximum allowed: `20,000,000,000`.
- SQL SHA-256:
  `d610ec954cf57ce98d3030b318e5844df405592174bd7da50c0a045c43b14a13`.
- Runner SHA-256:
  `2ab924f67f6747f0217c1d5261e66b28d69a73d8dcd13ee8f1dc45da4f5a0311`.
- Private lineage result: 5,636 rows, SHA-256
  `030d239d3e361e81750bc77ee0b1e97969e9d13a2eece588f3cd780385418ae4`.
  The rows remain outside both repositories in a mode-`0600` private output
  directory; no row payload or identifier was committed here.
- Aggregate summary SHA-256:
  `bdd27e236240b84c82e11f744e88fd49a29c7683255dd5eafe600c043815c00e`.
- Final private receipt SHA-256:
  `3dd947de67d7474ec275dc60696d93f23b93e8c61a20faf5026974a82bfc76c9`.

The source tables were the current materialized transaction table, the older
materialized Plaid history table, and the existing assessment, checkout, user
and customer link relations. The exact source metadata, job receipt and
private row hash are retained with the operator's private evidence, while this
packet contains only aggregate facts and integrity digests.

## Aggregate observations

- All 5,000 candidate events had at least one selected-lineage row. The result
  contained 4,672 accounts and 4,542 customer IDs; selected lineage per account
  ranged from 1 to 4 rows. This is **candidate-event lineage**, not complete
  account/report history.
- Source rows were 5,000 current-materialized rows and 636 older Plaid-history
  rows. There were 636 repeated source observations and 636 source-metadata
  variants in the selected keys, while comparable transaction content variants
  numbered 0. The repeated observations and metadata differences still require
  alias review; they are not proof that a transaction ID is an economic-event
  alias.
- Five selected events had a pending state in the available history; none had
  both pending and posted states in this extract. Neither source exposes a
  `pending_transaction_id`, so pending/reconnect alias resolution is not
  certified.
- No selected account had multiple linked customer IDs in the returned
  lineage, but 121 customer IDs had multiple candidate accounts. The source
  and query scope do not prove complete historical identity coverage.
- Candidate blocks were 4,672 account groups (maximum 4 rows), 4,542 customer
  groups (maximum 5 rows), and 4,542 assignment groups (maximum 5 rows). These
  are evidence for later whole-block allocation, not permission to allocate.
- No reviewed merchant-family index was supplied. Exact merchant-name absence
  is not evidence of unfamiliar-family absence.

## Admission result

The eligible count is **0**. The evidence remains explicitly non-authorizing
because these blockers are unresolved:

1. pending/reconnection aliases are unverified;
2. historical identity completeness is not certified;
3. the effective-input history profile is non-authorizing;
4. the reviewed merchant-family index is missing;
5. legacy protected-membership migration is missing; and
6. managed reservation and consumer gates are not authorizing.

The private query was deliberately limited to exact candidate account and
transaction parameter sets. It did not read the raw report stream or establish
full account history, complete training/selection exposure, view-specific
novelty, sampling weights or a family absence certificate. Local summaries do
not turn those unknowns into an allow.

## Attempt and mutation record

An unused fresh candidate draw was completed during setup but was not admitted
or used because its exact exposure profile was not recomputed. An earlier
account-only lineage attempt was abandoned after its estimated result exceeded
the local lineage-row guard; a later bounded run was corrected for receipt
serialization before the final hash-bound execution. These private attempts
made no authority or source mutation and are not admission evidence.

The final execution performed no BigQuery writes or destination-table writes,
and created no authority objects or documents. It reserved or labelled zero
rows, made zero provider calls, read no locked evaluation set, and changed no
training, selection, model, score or deployment state.

## Independent review

Astra (Rawls) performed a second read-only review after the first review's five
findings were corrected. The final review approved the exact paired-key query,
pre-write candidate coverage/customer checks, strict boolean and profile
validation, separate content/metadata signals, final receipt hashes and
byte-identical app/research mirrors, with zero remaining actionable findings.
Private files remain mode `0600`; admission remains blocked and complete raw
history, aliases and merchant-family evidence remain explicitly unproven.

## Next gate

Before any real reservation, obtain an approved source/sidecar that exposes
pending/reconnection aliases and complete report lineage (or a prospective
cutoff that makes completeness explicit), rerun the candidate-level exposure
and novelty checks, add the reviewed merchant-family index and legacy
membership mapping, and pass the managed reservation/consumer gate. Only then
can a 500-row manifest be reserved for the three independent annotators.

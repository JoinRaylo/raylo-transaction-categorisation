# B03-D synthetic candidate allocation

Status: **complete bounded local milestone; synthetic only; non-authorizing**.

The app worktree now contains a strict deterministic allocator for opaque
candidate blocks. It exercises the next step in creating evaluation views:
reserve whole identity/projection blocks in a declared order, keep pilot,
benchmark, selection and training roles disjoint, and preserve the approved
distinction between representative recurrence and strict input/family novelty.

This is a planning contract, not a real evaluation-set builder. It accepts no
transaction payload, source ID, URI, cloud client, authority receipt or
production environment binding. The candidate type is limited to a named
synthetic fixture and the result carries `scope="synthetic_only"` and
`authorizes_consumption=false`. No BigQuery query, Firestore write, Cloud
Storage write, label, model fit, locked-set access, score or retrain occurred.

## Implementation and evidence

- Contract: `lib/raylo-txncat/src/raylo_txncat/benchmark_allocation.py`
- Adversarial tests: `lib/raylo-txncat/tests/test_benchmark_allocation.py`
- Design mapping: [`DESIGN.md`](DESIGN.md)
- Source hashes and actual verification: [`implementation.json`](implementation.json), [`verification.json`](verification.json)

The contract uses the canonical B02 frozen models and projection/view types. It
requires one source snapshot and policy version, rejects ineligible or
contradictory candidates, validates event/account/customer blocks, rejects
strict-view input collisions even inside an indivisible block, and binds the
result to a canonical digest of prior assignments. Budgets are a strict role
vocabulary and must be ordered before training. Exact block-capacity failures
and non-exact shortfalls are explicit.

The bounded backtracking selection helper is suitable only for synthetic
fixtures and small planning previews. A real admission job must do equivalent
group/block assignment in a bounded warehouse query or reviewed streaming
planner; it must not load the full customer pool into this process.

## Review and next gate

Sol and Astra independently returned conditional approval for this synthetic
milestone. They agreed that the unresolved effective IAM and authority gate is
unchanged. The next real-data action is therefore still gated: obtain the
security/infra effective-access attestation, then run a fresh linked-only
admission profile, commit the 500-row pilot reservation through the managed
authority, and submit one independent batch annotation per approved provider.
The three model annotations remain method evidence only; disagreements are not
auto-adjudicated. Final evaluation labels still require two independent human
labels plus Carlos's adjudication.

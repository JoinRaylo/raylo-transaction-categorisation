# Synthetic Stage 0–3 proof plan

Status: **specified, not executed**. This plan is the next gate after the
runtime identity/binding milestone. It does not authorize fixture creation,
Cloud Run enablement, key rotation, customer-data access or benchmark
consumption.

## Pinned proof namespace and principals

- Synthetic namespace: `synthetic-stage0-20260918-v1`.
- Authority writer: `txncat-authority-writer`, unique ID
  `110799062502316526083`.
- Receipt verifier: `txncat-receipt-verifier`, unique ID
  `102004524245181644069`.
- Learning worker: `txncat-learning-worker`, unique ID
  `103294586886679890509`.
- Selection worker: `txncat-selection-worker`, unique ID
  `111373158714103570704`.
- Synthetic contract-test audience: `https://synthetic-verifier.example`.
- Live verifier audience: the exact private Cloud Run service URL, to be pinned
  before deployment; no live service currently exists.
- Live image digest, deployment identity, disposable signing version, retention
  owner and audit-log owner: not yet selected; these are execution
  prerequisites, not placeholders to be invented during the proof.

## Stage 0 — fixture/bootstrap

A separately approved fixture owner creates only synthetic objects and registry
documents in the namespace: an index, one committed learning operation, one
committed selection operation, one pending operation, one held/revoked
operation, one orphan object, one opposite-plane object and an alias evidence
object. A separately approved key administrator selects a disposable signing
version. The fixture manifest records names, generations, digests, epochs and
key version, never transaction narratives or customer identifiers.

Expected bootstrap facts:

- only the authority writer can create the synthetic authority objects and
  registry mutations;
- the registry stores pointers and operation metadata, not row payloads;
- no object is reachable by a worker solely because it exists in the bucket;
- fixture cleanup/retention ownership is recorded before any write.

## Stage 1 — no-write identity and direct-read proof

Run each identity against the same fixtures without creating, updating,
deleting, rotating or retiring anything.

| Identity | Expected allow | Expected deny or absence |
| --- | --- | --- |
| authority writer | exact authority object create/readback; named registry lookup/write; receipt signing | list, delete, update, sealed objects, serving/training reads, worker fallback |
| receipt verifier | exact committed worker object through receipt-bound path; named registry lookup; receipt public-key/state read | direct generic object path, authority/private/sealed objects, list, mutation, signing |
| learning worker | authenticated verifier invocation for learning receipt | direct Storage/Firestore/KMS access, selection/sealed objects, cross-kind receipt |
| selection worker | authenticated verifier invocation for selection receipt | direct Storage/Firestore/KMS access, learning/sealed objects, cross-kind receipt |

The verifier itself must successfully read an allowed worker object; the
worker's direct generic read must fail. Test allowed, pending, held/revoked,
orphan and opposite-plane references, plus learning/selection prefix
substitution. Forged, forwarded, audience-swapped and role-swapped token
claims must fail against the immutable unique-ID mapping.

## Stage 2 — cross-process mutation and CAS proof

Two independent authority processes use the same synthetic epoch. For
conflicting proposals, exactly one operation commits and the other returns an
explicit stale/conflict result. The losing retry must reread the index and
rerun policy. For non-conflicting proposals, both commit serially. An identical
lost-response retry returns the original operation without a duplicate epoch.
An after-commit alias joining a protected and learned group must hold
certification and retain the earlier exposure.

## Stage 3 — failure, retention and key lifecycle

Exercise an orphan upload, failed registry CAS, held/revoked operation,
contamination alias and disposable signing-key rotation/retirement. Each
affected read fails closed; no orphan or historical membership is deleted by a
cleanup shortcut. Evidence records the caller unique ID, operation ID, object
name/generation/digest, registry epoch, key version and outcome only.

## Execution blockers

The plan remains unexecuted because Cloud Run is not enabled/deployed, the live
audience and image digest are not pinned, and separate approval is needed for
synthetic fixture/bootstrap and disposable-key mutations. The runtime
identities and IAM bindings alone do not authorize real rows, labels,
reservations, provider calls, training or locked-set scoring.

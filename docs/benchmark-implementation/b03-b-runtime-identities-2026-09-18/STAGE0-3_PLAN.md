# Synthetic Stage 0–3 proof plan

Status: **bounded live proof executed and passed synthetically on 2026-09-18**.
This plan records the live proof after the runtime identity/binding milestone.
The extended writer/key-rotation cases remain deferred, and nothing here
authorizes customer-data access or benchmark consumption.

## Pinned proof namespace and principals

- Synthetic namespace: `synthetic-stage0-20260918-v3`.
- Authority writer: `txncat-authority-writer`, unique ID
  `110799062502316526083`.
- Receipt verifier: `txncat-receipt-verifier`, unique ID
  `102004524245181644069`.
- Learning worker: `txncat-learning-worker`, unique ID
  `103294586886679890509`.
- Selection worker: `txncat-selection-worker`, unique ID
  `111373158714103570704`.
- Synthetic contract-test audience: `https://synthetic-verifier.example`.
- Live verifier audience: the exact private Cloud Run service URL, pinned in
  the execution receipt after deployment.
- Object paths are permanently namespaced under
  `_authority/synthetic-stage0-20260918-v3/`,
  `worker/learning/synthetic-stage0-20260918-v3/` and
  `worker/selection/synthetic-stage0-20260918-v3/`. Private canaries use
  `private/synthetic-stage0-20260918-v3/`.
- Firestore collections are
  `txncat_synthetic-stage0-20260918-v3_registry`,
  `txncat_synthetic-stage0-20260918-v3_proposals` and
  `txncat_synthetic-stage0-20260918-v3_operations`; only the current
  synthetic namespace uses them.
- The live image digest, deployment identity, manifest generation/digest,
  proof owner and retention/audit ownership disposition are recorded in the
  retained receipt; deferred controls are named rather than invented.

## Stage 0 — fixture/bootstrap

A separately approved fixture owner creates only synthetic objects and registry
documents in the namespace: an index, one committed learning operation, one
committed selection operation, one proposal-only pending operation, one
contaminated operation, one orphan object, one opposite-plane object and an
alias evidence object. There is no `revoked` operation state in the canonical
model: `committed` + `exposed` + `certification=held` is the normal allowed
state, while `certification=contaminated` must deny. A separately approved key
administrator selects a disposable signing version. The fixture manifest
records names, generations, digests, epochs and key version, never transaction
narratives or customer identifiers.

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
| receipt verifier | exact committed worker object through receipt-bound path; named registry lookup; receipt public-key/state read | private/authority/sealed objects, list, mutation, signing; no generic read endpoint is exposed |
| learning worker | authenticated verifier invocation for learning receipt | direct Storage/Firestore/KMS access, selection/sealed objects, cross-kind receipt |
| selection worker | authenticated verifier invocation for selection receipt | direct Storage/Firestore/KMS access, learning/sealed objects, cross-kind receipt |

The verifier itself must successfully read an allowed worker object; the
worker's direct Storage, Firestore and KMS calls must fail. The verifier's
underlying Storage identity necessarily has `storage.objects.get` on the two
worker prefixes; that is an application-boundary capability, not a claim that
IAM alone prevents the verifier from reading those objects. Test allowed,
proposal-only, contaminated, orphan and opposite-plane references, plus
learning/selection prefix substitution. Forged, wrong-issuer, wrong-audience,
unknown-subject and role-swapped token claims must fail against the immutable
unique-ID mapping. A valid token/receipt pair forwarded by a caller is not
distinguishable from the original caller by this design; do not claim generic
forwarding prevention.

## Stage 2 — cross-process mutation and CAS proof

Two independent authority processes/clients use the same synthetic epoch. For
conflicting proposals, exactly one operation commits and the other returns an
explicit stale/conflict result. The losing retry must reread the index and
rerun policy with a **new operation ID**. For non-conflicting proposals, both
commit serially. An identical lost-response retry returns the original
operation without a duplicate epoch. An after-commit alias joining a protected
and learned group must hold certification and retain the earlier exposure.

The executed v3 live race used two non-conflicting prepared proposals, a
process barrier immediately before the real registry transaction, and the same
expected epoch. Both contenders therefore reached the Firestore CAS boundary;
the observed outcomes were exactly one `committed` and one `stale_epoch`. The
loser was reprepared with a new operation ID, committed at the next epoch, and
the exact original retry returned `already_committed`. Conflicting-proposal
contention and the full non-conflicting serial matrix remain deferred.

## Stage 3 — failure, retention and key lifecycle

The executed v3 proof exercised an orphan upload, a pending proposal,
contaminated operation/alias, changed reference, failed registry CAS,
receipt-key disable and recovery. Each exercised read failed closed; disabling
the active signing version returned 503/unavailable rather than a cached allow,
and re-enabling it restored a valid 200 read. No orphan or historical
membership was deleted by a cleanup shortcut. Live writer restriction probes,
unknown-subject/forged-token probes and signing-key rotation/retirement are
deferred. Evidence records only synthetic caller/operation/object metadata,
registry epochs, key version and outcome.

## Execution blockers

The synthetic fixture/bootstrap, bounded disposable-key disable/recovery and
Cloud Run identity actions completed. Cloud Run was used only to obtain the
approved service-account identities without creating user-managed keys; it is
not required for the offline protocol semantics. The runtime identities, IAM
bindings and synthetic proof do not authorize real rows, labels, reservations,
provider calls, training or locked-set scoring. The next gate is fresh
linked-only admission evidence; the deferred live proof cases are a separate
hardening follow-up, not an authority grant.

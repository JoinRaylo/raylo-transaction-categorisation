# Synthetic live-proof design

Status: **bounded synthetic live proof passed on 2026-09-18; the deferred
extended matrix and real admission remain closed**.

The canonical runtime is
`apps/ob-txn-categoriser/scripts/benchmark_authority_live_proof.py`. The
deployment context contains only that runtime, a wheel built from the
canonical `raylo-txncat` package, and pinned infrastructure dependencies. It
accepts no customer payloads and writes only deterministic synthetic objects
under the explicitly configured namespace `synthetic-stage0-20260918-v3`.

## Runtime split

- An authority-writer Cloud Run job bootstraps the empty index, synthetic
  evidence, learning/selection claims, a proposal-only pending claim, an
  orphan, a contamination alias and a two-process Firestore CAS race. It is
  the only component that creates or updates authority objects/documents and
  signs receipts.
- A receipt-verifier Cloud Run service runs the canonical
  `ProductionAuthorityVerifier` with the verify-only KMS adapter. It exposes
  exactly one HTTP operation: a worker supplies an operation, immutable object
  reference and signed receipt; the service returns only a digest and size.
  There is no generic object-read or receipt-issuance endpoint.
- Learning and selection worker Cloud Run jobs obtain their own Google identity
  tokens from the metadata server. Each first attempts direct Storage,
  Firestore and KMS access, which must be denied, then calls the verifier. The
  successful verifier response proves application-level receipt binding, not
  that the verifier's own object-get permission is absent.
- A verifier probe runs under the receipt-verifier identity and must be denied
  private-object reads, Firestore mutation and KMS signing.

Cloud Run is used for this live pass because the local operator cannot mint
tokens for the keyless service accounts. The offline protocol tests remain
valid without Cloud Run; deployment is not treated as a substitute for those
tests.

## Expected outcomes

The committed/exposed/held learning and selection claims return only through
the matching worker identity and receipt. In the bounded live matrix,
proposal-only, contaminated, opposite-plane, orphan, changed-reference,
wrong-audience and role-swapped requests returned denied/unavailable without
bytes. The receipt-verifier's KMS sign attempt and worker direct data-plane
calls returned permission denied. Live writer list/delete/update restrictions,
unknown-subject/forged-token probes and signing-key rotation/retirement remain
deferred rather than implied by these results.

The live proof records only service-account unique IDs, operation IDs,
generations, SHA-256 digests, epochs, key version and status. It records no
transaction narrative, customer identifier or raw payload.

## Observed execution

The writer completed in Cloud Run execution
`txncat-proof-bootstrap-v2-8gfz2`. The final image digest was
`sha256:9ee6f539ab3ac1760e87e3021baf2311d6a7dc8f84418dcfab2f18c86cc731b0`.
The private verifier service ran as
`txncat-receipt-verifier@raylo-txncat-authority-prod.iam.gserviceaccount.com`
with only the learning and selection service accounts as invokers, revision
`txncat-proof-verifier-00006-9nc`. The v3 manifest object was generation
`1789720806638620`, 12,148 bytes, SHA-256
`655e36e867eaad8a6d2e7ab9c8bb60906df03c2e4212b02f4ecab1ed12a9ae58`.

The execution receipt owner is Carlos. Fixture writes ran under the named
authority-writer account; bucket retention remains platform-governed and
provider audit logs remain platform-managed, with execution IDs and image
digest retained for review.

The live outcomes were:

- learning and selection valid receipts: HTTP 200;
- both learning/selection cross-plane swaps, the contaminated receipt, the
  orphan reference and the changed reference: HTTP 403;
- proposal-only pending request: HTTP 503/unavailable;
- wrong-audience Cloud Run identity token: HTTP 401;
- worker direct Storage/Firestore/KMS calls: all denied;
- verifier private-object read, Firestore mutation and KMS signing: all denied;
- disabled receipt-key version 2: HTTP 503/unavailable; re-enabled version 2:
  valid learning read recovered HTTP 200.

The first v1 namespace was abandoned after a synthetic-only runner
serialization failure before manifest publication. The earlier v2 namespace is
also retained only as historical synthetic evidence; this bounded receipt uses
v3 after the CAS barrier and denial-probe fixes. No customer-derived bytes,
labels, reservations, retraining or locked-set scores were involved.

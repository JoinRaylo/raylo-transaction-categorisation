# Synthetic live-proof design

Status: **synthetic live proof passed on 2026-09-18; real admission remains
closed**.

The canonical runtime is
`apps/ob-txn-categoriser/scripts/benchmark_authority_live_proof.py`. The
deployment context contains only that runtime, a wheel built from the
canonical `raylo-txncat` package, and pinned infrastructure dependencies. It
accepts no customer payloads and writes only deterministic synthetic objects
under `synthetic-stage0-20260918-v2`.

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
the matching worker identity and receipt. Proposal-only, contaminated,
opposite-plane, orphan, changed-reference, wrong-audience and role-swapped
requests return denied/unavailable without bytes. The receipt-verifier's KMS
sign attempt and worker direct data-plane calls return permission denied.

The live proof records only service-account unique IDs, operation IDs,
generations, SHA-256 digests, epochs, key version and status. It records no
transaction narrative, customer identifier or raw payload.

## Observed execution

The writer completed in Cloud Run execution
`txncat-proof-bootstrap-v2-mfczw`. The final image digest was
`sha256:510f24807152026b3cf65dd5478ab6aaa9825d07901247964eff7d2ed3d50e3d`.
The private verifier service ran as
`txncat-receipt-verifier@raylo-txncat-authority-prod.iam.gserviceaccount.com`
with only the learning and selection service accounts as invokers.

The live outcomes were:

- learning and selection valid receipts: HTTP 200;
- both learning/selection cross-plane swaps and the contaminated receipt: HTTP
  403;
- wrong-audience Cloud Run identity token: HTTP 401;
- worker direct Storage/Firestore/KMS calls: all denied;
- verifier private-object read, Firestore mutation and KMS signing: all denied;
- disabled receipt-key version 2: HTTP 503/unavailable; re-enabled version 2:
  valid learning read recovered HTTP 200.

The first v1 namespace was abandoned after a synthetic-only runner
serialization failure before manifest publication. It is not reused or treated
as proof; v2 is the only evidence namespace. No customer-derived bytes,
labels, reservations, retraining or locked-set scores were involved.

# B03-B runtime identities and bindings

Status: **named identities, least-privilege bindings and the synthetic live
proof passed; fresh linked-only admission remains pending**.

Carlos explicitly approved creation of the four keyless runtime identities and
the exact least-privilege matrix in `raylo-txncat-authority-prod`. This packet
now records the synthetic-only Cloud Run/Firestore/KMS proof as well. It
authorizes no customer data read, BigQuery export, candidate reservation,
label, provider call, training/selection read, retrain, locked-set access or
score.

## Applied scope

| Resource | Value |
| --- | --- |
| Project | `raylo-txncat-authority-prod` (`357892832103`) |
| Region | `europe-west2` |
| Bucket | `gs://raylo-txncat-authority-prod-europe-west2` |
| Registry | `projects/raylo-txncat-authority-prod/databases/txncat-benchmark-authority` |
| Receipt key | `.../keyRings/txncat-benchmark-authority-europe-west2/cryptoKeys/txncat-benchmark-receipts` |
| Storage key | `.../keyRings/txncat-benchmark-authority-europe-west2/cryptoKeys/txncat-benchmark-storage` |

The four active service accounts and immutable provider unique IDs are:

| Role | Service account | Unique ID |
| --- | --- | --- |
| authority writer | `txncat-authority-writer@raylo-txncat-authority-prod.iam.gserviceaccount.com` | `110799062502316526083` |
| receipt verifier | `txncat-receipt-verifier@raylo-txncat-authority-prod.iam.gserviceaccount.com` | `102004524245181644069` |
| learning worker | `txncat-learning-worker@raylo-txncat-authority-prod.iam.gserviceaccount.com` | `103294586886679890509` |
| selection worker | `txncat-selection-worker@raylo-txncat-authority-prod.iam.gserviceaccount.com` | `111373158714103570704` |

No user-managed service-account keys exist. The receipt-verifier and learning-
worker accounts were present at the pre-mutation recheck after the earlier
interrupted creation request; the authority-writer and selection-worker
accounts were created in this approved step. No duplicate account or key was
created.

## Synthetic live proof passed

The canonical runtime
`apps/ob-txn-categoriser/scripts/benchmark_authority_live_proof.py` ran in
`raylo-txncat-authority-prod` under the four named identities, using namespace
`synthetic-stage0-20260918-v2`. The immutable image was
`europe-west2-docker.pkg.dev/raylo-txncat-authority-prod/txncat-proof/authority-proof@sha256:510f24807152026b3cf65dd5478ab6aaa9825d07901247964eff7d2ed3d50e3d`.

- The writer job completed the synthetic bootstrap, including a pending
  proposal, orphan, reservation/learning contamination alias and real
  Firestore CAS race. The observed race was `committed` versus `stale_epoch`;
  the new-operation retry committed and the exact retry returned
  `already_committed`.
- Valid learning and selection probes returned HTTP 200. Both cross-plane
  receipt swaps and the contaminated claim returned HTTP 403. A wrong-audience
  identity token was rejected by Cloud Run with HTTP 401.
- Every worker probe observed direct Storage, Firestore and KMS access as
  `denied`. The verifier identity probe observed private-object read,
  Firestore mutation and KMS signing as `denied`.
- Disabling receipt-key version 2 produced HTTP 503 (`unavailable`) for a
  previously valid receipt; re-enabling it restored HTTP 200. The version is
  currently `ENABLED` and HSM-protected.

The proof manifest is synthetic-only and explicitly
`authorizes_consumption=false`. Its object is the only authority object Carlos
can read directly, through the narrowly scoped
`txncatSyntheticManifestReader` role, solely to assemble local probe inputs;
workers and the verifier retain their separate runtime permissions.

## Custom roles

Six project custom roles were created, with no predefined project-wide Storage,
Firestore, KMS, Editor or Owner role granted to a runtime identity:

| Role | Permissions |
| --- | --- |
| `txncatAuthorityObjectCreateRead` | `storage.objects.create`, `storage.objects.get` |
| `txncatWorkerObjectGet` | `storage.objects.get` |
| `txncatRegistryWriter` | `datastore.databases.get`, `datastore.entities.create`, `datastore.entities.get`, `datastore.entities.list`, `datastore.entities.update` |
| `txncatRegistryLookup` | `datastore.entities.get` |
| `txncatReceiptSigner` | `cloudkms.cryptoKeyVersions.useToSign`, `cloudkms.cryptoKeyVersions.get`, `cloudkms.cryptoKeyVersions.viewPublicKey` |
| `txncatReceiptVerifier` | `cloudkms.cryptoKeyVersions.get`, `cloudkms.cryptoKeyVersions.viewPublicKey`, `cloudkms.locations.get`, `cloudkms.locations.list`, `resourcemanager.projects.get` |

## Bindings applied

- The authority writer has the object create/get role with a CEL condition
  limited to `_authority/`, `private/`, `worker/learning/` and
  `worker/selection/` object prefixes in the named bucket.
- The receipt verifier has object get with a CEL condition limited to
  `worker/learning/` and `worker/selection/` in the named bucket.
- The authority writer has registry-writer permissions only when the resource
  name equals the named Firestore database.
- The receipt verifier has registry-lookup permission only under the same named
  database condition.
- The authority writer has the custom receipt-signer role on the receipt key.
- The receipt verifier has the custom receipt-verifier role on the receipt key.
- The Cloud Storage service agent remains the only binding on the storage key,
  with `roles/cloudkms.cryptoKeyEncrypterDecrypter`.
- Learning and selection workers have no Storage, Firestore or KMS bindings.
  They receive only `roles/run.invoker` on the exact private verifier service.
- Carlos has a separate custom role containing only `storage.objects.get`, with
  a CEL condition matching the v2 synthetic proof-manifest object exactly. It
  does not grant bucket listing or claim-object access.

## Bucket-policy fallback and proof boundary

The active Carlos identity could list the bucket but received
`storage.buckets.getIamPolicy` denial when attempting a bucket-level binding.
The two object bindings therefore use project-level custom-role bindings with
the same canonical `projects/_/buckets/<bucket>/objects/<prefix>/` CEL
conditions. No broad project Storage role or bucket-policy bypass was added.
The only human data-plane exception is the exact synthetic manifest reader
described above. The writer/verifier/worker direct-read and deny probes passed
before any real authority object could be considered.

The service-account IAM policies are empty (`etag ACAB`) and all four
user-managed-key listings are empty. The project policy contains the four
runtime conditional bindings, the exact synthetic-manifest reader binding,
Carlos's existing Owner grant and Google-managed service-agent bindings. The
receipt-key policy contains only the writer and verifier custom roles.

## Remaining gate

The next bounded action is a fresh linked-only admission evidence pass for the
customer-linked Plaid pool. It must establish candidate-level event/customer/
account history, input and merchant-family novelty, training/selection
exclusions and pilot block eligibility before any real reservation or label.
The current local preflight, synthetic manifest and these IAM bindings remain
non-authorizing; no real data may be consumed until that admission review and
the later annotation/retrain gates pass.

# B03-B runtime identities and bindings

Status: **named identities and least-privilege bindings applied; synthetic
runtime proof pending**.

Carlos explicitly approved creation of the four keyless runtime identities and
the exact least-privilege matrix in `raylo-txncat-authority-prod`. This packet
records only the authority control-plane mutation. It authorizes no customer
data read, BigQuery export, candidate reservation, label, provider call,
training/selection read, retrain, locked-set access or score.

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
  They will receive only `roles/run.invoker` on the exact private verifier
  service after that service exists; Cloud Run is not enabled or deployed in
  this milestone.

## Bucket-policy fallback and proof boundary

The active Carlos identity can list the bucket but receives
`storage.buckets.getIamPolicy` denial when attempting a bucket-level binding.
The two object bindings therefore use project-level custom-role bindings with
the same canonical `projects/_/buckets/<bucket>/objects/<prefix>/` CEL
conditions. No broad project Storage role or bucket-policy bypass was added.
This scope-preserving fallback must be validated in the synthetic direct-read
and deny probes before any real authority object is written.

The service-account IAM policies are empty (`etag ACAB`) and all four
user-managed-key listings are empty. The project policy contains only the two
conditional object bindings, the two conditional registry bindings, Carlos's
existing Owner grant and Google-managed service-agent bindings. The receipt-key
policy contains only the writer and verifier custom roles.

## Remaining gate

The next bounded action is a separately reviewed synthetic Stage 0–3 proof:
deploy or otherwise exercise the receipt-bound verifier, verify immutable
unique-ID token mapping, test direct-read/list/cross-kind/held/orphan denies,
prove receipt signing and CAS contention, and capture only non-sensitive
digests, generations, epochs and caller identities. The current local
preflight and these IAM bindings remain non-authorizing until that proof and
the remaining admission evidence pass.

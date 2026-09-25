# Historical authority-scope supersession

Status: **recorded; no cloud deletion or retention change performed**.

The earlier physical-scope packet recorded an authority-shaped bucket, Firestore
database and HSM keys in `raylo-production`. Those resources are now explicitly
superseded for this dataset work. They are **synthetic-only,
non-authoritative and outside the current verifier trust set**.

The current authority coordinates are exclusively:

- project `raylo-txncat-authority-prod` (`357892832103`);
- bucket `gs://raylo-txncat-authority-prod-europe-west2`;
- database `txncat-benchmark-authority` in that project; and
- receipt-key versions in the new project's
  `txncat-benchmark-authority-europe-west2` keyring.

The old resources must not receive new objects, documents, identities,
bindings, receipts, labels, customer-linked rows or benchmark membership. A
future verifier must bind the new project, authority ID, environment, exact
bucket/database names and new receipt-key versions; old synthetic receipts must
not replay across that binding.

No cleanup, deletion, retention reduction, key destruction or old-resource IAM
change is performed by this record. Any such action is a separate, explicitly
approved retention/change-management decision. Until then, the old resources
remain preserved as historical evidence only and are not permission to consume
data.

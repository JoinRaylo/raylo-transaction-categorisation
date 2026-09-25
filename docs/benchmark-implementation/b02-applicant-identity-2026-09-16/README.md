# Applicant identity and transport

The current checkout → Taktile/Plaid → categorisation path preserves useful assessment, request, report, account, and transaction correlation keys. It does not preserve a verified person identity for an anonymous pre-registration applicant. Checkout UUIDs, Plaid report/client IDs, account IDs, transaction IDs, and Taktile entity references support grouping or repeat-event detection, but do not prove ownership across applications.

The minimal practical path is a warehouse/sidecar join through the persisted assessment ID, using an independently verified Rails assessment → checkout → applicant/customer relation where present. Missing links remain unresolved. AIE-496 improves assessment/replay lineage and snapshot fidelity; it does not itself solve anonymous applicant identity.

This is a source review, not a deployment or production-schema attestation. The fixed-cohort aggregate result is in [`MEASUREMENTS.md`](MEASUREMENTS.md); it does not certify population coverage or identity.

- [Backend and transport evidence](BACKEND_AND_TRANSPORT.md) explains the checkout/User/Customer lifecycle and provider identifiers.
- [Next step](NEXT_STEP.md) records the proposed dated identity sidecar and remaining admission prerequisites.
- [Reproduction](RUNNING.md) retains the read-only query and offline checks.

No new rows were reserved, labelled, predicted on or trained on. The waterfall, model bytes, accuracy scores and staging deployment are unchanged.

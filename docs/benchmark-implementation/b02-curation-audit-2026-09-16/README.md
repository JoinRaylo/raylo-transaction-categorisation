# Historical regression cohort and source-readiness audit

This increment implements the approved reuse of existing labelled data and
investigates the remaining customer/event and exposure gaps before fresh sampling.
It creates **historical-regression-v1**, not the independent master benchmark.
No fresh source rows have been reserved, labelled, scored by a model or trained on.

- [REGRESSION.md](REGRESSION.md): frozen cases, label provenance, conflicts and scores.
- [IDENTITY_EXPOSURE.md](IDENTITY_EXPOSURE.md): recovered linkage and completed exposure checks.
- [FOLLOW_UP.md](FOLLOW_UP.md): unresolved evidence and the order of work before admission.
- [RUNNING.md](RUNNING.md): reproducible commands and private artifact handling.

`legacy-summary.json` binds the private membership/conflict objects and contains
all 19 separately scored groups. `legacy-rescore.json` verifies the reusable scorer
against the retained complete baseline predictions. Identity, effective-input and
merchant reports contain aggregate counts and private-object hashes only.
`implementation.json` pins the canonical shared module and executable adapters;
`verification.json` records tests, research replay and privacy/integrity checks.

The earlier [three-view amendment](../b02-initial/CONTRACT_AMENDMENT.md) still governs
representative events, unseen inputs and unfamiliar merchant families. They can
overlap within a partition; their scores must remain separate. Existing selection
validation keeps its role, and v5/v6 contents remain unopened. No serving pipeline,
model, taxonomy, mask or staging deployment changed during this increment.

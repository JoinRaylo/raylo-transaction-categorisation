# Admission prerequisites after this audit

The historical regression cohort is usable now for development diagnostics. The
fresh benchmark still has unresolved prerequisites; this audit does not turn a
missing history record into a clean result or mark B03/B04 complete.

| Remaining evidence / control | Why it matters | Concrete next action |
|---|---|---|
| Stable identity for anonymous applicants | 38,498 sampled event keys still lack customer identity. | Define a retained stable applicant identity and reviewed checkout/account aliases with the source owner. Reconcile later-arriving direct links as dated evidence. Keep unresolved cases outside admission; quantify the coverage gap if an initial population is limited to registered customers. |
| Pending/posted and reconnect event/account aliases | Current account/transaction IDs are not proof that historical aliases are absent. | Export existing provider alias history or a reviewed alias map, with provenance and ambiguity handling; preserve the original source/report IDs. Never merge on merchant/amount/date alone. |
| Historical event/customer linkage and original consumption | The preserved 21.5M MLM corpus and some other learning sources lack economic-event/customer IDs. File hashes and input matches do not reconstruct those IDs. | Recover original extraction/source manifests and consumed-row/group receipts where available. Record irrecoverable ancestry. If recovery fails, explicitly redesign the prospective clean-ancestry collection/training boundary; do not describe today's unmatched rows as proven never exposed. |
| Reviewed merchant-family and enrichment history | Exact known names do not cover aliases or historical dictionary/rule/prompt/retrieval use. | Build a reviewed, versioned family map across known learning/enrichment merchants and candidates. Preserve excluded/ambiguous families and a coverage receipt; complete lineage review for unrecorded historical sources. |
| Protected legacy membership export | The registry and export schema exist, but no reviewed real identity-only membership export was found in the inspected repositories. | Produce and verify the required identity-only transaction/merchant/family export through the protected-set owner/process. Do not read v5/v6 contents for this audit or run their evaluations. Keep their roles/protections until an explicit migration decision. |
| Durable B03 reservations and B04 consumers | Offline hash reports do not stop future training, MLM, dictionary, rule or prompt/retrieval jobs from consuming held-out rows. | Publish versioned membership and aliases in controlled storage; implement atomic reservation/conflict checks and integrate every learning/enrichment/selection consumer plus promotion gates. Prove rejection on protected and unknown identities before enabling admission. |

After those requirements are met, freeze a source window and review its category,
direction, missing-merchant, payment-pattern, customer/account and provider mix.
Then reserve an independently labelled pilot with the three declared views and
appropriate population weights. Final sample sizes and sealed-confirmation
allocation follow that profile, not the current engineering sample's counts.

Existing labels can save work in the historical regression suite. They cannot fill
the fresh master denominator merely because they are already labelled or lack an
exact supervised-training match. Retain a separate independently labelled future
cohort for model/engine generalisation, and a protected confirmation process to
limit adaptation to repeatedly inspected evaluation results.

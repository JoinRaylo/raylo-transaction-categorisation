# Canonical product and model names

Decision recorded: 17 September 2026. Owner: Carlos.

Use these names in service-facing documentation, reports, dashboards, presentations
and external communication:

- **Raylo Transaction Categorisation Engine** is the official name for the complete
  T1–T7 categorisation pipeline. **Raylo TxCat Engine** is the approved short name.
- **TxCat-1** is the official name for the transformer model used at T6.

`TxCat-1` refers to the transformer itself, not the entire engine and not the hinge
rollback model. When technical precision is useful, write “TxCat-1 transformer at
T6”. Internal package, infrastructure and API identifiers may remain
`ob-txn-categoriser` where renaming them would create an unnecessary compatibility
or migration change.

Historical artefacts remain immutable. Older reports may use “waterfall”,
“transaction categorisation pipeline”, a transformer implementation name, or a
training-run name. Preserve that wording when quoting or reproducing a historical
result, while using the canonical names in any new explanation around it.

These names do not imply a model, policy, tier, API or score change. The current
served tiers remain deterministic T1–T5, classifier T6 and unclassified T7.

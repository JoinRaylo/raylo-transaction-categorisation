# Archive — superseded and discarded work

Kept for provenance. Do not build on these.

| File | Why it's here |
|---|---|
| `taxonomy_v2_SUPERSEDED.csv` | 73-leaf version pruned using IV against 3-month arrears as an inclusion test. Wrong criterion — IV measures predictive value for one outcome, not categorisation quality. Rebuilt as the 274-leaf v3. |
| `plaid_only_crosswalk_SUPERSEDED.csv` | First crosswalk, Plaid only, single `raylo_category_group` column. Superseded when the mortgage/rent case showed necessity and debt-status must be orthogonal dimensions. |
| `accountscore_xml_parser_DISCARDED.sql` | Validated dbt model to parse `landing_sentinel_proposal_v2.AccountScoreResults` XML. **Discarded**: 75,910 of its 75,912 references (99.997%) already appear in `equifax_data.open_banking_full_dump`, which is flat, proposal-matched and already modelled. Do not resurrect. |

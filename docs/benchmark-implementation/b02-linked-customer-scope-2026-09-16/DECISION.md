# Decision: linked-customer population for v1 candidates

**Date:** 16 September 2026  
**Decision:** For now, v1 benchmark candidates use the audited linked-customer Plaid pool: rows with an unambiguous existing `assessment → checkout → user → customer` link. Unresolved or ambiguous identity rows are excluded from v1 candidate admission, while their source records and prior audit artifacts remain preserved.

The last audited Plaid source covered 20,084,276 of 35,553,295 raw rows (56.49%) linked to 45,617 users/customers. The remaining 15,469,019 rows (43.51%) were unresolved or otherwise outside that linked population. These are raw source-row counts before deduplication and exposure checks, not unique economic transactions and not admitted or labelled examples. Other-provider and historical regression evaluation remains separate.

This supports a representative identified-customer population claim only. The three existing benchmark views and held-out protection remain unchanged. This decision supersedes the earlier suggestion that anonymous-identity recovery must precede v1. Anonymous identity recovery is stopped for this scope; no new identity system is required.

Next bounded work is to profile the linked pool by dates, direction, missing merchants, provider, account and customer breadth; resolve deduplication and alias handling; apply view-specific exposure checks; and then prepare a sampling plan. Category coverage requires reliable independent labels; provider labels or model outputs are not category truth.

Source context: [B01 exposure/source-identity audit](../../benchmark-audits/b01-2026-09-15/REPORT.md), [B02 curation audit](../b02-curation-audit-2026-09-16/README.md), [B02 source/index audit](../b02-source-index-2026-09-16/REPORT.md), and [applicant identity/transport review](../b02-applicant-identity-2026-09-16/README.md). These existing dated audit files remain hash-pinned and unchanged.

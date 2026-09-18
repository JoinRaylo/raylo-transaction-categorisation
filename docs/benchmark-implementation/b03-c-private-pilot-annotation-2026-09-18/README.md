# B03-C private pilot annotation and review queue

This milestone completes the three independent model annotation streams for
the reviewed private 500-row customer-linked Plaid pilot and prepares the
disagreements for Carlos. It does not create final benchmark labels and does
not authorize training, selection, scoring or promotion.

## Outcome

Sonnet 5, Gemini 3.7 Flash and Gemini 3.8 Flash each have 500 strict-valid
votes. The final Gemini recovery was deliberately narrow:

| Model | Rows already valid | Attempt-3 rows | Attempt-3 valid | Final votes |
| --- | ---: | ---: | ---: | ---: |
| Gemini 3.8 Flash | 474 | 26 | 26 | 500 |
| Gemini 3.7 Flash | 486 | 14 | 14 | 500 |
| Sonnet 5 | 500 | 0 | 0 | 500 |

Each Gemini model first passed a live 10/10 synthetic batch acceptance suite
using the exact production request envelope. The accepted request and parser
fingerprints, returned-model identity, gate receipt, parent artifacts and
canonical state path were required again for the real submission. Collection
accepted only one non-thought JSON response with an exact STOP finish, exact
four-key schema, finite confidence in range, and a taxonomy-bound leaf.

The three-way comparison contains 261 model-unanimous rows, 239 disagreements
and zero incomplete rows. Twenty-four unanimous rows are still unresolved:
11 are unanimously ambiguous and 13 are unanimously insufficient-evidence.
Only the 237 unanimously labelled rows avoid Carlos review. The mutually
exclusive primary views are:

| Primary view | Rows | Unanimous labelled | Model disagreement | Unanimous abstention | Carlos review |
| --- | ---: | ---: | ---: | ---: | ---: |
| Representative | 250 | 130 | 109 | 11 | 120 |
| Unseen input | 150 | 74 | 71 | 5 | 76 |
| Unfamiliar merchant | 100 | 33 | 59 | 8 | 67 |
| **Total** | **500** | **237** | **239** | **24** | **263** |

The comparison contract also retains overlapping protection-view memberships;
those counts must not be confused with the primary-view partition above.

## Carlos review artifact

The private experiment contains an owner-only `adjudication-v2/` directory with:

- the complete comparison evidence;
- the 263-row review queue with all three independent votes and an explicit
  disagreement/unanimous-abstention reason;
- a digest receipt and aggregate summary; and
- `carlos_annotation_review.xlsx`, with local dropdowns for decision status
  and taxonomy leaf plus a formula-driven review state.

The workbook contains only opaque pilot IDs and the identifier-free annotation
payload. Source transaction, account and customer IDs remain in the separate
private membership file. The directory mode is `0700`; queue, receipt, summary
and workbook modes are `0600`. The initial workbook receipt binds its bytes to
the review queue, summary, membership and comparison receipt.

The earlier `adjudication/` directory contained only the 239 model
disagreements and is retained as superseded evidence. It must not be used for
Carlos review.

No automatic or majority adjudication was applied. Unanimous abstention is not
a final label. The 237 unanimously labelled rows are accepted only under the
approved pilot workflow. The published state records `carlos_decisions=0`,
`gold_labels_created=0` and `authorizes_consumption=false`.

## Verification

- Full research suite: **197 passed**, with two pre-existing unknown-marker
  warnings.
- Focused recovery/review tests after the correction: **37 passed**.
- Review-queue tests: **10 passed**, including unanimous ambiguous and
  insufficient-evidence cases.
- Focused Ruff rules `E,F,I,BLE`: passed.
- Workbook export/import: two sheets present; decision-state transitions
  `Needs decision -> Missing leaf -> Complete -> Remove leaf -> Complete`
  passed; formula-error scan found zero matches.
- Spreadsheet summary and reference sheets were rendered and visually checked.
- Independent Astra review found the omitted unanimous abstentions and stale
  saved bundle. After correction, focused re-review approved the v2 packet
  with no remaining findings.

The machine-readable evidence is in `verification.json`. Private rows, prompts,
rationales, provider job IDs and model outputs are intentionally not committed.

## Limitations and next gate

This is an internal annotation pilot, not human gold and not a
population-weighted accuracy estimate. Merchant unfamiliarity still means an
unseen normalized merchant string rather than a reviewed alias-family ontology,
and legacy training rows without Plaid IDs still prevent retrospective exact
history completeness.

The next gate is Carlos's decision on all 263 queued rows. A separate importer
must then validate the edited workbook against the initial receipt, reject
missing or contradictory decisions, publish immutable final labels and bind
them to the permanent evaluation membership. Only after that review is frozen
should the separate training augmentation and one supervised hinge/transformer
retrain proceed.

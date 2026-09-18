# B03-E private evaluation pilot construction

Status: **constructed, prospectively protected from Tier-B training/selection and
independently approved for annotation preparation; not yet labelled or authorized
for training/scoring consumption**.

This milestone turns the existing receipt-bound, customer-linked Plaid candidate
draw into the simple private lookup Carlos requested. It assigns 500 distinct
transactions to `eval` before any label request and keeps source identifiers in a
mode-`0600` membership CSV separate from the identifier-free annotation payload.
No Firestore/CMEK service or new cloud project is involved.

## Approved v2 artifact

The approved local artifact is
`/private/tmp/txncat-eval-pilot-20260918-v2`. The earlier v1 artifact is
superseded and unapproved; it must not be annotated or consumed.

The builder verifies the executed candidate receipt, opaque exposure profile and
lineage receipt before allocation. Their pinned result/profile hashes are:

- candidate result: `f9c549ee7a8a6bbfaec8999d3edaf2dca22f0d4f4fa463a486dcc3fd5a8f32ef`;
- exposure profile: `04efff789eadd9bbae635109bd15be80e34164bf8132e1d78f7bacbce2eb7ec5`;
- lineage result: `030d239d3e361e81750bc77ee0b1e97969e9d13a2eece588f3cd780385418ae4`.

The private outputs are hash-bound by `receipt.json`:

- identifier-free `pilot.jsonl`: `fc5c626cdc0966d46dd1a1a9c04f04f2f9c515cecfedb0587019c16a7f684248`;
- exact-ID `membership.csv`: `0afb4155c750808e332ef2bf1cfb17866d152b3b374771ad77d2399a62d43068`;
- aggregate `summary.json`: `c261ccbd4da660a75aa0fb9f4df99699f760411db96343ee71b17942847cb668`;
- receipt: `3a903922ca6a13becd62bc57751b11b35a1b9a579a6f6696d55f064aac04b623`.

The directory is mode `0700`; all four files are mode `0600`.

## Allocation result

The deterministic whole-customer allocator selected 500 events across 464
customer blocks, with at most four rows per customer:

| Primary view | Rows | Known historical effective-input matches |
| --- | ---: | ---: |
| representative | 250 | 111 |
| unseen input | 150 | 0 |
| unfamiliar merchant | 100 | 0 |

Primary cohorts are disjoint. View tags describe row properties and therefore
overlap: all 500 rows are representative-tagged, 389 are unseen-input-tagged and
156 are unfamiliar-merchant-tagged. The unfamiliar cohort is also unseen-input.
Representative rows intentionally preserve familiar and unfamiliar model-input
patterns; this is separate from permanent transaction membership.

The allocator rejects an entire customer block when an existing membership file
touches any exact event, account or customer in that block. Strict novelty views
require every row in their selected customer blocks to meet the corresponding
screen. Historical customer contradictions, incomplete current lineage, opaque
customer-token splits/collisions and changed input hashes fail closed. Any supplied
membership file is itself hash-bound in the output receipt.

This run supplied zero prior exact-ID membership files because the historical
training exports do not contain recoverable provider identities. The private
exposure profile remains the only retrospective model-input screen. Prospective
separation begins with this eval lookup. Future Tier-B fetch and build commands now
require the same private membership file and exclude these exact events and
connected account/customer groups.

## Prospective training protection

`src/build_tuning_dataset.py` now requires one or more
`--protected-membership` inputs for both `fetch` and `build`. The linked query
retains `customer_id` in the private source artifact, while model JSONL remains
identifier-free. Before train/selection assignment, the fetch rejects exact eval
events and every fetched row sharing an eval account or customer. Contradictory
account/customer mappings fail closed.

The private fetched transaction file is published with a receipt binding its hash,
row count and each eval lookup hash/row count. Build reloads the supplied lookup and
requires those bindings to match. Missing receipts, changed lookup/data, duplicate
headers/events, malformed CSV widths, blank identifiers and inconsistent connected
groups are rejected. This is a simple local protection and receipt, not a new
database or cloud authority service.

The updated SQL compiled in a BigQuery EU dry run without returning rows; its
upper-bound bytes processed were `7,657,252,259`. Twenty-four focused membership
tests and 135 full regressions passed. Independent Astra review found three initial
fail-closed gaps; after correction it approved with no remaining findings.

## Verification and review

- 12 focused synthetic/adversarial pilot tests passed.
- 135 research and benchmark regression tests passed; two pre-existing unknown
  pytest-marker warnings remain.
- Independent Astra review initially found four issues: over-restricting the
  representative cohort, accepting contradictory historical customers, trusting
  an unchecked opaque customer grouping and omitting membership-input hashes.
  All four were corrected and regression-tested.
- Astra then approved v2 with no remaining actionable findings. It independently
  reproduced the 500-row count, 250/150/100 allocation, 464 whole customer blocks,
  strict-view zero-overlap result, hashes, row digests, permissions and absence of
  explicit source identifiers from `pilot.jsonl`.

No provider call, label, model retrain, locked-set score, cloud mutation or real
training fetch/export occurred.

## Deliberate limitations and next gate

- Historical exact event/group separation cannot be proven for legacy training
  rows whose source IDs were never retained. Absence from the new lookup is not
  evidence of historical non-use.
- “Unfamiliar merchant” currently means an unseen normalized merchant string,
  not a reviewed alias-family ontology.
- This quota-based 500-row annotation pilot does not establish population-weighted
  benchmark metrics.
- Transaction narratives may contain personal information even though explicit
  source identity fields are absent from the annotation payload.
- `authorizes_consumption=false`: the artifact is annotation input and membership
  evidence, not authority to train or score.

The next gate is to extend the already-synthetic provider runner to this reviewed
private manifest, add output/PII handling checks, and then send the identifier-free
pilot independently to the three approved annotation models. Preserve all three
outputs and route every disagreement to Carlos; do not auto-adjudicate.

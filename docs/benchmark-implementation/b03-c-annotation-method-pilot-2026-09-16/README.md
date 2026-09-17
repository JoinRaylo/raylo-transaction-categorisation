# B03-C annotation-method pilot runner

Status: **runner implemented and synthetic provider paths verified; no real
pilot admitted**.

This increment prepares the separately quarantined 500-row annotation-method
pilot requested by Carlos. It is not an evaluation gold-set builder. The three
provider outputs remain independent annotations; agreement is descriptive only,
and no majority label is created. Any disagreement or incomplete provider
result remains a queue item for Carlos rather than becoming a label.

## Canonical implementation

- Contract: lib/raylo-txncat/benchmark_annotation.py in the app monorepo
- Adversarial contract tests: lib/raylo-txncat/tests/test_benchmark_annotation.py in the app monorepo
- Provider runner: tools/benchmark/annotation_pilot.py

The contract binds every item to an opaque ID, manifest digest, content digest,
prompt digest, source snapshot digest, taxonomy/guide versions and the
non-authoritative reservation operation. It requires exactly three declared
model batches for comparison, validates taxonomy leaves, records explicit
labelled/ambiguous/insufficient_evidence outcomes, and never derives a gold
label from model consensus. A labelled response must include a leaf and finite
confidence; non-labelled responses must include neither.

## Provider and batch boundary

Online calls are one request per item. Anthropic uses the Anthropic API with a
forced structured tool. Gemini online uses Vertex AI with ADC. Batch calls are
explicitly asynchronous and have separate submit, status and collect commands:

- Anthropic uses messages.batches.create, retrieve and results.
- Gemini uses the Gemini API-key batch route with inline requests, because the
  Vertex batch route requires a GCS or BigQuery source. No customer payload is
  uploaded to GCS or BigQuery by this runner.

The Anthropic provider's 64-character custom-ID limit is handled by a
deterministic short request ID; collection maps it back to the committed opaque
item ID and rejects unknown, duplicate or missing mappings. A digest-only job
state is written before submission. If submission or collection becomes
uncertain, the state is held and the runner does not resubmit or silently fall
back to online calls.

The input manifest and prompt JSONL are private, exclusive-create artifacts.
They must already be produced from an admitted, linked-only snapshot. The
runner requires output and job state below a directory named
annotation_method_experiment. It does not query BigQuery, accept source IDs,
build eligibility, or authorize a reservation. In this increment the executable
also rejects `real_pilot` manifests; only synthetic manifests can reach a
provider until the reviewed physical authority gate exists.

## Synthetic evidence

The isolated API smoke fixture contained one synthetic transaction and no
customer or production data.

| Route | Result |
| --- | --- |
| Sonnet 5 online | 1 received, groceries, returned model claude-sonnet-5 |
| Gemini 3.8 Flash online | 1 received, groceries, returned model gemini-3.8-flash |
| Gemini 3.7 Flash online | 1 received, groceries, returned model gemini-3.7-flash |
| Sonnet 5 batch | One result was correctly collected as a vote; a separate invalid non-labelled result was rejected because it carried confidence |
| Gemini API batch | Accepted and reached JOB_STATE_SUCCEEDED; the provider omitted required rationale, so the result was recorded as schema_failed rather than a vote |

Adversarial synthetic checks also rejected a provider result with an unknown
item ID, an Anthropic custom ID above the provider limit, a non-JSON/empty
structured response, an unknown taxonomy leaf, a missing batch result and
non-labelled output that smuggled in a leaf or confidence. Failed provider
attempts remain explicit and do not fill a vote.

Canonical contract tests: **13 passed**. Research runner checks: **12 passed**,
Ruff and bytecode compilation passed, and a synthetic three-model runner-to-
contract integration harness passed. The three online calls and the two asynchronous
batch routes were API calls containing synthetic text only; all strict
provider-output failures remained visible and non-authorizing.

## Non-authorizing limitations and next step

This is not evidence that B03/B04 is complete. Physical authority resources,
IAM/retention/KMS scope, authenticated receipts, cross-process races, complete
event/customer/account and pending/posted/reconnect history, legacy
protections, reviewed-family coverage, B04 consumer gates and sampling
eligibility remain open. No 500-row pilot manifest exists; no real rows were
downloaded or labelled; no locked set was scored; and no B04 training,
selection or locked-evaluation consumer is wired to these outputs in this
increment. The runner only writes below the dedicated experiment quarantine;
that path guard is not a substitute for downstream consumer gates.

After the concrete authority scope and authenticated receipt review, the next
bounded action is to produce a fresh linked-only candidate snapshot, rerun all
eligibility/protection checks, commit the separate 500-row pilot reservation,
and then submit exactly one batch per model. The pilot's three model votes are
annotation-method evidence, not human gold: unanimous agreement is descriptive
only, while every disagreement or incomplete result is raised to Carlos for a
decision. Two independent human labels plus adjudication remain the policy for
a later human-gold evaluation set unless explicitly superseded.

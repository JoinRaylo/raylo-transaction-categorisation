# Three-view contract amendment — revision 2

Approved direction: three separately reported evaluation views. This amendment
supersedes the universal effective-input exclusion and novel-input-only headline
in master-v1 where they conflict below. All other identity, permanent reservation,
legacy exclusion, label independence and sealed-confirmation requirements remain.
The original design and B01 audit remain immutable historical records.

## Eligibility and scope

| Requirement | Representative future events | Unseen model inputs | Unfamiliar merchant families |
|---|---|---|---|
| Verified new event, with aliases checked against learning/selection history | Required | Required | Required |
| Verified customer/account separation within the declared target population | Required | Required | Required |
| Familiar merchant allowed | Yes | Yes | No |
| Natural recurrence of a previously seen effective input on a different event/group | Allowed, exposure reported | Excluded | Excluded |
| Reviewed merchant-family identity and full controlled family-history check | Not a novelty requirement | Not a novelty requirement | Required |
| Blank merchant | Eligible if other requirements pass | Eligible if other requirements pass | No merchant novelty claim; separate blank-merchant slice |
| Historical input exposure unknown, but event/group separation proved | May be reported as input-exposure unknown | Quarantine | Quarantine |
| Event/group history unknown | Quarantine | Quarantine | Quarantine |

Family novelty covers Raylo-controlled training, MLM, distillation, model selection,
dictionary/rule evidence and prompt/retrieval examples. It is not a claim that a
public foundation model has never encountered the merchant. Merchant identity and
family identity are separate reviewed attributes; matching either rejects a claimed
unfamiliar family. Merchant spelling changes alone do not establish novelty.

A view is a question, not a train/test split. Record view eligibility independently
from dataset role, sampling cohort, partition and lifecycle. One held-out observation
may contribute to multiple views **within the same assigned partition**; its results
are correlated, never independent evidence. Do not multiply-count it in an overall
headline. Customers/events cannot cross development and sealed confirmation.

The representative headline comes from a probability sample of the declared service
population, retaining natural frequencies and inclusion probabilities. Unseen/family
challenge additions are separate targeted samples. Do not merge them unweighted into
an average day-to-day accuracy score. If identity linkage excludes an applicant group,
the representative claim must name that restriction and measure the population loss.

## Permanent reservations and learning admission

Every reserved event, verified alias, customer and account remains excluded from all
nine learning/enrichment purposes and the separate selection-validation purpose.
Retired, ambiguous, failed-label and spent members never become training data.

- A **representative-only** reservation does not ban every distinct independent event
  with the same common input signature. It still protects the reserved event/group,
  its labels and its use as training/rule/prompt evidence.
- An **unseen-input** reservation also protects its applicable effective-input signatures.
- An **unfamiliar-family** reservation additionally protects its reviewed merchant family.
- If a member belongs to several views, apply the union of protections permanently.
  Changing a label, filename, active view or benchmark version never downgrades them.
- Selection-validation remains separate from training and benchmark events/groups;
  this first contract conservatively excludes matching effective inputs too.
- Legacy v1 transaction/merchant/family exclusions remain in force. A blank new v2
  merchant may pass only with verified source/group identity and a complete legacy
  index; absence of a merchant name is not an identity or evidence of novelty.

Input-sharing across **independent strict or sealed pools** still requires the frozen
sampling-block policy. Representative recurrence is explicitly modelled and reported;
it must not be silently deleted to make sample statistics look independent. B03/B05
must implement partition assignment and grouping before sampling; this preflight
implementation only compares a candidate with an already assembled snapshot.

## Meaning of the initial implementation

`eligible_preflight` means no conflict was found against the supplied, hash-bound
index and declared coverage. It is not a reservation, original fit-consumption
attestation, representative-sample certificate or permission to train. Every result
has `authorizes_consumption=false`. Caller-supplied completeness flags require
verified evidence from the future authority; they do not establish their own truth.

The B01 historic corpus lacks recovered customer/event lineage. Do not mark its
identity history complete merely because sentence hashes are available. A scoped
prospective/new-customer claim needs its own cutoff, alias and source evidence.

Implemented projections: original logical transaction fields without source IDs;
actual serving/research transformer sentence; retained hinge text and float32
log-amount/direction; optional token-48 encoding through a verified frozen tokenizer.
Tokenizer digest is part of the encoded projection version. No tokenizer is fitted.
Missing required or unknown projection versions fail closed. These functions do not
yet audit sparse vectorizer feature collisions, all MLM chunks or teacher prompts.
They cannot certify all ancestors until those adapters and indexes are complete.

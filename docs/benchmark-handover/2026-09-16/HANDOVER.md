# Dataset work handover — 16 September 2026

**Start here. No previous conversation is required.** Your task is to continue the
transaction-categorisation evaluation/training dataset work. The next bounded
milestone is **B03-A: a reservation protocol and synthetic implementation/tests**.
Deliver that for review before admitting real data. Do not restart the source audit,
recover anonymous customers, retrain models or work on the Taktile integration.

This is an execution handover, not evidence that all dataset safeguards exist.
Use [NEXT_AGENT_PROMPT.md](NEXT_AGENT_PROMPT.md) as the initial assignment and
[STATE.json](STATE.json) for pinned source/evidence references and completed checks.
Routine code, tests and documentation can progress without repeated permission
requests. The later review boundaries below concern new authority/infrastructure,
real dataset use and model decisions, not every reversible implementation choice.

## 1. User intent and decisions already made

Carlos wants one independently labelled master benchmark to measure both standalone
ML heads and the complete waterfall, and better training data for **one more
supervised retraining pass** before model promotion. Dataset creation and training
augmentation must be planned together so the retrain cannot consume the future test
set. Luna agents are preferred for bounded execution, with stronger review of the
results. Do not claim that a lower-cost model plus documentation guarantees quality;
demonstrate the acceptance checks and obtain the specified reviews.

Decisions that must survive the handoff:

1. V1 candidates come from the **existing customer-linked Plaid population** only.
   Require unambiguous assessment → checkout → user → customer linkage. Exclude
   ambiguous/unlinked candidates, preserve their sources, and stop anonymous-ID
   recovery. No new applicant identity system is required.
2. Keep three evaluation **views**: representative new events, unseen model inputs,
   and unfamiliar merchant families. A familiar merchant is allowed in the first
   two. A familiar input on a different verified event/group can appear in the
   representative view. It cannot satisfy strict input novelty. Event/customer/
   account separation still applies to every view.
3. Views and data roles are different. Core/challenge/confirmation are partitions;
   a member can contribute to several views within its partition. Apply the union
   of its protections. Do not turn three views into three independent random splits.
4. Preserve every reservation through relabelling, copies, retirement and aliases.
   Representative-only membership protects event/customer/account, strict-input
   membership adds effective inputs, and family membership adds reviewed families.
   Selection validation also remains separate and protects applicable inputs.
5. Keep old labelled cases as **historical development diagnostics**, with their
   exposure limitations. Do not rename them “untouched” or mix their scores into
   the fresh master headline. Provider categories and model consensus are not
   independent evaluation labels.
6. Any waterfall/model behaviour change requires the complete permitted evaluations,
   a change record, mirrored implementation and scores in the research repo.
   No model, mask, threshold, label or staging change is part of this handover.

## 2. Repositories and ownership

| Location | State and use |
|---|---|
| `/private/tmp/txncat-d2-worktree` | App implementation checkout, branch `feat/ob-txn-categoriser-plan`; pre-handover base `b83cc230a2491d95a52fb43d4082a13d59b0ed68`; clean when handover began |
| `/Users/carlosnoblejesus/Repos/internal-services-monorepo` | Saved project/default checkout. It is a different working branch; do not perform dataset edits there accidentally |
| `/Users/carlosnoblejesus/Repos/raylo-transaction-categorisation` | Research mirror, `main`; pre-handover base `1687a589a005298a809e421ac8e54666b8227053`; has unrelated dirty/untracked work |
| `/Users/carlosnoblejesus/Repos/dbt` | Read-only source context at the audited revision; use **root `manifest.json`**, not `target/manifest.json`, for production relations |
| Existing app PR | [#375](https://github.com/JoinRaylo/internal-services-monorepo/pull/375), draft working-staging checkpoint; do not merge it as part of dataset work |

Prefer a **dedicated app worktree and `codex/` branch based on the completed
handover commit**, so Carlos and this task can work independently. Determine that
commit from the existing feature branch after verifying the handover files are
present; the base above is before these documentation files were committed. A
new task may initially land on main: verify its own worktree is clean and create a
new branch from the handover state before editing. Never reset or switch the user's
default checkout to achieve this. Record your actual branch/base in your first update.

The launcher should supply exact app/research **handover commits**. If launched
manually, find each introduction commit with `git log -1 --diff-filter=A --format=%H --`
followed by the handover's repository-relative `HANDOVER.md` path. Verify the file
exists at that commit before creating the branch. Do not substitute the current
main/feature-branch tip if later work has moved it. The research copy lives at
`docs/benchmark-handover/2026-09-16/`.

Keep dataset implementation commits on that dedicated branch for review. Do not
push to `feat/ob-txn-categoriser-plan` from the continuation task without coordinating
integration: that branch contains the broader app work. Research adapter/docs mirrors
are still required, but prefer a dedicated research worktree/branch when continuing
independently; do not discard the existing main checkout's work or push its unpublished
history. Stage explicit paths, never `git add .` in the research checkout.

Unrelated research work includes the September LaTeX report/zip, generated PDFs,
architecture documents, `.codex-*`, `output/`, `tmp/`, the experiment-3 champion
script/report, and assorted `tools/` files. The exact starting status is in STATE.
Read applicable `AGENTS.md`/`CLAUDE.md` in each checkout before editing. Research
requires updates to README, CLAUDE current context and project-summary §8/progress log.

## 3. Read in this order

Paths here are relative to this handover folder and work in both mirrored copies.
Do not read every historical report before starting B03-A.

1. [Joint plan](../../benchmark-implementation/b02-joint-data-plan-2026-09-16/PLAN.md)
   and its [measured findings](../../benchmark-implementation/b02-joint-data-plan-2026-09-16/README.md).
2. [Three-view amendment](../../benchmark-implementation/b02-initial/CONTRACT_AMENDMENT.md).
   **It overrides the older design's universal input-novelty requirement.**
3. [Data contract](../../benchmark-design/master-v1/DATA_CONTRACT.md), especially
   manifests, permanent membership, compare-and-commit and contamination response.
4. [Implementation packages](../../benchmark-design/master-v1/IMPLEMENTATION_PLAN.md),
   B03 and B04 first; then B05/B06 for the later acceptance boundaries.
5. [B02 foundation status](../../benchmark-implementation/b02-initial/README.md)
   and [remaining source/exposure work](../../benchmark-implementation/b02-curation-audit-2026-09-16/FOLLOW_UP.md).
   Any older requirement to recover the excluded anonymous cohort is superseded.
6. [Training audit](../../benchmark-implementation/b02-joint-data-plan-2026-09-16/training/TRAINING_AUGMENTATION.md)
   before changing training consumers; [change policy](../../waterfall-changes/POLICY.md)
before touching categorisation behaviour.

Runtime context for later comparisons: the app uses hinge v8 / selected transformer
seed 123 and **T5b abstention directly to T7**, not a restored provider T6 fallback.
The narrow `CREDIT-PAYROLL-001` research/app-source candidate recognises an exact
Waitrose credit with the complete payroll narrative; it passed the permitted
regression suite but has not replaced the original staging bundle. Bare Waitrose
credits remain ambiguous. Read that change record before choosing a comparison
baseline; do not conflate the latest local candidate with the deployed bundle.

For conflicts, use Carlos's decisions above, then the joint plan/three-view amendment,
then the older design. Source and execution receipts settle factual counts; prose
does not override their scope. Never rewrite a hash-pinned historical artifact to
make it match a later result. Add a new version and an explicit supersession note.

## 4. What is actually complete

| Area | Evidence and limits |
|---|---|
| Linked-population profile | Full current materialization SELECT: 20,473,397 linked rows / 36,312,899 source rows; 46,049 customers; 71,103 accounts. Aggregate evidence only |
| Breadth | 22.85% credits; 35.22% blank merchants; 90.26% of credits blank; 17 months. Business 5.21%, unknown checkout scope 0.62%; neither was silently excluded |
| Event counting | Table already globally deduplicates `transaction_id` by latest report creation time. This is not proof of unique economic events, pending/posted/reconnect aliases or raw-report stability |
| Training profile | 414,400 supervised rows; 342,268 exact input messages; 342,405 input/label pairs; 133 conflicting-input groups; 71,995 repeated rows above unique pairs |
| Training gaps | 7.31% credits; 7.91% blank merchants; four absent leaves (`account_misuse`, `balance_transfer_fee`, `interest_charged`, `loan_repayment_dd`); 21 represented leaves below 20 distinct inputs |
| Existing selection set | 5,000 rows, nine credits, no blank merchants; 119 repeated pairs and documented historical distillation overlap. Refresh separately; do not use confirmation for selection |
| Transformer ancestry | Additional 404,982 consensus texts (21.63% credits, 29.45% blank merchants), plus retained 21.5M-sentence MLM ancestry. Not the same total exposure as hinge |
| Existing labels retained | 8,212 historical transaction cases, 641 head-only, 1,810 dictionary cases; 28 conflicting-label groups withheld. These **28 historical conflicts differ from the 133 training conflicts** |
| Cached engineering sample | 78,537 observations / 77,925 event keys in 100 requests; 39,427 linked keys. The linked sample has 10,527 known-input union matches. Neither a random population sample nor a clean reserve |
| Historical input screens | Retained exact corpus/index and scoped token-48, hinge sparse, folded-text and merchant-name screens exist. Full customer/event ancestry, aliases, protected legacy exports and reviewed family coverage remain incomplete |
| B02 implementation | Shared local policy/projections, input-presence index, adapters and synthetic tests. All decisions are `authorizes_consumption=false` |
| B03/B04 | **Not implemented.** No authoritative reservation, managed sealed-store permissions, authenticated learning receipt or enforced promotion gate |
| Master/augmentation | **Not collected/reserved/labelled. No new retrain.** Proposed sizes are budgets, not achieved counts or permission to consume data |

The previous linked count was 20,084,276 / 35,553,295, covering 45,617 customers.
The later count is a refreshed snapshot. Earlier wording “raw rows before
deduplication” was corrected in the joint report. Do not spend time reconciling
those counts as though the warehouse was frozen across both dates.

## 5. Existing code to extend

The **canonical code is in the app monorepo**, not an independently maintained
research implementation. Research `tools/benchmark/` mirrors CLI adapters and
imports the canonical package using an explicit monorepo root.

| App path | Use |
|---|---|
| `lib/raylo-txncat/src/raylo_txncat/benchmark.py` | `Subject`, `Membership`, `IndexSnapshot`, `Preflight`, versioned identities/projections and view/purpose policy. Keep its non-authorizing contract |
| `lib/raylo-txncat/src/raylo_txncat/benchmark_exposure.py` | Existing disk-backed input-presence index; source lineage and incomplete-history semantics |
| `lib/raylo-txncat/src/raylo_txncat/benchmark_regression.py` | Existing historical cohort/identity helpers; inspect before creating equivalent code |
| `apps/ob-txn-categoriser/scripts/benchmark_*.py` | Preflight, source extraction/profile, identity reconciliation, exposure/merchant screens, historical scoring; read CLI help before reuse |
| `lib/raylo-txncat/tests/test_benchmark*.py` | Existing synthetic contract, exposure and regression cases |
| `apps/ob-txn-categoriser/tests/unit/test_benchmark_preflight.py` | Synthetic adapter replay and corruption guards |
| `apps/ob-txn-categoriser/src/ob_txn_categoriser/cloud_persistence.py` | Existing Firestore/GCS client conventions and generation checks; useful patterns, **not an atomic benchmark authority** |
| `infra/apps/ob-txn-categoriser/` | Repository infrastructure patterns. Existing serving resources are not permission to reuse the runtime archive for sealed benchmark data |

Read the full `Subject`/`IndexSnapshot` validators. Completeness flags supplied by
a script are not independent proof. The future authority must verify their evidence
and scope. Never change `Decision.authorizes_consumption` to true to bypass B03.
Do not put millions of members into a Firestore document or JSON request.

## 6. First assignment: B03-A, synthetic only

This is a local sub-milestone, **not a new Linear ticket or a claim B03 is complete**.
It should produce a small reviewable implementation, not a second architecture
discovery exercise or an attempt to label the entire source pool.

Use these proposed destinations (record any necessary deviation in the design):

| Deliverable | App repository | Research mirror |
|---|---|---|
| Canonical protocol/types | `lib/raylo-txncat/src/raylo_txncat/benchmark_authority.py` | Import the app package; no second implementation |
| Synthetic protocol tests | `lib/raylo-txncat/tests/test_benchmark_authority.py` | Run against the same canonical package; mirror only a needed adapter test |
| Design, result and implementation pins | `apps/ob-txn-categoriser/research/benchmark-implementation/b03-a-synthetic/` | `docs/benchmark-implementation/b03-a-synthetic/`, byte-identical artifacts |
| Optional simulation CLI, only if useful | `apps/ob-txn-categoriser/scripts/benchmark_authority_simulate.py` | `tools/benchmark/benchmark_authority_simulate.py`, byte-identical adapter importing the canonical module |

The new evidence directory should contain `DESIGN.md`, `README.md`, a source-hash
`implementation.json` and actual `verification.json`. Preserve older B02 pins.

1. Read the contract and current preflight code. Write a concise B03 design note
   mapping proposed types and storage operations to contract §6. Identify actual
   production integration dependencies, without applying infrastructure.
2. Implement strict versioned proposal/object-reference/operation-state types and
   the deterministic commit/retry state machine in a new canonical module. Reuse
   canonical JSON/hash/purpose definitions. Keep authority receipts distinct from
   preflight decisions and explicitly non-authorizing in local simulations.
3. Define the minimal storage interface for immutable verified objects, epoch
   compare-and-commit and idempotent operation lookup. A thread-safe test double
   may exercise interleavings; it is not the production store or security boundary.
   Document how the later Firestore transaction must implement the same semantics.
4. Exercise reservation **and pending learning/selection claims** through the same
   conflict protocol. Claims must bind exact content, identities/projections,
   purpose, policy/key versions, parent/index hashes and observed epoch. Required
   provenance must resolve to verified content; a syntactically valid hash alone
   is not evidence. Compute fixture hashes from actual synthetic bytes. Do not add
   an arbitrary zero-hash blacklist to the shared `Sha256` type: a false digest is
   rejected by comparing referenced bytes/generation, and missing evidence follows
   the existing quarantine policy. Local simulations still cannot certify real data.
5. Add the adversarial tests below. Mirror adapters/docs, update context, and report
   changed files, actual commands/results, limitations and outstanding gates.
6. Stop at a review checkpoint. Ask for review of the protocol and test evidence;
   do not silently graduate the prototype into real admission or cloud authority.

Required synthetic acceptance cases:

| Case | Required outcome |
|---|---|
| Reserve and train the same event, customer, account or applicable protected input from epoch N | At most one conflicting commit; loser must re-read/re-evaluate. The reverse ordering must also be tested |
| Two different, non-conflicting proposals prepared at N | First commits; second can succeed after fresh checks at N+1; no permanent spurious rejection |
| Lost response then identical operation retry | Return the same committed operation; no duplicate exposure or new epoch |
| Same operation ID, changed bytes/purpose/parents | Reject, including after an uncertain response |
| Upload without metadata commit; commit without worker start | First is an inaccessible orphan; second remains an exposure/reservation even if work never starts |
| Missing/changed object digest or generation, stale index, missing key/version/history | Fail or quarantine; no consumption or cached allow fallback |
| Reservation retired/quarantined/spent; alias appended later | Protection persists; cross-partition exposure raises a contamination condition, never frees old IDs |
| Representative recurrence vs strict input/family novelty | Preserve the approved distinction and union protections; no blanket ban on common narratives |
| Selection data relabelled as training; unregistered artifact sent to a consumer/promotion check | Reject; local simulated receipts cannot authorize real training or promotion |
| Authority unavailable or local client forges an allow/completeness flag | No real admission. Specify the authenticated adapter requirement explicitly |

Make outcomes observable and deterministic in the public protocol/test interface:
invalid schema, changed operation content and object digest/generation mismatch
are validation failures with no commit; incomplete required provenance follows
`Preflight`'s quarantine/reject result with no commit. A compare-and-commit epoch
conflict returns an explicit stale-epoch outcome, never an allow. Repreparation
must load the new snapshot and rerun policy; test hooks should record the snapshot
epoch and checks used. A recomputed proposal uses a new operation ID, whereas an
exact retry reuses unchanged bytes/ID and returns its original committed record.
Unavailable authority yields an explicit unavailable outcome and no consumption.
An after-commit alias that joins protected and learned groups records contamination
and holds certification; it never erases the earlier exposure. Record the chosen
type names and exact assertions in DESIGN.md rather than testing only truthy values.

First-milestone completion means synthetic semantics are implemented and reviewed.
It does **not** satisfy cross-process/cloud race tests, IAM separation, authenticated
receipts, legacy migration, full ancestry, sampling eligibility or consumer rollout.
Keep those pending, with exact next actions. If a contract ambiguity affects safety
or statistical meaning, write the alternatives and request a decision while
continuing unaffected tests. Do not weaken the contract to make tests green.

## 7. Later sequence and mandatory review boundaries

After B03-A review: implement the production object/transaction adapter and prepare
a scoped infrastructure/IAM plan. Obtain review/approval of that concrete new cloud
scope before apply; previous D2/E4 staging approvals covered the serving app, not
new benchmark stores, identities or permissions. Verify real concurrent claims,
denied training access to sealed data, failure recovery, migrations and authority-
authenticated receipts. Only then connect B04 consumers and promotion gates.

B04 includes tuning/credit/top-up builders; transformer corpus/MLM/tokenizer and
classifier stages; TF-IDF fit; teacher/consensus inputs; dictionary/rule evidence;
LangGraph retrieval/recommendations; and artifact promotion. Use the full table in
IMPLEMENTATION_PLAN.md and inspect callers. A wrapper alone is insufficient when
a direct `.fit` can bypass it. Negative integration tests must fail before learning
or prompt/evidence consumption. No process may silently filter a protected row and
then claim it consumed the unchanged original manifest.

Real candidate admission still needs verified event/customer/account history,
pending/posted/reconnect aliases, complete legacy protections and view-specific
input/family evidence. Work only on the linked pool. When historical IDs cannot be
proved, a prospective **new-customer and new-event** cutoff may be necessary; tie it
to verified immutable exposure snapshots. New customers often bring old history.
Do not invent a cutoff date or change completeness flags to admit that history.

Then reserve the separate 500-row annotation-method pilot. Independently measure
agreement/adjudication yield, refine and freeze the guide, and permanently quarantine
pilot membership. Final labels need two independent humans plus adjudication;
names/roles, quotas and statistical thresholds are not yet all assigned/finalized.
Prepare concrete decisions for Carlos rather than inventing reviewers or acceptable
regression margins. B03/B04 must prevent competing consumption before exports.

Planning envelopes: core 10,000; challenge 5,000; sealed confirmation 5,000
(4,000 representative + 1,000 challenge, reported separately); separate selection
5,000 proposed; up to 10,000 shared training additions proposed. Training buckets
are 4,000 credits, 3,000 critical/thin debits, 2,000 other blank-merchant debits,
1,000 representative remainder, subject to measured label yield. Preserve probability
weights and customer/input sampling blocks. Do not fill quotas with duplicate copies.

Before retraining, resolve or explicitly exclude the 133 current input-label conflict
groups through source review. Do not infer salary/refund from amount or merchant
alone. Pin hinge v8 and transformer iteration-8 seed 123 plus the same waterfall.
Use the existing model recipe and frozen encoder/tokenizer ancestry; no new MLM or
vocabulary extension is planned. Fit the hinge vectorizer on admitted training only.
The transformer rebuilds empirical direction masks: record/review any mask diff.
Choose the actual fitted checkpoint using separate selection data, freeze artifact
bytes, then use sealed confirmation once. Never tune or retrain after seeing its
results and present the next score as another untouched look.

Every real model/waterfall revision must rerun the complete 15 permitted historical
datasets and applicable new benchmark partitions for both heads/full engine. Use
[the existing runner guide](../../waterfall-changes/RUNNING.md); do not improvise a
short replacement evaluation or mix historical and new denominators. Mirror code,
score history and receipts. An independent master exists only after B01–B06 gates
have real evidence; code completion alone does not certify one.

## 8. Private evidence and access

Stable private archive (owner-only, outside Git):
`/Users/carlosnoblejesus/.local/share/raylo-txncat/benchmark-engineering/2026-09-16/`.
It contains source observations/receipt, retained identity links/account/report
evidence, reconciled identity sidecar, effective-input and merchant screens,
historical-regression-v1, cached baseline predictions and exact-index receipts.
This is local retained evidence, **not** B03 managed authority or an eligible pool.
The large SQLite index has its own earlier private location; discover it from the
retained source/index records only if needed, verify its digest, and do not rebuild
it simply to start B03-A. This first milestone needs none of these private rows.

The archive's `source/identity.key` exists for existing controlled adapters. Its
public ID is `benchmark-private-20260916-v1`. Never print/read its bytes into chat,
logs or source, or generate a different key under that ID. Do not infer that an
absent local copy licenses a replacement; continue synthetic work and report the
specific missing dependency. Fingerprints and private memberships stay private.
Public reports may contain aggregate counts, schema metadata and content hashes.

Never open `data/gold_transactions_v5_LOCKED.csv` or
`data/gold_transactions_v6_LOCKED.csv` during this work. V5 is retired; v6 remains
reserved for the separate final go/no-go. Never read
`/private/tmp/txncat-e4-private/signing-key`. Do not use Docker Desktop. Do not
change staging/production/Taktile, contact an admin, or request Monorail/Cloudflare
credentials for B03-A. None is needed for the local milestone.

If later read-only warehouse work is needed, use existing BigQuery access to
`raylo-production`, EU; inspect dbt's CLAUDE and root manifest, reuse known production
relations, dry-run SELECTs and cap each at 20,000,000,000 bytes. No dbt model builds,
bootstrap, source mutations or unrestricted all-time raw JSON scans. Later SELECTs
create new dated evidence because tables are live.

## 9. Tested startup commands and delivery format

These commands were run from the app checkout on 16 September: **115 tests passed**.
If the checkout path changes, set `TXNCAT_HANDOFF_REPO` to the new task's app root.
The known Python 3.12 runtime has the relevant test dependencies. Research Python
is at `/Users/carlosnoblejesus/Repos/raylo-transaction-categorisation/.venv/bin/python`
(3.14, with PyArrow/BigQuery); the app runtime does not have BigQuery/PyArrow.
If a temporary runtime has disappeared, use the repo's pinned workspace setup;
do not silently install latest dependencies or start Docker Desktop.

```sh
TXNCAT_HANDOFF_REPO=/private/tmp/txncat-d2-worktree
cd "$TXNCAT_HANDOFF_REPO"
git status --short
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH="$TXNCAT_HANDOFF_REPO/lib/raylo-txncat/src:$TXNCAT_HANDOFF_REPO/apps/ob-txn-categoriser/src" \
/private/tmp/txncat-c2-env/bin/python -m pytest -q -m unit \
  lib/raylo-txncat/tests/test_benchmark.py \
  lib/raylo-txncat/tests/test_benchmark_exposure.py \
  apps/ob-txn-categoriser/tests/unit/test_benchmark_preflight.py
```

Use `/private/tmp/txncat-c2-env/bin/ruff check --config "$TXNCAT_HANDOFF_REPO/pyproject.toml"`
and `ruff format --check` with the same explicit config on changed Python files.
The config matters: a pass against a different checkout/default config is not the
same check. Run new B03 tests and existing affected contract tests; expand to the
full app/library suite before shipping implementation changes. No full model scoring
is needed for this documentation handover or synthetic-only authority work.

At each milestone update the handover successor record and report:

- exact base/branch/commits and changed paths;
- tests actually run and their results, including failed attempts that affect trust;
- checks implemented versus merely specified, and what remains non-authorizing;
- mirrored files and verified hashes; no private payloads in output;
- the next bounded action and any precise review/approval dependency.

Do not report another agent's “done” as verification. Read the actual final diff,
rerun the necessary checks, check receipt hashes **after final code edits**, and
reconcile raw rows, distinct inputs, events and customer groups separately. Every
new dated public evidence set needs a reproducible source/command/receipt trail.

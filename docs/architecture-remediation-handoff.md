# Transaction Categorisation Architecture and Remediation Handoff

**Status:** Proposed (architecture / process, 25 August 2026)  
**Prepared:** 25 August 2026  
**Audience:** Data Science, Data Engineering, Credit Risk, Information Security, and project sponsors  
**Decision required:** Agree the stabilisation and migration plan before expanding the dictionary or selecting another production model.

> **Not the live research status.** Dictionary ingest, Plaid coverage remeasure, classifier v5, Equifax-tranche rejection, provenance retag, T4 table-join SQL (~158 KB), signed GINI, and v5→v6 eval replacement landed **26 August 2026**. Agents continuing the research work should read [`CLAUDE.md`](../CLAUDE.md) (current-state block first) and [`docs/project-summary.md`](project-summary.md). This document is an architecture-remediation proposal; do not treat its coverage/model numbers or the “1.68 MB SQL” diagnosis as current, and do not rewrite it as if those later measurements were already in the review.

## Executive summary

The project is pursuing the right core strategy:

- Own a provider-independent transaction taxonomy.
- Keep risk attributes separate from ordinary spending categories.
- Use a deterministic waterfall where the evidence is sufficiently strong.
- Use models and LLMs offline to improve coverage, not as an opaque runtime dependency.
- Retain provenance, confidence, abstention, and multiple evaluation views.

The project has, however, outgrown its research-script architecture. The next material improvement is unlikely to come from another large labelling tranche, a larger merchant dictionary, or a more complex classifier. The priority is to make label provenance truthful, eliminate evaluation contamination, move reference data out of generated SQL, establish privacy controls, and make releases reproducible.

This is an incremental reset rather than a rebuild. The existing taxonomy, research findings, rules, and genuinely reviewed labels remain valuable.

## Current position

### What is working well

- A provider-independent taxonomy has been established, with approximately 275 leaves across 29 general categories.
- Provider category limitations and merchant collisions have been investigated in detail.
- The classifier waterfall separates direction, mechanism, entity/dictionary matches, regex rules, provider mappings, and fallback behaviour.
- The project recognises the importance of risk-specific categories and applicant-level predictive value.
- Volume, tail, risk-focused, and locked evaluation sets have all been attempted.
- The test suite is currently green: 19 tests pass, and the Python source compiles.
- Experiment 3 has reported an unfavourable result honestly: the current taxonomy-derived model has not yet beaten the live baseline.

### Why production promotion should pause

The review found several issues that make current performance numbers difficult to trust as production evidence:

1. Most rows currently called `human_reviewed` were resolved by agents rather than humans.
2. Missing Opus predictions can be replaced with other sources and then written back into the Opus-named output, obscuring provenance and potentially creating artificial consensus.
3. The current merchant dictionary cannot be reproduced from the current tranche-four labels; thousands of entries have changed tier or label since dictionary generation.
4. The v5 locked set now overlaps tranche-four labels, the merchant dictionary, and tuning data, so it no longer measures genuinely unseen merchants.
5. The risk evaluation set materially overlaps classifier training inputs. Performance is much stronger on seen examples than unseen examples.
6. The generated BigQuery SQL embeds the dictionary inline and is now approximately 1.68 MB, above BigQuery's 1 MB unresolved GoogleSQL query-length limit.
7. Pending and `unclassified_*` dictionary records are eligible for deterministic tier-four matching.
8. Raw transaction narratives and identifiers appear in tracked data and are sent to external model APIs. This needs an explicit privacy, retention, residency, and vendor approval decision.
9. Experiment 3 has reused its out-of-time period for iterative development and calculates a sign-insensitive GINI. A new untouched confirmation period is required.
10. The repository has few automated controls for provenance, split integrity, SQL/Python parity, approval status, sensitive data, and release reproducibility.

## Target design

The proposed target flow is:

```text
Raw transaction snapshot
        |
        v
Direction and mechanism rules
        |
        v
Counterparty/entity resolution
        |
        v
Transaction-purpose classification
        |
        +--> General category
        +--> Leaf category or parent fallback
        +--> Classification confidence and provenance
        |
        v
Independent risk attributes and applicant-level features
        |
        v
Versioned release, monitoring, and frozen evaluation
```

The important boundary is between resolving *who the counterparty is* and predicting *what this transaction represents*. Entity identity can inform classification, but should not always determine it.

## Workstream 0: Stabilise the current state

### Objective

Create a trustworthy and reproducible baseline before making further model or dictionary changes.

### Practical steps

- [ ] Pause regeneration of the merchant dictionary, training data, production crosswalk, and locked evaluation sets.
- [ ] Identify one current repository commit and one data snapshot as the research baseline.
- [ ] Create a release manifest containing:
  - Git commit.
  - Input file and table hashes.
  - Source snapshot timestamps.
  - Taxonomy and dictionary versions.
  - Model artifact hashes.
  - Script names and runtime parameters.
  - Row counts and category distributions.
- [ ] Replace ambiguous label tiers with truthful source types:
  - `human_reviewed`.
  - `agent_consensus`.
  - `agent_tiebreak`.
  - `model_prediction`.
  - `rule_derived`.
  - `unresolved`.
- [ ] Require a named or pseudonymous human reviewer ID for `human_reviewed` labels.
- [ ] Change `src/fill_agent_tiebreak.py` so it creates a separate derived decision artifact and never overwrites a file representing one model's predictions.
- [ ] Mark existing v5, risk-set, and repeatedly used out-of-time results as exploratory rather than confirmatory.
- [ ] Obtain an Information Security and privacy decision on raw narratives in Git and external LLM processing.
- [ ] Move raw transaction data to approved controlled storage; retain only redacted fixtures and aggregates in Git.

### Deliverables

- Baseline release manifest.
- Label provenance vocabulary and migration mapping.
- Data-handling decision record.
- Register of evaluation sets and whether each is development or confirmation data.

### Acceptance criteria

- Every production-eligible label has a truthful and queryable origin.
- No output associated with one model contains silently substituted predictions.
- The baseline can be regenerated from identified inputs.
- Sensitive-data handling is explicitly approved and documented.

## Workstream 1: Separate entity resolution from transaction classification

### Objective

Prevent merchant identity from being treated as an unconditional transaction-purpose label.

### Why this matters

The same organisation can generate different transaction purposes. A supermarket may also operate petrol stations, mobile services, ATMs, or marketplace payments. HMRC may represent an outgoing tax payment or incoming refund. Payment processors and marketplaces can represent thousands of underlying merchants.

### Proposed outputs

Entity resolution should return:

```yaml
entity_id: tesco
entity_confidence: 0.98
matched_alias: TESCO STORES 4321
collision_possible: true
```

Transaction classification should separately return:

```yaml
general_category: food_and_groceries
leaf_category: supermarket
classification_confidence: 0.87
```

Independent risk annotation should return values such as:

```yaml
gambling: false
essential_spend: true
income: false
priority_debt: false
```

### Practical steps

- [ ] Introduce a stable `entity_id`; do not use normalised merchant text as an entity primary key.
- [ ] Split the existing dictionary into:
  - Alias-to-entity mappings.
  - Entity metadata and category priors.
  - Transaction-context rules.
- [ ] Remove direction, amount, mechanism, description-pattern, and account-context decisions from the alias table.
- [ ] Allow ambiguous aliases to generate multiple candidates or `unknown_entity`.
- [ ] Add collision flags for processors, marketplaces, government bodies, councils, transfer narratives, supermarkets, and multi-service organisations.
- [ ] Use entity category as a feature or prior in the classifier, not always as the final label.
- [ ] Assemble a regression dataset focused on known collision merchants.
- [ ] Measure entity-resolution accuracy independently from transaction-category accuracy.

### Acceptance criteria

- One entity can legitimately map to multiple leaf categories based on transaction context.
- Ambiguous aliases cannot automatically become deterministic tier-four classifications.
- Known collision cases pass regression tests.
- Failed resolution can produce `unknown_entity` without forcing an incorrect match.

## Workstream 2: Introduce governed reference tables

### Objective

Manage taxonomy, aliases, rules, labels, and releases as versioned data rather than generated source-code literals.

### Minimum table set

| Table | Purpose |
|---|---|
| `taxonomy_dim` | Versioned category definitions, hierarchy, status, and effective dates |
| `merchant_entity` | Canonical counterparties and entity metadata |
| `merchant_alias` | Normalised aliases mapped to entities with scope and approval status |
| `classification_rule` | Direction, mechanism, amount, and description rules |
| `label_event` | Immutable history of human, agent, rule, and model label decisions |
| `evaluation_membership` | Immutable assignment of transactions to evaluation sets |
| `classifier_release` | Artifact hashes, inputs, metrics, status, and deployment metadata |

Recommended `merchant_alias` fields include:

- `alias_id`.
- `normalised_alias`.
- `entity_id`.
- `provider_scope`.
- `direction_scope`.
- `confidence`.
- `review_status`.
- `source_type` and `source_id`.
- `effective_from` and `effective_to`.
- `taxonomy_version`.

### Practical steps

- [ ] Define table schemas and validation constraints in version-controlled SQL.
- [ ] Load the current taxonomy, dictionary, and rules into staging tables.
- [ ] Create approved views that expose only active, approved, currently effective records.
- [ ] Exclude `pending`, `rejected`, and `unclassified_*` entries from deterministic matching.
- [ ] Implement a lifecycle of `draft -> reviewed -> approved -> released -> retired`.
- [ ] Make label events append-only; corrections should supersede prior events rather than erase them.
- [ ] Record reviewer type, reviewer/model ID, prompt version, confidence, rationale, source snapshot, and timestamp.
- [ ] Change `src/generate_crosswalk_sql.py` so it generates classification logic and joins reference tables instead of embedding dictionary rows.
- [ ] Run the old and new crosswalks against an immutable comparison sample.
- [ ] Classify and explain every output difference before cutover.
- [ ] Add release manifests and rollback metadata for every published table version.

### Acceptance criteria

- Serving SQL is below the platform query-size limit.
- Only approved, active, classifiable mappings reach production views.
- Every active mapping has an auditable decision trail.
- Training and serving can use the same versioned reference data.
- A prior release can be reconstructed or restored without rebuilding it from mutable files.

## Workstream 3: Build a hierarchical classifier with abstention

### Objective

Improve generalisation and confidence handling without forcing every transaction into one of approximately 275 leaves.

### Proposed hierarchy

1. Determine direction and transaction mechanism.
2. Predict the general category.
3. Run a specialist leaf classifier within that family.
4. Predict risk attributes independently.
5. Return a parent category or abstain when leaf evidence is insufficient.

Example:

```text
outgoing
  -> food_and_dining
       -> restaurant / takeaway / pub / supermarket
```

### Practical steps

- [ ] Preserve the current flat TF-IDF classifier as the comparison baseline.
- [ ] Train a general-category model on clean, provenance-filtered labels.
- [ ] Train specialist leaf models for families with enough examples.
- [ ] Keep deterministic rules or parent-only output for data-starved families.
- [ ] Add resolved entity, provider category, direction, mechanism, amount band, recurrence, and description tokens as features.
- [ ] Avoid using any field derived from future transaction behaviour relative to the scoring point.
- [ ] Calibrate confidence separately by category family.
- [ ] Define explicit output behaviour:
  - High confidence: return a leaf.
  - Medium confidence: return the parent category.
  - Low confidence: abstain or send for review.
- [ ] Compare flat and hierarchical approaches using leaf accuracy, parent accuracy, risk-weighted recall, abstention coverage, and unseen-entity performance.
- [ ] Explore embeddings or neural classifiers only after the clean linear and hierarchical baselines are established.

### Acceptance criteria

- The hierarchy improves a pre-agreed clean-holdout objective or provides meaningfully safer abstention.
- Rare leaves are not populated by forced low-confidence predictions.
- Every threshold has documented precision and coverage.
- Downstream consumers can accept parent-category and abstained outputs.

## Workstream 4: Adopt active learning

### Objective

Spend human-review capacity on examples with the greatest expected information or risk value rather than labelling another blanket high-volume tranche.

### Review-batch composition

Each batch should deliberately combine:

- High-volume unknown merchants.
- Model-versus-rule or model-versus-provider disagreements.
- High-uncertainty predictions.
- Novel entity clusters.
- Known collision merchants.
- Risk-critical categories.
- Rare leaves.
- A random audit sample.

### Practical steps

- [ ] Score the unlabelled pool with the current production candidate.
- [ ] Calculate uncertainty, model/rule disagreement, volume, novelty, risk importance, and leaf scarcity.
- [ ] Cluster near-duplicate narratives before sampling.
- [ ] Cap examples per entity so one counterparty cannot dominate a batch.
- [ ] Create minimally necessary, privacy-safe review packets.
- [ ] Reserve human review for ambiguous, collision, risk-critical, and evaluation labels.
- [ ] Treat LLM labels as weak supervision and retain each model's independent output.
- [ ] Record model and prompt versions for all agent-assisted labels.
- [ ] Require two reviewers or adjudication for agreed high-risk categories.
- [ ] Measure accepted labels, corrected labels, new entity coverage, leaf coverage, disagreement rate, and clean-holdout gain after each cycle.
- [ ] Stop a labelling cycle when marginal improvement per reviewed item becomes negligible.

### Acceptance criteria

- Every batch has a versioned sampling specification.
- Duplicates and easy examples no longer dominate review volume.
- Agent-assisted labels remain distinguishable from human labels.
- Labelling value is reported per reviewed example, not only as total dataset growth.

## Workstream 5: Optimise for underwriting and risk signals

### Objective

Measure success by incremental, stable underwriting value rather than taxonomy accuracy alone.

### Candidate risk outputs

- Salary and income regularity.
- Benefits and pension income.
- P2P versus own-account transfers.
- Gambling activity.
- Debt repayments.
- Priority debts.
- Arrears or returned payments.
- Essential versus discretionary expenditure.
- Rent and housing costs.
- Cash withdrawals.
- Subscriptions and recurring commitments.
- Refund frequency.
- Income volatility.

### Practical steps

- [ ] Agree with Credit Risk which decisions or scorecard components the work should improve.
- [ ] Define every risk signal, including exclusions and ambiguous cases.
- [ ] Build applicant-level temporal features such as:
  - Monthly frequency.
  - Median amount and variability.
  - Cadence regularity.
  - First and last observed dates.
  - Share of income or expenditure.
  - Trend and recurrence.
  - Counterparty concentration.
- [ ] Develop explicit own-account-transfer logic so transfers are not simultaneously treated as income and expenditure.
- [ ] Determine income using counterparty, direction, cadence, amount stability, and transaction text rather than a single merchant label.
- [ ] Compare models incrementally:

```text
live baseline
+ provider categories
+ taxonomy aggregates
+ entity features
+ temporal and risk features
```

- [ ] Evaluate by provider, time period, cohort, and data availability.
- [ ] Add bootstrap confidence intervals and paired comparisons.
- [ ] Remove features that are unstable, difficult to explain, or provide no out-of-time benefit.
- [ ] Report transaction-classification metrics separately from credit-risk metrics.

### Acceptance criteria

- Every production risk feature has a business definition and end-to-end lineage.
- Features provide incremental value on untouched out-of-time data.
- Performance is acceptably stable across providers, periods, and relevant customer cohorts.
- Transfer and income logic passes targeted applicant-level case reviews.

## Workstream 6: Rebuild frozen evaluation

### Objective

Create independent evidence of production generalisation and prevent evaluation data from influencing training or model selection.

### Required evaluation sets

| Set | Purpose |
|---|---|
| Volume | Measure ordinary production traffic, coverage, and weighted accuracy |
| Novelty | Measure generalisation to entities absent from training, rules, and the dictionary |
| Risk | Measure recall and errors for pre-agreed risk-critical classes |
| Temporal confirmation | Measure underwriting value on a later period used only for final confirmation |

### Practical steps

- [ ] Preserve source transaction IDs, applicant IDs, entity IDs, and snapshot dates.
- [ ] Assign immutable evaluation membership before model training begins.
- [ ] Split by applicant before splitting individual transactions.
- [ ] For novelty evaluation, exclude all aliases attached to training entities rather than only exact merchant strings.
- [ ] Check overlap by:
  - Transaction ID.
  - Applicant ID.
  - Entity ID.
  - Normalised merchant.
  - Exact description and transaction attributes.
  - Dictionary and rule source.
  - Label-event ancestry.
- [ ] Freeze the training snapshot before creating a new v6 evaluation set.
- [ ] Separate training, validation, development OOT, and confirmation OOT roles.
- [ ] Prevent repeated inspection of the confirmation set during model development.
- [x] Correct the GINI calculation in `src/experiment3_taxonomy_iv.py` so inverted scores are not silently treated as equivalent. (`signed_gini`, 2026-08-26; published 0.328 vs 0.308 were unsigned — do not re-quote until re-scored)
- [ ] Add bootstrap confidence intervals and paired comparisons with the live baseline.
- [ ] Make leakage checks mandatory CI gates for dataset and model releases.

### Acceptance criteria

- V6 has zero prohibited overlap by transaction, applicant, entity, and label ancestry.
- Risk-set inputs do not occur in the model's training inputs.
- Confirmation data has not been used for feature selection, thresholds, or model choice.
- Reported improvements include uncertainty and a paired baseline comparison.

## Delivery sequence

Effort should be estimated by the delivery team after ownership and infrastructure constraints are confirmed. The phases below show dependencies rather than fixed calendar commitments.

### Phase 1: Containment

- Freeze generated artifacts.
- Correct provenance terminology.
- Stop cross-model output overwrites.
- Resolve privacy and external-model processing requirements.

**Gate:** No new labels, mappings, or evaluations are promoted until provenance and data-handling decisions are complete.

### Phase 2: Governance

- Create versioned reference schemas.
- Migrate labels as immutable events.
- Filter production mappings by approval status.
- Remove `unclassified_*` from deterministic tier four.
- Introduce manifests and release IDs.

**Gate:** A release can be reproduced and audited from its manifest.

### Phase 3: Serving migration

- Load governed reference data into BigQuery.
- Replace embedded dictionary arrays with table joins.
- Run old/new parity and performance tests.
- Publish the first governed crosswalk release.

**Gate:** Approved mappings behave as expected, differences are explained, and serving is within platform limits.

### Phase 4: Evaluation reset

- Freeze the eligible training universe.
- Build new volume, novelty, risk, and temporal evaluation sets.
- Add automatic overlap checks.
- Reclassify historical results as exploratory where necessary.

**Gate:** Independent review confirms that the new sets meet their isolation rules.

### Phase 5: Modelling

- Re-establish the clean flat baseline.
- Train and assess hierarchical models.
- Calibrate parent fallback and abstention.
- Compare candidates only on approved development evaluations.

**Gate:** A candidate meets agreed performance, calibration, stability, and coverage thresholds without using confirmation data.

### Phase 6: Risk optimisation and continuous active learning

- Build applicant-level temporal and risk features.
- Measure incremental underwriting value.
- Use model errors and uncertainty to select review batches.
- Promote new data and models through the governed release process.

**Gate:** The final candidate demonstrates stable incremental value on the untouched temporal confirmation cohort.

## Recommended ownership

| Area | Accountable role | Supporting roles |
|---|---|---|
| Taxonomy definitions | Credit Risk or domain product owner | Data Science, Operations |
| Entity and alias tables | Data Engineering | Data Science, Operations |
| Label policy and adjudication | Domain labelling owner | Credit Risk, Data Science |
| Classifier and calibration | Data Science | ML Engineering |
| BigQuery serving | Data Engineering | Data Science |
| Evaluation isolation | Independent Data Science reviewer | Credit Risk, Data Engineering |
| Privacy and model-vendor approval | Information Security/Privacy | Legal, Data Science |
| Release approval | Named project sponsor | Risk, Data, Security |

No individual should both construct the final confirmation set and make an unreviewed assertion that it is leakage-free.

## Initial backlog

### Priority 0: Must happen before further promotion

- [ ] Freeze and hash current inputs and artifacts.
- [x] Stop overwriting model-specific prediction files. (`src/fill_agent_tiebreak.py` writes `production_predictions_opus_filled.csv`; 2026-08-26)
- [x] Correct false `human_reviewed` provenance. (tranche 4: 91,803 → 4 Carlos; remainder `agent_*`; 2026-08-26)
- [x] Block pending and unclassified dictionary entries from deterministic matching. (36 dropped; original seed including Tesco marked `approved` — `pending` was a stale flag; 2026-08-26)
- [ ] Decide how tracked raw transaction data and external API processing will be handled.
- [x] Mark contaminated evaluation sets as development-only. (v5 retired as confirmation gold 2026-08-26; iteration suite unchanged. v6 drafts done, human review outstanding.)

### Priority 1: Restore a production-capable foundation

- [ ] Create governed BigQuery schemas and approved views.
- [x] Migrate the crosswalk from inline arrays to joins. (`sql/apply_crosswalk.sql` joins `credit_risk_research.merchant_dictionary_t4`; 2026-08-26)
- [ ] Add release manifests and immutable label events.
- [ ] Add automated leakage, provenance, and approval-status tests.
- [x] Build a genuinely isolated v6 evaluation set. (builder + 1,100-row sample + Gemini/Sonnet drafts 2026-08-26; human review still outstanding)

### Priority 2: Improve the approach

- [ ] Separate entity resolution from purpose classification.
- [ ] Establish flat and hierarchical clean baselines.
- [ ] Add calibrated parent fallback and abstention.
- [ ] Launch the first active-learning batch.
- [ ] Build applicant-level risk feature families.

### Priority 3: Production decision

- [ ] Validate operational cost, latency, monitoring, and rollback.
- [ ] Run the final untouched temporal evaluation.
- [ ] Complete Risk, Data, and Security approval.
- [ ] Release with a versioned model card and monitoring plan.

## Tests and controls to add

The existing taxonomy invariant tests should be retained and expanded with:

- Generator idempotence tests.
- SQL/Python classification parity tests.
- Approval-status filtering tests.
- `unclassified_*` non-promotion tests.
- Model-source provenance tests.
- Dictionary reproducibility tests.
- Transaction, applicant, merchant, and entity overlap tests.
- Label-ancestry leakage tests.
- Known merchant-collision regression tests.
- Sensitive-data scanning for tracked fixtures.
- Temporal feature cut-off tests.
- Confidence calibration and abstention tests.
- Release-manifest completeness and artifact-hash tests.

## Decisions required from stakeholders

1. Who is authorised to approve labels and mappings for production?
2. Which external model vendors and processing modes are approved for transaction narratives?
3. What raw data may be stored in Git, local workspaces, BigQuery, and model prompts?
4. Which risk categories require double review or mandatory human adjudication?
5. What minimum performance, stability, coverage, and abstention thresholds constitute production readiness?
6. Which later time period can be reserved as a genuinely untouched confirmation cohort?
7. Which team owns ongoing entity resolution and alias curation after the research phase?

## Definition of done

The project is ready for a production decision when:

- Every production mapping and training label has truthful, immutable provenance.
- Reference data is governed, versioned, approved, and served from tables.
- Raw sensitive data is handled under an approved policy.
- Training and serving transformations use the same released definitions.
- Evaluation sets are isolated by applicant, transaction, entity, time, and label ancestry as appropriate.
- The chosen classifier is calibrated and can abstain or return a parent category.
- Incremental underwriting value is demonstrated on an untouched temporal cohort with uncertainty reported.
- Release artifacts, inputs, metrics, and rollback instructions are reproducible.
- Data Science, Data Engineering, Credit Risk, and Information Security have approved the release.

## Key implementation touchpoints

- `src/build_tranche4_final_labels.py`: correct provenance and tier semantics.
- `src/fill_agent_tiebreak.py`: preserve model identity and write a distinct derived output.
- `src/build_merchant_dictionary.py`: require approved, stable, classifiable sources and make generation reproducible.
- `src/generate_crosswalk_sql.py`: replace inline dictionary generation with governed table joins.
- `src/build_gold_v5_locked.py`: supersede with a v6 builder using complete exclusion rules.
- `src/build_tuning_dataset.py`: centralise split and ancestry exclusion controls.
- `src/score_classifier_risk_categories.py`: supersede the contaminated evaluation with an isolated risk set.
- `src/experiment3_taxonomy_iv.py`: correct GINI and separate development from confirmation periods.
- `src/production_labelling.py`: minimise prompt data and enforce approved model-processing configuration.

## Final recommendation

Do not discard the taxonomy or deterministic waterfall. Preserve the research, but pause further dictionary expansion and production model selection until the project can reliably answer three questions:

1. Where did this label or mapping come from?
2. Was this evaluation example genuinely unseen?
3. Can this exact release be reproduced and safely operated?

Once those foundations are in place, hierarchical classification, active learning, and applicant-level risk features can be evaluated quickly and credibly.

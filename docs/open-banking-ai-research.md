# Open Banking AI: Research Findings & Options for Raylo

*Prepared for the AI Acceleration team, following the [INT] AI Acceleration weekly (22 Jun 2026) discussion on Open Banking / LLM credit scoring.*

## Recap: what was agreed in the meeting

Three architectural options for open banking + LLM credit decisioning:
1. **LLM-generated features → standard ML model** (agreed near-term path, Carlos leading, Adam executing)
2. **Fine-tuned open-source LLM making decisions directly** (research track, after 1 is stable)
3. **Full transformer-based approach** (parked — "too far out")

This doc maps external research and vendor landscape onto that framework, adds categories the meeting didn't cover, and scores each on effort vs upside.

---

## 1. Directly validates Option 1: automated feature generation

**Revolut — Deep Feature Synthesis (DFS) + Marginal Information Value (MIV)**

- DFS automatically generates features by traversing relational/temporal structure in transaction data (e.g. `customer.TREND(account_history.amount_past_due WHERE contract_type=Personal_Loan)`), run nightly on all transaction data for every credit application.
- MIV is the feature *selection* layer — iteratively picks features that are independent of each other but collectively maximise model performance, stopping when GINI on test set stops increasing.
- **Result**: personal loan model using this ~30% increase in sales (mostly higher take-up, not more approvals) + reduced delinquency. Positive selection effect — better prices attract lower-risk borrowers who'd otherwise go elsewhere.
- **Revolut's own stated next step**: use LLMs for even more nuanced feature generation from relationships between data sources, plus embeddings as model inputs. i.e. Revolut is moving *toward* your Option 1/2, not away from it.

**Effort**: Medium — Featuretools (open source Python lib) implements DFS directly; this isn't proprietary Revolut tech, it's a known MIT algorithm. Feature *selection* (MIV/WoE/IV) is standard credit scoring methodology your data science background already covers.
**Upside**: High — directly reusable for Option 1, doesn't require any transformer/LLM infrastructure to get started, and has a proven real-world credit outcome (not just an academic benchmark).
**Fit**: This *is* a concrete implementation path for Option 1. Recommend starting here rather than jumping straight to "LLM generates features" — get DFS + MIV working on structured transaction data first, then evaluate whether an LLM adds anything DFS can't already do relationally.

---

## 2. Directly validates Option 3 (with an important caveat)

**Revolut — PRAGMA foundation model** (arXiv:2604.08649)

- Encoder-only transformer, 10M–1B params, pre-trained with masked modelling on 26M users / 24B events / 207B tokens of banking event history (transactions, app events, comms, trading).
- One backbone → six downstream tasks via frozen embedding probe or LoRA fine-tuning (2-4% of params updated).
- Credit scoring: **+130.2% PR-AUC, +12.4% ROC-AUC** vs task-specific baselines. Similar large gains on fraud, comms engagement, product rec.
- **Important limitation**: PRAGMA *failed* on AML (-47.1% F0.5) because it processes each user's event history in isolation and can't capture cross-record/network signals that relational AML detection needs. Foundation models on transactions are not a universal hammer.
- Training cost: 1B param model needed 32× H100s for ~2 weeks. Not a side project.

**Nubank — nuFormer** (arXiv:2507.23267): smaller-scale version of the same idea — adapt transformer representation learning to transaction data, fuse learned embeddings with existing tabular features, gains purely from better representations (no new data sources).

**Effort**: Very high — this needs serious ML infra, a large pre-training corpus, and months of engineering even at small scale. Genuinely not something to attempt before Option 1 is stable, consistent with the meeting's "parked" framing.
**Upside**: Very high *if* Raylo has enough transaction volume and multiple downstream tasks (credit + fraud + LTV + churn) to justify a shared backbone — the whole pitch is amortising pre-training cost across many use cases. Worth revisiting once Option 1 has generated a track record and a second/third use case is on the roadmap (fraud? churn?).
**Fit**: Correctly parked. Flag the AML failure mode for whenever this does get picked back up — don't assume a transformer approach transfers to every future use case.

---

## 3. Buy vs. build — categories the meeting didn't discuss

**Cash-flow underwriting is now a mature, purchasable product category.** This is the single biggest thing worth raising with the team: before spending months building Option 1 from scratch, it's worth knowing what's already on the market.

- **Prism Data CashScore**: a three-digit score built from open banking/deposit data, trained on a multi-lender consortium dataset. Claims ~30% predictive lift over bureau scores alone, works for thin-file/no-file consumers, ships with FCRA/ECOA-compliant adverse action reason codes as a *core* feature (not an afterthought). Also sells "Ability-to-Pay" — automated DTI/affordability calc inclusive of gig income, BNPL obligations, rent, subscriptions.
- Resold through Equifax and LexisNexis, so it may already be reachable via existing bureau relationships rather than a fresh vendor contract.
- **Effort**: Low (integration, not model-building) if going the buy route; **Upside**: Medium-high but caps out at "as good as an off-the-shelf consortium model" — no Raylo-specific edge, and you don't build internal capability (which the meeting explicitly flagged as a goal of Option 1).
- **Recommendation**: worth a scoping call even if the team stays on the build path — as a benchmark to beat, or a fallback if Option 1 timelines slip.

**Transaction categorisation/enrichment is also a solved, buyable problem.**
- **Ntropy**: LLM-based API that turns messy bank transaction descriptions into clean merchant names, categories, recurring-payment flags. Their own engineering notes are candid: large LLMs (175B+) are more *accurate* with a good prompt, but they run stacks of small language models (≤1B params) in production because that's the only way to hit accuracy + latency + cost at billions of transactions/month.
- **Effort**: Low (API integration) vs building categorisation in-house.
- **Upside**: Medium — this is infrastructure underneath any feature-generation pipeline (DFS-style features need clean merchant/category data to work well), not a differentiator itself.
- **Fit**: Could de-risk and accelerate Option 1 — better categorisation directly improves DFS feature quality. Cheap to test.

---

## 4. A category the meeting missed entirely: financial vulnerability detection

This deserves separate attention because it's a live UK regulatory expectation with a concrete precedent, not a hypothetical.

- FCA has six explicit expectations around vulnerable customers, and gambling-related harm specifically is called out because at-risk groups are **over-represented in high-cost credit, motor finance, and revolving credit that isn't paid off in full** — categories close to Raylo's customer base.
- **South Manchester Credit Union** already does this in practice: analyses up to 3 months of Open Banking data at loan application, and where gambling transactions appear, proactively shares that analysis with the member as part of Consumer Duty compliance — not to decline them, but to support them.
- One bank found ~2.8% of customers showed signs of harmful gambling, ~1% a serious concern.

**Effort**: Medium — this reuses the same transaction categorisation/feature layer as Option 1 (gambling merchant category codes, frequency/amount patterns), it's mostly a downstream *use* of infrastructure you're building anyway, plus a customer comms/ops workflow.
**Upside**: High on a non-financial dimension — Consumer Duty compliance, genuine customer harm reduction, and good PR/regulatory goodwill; moderate financial upside via better-targeted forbearance/support reducing default cascades.
**Fit**: Strong candidate to bolt onto Option 1's output rather than being a separate project — same underlying transaction features, different application layer.

---

## 5. Regulatory reality check on the "build first, then have the FCA conversation" plan

Worth raising back to the team, gently: the meeting's LLM-explainability approach (ask the model for bullet-point reasons, monitor for bias) carries more legal risk than it might sound like, per legal commentary on adverse action requirements:

> "The shadow-deployment phase generates explanations from a different model than the one making decisions, so the reasons drift from the actual driver... The model that issues the decision should be the model that produces the reasons. SHAP on a black box gives you a story; an interpretable model gives you the actual driver."

The good news: **Option 1's architecture is actually well-suited to this constraint already**, without needing to change plan. If the LLM only *generates features* and a conventional (monotonic/interpretable) ML model makes the actual accept/decline decision, that decision model can produce faithful SHAP-style reason codes tied to the real decision driver — you're not asking an LLM to explain its own black-box judgment. Worth being explicit about this distinction (LLM-as-feature-factory vs. LLM-as-decision-maker) when the FCA conversation eventually happens, since Option 2 (LLM decides directly) is where the adverse-action risk gets much harder.

---

## 6. Adjacent opportunities worth a mention (lower priority, for the brainstorm)

| Idea | Effort | Upside | Notes |
|---|---|---|---|
| **Income verification for gig/irregular income** | Medium | Medium-high | Open banking + AI to normalise irregular deposits into a usable income figure — directly relevant if Raylo customers include gig workers with non-PAYE income patterns |
| **Synthetic transaction data for model dev** | Medium | Medium | Real academic result: synthetic-trained credit models lose ~3% AUC / 6% KS vs real-data-trained — an acceptable tradeoff if it lets Adam build/test Option 1 without needing production data access from day one |
| **Agentic underwriting workflow (beyond scoring)** | High | Medium (now) / High (later) | 2026 vendor trend is agents running the *whole* underwriting workflow (data gathering, verification, memo, escalation), not just scoring. Premature before Option 1 is stable, but a natural v2 once the scoring layer works — could reuse Pricing Agent's LangGraph-style architecture |
| **AML / relational fraud detection** | High | Medium | PRAGMA's own failure case — flagging so nobody assumes the transformer approach automatically extends here later; relational/graph methods are a different problem class |

---

## Suggested discussion order for next session

1. Does DFS + MIV (section 1) give us a faster path to a working Option 1 prototype than "ask an LLM to invent features from scratch"?
2. Is a Prism Data / Equifax scoping call worth 30 minutes, purely as a benchmark or fallback?
3. Should gambling/vulnerability detection (section 4) be scoped as a *use* of Option 1's output rather than a separate initiative?
4. Confirm the LLM-as-feature-factory vs. LLM-as-decision-maker distinction before the FCA conversation happens — does this change how "Option 2" (fine-tuned LLM decides directly) gets framed?

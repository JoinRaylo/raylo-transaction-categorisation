# Open Banking AI: Implementation Detail — DFS & Fine-Tuning/Foundation Model Approaches

Follow-up to `open-banking-ai-research.md`. Covers: (1) how to actually implement Deep Feature Synthesis, and (2) tangible data/compute/process requirements for Options 2 & 3 (fine-tuning an existing LLM vs. building a PRAGMA-style foundation model from scratch).

---

# Part 1: Implementing Deep Feature Synthesis (DFS)

## 1.1 The core idea in one sentence

DFS treats your data as a **relational graph** (customers → applications → transactions → merchants) and mechanically walks that graph applying aggregation functions (sum, mean, trend, count-where...) at each hop, so instead of hand-writing "average spend in last 30 days" you generate hundreds of such features automatically and let a selection step (Part 1.4) decide which ones actually matter.

## 1.2 Step 1 — Structure your data as an EntitySet

The library is **Featuretools** (`pip install featuretools`), open source, MIT-algorithm-backed (the same one Revolut cites). It needs your data shaped as a set of tables with declared relationships — this maps almost exactly onto your existing dbt model structure (customers, applications, transactions, orders).

```python
import featuretools as ft

# Each entry: (dataframe, index_column, time_index_column [optional])
dataframes = {
    "customers":    (customers_df,    "customer_id"),
    "applications":    (applications_df, "application_id", "application_date"),
    "transactions": (transactions_df, "transaction_id",  "transaction_time"),
}

# (parent_df, parent_col, child_df, child_col)
relationships = [
    ("customers", "customer_id", "applications", "customer_id"),
    ("customers", "customer_id", "transactions", "customer_id"),
]

feature_matrix, feature_defs = ft.dfs(
    dataframes=dataframes,
    relationships=relationships,
    target_dataframe_name="applications",   # one row per credit decision
    agg_primitives=["sum", "mean", "std", "trend", "mode", "skew", "count"],
    trans_primitives=["month", "weekday", "time_since_previous"],
    where_primitives=["count", "sum"],      # enables conditional aggregations
    max_depth=2,
)
```

For Raylo specifically, `target_dataframe_name="applications"` (or your equivalent evaluation-point table) is the key choice — it's "one row per thing we're scoring," and DFS builds every feature relative to that.

## 1.3 Step 2 — The features you actually get

With `max_depth=2` you get things like:
- `SUM(transactions.amount)` — depth 1, straightforward aggregation
- `MEAN(transactions.MONTH(transaction_time))` — depth 2, a "deep feature"
- `COUNT(transactions WHERE category = 'gambling')` — via `where_primitives`, directly relevant to the vulnerability-detection use case from the first doc
- `TREND(transactions.amount, transaction_time)` — Revolut's example primitive, captures whether spending is rising/falling over time

`max_depth=3+` explodes combinatorially — Revolut's own slides note this is why the pipeline needs a selection step immediately after. Realistically, cap at depth 2 initially and only go deeper for specific hypotheses (e.g. Revolut's `TREND(account_history.amount_past_due WHERE contract_type=D3.Personal_Loan)` is a hand-guided depth-3+ feature, not something you'd blindly generate at scale).

## 1.4 Step 3 — Feature selection (the "MIV" half)

Featuretools doesn't include MIV out of the box — that part is standard credit-scoring methodology you implement alongside it. Two building blocks:

**Weight of Evidence / Information Value** — use `optbinning` (`pip install optbinning`), purpose-built for this and already widely used in credit scorecard modelling:

```python
from optbinning import OptimalBinning

optb = OptimalBinning(name="SUM_transactions_amount", dtype="numerical")
optb.fit(feature_matrix["SUM(transactions.amount)"], y)  # y = default flag
optb.binning_table.build()  # gives WoE, IV per bin
```

IV tells you the standalone predictive power of one feature. **Marginal Information Value** is the iterative wrapper: add the feature with the highest *marginal* contribution given what's already in the model, refit, check whether test-set GINI improved, repeat, stop when it plateaus. This isn't a packaged library call — it's a loop:

```python
selected = []
candidates = list(feature_matrix.columns)
best_gini = 0

while candidates:
    gains = {}
    for feat in candidates:
        trial_features = selected + [feat]
        model = fit_logistic_or_gbm(feature_matrix[trial_features], y)
        gains[feat] = compute_gini(model, X_test[trial_features], y_test)
    best_feat = max(gains, key=gains.get)
    if gains[best_feat] <= best_gini:
        break  # no more improvement — stop
    selected.append(best_feat)
    best_gini = gains[best_feat]
    candidates.remove(best_feat)
```

This is exactly the "recursive process, features added iteratively until GINI stops increasing" from Revolut's slides — it's a straightforward greedy forward-selection loop, nothing exotic.

## 1.5 Step 4 — Productionising (mapping onto Raylo's stack)

Revolut's pipeline (fetch → reconstruct state at context date → convert currency → split by tx state → calculate features, run nightly) maps directly onto tools you already run:
- **dbt models** in BigQuery to do the "reconstruct transaction state as of context date" step — this is standard point-in-time correctness, something dbt snapshots handle natively
- **Orchestra** to schedule the nightly DFS batch run (you already use it for dbt scheduling)
- Output: a feature-store-style table in BigQuery, one row per application/customer/evaluation-point, feeding into Lightdash for monitoring feature drift and into the actual scoring model

**Practical gotcha to flag to Adam early**: DFS needs point-in-time correctness — the feature at evaluation time must only use data available *before* that point, or you leak future information into the model (this is the single most common real-world bug in this kind of pipeline). Worth writing a specific test for this before trusting any output.

## 1.6 What you need before starting

- A `bad` flag (default/delinquency outcome) with enough positive examples — classic scorecard literature (which Revolut cites — Siddiqi's *Intelligent Credit Scoring*) generally wants a few hundred to a few thousand "bad" cases minimum for stable WoE bins; check what volume you actually have before committing time here
- Clean transaction categorisation (garbage in, garbage out — this is where Ntropy-style enrichment from the first doc becomes a genuine prerequisite rather than a nice-to-have)
- A defined evaluation point (the application/decision moment) with a temporal boundary DFS can respect

---

# Part 2: Fine-tuning / building an LLM for direct decisioning (Options 2 & 3)

These are genuinely two different technical projects wearing similar names. Worth being explicit about which one you mean before scoping either.

| | **Option 2: Fine-tune an existing open LLM** | **Option 3: Build a PRAGMA-style foundation model from scratch** |
|---|---|---|
| What it is | Take Llama/Mistral/Qwen, teach it to read a transaction history and output a score/decision | Pre-train a bespoke transformer encoder on raw banking events, purpose-built for tabular/sequential financial data |
| Data needed | ~1,000–50,000 labelled examples | Tens of millions of user histories, billions of events |
| Compute | Single GPU (24–80GB) | Dozens of H100s for days-to-weeks |
| Realistic for Raylo now? | Yes, as an experiment | No — this needs Revolut/Nubank-scale data and infra |

## 2.1 Option 2 — Fine-tuning an existing open-source LLM

**Data requirements, concretely**: industry guidance for LoRA/QLoRA classification fine-tuning is a minimum viable dataset of **1,000–5,000 high-quality labelled examples**, with **10,000–50,000 as a production-grade baseline**. For credit risk specifically, the constraint that actually bites is class imbalance, not raw row count — if your default rate is ~5%, a 10,000-row dataset only has ~500 "bad" examples, which is thin. Practically: aim for at least a few thousand bad cases, which likely means tens of thousands of total rows given typical Raylo default rates — check this against what you actually have before scoping the project.

**Step-by-step process**:

1. **Assemble & label the dataset.** One row per customer/application, with a serialised transaction history as input and the outcome (default within N months) as the label. Serialisation matters a lot — a raw dump of transaction rows wastes tokens; something closer to PRAGMA's key-value-time format works better than free text:
   ```
   [2026-04-01] card_payment, -£45.20, TESCO, category=groceries
   [2026-04-03] direct_debit, -£89.00, RAYLO, category=device_lease
   [2026-04-05] transfer_in, +£1,850.00, source=salary
   ...
   Profile: account_age=340d, region=UK, balance_quantile=Q3
   ```
2. **Pick a base model.** Llama 3.1 8B, Mistral 7B, or Qwen2.5 7B are the standard open-weight starting points. Given Ntropy's own finding that large general LLMs beat smaller fine-tuned ones on raw *accuracy* but small fine-tuned models win on cost/latency at scale, start with a mid-size model (7-8B) rather than reaching for the biggest open model available.
3. **Set up QLoRA fine-tuning** via Hugging Face `peft` + `bitsandbytes`. Typical config: 4-bit NF4 quantisation of the frozen base model, LoRA rank 8–16 applied to attention (`q_proj`, `k_proj`, `v_proj`, `o_proj`) and MLP (`gate_proj`, `up_proj`, `down_proj`) layers — this is literally the same recipe PRAGMA uses for its downstream adaptation, just applied to a general-purpose LLM instead of a bespoke encoder.
   ```python
   from peft import LoraConfig, get_peft_model
   from transformers import AutoModelForSequenceClassification, BitsAndBytesConfig

   bnb_config = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4")
   model = AutoModelForSequenceClassification.from_pretrained(
       "mistralai/Mistral-7B-v0.1", quantization_config=bnb_config, num_labels=2
   )
   lora_config = LoraConfig(
       r=16, lora_alpha=16,
       target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
       task_type="SEQ_CLS",
   )
   model = get_peft_model(model, lora_config)
   ```
4. **Train.** A single RTX 4090 (24GB) or A100 (40-80GB) is genuinely sufficient at this scale — this is not a multi-GPU cluster project. Training time: hours to a couple of days depending on dataset size, not weeks.
5. **Evaluate** against your existing pricing/risk model baseline using AUC, PR-AUC, and KS statistic (the standard credit-scoring metrics you're already using for the Pricing Agent work) — not just classification accuracy, which is misleading under class imbalance.
6. **Solve explainability before going near production.** This is the step most guides skip and where the real risk sits (see the adverse-action discussion in the first doc). If the LLM is the decision-maker, you need a way to produce faithful reason codes tied to the actual decision driver, not a post-hoc SHAP story on a black box. Realistic options: constrain the LLM to a small, auditable set of extracted factors it must cite; or fall back to the "LLM as feature generator, interpretable model decides" pattern from Option 1, which avoids this problem entirely.
7. **Deploy** as a batch or near-real-time scoring step — LoRA adapters merge cleanly into the base model for inference, adding no extra latency vs. a plain fine-tune.

**Honest framing for the team**: this is a good *research/comparison* project — worth doing to see whether it beats Option 1's feature-generation approach — but it inherits Option 2's regulatory risk (point 6) in a way Option 1 doesn't. That's a genuine trade-off to weigh, not just an engineering choice.

## 2.2 Option 3 — Building a PRAGMA-style foundation model from scratch

Being direct about this: **it's not realistic at Raylo's current scale**, and the numbers explain why clearly enough to make that case to anyone who asks.

- **Data**: PRAGMA was pre-trained on 26 million users, 24 billion events, 207 billion tokens, spanning 111 countries and 25 months. Even their smallest useful variant (PRAGMA-S, 10M params) needed that same corpus to pre-train on — the small model is cheap to *run*, not cheap to *create*. Raylo's customer base and transaction volume are not at neobank scale.
- **Compute**: PRAGMA-S trained on 16× H100 GPUs for ~2 days; PRAGMA-M and PRAGMA-L each needed 16–32× H100s for ~2 weeks. At current cloud GPU pricing that's roughly **$50,000–$500,000+ of compute for one training run**, before any of the iteration, hyperparameter search, or engineering time (sequence packing, dynamic batching, custom tokenisation) the paper describes as necessary to make it work at all.
- **What you'd actually need to justify this**: enough transaction volume to make self-supervised pre-training meaningful, and — critically — multiple downstream tasks (credit + fraud + LTV + churn, as PRAGMA does) to amortise that one-time cost across. A single-use-case justification doesn't clear the bar.

**The honest middle ground, if this comes up again in future**: rather than building a foundation model from scratch, two cheaper paths exist if Option 1 proves out and the team wants to revisit "should we go further":
- **TabPFN-v2.5** — an open, already-pretrained tabular foundation model (trained on synthetic priors, not requiring your own billions of events) that can be applied directly to structured features via in-context learning, no training run required. Worth a cheap experiment as a comparison point to a GBM, without any of PRAGMA's infra cost.
- Wait and watch whether a vendor (Prism Data, or a bureau) ships something PRAGMA-like commercially — Revolut's paper is a research artifact, not a licensable product, but the pattern may show up as a purchasable service before it's worth Raylo building in-house.

**Recommendation**: keep this parked, as the meeting already concluded, and treat the PRAGMA paper as useful context for *why* it's parked (concrete numbers to point to) rather than a near-term roadmap item.

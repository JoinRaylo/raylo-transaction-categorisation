# Distillation labels — Gemini + Sonnet consensus on the 500k most frequent Plaid texts (2026-09-05)

**Purpose.** Training signal for the T5b classifier (transformer distillation), never a source of
truth: not served, not a dictionary source, not an eval set. Gold sets stay human-adjudicated.

**Sample.** `TRANCHE=distil fetch`: the 500,000 most frequent distinct `(merchant, description,
direction)` texts on live Plaid (from 800k candidates), each with its median amount and modal
Plaid category; covers **2,640,930 live rows (61.7%)**. Merchant-level exclusion only for the
merchant-disjoint evals (holdout, risk gold, credit eval, T6-bound risk gold); exact-text
exclusion for every other gold file. Dictionary/tranche merchants deliberately kept.

**Labelling.** Gemini 3.7 Flash (thinking off, 120 s timeout) and Claude Sonnet 5, row-level
prompt shared with gold v6, in parallel shards (4 Gemini; Sonnet 3 → 6 → 12 shards, then the
18,784-row tail re-split into 10). ~22 h wall, no rows lost; one shard crash (malformed model
response) and one Gemini hang were fixed in the labeller and resumed from saved predictions.

**Gate — consensus only, no tiebreak (Carlos, 4 Sep).** Evidence from the credit tranche
against Carlos's labels: Gemini==Sonnet rows **95.3%** leaf / 97.7% general correct (n=515);
Opus-tiebreak-accepted rows 63.8% (n=127); a second Gemini call as tiebreak 56.4%. So:

| | rows |
|---|---:|
| labelled by both models | 500,000 |
| Gemini == Sonnet (kept, `agent_consensus`) | **404,982 (81.0%)** |
| disagreements (dropped) | 95,018 |
| live rows covered by kept texts | 2,241,761 (52.4%) |
| leaves present | 271 |
| credit share | 21.6% |

Top leaves: transfer_p2p 120,761 · groceries 24,451 · restaurant_cafe 17,404 · takeaway 15,697 ·
marketplace_amazon 13,813 · convenience_store 13,625 · fuel 11,156 · pub_bar 8,191.

**File.** `data/distillation_labels_consensus.parquet` (columns: row_id, merchant, description,
direction, merchant_raw, description_raw, amount, native_category, n, stratum, provider,
gemini_leaf, sonnet_leaf, final_leaf, tier, general_category). Expected label accuracy ≈ 93–95%
leaf by the consensus measurements above; systematic biases are handled by the accepted
convention remaps at training time, not by editing this file.

**Next.** Use as the first fine-tune pass for the DistilBERT encoder (MLM → distil → gold),
3 seeds, scored against hinge v8 and against the current DistilBERT silver→gold result.

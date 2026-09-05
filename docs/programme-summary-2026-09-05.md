# Transaction categorisation — programme summary as of 5 September 2026

Written for the team after the 2–5 Sep sprint. Evidence for every number is in the dated
reports under `data/` and in `docs/review-2026-09-02-state-and-next-steps.md`.

## 1. What has been built (cumulative)

**A taxonomy Raylo owns.** 275 detailed leaves rolling up to 29 general categories, with
orthogonal dimensions (necessity, cash-flow type, debt, priority debt, age restriction, risk
flag). Verified to cover 100% of both providers' category values. Granularity tests show 275,
the current 69-feature grouping and 29 groups are statistically indistinguishable for risk
GINI, 17 groups is close, 9 and fewer degrade; an expansion pilot to 287 leaves showed no gain.
Keep 275 as the governed source of truth and let models consume rollups.

**A seven-tier waterfall with provenance.** T1 direction overrides → T2 compound merchant+
narrative rules → T3 mechanism overrides → T4 merchant dictionary (90,264 keys) → T5 regex
rules (51) → T5b ML classifier → T6 provider crosswalk → T7 explicit unclassified. Every row
records the tier that decided it. Generated SQL (`sql/apply_crosswalk.sql`) and the Python
evaluation mirror are proven identical on 2,000 rows by `src/check_waterfall_parity.py`.

**Labelled data.** ~100k merchant strings (tranches 1–4, two-model consensus + Opus tiebreak);
30,379 row-level credit labels; 4,998 row-level T6-bound risk debits; 404,982 consensus-labelled
distinct Plaid texts for distillation. Training file 414,400 rows (credit share 7.4%, was 0.65%).

**Evaluation sets** (all human- or consensus-adjudicated, none scored for selection except the
iteration suite): merchant-disjoint holdout (1,055); risk gold (711); row-disjoint pipeline eval
(2,000); credit eval (2,000, merchant-disjoint, 84.3% blind human agreement); T6-bound risk
gold (400); locked v6 (1,100, scored once at go/no-go, untouched).

**Two classifiers for the T5b slot.** Char-TF-IDF + SGD hinge (65 MB, ~1,050 rows/s CPU) at
v8; and a transformer: DistilBERT domain-pretrained on 21.5M transaction sentences, fine-tuned on
the consensus labels then the gold file, with a taxonomy-aware dual head and a direction mask
(~120 MB, 360 rows/s CPU).

## 2. The 2–5 Sep sprint, in order

1. **Programme review** found four measurement problems and fixed them the same week: the risk
   gold set had leaked into training (86.1% → honest 62.7%); credits were 0.65% of training
   (pipeline 53% on credits vs 83% debits); Experiment 3's Equifax history had no as-of filter;
   T4 held 1,575 keys tranche 4 had itself marked ambiguous. Python/SQL parity work also found
   34 hand-written rules that had never fired in BigQuery.
2. **Credit tranche** (30k rows, Carlos-reviewed): hinge credit-eval accuracy 62% → 85%.
3. **Risk rules + tranche**: five card-issuer/overdraft rules (48% → 59% on T6-bound risk
   leaves), then 5k labelled T6-bound risk debits (→ 76% hinge, above the 70% bar for the first
   time).
4. **Transformer**, eight iterations: BERT-small baseline → mask fixes → uncapped training →
   seed confirmation → DistilBERT with full-corpus pretraining on GCP (6.5 GPU-hours, £7) →
   distillation from Gemini+Sonnet consensus labels. Two labelling-quality findings shaped the
   design: consensus rows are 95.3% correct against Carlos, tiebreak-accepted rows only 63.8%,
   so the distillation set is consensus-only, no tiebreak.

## 3. Where the classifier stands (3 seeds each, hinge v8 as reference, same data)

| cut | hinge v8 | transformer (distilled) | Δ [95% CI] |
|---|---:|---:|---:|
| holdout, novel merchants (n=416) | 59.4% | **64.5%** | +5.1 [+1.8, +8.8] |
| pipeline residual (n=478) | 59.8% | **65.0%** | +5.2 [+2.0, +8.2] |
| credit eval (n=2,000) | 85.9% | **88.8%** | +2.9 [+1.8, +4.2] |
| T6-bound risk leaves (n=174) | 75.9% | **85.6%** | +9.8 [+5.2, +15.1] |
| full pipeline T1–T5 then model (n=2,000) | 82.2% | **83.2%** | — |
| general-level accuracy | — | +7 to +13pp | — |
| CPU throughput | ~1,050 rows/s | 360 rows/s | — |

Every accuracy criterion set on 2 Sep now clears with intervals excluding zero. Carlos's call
(5 Sep): 360 rows/s is acceptable for now. The transformer is therefore the recommended T5b
head, pending a serving path. The serving dump in the repo is still the v5 hinge and is 24–28pp
behind on credits and T6-bound risk; promoting hinge v8 is the zero-risk interim step.

## 4. How this feeds the OB-transformer work

The OB-transformer repo (Open Banking risk prediction) currently uses our Experiment 3 taxonomy
features as its reference (`exp3_xgb_refit`, Gini 0.558 on its OOT), and found frozen
`bge-small` text embeddings add +0.011 PR-AUC / +0.017 Gini when stacked on them. Three direct
hand-offs from here:

1. **Regenerate the Experiment 3 features from the current pipeline** (as-of filter, rules R33–
   R51, dictionary 90,264) before quoting any stacked comparison; their reference used the pre-
   fix 80-feature artefact.
2. **Swap the text encoder.** Our DistilBERT encoder is pretrained on 21.5M transaction sentences
   and fine-tuned on 400k+ labelled texts; `bge-small` is generic English. Mean-pooled embeddings
   from `outputs/distill_models/txn_classifier_gold_distilled_s42` are a drop-in replacement for
   the PCA-32 block and should carry more category-aware signal. Cheap to test on their Phase 1
   harness.
3. **Category tokens and per-transaction probabilities.** The classifier's leaf probabilities
   (275-d) or general probabilities (29-d) per transaction are the "category token" the OB
   handoff planned to inject into the sequence model. Both are available from `predict()` in
   `src/transformer/score_transformer.py`; the direction mask guarantees they are legal for the
   transaction's direction.

Keep the stacked embedding block in the final model process as Carlos decided, but decide it in
that repo with the regenerated features, and price in that 32 PCA columns are not explainable
the way category months are.

## 5. Open items and recommended next steps

1. **Promotion path for T5b.** Decide hinge v8 now (zero risk) or the transformer (best
   accuracy, 360 rows/s, ~70 CPU-minutes for the full Plaid table). Either needs: a per-row
   categorisation SQL/job with transaction ids, a serving artefact (ONNX export recommended for
   the transformer), and the one-shot score of locked v6 at go/no-go.
2. **Speed, if the transformer is chosen**: int8 dynamic quantisation + ONNX Runtime (2–3× on
   CPU, a day) or distil into the 29M BERT-small with the same labels.
3. **Frozen prospective test for Experiment 3**: freeze taxonomy/dictionary/classifier with an
   effective date, then score the next matured outcome window once. The retrospective uplift
   (Plaid-only 0.445/0.504 vs live 0.382/0.385) is a bundle effect and needs this before any
   production claim.
4. **Remaining data gaps**: thin risk leaves (debt collection 22 rows, casino 9); a human blind
   slice on the risk tranche (currently agent-only); person-name transfer keys checked and found
   not to be a problem.
5. **Housekeeping**: fold the 3–5 Sep headline lines into CLAUDE.md / README / project summary
   once the concurrent sub-leaf-pilot session commits; delete the GCS scratch bucket when the
   encoder tgz has a second home; Plaid 90-day Asset Report finding still belongs with the
   integration owner.

## 6. Spend this sprint
LLM labelling ≈ £600–900 (credit tranche, risk tranche, 500k-text distillation with two models);
GCP GPU ≈ £7; everything else local.

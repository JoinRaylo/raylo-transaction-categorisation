# benchmarks/

Reproducibility harness for the frontier-LLM / SLM / classifier comparisons in
CLAUDE.md §6a and `docs/project-summary.md`. These scripts previously lived,
uncommitted, under the gitignored `outputs/mlx_full_run/` — every number in the
model comparison table existed only on one laptop. Moved here 2026-08-23 so the
benchmark is reproducible from git alone.

Scripts write their prediction CSVs and logs back into `outputs/mlx_full_run/`
(scratch, gitignored) — only the code and the two small system-prompt text
files are tracked here. Large model artefacts (fine-tuned adapter weights,
~562MB, and intermediate checkpoint scan directories) intentionally stay
untracked in `outputs/mlx_full_run/adapters` and `_ckpt_*` — they're
regenerable from the local Mac fine-tuning runbook (`docs/`), not source data.

- `score_llm.py`, `score_llm_taxonomy.py`, `score_gemini37_finalprompt.py` —
  frontier-model (Haiku/Sonnet/Opus/Gemini) scoring against
  `data/gold_v2_slm_eval_holdout.csv`, at increasing levels of taxonomy
  grounding (bare hint → full enum-constrained taxonomy → final production
  prompt with worked examples).
- `score_vanilla_baseline.py`, `score_local_taxonomy.py`, `score_gold_eval.py`,
  `score_checkpoint_full.py`, `scan_checkpoints.py` — local MLX
  (vanilla/fine-tuned Gemma) scoring and checkpoint sweep.
- `score_gemini_tuned.py`, `convert_to_gemini_format.py` — Vertex AI
  supervised-tuning data prep and scoring for the tuned Gemini 2.5 Flash
  endpoint.
- `compare_prompt_versions.py`, `curated_examples_draft.py`,
  `constrained_decode.py` — the five-variant prompt-compression test
  (CLAUDE.md §6a) and constrained-decoding support.
- `monitor_*.py` — polling helpers used while the Vertex/local training jobs
  ran (not part of the scoring path itself).
- `system_prompt_llm_compare.txt`, `tuning_system_prompt.txt` — the minimal
  system prompts used for the bare-hint and SLM-training-format comparisons.

For the current gold-v4 production-population scorer, see `src/score_gold_v4.py`
(kept in `src/` since it scores against a tracked `data/` gold set, not a
one-off `outputs/` benchmark).

Classifier v4 vs v5 (logreg + SGD hinge) is `src/compare_classifier_versions.py`,
scored on `data/gold_v2_slm_eval_holdout.csv` and
`data/gold_transactions_risk_categories.csv`. Write-up:
`data/classifier_v5_retrain_report.md`. Those 2026-08-26 numbers supersede the
32.0% TF-IDF row in the §6a league table (that row is the 21 Aug dump).
`score_qwen_eval.py` refuses locked confirmation sets (v5 retired; v6 at
go/no-go) via `eval_sets.refuse_confirmation_eval()`.

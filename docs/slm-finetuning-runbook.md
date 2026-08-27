# Fine-tuning Gemma on the Mac — runbook

Self-contained instructions for whichever agent/session runs this on the laptop. Uses **MLX** (Apple's ML framework) since it's the natural, GPU-accelerated choice for local fine-tuning on Apple Silicon — no need to replicate the earlier Vertex AI managed-tuning approach.

> **2026-08-26:** `outputs/tuning_train.jsonl` was rebuilt from tranche 4 and is now **382,183** rows. The SLM / Gemma adapter has **not** been retrained on that file — the §6a numbers (50.0% leaf at ckpt 38000) are the earlier ~164k-row run. Do not assume a new adapter exists. Frozen tranche-3 jsonl: `outputs/tuning_train_v4.jsonl`.

**Inputs already prepared in this repo — don't regenerate these, just use them:**
- `outputs/tuning_train.jsonl` (382,183 rows as of 26 Aug 2026; previously 164,445) — chat-format, one `{"messages": [system, user, assistant]}` per line
- `outputs/tuning_val.jsonl` (5,000 rows) — same format, for training-time validation loss only
- `outputs/tuning_system_prompt.txt` — the exact system prompt baked into every row; reuse byte-for-byte at inference time
- `data/gold_v2_slm_eval_holdout.csv` (1,055 real transactions) — **do not touch during training.** This is the clean, zero-overlap eval set for scoring the finished model. Never fine-tune, validate, or early-stop on it.

## 0. Environment check
```bash
pip install -U mlx-lm
```
Confirm you're on Apple Silicon (`uname -m` → `arm64`) and have enough unified memory free for a ~4B-parameter model plus LoRA overhead (16GB+ recommended; use 4-bit quantization below if tight).

## 1. Get the base model
Search Hugging Face for an MLX-converted Gemma 4 E4B checkpoint (org `mlx-community` typically hosts pre-converted models — search `mlx-community gemma-4`). If no pre-converted version exists, convert it yourself:
```bash
mlx_lm.convert --hf-path google/gemma-4-e4b-it -q --mlx-path ./gemma-4-e4b-mlx
```
(`-q` quantizes to 4-bit — worth it for laptop memory headroom; drop it if you have memory to spare and want full precision.)

## 2. Point MLX at the prepared data
`mlx_lm.lora` expects a folder with `train.jsonl` and `valid.jsonl` (chat format, which ours already is):
```bash
mkdir -p tuning_data
cp outputs/tuning_train.jsonl tuning_data/train.jsonl
cp outputs/tuning_val.jsonl tuning_data/valid.jsonl
```

## 3. Run LoRA fine-tuning
```bash
mlx_lm.lora \
  --model ./gemma-4-e4b-mlx \
  --train \
  --data tuning_data \
  --iters 1000 \
  --batch-size 4 \
  --learning-rate 1e-5 \
  --adapter-path ./gemma-4-adapters
```
Start with these defaults — `--iters 1000` and `--batch-size 4` are conservative for a first run on a laptop. Watch training/validation loss in the console; stop early (`Ctrl+C`, the adapter checkpoints periodically) if validation loss stops improving.

## 4. Sanity-check the adapter
```bash
mlx_lm.generate \
  --model ./gemma-4-e4b-mlx \
  --adapter-path ./gemma-4-adapters \
  --prompt "$(cat outputs/tuning_system_prompt.txt)

merchant: tesco
description: TESCO STORES 3213 STEVENAGE GB
amount: 34.50
direction: debit" \
  --max-tokens 10
```
Expect it to output `groceries` (or close). If it outputs garbage or a category that isn't in the taxonomy, something's wrong before you invest more training time — stop and check the data format.

## 5. Score against the held-out eval set
This is the real test — **don't skip it, and don't substitute a different eval set.** Run the fine-tuned model over every row in `data/gold_v2_slm_eval_holdout.csv`, using the exact same system prompt + user message format as training, and compare its output to `gold_leaf`. Report accuracy back so it can be compared against:
- The current production pipeline's numbers (`data/final_evaluation_v2_report.md`)
- The TF-IDF/logistic-regression classifier's numbers (`data/distillation_bakeoff_report.md`)

If useful, ask the main session (this repo's owner) to write the scoring script — it's a small extension of the same pattern already used in `src/final_evaluation.py`, just swapping in the fine-tuned model's predictions instead of the crosswalk/dictionary.

## Notes
- Do not re-run `src/build_tuning_dataset.py fetch`/`build` from this laptop session — the training/eval files are already committed to the repo (or in `outputs/`, gitignored but already generated). Regenerating them without the exact same logic risks silently breaking the train/eval separation.
- If you need more training iterations or a bigger LoRA rank (`--num-layers`, `--lora-rank` flags), scale up gradually and re-check validation loss rather than guessing a large config up front.

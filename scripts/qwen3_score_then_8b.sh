#!/usr/bin/env bash
# Score the early-stopped Qwen3-4B checkpoint, then train 8B with the same
# early-stop rule (patience=2 evals, min-delta=0.005).
set -euo pipefail
ROOT="/Users/carlosnoblejesus/Repos/raylo-transaction-categorisation"
cd "$ROOT"
PY="$ROOT/.venv/bin/python"
LORA="$ROOT/.venv/bin/mlx_lm.lora"
MODEL4="mlx-community/Qwen3-4B-Instruct-2507-4bit"
MODEL8="mlx-community/Qwen3-8B-4bit"
ADP4="$ROOT/outputs/qwen3_4b_adapters"
ADP8="$ROOT/outputs/qwen3_8b_adapters"
LOG8="$ADP8/train.log"
mkdir -p "$ADP8"

score_one() {
  local model="$1" adapter="$2" gold="$3" out="$4" extra="${5:-}"
  if [[ -f "$out" ]]; then
    echo "skip existing $out"
    return 0
  fi
  echo "=== scoring $out $(date) ==="
  $PY "$ROOT/benchmarks/score_qwen_eval.py" \
    --model "$model" --adapter "$adapter" \
    --gold "$gold" --out "$out" $extra
  $PY "$ROOT/src/confusion_analysis.py" "$out" --min-risk-accuracy 0.70 || true
}

echo "=== 4B evals (early-stopped best val) $(date) ==="
score_one "$MODEL4" "$ADP4" \
  "$ROOT/data/gold_v2_slm_eval_holdout.csv" \
  "$ROOT/outputs/qwen3_4b_holdout_predictions.csv"
score_one "$MODEL4" "$ADP4" \
  "$ROOT/data/gold_transactions_v4_slm_volume.csv" \
  "$ROOT/outputs/qwen3_4b_v4_residual_predictions.csv" \
  "--residual-t4"
score_one "$MODEL4" "$ADP4" \
  "$ROOT/data/gold_transactions_risk_categories.csv" \
  "$ROOT/outputs/qwen3_4b_risk_predictions.csv"

echo "=== start Qwen3-8B LoRA with early stop $(date) ==="
PYTHONUNBUFFERED=1 "$LORA" \
  --model "$MODEL8" \
  --train \
  --data "$ROOT/outputs/qwen3_data" \
  --fine-tune-type lora \
  --optimizer adam \
  --mask-prompt \
  --num-layers 16 \
  --batch-size 4 \
  --iters 38000 \
  --val-batches 25 \
  --learning-rate 1e-5 \
  --steps-per-report 50 \
  --steps-per-eval 2000 \
  --adapter-path "$ADP8" \
  --save-every 2000 \
  --max-seq-length 2048 \
  --seed 42 \
  --grad-checkpoint \
  > "$LOG8" 2>&1 &
LORA_PID=$!
echo "8B lora pid=$LORA_PID"
$PY "$ROOT/scripts/qwen3_early_stop.py" \
  --log "$LOG8" --pid "$LORA_PID" --adapter-dir "$ADP8" \
  --patience 2 --min-delta 0.005
wait "$LORA_PID" || true

echo "=== 8B evals $(date) ==="
score_one "$MODEL8" "$ADP8" \
  "$ROOT/data/gold_v2_slm_eval_holdout.csv" \
  "$ROOT/outputs/qwen3_8b_holdout_predictions.csv"
score_one "$MODEL8" "$ADP8" \
  "$ROOT/data/gold_transactions_v4_slm_volume.csv" \
  "$ROOT/outputs/qwen3_8b_v4_residual_predictions.csv" \
  "--residual-t4"
score_one "$MODEL8" "$ADP8" \
  "$ROOT/data/gold_transactions_risk_categories.csv" \
  "$ROOT/outputs/qwen3_8b_risk_predictions.csv"

echo "=== bakeoff complete $(date) ==="
echo BAKEOFF_DONE

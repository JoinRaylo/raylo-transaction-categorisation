#!/usr/bin/env bash
# Retrain Qwen3-8B with a liberal early-stop and score the *latest* ckpt
# (last run rolled back to iter 2000 best-val and underfit the holdout).
set -euo pipefail
ROOT="/Users/carlosnoblejesus/Repos/raylo-transaction-categorisation"
cd "$ROOT"
PY="$ROOT/.venv/bin/python"
LORA="$ROOT/.venv/bin/mlx_lm.lora"
MODEL8="mlx-community/Qwen3-8B-4bit"
ADP8="$ROOT/outputs/qwen3_8b_long_adapters"
LOG8="$ADP8/train.log"
mkdir -p "$ADP8"

score_one() {
  local gold="$1" out="$2" extra="${3:-}"
  if [[ -f "$out" ]]; then
    echo "skip existing $out"
    return 0
  fi
  echo "=== scoring $out $(date) ==="
  $PY "$ROOT/benchmarks/score_qwen_eval.py" \
    --model "$MODEL8" --adapter "$ADP8" \
    --gold "$gold" --out "$out" $extra
  $PY "$ROOT/src/confusion_analysis.py" "$out" --min-risk-accuracy 0.70 || true
}

echo "=== Qwen3-8B long LoRA (patience=8, keep latest) $(date) ==="
# caffeinate so overnight train isn't killed by idle sleep
caffeinate -is env PYTHONUNBUFFERED=1 "$LORA" \
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
echo "8B-long lora pid=$LORA_PID"
$PY "$ROOT/scripts/qwen3_early_stop.py" \
  --log "$LOG8" --pid "$LORA_PID" --adapter-dir "$ADP8" \
  --patience 8 --min-delta 0.001 --keep-latest
wait "$LORA_PID" || true

echo "=== 8B-long evals $(date) ==="
score_one \
  "$ROOT/data/gold_v2_slm_eval_holdout.csv" \
  "$ROOT/outputs/qwen3_8b_long_holdout_predictions.csv"
score_one \
  "$ROOT/data/gold_transactions_v4_slm_volume.csv" \
  "$ROOT/outputs/qwen3_8b_long_v4_residual_predictions.csv" \
  "--residual-t4"
score_one \
  "$ROOT/data/gold_transactions_risk_categories.csv" \
  "$ROOT/outputs/qwen3_8b_long_risk_predictions.csv"

echo "=== 8B-long complete $(date) ==="
echo QWEN3_8B_LONG_DONE

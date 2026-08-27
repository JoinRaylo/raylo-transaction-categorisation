#!/usr/bin/env bash
# Wait for the Qwen3-4B LoRA run to finish, score it, then train+score 8B.
# Safe to re-run: scoring is skipped if prediction CSVs already exist.
set -euo pipefail
ROOT="/Users/carlosnoblejesus/Repos/raylo-transaction-categorisation"
cd "$ROOT"
PY="$ROOT/.venv/bin/python"
LORA="$ROOT/.venv/bin/mlx_lm.lora"
LOG4="$ROOT/outputs/qwen3_4b_adapters/train.log"
LOG8="$ROOT/outputs/qwen3_8b_adapters/train.log"
ORCH="$ROOT/outputs/qwen3_bakeoff_orchestrator.log"
MODEL4="mlx-community/Qwen3-4B-Instruct-2507-4bit"
MODEL8="mlx-community/Qwen3-8B-4bit"
ADP4="$ROOT/outputs/qwen3_4b_adapters"
ADP8="$ROOT/outputs/qwen3_8b_adapters"
mkdir -p "$ADP8"

echo "=== orchestrator start $(date) ==="

wait_for_final() {
  local log="$1" label="$2"
  echo "Waiting for $label: 'Saved final weights' in $log"
  while true; do
    if grep -q "Saved final weights" "$log" 2>/dev/null; then
      echo "$label finished at $(date)"
      return 0
    fi
    if grep -q "Traceback (most recent call last)" "$log" 2>/dev/null \
       && ! pgrep -f "mlx_lm.lora" >/dev/null; then
      echo "$label failed; last 30 lines:"
      tail -n 30 "$log"
      return 1
    fi
    sleep 60
  done
}

score_one() {
  local model="$1" adapter="$2" gold="$3" out="$4" extra="${5:-}"
  if [[ -f "$out" ]]; then
    echo "skip existing $out"
    return 0
  fi
  echo "=== scoring $out ==="
  $PY "$ROOT/benchmarks/score_qwen_eval.py" \
    --model "$model" --adapter "$adapter" \
    --gold "$gold" --out "$out" $extra
  $PY "$ROOT/src/confusion_analysis.py" "$out" --min-risk-accuracy 0.70 || true
}

wait_for_final "$LOG4" "Qwen3-4B"

echo "=== 4B evals ==="
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

echo "=== start Qwen3-8B LoRA $(date) ==="
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
  > "$LOG8" 2>&1

wait_for_final "$LOG8" "Qwen3-8B"

echo "=== 8B evals ==="
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

#!/usr/bin/env bash
# Resume Qwen3-8B LoRA from the 22k checkpoint in a new process group so a
# Cursor terminal abort does not SIGKILL the train. Scores the latest ckpt
# when training exits.
set -euo pipefail
ROOT="/Users/carlosnoblejesus/Repos/raylo-transaction-categorisation"
cd "$ROOT"
PY="$ROOT/.venv/bin/python"
LORA="$ROOT/.venv/bin/mlx_lm.lora"
MODEL8="mlx-community/Qwen3-8B-4bit"
RESUME="$ROOT/outputs/qwen3_8b_long_adapters/0022000_adapters.safetensors"
ADP="$ROOT/outputs/qwen3_8b_long_cont_adapters"
LOG="$ADP/train.log"
CAFF_PID_FILE="$ADP/caffeinate.pid"
LORA_PID_FILE="$ADP/lora.pid"
WATCH_PID_FILE="$ADP/watcher.pid"

test -f "$RESUME"
mkdir -p "$ADP"
cp "$ROOT/outputs/qwen3_8b_long_adapters/adapter_config.json" "$ADP/adapter_config.json"

# MLX still pointed at the 24 Aug jsonl; corrections landed in tuning_train.jsonl.
rm -f "$ROOT/outputs/qwen3_data/train.jsonl"
ln "$ROOT/outputs/tuning_train.jsonl" "$ROOT/outputs/qwen3_data/train.jsonl"

if pgrep -f 'mlx_lm.lora .*qwen3_8b_long_cont_adapters' >/dev/null 2>&1; then
  echo "already running" >&2
  exit 1
fi

{
  echo ""
  echo "=== Qwen3-8B continuation from 22k $(date) ==="
  echo "resume=$RESUME"
  echo "train_jsonl=$(ls -l "$ROOT/outputs/qwen3_data/train.jsonl")"
} >> "$LOG"

# Keep the Mac awake independently of the train process group.
nohup caffeinate -is >/dev/null 2>&1 &
echo $! > "$CAFF_PID_FILE"

"$PY" - <<PY
import os
from pathlib import Path

root = Path("$ROOT")
log = Path("$LOG")
pidfile = Path("$LORA_PID_FILE")
argv = [
    "$LORA",
    "--model", "$MODEL8",
    "--train",
    "--data", str(root / "outputs/qwen3_data"),
    "--fine-tune-type", "lora",
    "--optimizer", "adam",
    "--mask-prompt",
    "--num-layers", "16",
    "--batch-size", "4",
    "--iters", "16000",
    "--val-batches", "25",
    "--learning-rate", "1e-5",
    "--steps-per-report", "50",
    "--steps-per-eval", "2000",
    "--resume-adapter-file", "$RESUME",
    "--adapter-path", str(Path("$ADP")),
    "--save-every", "2000",
    "--max-seq-length", "2048",
    "--seed", "42",
    "--grad-checkpoint",
]
if os.fork() > 0:
    raise SystemExit(0)
os.setsid()
if os.fork() > 0:
    os._exit(0)
os.chdir(root)
os.umask(0)
log.parent.mkdir(parents=True, exist_ok=True)
logf = open(log, "a", buffering=1)
os.dup2(logf.fileno(), 1)
os.dup2(logf.fileno(), 2)
pidfile.write_text(str(os.getpid()))
os.execv(argv[0], argv)
PY

# Wait until the daemon has written its pid.
for _ in $(seq 1 50); do
  if [[ -s "$LORA_PID_FILE" ]]; then
    break
  fi
  sleep 0.1
done
LORA_PID="$(cat "$LORA_PID_FILE")"
echo "cont lora pid=$LORA_PID pgid=$(ps -o pgid= -p "$LORA_PID" | tr -d ' ')"

"$PY" - <<PY
import os
from pathlib import Path

root = Path("$ROOT")
log = Path("$ADP/watcher.log")
pidfile = Path("$WATCH_PID_FILE")
argv = [
    "$PY",
    str(root / "scripts/qwen3_early_stop.py"),
    "--log", "$LOG",
    "--pid", "$LORA_PID",
    "--adapter-dir", "$ADP",
    "--patience", "8",
    "--min-delta", "0.001",
    "--keep-latest",
]
if os.fork() > 0:
    raise SystemExit(0)
os.setsid()
if os.fork() > 0:
    os._exit(0)
os.chdir(root)
log.parent.mkdir(parents=True, exist_ok=True)
logf = open(log, "a", buffering=1)
os.dup2(logf.fileno(), 1)
os.dup2(logf.fileno(), 2)
pidfile.write_text(str(os.getpid()))
os.execv(argv[0], argv)
PY

echo "watcher pid=$(cat "$WATCH_PID_FILE")"
echo "detached. log=$LOG"
sleep 2
ps -p "$LORA_PID" -o pid,pgid,etime,%cpu,command=
tail -n 8 "$LOG"

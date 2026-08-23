"""Tracked monitor for the local Gemma 3 4B LoRA run (2026-08-21).
Polls the training log/process; prints a heartbeat periodically and exits
(with a summary) the moment the process ends, so the harness can notify
on completion the way it does for any other tracked background command.
"""
import re
import subprocess
import sys
import time

PID = 66583
LOG = "/Users/carlosnoblejesus/Repos/raylo-transaction-categorisation/outputs/mlx_full_run/run.log"
POLL_SECS = 60
HEARTBEAT_EVERY = 15  # ~15 minutes

ITER_RE = re.compile(r"Iter (\d+): Train loss ([\d.]+).*It/sec ([\d.]+)")

def pid_alive(pid):
    return subprocess.run(["kill", "-0", str(pid)], capture_output=True).returncode == 0

def last_iter_line():
    try:
        with open(LOG) as f:
            lines = f.readlines()
    except FileNotFoundError:
        return None
    for line in reversed(lines):
        m = ITER_RE.search(line)
        if m:
            return f"Iter {m.group(1)}/41112, train loss {m.group(2)}, {m.group(3)} it/sec"
    return None

start = time.monotonic()
poll_count = 0
while True:
    alive = pid_alive(PID)
    elapsed_min = (time.monotonic() - start) / 60
    status = last_iter_line() or "starting up..."

    if not alive:
        print(f"[{elapsed_min:5.1f}m] TRAINING PROCESS ENDED. Last status: {status}", flush=True)
        with open(LOG) as f:
            tail = f.readlines()[-15:]
        print("--- last 15 lines of run.log ---", flush=True)
        print("".join(tail), flush=True)
        sys.exit(0)

    if poll_count % HEARTBEAT_EVERY == 0:
        print(f"[{elapsed_min:5.1f}m] heartbeat: still running. {status}", flush=True)

    poll_count += 1
    time.sleep(POLL_SECS)

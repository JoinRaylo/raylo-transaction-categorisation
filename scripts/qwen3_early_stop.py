"""Watch an mlx_lm.lora train.log and SIGTERM when val loss stalls.

Patience counts consecutive evals (after iter 1, the pre-train probe) that
fail to beat the best val by --min-delta. On stop, copy the best numbered
checkpoint over adapters.safetensors so scoring uses the early-stopped weights.

Usage:
    .venv/bin/python scripts/qwen3_early_stop.py \\
        --log outputs/qwen3_8b_adapters/train.log \\
        --pid 12345 \\
        --adapter-dir outputs/qwen3_8b_adapters \\
        --patience 2 --min-delta 0.005
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import signal
import sys
import time
from pathlib import Path

VAL_RE = re.compile(r"Iter (\d+): Val loss ([0-9.]+)")


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def restore_best(adapter_dir: Path, best_iter: int) -> None:
    src = adapter_dir / f"{best_iter:07d}_adapters.safetensors"
    dst = adapter_dir / "adapters.safetensors"
    if not src.exists():
        print(f"best checkpoint missing: {src}", file=sys.stderr)
        return
    shutil.copy2(src, dst)
    print(f"restored best iter {best_iter} -> {dst}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--log", required=True, type=Path)
    p.add_argument("--pid", required=True, type=int)
    p.add_argument("--adapter-dir", required=True, type=Path)
    p.add_argument("--patience", type=int, default=2)
    p.add_argument("--min-delta", type=float, default=0.005)
    p.add_argument("--poll", type=int, default=30)
    p.add_argument(
        "--keep-latest",
        action="store_true",
        help="On stop, leave adapters.safetensors as the last saved ckpt "
        "(do not roll back to lowest val NLL — that underfit holdout last time).",
    )
    args = p.parse_args()

    seen: dict[int, float] = {}
    best: tuple[int, float] | None = None
    stale = 0
    print(
        f"watching pid={args.pid} log={args.log} "
        f"patience={args.patience} min_delta={args.min_delta} "
        f"keep_latest={args.keep_latest}"
    )

    while True:
        if not pid_alive(args.pid):
            print("train pid exited")
            if best is not None and not args.keep_latest:
                restore_best(args.adapter_dir, best[0])
            return

        if args.log.exists():
            text = args.log.read_text(errors="replace")
            for m in VAL_RE.finditer(text):
                it, loss = int(m.group(1)), float(m.group(2))
                if it in seen:
                    continue
                seen[it] = loss
                if it <= 1:
                    print(f"warmup iter {it} val={loss:.4f} (ignored)")
                    continue
                if best is None or loss < best[1] - args.min_delta:
                    best = (it, loss)
                    stale = 0
                    print(f"new best iter={it} val={loss:.4f}")
                else:
                    stale += 1
                    print(
                        f"no improve iter={it} val={loss:.4f} "
                        f"stale={stale}/{args.patience} best={best[0]}@{best[1]:.4f}"
                    )
                    if stale >= args.patience:
                        print(
                            f"EARLY STOP pid={args.pid} "
                            f"best_iter={best[0]} best_val={best[1]:.4f}"
                        )
                        os.kill(args.pid, signal.SIGTERM)
                        for _ in range(20):
                            if not pid_alive(args.pid):
                                break
                            time.sleep(1)
                        if pid_alive(args.pid):
                            os.kill(args.pid, signal.SIGKILL)
                        if not args.keep_latest:
                            restore_best(args.adapter_dir, best[0])
                        note = args.adapter_dir / "early_stop.txt"
                        note.write_text(
                            f"early_stop=1\nbest_iter={best[0]}\n"
                            f"best_val={best[1]}\npatience={args.patience}\n"
                            f"keep_latest={int(args.keep_latest)}\n"
                            f"stopped_at_eval_iter={it}\nstopped_val={loss}\n"
                        )
                        return
        time.sleep(args.poll)


if __name__ == "__main__":
    main()

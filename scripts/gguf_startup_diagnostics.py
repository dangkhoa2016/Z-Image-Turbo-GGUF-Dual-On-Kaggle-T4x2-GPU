#!/usr/bin/env python3
"""CPU-only, read-only GGUF startup instrumentation for the Kaggle notebook.

Modes:
  inspect PID       Linux procfs read-only sampler
  io-probe FILE     Bounded warm-cache-inclusive read probe (not a disk benchmark)
  run SCRIPT ARGS   Execute the unchanged worker with an opt-in SIGUSR1 stack dump.

Does not load a GGUF model, allocate CUDA, alter model checkpoints, or install packages.
"""
from __future__ import annotations

import argparse
import faulthandler
import json
import os
from pathlib import Path
import runpy
import signal
import sys
import time


def read_process(pid: int) -> dict:
    """Read Linux process CPU, RSS, page faults and I/O accounting.

    /proc/<pid>/stat has a parenthesized process-name field that may contain
    spaces or closing parens. Parse after the final ')' as documented by procfs.
    """
    if not isinstance(pid, int) or pid <= 0:
        raise ValueError("pid must be a positive integer")
    root = Path("/proc") / str(pid)
    raw = (root / "stat").read_text()
    assert raw.startswith(str(pid) + " ("), "unrecognized procfs stat"
    right = raw.rsplit(")", 1)[1].strip().split()
    # right[0] is stat field 3 (state). See proc(5).
    state = right[0]
    minflt = int(right[7])          # field 10
    majflt = int(right[9])          # field 12
    utime = int(right[11])          # field 14
    stime = int(right[12])          # field 15
    threads = int(right[17])        # field 20
    start_ticks = int(right[19])    # field 22: PID-reuse identifier
    rss_pages = int(right[21])      # field 24

    io = {}
    try:
        for line in (root / "io").read_text().splitlines():
            key, _, value = line.partition(":")
            if key in ("rchar", "wchar", "read_bytes", "write_bytes", "syscr", "syscw"):
                io[key] = int(value.strip())
    except (OSError, ValueError):
        pass  # Some containers restrict /proc/<pid>/io.
    status = {}
    try:
        for line in (root / "status").read_text().splitlines():
            key, _, value = line.partition(":")
            if key in ("VmRSS", "VmHWM", "VmSize", "RssAnon", "RssFile", "VmSwap"):
                status[key.lower() + "_kib"] = int(value.strip().split()[0])
    except (OSError, ValueError, IndexError):
        pass
    return {
        "pid": pid,
        "process_state": state,
        "process_start_ticks": start_ticks,
        "cpu_user_ticks": utime,
        "cpu_system_ticks": stime,
        "cpu_ticks_per_second": os.sysconf("SC_CLK_TCK"),
        "minor_faults": minflt,
        "major_faults": majflt,
        "threads": threads,
        "rss_bytes": rss_pages * os.sysconf("SC_PAGE_SIZE"),
        **status,
        **io,
    }


def io_probe(path: Path, max_mib: int = 32) -> dict:
    """Bounded sequential read; cached reads are possible and explicitly noted."""
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("GGUF file missing or symlink; probe blocked")
    if max_mib < 1 or max_mib > 64:
        raise ValueError("max_mib must be 1..64")
    expected = min(path.stat().st_size, max_mib * 1024 * 1024)
    read = 0
    started = time.monotonic()
    with path.open("rb") as stream:
        while read < expected:
            part = stream.read(min(1 << 20, expected - read))
            if not part:
                break
            read += len(part)
    seconds = max(time.monotonic() - started, 1e-6)
    return {
        "path": str(path),
        "size_bytes": path.stat().st_size,
        "sample_bytes": read,
        "seconds": round(seconds, 4),
        "sample_mib_per_second": round(read / 1048576 / seconds, 2),
        "interpretation": "read-only bounded sample; OS page cache may affect measurement",
    }


def run_instrumented(worker_path: Path, argv: list[str]) -> None:
    """Keep the original worker module as __main__, only register a diagnostic signal."""
    worker_path = Path(worker_path)
    if worker_path.is_symlink():
        raise ValueError("Worker script must not be a symlink")
    worker_path = worker_path.resolve(strict=True)
    if worker_path.name != "dynamic_worker.py":
        # Testing with a synthetic worker is intentionally supported separately.
        if os.environ.get("ZIMAGE_PROFILE_TEST_WORKER") != "1":
            raise ValueError("Refusing to wrap an unexpected worker")
    faulthandler.enable(file=sys.stderr, all_threads=True)
    if not hasattr(signal, "SIGUSR1"):
        raise RuntimeError("Linux SIGUSR1 support is required for stack profiling")
    faulthandler.register(signal.SIGUSR1, file=sys.stderr, all_threads=True, chain=False)
    print(
        "ZIMAGE_GGUF_STACK_PROBE_READY " + json.dumps({
            "worker_path": str(worker_path),
            "pid": os.getpid(),
            "signal": "SIGUSR1",
            "mode": "read_only",
        }, sort_keys=True), flush=True,
    )
    sys.argv = [str(worker_path), *argv]
    sys.path.insert(0, str(worker_path.parent))
    runpy.run_path(str(worker_path), run_name="__main__")


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    p = sub.add_parser("inspect")
    p.add_argument("pid", type=int)
    q = sub.add_parser("io-probe")
    q.add_argument("path", type=Path)
    q.add_argument("--mib", type=int, default=32)
    r = sub.add_parser("run")
    r.add_argument("script", type=Path)
    r.add_argument("worker_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.action == "run":
        run_instrumented(args.script, args.worker_args)
        return 0
    result = read_process(args.pid) if args.action == "inspect" else io_probe(args.path, args.mib)
    print(json.dumps(result, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

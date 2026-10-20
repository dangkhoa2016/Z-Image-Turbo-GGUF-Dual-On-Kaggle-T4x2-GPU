#!/usr/bin/env python3
"""Deterministic, process-isolated CPU test runner.

The project's ``production-system/test_*.py`` files are self-contained scripts
that execute assertions at import time and mutate process-global state (env
vars, SQLite paths, module cache). Running them all in one interpreter (e.g.
``unittest discover``) causes cross-test contamination and false failures.

This runner executes each test file in its own subprocess, classifies it, and
reports a stable PASS/FAIL/SKIP summary with a non-zero exit code on failure.
It never edits test assertions and never silently skips a failing test.
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = ROOT / "production-system"

# Classification by test filename prefix. GPU tests require a real T4x2 and are
# skipped (not failed) on CPU-only hosts.
GPU_MARKERS = ("gpu", "cuda", "t4")


def classify(name):
    stem = name[:-3] if name.endswith(".py") else name
    lowered = stem.lower()
    if any(marker in lowered for marker in GPU_MARKERS):
        return "gpu"
    if "integration" in lowered or "unified" in lowered or "http" in lowered:
        return "integration"
    return "unit"


def discover(pattern):
    return sorted(p for p in TESTS_DIR.glob(pattern) if p.is_file())


def run_one(path, timeout, gpu_available):
    group = classify(path.name)
    if group == "gpu" and not gpu_available:
        return group, "SKIP", "GPU not available on this host", ""
    try:
        proc = subprocess.run(
            [sys.executable, path.name], cwd=str(TESTS_DIR),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return group, "FAIL", "TIMEOUT after %ss" % timeout, ""
    status = "PASS" if proc.returncode == 0 else "FAIL"
    return group, status, "exit=%d" % proc.returncode, proc.stdout


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pattern", default="test_*.py")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--log-dir", default="")
    args = parser.parse_args(argv)

    probe = subprocess.run([sys.executable, "-c",
                            "import torch,sys;sys.exit(0 if torch.cuda.is_available() else 1)"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    gpu_available = probe.returncode == 0

    log_dir = Path(args.log_dir) if args.log_dir else None
    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)

    counts = {"unit": {}, "integration": {}, "gpu": {}}
    failures = []
    print("CPU_TEST_RUNNER dir=%s gpu_available=%s" % (TESTS_DIR, gpu_available))
    for path in discover(args.pattern):
        group, status, detail, out = run_one(path, args.timeout, gpu_available)
        counts[group][status] = counts[group].get(status, 0) + 1
        print("%-4s %-11s %-28s %s" % (status, group, path.name, detail))
        if out.strip():
            last = out.strip().splitlines()[-1]
            print("        %s" % last)
        if log_dir:
            (log_dir / (path.name + ".log")).write_text(out)
        if status == "FAIL":
            failures.append(path.name)

    total = sum(sum(v.values()) for v in counts.values())
    passed = sum(v.get("PASS", 0) for v in counts.values())
    skipped = sum(v.get("SKIP", 0) for v in counts.values())
    print("SUMMARY total=%d passed=%d skipped=%d failed=%d" % (total, passed, skipped, len(failures)))
    for group in ("unit", "integration", "gpu"):
        if counts[group]:
            print("  %-11s %s" % (group, counts[group]))
    if failures:
        print("FAILED_TESTS %s" % ",".join(failures))
        return 1
    print("CPU_TESTS=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

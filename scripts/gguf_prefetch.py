#!/usr/bin/env python3
"""CPU-only, bounded, fail-closed prefetch of the original GGUF staging policy.

This optimization overlaps network/storage reads with the independent encoder
phase. It does NOT replace the worker's full checkpoint verification, nor
does it alter inference/model code. Launched from a Kaggle notebook subprocess.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import tempfile
import time

from gguf_source_policy import select_gguf_source

MAX_PREFETCH_SECONDS = 420
_ALLOWED_ROOT = Path("/kaggle/working")


def prefetch(manifest_path: Path, destination: Path, report: Path) -> dict:
    manifest_path=Path(manifest_path)
    destination=Path(destination)
    report=Path(report)
    if not manifest_path.is_absolute() or manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError("P24_MANIFEST_INVALID")
    if not destination.is_absolute() or ".." in destination.parts or destination.is_symlink():
        raise ValueError("P24_STAGE_ROOT_UNSAFE")
    if not destination.resolve(strict=False).is_relative_to(_ALLOWED_ROOT):
        raise ValueError("P24_STAGE_ROOT_OUTSIDE_KAGGLE_WORKING")
    if not report.is_absolute() or report.is_symlink() or not report.parent.is_dir():
        raise ValueError("P24_REPORT_PATH_UNSAFE")
    if not report.parent.resolve().is_relative_to(_ALLOWED_ROOT):
        raise ValueError("P24_REPORT_OUTSIDE_KAGGLE_WORKING")
    if report.exists():
        raise RuntimeError("P24_REPORT_ALREADY_EXISTS")
    manifest=json.loads(manifest_path.read_text(encoding="utf8"))
    started=time.monotonic()
    # Reuse the project's existing atomic, SHA256-streaming stage_model().
    # It accepts no hash override; prior checkpoints are independently rehashed.
    choice=select_gguf_source(manifest,destination,mode="local")
    if choice["effective_mode"]!="local" or choice["integrity"]!="sha256_verified_local":
        raise RuntimeError("P24_PREFETCH_SOURCE_NOT_VERIFIED")
    summary={
        "schema":"ZIMAGE_P24_GGUF_PREFETCH_V1",
        "status":"VERIFIED_LOCAL_GGUF_READY",
        "requested_mode":"local",
        "source_model_bytes":choice["bytes_expected"],
        "source_sha256":choice["sha256_expected"],
        "staged_path":choice["staged_override_path"],
        "selection_seconds":choice["source_selection_seconds"],
        "total_elapsed_seconds":round(time.monotonic()-started,3),
        "finished_utc":datetime.now(timezone.utc).isoformat(),
        "identity_guard":"sha256_stream_copy_or_full_rehash",
        "worker_must_reverify":True,
    }
    # Atomic metadata publication. File contents contain no credentials.
    handle=None
    try:
        handle=tempfile.NamedTemporaryFile(
            mode="w",prefix=".p24-",suffix=".json.tmp",dir=report.parent,delete=False)
        json.dump(summary,handle,sort_keys=True,indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
        handle.close()
        if report.exists() or report.is_symlink():
            raise RuntimeError("P24_REPORT_RACE")
        os.link(handle.name, report,follow_symlinks=False)
        fd=os.open(report.parent,os.O_RDONLY|getattr(os,"O_DIRECTORY",0))
        try:os.fsync(fd)
        finally:os.close(fd)
    finally:
        if handle is not None:
            if not handle.closed:handle.close()
            if os.path.exists(handle.name):os.unlink(handle.name)
    print("P24_PREFETCH_VERIFIED",json.dumps(summary,sort_keys=True),flush=True)
    return summary


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--manifest",type=Path,required=True)
    ap.add_argument("--destination",type=Path,required=True)
    ap.add_argument("--report",type=Path,required=True)
    args=ap.parse_args()
    def timed_out(_signum,_frame):raise TimeoutError("P24_PREFETCH_TIMEOUT_420S")
    def terminated(_signum,_frame):raise RuntimeError("P24_PREFETCH_TERMINATED")
    signal.signal(signal.SIGALRM,timed_out)
    signal.signal(signal.SIGTERM,terminated)
    signal.alarm(MAX_PREFETCH_SECONDS)
    # Reduce competition with the encoder, best effort only.
    try: os.nice(10)
    except OSError:pass
    prefetch(args.manifest,args.destination,args.report)
    signal.alarm(0)
    return 0

if __name__=="__main__":
    raise SystemExit(main())

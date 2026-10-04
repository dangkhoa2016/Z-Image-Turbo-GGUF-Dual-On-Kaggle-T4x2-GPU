#!/usr/bin/env python3
"""Safely stage a SHA256-verified GGUF once to local Kaggle storage.

No CUDA, model parsing, numpy or third-party dependencies. Fail closed on
insufficient space, hashes, pre-existing corrupt cache, or unsafe paths.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import time
import uuid

RESERVE_BYTES = 1024 * 1024 * 1024
CHUNK_BYTES = 8 * 1024 * 1024
REPORT_EVERY_BYTES = 256 * 1024 * 1024


def _expected(manifest: dict) -> tuple[Path, int, str]:
    source = Path(manifest["gguf_path"])
    size = manifest["gguf_bytes"]
    digest = manifest["gguf_sha256"]
    if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
        raise ValueError("STAGE_INVALID_EXPECTED_SIZE")
    if not isinstance(digest, str) or not re.fullmatch("[0-9a-f]{64}", digest):
        raise ValueError("STAGE_INVALID_EXPECTED_SHA256")
    if not source.is_absolute() or source.is_symlink() or not source.is_file():
        raise ValueError("STAGE_INVALID_SOURCE_FILE")
    if source.stat().st_size != size:
        raise ValueError("STAGE_SOURCE_SIZE_MISMATCH")
    return source, size, digest


def _stage_root(path: Path) -> Path:
    path = Path(path)
    if not path.is_absolute() or path.is_symlink():
        raise ValueError("STAGE_INVALID_DESTINATION")
    if path.exists() and not path.is_dir():
        raise ValueError("STAGE_DESTINATION_NOT_DIRECTORY")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError("STAGE_DESTINATION_SYMLINK")
    return path


def staged_path(manifest: dict, destination: Path) -> Path:
    digest = manifest["gguf_sha256"]
    if not isinstance(digest, str) or not re.fullmatch("[0-9a-f]{64}", digest):
        raise ValueError("STAGE_INVALID_EXPECTED_SHA256")
    return Path(destination) / (digest + ".gguf")


def verify_file(path: Path, expected_size: int, expected_sha256: str) -> None:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("STAGE_VERIFICATION_FILE_INVALID")
    if path.stat().st_size != expected_size:
        raise RuntimeError("STAGE_VERIFICATION_SIZE_MISMATCH")
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(CHUNK_BYTES), b""):
            h.update(block)
    if h.hexdigest() != expected_sha256:
        raise RuntimeError("STAGE_VERIFICATION_SHA256_MISMATCH")


def stage_model(manifest: dict, destination: Path, reserve_bytes: int = RESERVE_BYTES) -> Path:
    """Streaming copy+hash, atomic publish, and serialized cache integrity checks."""
    source, size, digest = _expected(manifest)
    if not isinstance(reserve_bytes, int) or reserve_bytes < 0:
        raise ValueError("STAGE_INVALID_RESERVE")
    root = _stage_root(destination)
    target = staged_path(manifest, root)
    lock = root / ".staging.lock"
    if lock.is_symlink():
        raise RuntimeError("STAGE_LOCK_SYMLINK")
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(lock, flags, 0o600)
    with os.fdopen(fd, "r+b", buffering=0):
        fcntl.flock(fd, fcntl.LOCK_EX)
        if target.exists() or target.is_symlink():
            # Corrupt cached data cannot be overwritten automatically.
            verify_file(target, size, digest)
            print("GGUF_STAGE_REUSED_VERIFIED", str(target), flush=True)
            return target
        free = shutil.disk_usage(root).free
        required = size + reserve_bytes
        if free < required:
            raise RuntimeError(
                f"STAGE_INSUFFICIENT_DISK_SPACE free_bytes={free} required_bytes={required}"
            )
        temp = root / ("." + digest + "." + str(os.getpid()) + "." + uuid.uuid4().hex + ".partial")
        copy_flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        if hasattr(os, "O_NOFOLLOW"):
            copy_flags |= os.O_NOFOLLOW
        h = hashlib.sha256()
        n = 0
        since_report = 0
        started = time.monotonic()
        try:
            tfd = os.open(temp, copy_flags, 0o600)
            with os.fdopen(tfd, "wb") as out, source.open("rb") as inp:
                while True:
                    block = inp.read(CHUNK_BYTES)
                    if not block:
                        break
                    out.write(block)
                    h.update(block)
                    n += len(block)
                    if n - since_report >= REPORT_EVERY_BYTES:
                        print("GGUF_STAGE_PROGRESS", f"{n}/{size}", f"elapsed={time.monotonic()-started:.1f}s", flush=True)
                        since_report = n
                out.flush()
                os.fsync(out.fileno())
            if n != size:
                raise RuntimeError(f"STAGE_COPY_SIZE_MISMATCH read={n} expected={size}")
            if h.hexdigest() != digest:
                raise RuntimeError(
                    f"STAGE_COPY_SHA256_MISMATCH actual={h.hexdigest()} expected={digest}"
                )
            # Exclusive atomic link prevents clobbering a cache created elsewhere.
            os.link(temp, target, follow_symlinks=False)
            dir_fd = os.open(root, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
            print("GGUF_STAGE_CREATED_VERIFIED", str(target),
                  f"bytes={size}", f"elapsed={time.monotonic()-started:.1f}s", flush=True)
            return target
        finally:
            if temp.exists():
                temp.unlink()


def verify_staged_override(manifest: dict, path: Path, destination: Path) -> Path:
    """Independent worker-side trust boundary; do not trust an environment string."""
    source, size, digest = _expected(manifest)
    del source
    root = Path(destination)
    if root.is_symlink() or not root.is_dir():
        raise RuntimeError("STAGE_OVERRIDE_ROOT_INVALID")
    target = staged_path(manifest, root)
    if str(path) != str(target):
        raise RuntimeError("STAGE_OVERRIDE_PATH_MISMATCH")
    verify_file(target, size, digest)
    return target


if __name__ == "__main__":
    raise SystemExit("Import stage_model() from the maintained Kaggle notebook; this is not a GPU loader.")

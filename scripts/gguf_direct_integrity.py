#!/usr/bin/env python3
"""Fail-closed full-file SHA256 verification of direct mounted GGUF before workers.

Verification is a separate, timed read, included in measured model-startup wall.
A successful read identifies the input bytes at verification time; it does not
promise the page cache is cold or that a mutable file could never change later.
"""
from __future__ import annotations
import time
from pathlib import Path
from stage_gguf_model import _expected, verify_file

SCHEMA = "ZIMAGE_P28_DIRECT_INTEGRITY_V1"

def verify_direct_source(manifest: dict) -> dict:
    source, size, digest = _expected(manifest)
    before = source.stat()
    started = time.monotonic()
    verify_file(source, size, digest)
    elapsed = round(time.monotonic() - started, 3)
    after = source.stat()
    # Detect replacement/metadata changes while hashing (read-only Kaggle mount expected).
    def identity(s):
        return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    if identity(before) != identity(after):
        raise RuntimeError("P28_DIRECT_SOURCE_CHANGED_DURING_VERIFICATION")
    return {
        "schema": SCHEMA,
        "status": "FULL_SHA256_VERIFIED_BEFORE_WORKERS",
        "path": str(source),
        "bytes_verified": size,
        "sha256_verified": digest,
        "verification_seconds": elapsed,
        "source_identity_checked": True,
        "read_only_source_expected": True,
        "note": "Identity verified at startup, not a cold-cache measurement.",
    }

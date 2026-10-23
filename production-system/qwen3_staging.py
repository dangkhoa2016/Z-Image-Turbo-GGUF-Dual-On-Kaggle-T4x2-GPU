#!/usr/bin/env python3
"""Opt-in, fail-closed Qwen3 checkpoint staging for Kaggle (stdlib only).

direct (default): preserve original code path; no file copies or scans.
auto: only reuse an existing verified local cache, else use original input.
local: create or reuse a verified local cache, never overwrite corruption.

Model identity comes exclusively from the SHA256-authenticated Kaggle support
manifest; tensor formats and precision are unchanged. No CUDA or ML imports.
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

CHUNK_BYTES = 8 * 1024 * 1024
RESERVE_BYTES = 2 * 1024**3
LOCK_TIMEOUT_SECONDS = 600
FILES = frozenset((
    "config.json", "generation_config.json", "model.safetensors.index.json",
    "model-00001-of-00003.safetensors",
    "model-00002-of-00003.safetensors",
    "model-00003-of-00003.safetensors",
))
MODES = ("direct", "auto", "local")


def _hex(text: object) -> str:
    if not isinstance(text, str) or not re.fullmatch(r"[0-9a-f]{64}", text):
        raise ValueError("QWEN3_MANIFEST_SHA256_INVALID")
    return text


def _safe_path(path: Path, *, destination: bool = False) -> Path:
    """Reject traversal, symlinks in existing ancestors, and relative paths."""
    p = Path(path)
    if not p.is_absolute() or ".." in p.parts or os.path.normpath(str(p)) != str(p):
        raise ValueError("QWEN3_PATH_UNSAFE")
    for ancestor in (p, *p.parents):
        if ancestor.is_symlink():
            raise RuntimeError("QWEN3_PATH_SYMLINK")
    if destination and p.exists() and not p.is_dir():
        raise RuntimeError("QWEN3_DESTINATION_NOT_DIRECTORY")
    return p


def _support_paths(support: dict) -> tuple[Path, Path, str]:
    if not isinstance(support, dict):
        raise ValueError("QWEN3_SUPPORT_INVALID")
    source = _safe_path(Path(support["support_root"]) / "text_encoder")
    manifest = _safe_path(Path(support["manifest_path"]))
    digest = _hex(support["manifest_sha256"])
    if not source.is_dir() or not manifest.is_file():
        raise RuntimeError("QWEN3_SUPPORT_NOT_ATTACHED")
    return source, manifest, digest


def _manifest_entries(support: dict) -> tuple[Path, str, dict]:
    source, manifest, expected = _support_paths(support)
    content = manifest.read_bytes()
    if hashlib.sha256(content).hexdigest() != expected:
        raise RuntimeError("QWEN3_SUPPORT_MANIFEST_SHA256_MISMATCH")
    payload = json.loads(content)
    if not isinstance(payload, list):
        raise ValueError("QWEN3_SUPPORT_MANIFEST_SCHEMA_INVALID")
    entries = {}
    for item in payload:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise ValueError("QWEN3_SUPPORT_MANIFEST_ENTRY_INVALID")
        relative = item["path"]
        if not relative.startswith("text_encoder/"):
            continue
        name = relative[len("text_encoder/"):]
        if name not in FILES or name in entries:
            raise ValueError("QWEN3_SUPPORT_MANIFEST_FILES_INVALID")
        n = item.get("bytes")
        if isinstance(n, bool) or not isinstance(n, int) or n < 0:
            raise ValueError("QWEN3_SUPPORT_MANIFEST_SIZE_INVALID")
        entries[name] = (n, _hex(item.get("sha256")))
    if frozenset(entries) != FILES:
        raise ValueError("QWEN3_SUPPORT_MANIFEST_FILES_MISSING")
    return source, expected, entries


def _hash_file(p: Path, expected_bytes: int, expected_hash: str) -> None:
    if p.is_symlink() or not p.is_file() or p.stat().st_size != expected_bytes:
        raise RuntimeError("QWEN3_LOCAL_VERIFY_SIZE_OR_TYPE_MISMATCH: " + p.name)
    h = hashlib.sha256()
    with p.open("rb") as inp:
        for piece in iter(lambda: inp.read(CHUNK_BYTES), b""):
            h.update(piece)
    if h.hexdigest() != expected_hash:
        raise RuntimeError("QWEN3_LOCAL_VERIFY_SHA256_MISMATCH: " + p.name)


def _verify_target(target: Path, entries: dict) -> Path:
    folder = target / "text_encoder"
    if target.is_symlink() or not target.is_dir() or folder.is_symlink() or not folder.is_dir():
        raise RuntimeError("QWEN3_LOCAL_CACHE_INVALID")
    if {p.name for p in folder.iterdir()} != FILES:
        raise RuntimeError("QWEN3_LOCAL_CACHE_FILE_SET_MISMATCH")
    for name, (size, digest) in entries.items():
        _hash_file(folder / name, size, digest)
    return folder


def _root(path: Path, source: Path, *, create: bool) -> Path:
    root = _safe_path(Path(path), destination=True)
    source_real = source.resolve()
    root_real = root.resolve(strict=False)
    # Never copy into the mounted source or use a parent of the source.
    if root_real == source_real or root_real in source_real.parents or source_real in root_real.parents:
        raise RuntimeError("QWEN3_DESTINATION_OVERLAPS_SOURCE")
    if create:
        root.mkdir(parents=True, mode=0o700, exist_ok=True)
        _safe_path(root, destination=True)
    return root


def _lock_root(root: Path, timeout_seconds: float):
    lock = root / ".qwen3-stage.lock"
    if lock.is_symlink():
        raise RuntimeError("QWEN3_STAGE_LOCK_SYMLINK")
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(lock, flags, 0o600)
    if not stat.S_ISREG(os.fstat(fd).st_mode):
        os.close(fd)
        raise RuntimeError("QWEN3_STAGE_LOCK_NOT_REGULAR")
    started = time.monotonic()
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return fd
        except BlockingIOError:
            if time.monotonic() - started >= timeout_seconds:
                os.close(fd)
                raise RuntimeError("QWEN3_STAGE_LOCK_TIMEOUT")
            time.sleep(0.1)


def _copy_stream_verified(source: Path, dest: Path, expected_size: int, expected_hash: str) -> None:
    if source.is_symlink() or not source.is_file() or source.stat().st_size != expected_size:
        raise RuntimeError("QWEN3_STAGE_SOURCE_SIZE_OR_TYPE_MISMATCH: " + source.name)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(dest, flags, 0o600)
    h = hashlib.sha256()
    count = 0
    try:
        with os.fdopen(fd, "wb") as out, source.open("rb") as inp:
            while piece := inp.read(CHUNK_BYTES):
                count += len(piece)
                if count > expected_size:
                    raise RuntimeError("QWEN3_STAGE_SOURCE_GREW")
                out.write(piece)
                h.update(piece)
            out.flush()
            os.fsync(out.fileno())
        if count != expected_size or h.hexdigest() != expected_hash:
            raise RuntimeError("QWEN3_STAGE_SOURCE_SHA256_OR_SIZE_MISMATCH: " + source.name)
        # Independent on-disk readback before atomic publication.
        _hash_file(dest, expected_size, expected_hash)
    except BaseException:
        # Caller cleans the whole unpublished temporary directory.
        raise


def select_qwen3_source(
    support: dict,
    local_root: Path,
    mode: str = "direct",
    *,
    reserve_bytes: int = RESERVE_BYTES,
    lock_timeout_seconds: float = LOCK_TIMEOUT_SECONDS,
) -> dict:
    if mode not in MODES or not isinstance(mode, str):
        raise ValueError("QWEN3_STAGE_MODE_INVALID")
    if isinstance(reserve_bytes, bool) or not isinstance(reserve_bytes, int) or reserve_bytes < 0:
        raise ValueError("QWEN3_STAGE_RESERVE_INVALID")
    if not isinstance(lock_timeout_seconds, (int, float)) or lock_timeout_seconds < 0:
        raise ValueError("QWEN3_STAGE_LOCK_TIMEOUT_INVALID")

    started = time.monotonic()
    if mode == "direct":
        # Fast default: no large hash scans, disk writes, or new source dependencies.
        source = _safe_path(Path(support["support_root"]) / "text_encoder")
        if not source.is_dir():
            raise RuntimeError("QWEN3_SUPPORT_NOT_ATTACHED")
        return dict(requested_mode=mode, effective_mode="direct",
                    text_encoder_dir=str(source), copied=False,
                    selection_seconds=round(time.monotonic() - started, 3),
                    integrity="read_only_input_original")

    source, identity, entries = _manifest_entries(support)
    root = _root(Path(local_root), source, create=(mode == "local"))
    target = root / identity
    if mode == "auto" and not target.exists() and not target.is_symlink():
        return dict(requested_mode=mode, effective_mode="direct",
                    text_encoder_dir=str(source), copied=False,
                    selection_seconds=round(time.monotonic() - started, 3),
                    integrity="read_only_input_fallback", support_manifest_sha256=identity)

    if mode == "auto" and not root.is_dir():
        raise RuntimeError("QWEN3_STAGE_ROOT_UNAVAILABLE")
    if mode == "local":
        root = _root(root, source, create=True)

    fd = _lock_root(root, lock_timeout_seconds)
    try:
        if target.exists() or target.is_symlink():
            folder = _verify_target(target, entries)
            copied = False
            print("QWEN3_STAGE_REUSED_VERIFIED", str(folder), flush=True)
        else:
            if mode == "auto":
                # Only local mode may create the cache.
                return dict(requested_mode=mode, effective_mode="direct",
                            text_encoder_dir=str(source), copied=False,
                            selection_seconds=round(time.monotonic() - started, 3),
                            integrity="read_only_input_fallback", support_manifest_sha256=identity)
            total = sum(item[0] for item in entries.values())
            free = shutil.disk_usage(root).free
            if free < total + reserve_bytes:
                raise RuntimeError(f"QWEN3_STAGE_INSUFFICIENT_DISK free={free} required={total + reserve_bytes}")
            temp = root / ("." + identity + "." + str(os.getpid()) + "." + uuid.uuid4().hex + ".partial")
            temp.mkdir(mode=0o700)
            try:
                sub = temp / "text_encoder"
                sub.mkdir(mode=0o700)
                for name, (size, digest) in sorted(entries.items()):
                    _copy_stream_verified(source / name, sub / name, size, digest)
                    print("QWEN3_STAGE_VERIFIED", name, size, flush=True)
                dir_fd = os.open(sub, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
                try:os.fsync(dir_fd)
                finally:os.close(dir_fd)
                dir_fd = os.open(temp, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
                try:os.fsync(dir_fd)
                finally:os.close(dir_fd)
                if target.exists() or target.is_symlink():
                    raise RuntimeError("QWEN3_STAGE_DESTINATION_BECAME_OCCUPIED")
                temp.rename(target)
                dir_fd = os.open(root, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
                try:os.fsync(dir_fd)
                finally:os.close(dir_fd)
                folder = target / "text_encoder"
                copied = True
                print("QWEN3_STAGE_CREATED_VERIFIED", str(folder), total, flush=True)
            finally:
                # Delete only our private unpublished scratch dir.
                if temp.exists():
                    shutil.rmtree(temp)
        return dict(requested_mode=mode, effective_mode="local",
                    text_encoder_dir=str(folder), copied=copied,
                    selection_seconds=round(time.monotonic() - started, 3),
                    support_manifest_sha256=identity,
                    verified_bytes=sum(x[0] for x in entries.values()),
                    integrity="support_manifest_sha256_verified_files")
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)

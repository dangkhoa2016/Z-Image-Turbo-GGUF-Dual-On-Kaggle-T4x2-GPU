#!/usr/bin/env python3
"""Read-only Qwen3 disk budget hint for consecutive P2.8 Kaggle trials.

This is NOT a cache-integrity verdict: the existing encoder-side staging
re-verifies full support-manifest SHA256 and every file, failing closed.
"""
from __future__ import annotations
from pathlib import Path
import re

def qwen3_stage_budget_hint(stage_root: Path, manifest_sha256: str,
                            source_dir: Path, names: tuple[str, ...]) -> dict:
    if not isinstance(manifest_sha256,str) or not re.fullmatch(r"[0-9a-f]{64}",manifest_sha256):
        raise ValueError("P28_SUPPORT_ID_INVALID")
    source_dir=Path(source_dir)
    if not names or len(set(names))!=len(names):
        raise ValueError("P28_QWEN3_FILES_INVALID")
    sizes={}
    for name in names:
        if not isinstance(name,str) or not re.fullmatch(r"[A-Za-z0-9_.-]+",name) or name in (".",".."):
            raise ValueError("P28_QWEN3_NAME_INVALID")
        p=source_dir/name
        if p.is_symlink() or not p.is_file():
            raise RuntimeError("P28_QWEN3_INPUT_INVALID")
        sizes[name]=p.stat().st_size
    root=Path(stage_root)
    cached=root/manifest_sha256/"text_encoder"
    matching=(
        not root.is_symlink() and not cached.parent.is_symlink() and
        not cached.is_symlink() and cached.is_dir() and
        all(not (cached/name).is_symlink() and (cached/name).is_file()
            and (cached/name).stat().st_size == size for name,size in sizes.items())
    )
    total=sum(sizes.values())
    return {
        "qwen3_total_bytes":total,
        "qwen3_new_stage_budget_bytes":0 if matching else total,
        "existing_file_sizes_match_hint":bool(matching),
        "cache_integrity_verified":False,
        "verification_deferred_to_encoder":True,
    }

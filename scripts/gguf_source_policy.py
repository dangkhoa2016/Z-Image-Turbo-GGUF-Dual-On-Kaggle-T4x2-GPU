#!/usr/bin/env python3
"""Choose direct or verified local GGUF without silently creating a 5.9 GiB copy.

The policy is deliberately separated from GPU inference. In 'auto' a preexisting
verified local cache is reused; otherwise read the original model directly.
The 'local' mode explicitly opts into staging. No model bytes are ever changed.
"""
from __future__ import annotations
from pathlib import Path
import time

from stage_gguf_model import _expected, staged_path, stage_model

MODES = ("auto", "direct", "local")


def select_gguf_source(manifest: dict, local_root: Path, mode: str = "auto") -> dict:
    if not isinstance(mode, str) or mode not in MODES:
        raise ValueError("GGUF_SOURCE_MODE_INVALID: expected auto, direct, or local")
    source, size, digest = _expected(manifest)
    root=Path(local_root)
    if not root.is_absolute() or root.is_symlink():
        raise ValueError("GGUF_LOCAL_ROOT_INVALID")
    started=time.monotonic()
    destination=staged_path(manifest,root)
    # No filesystem modifications in the direct path or auto without cache.
    if mode=="local":
        effective="local"
        verified=stage_model(manifest,root)
    elif mode=="auto" and (destination.exists() or destination.is_symlink()):
        effective="local"
        verified=stage_model(manifest,root)  # Verifies full SHA256, rejects corrupt cache.
    else:
        effective="direct"
        verified=source
    return {
        "requested_mode":mode,
        "effective_mode":effective,
        "model_path":str(verified),
        "source_manifest_path":str(source),
        "sha256_expected":digest,
        "bytes_expected":size,
        "source_selection_seconds":round(time.monotonic()-started,3),
        "staged_override_path":str(verified) if effective=="local" else None,
        "integrity":"sha256_verified_local" if effective=="local" else "manifest_size_verified_direct",
    }

"""CPU-only staging acceptance: full streaming, caching, failure and integrity gates."""
import hashlib
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"scripts"))
from stage_gguf_model import stage_model, verify_staged_override, staged_path
from inference_provenance import (
    ACCEPTED_INFERENCE_FINGERPRINT, STAGED_INFERENCE_FINGERPRINT, SELECTABLE_GGUF_INFERENCE_FINGERPRINT,
    ACCEPTED_ENCODER_SUBSET_FINGERPRINT, encoder_subset_fingerprint,
    inference_fingerprint, verify_cached_source,
)

assert inference_fingerprint(ROOT) == SELECTABLE_GGUF_INFERENCE_FINGERPRINT
assert encoder_subset_fingerprint(ROOT) == ACCEPTED_ENCODER_SUBSET_FINGERPRINT
assert STAGED_INFERENCE_FINGERPRINT != ACCEPTED_INFERENCE_FINGERPRINT
# Previously accepted PNG reports must NOT be silently reused under altered worker source.
try:
    verify_cached_source(
        {"source_sha":"a"*40, "inference_fingerprint":ACCEPTED_INFERENCE_FINGERPRINT},
        "b"*40, STAGED_INFERENCE_FINGERPRINT)
except ValueError:
    pass
else:
    raise AssertionError("old GPU outputs incorrectly accepted as a new GPU result")

def rejected(fn, label):
    try:
        fn()
    except (RuntimeError, ValueError, OSError):
        return
    raise AssertionError("expected fail-closed: "+label)

with tempfile.TemporaryDirectory(prefix="zimage-gguf-staging-cpu-") as dir:
    root=Path(dir)
    source=root/"input.gguf"
    payload=(bytes(range(256))*8192)  # 2 MiB synthetic bytes, no real model.
    source.write_bytes(payload)
    expected=hashlib.sha256(payload).hexdigest()
    m={"gguf_path":str(source),"gguf_bytes":len(payload),"gguf_sha256":expected}
    dest=root/"stage"
    target=staged_path(m,dest)
    assert target.name==expected+".gguf"
    rejected(lambda: stage_model(m,dest,reserve_bytes=10**18),"insufficient disk")
    assert not target.exists()
    first=stage_model(m,dest,reserve_bytes=0)
    assert first==target and first.read_bytes()==payload
    assert verify_staged_override(m,first,dest)==first
    original_mtime=first.stat().st_mtime_ns
    assert stage_model(m,dest,reserve_bytes=0)==first
    assert first.stat().st_mtime_ns==original_mtime
    rejected(lambda: verify_staged_override(m,root/"wrong.gguf",dest),"bad override path")
    bad=dict(m,gguf_sha256="0"*64)
    rejected(lambda: stage_model(bad,root/"bad-stage",reserve_bytes=0),"bad checksum")
    assert not staged_path(bad,root/"bad-stage").exists()
    assert not list((root/"bad-stage").glob("*.partial"))
    first.write_bytes(b"x"+payload[1:])
    rejected(lambda: stage_model(m,dest,reserve_bytes=0),"corrupt pre-existing cache")
    rejected(lambda: verify_staged_override(m,first,dest),"corrupt worker cache")
    assert first.read_bytes()!=payload  # It was never silently repaired.
    link=root/"symlink-root"
    link.symlink_to(dest,target_is_directory=True)
    rejected(lambda: stage_model(m,link,reserve_bytes=0),"symlink destination")
    # Interrupted .partial is never trusted, even if it matches target bytes.
    another=root/"another-stage"
    another.mkdir()
    (another/"orphan.partial").write_bytes(payload)
    assert stage_model(m,another,reserve_bytes=0).is_file()
    assert (another/"orphan.partial").read_bytes()==payload
print("GGUF_LOCAL_STAGE_CPU_PASS streaming_sha256 atomic_cache disk_guard symlink_guard old_GPU_proof_closed")

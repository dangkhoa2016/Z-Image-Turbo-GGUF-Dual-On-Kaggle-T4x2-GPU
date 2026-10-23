"""P2.8 CPU-only integrity, notebook contract and negative fixtures."""
from pathlib import Path
import ast
import copy
import hashlib
import json
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from gguf_direct_integrity import verify_direct_source
from gguf_disk_budget import qwen3_stage_budget_hint
from inference_provenance import inference_fingerprint, STUDIO_TMP_INFERENCE_FINGERPRINT

def rejected(call, code):
    try:
        call()
    except (RuntimeError, ValueError, OSError) as exc:
        assert code in str(exc), f"unexpected rejection: {exc!s}"
        return
    raise AssertionError("P28 bad input wrongly accepted: "+code)

with tempfile.TemporaryDirectory(prefix="zimage-p28-verification-") as d:
    root=Path(d)
    p=root/"model.gguf"
    b=(bytes(range(256))*4096)
    p.write_bytes(b)
    digest=hashlib.sha256(b).hexdigest()
    m={"gguf_path":str(p),"gguf_bytes":len(b),"gguf_sha256":digest}
    before={x.name for x in root.iterdir()}
    out=verify_direct_source(m)
    assert out["status"]=="FULL_SHA256_VERIFIED_BEFORE_WORKERS"
    assert out["bytes_verified"]==len(b) and out["sha256_verified"]==digest
    assert {x.name for x in root.iterdir()}==before, "direct verifier staged files unexpectedly"
    p.write_bytes(b"x"+b[1:])
    rejected(lambda: verify_direct_source(m),"STAGE_VERIFICATION_SHA256_MISMATCH")
    p.write_bytes(b[:-1])
    rejected(lambda: verify_direct_source(m),"STAGE_SOURCE_SIZE_MISMATCH")
    p.write_bytes(b)
    alternate=root/"alternate.gguf"
    alternate.write_bytes(b)
    link=root/"source-link.gguf"
    link.symlink_to(alternate)
    rejected(lambda:verify_direct_source(dict(m,gguf_path=str(link))),"STAGE_INVALID_SOURCE_FILE")
    assert not (root/"stage").exists()

# A pre-existing local cache can reduce REQUIRED NEW disk without being trusted.
with tempfile.TemporaryDirectory(prefix="zimage-p28-disk-budget-") as d:
    root=Path(d)
    source=root/"input";source.mkdir()
    (source/"shard-a").write_bytes(b"a"*1024)
    (source/"shard-b").write_bytes(b"b"*2048)
    names=("shard-a","shard-b")
    digest="a"*64
    stage=root/"stage"
    first=qwen3_stage_budget_hint(stage,digest,source,names)
    assert first["qwen3_new_stage_budget_bytes"]==3072
    assert first["cache_integrity_verified"] is False
    cached=stage/digest/"text_encoder";cached.mkdir(parents=True)
    for name in names:(cached/name).write_bytes((source/name).read_bytes())
    next_run=qwen3_stage_budget_hint(stage,digest,source,names)
    assert next_run["qwen3_new_stage_budget_bytes"]==0
    assert next_run["existing_file_sizes_match_hint"] is True
    assert next_run["cache_integrity_verified"] is False
    # The size-only hint never asserts data correctness: mandatory encoder check remains.
    (cached/"shard-a").write_bytes(b"x"*1024)
    assert qwen3_stage_budget_hint(stage,digest,source,names)["cache_integrity_verified"] is False
    (cached/"shard-a").write_bytes(b"x")
    assert qwen3_stage_budget_hint(stage,digest,source,names)["qwen3_new_stage_budget_bytes"]==3072
    (cached/"shard-a").unlink()
    (cached/"shard-a").symlink_to(source/"shard-a")
    assert qwen3_stage_budget_hint(stage,digest,source,names)["qwen3_new_stage_budget_bytes"]==3072

# Optional benchmark notebooks must not be part of the public repository.
assert not (ROOT/"benchmarks/notebooks").exists()
assert inference_fingerprint(ROOT)==STUDIO_TMP_INFERENCE_FINGERPRINT
print("GGUF_DIRECT_INTEGRITY_CPU_PASS direct_full_sha256 tamper_rejected size_rejected symlink_rejected no_staging unchanged_fingerprint cache_aware_disk_budget_untrusted_hint")
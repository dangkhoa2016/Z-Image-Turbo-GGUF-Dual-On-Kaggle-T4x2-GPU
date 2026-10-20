"""CPU-only GGUF source policy: auto is no-copy absent cache, local is explicit."""
import hashlib
from pathlib import Path
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from gguf_source_policy import select_gguf_source
from inference_provenance import (
    SELECTABLE_GGUF_INFERENCE_FINGERPRINT,STAGED_INFERENCE_FINGERPRINT,
    ACCEPTED_ENCODER_SUBSET_FINGERPRINT,encoder_subset_fingerprint,
    inference_fingerprint,verify_cached_source)

assert inference_fingerprint(ROOT)==SELECTABLE_GGUF_INFERENCE_FINGERPRINT
assert encoder_subset_fingerprint(ROOT)==ACCEPTED_ENCODER_SUBSET_FINGERPRINT
assert STAGED_INFERENCE_FINGERPRINT!=SELECTABLE_GGUF_INFERENCE_FINGERPRINT
try:
    verify_cached_source({"inference_fingerprint":STAGED_INFERENCE_FINGERPRINT},
                         "a"*40,SELECTABLE_GGUF_INFERENCE_FINGERPRINT)
except ValueError:pass
else:raise AssertionError("previous source version images wrongly accepted")

def reject(fn):
    try:fn()
    except (RuntimeError,ValueError,OSError):return
    raise AssertionError("unsafe source choice accepted")

with tempfile.TemporaryDirectory(prefix="zimage-gguf-source-policy-test-") as d:
    root=Path(d)
    source=root/"source.gguf"
    data=b"valid-test-model"+bytes(range(256))*1024
    source.write_bytes(data)
    manifest={
        "gguf_path":str(source),"gguf_bytes":len(data),
        "gguf_sha256":hashlib.sha256(data).hexdigest(),
    }
    dest=root/"stage"
    auto=select_gguf_source(manifest,dest)
    assert auto["requested_mode"]=="auto"
    assert auto["effective_mode"]=="direct"
    assert auto["staged_override_path"] is None
    assert auto["model_path"]==str(source)
    assert not dest.exists(), "auto unexpectedly created 5.9 GB staging"
    direct=select_gguf_source(manifest,dest,mode="direct")
    assert direct["effective_mode"]=="direct" and not dest.exists()
    reject(lambda:select_gguf_source(manifest,dest,mode="fast"))
    reject(lambda:select_gguf_source(manifest,dest,mode="LOCAL"))
    local=select_gguf_source(manifest,dest,mode="local")
    assert local["effective_mode"]=="local"
    assert Path(local["model_path"]).is_file()
    assert local["staged_override_path"]==local["model_path"]
    reused=select_gguf_source(manifest,dest,mode="auto")
    assert reused["effective_mode"]=="local"
    assert reused["model_path"]==local["model_path"]
    assert select_gguf_source(manifest,dest,mode="direct")["effective_mode"]=="direct"
    cached=Path(local["model_path"])
    cached.write_bytes(b"tamper"+data[6:])
    reject(lambda:select_gguf_source(manifest,dest,mode="auto"))
    reject(lambda:select_gguf_source(manifest,dest,mode="local"))
    # A corrupt cached file blocks auto/local but never forces direct mode to copy.
    assert select_gguf_source(manifest,dest,mode="direct")["effective_mode"]=="direct"
    assert cached.read_bytes()!=data
print("GGUF_SOURCE_POLICY_CPU_PASS auto_no_copy direct_no_copy local_verified reusable_cache corrupt_cache_fail_closed")

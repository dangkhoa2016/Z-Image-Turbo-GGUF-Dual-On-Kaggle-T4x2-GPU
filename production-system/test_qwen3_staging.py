"""P2.2 CPU-only Qwen3 checkpoint staging: integrity, atomicity and concurrency."""
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "scripts"))
from kaggle_production_demo import engine_notebook
import shutil
import subprocess
import sys
import tempfile
import time

from qwen3_staging import FILES, select_qwen3_source

def digest(b):return hashlib.sha256(b).hexdigest()
def rejected(fn,fragment):
    try:fn()
    except (RuntimeError,ValueError,OSError) as e:
        assert fragment in str(e),(fragment,e)
        return
    raise AssertionError("unexpected acceptance: "+fragment)
def make(root):
    src=root/"dataset"/"support"/"text_encoder"
    src.mkdir(parents=True)
    rows=[]
    for name in sorted(FILES):
        content=(name+"!").encode()*4 if name.endswith(".json") else (name+"!"*6).encode()*10
        (src/name).write_bytes(content)
        rows.append(dict(path="text_encoder/"+name,bytes=len(content),sha256=digest(content)))
    rows.append(dict(path="scheduler/config.json",bytes=3,sha256=digest(b"cat")))
    manifest=root/"dataset"/"support-files-manifest.json"
    manifest.write_text(json.dumps(rows))
    support=dict(support_root=str(src.parent),manifest_path=str(manifest),manifest_sha256=digest(manifest.read_bytes()))
    return src,support,rows

with tempfile.TemporaryDirectory(prefix="zimage-p22-qwen3-cpu-") as tmp:
    root=Path(tmp)
    src,support,rows=make(root)
    stage=root/"cache"
    # Direct is deliberately the non-copying default; no manifest hash read.
    a=select_qwen3_source(support,stage)
    assert a["effective_mode"]=="direct" and a["text_encoder_dir"]==str(src)
    assert not stage.exists()
    unsupported=dict(support,manifest_sha256="bad")
    assert select_qwen3_source(unsupported,stage,"direct")["effective_mode"]=="direct"
    rejected(lambda:select_qwen3_source(support,stage,"internet"),"QWEN3_STAGE_MODE_INVALID")
    rejected(lambda:select_qwen3_source(support,stage,"local",reserve_bytes=-1),"QWEN3_STAGE_RESERVE_INVALID")
    # In auto, no new cache is created.
    a=select_qwen3_source(support,stage,"auto")
    assert a["effective_mode"]=="direct" and not stage.exists()
    rejected(lambda:select_qwen3_source(unsupported,stage,"local"),"QWEN3_MANIFEST_SHA256_INVALID")
    tampered=dict(support,manifest_sha256=digest(b"changed"))
    rejected(lambda:select_qwen3_source(tampered,stage,"local"),"QWEN3_SUPPORT_MANIFEST_SHA256_MISMATCH")
    # Disk guard is enforced before any partial file.
    rejected(lambda:select_qwen3_source(support,stage,"local",reserve_bytes=10**20),
             "QWEN3_STAGE_INSUFFICIENT_DISK")
    assert not list(stage.glob(".*.partial"))
    original=src/"model-00001-of-00003.safetensors"
    original.write_bytes(b"x"*original.stat().st_size)
    rejected(lambda:select_qwen3_source(support,stage,"local",reserve_bytes=0),
             "QWEN3_STAGE_SOURCE_SHA256_OR_SIZE_MISMATCH")
    assert not list(stage.glob(".*.partial"))
    assert not (stage/support["manifest_sha256"]).exists()
    original.write_bytes((original.name+"!"*6).encode()*10)
    # Fresh staging, six hash verified local copies.
    before=time.monotonic()
    a=select_qwen3_source(support,stage,"local",reserve_bytes=0)
    assert a["effective_mode"]=="local" and a["copied"] and a["integrity"]=="support_manifest_sha256_verified_files"
    assert a["selection_seconds"]<=time.monotonic()-before+0.1
    local=Path(a["text_encoder_dir"])
    assert {p.name for p in local.iterdir()}==FILES
    assert all((local/name).read_bytes()==(src/name).read_bytes() for name in FILES)
    assert a["verified_bytes"]==sum(len((src/n).read_bytes()) for n in FILES)
    # Stale scratch from a different process must never be deleted automatically.
    stale=stage/".orphaned-from-other-session.partial"
    stale.mkdir()
    (stale/"record").write_text("keep")
    b=select_qwen3_source(support,stage,"auto")
    assert b["effective_mode"]=="local" and not b["copied"] and stale.exists()
    assert b["text_encoder_dir"]==str(local)
    # Fail closed for corrupt pre-existing cache, never repair or overwrite it.
    victim=local/"config.json"
    original_content=victim.read_bytes()
    victim.write_bytes(b"A"*len(original_content))
    rejected(lambda:select_qwen3_source(support,stage,"local"),"QWEN3_LOCAL_VERIFY_SHA256_MISMATCH")
    rejected(lambda:select_qwen3_source(support,stage,"auto"),"QWEN3_LOCAL_VERIFY_SHA256_MISMATCH")
    assert victim.read_bytes()==b"A"*len(original_content)
    victim.write_bytes(original_content)
    # Extra untracked file is an integrity violation.
    unexpected=local/"untracked.txt"
    unexpected.write_text("unexpected")
    rejected(lambda:select_qwen3_source(support,stage,"local"),"QWEN3_LOCAL_CACHE_FILE_SET_MISMATCH")
    unexpected.unlink()
    # Symlink in the verified cache must fail.
    victim.unlink()
    victim.symlink_to(src/"config.json")
    rejected(lambda:select_qwen3_source(support,stage,"local"),"QWEN3_LOCAL_VERIFY_SIZE_OR_TYPE_MISMATCH")
    victim.unlink()
    victim.write_bytes(original_content)
    assert select_qwen3_source(support,stage,"local")["copied"] is False
    # Cache-root and ancestor symlinks are forbidden.
    alias=root/"alias"
    alias.symlink_to(stage,target_is_directory=True)
    rejected(lambda:select_qwen3_source(support,alias,"local"),"QWEN3_PATH_SYMLINK")
    rejected(lambda:select_qwen3_source(support,src/"inside","local"),"QWEN3_DESTINATION_OVERLAPS_SOURCE")
    rejected(lambda:select_qwen3_source(support,root/".." /"outside","local"),"QWEN3_PATH_UNSAFE")
    # Lock symlink fails before open. Cache remains preserved.
    lock=stage/".qwen3-stage.lock"
    lock.unlink()
    lock.symlink_to(src/"config.json")
    rejected(lambda:select_qwen3_source(support,stage,"local"),"QWEN3_STAGE_LOCK_SYMLINK")
    lock.unlink()
    # Child cannot stage concurrently while another process holds the lock.
    fd=os.open(lock,os.O_CREAT|os.O_RDWR,0o600)
    fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    helper="from pathlib import Path;from qwen3_staging import select_qwen3_source; import json,sys; result=select_qwen3_source(json.loads(sys.argv[1]),Path(sys.argv[2]),'local',reserve_bytes=0,lock_timeout_seconds=4); print(result['effective_mode'])"
    env=os.environ.copy();env["PYTHONPATH"]=str(Path(__file__).parent)
    command=[sys.executable,"-c",helper,json.dumps(support),str(stage)]
    proc=subprocess.Popen(command,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        time.sleep(0.4)
        assert proc.poll() is None, "Child bypassed lock"
    finally:
        fcntl.flock(fd,fcntl.LOCK_UN);os.close(fd)
    stdout,stderr=proc.communicate(timeout=12)
    assert proc.returncode==0,(stdout,stderr)
    assert stdout.strip().endswith("local")
    # Two simultaneous copy attempts must converge to one atomic publication.
    other=root/"new-cache"
    runners=[subprocess.Popen([sys.executable,"-c",helper,json.dumps(support),str(other)],
               env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for _ in range(2)]
    results=[p.communicate(timeout=12) for p in runners]
    assert all(p.returncode==0 for p in runners),results
    assert sum("QWEN3_STAGE_CREATED_VERIFIED" in o for o,e in results)==1,results
    assert sum("QWEN3_STAGE_REUSED_VERIFIED" in o for o,e in results)==1,results
    assert not list(other.glob("*.partial"))
    assert select_qwen3_source(support,other,"auto")["effective_mode"]=="local"
    # Tampered source even with same size cannot be published under a new root.
    (src/"model-00002-of-00003.safetensors").write_bytes(b"!"*(src/"model-00002-of-00003.safetensors").stat().st_size)
    bad=root/"bad-cache"
    rejected(lambda:select_qwen3_source(support,bad,"local",reserve_bytes=0),"QWEN3_STAGE_SOURCE_SHA256_OR_SIZE_MISMATCH")
    assert not list(bad.glob("*.partial"))
    assert not (bad/support["manifest_sha256"]).exists()

# Static contract: production encoder leaves the tokenizer on original input.
code=(Path(__file__).parent/"encode_batch_gpu.py").read_text()
assert 'from qwen3_staging import select_qwen3_source' in code
assert 'qwen3_cache_root=Path(os.environ.get("ZIMAGE_QWEN3_STAGE_ROOT"' in code
assert 'qwen3_mode=os.environ.get("ZIMAGE_QWEN3_SOURCE_MODE", "direct")' in code
assert 'QWEN3_STAGE_ROOT_OUTSIDE_ALLOWED_CACHE_ROOT' in code
assert 'mode=qwen3_mode' in code
assert code.index('TOKENIZER_LOAD_FINISHED') < code.index('QWEN3_SOURCE_SELECTION_BEGIN') < code.index('QWEN3_WEIGHTS_LOAD_BEGIN')
assert 'str(support_root/"tokenizer")' in code
assert 'Qwen3Model.from_pretrained(selected["text_encoder_dir"]' in code
# Modified encoder code invalidates automatic use of prior saved image/embedding source proofs.
sys.path.insert(0,str(Path(__file__).parents[1]/"scripts"))
from inference_provenance import (
    ACCEPTED_SOURCE_SHA,SELECTABLE_GGUF_INFERENCE_FINGERPRINT,
    P22_QWEN3_STAGING_INFERENCE_FINGERPRINT,verify_cached_source,
)
rejected(lambda:verify_cached_source(
    {"source_sha":ACCEPTED_SOURCE_SHA,"inference_fingerprint":SELECTABLE_GGUF_INFERENCE_FINGERPRINT},
    "a"*40,P22_QWEN3_STAGING_INFERENCE_FINGERPRINT,
),"CACHED_INFERENCE_SOURCE_MISMATCH")
rejected(lambda:verify_cached_source(
    {"source_sha":ACCEPTED_SOURCE_SHA}, "a"*40,
    P22_QWEN3_STAGING_INFERENCE_FINGERPRINT,
),"CACHED_INFERENCE_SOURCE_NOT_VERIFIED")

notebook=engine_notebook(ROOT)
assert len(notebook["cells"])==28
checkout_code="".join(notebook["cells"][3]["source"])
assert 'SOURCE_REF = os.environ.get("ZIMAGE_SOURCE_REF", "main")' in checkout_code
assert 'EXPECTED_SOURCE_SHA = published_source_sha()' in checkout_code
assert 'git", "clone", "--branch", SOURCE_REF, REPO_URL' in checkout_code

diagnostic_code="".join(notebook["cells"][9]["source"])
assert "QWEN3_SOURCE_MODE = 'local'" in diagnostic_code
assert "VENDOR_ENV['ZIMAGE_QWEN3_SOURCE_MODE'] = QWEN3_SOURCE_MODE" in diagnostic_code
assert "VENDOR_ENV['ZIMAGE_QWEN3_STAGE_ROOT'] = str(QWEN3_STAGE_ROOT)" in diagnostic_code
diagnostic_doc="".join(notebook["cells"][8]["source"])
assert "Qwen3" in diagnostic_code and "text encoder" in (ROOT/"notebooks/kaggle-dual-gpu-production-demo.ipynb").read_text().lower()

print("QWEN3_LOCAL_STAGE_CPU_PASS manifest_signed file_sha256 disk_guard copy_atomic corrupt_fail_closed auto_policy direct_default symlink_guard locking_concurrency GPU_UNUSED")

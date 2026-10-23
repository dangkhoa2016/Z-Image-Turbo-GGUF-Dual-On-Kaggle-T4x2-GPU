"""P2.4 CPU-only prefetch fixture tests: atomic, SHA, lock, notebook contract."""
from pathlib import Path
import ast
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
ROOT=Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "scripts"))
from kaggle_production_demo import engine_notebook
PREFETCH=ROOT/"scripts/gguf_prefetch.py"
assert PREFETCH.is_file()
CODE=PREFETCH.read_text()
assert 'select_gguf_source(manifest,destination,mode="local")' in CODE
assert "MAX_PREFETCH_SECONDS = 420" in CODE
assert "signal.signal(signal.SIGTERM,terminated)" in CODE

# CI uses /tmp, Kaggle uses /kaggle/working. Override the private test
# subprocess module constant in-memory; production CLI has NO env bypass.
with tempfile.TemporaryDirectory(prefix="zimage-p24-") as temp:
    T=Path(temp)
    TEST_WRAPPER = (
        "import sys; from pathlib import Path; "
        "sys.path.insert(0,sys.argv[1]); import gguf_prefetch as m; "
        "m._ALLOWED_ROOT=Path(sys.argv[2]); "
        "sys.argv=['gguf_prefetch.py']+sys.argv[3:]; "
        "raise SystemExit(m.main())"
    )
    # The real module still rejects any path outside /kaggle/working.
    CMD=[sys.executable,"-c",TEST_WRAPPER,str(ROOT/"scripts"),str(T)]
    source=T/"synthetic.gguf"
    # Synthetic bytes are NOT a real model. Exercises I/O and integrity only.
    data=(b"P24_CPU_SYNTHETIC_BLOCK\x00"*4096)*128  # ~12 MiB
    source.write_bytes(data)
    sha=hashlib.sha256(data).hexdigest()
    manifest=T/"model.json"
    manifest.write_text(json.dumps({"gguf_path":str(source),"gguf_bytes":len(data),
                                    "gguf_sha256":sha}))
    stage=T/"stage"
    r1=T/"prefetch-1.json"
    r2=T/"prefetch-2.json"
    def cli(report,expected=0):
        args=CMD + [
              "--manifest",str(manifest),
              "--destination",str(stage),
              "--report",str(report)]
        run=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                           text=True,timeout=35)
        assert (run.returncode==0)==(expected==0),run.stdout[-900:]
        return run.stdout

    output=cli(r1)
    assert "P24_PREFETCH_VERIFIED" in output
    receipt=json.loads(r1.read_text())
    target=Path(receipt["staged_path"])
    assert target.is_file() and target.stat().st_size==len(data)
    assert hashlib.sha256(target.read_bytes()).hexdigest()==sha
    assert receipt["worker_must_reverify"] is True
    assert receipt["source_sha256"]==sha
    assert receipt["status"]=="VERIFIED_LOCAL_GGUF_READY"
    assert not list(stage.glob("*.partial"))
    # Rerun must VERIFY existing local ciphertext, never replace with blind cache.
    output=cli(r2)
    assert "GGUF_STAGE_REUSED_VERIFIED" in output
    assert json.loads(r2.read_text())["source_sha256"]==sha

    # Parallel workers competing for a new cache must serialize on existing flock.
    shared=T/"parallel-cache"; reports=[T/f"parallel-{i}.json" for i in range(2)]
    def run_parallel(rep):
        return subprocess.run(
            CMD + ["--manifest",str(manifest),
             "--destination",str(shared),"--report",str(rep)],
            stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=40)
    with ThreadPoolExecutor(max_workers=2) as ex:
        results=list(ex.map(run_parallel,reports))
    assert all(x.returncode==0 for x in results),[x.stdout for x in results]
    assert sum("GGUF_STAGE_CREATED_VERIFIED" in x.stdout for x in results)==1
    assert sum("GGUF_STAGE_REUSED_VERIFIED" in x.stdout for x in results)==1
    assert all(r.is_file() for r in reports)
    assert hashlib.sha256((shared/(sha+".gguf")).read_bytes()).hexdigest()==sha

    # Reject corruption, never overwrite it, never publish success metadata.
    target.write_bytes(b"x"*len(data))
    evil=T/"corrupt-no-success.json"
    output=cli(evil,expected=1)
    assert "STAGE_VERIFICATION_SHA256_MISMATCH" in output
    assert not evil.exists()
    assert target.read_bytes()[:2]==b"xx"
    # Tampered source data cannot publish a local cache or receipt.
    source.write_bytes(b"z"*len(data))
    wrong=T/"tampered-source-cache"; wrong_report=T/"tampered-no-success.json"
    run=subprocess.run(
       CMD + ["--manifest",str(manifest),
        "--destination",str(wrong),"--report",str(wrong_report)],
       capture_output=True,text=True,timeout=35)
    assert run.returncode!=0 and "STAGE_COPY_SHA256_MISMATCH" in run.stderr
    assert not wrong_report.exists() and not (wrong/(sha+".gguf")).exists()
    assert not list(wrong.glob("*.partial"))
    # Symlink root and invalid non-working destinations rejected.
    symlink=T/"link";symlink.symlink_to(stage,target_is_directory=True)
    run=subprocess.run(
       CMD + ["--manifest",str(manifest),
        "--destination",str(symlink),"--report",str(T/"no-success.json")],
       capture_output=True,text=True,timeout=20)
    assert run.returncode!=0 and "P24_STAGE_ROOT_UNSAFE" in run.stderr
    assert not (T/"no-success.json").exists()

notebook=engine_notebook(ROOT)
assert len(notebook["cells"])==28
for n,c in enumerate(notebook["cells"]):
    if c["cell_type"]=="code":
        ast.parse("".join(c["source"]),filename=f"notebook-cell-{n}")
checkout="".join(notebook["cells"][3]["source"])
encoder="".join(notebook["cells"][9]["source"])
workers="".join(notebook["cells"][11]["source"])
assert 'SOURCE_REF = os.environ.get("ZIMAGE_SOURCE_REF", "main")' in checkout
assert "P24_GGUF_PREFETCH_ENABLED = False" in checkout
assert "P24_GGUF_PREFETCH_STARTED" in encoder
assert 'P24_PREFETCH_PROCESS=subprocess.Popen(' in encoder
assert 'start_new_session=True' in encoder
assert 'if P24_GGUF_PREFETCH_ENABLED and os.environ.get("ZIMAGE_GGUF_SOURCE_MODE","local")=="local":' in encoder
assert 'P24_PREFETCH_PROCESS.wait(timeout=430)' in workers
assert "P24_GGUF_PREFETCH_FAILED: worker startup BLOCKED" in workers
assert "P24_GGUF_PREFETCH_RECEIPT_MISSING" in workers
assert "gguf_choice = select_gguf_source(" in workers
assert workers.index("P24_PREFETCH_PROCESS.wait(timeout=430)") < workers.index("gguf_choice = select_gguf_source(")
assert "P24_PREFETCH_RESULT" in workers and "'p24_gguf_prefetch':P24_PREFETCH_RESULT" in workers
assert "STARTUP_PER_GPU_LIMIT_SECONDS = 1200" in workers
print("GGUF_PREFETCH_CPU_PASS synthetic_atomic_sha256 race_serialized corruption_rejected timeout_bound notebook_GPU_UNUSED")

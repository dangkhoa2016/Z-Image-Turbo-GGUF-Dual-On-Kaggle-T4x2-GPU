"""CPU-only Qwen3 storage and live child-process I/O diagnostic contracts."""
import sys
import os
import time
import tempfile
import subprocess
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "scripts"))
from kaggle_production_demo import engine_notebook
sys.path.insert(0,str(ROOT/"scripts"))
from qwen3_encoder_diagnostics import (
    describe_text_encoder_storage, encoder_child_snapshot, process_delta,
)

def rejected(work):
    try:work()
    except (ValueError,OSError):return
    raise AssertionError("invalid Qwen3 diagnostic input accepted")

with tempfile.TemporaryDirectory(prefix="zimage-encoder-io-cpu-") as name:
    root=Path(name)
    folder=root/"text_encoder"
    folder.mkdir()
    shard=folder/"model-00001-of-00002.safetensors"
    shard.write_bytes(b"x"*(2*1048576))
    (folder/"model-00002-of-00002.safetensors").write_bytes(b"y"*(1*1048576))
    (folder/"config.json").write_text("{}")
    meta=describe_text_encoder_storage(folder,sample_mib=1)
    assert meta["shards"]==2 and meta["total_weight_bytes"]==3*1048576
    assert meta["sample_bytes"]==1048576 and meta["sample_mib_per_second"]>0
    assert describe_text_encoder_storage(folder,sample_mib=0)["sample_bytes"]==0
    rejected(lambda:describe_text_encoder_storage(folder,sample_mib=32))
    fake=root/"bad-link"
    fake.symlink_to(folder,target_is_directory=True)
    rejected(lambda:describe_text_encoder_storage(fake))
    extra=folder/"linked.safetensors"
    extra.symlink_to(shard)
    rejected(lambda:describe_text_encoder_storage(folder))
    extra.unlink()
    assert encoder_child_snapshot(9999999) is None
    rejected(lambda:encoder_child_snapshot(-1))

    # Synthetic process tree: the phase-controller-shaped parent launches an
    # unrelated CPU-only fake child with precisely the encoder's script name.
    child_script=root/"encode_batch_gpu.py"
    child_script.write_text("import time\nprint('CPU_FAKE_ENCODER',flush=True)\ntime.sleep(3)\n")
    launch='import subprocess,sys,time; p=subprocess.Popen([sys.executable,sys.argv[1]],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); print(p.pid,flush=True); time.sleep(3)'
    parent=subprocess.Popen([sys.executable,"-u","-c",launch,str(child_script)],
                            stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        child_pid=int(parent.stdout.readline().strip())
        snap=None
        for _ in range(40):
            snap=encoder_child_snapshot(parent.pid)
            if snap is not None:break
            time.sleep(0.04)
        assert snap is not None,(parent.pid,child_pid)
        assert snap["pid"]==child_pid and snap["rss_bytes"]>0
        assert snap["process_start_ticks"]>0
        before=process_delta(None,snap,1.0)
        assert before["pid"]==child_pid and "read_mib_per_second" not in before
        assert process_delta(snap,snap,1.0)["read_mib_per_second"]==0
        assert process_delta(snap,snap,1.0)["cpu_pct_one_core_100"]==0
        other=dict(snap)
        other["process_start_ticks"]=snap["process_start_ticks"]+1
        assert "read_mib_per_second" not in process_delta(other,snap,1)
        assert process_delta(snap,None,1)["state"]=="ENCODER_PROCESS_NOT_FOUND"
    finally:
        if parent.poll() is None:
            parent.terminate()
            parent.wait(timeout=5)
        try:os.kill(child_pid,15)
        except ProcessLookupError:pass

nb=engine_notebook(ROOT)
assert len(nb["cells"])==28
code="".join(nb["cells"][9]["source"])
assert "encoder_child_snapshot(encoder.pid)" in code
assert "encoder-resources-" in code and "QWEN3_ENCODER_RESOURCE" in code
assert "describe_text_encoder_storage(" in code
assert "GGUF_STAGED_PATH" not in code
assert "DIRECT_REUSE_ENCODER" in code
assert "elapsed > 1500" in code
print("QWEN3_LIVE_IO_CPU_PASS storage_bounds_symlink_guard child_identity pid_guard counter_delta notebook_contract GPU_UNUSED")

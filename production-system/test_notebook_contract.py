"""Offline contract checks for notebook source identity and documentation."""
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from inference_provenance import (
    STUDIO_TMP_INFERENCE_FINGERPRINT,STUDIO_TMP_ENCODER_SUBSET_FINGERPRINT,
    P22_QWEN3_STAGING_INFERENCE_FINGERPRINT, P22_QWEN3_STAGING_ENCODER_SUBSET_FINGERPRINT,
    ACCEPTED_SOURCE_SHA,ACCEPTED_INFERENCE_FINGERPRINT,
    STAGED_INFERENCE_FINGERPRINT,SELECTABLE_GGUF_INFERENCE_FINGERPRINT,ACCEPTED_ENCODER_SUBSET_FINGERPRINT,
    PREDIAGNOSTIC_STAGED_INFERENCE_FINGERPRINT,
    check_source_sha,inference_fingerprint,encoder_subset_fingerprint,verify_cached_source
)
from validate_public_demo import validate as validate_public

assert inference_fingerprint(ROOT)==STUDIO_TMP_INFERENCE_FINGERPRINT
assert encoder_subset_fingerprint(ROOT)==STUDIO_TMP_ENCODER_SUBSET_FINGERPRINT
assert P22_QWEN3_STAGING_INFERENCE_FINGERPRINT != SELECTABLE_GGUF_INFERENCE_FINGERPRINT
assert P22_QWEN3_STAGING_ENCODER_SUBSET_FINGERPRINT != ACCEPTED_ENCODER_SUBSET_FINGERPRINT

assert STAGED_INFERENCE_FINGERPRINT != ACCEPTED_INFERENCE_FINGERPRINT
assert PREDIAGNOSTIC_STAGED_INFERENCE_FINGERPRINT != STAGED_INFERENCE_FINGERPRINT
assert check_source_sha("a"*40)=="a"*40
assert check_source_sha("")==""
for candidate in ["nope","a"*39,"z"*40,"123","a"*41]:
    try:check_source_sha(candidate)
    except ValueError:pass
    else:raise AssertionError("Invalid SHA accepted")

CURRENT="f"*40
report={"source_sha":CURRENT,"inference_fingerprint":ACCEPTED_INFERENCE_FINGERPRINT}
assert verify_cached_source(report,CURRENT,ACCEPTED_INFERENCE_FINGERPRINT)=="SAME_INFERENCE_CONTENT"
assert verify_cached_source(report,"d"*40,ACCEPTED_INFERENCE_FINGERPRINT)=="SAME_INFERENCE_CONTENT"
assert verify_cached_source({"source_sha":ACCEPTED_SOURCE_SHA},"e"*40,
                            ACCEPTED_INFERENCE_FINGERPRINT)=="VERIFIED_ACCEPTED_INFERENCE_CONTENT"
assert verify_cached_source({"source_sha":CURRENT},CURRENT,
                            ACCEPTED_INFERENCE_FINGERPRINT)=="SAME_CHECKOUT"

for bad in (
    ({"source_sha":CURRENT,"inference_fingerprint":"0"*64},CURRENT,ACCEPTED_INFERENCE_FINGERPRINT),
    ({"source_sha":ACCEPTED_SOURCE_SHA},"d"*40,"0"*64),
    ({"source_sha":"1"*40},"2"*40,ACCEPTED_INFERENCE_FINGERPRINT),
):
    try:verify_cached_source(*bad)
    except ValueError:pass
    else:raise AssertionError("Unverified source cache accepted")


# The probe must work on an ordinary CPU host and SIGUSR1 must not kill its worker.
import importlib.util
import os
import select
import signal
import subprocess
import tempfile
import time

probe_path=ROOT/'scripts/gguf_startup_diagnostics.py'
spec=importlib.util.spec_from_file_location('zimage_cpu_gguf_probe',probe_path)
probe=importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
mine=probe.read_process(os.getpid())
assert mine['pid']==os.getpid() and mine['rss_bytes']>0
assert mine['process_start_ticks']>0 and mine['cpu_ticks_per_second']>0
with tempfile.TemporaryDirectory(prefix='zimage-stack-probe-test-') as temp:
    sample=Path(temp)/'mock.gguf'
    sample.write_bytes(b'1234567890'*100000)
    result=probe.io_probe(sample,max_mib=1)
    assert result['sample_bytes']==sample.stat().st_size
    assert result['seconds']>0 and result['sample_mib_per_second']>0
    fake=Path(temp)/'synthetic_worker.py'
    fake.write_text(
        'import time\n'
        'print("CPU_FAKE_WORKER_READY",flush=True)\n'
        'time.sleep(1.5)\n',
        encoding='utf-8')
    env=os.environ.copy()
    env['ZIMAGE_PROFILE_TEST_WORKER']='1'
    child=subprocess.Popen(
        [sys.executable,'-u',str(probe_path),'run',str(fake)],
        stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,text=True,env=env)
    try:
        available,_,_=select.select([child.stdout],[],[],5)
        assert available,'profiling wrapper startup timed out'
        marker=child.stdout.readline()
        assert marker.startswith('ZIMAGE_GGUF_STACK_PROBE_READY '),marker
        assert child.poll() is None
        time.sleep(0.25)  # Let runpy enter the synthetic worker's sleep.
        os.kill(child.pid,signal.SIGUSR1)
        out,err=child.communicate(timeout=6)
        assert child.returncode==0,(out,err[-400:])
        assert 'CPU_FAKE_WORKER_READY' in out
        assert 'synthetic_worker.py' in err,err[-800:]
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=5)
print('GGUF_STACK_PROBE_CPU_PASS no_gpu_used=YES')

validate_public()
print("NOTEBOOK_PROVENANCE_CONTRACT_PASS no_gpu_used=YES")

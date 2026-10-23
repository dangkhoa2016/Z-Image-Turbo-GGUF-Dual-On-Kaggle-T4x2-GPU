"""P2.5 load-only CPU acceptance, no CUDA/model or real image generation."""
from pathlib import Path
import copy
import hashlib
import json
import sys
import tempfile
import zipfile
import ast

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from loadonly_evidence import export_loadonly_evidence
SOURCE="a"*40
FP="b"*64

def rejects(fragment,fn):
    try:fn()
    except (RuntimeError,ValueError) as e:
        assert fragment in str(e),(fragment,str(e))
    else:
        raise AssertionError("EXPECTED_REJECTION_NOT_RAISED:"+fragment)

with tempfile.TemporaryDirectory(prefix="p25-no-gpu-") as d:
    root=Path(d)
    report=root/"report.json"
    archive=root/"p25-loadonly-evidence.zip"
    obj={
        "schema":"ZIMAGE_P25_T4X2_LOAD_ONLY_V1",
        "status":"P25_TWO_GPU_MODELS_READY_NO_IMAGE_GENERATION",
        "source_sha":SOURCE,"inference_fingerprint":FP,
        "benchmark_mode":"overlap","fresh_benchmark_root":str(root),
        "checkpoint_cache_present_at_start":{"gguf_path_existed":False,"qwen3_path_existed":False},
        "png_count":0,"images":[],"generate_requests_sent":0,
        "gpu_count":2,"encoder_gpu":0,
        "worker_readiness":{"0":True,"1":True},
        "gpu_model_load_verified":True,
        "model_startup_seconds_per_gpu":{"0":51.3,"1":33.2},
    }
    def write(data):report.write_text(json.dumps(data))
    def export():return export_loadonly_evidence(
        report_path=report,archive_path=archive,source_sha=SOURCE,
        inference_fingerprint=FP,mode="overlap")
    write(obj)
    (root/"worker-0.log").write_text("PIPELINE_READY gpu0")
    (root/"worker-1.log").write_text("PIPELINE_READY gpu1")
    (root/"encoder.log").write_text("Authorization: Bearer secret")
    (root/"never-package.txt").write_text("secret")
    receipt=export()
    assert receipt["status"]=="P25_LOAD_ONLY_EVIDENCE_PACKAGED"
    assert receipt["mode"]=="overlap" and receipt["gpu_speedup_claimed"] is False
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        data=json.loads(z.read("acceptance.json"))
        assert data["images_generated"]==0 and data["gpu_speedup_claimed"] is False
        assert data["files"]["report.json"]["sha256"]==hashlib.sha256(report.read_bytes()).hexdigest()
        assert "diagnostics/encoder.log" not in z.namelist()
        assert "never-package.txt" not in z.namelist()
        assert {"diagnostics/worker-0.log","diagnostics/worker-1.log"}.issubset(set(z.namelist()))
    mutated=copy.deepcopy(obj);mutated["images"]=[{"file":"bad.png"}];write(mutated)
    rejects("P25_GENERATION_NOT_ZERO",export)
    mutated=copy.deepcopy(obj);mutated["generate_requests_sent"]=1;write(mutated)
    rejects("P25_GENERATION_NOT_ZERO",export)
    mutated=copy.deepcopy(obj);mutated["worker_readiness"]["1"]=False;write(mutated)
    rejects("P25_GPU_READINESS_PROOF_INVALID",export)
    mutated=copy.deepcopy(obj);mutated["source_sha"]="c"*40;write(mutated)
    rejects("P25_PROVENANCE_MISMATCH",export)
    mutated=copy.deepcopy(obj);mutated["status"]="PENDING";write(mutated)
    rejects("P25_REPORT_STATUS_INVALID",export)
    write(obj)
    (root/"fake.png").write_bytes(b"not a PNG")
    rejects("P25_PNG_PRESENT",export)
    (root/"fake.png").unlink()
    assert zipfile.is_zipfile(archive)

assert not (ROOT/"benchmarks/notebooks").exists()
print("MODEL_STARTUP_EVIDENCE_CPU_PASS zero_png zero_generation fail_closed_provenance exact_gpu_workers clean_report archive_integrity")

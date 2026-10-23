"""CPU-only contract and negative tests for P2.6 load-only A/B tools."""
from pathlib import Path
import copy
import hashlib
import io
import json
import sys
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from compare_loadonly_benchmarks import compare,render_markdown

# Historical comparison notebooks are intentionally not distributed.
# The synthetic A/B reports below test the maintained comparison implementation.
assert not (ROOT/"benchmarks/notebooks").exists()

SHA="a"*40
FP="b"*64
GGUF="c"*64

def receipt(root, mode, *, qcache=False, gcache=False):
    report={
        "schema":"ZIMAGE_P25_T4X2_LOAD_ONLY_V1",
        "status":"P25_TWO_GPU_MODELS_READY_NO_IMAGE_GENERATION",
        "source_sha":SHA,"inference_fingerprint":FP,
        "benchmark_mode":mode,
        "fresh_benchmark_root":str(root),
        "png_count":0,"images":[],"generate_requests_sent":0,
        "gpu_count":2,"encoder_gpu":0,
        "gpu_model_load_verified":True,
        "worker_readiness":{"0":True,"1":True},
        "model_startup_seconds_per_gpu":{"0":40.0,"1":30.0},
        "encoding_seconds":150 if mode=="sequential" else 180,
        "model_startup_seconds":140 if mode=="sequential" else 100,
        "gguf_source_selection":{"effective_mode":"local","sha256_expected":GGUF},
        "p24_gguf_prefetch":{
            "enabled":mode=="overlap",
            "status":"PASS" if mode=="overlap" else None,
            "receipt":{"total_elapsed_seconds":80} if mode=="overlap" else None,
            "wait_seconds_after_encoder":0 if mode=="overlap" else None,
        },
        "checkpoint_cache_present_at_start":{"gguf_path_existed":gcache,
                                             "qwen3_path_existed":qcache},
        "execution_host":"synthetic-cpu-host",
        "gpu_inventory":["GPU0 Tesla T4 fixture","GPU1 Tesla T4 fixture"],
    }
    content=json.dumps(report).encode()
    archive=root/(mode+".zip")
    acceptance={
        "schema":"ZIMAGE_P25_LOAD_ONLY_EXPORT_V1",
        "status":"P25_LOAD_ONLY_EVIDENCE_PACKAGED",
        "mode":mode,"images_generated":0,"gpu_speedup_claimed":False,
        "source_sha":SHA,"inference_fingerprint":FP,
        "files":{"report.json":{"bytes":len(content),
                                "sha256":hashlib.sha256(content).hexdigest()}}
    }
    with zipfile.ZipFile(archive,"w") as z:
        z.writestr("report.json",content)
        z.writestr("acceptance.json",json.dumps(acceptance))
    return archive,report

def rejects(needle,func):
    try:func()
    except RuntimeError as e:assert needle in str(e),(needle,str(e))
    else:raise AssertionError("expected rejection: "+needle)

with tempfile.TemporaryDirectory(prefix="zimage-p26-ab-") as d:
    root=Path(d)
    seqzip,seqrecord=receipt(root,"sequential")
    ovzip,ovrecord=receipt(root,"overlap")
    r=compare(seqzip,ovzip)
    delta=r["metrics"]["total_encoder_plus_workers_s"]
    assert delta=={"sequential_s":290,"overlap_s":280,
                   "sequential_minus_overlap_s":10}
    assert r["gpu_speedup_proven"] is False
    assert r["cache_state"]["same_path_presence"] is True
    assert "Raw timings only" in render_markdown(r)
    # Warm cache mismatch must trigger warning and NO claim of speedup.
    ovzip,_=receipt(root,"overlap",qcache=True)
    r=compare(seqzip,ovzip)
    assert any("cache" in s.lower() for s in r["warnings"])
    assert r["gpu_speedup_proven"] is False
    # Different model identity blocks comparison.
    modified=json.loads(zipfile.ZipFile(ovzip).read("report.json"))
    modified["gguf_source_selection"]["sha256_expected"]="d"*64
    tampered=root/"tampered.zip"
    c=json.dumps(modified).encode()
    accept=json.loads(zipfile.ZipFile(ovzip).read("acceptance.json"))
    accept["files"]["report.json"]={"bytes":len(c),
        "sha256":hashlib.sha256(c).hexdigest()}
    with zipfile.ZipFile(tampered,"w") as z:
        z.writestr("report.json",c)
        z.writestr("acceptance.json",json.dumps(accept))
    rejects("P26_MISMATCHED_SOURCE_OR_MODEL",lambda:compare(seqzip,tampered))
    # Corruption detected even if ZIP CRC is valid.
    bogus=root/"bogus.zip"
    with zipfile.ZipFile(bogus,"w") as z:
        z.writestr("report.json",b"{}")
        z.writestr("acceptance.json",json.dumps(accept))
    rejects("P26_CONTENT_HASH_MISMATCH",lambda:compare(seqzip,bogus))
    # Any new image breaks load-only proof (not just timing).
    report=copy.deepcopy(ovrecord)
    report["images"]=[{"sha":"not-allowed"}]
    body=json.dumps(report).encode()
    accept["files"]["report.json"]={"bytes":len(body),
        "sha256":hashlib.sha256(body).hexdigest()}
    accept["mode"]="overlap"
    with zipfile.ZipFile(bogus,"w") as z:
        z.writestr("report.json",body)
        z.writestr("acceptance.json",json.dumps(accept))
    rejects("P26_REPORT_INVALID",lambda:compare(seqzip,bogus))
print("MODEL_LOADING_COMPARISON_CPU_PASS synthetic_modes no_inference cache_warning SHA256_corruption model_mismatch image_rejected speedup_not_claimed")

#!/usr/bin/env python3
"""Compare P2.5 sequential/overlap load-only receipts without claiming causality."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile

HEX40=re.compile(r"[0-9a-f]{40}")
HEX64=re.compile(r"[0-9a-f]{64}")

def read_archive(path: Path, mode: str) -> dict:
    path=Path(path)
    if path.is_symlink() or not path.is_file() or not 0<path.stat().st_size<64*1024**2:
        raise RuntimeError("P26_UNSAFE_ZIP")
    with zipfile.ZipFile(path) as z:
        names=z.namelist()
        if len(names)>45 or len(set(names))!=len(names):
            raise RuntimeError("P26_INVALID_ZIP_MEMBERS")
        if {"report.json","acceptance.json"}-set(names) or z.testzip() is not None:
            raise RuntimeError("P26_INVALID_ARCHIVE")
        for entry in z.infolist():
            if entry.is_dir() or entry.file_size>8*1024**2 or entry.filename.startswith("/") or ".." in Path(entry.filename).parts:
                raise RuntimeError("P26_INVALID_ARCHIVE_ENTRY")
        acceptance=json.loads(z.read("acceptance.json"))
        report=json.loads(z.read("report.json"))
        if (acceptance.get("schema")!="ZIMAGE_P25_LOAD_ONLY_EXPORT_V1"
                or acceptance.get("mode")!=mode
                or acceptance.get("images_generated")!=0
                or acceptance.get("gpu_speedup_claimed") is not False):
            raise RuntimeError("P26_RECEIPT_INVALID")
        files=acceptance.get("files",{})
        if set(files)!=(set(names)-{"acceptance.json"}):
            raise RuntimeError("P26_FILES_MANIFEST_MISMATCH")
        for name,record in files.items():
            blob=z.read(name)
            if len(blob)!=record.get("bytes") or hashlib.sha256(blob).hexdigest()!=record.get("sha256"):
                raise RuntimeError("P26_CONTENT_HASH_MISMATCH")
        if (report.get("schema")!="ZIMAGE_P25_T4X2_LOAD_ONLY_V1"
                or report.get("status")!="P25_TWO_GPU_MODELS_READY_NO_IMAGE_GENERATION"
                or report.get("benchmark_mode")!=mode
                or report.get("png_count")!=0 or report.get("images")!=[]
                or report.get("generate_requests_sent")!=0
                or report.get("worker_readiness")!={"0":True,"1":True}
                or report.get("gpu_count")!=2
                or report.get("gpu_model_load_verified") is not True):
            raise RuntimeError("P26_REPORT_INVALID")
        if (not HEX40.fullmatch(report.get("source_sha",""))
                or not HEX64.fullmatch(report.get("inference_fingerprint",""))
                or report["source_sha"]!=acceptance.get("source_sha")
                or report["inference_fingerprint"]!=acceptance.get("inference_fingerprint")):
            raise RuntimeError("P26_PROVENANCE_INVALID")
        gguf=report.get("gguf_source_selection",{})
        if gguf.get("effective_mode")!="local" or not HEX64.fullmatch(gguf.get("sha256_expected","")):
            raise RuntimeError("P26_GGUF_IDENTITY_INVALID")
        pref=report.get("p24_gguf_prefetch",{})
        if pref.get("enabled") is not (mode=="overlap"):
            raise RuntimeError("P26_PREFETCH_MODE_INVALID")
        if mode=="overlap" and pref.get("status")!="PASS":
            raise RuntimeError("P26_PREFETCH_NOT_VERIFIED")
        for name in ("encoding_seconds","model_startup_seconds"):
            num=report.get(name)
            if isinstance(num,bool) or not isinstance(num,(int,float)) or num<0 or num>3600:
                raise RuntimeError("P26_DURATION_INVALID")
        workers=report.get("model_startup_seconds_per_gpu",{})
        if set(workers)!={"0","1"} or any(not isinstance(x,(float,int)) or x<0 for x in workers.values()):
            raise RuntimeError("P26_WORKER_DURATION_INVALID")
        return report

def compare(sequential: Path, overlap: Path) -> dict:
    a=read_archive(sequential,"sequential")
    b=read_archive(overlap,"overlap")
    if (a["source_sha"]!=b["source_sha"]
            or a["inference_fingerprint"]!=b["inference_fingerprint"]
            or a["gguf_source_selection"]["sha256_expected"]!=b["gguf_source_selection"]["sha256_expected"]):
        raise RuntimeError("P26_MISMATCHED_SOURCE_OR_MODEL")
    ac=a.get("checkpoint_cache_present_at_start")
    bc=b.get("checkpoint_cache_present_at_start")
    cache_known=isinstance(ac,dict) and isinstance(bc,dict) and "gguf_path_existed" in ac and "qwen3_path_existed" in ac and "gguf_path_existed" in bc and "qwen3_path_existed" in bc
    warnings=[]
    if not cache_known:
        warnings.append("Initial cache state unknown; comparison biased.")
    elif ac!=bc:
        warnings.append("Initial cache presence differs; not a controlled A/B.")
    elif any(ac.values()):
        warnings.append("Cache already existed; this is not a cold-start comparison.")
    if a.get("gpu_inventory")!=b.get("gpu_inventory"):
        warnings.append("GPU inventory differs between sessions.")
    if a.get("execution_host")!=b.get("execution_host"):
        warnings.append("Host differs; storage/CPU contention may differ.")
    warnings.append("OS page-cache state and Kaggle mount variability remain uncontrolled.")
    fields=["encoding_seconds","model_startup_seconds"]
    metrics={}
    for key in fields:
        metrics[key]={"sequential_s":a[key],"overlap_s":b[key],"sequential_minus_overlap_s":round(a[key]-b[key],3)}
    for i in ("0","1"):
        u=a["model_startup_seconds_per_gpu"][i]
        v=b["model_startup_seconds_per_gpu"][i]
        metrics["gpu"+i+"_startup_s"]={"sequential_s":u,"overlap_s":v,"sequential_minus_overlap_s":round(u-v,3)}
    u=round(a["encoding_seconds"]+a["model_startup_seconds"],3)
    v=round(b["encoding_seconds"]+b["model_startup_seconds"],3)
    metrics["total_encoder_plus_workers_s"]={"sequential_s":u,"overlap_s":v,"sequential_minus_overlap_s":round(u-v,3)}
    return {"schema":"ZIMAGE_P26_AB_ANALYSIS_V1",
            "status":"RAW_TIMINGS_ONLY_NOT_CAUSAL_SPEEDUP",
            "source_sha":a["source_sha"],
            "inference_fingerprint":a["inference_fingerprint"],
            "gguf_sha256":a["gguf_source_selection"]["sha256_expected"],
            "cache_state":{"sequential":ac,"overlap":bc,"same_path_presence":cache_known and ac==bc},
            "metrics":metrics,
            "overlap_prefetch_stage_s":b["p24_gguf_prefetch"].get("receipt",{}).get("total_elapsed_seconds"),
            "overlap_prefetch_wait_after_encoder_s":b["p24_gguf_prefetch"].get("wait_seconds_after_encoder"),
            "warnings":warnings,"gpu_speedup_proven":False}

def render_markdown(r: dict) -> str:
    lines=["# Load-only P2.6 A/B comparison",
           "",
           "Raw timings only — no proven speedup.",
           "",
           "| Metric | Sequential (s) | Overlap (s) | Sequential minus overlap (s) |",
           "|---|---:|---:|---:|"]
    for key,v in r["metrics"].items():
        lines.append("| "+key+" | "+str(v["sequential_s"])+" | "+str(v["overlap_s"])+" | "+str(v["sequential_minus_overlap_s"])+" |")
    lines+=["","## Measurement limitations"]
    lines.extend("- "+s for s in r["warnings"])
    lines+=["","Source SHA: "+r["source_sha"],
            "GGUF SHA256: "+r["gguf_sha256"],"",
            "Do not merge based on a single comparison."]
    return "\n".join(lines)+"\n"

def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument("--sequential",required=True,type=Path)
    ap.add_argument("--overlap",required=True,type=Path)
    ap.add_argument("--output-dir",required=True,type=Path)
    args=ap.parse_args()
    result=compare(args.sequential,args.overlap)
    args.output_dir.mkdir(parents=True,exist_ok=True)
    (args.output_dir/"p26-ab-analysis.json").write_text(json.dumps(result,indent=2)+"\n")
    (args.output_dir/"p26-ab-analysis.md").write_text(render_markdown(result))
    print("P26_RAW_AB_COMPARISON_PASS_NOT_PERFORMANCE_CLAIM")
    print(json.dumps(result["metrics"]["total_encoder_plus_workers_s"],sort_keys=True))
    for warning in result["warnings"]:print("WARNING",warning)

if __name__=="__main__":
    main()

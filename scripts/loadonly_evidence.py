#!/usr/bin/env python3
"""CPU-only post-run acceptance exporter for P2.5 *load only* trials.

Never loads models, submits inference, or creates images. Requires verifiable
notebook-generated report with zero inference requests and no PNG artifacts.
"""
from __future__ import annotations
from pathlib import Path
import hashlib
import json
import os
import re
import tempfile
import zipfile

_ALLOWED_LOG = re.compile(
    r"(?:encoder\.log|encoder-timing\.json|"
    r"encoder-resources-[A-Za-z0-9TZ-]+\.jsonl|"
    r"gguf-prefetch-[A-Za-z0-9TZ-]+\.(?:json|log)|"
    r"gguf-source-selection-[A-Za-z0-9TZ_-]+\.json|"
    r"worker-[01](?:-retry-[A-Za-z0-9TZ_-]+)?\.log|"
    r"model-startup-[A-Za-z0-9TZ_-]+\.jsonl)$"
)
_SECRET_PATTERN = re.compile(
    r"(authorization\s*:|bearer\s+\S+|password\s*[=:]|"
    r"api[_-]?token\s*[=:]|service[_-]?key\s*[=:])",re.I
)
MAX_LOG_BYTES = 6 * 1024**2


def _safe_read(path: Path, limit: int) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("P25_EVIDENCE_FILE_UNSAFE")
    size=path.stat().st_size
    if size<1 or size>limit:
        raise RuntimeError("P25_EVIDENCE_SIZE_INVALID")
    with path.open("rb") as f: contents=f.read(limit+1)
    if len(contents)>limit:
        raise RuntimeError("P25_EVIDENCE_OVERSIZE")
    return contents


def export_loadonly_evidence(*, report_path: Path, archive_path: Path,
                             source_sha: str, inference_fingerprint: str,
                             mode: str) -> dict:
    report_path=Path(report_path)
    archive_path=Path(archive_path)
    if mode not in ("sequential","overlap"):
        raise RuntimeError("P25_MODE_INVALID")
    if not re.fullmatch("[a-f0-9]{40}",source_sha):
        raise RuntimeError("P25_SOURCE_SHA_INVALID")
    if not re.fullmatch("[a-f0-9]{64}",inference_fingerprint):
        raise RuntimeError("P25_FINGERPRINT_INVALID")
    if (not report_path.is_absolute() or report_path.is_symlink()
            or report_path.name!="report.json"):
        raise RuntimeError("P25_REPORT_PATH_UNSAFE")
    root=report_path.parent.resolve(strict=True)
    if not root.is_dir():
        raise RuntimeError("P25_REPORT_ROOT_UNSAFE")
    if (not archive_path.is_absolute() or archive_path.is_symlink()
            or archive_path.name!="p25-loadonly-evidence.zip"
            or archive_path.parent.resolve(strict=True)!=root):
        raise RuntimeError("P25_ARCHIVE_PATH_UNSAFE")
    body=_safe_read(report_path,2*1024**2)
    data=json.loads(body)
    if data.get("schema")!="ZIMAGE_P25_T4X2_LOAD_ONLY_V1" or data.get("status")!="P25_TWO_GPU_MODELS_READY_NO_IMAGE_GENERATION":
        raise RuntimeError("P25_REPORT_STATUS_INVALID")
    if (data.get("source_sha")!=source_sha
            or data.get("inference_fingerprint")!=inference_fingerprint
            or data.get("benchmark_mode")!=mode):
        raise RuntimeError("P25_PROVENANCE_MISMATCH")
    if (data.get("png_count")!=0 or data.get("images")!=[]
            or data.get("generate_requests_sent")!=0):
        raise RuntimeError("P25_GENERATION_NOT_ZERO")
    if (data.get("gpu_count")!=2 or data.get("encoder_gpu")!=0
            or data.get("worker_readiness")!={"0":True,"1":True}
            or data.get("gpu_model_load_verified") is not True
            or set(data.get("model_startup_seconds_per_gpu",{}))!={"0","1"}):
        raise RuntimeError("P25_GPU_READINESS_PROOF_INVALID")
    if data.get("fresh_benchmark_root")!=str(root):
        raise RuntimeError("P25_BENCHMARK_ROOT_MISMATCH")
    if any(root.glob("*.png")):
        raise RuntimeError("P25_PNG_PRESENT")
    blobs={"report.json":body}
    omitted=[]
    for f in sorted(root.iterdir()):
        if _ALLOWED_LOG.fullmatch(f.name):
            try:
                log=_safe_read(f,MAX_LOG_BYTES)
                if _SECRET_PATTERN.search(log.decode("utf8",errors="replace")):
                    omitted.append({"name":f.name,"reason":"POSSIBLE_SECRET"})
                else:
                    blobs["diagnostics/"+f.name]=log
            except (RuntimeError,OSError):
                omitted.append({"name":f.name,"reason":"UNSAFE_OR_OVERSIZE"})
    manifest={
        "schema":"ZIMAGE_P25_LOAD_ONLY_EXPORT_V1",
        "status":"P25_LOAD_ONLY_EVIDENCE_PACKAGED",
        "source_sha":source_sha,
        "inference_fingerprint":inference_fingerprint,
        "mode":mode,
        "images_generated":0,
        "archive_verified_sha256":True,
        "potential_page_cache_bias":True,
        "gpu_speedup_claimed":False,
        "omitted_diagnostics":omitted,
        "files":{name:{"sha256":hashlib.sha256(b).hexdigest(),"bytes":len(b)}
                 for name,b in blobs.items()},
    }
    tmp_path=None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=".p25-evidence-",suffix=".tmp.zip",dir=root,delete=False
        ) as tmp:
            tmp_path=tmp.name
        with zipfile.ZipFile(tmp_path,"w",zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            z.writestr("acceptance.json",json.dumps(manifest,indent=2,ensure_ascii=False)+"\n")
            for name,b in blobs.items():z.writestr(name,b)
        with zipfile.ZipFile(tmp_path) as z:
            assert z.testzip() is None
            for name,item in manifest["files"].items():
                c=z.read(name)
                if len(c)!=item["bytes"] or hashlib.sha256(c).hexdigest()!=item["sha256"]:
                    raise RuntimeError("P25_EVIDENCE_INTEGRITY_FAILED")
        os.replace(tmp_path,archive_path)
    finally:
        if tmp_path and os.path.exists(tmp_path):os.unlink(tmp_path)
    h=hashlib.sha256()
    with archive_path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024**2),b""):h.update(chunk)
    return {
        "status":manifest["status"],
        "mode":mode,
        "archive_path":str(archive_path),
        "sha256":h.hexdigest(),
        "bytes":archive_path.stat().st_size,
        "diagnostics_included":len(blobs)-1,
        "diagnostics_omitted":omitted,
        "gpu_speedup_claimed":False,
    }

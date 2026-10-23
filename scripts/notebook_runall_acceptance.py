#!/usr/bin/env python3
"""Offline, CPU-only acceptance evidence for Kaggle notebook-native GPU images.

This module never starts a worker or fabricates an image. It audits existing
GPU worker output after notebook steps 04–06 complete, and creates a portable
ZIP with verified PNGs, JSON manifest, and bounded diagnostics.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import struct
import tempfile
import zipfile

MAX_IMAGE_BYTES = 40 * 1024**2
MAX_DIAGNOSTIC_BYTES = 6 * 1024**2
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
LOG_PATTERN = re.compile(
    r"(?:encoder\.log|gguf-prefetch-[0-9TZ]+\.(?:json|log)|worker-[01](?:-retry-[a-zA-Z0-9_-]+)?\.log|"
    r"encoder-resources-[0-9TZ]+\.jsonl|"
    r"gguf-source-selection-[0-9A-Za-zTZ_-]+\.json|"
    r"startup-resources-[0-9A-Za-zTZ_-]+\.jsonl|"
    r"encoder-timing\.json)$"
)
PROHIBITED_LOG_PATTERNS = re.compile(
    r"(?:authorization\s*:|bearer\s+\S+|api[_-]?token\s*[=:]|"
    r"studio_password\s*[=:]|service_key\s*[=:]|password\s*[=:])",
    flags=re.I,
)


def _read_bounded(path: Path, limit: int) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("P23_UNSAFE_OR_MISSING_EVIDENCE: " + str(path))
    if not 0 < path.stat().st_size <= limit:
        raise RuntimeError("P23_UNEXPECTED_EVIDENCE_SIZE: " + str(path))
    with path.open("rb") as f:
        data = f.read(limit + 1)
    if len(data) > limit:
        raise RuntimeError("P23_EVIDENCE_TOO_LARGE: " + str(path))
    return data


def _valid_png(path: Path) -> tuple[bytes, str]:
    data = _read_bounded(path, MAX_IMAGE_BYTES)
    if len(data) < 33 or data[:8] != PNG_SIGNATURE:
        raise RuntimeError("P23_INVALID_PNG_SIGNATURE")
    if data[12:16] != b"IHDR" or struct.unpack(">I", data[8:12])[0] != 13:
        raise RuntimeError("P23_INVALID_PNG_IHDR")
    w, h = struct.unpack(">II", data[16:24])
    if (w, h) != (1024, 1024):
        raise RuntimeError("P23_PNG_RESOLUTION_MISMATCH")
    # Pillow is already used by the demo; the no-dependency helper verifies
    # container and dimensions while the original notebook performs full decode.
    if b"IEND" not in data[-32:]:
        raise RuntimeError("P23_INVALID_PNG_END")
    return data, hashlib.sha256(data).hexdigest()


def _fingerprint(text: str, kind: str) -> str:
    if not isinstance(text, str) or not re.fullmatch(r"[a-fA-F0-9]{" + str(64 if kind == "fp" else 40) + r"}", text):
        raise RuntimeError("P23_INVALID_" + kind.upper())
    return text.lower()


def export_runall_evidence(
    *,
    report_path: Path,
    output_zip: Path,
    source_sha: str,
    inference_fingerprint: str,
    seeds: tuple[int, int],
    prompts: tuple[str, str],
    reuse: bool,
) -> dict:
    report_path = Path(report_path)
    output_zip = Path(output_zip)
    expected_source = _fingerprint(source_sha, "sha")
    expected_fp = _fingerprint(inference_fingerprint, "fp")
    root = report_path.parent.resolve(strict=True)
    if report_path.is_symlink() or report_path.name != "report.json":
        raise RuntimeError("P23_UNTRUSTED_REPORT")
    if not output_zip.is_absolute() or output_zip.resolve(strict=False).parent != root:
        raise RuntimeError("P23_ZIP_MUST_SHARE_REPORT_ROOT")
    if output_zip.is_symlink() or output_zip.name != "p23-runall-acceptance.zip":
        raise RuntimeError("P23_UNSAFE_OUTPUT_ZIP")
    body = _read_bounded(report_path, 1024**2)
    report = json.loads(body)
    if report.get("status") != "DUAL_GPU_NOTEBOOK_RENDER_VERIFIED":
        raise RuntimeError("P23_GPU_RENDER_NOT_VERIFIED")
    if report.get("source_sha", "").lower() != expected_source:
        raise RuntimeError("P23_SOURCE_SHA_MISMATCH")
    if report.get("inference_fingerprint", "").lower() != expected_fp:
        raise RuntimeError("P23_INFERENCE_FINGERPRINT_MISMATCH")
    if not isinstance(report.get("images"), list) or len(report["images"]) != 2:
        raise RuntimeError("P23_EXPECTED_TWO_GPU_IMAGES")
    if set(item.get("gpu") for item in report["images"]) != {0, 1}:
        raise RuntimeError("P23_GPU_DISTRIBUTION_INVALID")
    if report.get("encoder_gpu") != 0:
        raise RuntimeError("P23_ENCODER_GPU_INVALID")
    if not isinstance(reuse, bool):
        raise RuntimeError("P23_REUSE_FLAG_INVALID")

    img_blobs = {}
    verified = []
    for item in sorted(report["images"], key=lambda x: x["gpu"]):
        i = item["gpu"]
        if item.get("seed") != seeds[i] or item.get("prompt") != prompts[i]:
            raise RuntimeError("P23_PROMPT_OR_SEED_MISMATCH")
        if not isinstance(item.get("pid"), int) or item["pid"] <= 0:
            raise RuntimeError("P23_INVALID_WORKER_PID")
        path = Path(item["file"])
        if not path.is_absolute() or path.is_symlink() or path.parent.resolve() != root:
            raise RuntimeError("P23_IMAGE_PATH_OUTSIDE_OUTPUT_ROOT")
        data, digest = _valid_png(path)
        if digest != item.get("sha256"):
            raise RuntimeError("P23_IMAGE_SHA256_MISMATCH")
        arcname = f"images/gpu{i}-1024x1024.png"
        img_blobs[arcname] = data
        verified.append({
            "gpu": i, "sha256": digest, "bytes": len(data),
            "image_archive_path": arcname, "generation_seconds": item.get("generation_seconds"),
            "worker_pid": item["pid"], "seed": seeds[i],
        })
    if verified[0]["sha256"] == verified[1]["sha256"]:
        raise RuntimeError("P23_DUPLICATE_IMAGE_OUTPUT")

    manifest = {
        "schema": "ZIMAGE_P23_NOTEBOOK_NATIVE_GPU_RUNALL_EVIDENCE_V1",
        "status": "P23_TWO_GPU_IMAGES_SHA256_VERIFIED",
        "source_sha": expected_source,
        "inference_fingerprint": expected_fp,
        "execution": "VERIFIED_REUSE" if reuse else "GENERATED_IN_CURRENT_KERNEL_RUN",
        "new_gpu_images_generated_during_this_cell": False,
        "new_gpu_images_generated_during_this_run": not reuse,
        "source_report_status": report["status"],
        "encoder_gpu": 0,
        "gpu_count_verified": 2,
        "images": verified,
        "encoding_seconds": report.get("encoding_seconds"),
        "model_startup_seconds": report.get("model_startup_seconds"),
        "model_startup_seconds_per_gpu": report.get("model_startup_seconds_per_gpu"),
        "parallel_inference_wall_seconds": report.get("parallel_inference_wall_seconds"),
        "gguf_source_selection": report.get("gguf_source_selection"),
        "note": "Report is generated only after the actual notebook verifies two independent model workers and two 1024x1024 PNG files. Reuse is marked explicitly.",
    }
    files: dict[str, bytes] = {"report.json": body}
    files.update(img_blobs)
    omitted = []
    for f in sorted(root.iterdir()):
        if LOG_PATTERN.fullmatch(f.name):
            try:
                data = _read_bounded(f, MAX_DIAGNOSTIC_BYTES)
                if PROHIBITED_LOG_PATTERNS.search(data.decode("utf-8", errors="replace")):
                    omitted.append({"file": f.name, "reason": "POSSIBLE_SECRET"})
                    continue
                files["diagnostics/" + f.name] = data
            except (OSError, RuntimeError):
                omitted.append({"file": f.name, "reason": "UNSAFE_OR_OVERSIZED"})
    manifest["diagnostics_omitted"] = omitted
    manifest["file_hashes"] = {
        name: {"sha256": hashlib.sha256(contents).hexdigest(), "bytes": len(contents)}
        for name, contents in files.items()
    }
    final = json.dumps(manifest, indent=2, ensure_ascii=False).encode() + b"\n"
    tmp_name = ""
    try:
        with tempfile.NamedTemporaryFile(dir=root, prefix=".p23-evidence-", suffix=".zip.tmp", delete=False) as tmp:
            tmp_name = tmp.name
        with zipfile.ZipFile(tmp_name, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as package:
            package.writestr("acceptance.json", final)
            for name, contents in files.items():
                package.writestr(name, contents)
        with zipfile.ZipFile(tmp_name, "r") as package:
            if package.testzip() is not None:
                raise RuntimeError("P23_ARCHIVE_CRC_FAILED")
            for name, item in manifest["file_hashes"].items():
                saved = package.read(name)
                if len(saved) != item["bytes"] or hashlib.sha256(saved).hexdigest() != item["sha256"]:
                    raise RuntimeError("P23_ARCHIVE_INTEGRITY_FAILED")
        os.replace(tmp_name, output_zip)
    finally:
        if tmp_name and os.path.exists(tmp_name):
            os.unlink(tmp_name)
    return {
        "status": manifest["status"],
        "execution": manifest["execution"],
        "bundle": str(output_zip),
        "bundle_bytes": output_zip.stat().st_size,
        "bundle_sha256": hashlib.sha256(output_zip.read_bytes()).hexdigest(),
        "gpu_images": len(verified),
        "included_diagnostics": len(files) - 3,
        "omitted_diagnostics": omitted,
    }

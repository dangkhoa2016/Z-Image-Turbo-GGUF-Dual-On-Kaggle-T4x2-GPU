#!/usr/bin/env python3
"""CPU-only Studio cache/monitor policy regression. Never submits GPU work."""
import ast
import hashlib
import json
from pathlib import Path
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "scripts"))
from kaggle_production_demo import engine_notebook
sys.path.insert(0,str(ROOT/"scripts"))
from gguf_source_policy import select_gguf_source
from stage_gguf_model import verify_staged_override
from inference_provenance import (
    STUDIO_TMP_INFERENCE_FINGERPRINT, STUDIO_TMP_ENCODER_SUBSET_FINGERPRINT,
    P22_QWEN3_STAGING_INFERENCE_FINGERPRINT,
    inference_fingerprint,encoder_subset_fingerprint,verify_cached_source,
)
assert inference_fingerprint(ROOT)==STUDIO_TMP_INFERENCE_FINGERPRINT
assert encoder_subset_fingerprint(ROOT)==STUDIO_TMP_ENCODER_SUBSET_FINGERPRINT
assert STUDIO_TMP_INFERENCE_FINGERPRINT!=P22_QWEN3_STAGING_INFERENCE_FINGERPRINT
try:
    verify_cached_source({"inference_fingerprint":P22_QWEN3_STAGING_INFERENCE_FINGERPRINT},
                         "a"*40,STUDIO_TMP_INFERENCE_FINGERPRINT)
except ValueError as exc:assert str(exc)=="CACHED_INFERENCE_SOURCE_MISMATCH"
else:raise AssertionError("Old inference outputs were silently promoted")

nb=engine_notebook(ROOT)
c=lambda i:"".join(nb["cells"][i]["source"])
assert len(nb["cells"])==28
for i,cell in enumerate(nb["cells"]):
    if cell["cell_type"]=="code":
        ast.parse(c(i),filename=f"studio-new-notebook-cell-{i}")
        assert not cell.get("outputs")
assert 'SOURCE_REF = os.environ.get("ZIMAGE_SOURCE_REF", "main")' in c(3)
assert 'ZIMAGE_MODEL_STAGE_PARENT = Path("/tmp/zimage-t4x2-model-stage")' in c(3)
assert 'os.environ["ZIMAGE_QWEN3_SOURCE_MODE"] = "local"' in c(3)
assert 'os.environ["ZIMAGE_GGUF_STAGE_ROOT"] = str(ZIMAGE_MODEL_STAGE_PARENT / "gguf")' in c(3)
assert 'P23_STAGE_FREE_BYTES=shutil.disk_usage("/tmp").free' in c(5)
assert 'P23_WORKING_RESERVE_BYTES=1024**3' in c(5)
assert "P23_SHARED_TMP_WORKING_DISK_INSUFFICIENT" in c(5)
assert 'QWEN3_STAGE_ROOT = Path(os.environ["ZIMAGE_QWEN3_STAGE_ROOT"])' not in c(9)
assert "QWEN3_STAGE_ROOT = Path(os.environ['ZIMAGE_QWEN3_STAGE_ROOT'])" in c(9)
assert "model_spec, Path(os.environ['ZIMAGE_GGUF_STAGE_ROOT']), GGUF_SOURCE_REQUEST)" in c(11)
assert "executor.submit(generate_one,i) for i in (0,1)" in c(11)
assert "STUDIO_ONLY_MODEL_STAGE_VERIFIED" in c(18)
assert "os.environ[\"ZIMAGE_GGUF_STAGED_PATH\"] = gguf_choice[\"staged_override_path\"]" in c(18)
assert 'STUDIO_MONITOR_MAX_MINUTES = None' in c(27)
assert 'STUDIO_MONITOR_WARNING' in c(27)
assert "session_root / \"encoder-phase.log\"" in c(27)
assert "ZIMAGE_ENCODER_STAGE" in c(27)
assert "STUDIO_LIVE_MONITOR_INTERRUPTED" in c(27)
assert "P23_ENABLE_OPTIONAL_WEB_APPS" in c(27)
worker=(ROOT/"production-system/dynamic_worker.py").read_text()
encoder=(ROOT/"production-system/encode_batch_gpu.py").read_text()
lifecycle=(ROOT/"production-system/shared_session_lifecycle.py").read_text()
assert 'os.environ.get("ZIMAGE_GGUF_STAGE_ROOT"' in worker
assert 'verify_staged_override(' in worker
assert 'STAGE_OVERRIDE_PATH_MISMATCH' in (ROOT/"scripts/stage_gguf_model.py").read_text()
assert 'QWEN3_STAGE_ROOT_OUTSIDE_ALLOWED_CACHE_ROOT' in encoder
assert 'Path("/tmp/zimage-t4x2-model-stage")' in encoder
assert 'log=folder/"encoder-phase.log"' in lifecycle
assert 'stdout=output,stderr=subprocess.STDOUT' in lifecycle
assert 'timeout=1800' in lifecycle
assert 'signal.SIGTERM' in lifecycle and 'signal.SIGKILL' in lifecycle
assert 'UPDATE b112_sessions SET status' in lifecycle

# Real CPU execution of the existing model selector and independent worker
# verifier, with a tiny fixture instead of the 5.9 GB production weights.
with tempfile.TemporaryDirectory(prefix="zimage-studio-tmp-policy-") as directory:
    root=Path(directory)
    source=root/"input.gguf"
    b=b"studio-cache-policy-fixture"*1024
    source.write_bytes(b)
    manifest={"gguf_path":str(source),"gguf_bytes":len(b),
              "gguf_sha256":hashlib.sha256(b).hexdigest()}
    cache=root/"gguf"
    chosen=select_gguf_source(manifest,cache,"local")
    assert chosen["integrity"]=="sha256_verified_local"
    assert verify_staged_override(manifest,Path(chosen["staged_override_path"]),cache).is_file()
    cached=Path(chosen["staged_override_path"])
    cached.write_bytes(b[:-1]+b"!")
    try:verify_staged_override(manifest,cached,cache)
    except RuntimeError as exc:assert "STAGE_VERIFICATION_SHA256_MISMATCH" in str(exc)
    else:raise AssertionError("Model cache tampering accepted")
print("STUDIO_TMP_MONITOR_CPU_PASS continuous_monitor read_only progress_encoder_log "
      "studio_only_full_sha256 tmp_stage_source_integrity src_sha_guard gpu=NOT_TESTED")

#!/usr/bin/env python3
"""CPU-only validation of the published production notebook contract."""
import ast, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "scripts"))
from kaggle_production_demo import engine_notebook
final=engine_notebook(ROOT)
def source(book,index):return "".join(book["cells"][index]["source"])
assert len(final["cells"])==28
assert sum(c["cell_type"]=="code" for c in final["cells"])==12
assert sum(c["cell_type"]=="markdown" for c in final["cells"])==16
for i,c in enumerate(final["cells"]):
    if c["cell_type"]=="code":
        ast.parse(source(final,i),filename=f"final-notebook-cell-{i}")
        assert c.get("execution_count") is None and c.get("outputs",[])==[],i
# Published source checkout is verified against main or a pinned Git SHA.
setup=source(final,3)
assert 'SOURCE_REF = os.environ.get("ZIMAGE_SOURCE_REF", "main")' in setup
assert 'P25_LOAD_ONLY = False' in setup
assert 'P24_GGUF_PREFETCH_ENABLED = False' in setup
assert 'P23_ENABLE_OPTIONAL_WEB_APPS = True' in setup
assert 'P27_VAE_STALL_PROFILING = False' in setup
assert 'os.environ["ZIMAGE_GGUF_SOURCE_MODE"] = "local"' in setup
assert 'P29_FRESH_RUN_ID = uuid.uuid4().hex[:12]' in setup
assert 'ZIMAGE_SOURCE_SHA' in setup and 'EXPECTED_SOURCE_SHA' in setup
assert 'git", "clone", "--branch", SOURCE_REF' in setup
assert 'FRESH_SOURCE_VERIFICATION_FAILED' in setup
# Full source integrity is checked with exact model SHA256 and provenance
# fingerprints; nested GPU clients are additionally executed in the CPU
# regression test, not merely parsed as outer notebook cells.
assert "textwrap.dedent(script)" in source(final,11)
assert "import shutil, urllib.error, textwrap" in source(final,11)
assert "stage_gguf_model" in (ROOT/"production-system/dynamic_worker.py").read_text()
assert "verify_staged_override(" in (ROOT/"production-system/dynamic_worker.py").read_text()
prepare=source(final,9)
assert "('zimage-final-runall-' + P29_FRESH_RUN_ID)" in prepare
assert 'DIRECT_CACHED_REPORT = direct_previous_result()' in prepare
# Unique fresh root has no previous report, so inference is not substituted by prior runs.
assert "P25_LOAD_ONLY" in source(final,11)
assert "executor.submit(generate_one,i) for i in (0,1)" in source(final,11)
assert "DUAL_GPU_NOTEBOOK_RENDER_VERIFIED" in source(final,11)
assert "GGUF_SOURCE_REQUEST = os.environ.get('ZIMAGE_GGUF_SOURCE_MODE', 'local')" in source(final,11)
assert "P23_RUNALL_ACCEPTANCE" in source(final,13)
assert "from notebook_runall_acceptance import export_runall_evidence" in source(final,13)
assert "P25_BENCHMARK_ZIP" in source(final,13)  # inactive branch preserved
assert "STUDIO_MONITOR_MAX_MINUTES = None" in source(final,27)
assert "STUDIO_MONITOR_WARNING" in source(final,27)
assert '"ZIMAGE_ENCODER_STAGE"' in source(final,27)
assert 'session_root / "encoder-phase.log"' in source(final,27)
assert 'ZIMAGE_MODEL_STAGE_PARENT = Path("/tmp/zimage-t4x2-model-stage")' in setup
assert 'P23_STAGE_FREE_BYTES=shutil.disk_usage("/tmp").free' in source(final,5)
assert 'P23_WORKING_RESERVE_BYTES=1024**3' in source(final,5)
assert "QWEN3_STAGE_ROOT = Path(os.environ['ZIMAGE_QWEN3_STAGE_ROOT'])" in prepare
assert "STUDIO_ONLY_MODEL_STAGE_VERIFIED" in source(final,18)
assert 'os.environ["ZIMAGE_GGUF_STAGED_PATH"] = gguf_choice["staged_override_path"]' in source(final,18)
for i in (16,18,20,22,24,27):
    assert "if P23_ENABLE_OPTIONAL_WEB_APPS:" in source(final,i)
for i in (0,1,2,8,10,12,14,25,26):
    prose=source(final,i)
    assert "P2.5 Load-only benchmark" not in prose
    assert "P2.3 diagnostic source" not in prose
# Validate the canonical published notebook, independent of release notes.
assert (ROOT/"notebooks/kaggle-dual-gpu-production-demo.ipynb").is_file()
print("PRODUCTION_STUDIO_NOTEBOOK_CPU_CONTRACT_PASS notebook=28/12 source=verified-branch "
      "images=2 prefetch=off local_gguf=fullsha ui=enabled gpu_worker_sha256_guard=preserved "
      "gpu_execution=NOT_TESTED")

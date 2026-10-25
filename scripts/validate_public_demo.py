#!/usr/bin/env python3
"""Public demo documentation/notebook agreement, offline and CPU-only."""
import ast
import hashlib
import json
from pathlib import Path
import re
import urllib.parse

ROOT=Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "scripts"))
from kaggle_production_demo import engine_notebook
NOTEBOOK=ROOT/"notebooks/kaggle-dual-gpu-production-demo.ipynb"
THUMB_SHA256={
 "010":"5bc8b19321640ef0e7404d7613c0687794a1d62c9e14134543bb94f8244d3a29",
 "011":"b6f57531c6059e0327285f092f49107c0634c717accfe6b967cdba7753a05be5",
 "013":"2a28c5cadd3b81540808bfcc10bb2caf496f19e799f5c35d29daf2b09de10017",
 "027":"8e238080e6baa15377d31b99e708ccb01522fc695b080c2ebaa3a36351a8f821",
}
def source(cell):
 return "".join(cell.get("source",[]))
def assert_relative_links(doc):
 for url in re.findall(r"(?<!!)\[[^\]]+\]\(([^)]+)\)",doc):
  path=urllib.parse.unquote(url.partition("#")[0])
  if path and not urllib.parse.urlsplit(path).scheme and not path.startswith("//"):
   assert (ROOT/path).is_file(),("Broken relative Markdown link",path)
def validate():
 from markdown_language_switch import validate_docs_language_switches
 language_audit=validate_docs_language_switches(ROOT/'docs',expected_pairs=11)
 assert language_audit=={'pairs':11,'documents':22}
 public=json.loads(NOTEBOOK.read_text(encoding="utf-8"))
 assert len(public["cells"])==28
 assert sum(c["cell_type"]=="code" for c in public["cells"])==12
 assert sum(c["cell_type"]=="markdown" for c in public["cells"])==16
 for i,cell in enumerate(public["cells"]):
  if cell["cell_type"]!="code":continue
  user_code=source(cell)
  ast.parse(user_code,filename=f"public-notebook-cell-{i}")
  assert len(user_code.splitlines())<=42,("Public notebook code too long",i)
  assert not cell.get("outputs") and cell.get("execution_count") is None
  assert "P25_" not in user_code and "P23_" not in user_code
 assert "from kaggle_production_demo import ProductionDemo" in source(public["cells"][3])
 assert 'branch = os.environ.get("ZIMAGE_SOURCE_REF", "main")' in source(public["cells"][3])
 assert 'PINNED_RELEASE_SOURCE_SHA' not in source(public["cells"][3])
 assert 'revision = os.environ.get("ZIMAGE_SOURCE_SHA", remote).strip().lower()' in source(public["cells"][3])
 assert 'git", "ls-remote", "--heads", repo, branch' in source(public["cells"][3])
 assert 'By default, the notebook resolves the selected GitHub' in source(public["cells"][2])
 for i,name in zip((5,7,9,11,13,16,18,20,22,24,27),
                   ("inputs","dependencies","encode","generate","verify",
                    "studio","consumer","galleries","gallery_links","studio_link","monitor")):
  assert source(public["cells"][i]).strip()=="demo."+name+"()"
 data=engine_notebook(ROOT)
 cells=data["cells"]
 code=[source(c) for c in cells if c["cell_type"]=="code"]
 markdown=[source(c) for c in cells if c["cell_type"]=="markdown"]
 assert len(cells)==28 and len(code)==12 and len(markdown)==16
 for i,s in enumerate(code):
  ast.parse(s,filename="notebook code cell "+str(i+1))
  assert data["cells"] is not None
 assert all(c.get("outputs",[])==[] and c.get("execution_count") is None
            for c in cells if c["cell_type"]=="code"),"Template includes run outputs"
 checkout=source(cells[3]); direct=source(cells[9])
 assert sorted(p.name for p in (ROOT/"notebooks").glob("*.ipynb")) == ["kaggle-dual-gpu-production-demo.ipynb"], "Only the canonical notebook may be published"
 assert 'ZIMAGE_MODEL_STAGE_PARENT = Path("/tmp/zimage-t4x2-model-stage")' in checkout
 assert 'P23_STAGE_FREE_BYTES=shutil.disk_usage("/tmp").free' in source(cells[5])
 assert 'STUDIO_ONLY_MODEL_STAGE_VERIFIED' in source(cells[18])
 assert 'textwrap.dedent(script)' in source(cells[11])
 assert 'session_root / "encoder-phase.log"' in source(cells[27])
 worker=source(cells[11]); display=source(cells[13])
 cloudflared=source(cells[22])
 assert 'gallery_public_https_status = {}' in cloudflared
 assert 'except (urllib.error.URLError, TimeoutError, OSError) as err:' in cloudflared
 assert 'GALLERY_PUBLIC_HTTPS_PROBE_PENDING' in cloudflared
 assert 'PENDING_BROWSER_VERIFICATION' in cloudflared
 assert 'GALLERY_CROSS_DOMAIN_NAV_PUBLIC_CONTENT_INVALID' in cloudflared
 assert 'PUBLIC_GALLERY_HTTPS_CHECK_FAILED' not in cloudflared
 assert 'SOURCE_REF = os.environ.get("ZIMAGE_SOURCE_REF", "main")' in checkout
 assert 'os.environ.get("ZIMAGE_SOURCE_SHA", "")' in checkout
 assert 'git", "clone", "--branch", SOURCE_REF, REPO_URL' in checkout
 assert 'if SOURCE_SHA:' in checkout and 'EXPECTED_SOURCE_SHA' in checkout
 assert 'git", "ls-remote", "--heads", REPO_URL, SOURCE_REF' in checkout
 assert 'target = EXPECTED_SOURCE_SHA' in checkout
 assert 'PREVIOUS_SOURCE_PRESERVED' in checkout
 assert 'SOURCE_CLONED_FRESH' in checkout
 assert 'validated_encoder_recovery' in direct
 assert 'GPU0_ENCODER_RECOVERED' in direct
 assert 'INCOMPLETE_RUN_PRESERVED' in direct
 assert 'NEW_ISOLATED_OUTPUT_ROOT' in direct
 assert 'DIRECT_REUSE_ENCODER' in direct
 assert 'PARTIAL_GPU_PNG_REQUIRES_RECONCILIATION' in direct
 assert 'log_suffix' in worker and 'worker-{i}-retry-' in worker
 assert (ROOT/'scripts/gguf_startup_diagnostics.py').is_file()
 assert 'gguf_startup_diagnostics import read_process' in worker
 assert "'run'," in worker and 'GGUF_PYTHON_STACK_DUMP_REQUESTED' in worker
 assert 'WORKER_PROC_RESOURCE' in worker and 'GGUF_IO_SAMPLE' in worker
 assert 'STARTUP_PER_GPU_LIMIT_SECONDS = 1200' in worker
 assert (ROOT/'scripts/stage_gguf_model.py').is_file()
 assert (ROOT/'scripts/gguf_source_policy.py').is_file()
 assert 'gguf_choice = select_gguf_source(' in worker
 assert (ROOT/'production-system/test_gguf_source_policy.py').is_file()
 assert "'gguf_source_mode':gguf_choice['effective_mode']" in worker
 assert "os.environ.get('ZIMAGE_GGUF_SOURCE_MODE', 'local')" in worker
 assert "'gguf_source_selection':gguf_choice" in worker
 assert "env.pop('ZIMAGE_GGUF_STAGED_PATH', None)" in worker
 assert "env['ZIMAGE_GGUF_STAGED_PATH']=gguf_choice['staged_override_path']" in worker
 assert 'GGUF_LOCAL_IO_SAMPLE' in worker
 assert 'encoder_subset_fingerprint(PROJECT)' in direct
 assert 'ZIMAGE_ENCODER_STAGE ' in direct
 assert 'stage='+chr(39)+'+last_stage' in direct
 assert (ROOT/'production-system/test_encoder_stage_diagnostics.py').is_file()
 assert (ROOT/'scripts/qwen3_encoder_diagnostics.py').is_file()
 assert (ROOT/'production-system/test_encoder_io_observer.py').is_file()
 assert 'encoder_child_snapshot(encoder.pid)' in direct
 assert 'encoder-resources-' in direct
 assert 'QWEN3_WEIGHT_STORAGE_SAMPLE' in direct
 assert (ROOT/'production-system/test_gguf_staging.py').is_file()
 assert 'executor.submit(generate_one,i) for i in (0,1)' in worker
 assert "from inference_provenance import inference_fingerprint, verify_cached_source" in direct
 assert "DIRECT_IMAGES_WERE_REUSED = DIRECT_CACHED_REPORT is not None" in direct
 assert "image['seed'] == DIRECT_SEEDS[index]" in direct
 assert "image['prompt'] == DIRECT_PROMPTS[index]" in direct
 assert "hashlib.sha256(p.read_bytes()).hexdigest() == image['sha256']" in direct
 assert "'inference_fingerprint':DIRECT_INFERENCE_FINGERPRINT" in worker
 assert "DIRECT_IMAGES_WERE_REUSED else 'GENERATED_IN_CURRENT_RUN'" in display
 assert 'from notebook_runall_acceptance import export_runall_evidence' in display
 assert 'P23_RUNALL_ACCEPTANCE' in display
 assert 'P23_ENABLE_OPTIONAL_WEB_APPS = True' in checkout
 assert 'P23_FRESH_DISK_PREFLIGHT' in source(cells[5])
 assert 'P23_DISK_RESERVE_BYTES=3*1024**3' in source(cells[5])
 assert 'GGUF_STAGE_BYTES=model.stat().st_size if GGUF_P23_REQUESTED=="local" else 0' in source(cells[5])

 assert (ROOT/'scripts/notebook_runall_acceptance.py').is_file()
 for index in (16,18,20,22,24,27):
  optional=source(cells[index])
  assert 'if P23_ENABLE_OPTIONAL_WEB_APPS:' in optional
  assert 'P23_OPTIONAL_UI_SKIPPED' in optional
 assert 'STUDIO_MONITOR_MAX_MINUTES = None' in source(cells[27])
 assert 'P24_GGUF_PREFETCH_ENABLED = False' in checkout
 assert 'P25_LOAD_ONLY = False' in checkout
 assert 'P27_VAE_STALL_PROFILING = False' in checkout
 assert 'from vae_startup_probe import sample_vae_startup, stack_request_allowed' in worker
 assert 'P27_VAE_STACK_DUMP_REQUESTED' in worker
 assert (ROOT/'scripts/vae_startup_probe.py').is_file()
 assert (ROOT/'production-system/test_vae_startup_probe.py').is_file()

 assert "assert P25_LOAD_ONLY is False" in checkout
 assert 'P25_TWO_GPU_MODELS_READY_NO_IMAGE_GENERATION' in worker
 assert 'from loadonly_evidence import export_loadonly_evidence' in display
 assert (ROOT/'scripts/loadonly_evidence.py').is_file()
 assert (ROOT/'production-system/test_loadonly_evidence.py').is_file()

 assert 'P24_GGUF_PREFETCH_STARTED' in direct
 assert 'P24_GGUF_PREFETCH_COMPLETED' in worker
 assert 'P24_GGUF_PREFETCH_FAILED: worker startup BLOCKED' in worker
 assert (ROOT/'scripts/gguf_prefetch.py').is_file()


 assert 'CLOUDFLARED_VERSION = "2026.10.2"' in cloudflared
 assert 'CLOUDFLARED_SHA256 = "35fbdd2beb378436c7da377d7358cea8e33f9c94a6705d1d8036bf9b0d6d8005"' in cloudflared
 assert "verify_cloudflared_digest(temporary)" in cloudflared
 for path in (ROOT/"README.md",ROOT/"README.vi.md"):
  text=path.read_text(encoding="utf-8")
  assert "28 cell" in text.lower(),(path,"notebook cell count")
  assert "ZIMAGE_SOURCE_SHA" in text
  assert "Studio" in text and "1024" in text
  assert ":18789" in text and ":18881" in text and ":18882" in text
  assert "notebooks/kaggle-dual-gpu-production-demo.ipynb" in text
  assert "18 cell" not in text
  assert "one static server" not in text
  assert "một webserver" not in text
  assert_relative_links(text)
 for path in (ROOT/"docs/kaggle.md",ROOT/"docs/kaggle.vi.md"):
  text=path.read_text(encoding="utf-8")
  assert "28" in text and "ZIMAGE_SOURCE_SHA" in text
  assert "Studio" in text and "GPU" in text
 for key,digest in THUMB_SHA256.items():
  f=ROOT/"assets/showcase"/("pqt_v1_"+key+".webp")
  blob=f.read_bytes()
  assert blob[:4]==b"RIFF" and blob[8:12]==b"WEBP"
  assert hashlib.sha256(blob).hexdigest()==digest,(f,"Asset integrity")
 print("PUBLIC_NOTEBOOK_README_CONTRACT_PASS cells=28 code=12 docs=EN+VI samples=4")
if __name__=="__main__":
 validate()
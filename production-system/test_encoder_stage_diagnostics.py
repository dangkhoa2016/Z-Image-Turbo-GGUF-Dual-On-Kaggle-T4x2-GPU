"""CPU-only checks: structured encoder stages, live stdout, and no model operations."""
from pathlib import Path
import ast
import contextlib
import io
import json
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "scripts"))
from kaggle_production_demo import engine_notebook
encoder=ROOT/"production-system/encode_batch_gpu.py"
controller=ROOT/"production-system/phase_controller.py"
tree=ast.parse(encoder.read_text())
functions={node.name:node for node in tree.body if isinstance(node,ast.FunctionDef)}
assert "encoder_stage" in functions and "main" in functions
lines=encoder.read_text()
milestones=(
 "TORCH_IMPORT_BEGIN","TORCH_AND_MODELS_IMPORTED",
 "TOKENIZER_LOAD_BEGIN","TOKENIZER_LOAD_FINISHED",
 "QWEN3_WEIGHTS_LOAD_BEGIN","QWEN3_WEIGHTS_LOAD_FINISHED",
 "QWEN3_CUDA_TRANSFER_BEGIN","QWEN3_CUDA_TRANSFER_FINISHED",
 "PROMPT_ENCODE_BEGIN","PROMPT_ENCODE_FINISHED",
 "EMBEDDING_SAVE_BEGIN","EMBEDDING_SAVE_VERIFIED",
 "ENCODER_BATCH_FINISHED",
)
for marker in milestones:
 assert lines.count('"'+marker+'"')==1,marker
assert lines.index('QWEN3_WEIGHTS_LOAD_BEGIN')<lines.index('QWEN3_WEIGHTS_LOAD_FINISHED')
assert lines.index('PROMPT_ENCODE_BEGIN')<lines.index('PROMPT_ENCODE_FINISHED')
assert lines.index('EMBEDDING_SAVE_BEGIN')<lines.index('EMBEDDING_SAVE_VERIFIED')
assert 'torch.cuda.synchronize()' not in ast.get_source_segment(lines,functions['encoder_stage'])
assert 'torch' not in ast.get_source_segment(lines,functions['encoder_stage'])
import pathlib
import subprocess
import json as json_module
namespace={"Path":pathlib.Path,"json":json_module,"time":time}
exec(compile(ast.Module(body=[functions["encoder_stage"]],type_ignores=[]),
             str(encoder),"exec"),namespace)
namespace["_ENCODER_STARTED"]=time.monotonic()-3.0
buf=io.StringIO()
with contextlib.redirect_stdout(buf):
 namespace["encoder_stage"]("TEST_CPU_STAGE",item=1)
output=buf.getvalue().strip()
assert output.startswith("ZIMAGE_ENCODER_STAGE ")
event=json.loads(output.split(" ",1)[1])
assert event["stage"]=="TEST_CPU_STAGE" and event["item"]==1
assert 3.0<=event["elapsed_seconds"]<10.0
assert event["rss_kib"] is None or event["rss_kib"]>0
assert event.get("read_bytes",0)>=0

src=controller.read_text()
assert 'if args.mode=="gpu0":' in src
assert 'stdout=sys.stdout,stderr=subprocess.STDOUT' in src
assert 'capture_output=True,text=True,timeout=3600,check=False' in src
assert '"cpu-mock"' in src
notebook=engine_notebook(ROOT)
assert len(notebook["cells"])==28
s="".join(notebook["cells"][9]["source"])
assert "ZIMAGE_ENCODER_STAGE " in s
assert "stage='+last_stage" in s
assert "max(0,end-32768)" in s
assert "DIRECT_REUSE_ENCODER" in s
assert "PREDIAGNOSTIC_STAGED_INFERENCE_FINGERPRINT" in s
print("QWEN3_STAGE_TELEMETRY_CPU_PASS no_gpu_no_model_load stage_json stdout_guard notebook_contract")

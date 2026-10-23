#!/usr/bin/env python3
"""CPU-only nested Python -c client smoke test; NO model/GPU used."""
import ast
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap

ROOT=Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "scripts"))
from kaggle_production_demo import engine_notebook
nb=engine_notebook(ROOT)
cell="".join(nb["cells"][11]["source"])
assert "import shutil, urllib.error, textwrap" in cell
assert "cmd = [sys.executable,'-c',textwrap.dedent(script)," in cell

root_ast=ast.parse(cell,filename="final Step 05")
fn=next(node for node in ast.walk(root_ast)
        if isinstance(node,ast.FunctionDef) and node.name=="generate_one")
script_node=next(node.value for node in fn.body if isinstance(node,ast.Assign)
                 and any(isinstance(t,ast.Name) and t.id=="script" for t in node.targets))
raw_script=ast.literal_eval(script_node)
try:
    compile(raw_script,"<original worker client>","exec")
except IndentationError as error:
    assert "unexpected indent" in str(error)
else:
    raise AssertionError("Original buggy client should have failed before dedent")
fixed_script=textwrap.dedent(raw_script)
compile(fixed_script,"<verified worker client>","exec")
assert fixed_script.splitlines()[1]=="import json,sys"

with tempfile.TemporaryDirectory(prefix="zimage-fresh-client-cpu-") as tmp:
    tmp=Path(tmp)
    # Synthetic modules and manifest: do not import project GPU/worker/model runtime.
    (tmp/"embedding_registry.py").write_text(
        "class Registry:\n"
        " def __init__(self, db, cache, identity):\n"
        "  assert identity['kind']=='synthetic'\n"
        " def key(self, prompt):return 'key:'+prompt\n")
    (tmp/"worker_adapter.py").write_text(
        "class WorkerAdapter:\n"
        " def __init__(self, worker, url, output, timeout):\n"
        "  assert url==f'http://127.0.0.1:{12340+worker}'\n"
        "  assert timeout==920\n"
        "  self.worker=worker\n"
        " def generate(self, key, seed):\n"
        "  assert key==f'key:prompt-{self.worker}'\n"
        "  assert seed==121041+self.worker\n"
        "  return {'worker_id':self.worker,'seed':seed,'key':key,'synthetic':True}\n")
    runtime=tmp/"mock_run";runtime.mkdir()
    (runtime/"cache").mkdir()
    (runtime/"registry.sqlite3").touch()
    (runtime/"prompts.json").write_text(json.dumps(["prompt-0","prompt-1"]))
    (runtime/"encoder-identity.json").write_text(json.dumps({"kind":"synthetic"}))
    (runtime/"inference-manifest.json").write_text(json.dumps({"entries":{
        "key:prompt-0":{},"key:prompt-1":{}}}))
    for gpu in (0,1):
        cp=subprocess.run(
            [sys.executable,"-c",fixed_script,
             str(tmp),str(runtime),str(tmp),str(gpu),str(121041+gpu)],
            capture_output=True,text=True,timeout=10)
        assert cp.returncode==0,(gpu,cp.stdout,cp.stderr)
        rec=json.loads(cp.stdout.strip().splitlines()[-1])
        assert rec=={"worker_id":gpu,"seed":121041+gpu,
                     "key":f"key:prompt-{gpu}","synthetic":True}
    # Fail closed: a removed registry/manifest key must not produce a success.
    (runtime/"inference-manifest.json").write_text(json.dumps({"entries":{
        "key:prompt-0":{}}}))
    bad=subprocess.run(
        [sys.executable,"-c",fixed_script,
         str(tmp),str(runtime),str(tmp),"1","121042"],
        capture_output=True,text=True,timeout=10)
    assert bad.returncode!=0 and "AssertionError" in bad.stderr
print("FINAL_RUNALL_SUBPROCESS_CLIENT_CPU_PASS dedent_real_python_c "
      "mock_gpu0_gpu1=2/2 missing_manifest_key_rejected=PASS gpu_used=NO")

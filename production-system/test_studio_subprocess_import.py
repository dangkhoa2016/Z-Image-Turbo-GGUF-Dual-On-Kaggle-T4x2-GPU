#!/usr/bin/env python3
"""CPU regression: Studio's real child Python interpreter can import the GGUF verifier."""
import ast,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"production-system"
p=ROOT/"deployment/start_persistent_gpu_consumer.py"
tree=ast.parse(p.read_text())
vals=[k.value for n in ast.walk(tree) if isinstance(n,ast.Call) for k in n.keywords if k.arg=="PYTHONPATH"]
assert len(vals)==1
e=ast.fix_missing_locations(ast.Expression(vals[0]))
paths=eval(compile(e,str(p),"eval"),{"root":SRC,"os":os})
entries=paths.split(os.pathsep)
assert len(entries)==6 and entries[-1]==str(ROOT/"scripts") and len(set(entries))==6
assert entries[0]==str(SRC/"vendor-shim")
env=os.environ.copy()
env["PYTHONPATH"]=paths
verify='import stage_gguf_model,gguf_source_policy;from pathlib import Path;import os;expected=Path(os.environ["ZIMAGE_TEST_ROOT"]);assert Path(stage_gguf_model.__file__).resolve()==expected/"scripts/stage_gguf_model.py";assert Path(gguf_source_policy.__file__).resolve()==expected/"scripts/gguf_source_policy.py";print("STUDIO_CHILD_IMPORT_PASS")'
env["ZIMAGE_TEST_ROOT"]=str(ROOT)
run=subprocess.run([sys.executable,"-c",verify],cwd=SRC,env=env,text=True,capture_output=True,timeout=40)
assert run.returncode==0,run.stdout[-1000:]+run.stderr[-1300:]
assert "STUDIO_CHILD_IMPORT_PASS" in run.stdout
print("STUDIO_CHILD_IMPORT_CONTRACT_PASS trusted_scripts_path vendor_paths_preserved gpu_unused")

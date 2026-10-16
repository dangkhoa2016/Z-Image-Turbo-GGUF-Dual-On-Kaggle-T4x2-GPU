#!/usr/bin/env python3
"""Additive B1.10 portable source+state+evidence checkpoint, no credentials or old DB."""
import hashlib,json,sqlite3,importlib.metadata as md,zipfile,tempfile,os
from pathlib import Path
root=Path("/kaggle/working/zimage-dual")
src=root/"production-system"
run=src/"gpu-integration-20261015"
out=Path("/kaggle/working/ZIMAGE-DUAL-B110-SOURCE-STATE-GPU-EVIDENCE-20261015-V2.zip")
if out.exists(): raise SystemExit("BLOCKED_ARCHIVE_EXISTS")
report=json.loads((run/"b110-real-gpu-evidence.json").read_text())
assert report["status"]=="REAL_GPU_TWO_JOB_INFERENCE_PASS" and len(report["jobs"])==2
with tempfile.TemporaryDirectory(prefix="zimage-b110-",dir="/kaggle/working") as t:
 tmp=Path(t)
 for name in ("api.sqlite3","registry.sqlite3"):
  with sqlite3.connect(str(run/name)) as source, sqlite3.connect(str(tmp/name)) as dest:
   source.backup(dest)
 files={}
 def include(p,arc=None):
  if p.is_file(): files[arc or str(p.relative_to(root))]=p
 for p in src.iterdir():
  if p.is_file() and p.suffix in (".py",".sh",".md"):
   include(p)
 for p in run.rglob("*"):
  if p.is_file() and p.suffix not in (".sqlite3",".lock") and not p.name.endswith(("-wal","-shm")):
   include(p)
 for name in ("api.sqlite3","registry.sqlite3"):
  files[f"zimage-dual/production-system/gpu-integration-20261015/{name}"]=tmp/name
 for p in (root/"manifests/model.json",root/"manifests/support.json",
           src/"gpu-integration-20261015-encoder.log",
           src/"gpu-integration-20261015-dispatch.log",
           src/"logs/b19-worker0.log",src/"logs/b19-worker1.log"):
  include(p)
 for item in report["jobs"]:
  include(Path(item["png_path"]))
 meta={"scope":"B1.10 source+new-state+GPU artifacts only; excludes historical full archive/model weights/secrets",
       "hardware":"Kaggle Tesla T4x2","production_acceptance":"PENDING",
       "dependencies":{n:md.version(n) for n in ("torch","diffusers","transformers","huggingface_hub","torchao","gguf")}}
 with zipfile.ZipFile(out,"x",zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  z.writestr("README-METADATA.json",json.dumps(meta,indent=2)+"\n")
  for arc,p in sorted(files.items()):
   assert not arc.startswith("/") and ".." not in Path(arc).parts
   z.write(p,arcname=arc)
digest=hashlib.sha256(out.read_bytes()).hexdigest()
Path(str(out)+".sha256").write_text(digest+"  "+out.name+"\n")
with zipfile.ZipFile(out) as z:
 assert z.testzip() is None
 print(json.dumps({"status":"B110_PORTABLE_INTEGRITY_PASS","files":len(z.namelist()),
                   "bytes":out.stat().st_size,"sha256":digest,"archive":str(out)},sort_keys=True))

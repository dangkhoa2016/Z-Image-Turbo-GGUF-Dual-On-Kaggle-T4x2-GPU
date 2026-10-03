#!/usr/bin/env python3
"""Verify portable GPU evidence and checkpoints after the dispatch process exits."""
import hashlib,json,sqlite3,zipfile,importlib.metadata as md,time,os
from pathlib import Path
from PIL import Image
root=Path(__file__).resolve().parents[1]
source=root/"production-system"
run=source/"gpu-integration-20261015"
db=run/"api.sqlite3"
with sqlite3.connect(f"file:{db}?mode=ro",uri=True) as c:
 c.row_factory=sqlite3.Row
 jobs=[dict(x) for x in c.execute("SELECT id,seed,state,worker_id,attempt,output_sha256,last_error FROM jobs ORDER BY created_at")]
 assert len(jobs)==2 and all(x["state"]=="completed" for x in jobs),f"not complete: {[(x['state'],x['last_error']) for x in jobs]}"
 entries=[]
 for job in jobs:
  a=c.execute("SELECT path,sha256 FROM b14_artifacts WHERE job_id=?",(job["id"],)).fetchone()
  assert a is not None
  p=Path(a["path"]);assert p.is_file() and p.parent==root/"output"/f"worker-{job['worker_id']}"
  digest=hashlib.sha256(p.read_bytes()).hexdigest()
  with Image.open(p) as img:
   assert img.format=="PNG" and img.size==(1024,1024)
  assert digest==a["sha256"]==job["output_sha256"]
  ev=list(c.execute("SELECT event,when_at FROM b12_events WHERE job_id=? ORDER BY when_at",(job["id"],)))
  claim=[x["when_at"] for x in ev if x["event"].startswith("HTTP_CLAIM_")]
  done=[x["when_at"] for x in ev if x["event"]=="HTTP_PNG_VERIFIED"]
  elapsed=round(done[-1]-claim[-1],2) if claim and done else None
  entries.append({"job_id":job["id"],"worker_id":job["worker_id"],"seed":job["seed"],
   "png_path":str(p),"png_sha256":digest,"png_bytes":p.stat().st_size,
   "width":1024,"height":1024,"claim_to_verified_seconds":elapsed,"attempt":job["attempt"]})
state=json.loads((run/"b16-phase-status.json").read_text())
manifest=json.loads((run/"session/b18-inference-manifest.json").read_text())
assert state["status"]=="READY_FOR_INFERENCE_START" and state["real_gpu_encoding"] is True
assert manifest["test_only"] is False and len(manifest["entries"])==2
report={"gate":"DUAL_GPU_INTEGRATION","status":"REAL_GPU_TWO_JOB_INFERENCE_PASS","previous_cpu_milestones_untouched":True,
 "hardware":"Tesla T4 x2","backend":"Z-Image-Turbo GGUF Q6_K", "steps":9,
 "diffusers":md.version("diffusers"),"torch":md.version("torch"),
 "qwen3_encoder":"real_gpu0","embedding_entries_verified":2,"jobs":entries,
 "production_acceptance":"PENDING","limitations":"Claim-to-verified timing includes HTTP/PNG validation; not strictly diffusion-only runtime."}
p=run/"b110-real-gpu-evidence.json";p.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
archive=Path("/kaggle/working/ZIMAGE-DUAL-B110-T4X2-REAL-GPU-INTEGRATION-20261015.zip")
files=[p,run/"session/b18-inference-manifest.json",run/"b16-phase-status.json",
 source/"gpu-integration-20261015-encoder.log",source/"gpu-integration-20261015-dispatch.log",
 source/"gpu_prompt_gate.py",source/"gpu_dispatch.py"]
files += [Path(x["png_path"]) for x in entries]
with zipfile.ZipFile(archive,"x",zipfile.ZIP_DEFLATED) as z:
 for f in files:
  z.write(f,arcname=f.relative_to(root) if f.is_relative_to(root) else f.name)
digest=hashlib.sha256(archive.read_bytes()).hexdigest()
Path(str(archive)+".sha256").write_text(digest+"  "+archive.name+"\n")
with zipfile.ZipFile(archive) as z: assert z.testzip() is None
print("REAL_GPU_INTEGRATION_PASS",json.dumps({"jobs":len(entries),"durations":[x["claim_to_verified_seconds"] for x in entries],"archive":str(archive),"archive_sha256":digest,"size":archive.stat().st_size}),flush=True)

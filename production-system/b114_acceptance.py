#!/usr/bin/env python3
"""B1.14 one-shot isolated real Kaggle GPU acceptance orchestrator. No historic DB."""
import argparse,importlib.metadata as md,json,os,secrets,sqlite3,subprocess,sys,time
from pathlib import Path
ROOT=Path("/kaggle/working/zimage-dual")
SRC=ROOT/"production-system"
def main():
 p=argparse.ArgumentParser()
 p.add_argument("--run",action="store_true",help="explicitly execute new GPU jobs")
 a=p.parse_args()
 run=SRC/"b114-real-gpu-acceptance-20261015"
 if run.exists():raise RuntimeError("acceptance directory exists: no replay or overwrite")
 run.mkdir(parents=True)
 os.environ["ZIMAGE_B1_DB"]=str(run/"api.sqlite3")
 os.environ["ZIMAGE_B1_API_KEY"]=secrets.token_urlsafe(40)
 from fastapi.testclient import TestClient
 import b113_admission
 from b113_shared_lifecycle import SharedLifecycle
 from b112_lifecycle import RolloverBlocked
 from http_dispatcher import connect
 support=json.loads((ROOT/"manifests/support.json").read_text())
 identity={"support_manifest_sha256":support["manifest_sha256"],
  "diffusers_version":md.version("diffusers"),"max_sequence_length":512,"text_encoder_dtype":"bfloat16"}
 prompts=[
 ("A miniature ivory lighthouse on a dark slate desk, fine architectural product photography, detailed reflections, crisp natural studio lighting",146401),
 ("A turquoise ceramic bowl containing three red apples, minimalist food still life, realistic texture, soft directional afternoon sunlight",146402)]
 client=TestClient(b113_admission.app)
 header={"Authorization":"Bearer "+os.environ["ZIMAGE_B1_API_KEY"]}
 ids=[]
 for prompt,seed in prompts:
  resp=client.post("/v1/jobs",headers=header,json={"prompt":prompt,"seed":seed})
  resp.raise_for_status();ids.append(resp.json()["job_id"])
 (run/"frozen-request-summary.json").write_text(json.dumps({"job_ids":ids,"seeds":[x[1] for x in prompts]},indent=2))
 life=SharedLifecycle(api_db=run/"api.sqlite3",sessions_root=run/"sessions",
  artifact_root=ROOT/"output",identity=identity,mode="gpu0",max_prompts=2,max_jobs=2)
 if not a.run:
  print("B114_DRY_RUN_CREATED_QUEUE_ONLY -- explicit --run required to encode or dispatch",flush=True)
  return
 def callback(sid,prepared):
  cmd=[sys.executable,str(SRC/"b114_shared_gpu_supervisor.py"),
   "--session-id",sid,"--api-db",str(run/"api.sqlite3"),
   "--sessions-root",str(run/"sessions"),"--run"]
  print("B114_GPU_SUPERVISOR_START",sid,flush=True)
  result=subprocess.run(cmd,capture_output=True,text=True,timeout=2700)
  (run/"gpu-supervisor-stdout.log").write_text(result.stdout)
  (run/"gpu-supervisor-stderr.log").write_text(result.stderr)
  if result.returncode:raise RuntimeError("GPU supervisor failed: "+result.stderr[-1200:])
  outcome=json.loads(result.stdout.strip().splitlines()[-1])
  if outcome.get("status")!="B114_GPU_DISPATCH_FINISHED":raise RuntimeError("incorrect supervisor outcome")
  print("B114_GPU_SUPERVISOR_DISPATCH_PASS",json.dumps(outcome),flush=True)
  return outcome
 print("B114_REAL_SESSION_START",flush=True)
 result=life.run_one(callback)
 assert result["archive"]["verified_png"]==2 and result["archive"]["frozen_jobs"]==2
 (run/"b114-acceptance-result.json").write_text(json.dumps(result,indent=2))
 print("B114_REAL_SHARED_DB_GPU_ACCEPTANCE_PASS",json.dumps(result["archive"]),flush=True)
if __name__=="__main__":
 try:main()
 except Exception as e:
  print("B114_ACCEPTANCE_BLOCKED "+type(e).__name__+": "+str(e),file=sys.stderr,flush=True)
  sys.exit(2)

#!/usr/bin/env python3
"""Bounded Kaggle T4x2 inference-session supervisor.

Runs only a separately prepared REAL manifest/session. Default is dry-run.
No historical DB mutation, no automatic retry of uncertain jobs, no public HTTP.
"""
import argparse,json,os,signal,socket,subprocess,sys,time,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"production-system"
def ensure(condition,message):
 if not condition:raise RuntimeError(message)
def ready(slot):
 try:
  with urllib.request.urlopen(f"http://127.0.0.1:{12340+slot}/ready",timeout=2) as resp:
   obj=json.load(resp)
  return obj.get("ready") is True and obj.get("worker_id")==slot
 except Exception:return False
def execute(a):
 from dynamic_manifest import read_manifest
 run=Path(a.session).resolve(strict=True)
 if a.run:ensure(not (run/"TEST_ONLY-NEVER-RUN-GPU.txt").exists(),"synthetic fixture forbidden for GPU execution")
 ensure(run.is_relative_to(SRC),"session must be inside production-system")
 manifest=run/"session/b18-inference-manifest.json"
 identity_path=run/"session/b18-encoder-identity.json"
 phase_path=run/"b16-phase-status.json"
 for p in (manifest,identity_path,phase_path,run/"api.sqlite3",run/"registry.sqlite3"):
  ensure(p.is_file(),f"missing {p.name}")
 phase=json.loads(phase_path.read_text())
 ensure(phase.get("status")=="READY_FOR_INFERENCE_START" and phase.get("real_gpu_encoding") is True,"real encoding phase not verified")
 entries=read_manifest(manifest,allow_mock=False)["entries"]
 ensure(entries and len(entries)<=32,"invalid real session manifest")
 ensure(not ready(0) and not ready(1),"worker already listening: fail closed")
 for port in (12340,12341):
  with socket.socket() as s:
   s.settimeout(.4)
   ensure(s.connect_ex(("127.0.0.1",port))!=0,f"port already occupied: {port}")
 import sqlite3
 with sqlite3.connect(f"file:{run/'api.sqlite3'}?mode=ro",uri=True) as db:
  states=dict(db.execute("SELECT state,COUNT(*) FROM jobs GROUP BY state").fetchall())
 ensure(states.get("running",0)==0 and states.get("uncertain",0)==0,"unresolved running/uncertain jobs")
 ensure(states.get("queued",0)>0,"no queued jobs: refusing needless GPU start")
 ensure(states.get("queued",0)<=a.max_jobs,"queued bound exceeded")
 evidence={"status":"INFERENCE_SESSION_PREFLIGHT_PASS","session":str(run),"real_prompt_ids":len(entries),"queued_jobs":states["queued"],
           "startup":"NOT_STARTED","dispatch":"NOT_STARTED"}
 if not a.run:
  print(json.dumps(evidence,sort_keys=True));return 0
 subprocess.run([sys.executable,str(SRC/"gpu_preflight.py"),"--expect-gpu","--manifest",str(manifest)],check=True,
                stdout=subprocess.DEVNULL)
 os.environ["ZIMAGE_B1_DB"]=str(run/"api.sqlite3")
 os.environ["HF_HUB_OFFLINE"]="1"
 os.environ["TRANSFORMERS_OFFLINE"]="1"
 logs=run/"supervisor-logs";logs.mkdir(exist_ok=True)
 procs=[];handles=[]
 try:
  for slot in (0,1):
   env=os.environ.copy();env["CUDA_VISIBLE_DEVICES"]=str(slot)
   f=(logs/f"worker{slot}.log").open("a")
   handles.append(f)
   p=subprocess.Popen([sys.executable,str(SRC/"dynamic_worker.py"),"--worker-id",str(slot),
     "--port",str(12340+slot),"--manifest",str(manifest)],cwd=str(SRC),env=env,stdout=f,stderr=subprocess.STDOUT,
     start_new_session=True)
   procs.append(p)
  deadline=time.monotonic()+a.ready_timeout
  while time.monotonic()<deadline:
   ensure(all(p.poll() is None for p in procs),"worker exited before readiness")
   if ready(0) and ready(1):break
   time.sleep(2)
  else:raise TimeoutError("worker ready timeout")
  evidence["startup"]="DUAL_WORKER_READY"
  identity=json.loads(identity_path.read_text())
  from unified_pipeline import UnifiedPipeline
  pipe=UnifiedPipeline(api_db=run/"api.sqlite3",registry_db=run/"registry.sqlite3",
   cache_root=run/"cache",identity=identity,session_dir=run/"session",
   artifact_root=ROOT/"output",mode="gpu0")
  outcome=pipe.dispatch(timeout=a.dispatch_timeout)
  evidence["dispatch"]=outcome
  ensure(outcome["states"].get("completed",0)==states.get("completed",0)+states["queued"],"some pending jobs not completed")
  ensure(outcome["verified_artifacts"]>=states["queued"],"artifact verification count mismatch")
  evidence["status"]="INFERENCE_SESSION_COMPLETE"
  print(json.dumps(evidence,sort_keys=True),flush=True)
  return 0
 finally:
  for p in procs:
   if p.poll() is None:p.terminate()
  for p in procs:
   try:p.wait(timeout=25)
   except subprocess.TimeoutExpired:p.kill();p.wait(timeout=10)
  for f in handles:f.close()
  evidence["cleanup"]="WORKER_PROCESSES_STOPPED"
  report=run/"b111-supervisor-result.json"
  if report.exists():report=run/f"b111-supervisor-result-{int(time.time())}.json"
  report.write_text(json.dumps(evidence,indent=2,sort_keys=True)+"\n")
def main():
 p=argparse.ArgumentParser()
 p.add_argument("--session",required=True)
 p.add_argument("--run",action="store_true",help="explicitly start two GPUs; default is dry run")
 p.add_argument("--ready-timeout",type=int,default=240)
 p.add_argument("--dispatch-timeout",type=int,default=1800)
 p.add_argument("--max-jobs",type=int,default=4)
 a=p.parse_args()
 ensure(30<=a.ready_timeout<=900 and 30<=a.dispatch_timeout<=3600 and 1<=a.max_jobs<=32,"invalid bounds")
 try:return execute(a)
 except Exception as e:
  print(f"INFERENCE_SESSION_BLOCKED={type(e).__name__}: {e}",file=sys.stderr,flush=True)
  return 2
if __name__=="__main__":sys.exit(main())

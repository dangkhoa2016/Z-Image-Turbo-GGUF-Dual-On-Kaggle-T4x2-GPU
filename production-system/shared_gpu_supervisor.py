#!/usr/bin/env python3
"""Bounded, fail-closed shared-SQLite GPU worker supervisor."""
import argparse,json,os,socket,subprocess,sys,time,urllib.request
from pathlib import Path
from contextlib import closing
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"production-system"
def must(cond,reason):
 if not cond:raise RuntimeError(reason)
def health(i):
 try:
  with urllib.request.urlopen(f"http://127.0.0.1:{12340+i}/ready",timeout=2) as r:
   o=json.load(r)
  return o.get("ready") is True and o.get("worker_id")==i
 except Exception:return False
def last_worker_stage(path):
 if not path.is_file():return "NO_LOG"
 try:
  with path.open("rb") as stream:
   stream.seek(max(0,path.stat().st_size-16384))
   lines=stream.read().decode("utf-8",errors="replace").splitlines()
  stages=[line[len("ZIMAGE_WORKER_STAGE "):] for line in lines
          if line.startswith("ZIMAGE_WORKER_STAGE ")]
  return json.loads(stages[-1])["stage"] if stages else "IMPORTING_OR_NO_STAGE"
 except (OSError,ValueError,KeyError):return "LOG_UNAVAILABLE"
def worker_rss_mib(pid):
 try:
  stat=next(line for line in open(f"/proc/{pid}/status") if line.startswith("VmRSS:"))
  return round(int(stat.split()[1])/1024)
 except (OSError,StopIteration,IndexError,ValueError):return None
def run(session_id,api_db,sessions_root,artifact_root,ready_timeout,dispatch_timeout,launch):
 os.environ["ZIMAGE_B1_DB"]=str(api_db)
 from http_dispatcher import connect
 from scoped_dispatcher import ScopedDispatcher
 from worker_adapter import WorkerAdapter,file_hash
 from dynamic_manifest import read_manifest
 folder=Path(sessions_root)/session_id
 must(folder.is_dir() and folder.resolve().is_relative_to(SRC),"invalid session folder")
 with closing(connect()) as c:
  s=c.execute("SELECT status,manifest,manifest_sha256,mode FROM b112_sessions WHERE session_id=?",(session_id,)).fetchone()
  must(s and s["status"]=="DISPATCHING" and s["mode"]=="gpu0","session not frozen for real GPU")
  frozen=c.execute("SELECT job_id FROM b113_session_jobs WHERE session_id=?",(session_id,)).fetchall()
  must(0<len(frozen)<=4,"frozen jobs out of bounds")
  must(c.execute("SELECT COUNT(*) FROM jobs j JOIN b113_session_jobs sj ON sj.job_id=j.id WHERE sj.session_id=? AND j.state='queued'",(session_id,)).fetchone()[0]==len(frozen),"in-flight or terminal snapshot")
  must(c.execute("SELECT COUNT(*) FROM jobs WHERE state IN ('running','uncertain')").fetchone()[0]==0,"unsafe jobs")
 manifest=Path(s["manifest"])
 must(manifest.is_file() and manifest.resolve().is_relative_to(folder.resolve()),"unsafe manifest path")
 must(file_hash(manifest)==s["manifest_sha256"],"manifest changed")
 obj=read_manifest(manifest,allow_mock=False)
 must(len(obj["entries"])>0,"empty manifest")
 for port in (12340,12341):
  with socket.socket() as sk:
   sk.settimeout(.3)
   must(sk.connect_ex(("127.0.0.1",port))!=0,"worker TCP port already occupied")
 if not launch:
  return {"status":"GPU_DRY_RUN_VALIDATED","session_id":session_id,"frozen_jobs":len(frozen),"workers_started":False}
 subprocess.run([sys.executable,str(SRC/"gpu_preflight.py"),"--expect-gpu","--manifest",str(manifest)],check=True,stdout=subprocess.DEVNULL)
 env=os.environ.copy();env["HF_HUB_OFFLINE"]="1";env["TRANSFORMERS_OFFLINE"]="1"
 logs=folder/"gpu-supervisor-logs";logs.mkdir(exist_ok=True)
 procs=[];handles=[]
 try:
  for i in (0,1):
   e=env.copy();e["CUDA_VISIBLE_DEVICES"]=str(i)
   f=(logs/f"worker-{i}.log").open("a");handles.append(f)
   procs.append(subprocess.Popen([sys.executable,str(SRC/"dynamic_worker.py"),"--worker-id",str(i),
    "--port",str(12340+i),"--manifest",str(manifest)],cwd=SRC,env=e,stdout=f,stderr=subprocess.STDOUT,start_new_session=True))
  started=time.monotonic()
  until=started+ready_timeout
  next_report=started
  while time.monotonic()<until:
   for i,p in enumerate(procs):
    if p.poll() is not None:
     raise RuntimeError("GPU worker "+str(i)+" exited with code "+str(p.returncode)+
      " at stage "+last_worker_stage(logs/f"worker-{i}.log"))
   if health(0) and health(1):
    print("GPU_WORKER_PAIR_READY "+json.dumps({"session_id":session_id,
      "elapsed_seconds":round(time.monotonic()-started,2),
      "worker_pids":[p.pid for p in procs]}),flush=True)
    break
   if time.monotonic()>=next_report:
    details={str(i):{"pid":p.pid,"stage":last_worker_stage(logs/f"worker-{i}.log"),
              "rss_mib":worker_rss_mib(p.pid)} for i,p in enumerate(procs)}
    print("GPU_WORKER_STARTUP_PROGRESS "+json.dumps({"elapsed_seconds":
      round(time.monotonic()-started,1),"workers":details},sort_keys=True),flush=True)
    next_report=time.monotonic()+15
   time.sleep(2)
  else:
   details={str(i):last_worker_stage(logs/f"worker-{i}.log") for i in (0,1)}
   raise TimeoutError("dual GPU startup timeout after "+str(ready_timeout)+
    "s; last stages="+json.dumps(details,sort_keys=True))
  adapters={i:WorkerAdapter(i,f"http://127.0.0.1:{12340+i}",artifact_root) for i in (0,1)}
  result=ScopedDispatcher(adapters,session_id).drain(timeout=dispatch_timeout)
  with closing(connect()) as c:
   statuses=c.execute("SELECT j.state,COUNT(*) FROM jobs j JOIN b113_session_jobs sj ON sj.job_id=j.id WHERE sj.session_id=? GROUP BY j.state",(session_id,)).fetchall()
  status=dict(statuses)
  must(status.get("completed",0)+status.get("cancelled",0)==len(frozen),"frozen jobs not all terminal")
  return {"status":"GPU_DISPATCH_FINISHED","session_id":session_id,"frozen_jobs":len(frozen),"scoped_states":status,"dispatcher":result}
 finally:
  for p in procs:
   if p.poll() is None:p.terminate()
  for p in procs:
   try:p.wait(timeout=25)
   except subprocess.TimeoutExpired:p.kill();p.wait(timeout=10)
  for f in handles:f.close()
def main():
 a=argparse.ArgumentParser()
 a.add_argument("--session-id",required=True)
 a.add_argument("--api-db",required=True)
 a.add_argument("--sessions-root",required=True)
 a.add_argument("--artifact-root",default=str(Path(__file__).resolve().parents[1]/"output"))
 a.add_argument("--run",action="store_true")
 a.add_argument("--ready-timeout",type=int,default=240)
 a.add_argument("--dispatch-timeout",type=int,default=1800)
 x=a.parse_args()
 must(30<=x.ready_timeout<=900 and 30<=x.dispatch_timeout<=3600,"invalid timeout bounds")
 must(x.session_id.startswith("b112-"),"invalid session identity")
 must(Path(x.api_db).resolve().is_relative_to(SRC),"API database must be isolated under production-system")
 must(Path(x.sessions_root).resolve().is_relative_to(SRC),"session root must be under production-system")
 must(Path(x.artifact_root).resolve()==ROOT/"output","artifact destination mismatch")
 # The adapter demands an existing canonical root even before the first worker writes.
 # Establish it only after all scope/identity checks and never follow a symlink.
 target=ROOT/"output"
 must(not target.is_symlink(),"artifact root symlink forbidden")
 target.mkdir(mode=0o755,parents=False,exist_ok=True)
 must(target.is_dir() and target.resolve(strict=True)==ROOT/"output","unsafe artifact root")
 print(json.dumps(run(x.session_id,Path(x.api_db),Path(x.sessions_root),Path(x.artifact_root),
  x.ready_timeout,x.dispatch_timeout,x.run),sort_keys=True),flush=True)
if __name__=="__main__":
 try:main()
 except Exception as e:
  print("GPU_DISPATCH_BLOCKED="+type(e).__name__+": "+str(e),file=sys.stderr,flush=True)
  sys.exit(2)

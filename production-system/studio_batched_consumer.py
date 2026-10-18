#!/usr/bin/env python3
"""Bounded batch queue consumer using the shared session lifecycle and fail-closed GPU supervisor."""
import argparse,fcntl,importlib.metadata as md,json,os,sys,time,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"production-system"
sys.path.insert(0,str(SRC))
from shared_session_lifecycle import SharedLifecycle
from shared_gpu_supervisor import run as gpu_run
from http_dispatcher import connect
def main():
 a=argparse.ArgumentParser()
 a.add_argument("--run-root",required=True)
 a.add_argument("--poll",type=float,default=2.0)
 a.add_argument("--batch-wait",type=float,default=25.0,help="Max seconds to gather a second queued job before freezing")
 a.add_argument("--once",action="store_true")
 opt=a.parse_args()
 d=Path(opt.run_root).resolve()
 if not d.is_relative_to(SRC) or not (d/"api.sqlite3").is_file():raise RuntimeError("invalid live root/database")
 if os.getenv("ZIMAGE_B1_DB")!=str(d/"api.sqlite3"):raise RuntimeError("DB environment mismatch")
 if not 1<=opt.poll<=30:raise RuntimeError("invalid polling interval")
 if not 0<=opt.batch_wait<=60:raise RuntimeError("invalid batching interval")
 lock=d/"auto-consumer.lock"
 with lock.open("a+") as f:
  try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:raise RuntimeError("queue consumer already running")
  support=json.loads((ROOT/"manifests/support.json").read_text())
  identity={"support_manifest_sha256":support["manifest_sha256"],"diffusers_version":md.version("diffusers"),"max_sequence_length":512,"text_encoder_dtype":"bfloat16"}
  life=SharedLifecycle(api_db=d/"api.sqlite3",sessions_root=d/"sessions",artifact_root=ROOT/"output",identity=identity,mode="gpu0",max_prompts=2,max_jobs=4)
  print("AUTO_CONSUMER_READY",str(d),flush=True)
  def dispatch(sid,prepared):
   result=gpu_run(sid,d/"api.sqlite3",d/"sessions",ROOT/"output",300,1800,True)
   print("AUTO_GPU_DISPATCH_DONE",json.dumps(result,sort_keys=True),flush=True)
   return result
  last_batch_notice=None
  while True:
   try:
    with connect() as c:
     stats=c.execute("SELECT COUNT(*), MIN(created_at) FROM jobs WHERE state='queued'").fetchone()
     outstanding,oldest=stats[0],stats[1]
    if outstanding:
     age=max(0,time.time()-oldest)
     if outstanding==1 and age<opt.batch_wait and not opt.once:
      if last_batch_notice != oldest:
       print("AUTO_BATCH_WAIT",json.dumps({"max_seconds":opt.batch_wait,"job_age":round(age,1),"queued":outstanding}),flush=True)
       last_batch_notice=oldest
     else:
      print("AUTO_QUEUE_DISCOVERED",outstanding,flush=True)
      last_batch_notice=None
      result=life.run_one(dispatch)
      print("AUTO_SESSION_DONE",json.dumps(result["archive"],sort_keys=True),flush=True)
    elif opt.once:print("AUTO_NO_PENDING",flush=True);break
   except BaseException as e:
    print("AUTO_CONSUMER_BLOCKED",type(e).__name__,str(e),flush=True)
    traceback.print_exc()
    raise
   if opt.once:break
   time.sleep(opt.poll)
if __name__=="__main__":main()

#!/usr/bin/env python3
"""Guarded encoding-to-inference phase coordinator with separate CPU mock and Kaggle GPU 0 modes.
Does not launch inference workers: it releases an explicit verified gate only.
"""
import os,sys,json,time,uuid,subprocess,fcntl,hashlib,argparse
from pathlib import Path
from embedding_registry import Registry
def atomic_json(path,data):
 t=path.with_name(path.name+"."+uuid.uuid4().hex+".tmp")
 with t.open("x") as f:
  json.dump(data,f,sort_keys=True,indent=2);f.write("\n");f.flush();os.fsync(f.fileno())
 os.replace(t,path)
def check_no_workers():
 import socket
 for port in (12340,12341):
  with socket.socket() as s:
   s.settimeout(.25)
   if s.connect_ex(("127.0.0.1",port))==0:raise RuntimeError("inference worker port is active")
def gate(db,root,identity,prompts):
 reg=Registry(db,root,identity)
 rows=[reg.enqueue(prompt) for prompt in prompts]
 return reg,rows
def main():
 a=argparse.ArgumentParser()
 a.add_argument("--db",required=True);a.add_argument("--cache-root",required=True)
 a.add_argument("--identity",required=True);a.add_argument("--prompt-json",required=True)
 a.add_argument("--mode",choices=["gpu0","cpu-mock"],required=True)
 a.add_argument("--max-items",type=int,default=8)
 args=a.parse_args()
 if not 1<=args.max_items<=32:raise ValueError("bad batch limit")
 identity=json.loads(Path(args.identity).read_text())
 prompts=json.loads(Path(args.prompt_json).read_text())
 if not isinstance(prompts,list) or not prompts or len(prompts)>args.max_items or any(not isinstance(x,str) for x in prompts):
  raise ValueError("prompts must be bounded list of text")
 control=Path(args.db).parent
 control.mkdir(parents=True,exist_ok=True)
 status=control/"b16-phase-status.json"
 lock=control/"b16-phase.lock"
 with lock.open("a+") as f:
  fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
  check_no_workers()
  reg,rows=gate(args.db,args.cache_root,identity,prompts)
  if any(row["status"]=="uncertain" for row in rows):
   raise RuntimeError("unresolved uncertain encoding; no phase switch")
  owner=uuid.uuid4().hex
  atomic_json(status,{"status":"ENCODING","mode":args.mode,"session":owner,"gpu_inference":"NOT_STARTED"})
  env=os.environ.copy()
  if args.mode=="cpu-mock":
   if not env.get("ZIMAGE_B16_TEST_ROOT","").startswith("/tmp/b16-test-"):raise RuntimeError("mock test boundary absent")
   script="encode_batch_cpu_mock.py"
   cmd=[sys.executable,str(Path(__file__).with_name(script)),"--db",args.db,"--cache-root",args.cache_root,
        "--identity",args.identity,"--max-items",str(args.max_items)]
  else:
   check_no_workers()
   env["CUDA_VISIBLE_DEVICES"]="0"
   env["HF_HUB_OFFLINE"]="1";env["TRANSFORMERS_OFFLINE"]="1"
   script="encode_batch_gpu.py"
   cmd=[sys.executable,str(Path(__file__).with_name(script)),"--db",args.db,"--cache-root",args.cache_root,
        "--max-items",str(args.max_items)]
  try:
   cp=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=3600,check=False)
   if cp.returncode!=0:raise RuntimeError("encoder subprocess failed: "+cp.stderr[-1000:])
   reg.expire()
   if not all(reg.check_ready(reg.key(prompt)) for prompt in prompts):
    raise RuntimeError("not all requested embeddings verified READY")
   check_no_workers()
   # For real GPU, subprocess has exited; GPU VRAM must additionally be verified
   # externally before workers start (nvidia-smi evidence).
   if args.mode=="gpu0":
    import shutil
    if shutil.which("nvidia-smi") is None:raise RuntimeError("missing post-encoder GPU verification")
    gp=subprocess.run(["nvidia-smi","--query-compute-apps=pid","--format=csv,noheader,nounits"],
      capture_output=True,text=True,timeout=15,check=True)
    if gp.stdout.strip():raise RuntimeError("GPU compute process still alive; cannot switch phase")
   result={"status":"READY_FOR_INFERENCE_START","mode":args.mode,"session":owner,
     "encoder_process_exit":0,"verified_ready":len(prompts),
     "real_gpu_encoding":args.mode=="gpu0",
     "inference_workers_started":False,
     "note":"In separate step start isolated dynamic worker processes; historical worker has 3-prompt cache"}
   atomic_json(status,result)
   print(json.dumps(result,sort_keys=True),flush=True)
  except BaseException as e:
   atomic_json(status,{"status":"BLOCKED","mode":args.mode,"session":owner,"reason":str(e),"inference_workers_started":False})
   raise
if __name__=="__main__":main()

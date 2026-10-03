#!/usr/bin/env python3
"""Idempotent CPU-only local Studio/API resume. Never starts the GPU consumer."""
import json,os,subprocess,sys,time,urllib.request,sqlite3,fcntl
from pathlib import Path
BASE=Path("/kaggle/working/zimage-dual")
SRC=BASE/"production-system"
RUN=SRC/"b3-studio-demo-live-20261016"
with (RUN/"local-restart.lock").open("a+") as lf:
 fcntl.flock(lf,fcntl.LOCK_EX)
 db=RUN/"api.sqlite3"
 if not db.is_file():raise RuntimeError("Missing SQLite: refuse to initialize/overwrite")
 with sqlite3.connect("file:"+str(db)+"?mode=ro",uri=True) as c:
  if c.execute("pragma integrity_check").fetchone()[0]!="ok":raise RuntimeError("SQLite corrupted")
  invalid=c.execute("SELECT COUNT(*) FROM jobs WHERE state IN ('running','uncertain')").fetchone()[0]
  if invalid:raise RuntimeError("Nonterminal GPU jobs require manual reconciliation")
 cfg=json.loads((RUN/"local-secrets.json").read_text())
 env=os.environ.copy()
 env.update({"ZIMAGE_B1_DB":str(db),"ZIMAGE_B1_API_KEY":cfg["service_key"],
 "ZIMAGE_B3_ARTIFACT_ROOT":str(RUN/"private"),
 "ZIMAGE_B3_TENANTS_JSON":json.dumps({"studio_demo":cfg["api_token"]}),
 "STUDIO_INTERNAL_KEY":cfg["api_token"],"VUE_STUDIO_PASSWORD":cfg["studio_password"],
 "ZIMAGE_STUDIO_DB":str(db)})
 checks=[
 ("api",18788,SRC/"studio-demo","demo_api:app","/health"),
 ("gateway",18789,BASE/"product-studio","gateway:app","/auth/session")
 ]
 for name,port,cwd,module,path in checks:
  url=f"http://127.0.0.1:{port}{path}"
  try:
   with urllib.request.urlopen(url,timeout=2) as r:ready=r.status==200
  except Exception:ready=False
  if ready:
   print(name.upper()+"_ALREADY_READY",port,flush=True);continue
  log=(RUN/(name+".log")).open("ab")
  p=subprocess.Popen([sys.executable,"-m","uvicorn",module,"--host","127.0.0.1","--port",str(port)],cwd=cwd,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  log.close();(RUN/(name+".pid")).write_text(str(p.pid))
  for i in range(40):
   try:
    with urllib.request.urlopen(url,timeout=2) as r:
     if r.status==200:break
   except Exception:time.sleep(.3)
  else:raise RuntimeError(name+" failed to start; see log")
  print(name.upper()+"_STARTED",port,flush=True)
 print("RESUME_CPU_ONLY=PASS; NO_GPU_REPLAY=YES")

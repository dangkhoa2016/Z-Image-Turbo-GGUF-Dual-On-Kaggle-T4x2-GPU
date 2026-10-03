from pathlib import Path
import os,secrets,json,subprocess,sys,urllib.request,time,signal
ROOT=Path("/kaggle/working/zimage-dual")
PROD=ROOT/"production-system"
RUN=PROD/"b3-studio-demo-live-20261016"
assert not RUN.exists(),"Existing demo run: refuse overwrite"
RUN.mkdir(mode=0o700)
os.chmod(RUN,0o700)
secret=secrets.token_urlsafe(40)
password=secrets.token_urlsafe(24)
cfg={"api_token":secret,"studio_password":password}
path=RUN/"local-secrets.json"
path.write_text(json.dumps(cfg))
os.chmod(path,0o600)
env=os.environ.copy()
env.update(ZIMAGE_B1_DB=str(RUN/"api.sqlite3"),
 ZIMAGE_B1_API_KEY=secrets.token_urlsafe(40),
 ZIMAGE_B3_ARTIFACT_ROOT=str(RUN/"private"),
 ZIMAGE_B3_TENANTS_JSON=json.dumps({"studio_demo":secret}),
 STUDIO_INTERNAL_KEY=secret,
 VUE_STUDIO_PASSWORD=password,
 ZIMAGE_STUDIO_DB=str(RUN/"api.sqlite3"))
# Keep the control-plane secret for a local restart, never print or transmit it.
cfg["service_key"]=env["ZIMAGE_B1_API_KEY"]
path.write_text(json.dumps(cfg))
os.chmod(path,0o600)
processes=[
 ("api",["python3","-m","uvicorn","demo_api:app","--host","127.0.0.1","--port","18788"],PROD/"b3-demo-studio-20261016"),
 ("gateway",["python3","-m","uvicorn","gateway:app","--host","127.0.0.1","--port","18789"],ROOT/"product-studio-vue-cdn-v3"),
]
for name,command,cwd in processes:
 log=(RUN/(name+".log")).open("ab")
 p=subprocess.Popen(command,cwd=cwd,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 (RUN/(name+".pid")).write_text(str(p.pid))
 log.close()
 print("STARTED",name,"pid",p.pid,"localhost only")
time.sleep(2)
for port in (18788,18789):
 try:
  with urllib.request.urlopen(f"http://127.0.0.1:{port}/health" if port==18788 else f"http://127.0.0.1:{port}/auth/session",timeout=3) as r:
   print("HTTP_READY",port,r.status,r.read(180).decode())
 except Exception as e:
  print("HTTP_NOT_READY",port,type(e).__name__,str(e)[:120])
print("LOCAL_CREDENTIAL_FILE",path)

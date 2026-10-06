import os,json,subprocess,sys,sqlite3
from pathlib import Path
root=Path("/kaggle/working/zimage-dual/production-system")
run=root/"b3-studio-demo-live-20261016"
pidfile=run/"persistent-gpu-consumer.pid"
if pidfile.exists():
 old=int(pidfile.read_text())
 try:os.kill(old,0);raise RuntimeError("Existing persistent consumer PID "+str(old))
 except ProcessLookupError:pass
with sqlite3.connect(run/"api.sqlite3") as db:
 assert db.execute("pragma integrity_check").fetchone()[0]=="ok"
 assert db.execute("select count(*) from jobs where state in ('running','uncertain')").fetchone()[0]==0
 assert db.execute("select count(*) from b112_sessions where status!='ARCHIVED'").fetchone()[0]==0
 print("QUEUED_BEFORE",db.execute("select count(*) from jobs where state='queued'").fetchone()[0])
cfg=json.loads((run/"local-secrets.json").read_text())
env=os.environ.copy()
env.update(ZIMAGE_B1_DB=str(run/"api.sqlite3"),ZIMAGE_B1_API_KEY=cfg["service_key"],
 ZIMAGE_B3_TENANTS_JSON=json.dumps({"studio_demo":cfg["api_token"]}),ZIMAGE_B3_ARTIFACT_ROOT=str(run/"private"),
 PYTHONPATH=":".join(str(root/x) for x in ("vendor-shim","vendor-hub128","vendor-diffusers041","vendor-torchao015","vendor-gguf")))
# Fail before spawning a persistent worker if imports or wheel metadata are shadowed.
audit=subprocess.run([sys.executable,str(root.parent/"scripts"/"verify_vendor_runtime.py")],
                     env=env,capture_output=True,text=True,timeout=120)
if audit.returncode:
 raise RuntimeError("Vendor runtime verification failed before GPU worker launch: "+audit.stderr[-1000:])
print("GPU_CONSUMER_VENDOR_GATE=PASS")
with (run/"persistent-gpu-consumer.log").open("ab") as log:
 p=subprocess.Popen([sys.executable,str(root/"studio-demo/demo_consumer.py"),
 "--run-root",str(run),"--private-root",str(run/"private"),"--enable-gpu","--poll","2","--batch-wait","25"],
 cwd=root,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
pidfile.write_text(str(p.pid))
print("PERSISTENT_CONSUMER_PID",p.pid)
print("AUTO_RETRY_UNCERTAIN=NO")

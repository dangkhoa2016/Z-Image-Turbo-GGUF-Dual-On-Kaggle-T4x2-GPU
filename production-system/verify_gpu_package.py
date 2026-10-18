#!/usr/bin/env python3
"""Package verified real-GPU source, SQLite snapshot and image artifacts."""
import hashlib,json,sqlite3,zipfile,tempfile
from pathlib import Path
from PIL import Image
root=Path(__file__).resolve().parents[1]
src=root/"production-system"
run=src/"b114-real-gpu-acceptance-20261015"
result=json.loads((run/"b114-acceptance-result.json").read_text())
assert result["status"]=="SESSION_ARCHIVED"
assert result["archive"]["verified_png"]==2
with sqlite3.connect(f"file:{run/'api.sqlite3'}?mode=ro",uri=True) as c:
 c.row_factory=sqlite3.Row
 jobs=[dict(x) for x in c.execute("SELECT id,state,seed,worker_id,output_sha256 FROM jobs")]
 artifacts=[dict(x) for x in c.execute("SELECT job_id,worker_id,path,sha256 FROM b14_artifacts")]
 assert len(jobs)==len(artifacts)==2
 assert all(j["state"]=="completed" for j in jobs)
 assert c.execute("SELECT COUNT(*) FROM b112_sessions WHERE status='ARCHIVED'").fetchone()[0]==1
 assert c.execute("SELECT COUNT(*) FROM b113_active_prompts").fetchone()[0]==0
 assert c.execute("SELECT COUNT(*) FROM b113_session_jobs").fetchone()[0]==2
 verified=[]
 for a in artifacts:
  p=Path(a["path"])
  assert p.is_file() and not p.is_symlink()
  with Image.open(p) as img:
   img.verify()
  with Image.open(p) as img:
   assert img.size==(1024,1024) and img.format=="PNG"
  sha=hashlib.sha256(p.read_bytes()).hexdigest()
  j=next(x for x in jobs if x["id"]==a["job_id"])
  assert sha==a["sha256"]==j["output_sha256"] and a["worker_id"]==j["worker_id"]
  verified.append({"worker":a["worker_id"],"png":str(p),"size":p.stat().st_size,"sha256":sha})
report={"status":"DUAL_GPU_INTEGRATION_PASS","frozen_jobs":2,"verified_png":verified,
        "sqlite_archived":True,"gpu_supervisor_auto_cleanup":True,"production_go":"PENDING"}
(run/"b114-final-verify.json").write_text(json.dumps(report,indent=2)+"\n")
files=[]
for name in ["shared_gpu_supervisor.py","gpu_acceptance.py","queue_admission.py","scoped_dispatcher.py","shared_session_lifecycle.py"]:
 files.append(src/name)
for p in run.rglob("*"):
 if p.is_file() and p.name not in ("api.sqlite3","api.sqlite3-wal","api.sqlite3-shm") and not p.name.endswith((".lock","-wal","-shm")):
  files.append(p)
files.extend(Path(a["png"]) for a in verified)
out=Path("/kaggle/working/ZIMAGE-DUAL-B114-REAL-SHARED-DB-GPU-ACCEPTANCE-20261015.zip")
with tempfile.TemporaryDirectory(prefix="b114-snapshot-",dir="/kaggle/working") as td:
 dbcopy=Path(td)/"api.sqlite3"
 with sqlite3.connect(run/"api.sqlite3") as origin,sqlite3.connect(dbcopy) as dest:origin.backup(dest)
 with zipfile.ZipFile(out,"x",zipfile.ZIP_DEFLATED) as z:
  z.write(dbcopy,"zimage-dual/production-system/b114-real-gpu-acceptance-20261015/api.sqlite3")
  for p in files:
   if p.is_relative_to(root):arc=p.relative_to(root)
   else:arc=p.name
   z.write(p,str(arc))
with zipfile.ZipFile(out) as z:assert z.testzip() is None
sha=hashlib.sha256(out.read_bytes()).hexdigest()
Path(str(out)+".sha256").write_text(sha+"  "+out.name+"\n")
print("GPU_ACCEPTANCE_PACKAGE_PASS",json.dumps({"archive":str(out),"bytes":out.stat().st_size,"sha256":sha,"png":verified},sort_keys=True))

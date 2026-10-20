#!/usr/bin/env python3
"""Session ledger and bounded API queue rollover with additive state transitions.
Preserve historical jobs, existing database tables, and verified evidence.
CPU mock works only under /tmp/b16-test-*; real GPU requires an explicit runner.
"""
import fcntl,hashlib,json,os,sqlite3,time,uuid
from contextlib import closing,contextmanager
from pathlib import Path
from PIL import Image
from unified_pipeline import UnifiedPipeline
from http_dispatcher import connect,prepare_http
from worker_adapter import file_hash

class RolloverBlocked(RuntimeError):pass
def require(ok,reason):
 if not ok:raise RolloverBlocked(reason)

class Lifecycle:
 def __init__(self,*,api_db,sessions_root,artifact_root,identity,mode,max_prompts=2,max_jobs=4):
  require(mode in ("cpu-mock","gpu0"),"explicit mode required")
  require(1<=max_prompts<=8 and 1<=max_jobs<=32,"bounded batch required")
  self.api_db=Path(api_db).resolve()
  self.root=Path(sessions_root).resolve()
  self.artifacts=Path(artifact_root).resolve()
  self.identity=identity
  self.mode=mode
  self.max_prompts=max_prompts;self.max_jobs=max_jobs
  require(self.api_db==Path(os.environ.get("ZIMAGE_B1_DB","")).resolve(),"API DB environment mismatch")
  if mode=="cpu-mock":
   test=Path(os.environ.get("ZIMAGE_B16_TEST_ROOT","")).resolve()
   require(str(test).startswith("/tmp/b16-test-") and all(p.is_relative_to(test) for p in
           (self.api_db,self.root,self.artifacts)),"CPU mock outside test sandbox")
  self.root.mkdir(parents=True,exist_ok=True)
  prepare_http()
  with closing(connect()) as c:
   c.execute("""CREATE TABLE IF NOT EXISTS b112_sessions (
      session_id TEXT PRIMARY KEY,status TEXT NOT NULL,created_at REAL NOT NULL,
      updated_at REAL NOT NULL,manifest TEXT,manifest_sha256 TEXT,mode TEXT NOT NULL)""")
   c.execute("""CREATE TABLE IF NOT EXISTS b112_mapping_history (
      session_id TEXT NOT NULL,prompt TEXT NOT NULL,prompt_id TEXT NOT NULL,
      PRIMARY KEY(session_id,prompt))""")
   c.execute("""CREATE TABLE IF NOT EXISTS b112_artifact_history (
      session_id TEXT NOT NULL,job_id TEXT NOT NULL,worker_id INTEGER NOT NULL,
      sha256 TEXT NOT NULL,path TEXT NOT NULL,PRIMARY KEY(job_id))""")
  self.lockpath=self.api_db.with_suffix(".b112-lifecycle.lock")

 @contextmanager
 def exclusive(self):
  with self.lockpath.open("a+") as f:
   try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
   except BlockingIOError:raise RolloverBlocked("another lifecycle controller owns the lock")
   try:yield
   finally:fcntl.flock(f,fcntl.LOCK_UN)

 def _idle(self):
  import socket
  for port in (12340,12341):
   with socket.socket() as s:
    s.settimeout(.2)
    require(s.connect_ex(("127.0.0.1",port))!=0,"worker still listening, rollover forbidden")

 def active(self):
  with closing(connect()) as c:
   rows=c.execute("SELECT session_id,status,manifest,manifest_sha256 FROM b112_sessions WHERE status IN ('PREPARING','READY','DISPATCHING','BLOCKED') ORDER BY created_at").fetchall()
   require(len(rows)<=1,"multiple active session records")
   return dict(rows[0]) if rows else None

 def start(self):
  self._idle()
  require(self.active() is None,"unresolved previous session; operator reconciliation required")
  with closing(connect()) as c:
   require(c.execute("SELECT COUNT(*) FROM b14_prompt_map").fetchone()[0]==0,
           "orphan mapping; manual reconciliation required")
   require(c.execute("SELECT COUNT(*) FROM jobs WHERE state IN ('running','uncertain')").fetchone()[0]==0,
           "in-flight/uncertain jobs; no new encoding")
   require(c.execute("SELECT COUNT(*) FROM jobs WHERE state='failed'").fetchone()[0]==0,
           "failed jobs need operator reconciliation")
   prompts=[r[0] for r in c.execute("SELECT prompt FROM jobs WHERE state='queued' GROUP BY prompt ORDER BY MIN(created_at),prompt LIMIT ?",(self.max_prompts,))]
   if not prompts:return None
   count=c.execute("SELECT COUNT(*) FROM jobs WHERE state='queued' AND prompt IN ("+
                   ",".join("?" for _ in prompts)+")",prompts).fetchone()[0]
   require(0<count<=self.max_jobs,"batch job bound exceeded")
   sid="b112-"+uuid.uuid4().hex
   now=time.time()
   c.execute("INSERT INTO b112_sessions VALUES(?,?,?,?,?,?,?)",(sid,"PREPARING",now,now,None,None,self.mode))
  folder=self.root/sid
  pipeline=UnifiedPipeline(api_db=self.api_db,registry_db=folder/"registry.sqlite3",
      cache_root=folder/"cache",identity=self.identity,session_dir=folder/"session",
      artifact_root=self.artifacts,mode=self.mode)
  try:
   prepared=pipeline.prepare(max_items=self.max_prompts)
   require(prepared["prompts"]==len(prompts),"prompt batch count mismatch")
   with closing(connect()) as c:
    c.execute("UPDATE b112_sessions SET status='READY',updated_at=?,manifest=?,manifest_sha256=? WHERE session_id=? AND status='PREPARING'",
       (time.time(),prepared["manifest"],prepared["manifest_sha256"],sid))
   return sid,pipeline,prepared
  except Exception:
   with closing(connect()) as c:
    c.execute("UPDATE b112_sessions SET status='BLOCKED',updated_at=? WHERE session_id=?",(time.time(),sid))
   raise

 def validate_finalize(self,sid):
  self._idle()
  with closing(connect()) as c:
   row=c.execute("SELECT * FROM b112_sessions WHERE session_id=?",(sid,)).fetchone()
   require(row is not None and row["status"] in ("READY","DISPATCHING","BLOCKED"),"invalid finalization state")
   manifest=Path(row["manifest"] or "")
   require(manifest.is_file() and file_hash(manifest)==row["manifest_sha256"],"manifest changed/missing")
   mapping=c.execute("SELECT prompt,prompt_id FROM b14_prompt_map ORDER BY prompt").fetchall()
   require(bool(mapping),"no active mapping to archive")
   obj=json.loads(manifest.read_text())
   require(set(x["prompt_id"] for x in mapping)==set(obj["entries"]),"mapping/manifest mismatch")
   jobs=c.execute("""SELECT j.id,j.state,j.output_sha256,j.worker_id,j.prompt,
    a.path,a.sha256 AS artifact_sha,a.worker_id AS artifact_worker
    FROM jobs j JOIN b14_prompt_map m ON m.prompt=j.prompt
    LEFT JOIN b14_artifacts a ON a.job_id=j.id ORDER BY j.id""").fetchall()
   require(bool(jobs),"no jobs tied to session")
   require(all(j["state"] in ("completed","cancelled") for j in jobs),"session has queued/running/uncertain/failed job")
   receipts=[]
   for j in jobs:
    if j["state"]=="cancelled":continue
    p=Path(j["path"] or "")
    require(j["worker_id"] in (0,1) and j["artifact_worker"]==j["worker_id"],"worker receipt mismatch")
    require(p.is_file() and not p.is_symlink() and not p.parent.is_symlink(),"missing/unsafe PNG")
    require(p.parent.resolve()==(self.artifacts/f"worker-{j['worker_id']}").resolve(),
       "PNG outside authorized worker directory")
    digest=file_hash(p)
    require(j["output_sha256"]==j["artifact_sha"]==digest,"artifact SHA mismatch")
    with Image.open(p) as img:
     img.verify()
    with Image.open(p) as img:
     require(img.format=="PNG" and img.size==(1024,1024),"PNG size/format mismatch")
    receipts.append((sid,j["id"],j["worker_id"],digest,str(p)))
   return [(r["prompt"],r["prompt_id"]) for r in mapping],receipts

 def finalize(self,sid):
  mapping,receipts=self.validate_finalize(sid)
  with closing(connect()) as c:
   c.execute("BEGIN IMMEDIATE")
   try:
    require(c.execute("SELECT status FROM b112_sessions WHERE session_id=?",(sid,)).fetchone()[0] in
            ("READY","DISPATCHING","BLOCKED"),"already archived")
    # Fail closed if jobs or map changed during validation.
    current=c.execute("SELECT prompt,prompt_id FROM b14_prompt_map ORDER BY prompt").fetchall()
    require([(x["prompt"],x["prompt_id"]) for x in current]==mapping,"mapping changed")
    placeholders=",".join("?" for _ in mapping)
    prompts=[x[0] for x in mapping]
    current_jobs=c.execute("SELECT id,state FROM jobs WHERE prompt IN ("+placeholders+")",prompts).fetchall()
    require(all(x["state"] in ("completed","cancelled") for x in current_jobs),"job state changed")
    expected_receipts={x[1] for x in receipts}
    require({x["id"] for x in current_jobs if x["state"]=="completed"}==expected_receipts,
            "new/unverified completed job")
    c.executemany("INSERT INTO b112_mapping_history VALUES(?,?,?)",[(sid,*x) for x in mapping])
    c.executemany("INSERT INTO b112_artifact_history VALUES(?,?,?,?,?)",receipts)
    c.execute("DELETE FROM b14_prompt_map")
    c.execute("UPDATE b112_sessions SET status='ARCHIVED',updated_at=? WHERE session_id=?",(time.time(),sid))
    c.execute("COMMIT")
   except BaseException:c.execute("ROLLBACK");raise
  return {"session_id":sid,"status":"ARCHIVED","prompts":len(mapping),"verified_png":len(receipts)}

 def run_one(self,run_dispatch):
  """One bounded cycle. Caller owns mock HTTP servers or real GPU worker lifecycle."""
  with self.exclusive():
   started=self.start()
   if started is None:return {"status":"NO_PENDING"}
   sid,pipeline,prepared=started
   with closing(connect()) as c:
    c.execute("UPDATE b112_sessions SET status='DISPATCHING',updated_at=? WHERE session_id=?",(time.time(),sid))
   try:
    result=run_dispatch(pipeline,sid)
    archived=self.finalize(sid)
    return {"status":"SESSION_ARCHIVED","prepare":prepared,"dispatch":result,"archive":archived}
   except BaseException:
    with closing(connect()) as c:
     c.execute("UPDATE b112_sessions SET status='BLOCKED',updated_at=? WHERE session_id=? AND status!='ARCHIVED'",(time.time(),sid))
    raise

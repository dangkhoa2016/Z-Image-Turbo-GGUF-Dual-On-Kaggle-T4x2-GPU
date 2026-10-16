"""B1.13 integrated shared-DB session controller. Additive; no historical mutation."""
import hashlib,json,os,subprocess,sys,time,uuid
from contextlib import closing
from pathlib import Path
from PIL import Image
from b112_lifecycle import Lifecycle,require,RolloverBlocked
from http_dispatcher import connect
from embedding_registry import Registry
from dynamic_manifest import export_manifest,read_manifest
from worker_adapter import file_hash

class SharedLifecycle(Lifecycle):
 def __init__(self,**kwargs):
  super().__init__(**kwargs)
  with closing(connect()) as c:
   c.execute("CREATE TABLE IF NOT EXISTS b113_active_prompts(prompt TEXT PRIMARY KEY,session_id TEXT NOT NULL)")
   c.execute("CREATE TABLE IF NOT EXISTS b113_session_jobs(session_id TEXT NOT NULL,job_id TEXT NOT NULL UNIQUE,PRIMARY KEY(session_id,job_id))")

 def freeze(self):
  """Freeze exact queued job IDs and prompt gates atomically with admission API."""
  self._idle()
  with closing(connect()) as c:
   c.execute("BEGIN IMMEDIATE")
   try:
    active=c.execute("SELECT session_id FROM b112_sessions WHERE status!='ARCHIVED'").fetchall()
    require(not active,"unresolved session; operator verification required")
    require(c.execute("SELECT COUNT(*) FROM b113_active_prompts").fetchone()[0]==0,"orphan prompt gate")
    require(c.execute("SELECT COUNT(*) FROM b14_prompt_map").fetchone()[0]==0,"orphan mapping")
    require(c.execute("SELECT COUNT(*) FROM jobs WHERE state IN ('running','uncertain','failed')").fetchone()[0]==0,"unresolved jobs")
    prompts=[r[0] for r in c.execute(
      "SELECT prompt FROM jobs WHERE state='queued' GROUP BY prompt ORDER BY MIN(created_at),prompt LIMIT ?",
      (self.max_prompts,)).fetchall()]
    if not prompts:
     c.execute("COMMIT");return None
    query="SELECT id FROM jobs WHERE state='queued' AND prompt IN ("+(",".join("?" for _ in prompts))+") ORDER BY created_at,id"
    ids=[r[0] for r in c.execute(query,prompts)]
    require(0<len(ids)<=self.max_jobs,"session exceeds job limit")
    sid="b112-"+uuid.uuid4().hex; now=time.time()
    c.execute("INSERT INTO b112_sessions VALUES(?,?,?,?,?,?,?)",(sid,"PREPARING",now,now,None,None,self.mode))
    c.executemany("INSERT INTO b113_active_prompts VALUES(?,?)",[(p,sid) for p in prompts])
    c.executemany("INSERT INTO b113_session_jobs VALUES(?,?)",[(sid,jid) for jid in ids])
    c.execute("COMMIT");return sid,prompts,ids
   except BaseException:c.execute("ROLLBACK");raise

 def prepare_frozen(self,sid,prompts,ids):
  """Encode only the frozen prompt list; never scan the queue again."""
  folder=self.root/sid
  session=folder/"session";session.mkdir(parents=True,exist_ok=False)
  cache=folder/"cache";regdb=folder/"registry.sqlite3"
  identity_path=session/"b18-encoder-identity.json"
  prompt_path=session/"b18-encoder-prompts.json"
  identity_path.write_text(json.dumps(self.identity,sort_keys=True))
  prompt_path.write_text(json.dumps(prompts,ensure_ascii=False))
  proc=subprocess.run([sys.executable,str(Path(__file__).with_name("phase_controller.py")),
   "--db",str(regdb),"--cache-root",str(cache),"--identity",str(identity_path),
   "--prompt-json",str(prompt_path),"--mode",self.mode,"--max-items",str(self.max_prompts)],
   capture_output=True,text=True,timeout=3600)
  if proc.returncode:raise RolloverBlocked("encoder phase failed: "+proc.stderr[-1000:])
  phase=json.loads((folder/"b16-phase-status.json").read_text())
  require(phase.get("status")=="READY_FOR_INFERENCE_START" and phase.get("mode")==self.mode,"encoder phase not READY")
  reg=Registry(regdb,cache,self.identity)
  manifest=session/"b18-inference-manifest.json"
  export_manifest(reg,prompts,manifest,allow_mock=self.mode=="cpu-mock")
  checked=read_manifest(manifest,allow_mock=self.mode=="cpu-mock")
  require(set(checked["entries"])=={reg.key(p) for p in prompts},"manifest prompt mismatch")
  digest=file_hash(manifest)
  with closing(connect()) as c:
   c.execute("BEGIN IMMEDIATE")
   try:
    require(c.execute("SELECT status FROM b112_sessions WHERE session_id=?",(sid,)).fetchone()[0]=="PREPARING","session status changed")
    found=[r[0] for r in c.execute("SELECT job_id FROM b113_session_jobs WHERE session_id=? ORDER BY job_id",(sid,))]
    require(sorted(found)==sorted(ids),"snapshot jobs changed")
    for p in prompts:
     require(c.execute("SELECT session_id FROM b113_active_prompts WHERE prompt=?",(p,)).fetchone()[0]==sid,"prompt gate changed")
     c.execute("INSERT INTO b14_prompt_map(prompt,prompt_id) VALUES(?,?)",(p,reg.key(p)))
    c.execute("UPDATE b112_sessions SET status='READY',manifest=?,manifest_sha256=?,updated_at=? WHERE session_id=?",
       (str(manifest),digest,time.time(),sid))
    c.execute("COMMIT")
   except BaseException:c.execute("ROLLBACK");raise
  return {"session_id":sid,"manifest":str(manifest),"manifest_sha256":digest,"frozen_prompts":len(prompts),"frozen_jobs":len(ids)}

 def finish(self,sid):
  """Verify every exact frozen job, then archive receipts and release gates atomically."""
  self._idle()
  with closing(connect()) as c:
   c.execute("BEGIN IMMEDIATE")
   try:
    s=c.execute("SELECT * FROM b112_sessions WHERE session_id=?",(sid,)).fetchone()
    require(s is not None and s["status"]=="DISPATCHING","session not dispatching")
    manifest=Path(s["manifest"])
    require(manifest.is_file() and file_hash(manifest)==s["manifest_sha256"],"manifest changed")
    obj=read_manifest(manifest,allow_mock=self.mode=="cpu-mock")
    mapped=c.execute("SELECT m.prompt,m.prompt_id FROM b14_prompt_map m JOIN b113_active_prompts a ON a.prompt=m.prompt WHERE a.session_id=? ORDER BY m.prompt",(sid,)).fetchall()
    require(mapped and {r["prompt_id"] for r in mapped}==set(obj["entries"]),"session mapping mismatch")
    require(c.execute("SELECT COUNT(*) FROM b14_prompt_map").fetchone()[0]==len(mapped),"foreign mapping present")
    frozen=c.execute("""SELECT j.id,j.state,j.worker_id,j.output_sha256,j.prompt,
       a.path,a.worker_id AS receipt_worker,a.sha256 AS receipt_sha
       FROM b113_session_jobs sj JOIN jobs j ON j.id=sj.job_id
       LEFT JOIN b14_artifacts a ON a.job_id=j.id WHERE sj.session_id=? ORDER BY j.id""",(sid,)).fetchall()
    require(frozen and all(r["state"] in ("completed","cancelled") for r in frozen),"nonterminal frozen job")
    receipts=[]
    for j in frozen:
     require(j["prompt"] in {x["prompt"] for x in mapped},"frozen job prompt changed")
     if j["state"]=="cancelled":continue
     p=Path(j["path"] or "")
     require(j["worker_id"] in (0,1) and j["receipt_worker"]==j["worker_id"],"worker ID mismatch")
     require(p.is_file() and not p.is_symlink() and not p.parent.is_symlink(),"missing/unsafe PNG")
     require(p.parent.resolve()==(self.artifacts/f"worker-{j['worker_id']}").resolve(),"artifact path escape")
     sha=file_hash(p)
     require(sha==j["output_sha256"]==j["receipt_sha"],"artifact SHA mismatch")
     with Image.open(p) as im:im.verify()
     with Image.open(p) as im:require(im.format=="PNG" and im.size==(1024,1024),"invalid PNG")
     receipts.append((sid,j["id"],j["worker_id"],sha,str(p)))
    c.executemany("INSERT INTO b112_mapping_history VALUES(?,?,?)",[(sid,x["prompt"],x["prompt_id"]) for x in mapped])
    c.executemany("INSERT INTO b112_artifact_history VALUES(?,?,?,?,?)",receipts)
    c.execute("DELETE FROM b14_prompt_map")
    c.execute("DELETE FROM b113_active_prompts WHERE session_id=?",(sid,))
    c.execute("UPDATE b112_sessions SET status='ARCHIVED',updated_at=? WHERE session_id=?",(time.time(),sid))
    c.execute("COMMIT")
    return {"session_id":sid,"status":"ARCHIVED","verified_png":len(receipts),"frozen_jobs":len(frozen)}
   except BaseException:c.execute("ROLLBACK");raise

 def run_one(self,dispatch_cb):
  """Call with an exclusive lifecycle lock; dispatch_cb owns worker startup/cleanup."""
  with self.exclusive():
   frozen=self.freeze()
   if frozen is None:return {"status":"NO_PENDING"}
   sid,prompts,ids=frozen
   try:
    prepared=self.prepare_frozen(sid,prompts,ids)
    with closing(connect()) as c:
     c.execute("UPDATE b112_sessions SET status='DISPATCHING',updated_at=? WHERE session_id=? AND status='READY'",(time.time(),sid))
    outcome=dispatch_cb(sid,prepared)
    archived=self.finish(sid)
    return {"status":"B113_SESSION_ARCHIVED","prepare":prepared,"dispatch":outcome,"archive":archived}
   except BaseException:
    with closing(connect()) as c:
     c.execute("UPDATE b112_sessions SET status='BLOCKED',updated_at=? WHERE session_id=? AND status!='ARCHIVED'",(time.time(),sid))
    raise

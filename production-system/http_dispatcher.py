"""B1.4 isolated HTTP dispatcher for B1 SQLite and B1.3 verified PNG adapter.
CPU tests use HTTP mocks. No arbitrary-text encoder, no GPU assertion.
"""
import os,time,sqlite3,threading,uuid,fcntl
from pathlib import Path
from contextlib import closing
from worker_adapter import WorkerAdapter
from mock_dispatcher import connect,prepare,event
DB=Path(os.environ.get("ZIMAGE_B1_DB",str(Path(__file__).resolve().parent/"state"/"b1-jobs.sqlite3")))
LOCK=DB.with_suffix(".http-dispatcher.lock")
def prepare_http():
 prepare()
 with closing(connect()) as c:
  c.execute("""CREATE TABLE IF NOT EXISTS b14_artifacts (
    job_id TEXT PRIMARY KEY,worker_id INTEGER NOT NULL,path TEXT NOT NULL,
    sha256 TEXT NOT NULL,created_at REAL NOT NULL)""")
  c.execute("""CREATE TABLE IF NOT EXISTS b14_prompt_map (
    prompt TEXT PRIMARY KEY,prompt_id TEXT UNIQUE NOT NULL)""")
def permit_prompt(prompt,prompt_id):
 """Controlled mapping, provisioned only for previously encoded cache entries."""
 if not isinstance(prompt,str) or not isinstance(prompt_id,str) or not prompt_id.isidentifier():
  raise ValueError("invalid controlled mapping")
 with closing(connect()) as c:
  c.execute("INSERT INTO b14_prompt_map(prompt,prompt_id) VALUES(?,?)",(prompt,prompt_id))
class Dispatcher:
 def __init__(self,adapters,lease=30,heartbeat=2,poll=.03):
  assert set(adapters)=={0,1}
  self.adapters=adapters;self.lease=lease;self.heartbeat=heartbeat;self.poll=poll
  self.owner=str(uuid.uuid4());self.running={}
  prepare_http()
 def reconcile(self):
  with closing(connect()) as c:
   c.execute("BEGIN IMMEDIATE")
   try:
    rows=c.execute("SELECT id FROM jobs WHERE state='running' AND (lease_deadline IS NULL OR lease_deadline<?)",(time.time(),)).fetchall()
    for r in rows:
     n=c.execute("""UPDATE jobs SET state='uncertain',lease_owner=NULL,lease_deadline=NULL,
       last_error='expired lease: no automatic replay',updated_at=? WHERE id=? AND state='running'""",(time.time(),r["id"])).rowcount
     if n:event(c,r["id"],"HTTP_UNCERTAIN_EXPIRED")
    c.execute("COMMIT")
   except BaseException:c.execute("ROLLBACK");raise
   return len(rows)
 def claim(self,slot):
  with closing(connect()) as c:
   c.execute("BEGIN IMMEDIATE")
   try:
    occupied=c.execute("SELECT COUNT(*) FROM jobs WHERE worker_id=? AND state IN ('running','uncertain')",(slot,)).fetchone()[0]
    if occupied:c.execute("COMMIT");return None
    row=c.execute("""SELECT j.*,m.prompt_id FROM jobs j JOIN b14_prompt_map m ON m.prompt=j.prompt
      WHERE j.state='queued' ORDER BY j.created_at,j.id LIMIT 1""").fetchone()
    if row is None:c.execute("COMMIT");return None
    n=c.execute("""UPDATE jobs SET state='running',worker_id=?,attempt=attempt+1,
      lease_owner=?,lease_deadline=?,updated_at=? WHERE id=? AND state='queued'""",
      (slot,self.owner,time.time()+self.lease,time.time(),row["id"])).rowcount
    assert n==1
    event(c,row["id"],f"HTTP_CLAIM_{slot}")
    c.execute("COMMIT");return dict(row)
   except BaseException:c.execute("ROLLBACK");raise
 def execute(self,job,slot):
  stop=threading.Event()
  def beat():
   with closing(connect()) as c:
    while not stop.wait(self.heartbeat):
     c.execute("UPDATE jobs SET lease_deadline=?,updated_at=? WHERE id=? AND state='running' AND lease_owner=?",
       (time.time()+self.lease,time.time(),job["id"],self.owner))
  t=threading.Thread(target=beat,daemon=True);t.start()
  try:
   result=self.adapters[slot].generate(job["prompt_id"],job["seed"])
   if result["worker_id"]!=slot or result["prompt_id"]!=job["prompt_id"] or result["seed"]!=job["seed"]:
    raise ValueError("adapter identity invalid")
   with closing(connect()) as c:
    c.execute("BEGIN IMMEDIATE")
    try:
     n=c.execute("""UPDATE jobs SET state='completed',output_sha256=?,lease_owner=NULL,lease_deadline=NULL,
       last_error=NULL,updated_at=? WHERE id=? AND state='running' AND lease_owner=?""",
       (result["output_sha256"],time.time(),job["id"],self.owner)).rowcount
     if n:
      c.execute("INSERT INTO b14_artifacts(job_id,worker_id,path,sha256,created_at) VALUES(?,?,?,?,?)",
        (job["id"],slot,result["output_path"],result["output_sha256"],time.time()))
      event(c,job["id"],"HTTP_PNG_VERIFIED")
     else:event(c,job["id"],"HTTP_STALE_RESULT_REJECTED")
     c.execute("COMMIT")
    except BaseException:c.execute("ROLLBACK");raise
  except Exception as exc:
   with closing(connect()) as c:
    c.execute("BEGIN IMMEDIATE")
    try:
     n=c.execute("""UPDATE jobs SET state='uncertain',lease_owner=NULL,lease_deadline=NULL,
       last_error=?,updated_at=? WHERE id=? AND state='running' AND lease_owner=?""",
       (str(type(exc).__name__)+": "+str(exc),time.time(),job["id"],self.owner)).rowcount
     if n:event(c,job["id"],"HTTP_FAILURE_UNCERTAIN")
     c.execute("COMMIT")
    except BaseException:c.execute("ROLLBACK");raise
  finally:stop.set();t.join(timeout=self.heartbeat+2)
 def drain(self,timeout=15):
  with LOCK.open("a+") as f:
   try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
   except BlockingIOError:raise RuntimeError("HTTP dispatcher already running")
   end=time.monotonic()+timeout
   while time.monotonic()<end:
    self.reconcile()
    for slot in (0,1):
     t=self.running.get(slot)
     if t and not t.is_alive():t.join();del self.running[slot]
     if slot in self.running:continue
     if not self.adapters[slot].ready():continue
     j=self.claim(slot)
     if j:
      t=threading.Thread(target=self.execute,args=(j,slot));self.running[slot]=t;t.start()
    with closing(connect()) as c:
     pending=c.execute("""SELECT COUNT(*) FROM jobs j JOIN b14_prompt_map m ON j.prompt=m.prompt WHERE j.state='queued'""").fetchone()[0]
    if not pending and not any(t.is_alive() for t in self.running.values()):break
    if pending and not any(t.is_alive() for t in self.running.values()):
     blocked=True
     with closing(connect()) as c:
      for slot in (0,1):
       if self.adapters[slot].ready() and not c.execute("SELECT 1 FROM jobs WHERE worker_id=? AND state IN ('running','uncertain')",(slot,)).fetchone():blocked=False
     if blocked:break
    time.sleep(self.poll)
   else:raise TimeoutError("HTTP integration did not reach idle")
   for t in self.running.values():t.join()
   with closing(connect()) as c:
    return {"states":{r[0]:r[1] for r in c.execute("SELECT state,COUNT(*) FROM jobs GROUP BY state")},
      "verified_artifacts":c.execute("SELECT COUNT(*) FROM b14_artifacts").fetchone()[0],
      "execution":"HTTP_INTEGRATION_CPU_MOCK"}

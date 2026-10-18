#!/usr/bin/env python3
"""CPU-only dual-slot test dispatcher; does not run GPU inference or write generated PNGs.

Uses the B1 API SQLite schema, added mock-only receipts and lease columns.
Fail closed: an expired running task becomes UNCERTAIN, never automatically retried.
"""
import argparse,fcntl,hashlib,json,os,sqlite3,threading,time,uuid
from contextlib import closing
from pathlib import Path
DB=Path(os.environ.get("ZIMAGE_B1_DB",str(Path(__file__).resolve().parent/"state"/"b1-jobs.sqlite3")))
ROOT=Path(__file__).resolve().parent
LOCKFILE=DB.with_suffix(".dispatcher.lock")
def connect():
 c=sqlite3.connect(DB,timeout=15,isolation_level=None,check_same_thread=False)
 c.row_factory=sqlite3.Row
 c.execute("PRAGMA busy_timeout=15000")
 c.execute("PRAGMA journal_mode=WAL")
 return c
def prepare():
 assert DB.exists(),"B1 service database must already exist"
 with closing(connect()) as c:
  names={x["name"] for x in c.execute("PRAGMA table_info(jobs)")}
  required={"id","prompt","seed","state","attempt","worker_id","output_sha256","last_error"}
  assert required<=names, "Unexpected B1 database schema"
  if "lease_owner" not in names:c.execute("ALTER TABLE jobs ADD COLUMN lease_owner TEXT")
  if "lease_deadline" not in names:c.execute("ALTER TABLE jobs ADD COLUMN lease_deadline REAL")
  c.execute("""CREATE TABLE IF NOT EXISTS b12_mock_receipts (
   job_id TEXT PRIMARY KEY, worker_id INTEGER NOT NULL,
   mock_digest TEXT NOT NULL, received_at REAL NOT NULL,
   FOREIGN KEY(job_id) REFERENCES jobs(id))""")
  c.execute("""CREATE TABLE IF NOT EXISTS b12_events (
   id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL,
   event TEXT NOT NULL, when_at REAL NOT NULL)""")
def event(c,job_id,kind):
 c.execute("INSERT INTO b12_events(job_id,event,when_at) VALUES(?,?,?)",(job_id,kind,time.time()))
class MockWorker:
 """Synthetic CPU worker. Digest is NOT an image digest and never enters output_sha256."""
 def __init__(self,latency=0.10,fail_ids=()):
  self.latency=latency
  self.fail_ids=set(fail_ids)
  self.lock=threading.Lock()
  self.active=set()
  self.peak=0
  self.calls=[]
 def generate(self,job,slot):
  with self.lock:
   assert slot not in self.active,"Duplicate invocation on worker slot"
   self.active.add(slot)
   self.peak=max(self.peak,len(self.active))
   self.calls.append((job["id"],slot))
  try:
   time.sleep(self.latency)
   if job["id"] in self.fail_ids:raise RuntimeError("injected mock worker failure")
   raw=f"MOCK_ONLY|{job['id']}|{job['seed']}|{job['prompt']}|{slot}".encode()
   return hashlib.sha256(raw).hexdigest()
  finally:
   with self.lock:self.active.remove(slot)
class Dispatcher:
 def __init__(self,worker=None,lease_seconds=20,heartbeat_seconds=2,poll=0.03):
  self.worker=worker or MockWorker()
  self.lease_seconds=lease_seconds
  self.heartbeat_seconds=heartbeat_seconds
  self.poll=poll
  self.owner=str(uuid.uuid4())
  self.threads={}
  prepare()
 def reconcile(self):
  """Expired in-flight job is uncertain; never turn uncertain back into queued."""
  with closing(connect()) as c:
   c.execute("BEGIN IMMEDIATE")
   try:
    rows=c.execute("SELECT id FROM jobs WHERE state='running' AND (lease_deadline IS NULL OR lease_deadline<?)",(time.time(),)).fetchall()
    for r in rows:
     n=c.execute("UPDATE jobs SET state='uncertain',lease_owner=NULL,lease_deadline=NULL,last_error=?,updated_at=? WHERE id=? AND state='running'",
          ("lease expired; operator reconciliation required",time.time(),r["id"])).rowcount
     if n:event(c,r["id"],"UNCERTAIN_LEASE_EXPIRED")
    c.execute("COMMIT")
   except BaseException:c.execute("ROLLBACK");raise
   return len(rows)
 def claim(self,slot):
  with closing(connect()) as c:
   c.execute("BEGIN IMMEDIATE")
   try:
    reserved=c.execute("SELECT COUNT(*) FROM jobs WHERE worker_id=? AND state IN ('running','uncertain')",(slot,)).fetchone()[0]
    if reserved:
     c.execute("COMMIT");return None
    row=c.execute("SELECT * FROM jobs WHERE state='queued' ORDER BY created_at,id LIMIT 1").fetchone()
    if row is None:c.execute("COMMIT");return None
    n=c.execute("UPDATE jobs SET state='running',worker_id=?,attempt=attempt+1,lease_owner=?,lease_deadline=?,updated_at=? WHERE id=? AND state='queued'",
      (slot,self.owner,time.time()+self.lease_seconds,time.time(),row["id"])).rowcount
    assert n==1
    event(c,row["id"],"CLAIMED_SLOT_"+str(slot))
    c.execute("COMMIT")
    return dict(row)
   except BaseException:c.execute("ROLLBACK");raise
 def execute(self,job,slot):
  stop=threading.Event()
  def heartbeat():
   with closing(connect()) as c:
    while not stop.wait(self.heartbeat_seconds):
     c.execute("UPDATE jobs SET lease_deadline=?,updated_at=? WHERE id=? AND state='running' AND lease_owner=?",
      (time.time()+self.lease_seconds,time.time(),job["id"],self.owner))
  beat=threading.Thread(target=heartbeat,daemon=True)
  beat.start()
  try:
   mock_digest=self.worker.generate(job,slot)
   with closing(connect()) as c:
    c.execute("BEGIN IMMEDIATE")
    try:
     n=c.execute("UPDATE jobs SET state='completed',lease_owner=NULL,lease_deadline=NULL,last_error=NULL,updated_at=? WHERE id=? AND state='running' AND lease_owner=?",
       (time.time(),job["id"],self.owner)).rowcount
     if n==1:
      c.execute("INSERT INTO b12_mock_receipts(job_id,worker_id,mock_digest,received_at) VALUES(?,?,?,?)",
       (job["id"],slot,mock_digest,time.time()))
      event(c,job["id"],"MOCK_COMPLETED")
     else:event(c,job["id"],"STALE_COMPLETION_IGNORED")
     c.execute("COMMIT")
    except BaseException:c.execute("ROLLBACK");raise
  except Exception as exc:
   with closing(connect()) as c:
    c.execute("BEGIN IMMEDIATE")
    try:
     n=c.execute("UPDATE jobs SET state='uncertain',lease_owner=NULL,lease_deadline=NULL,last_error=?,updated_at=? WHERE id=? AND state='running' AND lease_owner=?",
      (type(exc).__name__+": "+str(exc),time.time(),job["id"],self.owner)).rowcount
     if n:event(c,job["id"],"UNCERTAIN_MOCK_FAILURE")
     c.execute("COMMIT")
    except BaseException:c.execute("ROLLBACK");raise
  finally:
   stop.set();beat.join(timeout=max(1,self.heartbeat_seconds+1))
 def run_until_idle(self,max_seconds=30):
  """One dispatcher process at a time. Do not use against live GPU workers."""
  LOCKFILE.parent.mkdir(exist_ok=True,parents=True)
  with LOCKFILE.open("a+") as lock:
   try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
   except BlockingIOError:raise RuntimeError("dispatcher already active")
   deadline=time.monotonic()+max_seconds
   while time.monotonic()<deadline:
    self.reconcile()
    for slot in (0,1):
     th=self.threads.get(slot)
     if th is not None and not th.is_alive():th.join();del self.threads[slot]
     if slot in self.threads:continue
     job=self.claim(slot)
     if job is not None:
      th=threading.Thread(target=self.execute,args=(job,slot),name=f"mock-slot-{slot}")
      self.threads[slot]=th;th.start()
    with closing(connect()) as c:
     queued=c.execute("SELECT COUNT(*) FROM jobs WHERE state='queued'").fetchone()[0]
    if queued==0 and not any(t.is_alive() for t in self.threads.values()):break
    if queued and not any(t.is_alive() for t in self.threads.values()):
     # All slots blocked by uncertain tasks. Exit safely, no retries.
     break
    time.sleep(self.poll)
   else:raise TimeoutError("mock queue drain exceeded configured time")
   for thread in self.threads.values():thread.join()
   with closing(connect()) as c:
    counts={r[0]:r[1] for r in c.execute("SELECT state,COUNT(*) FROM jobs GROUP BY state")}
    mock_receipts=c.execute("SELECT COUNT(*) FROM b12_mock_receipts").fetchone()[0]
   return {"states":counts,"mock_receipts":mock_receipts,"peak_mock_concurrency":self.worker.peak,
           "gpu_inference":"NOT_CONNECTED","real_png_outputs":0}
def operator_requeue(job_id,*,confirmed_worker_stopped=False,checked_no_artifact=False):
 """Manual-only; caller must ensure stopped worker and no valid artifact before reset."""
 if not confirmed_worker_stopped or not checked_no_artifact:
  raise PermissionError("Operator evidence of stopped worker and no artifact required")
 with closing(connect()) as c:
  c.execute("BEGIN IMMEDIATE")
  try:
   row=c.execute("SELECT * FROM jobs WHERE id=?",(job_id,)).fetchone()
   if row is None or row["state"]!="uncertain":raise ValueError("Only uncertain job may be manually requeued")
   if c.execute("SELECT 1 FROM b12_mock_receipts WHERE job_id=?",(job_id,)).fetchone():
    raise RuntimeError("Mock completion receipt exists; cannot retry")
   n=c.execute("UPDATE jobs SET state='queued',worker_id=NULL,lease_owner=NULL,lease_deadline=NULL,last_error='manual mock retry after reconciliation',updated_at=? WHERE id=? AND state='uncertain'",
     (time.time(),job_id)).rowcount
   assert n==1
   event(c,job_id,"OPERATOR_REQUEUED")
   c.execute("COMMIT")
  except BaseException:c.execute("ROLLBACK");raise
if __name__=="__main__":
 p=argparse.ArgumentParser()
 p.add_argument("--max-seconds",type=float,default=30)
 args=p.parse_args()
 result=Dispatcher().run_until_idle(max_seconds=args.max_seconds)
 print(json.dumps(result,sort_keys=True),flush=True)

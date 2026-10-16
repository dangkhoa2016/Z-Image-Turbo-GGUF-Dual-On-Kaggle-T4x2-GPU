"""B1.13 local-only admission API for shared SQLite.

Use THIS app for POST /v1/jobs while B1.13 lifecycle is enabled.
The legacy service.app bypasses this admission gate; do not expose it concurrently.
"""
import hmac,sqlite3,time,uuid
from fastapi import FastAPI,Depends,Header,HTTPException
import service

app=FastAPI(title="Z-Image B1.13 guarded admission",version="0.1.13-cpu-contract")
DB=service.DB
def connection():
 c=sqlite3.connect(DB,timeout=15,isolation_level=None)
 c.row_factory=sqlite3.Row
 c.execute("PRAGMA busy_timeout=15000")
 c.execute("PRAGMA journal_mode=WAL")
 return c
def initialize():
 with connection() as c:
  c.execute("""CREATE TABLE IF NOT EXISTS b113_active_prompts(
    prompt TEXT PRIMARY KEY,session_id TEXT NOT NULL)""")
  c.execute("""CREATE TABLE IF NOT EXISTS b113_session_jobs(
    session_id TEXT NOT NULL,job_id TEXT NOT NULL UNIQUE,PRIMARY KEY(session_id,job_id))""")
initialize()

@app.get("/health")
def health():
 return {"status":"ok","backend":"SHARED_SQLITE_B113","inference":"NOT_AUTOMATICALLY_STARTED"}

@app.post("/v1/jobs",status_code=201,dependencies=[Depends(service.auth)])
def submit(body:service.JobIn,idempotency_key:str|None=Header(default=None,alias="Idempotency-Key")):
 if idempotency_key is not None and not 8<=len(idempotency_key)<=128:
  raise HTTPException(422,"Idempotency-Key must be 8..128 characters")
 with connection() as c:
  c.execute("BEGIN IMMEDIATE")
  try:
   if idempotency_key:
    old=c.execute("SELECT * FROM jobs WHERE idempotency_key=?",(idempotency_key,)).fetchone()
    if old is not None:
     if old["prompt"]!=body.prompt or old["seed"]!=body.seed:
      raise HTTPException(409,"Idempotency key conflict")
     c.execute("COMMIT");return service.view(old)
   if c.execute("SELECT 1 FROM b113_active_prompts WHERE prompt=?",(body.prompt,)).fetchone():
    raise HTTPException(423,"This exact prompt belongs to an active inference session; resubmit after rollover")
   queued=c.execute("SELECT COUNT(*) FROM jobs WHERE state='queued'").fetchone()[0]
   if queued>=100:raise HTTPException(429,"Queue full")
   jid=str(uuid.uuid4());now=time.time()
   c.execute("INSERT INTO jobs(id,prompt,seed,state,idempotency_key,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
      (jid,body.prompt,body.seed,"queued",idempotency_key,now,now))
   row=c.execute("SELECT * FROM jobs WHERE id=?",(jid,)).fetchone()
   c.execute("COMMIT");return service.view(row)
  except BaseException:
   c.execute("ROLLBACK");raise

app.add_api_route("/v1/jobs/{job_id}",service.get_job,methods=["GET"],dependencies=[Depends(service.auth)])
app.add_api_route("/v1/jobs",service.list_jobs,methods=["GET"],dependencies=[Depends(service.auth)])
app.add_api_route("/v1/jobs/{job_id}/cancel",service.cancel,methods=["POST"],dependencies=[Depends(service.auth)])

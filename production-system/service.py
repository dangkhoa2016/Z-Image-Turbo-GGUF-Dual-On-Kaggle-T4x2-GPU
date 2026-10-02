"""SQLite-backed job control plane. GPU inference runs in separate isolated workers."""
import os,sqlite3,time,uuid,hmac,threading
from pathlib import Path
from fastapi import FastAPI,Header,HTTPException,Depends,Query
from pydantic import BaseModel,Field
ROOT=Path(__file__).resolve().parent
DB=Path(os.getenv("ZIMAGE_B1_DB",str(ROOT/"state"/"b1-jobs.sqlite3")))
API_KEY=os.getenv("ZIMAGE_B1_API_KEY","")
if not API_KEY or len(API_KEY)<24:raise RuntimeError("Provide ZIMAGE_B1_API_KEY as a 24+ character secret")
DB.parent.mkdir(parents=True,exist_ok=True)
app=FastAPI(title="Z-Image Kaggle T4x2 Job API",version="0.1.0-b1-cpu",description="CPU-only job lifecycle; inference NOT connected")
LOCK=threading.RLock()
class JobIn(BaseModel):
 prompt:str=Field(min_length=3,max_length=2000)
 seed:int=Field(ge=0,le=4294967295)
 width:int=Field(default=1024,ge=1024,le=1024)
 height:int=Field(default=1024,ge=1024,le=1024)
 steps:int=Field(default=9,ge=9,le=9)
 guidance_scale:float=Field(default=0,ge=0,le=0)
def auth(authorization:str=Header(default="")):
 if not hmac.compare_digest(authorization,"Bearer "+API_KEY):raise HTTPException(401,"Unauthorized")
def db():
 c=sqlite3.connect(DB,timeout=15,isolation_level=None)
 c.row_factory=sqlite3.Row;c.execute("PRAGMA busy_timeout=15000");c.execute("PRAGMA journal_mode=WAL")
 return c
def initialize():
 with db() as c:
  c.execute("""CREATE TABLE IF NOT EXISTS jobs (
   id TEXT PRIMARY KEY,prompt TEXT NOT NULL,seed INTEGER NOT NULL,
   state TEXT NOT NULL CHECK(state IN ('queued','running','completed','failed','uncertain','cancelled')),
   idempotency_key TEXT UNIQUE,created_at REAL NOT NULL,updated_at REAL NOT NULL,
   attempt INTEGER NOT NULL DEFAULT 0, worker_id INTEGER,output_sha256 TEXT,last_error TEXT)""")
  c.execute("CREATE INDEX IF NOT EXISTS ix_jobs_state_created ON jobs(state,created_at)")
initialize()
def view(row):
 return {"job_id":row["id"],"state":row["state"],"seed":row["seed"],
  "created_at":row["created_at"],"updated_at":row["updated_at"],
  "attempt":row["attempt"],"worker_id":row["worker_id"],"output_sha256":row["output_sha256"],
  "last_error":row["last_error"],"inference_backend":"NOT_CONNECTED"}
@app.get("/health")
def health():return {"status":"ok","mode":"CPU_CONTROL_PLANE_ONLY","gpu_inference":"NOT_CONNECTED"}
@app.post("/v1/jobs",status_code=201,dependencies=[Depends(auth)])
def submit(body:JobIn,idempotency_key:str|None=Header(default=None,alias="Idempotency-Key")):
 if idempotency_key is not None and not 8<=len(idempotency_key)<=128:raise HTTPException(422,"Idempotency-Key must be 8..128 characters")
 now=time.time()
 with LOCK,db() as c:
  c.execute("BEGIN IMMEDIATE")
  try:
   if idempotency_key:
    prev=c.execute("SELECT * FROM jobs WHERE idempotency_key=?",(idempotency_key,)).fetchone()
    if prev:
     if prev["prompt"]!=body.prompt or prev["seed"]!=body.seed:raise HTTPException(409,"Idempotency key conflict")
     c.execute("COMMIT");return view(prev)
   queued=c.execute("SELECT COUNT(*) FROM jobs WHERE state='queued'").fetchone()[0]
   if queued>=100:raise HTTPException(429,"Queue full")
   jid=str(uuid.uuid4())
   c.execute("INSERT INTO jobs(id,prompt,seed,state,idempotency_key,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
       (jid,body.prompt,body.seed,"queued",idempotency_key,now,now))
   row=c.execute("SELECT * FROM jobs WHERE id=?",(jid,)).fetchone()
   c.execute("COMMIT");return view(row)
  except BaseException:c.execute("ROLLBACK");raise
@app.get("/v1/jobs/{job_id}",dependencies=[Depends(auth)])
def get_job(job_id:str):
 with db() as c:row=c.execute("SELECT * FROM jobs WHERE id=?",(job_id,)).fetchone()
 if row is None:raise HTTPException(404,"Job not found")
 return view(row)
@app.get("/v1/jobs",dependencies=[Depends(auth)])
def list_jobs(limit:int=Query(default=20,ge=1,le=100)):
 with db() as c:rows=c.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?",(limit,)).fetchall()
 return {"jobs":[view(x) for x in rows]}
@app.post("/v1/jobs/{job_id}/cancel",dependencies=[Depends(auth)])
def cancel(job_id:str):
 with LOCK,db() as c:
  n=c.execute("UPDATE jobs SET state='cancelled',updated_at=? WHERE id=? AND state='queued'",(time.time(),job_id)).rowcount
  row=c.execute("SELECT * FROM jobs WHERE id=?",(job_id,)).fetchone()
 if row is None:raise HTTPException(404,"Job not found")
 if not n and row["state"]!="cancelled":raise HTTPException(409,"Only queued jobs can be safely cancelled")
 return view(row)

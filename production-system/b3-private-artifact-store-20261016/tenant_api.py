"""Isolated B3 multi-tenant API: B1.13 admission logic, owner-bound private artifacts, no GPU."""
import os,sys,time,uuid,hmac,hashlib,sqlite3
from pathlib import Path
from fastapi import FastAPI,Header,Depends,HTTPException,Response
from fastapi.responses import Response as BinaryResponse
HERE=Path(__file__).resolve().parent
BASE=HERE.parent
sys.path.insert(0,str(BASE))
sys.path.insert(0,str(HERE))
import service
from store import Store
DB=service.DB
ROOT=Path(os.environ.get("ZIMAGE_B3_ARTIFACT_ROOT",str(HERE/"private-state")))
TENANTS=os.environ.get("ZIMAGE_B3_TENANTS_JSON","")
import json
AUTH=json.loads(TENANTS) if TENANTS else {}
if not AUTH or any(not isinstance(v,str) or len(v)<24 for v in AUTH.values()):
 raise RuntimeError("ZIMAGE_B3_TENANTS_JSON must map tenant IDs to 24+ char private secrets")
if len(set(AUTH.values()))!=len(AUTH):raise RuntimeError("Duplicate tenant credentials")
store=Store(ROOT)
app=FastAPI(title="Z-Image private tenant adapter",version="B3 CPU contract",docs_url=None,redoc_url=None,openapi_url=None)
def connect():
 c=service.db()
 c.execute("CREATE TABLE IF NOT EXISTS b113_active_prompts(prompt TEXT PRIMARY KEY,session_id TEXT NOT NULL)")
 c.execute("CREATE TABLE IF NOT EXISTS b113_session_jobs(session_id TEXT NOT NULL,job_id TEXT NOT NULL UNIQUE,PRIMARY KEY(session_id,job_id))")
 c.execute("CREATE TABLE IF NOT EXISTS b3_job_owner(job_id TEXT PRIMARY KEY,owner_id TEXT NOT NULL)")
 c.execute("CREATE INDEX IF NOT EXISTS b3_owner_ix ON b3_job_owner(owner_id,job_id)")
 return c
with connect() as c:pass
def tenant(authorization:str=Header(default="")):
 matched=None
 for owner,token in AUTH.items():
  if hmac.compare_digest(authorization,"Bearer "+token):matched=owner
 if matched is None:raise HTTPException(401,"Unauthorized")
 return matched
def owner_job(c,jid,who):
 row=c.execute("SELECT j.* FROM jobs j JOIN b3_job_owner o ON o.job_id=j.id WHERE j.id=? AND o.owner_id=?",(jid,who)).fetchone()
 if row is None:raise HTTPException(404,"Not found")
 return row
def view(row):
 return service.view(row)
@app.get("/health")
def health():return {"status":"ok","mode":"B3_PRIVATE_CPU_ADAPTER","gpu_inference":"NOT_CONNECTED"}
@app.post("/v1/jobs",status_code=201)
def submit(body:service.JobIn,who:str=Depends(tenant),idempotency_key:str|None=Header(default=None,alias="Idempotency-Key")):
 if idempotency_key is not None and not 8<=len(idempotency_key)<=128:raise HTTPException(422,"Invalid idempotency key")
 # DB has global key uniqueness; scope key by tenant with deterministic digest, no plaintext secrets stored.
 scoped=hashlib.sha256((who+"\0"+idempotency_key).encode()).hexdigest() if idempotency_key else None
 with connect() as c:
  c.execute("BEGIN IMMEDIATE")
  try:
   if scoped:
    old=c.execute("SELECT * FROM jobs WHERE idempotency_key=?",(scoped,)).fetchone()
    if old:
     owned=owner_job(c,old["id"],who)
     if any((old["prompt"]!=body.prompt,old["seed"]!=body.seed)):raise HTTPException(409,"Idempotency conflict")
     c.execute("COMMIT");return view(owned)
   if c.execute("SELECT 1 FROM b113_active_prompts WHERE prompt=?",(body.prompt,)).fetchone():
    raise HTTPException(423,"Prompt currently in active session")
   if c.execute("SELECT COUNT(*) FROM jobs WHERE state='queued'").fetchone()[0]>=100:raise HTTPException(429,"Queue full")
   jid=str(uuid.uuid4());now=time.time()
   c.execute("INSERT INTO jobs(id,prompt,seed,state,idempotency_key,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",(jid,body.prompt,body.seed,"queued",scoped,now,now))
   c.execute("INSERT INTO b3_job_owner(job_id,owner_id) VALUES(?,?)",(jid,who))
   row=owner_job(c,jid,who)
   c.execute("COMMIT");return view(row)
  except BaseException:c.execute("ROLLBACK");raise
@app.get("/v1/jobs")
def list_jobs(who:str=Depends(tenant)):
 with connect() as c:
  rows=c.execute("SELECT j.* FROM jobs j JOIN b3_job_owner o ON o.job_id=j.id WHERE o.owner_id=? ORDER BY j.created_at DESC LIMIT 100",(who,)).fetchall()
 return {"jobs":[view(r) for r in rows]}
@app.get("/v1/jobs/{job_id}")
def get_job(job_id:str,who:str=Depends(tenant)):
 with connect() as c:return view(owner_job(c,job_id,who))
@app.post("/v1/jobs/{job_id}/cancel")
def cancel(job_id:str,who:str=Depends(tenant)):
 with connect() as c:
  c.execute("BEGIN IMMEDIATE")
  try:
   row=owner_job(c,job_id,who)
   if row["state"] not in ("queued","cancelled"):raise HTTPException(409,"Only queued jobs can cancel")
   if row["state"]=="queued":
    c.execute("UPDATE jobs SET state='cancelled',updated_at=? WHERE id=? AND state='queued'",(time.time(),job_id))
   row=owner_job(c,job_id,who)
   c.execute("COMMIT");return view(row)
  except BaseException:c.execute("ROLLBACK");raise
@app.get("/v1/jobs/{job_id}/image")
def get_image(job_id:str,who:str=Depends(tenant)):
 with connect() as c:
  row=owner_job(c,job_id,who)
  if row["state"]!="completed":raise HTTPException(409,"Job not completed")
 try:data=store.get(job_id,who)
 except LookupError:raise HTTPException(404,"Image not published")
 except (RuntimeError,OSError):raise HTTPException(503,"Image integrity unavailable")
 digest=hashlib.sha256(data).hexdigest()
 if digest!=row["output_sha256"]:raise HTTPException(503,"Receipt SHA mismatch")
 return BinaryResponse(content=data,media_type="image/png",headers={"Cache-Control":"private, no-store","X-Content-Type-Options":"nosniff","Content-Disposition":"attachment; filename=result.png"})
# Publishing has deliberately NO public HTTP endpoint. Controlled internal reconciliation only:
def reconcile_completed(job_id,worker_png):
 with connect() as c:
  row=c.execute("SELECT j.id,j.state,j.output_sha256,o.owner_id,a.sha256,a.path FROM jobs j JOIN b3_job_owner o ON o.job_id=j.id JOIN b14_artifacts a ON a.job_id=j.id WHERE j.id=?",(job_id,)).fetchone()
 if row is None or row["state"]!="completed":raise RuntimeError("No completed owned worker receipt")
 png=Path(worker_png).resolve(strict=True)
 if png!=Path(row["path"]).resolve(strict=True):raise RuntimeError("Untrusted artifact path")
 raw=png.read_bytes()
 digest=hashlib.sha256(raw).hexdigest()
 if digest!=row["output_sha256"] or digest!=row["sha256"]:raise RuntimeError("Receipt digest mismatch")
 return store.put(job_id,row["owner_id"],raw)

import os,tempfile,importlib.util,secrets,concurrent.futures,sqlite3
from pathlib import Path
from fastapi.testclient import TestClient
secret=secrets.token_urlsafe(32)
with tempfile.TemporaryDirectory(prefix="zimage-b1-test-") as td:
 os.environ["ZIMAGE_B1_DB"]=str(Path(td)/"jobs.sqlite3")
 os.environ["ZIMAGE_B1_API_KEY"]=secret
 spec=importlib.util.spec_from_file_location("b1_service",Path(__file__).with_name("service.py"))
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 c=TestClient(module.app);headers={"Authorization":"Bearer "+secret}
 body={"prompt":"A detailed photorealistic bicycle beside a wooden porch","seed":45}
 assert c.get("/health").json()["gpu_inference"]=="NOT_CONNECTED"
 assert c.get("/v1/jobs").status_code==401
 assert c.post("/v1/jobs",json=body).status_code==401
 assert c.post("/v1/jobs",headers=headers,json={"prompt":"x","seed":1}).status_code==422
 assert c.post("/v1/jobs",headers=headers,json={**body,"steps":100}).status_code==422
 key={**headers,"Idempotency-Key":"test-key-001"}
 r=c.post("/v1/jobs",headers=key,json=body);assert r.status_code==201,r.text
 jid=r.json()["job_id"];assert r.json()["state"]=="queued"
 q=c.post("/v1/jobs",headers=key,json=body);assert q.status_code==201 and q.json()["job_id"]==jid
 assert c.post("/v1/jobs",headers=key,json={**body,"seed":46}).status_code==409
 assert c.get("/v1/jobs/"+jid,headers=headers).json()["state"]=="queued"
 assert c.get("/v1/jobs/"+str(jid)+"notfound",headers=headers).status_code==404
 assert len(c.get("/v1/jobs",headers=headers).json()["jobs"])==1
 done=c.post(f"/v1/jobs/{jid}/cancel",headers=headers);assert done.status_code==200 and done.json()["state"]=="cancelled"
 assert c.post(f"/v1/jobs/{jid}/cancel",headers=headers).status_code==200
 assert c.get("/v1/jobs/"+jid,headers=headers).json()["state"]=="cancelled"
 def create(i):
  h={**headers,"Idempotency-Key":"shared-race-0001"}
  return c.post("/v1/jobs",headers=h,json={**body,"seed":999}).json()["job_id"]
 with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:ids=list(pool.map(create,range(20)))
 assert len(set(ids))==1
 with sqlite3.connect(os.environ["ZIMAGE_B1_DB"]) as conn:
  assert conn.execute("PRAGMA integrity_check").fetchone()[0]=="ok"
  assert conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]==2
 print("B1_CPU_TEST_PASS auth validation create lookup list cancel idempotency conflict concurrency WAL")
 print("B1_TEST_DB_ISOLATED=YES")
 print("GPU_INFERENCE_NOT_CONNECTED=YES")

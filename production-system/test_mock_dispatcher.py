import os,tempfile,importlib.util,secrets,time,sqlite3
from pathlib import Path
from fastapi.testclient import TestClient
with tempfile.TemporaryDirectory(prefix="zimage-b12-") as td:
 os.environ["ZIMAGE_B1_DB"]=str(Path(td)/"jobs.sqlite3")
 os.environ["ZIMAGE_B1_API_KEY"]=secrets.token_urlsafe(30)
 def load(name):
  spec=importlib.util.spec_from_file_location(name,Path(__file__).with_name(name+".py"))
  mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
 service=load("service")
 md=load("mock_dispatcher")
 c=TestClient(service.app);h={"Authorization":"Bearer "+os.environ["ZIMAGE_B1_API_KEY"]}
 def create(n):
  r=c.post("/v1/jobs",headers=h,json={"prompt":f"Synthetic mock image scene {n}","seed":n})
  assert r.status_code==201,r.text
  return r.json()["job_id"]
 ids=[create(i) for i in range(6)]
 worker=md.MockWorker(latency=.15)
 result=md.Dispatcher(worker=worker).run_until_idle()
 assert result["states"]=={"completed":6},result
 assert result["mock_receipts"]==6 and result["peak_mock_concurrency"]==2,result
 assert result["real_png_outputs"]==0 and result["gpu_inference"]=="NOT_CONNECTED"
 assert {i for _,i in worker.calls}=={0,1}
 for jid in ids:
  j=c.get("/v1/jobs/"+jid,headers=h).json()
  assert j["state"]=="completed" and j["output_sha256"] is None
 assert md.Dispatcher(worker=md.MockWorker()).run_until_idle()["mock_receipts"]==6
 assert sum(j[0]==ids[0] for j in worker.calls)==1
 failure=create(20)
 worker2=md.MockWorker(latency=.03,fail_ids={failure})
 res2=md.Dispatcher(worker=worker2).run_until_idle()
 assert res2["states"]["uncertain"]==1,res2
 assert c.get("/v1/jobs/"+failure,headers=h).json()["state"]=="uncertain"
 assert c.post(f"/v1/jobs/{failure}/cancel",headers=h).status_code==409
 assert md.Dispatcher(worker=md.MockWorker()).run_until_idle()["states"]["uncertain"]==1
 try:md.operator_requeue(failure)
 except PermissionError:pass
 else:raise AssertionError("unsafe manual retry allowed")
 md.operator_requeue(failure,confirmed_worker_stopped=True,checked_no_artifact=True)
 assert c.get("/v1/jobs/"+failure,headers=h).json()["state"]=="queued"
 res3=md.Dispatcher(worker=md.MockWorker()).run_until_idle()
 assert res3["states"]=={"completed":7},res3
 with md.connect() as d:
  assert d.execute("PRAGMA integrity_check").fetchone()[0]=="ok"
  assert d.execute("SELECT COUNT(*) FROM b12_mock_receipts").fetchone()[0]==7
  assert d.execute("SELECT COUNT(*) FROM jobs WHERE output_sha256 IS NOT NULL").fetchone()[0]==0
  assert d.execute("SELECT COUNT(*) FROM b12_events WHERE event='OPERATOR_REQUEUED'").fetchone()[0]==1
 # isolated stale "running" after dispatcher crash: must be uncertain, no replay
 stale=create(40)
 with md.connect() as d:
  d.execute("UPDATE jobs SET state='running',worker_id=0,lease_owner='dead-owner',lease_deadline=?,updated_at=? WHERE id=?",(time.time()-20,time.time()-20,stale))
 assert md.Dispatcher(worker=md.MockWorker()).reconcile()==1
 assert c.get("/v1/jobs/"+stale,headers=h).json()["state"]=="uncertain"
 assert md.Dispatcher(worker=md.MockWorker()).run_until_idle()["states"]["uncertain"]==1
 # uncertain slot0 must not occupy slot1
 newer=create(41)
 spare=md.MockWorker()
 res4=md.Dispatcher(worker=spare).run_until_idle()
 assert c.get("/v1/jobs/"+newer,headers=h).json()["state"]=="completed"
 assert spare.calls[0][1]==1,spare.calls
 print("MOCK_DISPATCH_PASS dual_parallel_slots restart_no_replay fail_closed manual_retry recovery spare_worker sqlite_integrity")
 print("REAL_GPU_INFERENCE=NOT_TESTED")
 print("REAL_PNG_OUTPUTS=0")

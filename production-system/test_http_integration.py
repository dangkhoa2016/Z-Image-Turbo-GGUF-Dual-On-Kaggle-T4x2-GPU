"""B1.4 CPU-only actual loopback HTTP mock servers, B1 API, dual dispatcher and PNG validation."""
import os,tempfile,secrets,time,threading,json,sqlite3
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from fastapi.testclient import TestClient
from PIL import Image
from worker_adapter import WorkerAdapter
with tempfile.TemporaryDirectory(prefix="b14-http-") as td:
 os.environ["ZIMAGE_B1_DB"]=str(Path(td)/"api.sqlite3")
 os.environ["ZIMAGE_B1_API_KEY"]=secrets.token_urlsafe(32)
 import service
 import http_dispatcher as hd
 imgroot=Path(td)/"out"
 for n in (0,1):(imgroot/f"worker-{n}").mkdir(parents=True)
 state={"active":0,"peak":0,"calls":[]}
 lock=threading.Lock()
 servers=[]
 def server(slot):
  class Handler(BaseHTTPRequestHandler):
   def log_message(self,*args):pass
   def do_GET(self):
    raw=json.dumps({"worker_id":slot,"ready":True}).encode()
    self.send_response(200);self.send_header("Content-Type","application/json");self.send_header("Content-Length",str(len(raw)));self.end_headers();self.wfile.write(raw)
   def do_POST(self):
    data=json.loads(self.rfile.read(int(self.headers["Content-Length"])))
    with lock:
     state["active"]+=1;state["peak"]=max(state["peak"],state["active"]);state["calls"].append((slot,data["seed"]))
    try:
     time.sleep(.13)
     path=imgroot/f"worker-{slot}"/f"{data['prompt_id']}-seed-{data['seed']}.png"
     Image.new("RGB",(1024,1024),(50+slot,10,data["seed"]%255)).save(path)
     import hashlib
     digest=hashlib.sha256(path.read_bytes()).hexdigest()
     if data["seed"]==333:digest="0"*64
     response={"status":"complete","worker_id":slot,"prompt_id":data["prompt_id"],"seed":data["seed"],
               "png_path":str(path),"png_sha256":digest,"seconds":.13}
     raw=json.dumps(response).encode()
     self.send_response(200);self.send_header("Content-Type","application/json");self.send_header("Content-Length",str(len(raw)));self.end_headers();self.wfile.write(raw)
    finally:
     with lock:state["active"]-=1
  return ThreadingHTTPServer(("127.0.0.1",12340+slot),Handler)
 try:
  for slot in (0,1):
   srv=server(slot);servers.append(srv)
   threading.Thread(target=srv.serve_forever,daemon=True).start()
  c=TestClient(service.app)
  headers={"Authorization":"Bearer "+os.environ["ZIMAGE_B1_API_KEY"]}
  hd.prepare_http()
  # B1 API accepts arbitrary text. Only one explicitly preencoded prompt maps to this mock worker.
  hd.permit_prompt("scene with mock encoded prompt","prompt_alpha")
  def create(seed,prompt="scene with mock encoded prompt"):
   resp=c.post("/v1/jobs",headers=headers,json={"prompt":prompt,"seed":seed})
   assert resp.status_code==201,resp.text
   return resp.json()["job_id"]
  ids=[create(x) for x in (10,11,12,13)]
  adapters={i:WorkerAdapter(i,f"http://127.0.0.1:{12340+i}",imgroot) for i in (0,1)}
  d=hd.Dispatcher(adapters)
  result=d.drain()
  assert result["states"]=={"completed":4},result
  assert result["verified_artifacts"]==4 and state["peak"]==2,result
  with hd.connect() as db:
   assert db.execute("SELECT COUNT(*) FROM b14_artifacts").fetchone()[0]==4
  for jid in ids:
   item=c.get("/v1/jobs/"+jid,headers=headers).json()
   assert item["state"]=="completed" and len(item["output_sha256"])==64
  assert hd.Dispatcher(adapters).drain()["verified_artifacts"]==4
  assert len(state["calls"])==4,"restart replay"
  # Incorrect reported SHA256: must NEVER be marked completed
  invalid=create(333)
  after=hd.Dispatcher(adapters).drain()
  assert c.get("/v1/jobs/"+invalid,headers=headers).json()["state"]=="uncertain",after
  with hd.connect() as db:assert db.execute("SELECT 1 FROM b14_artifacts WHERE job_id=?",(invalid,)).fetchone() is None
  before=len(state["calls"])
  hd.Dispatcher(adapters).drain()
  assert len(state["calls"])==before,"uncertain automatically replayed"
  # Stale worker0 job, worker1 should handle a new job; no automatic replay
  stale=create(500)
  with hd.connect() as db:
   db.execute("UPDATE jobs SET state='running',worker_id=0,lease_owner='old-owner',lease_deadline=?,updated_at=? WHERE id=?",(time.time()-10,time.time()-10,stale))
  assert hd.Dispatcher(adapters).reconcile()==1
  assert c.get("/v1/jobs/"+stale,headers=headers).json()["state"]=="uncertain"
  fresh=create(501)
  hd.Dispatcher(adapters).drain()
  assert c.get("/v1/jobs/"+fresh,headers=headers).json()["state"]=="completed"
  assert state["calls"][-1][0]==1
  # Unencoded arbitrary prompt stays queued; must not reach frozen 3-prompt worker
  unencoded=create(700,"brand new arbitrary user request not encoded")
  hd.Dispatcher(adapters).drain()
  assert c.get("/v1/jobs/"+unencoded,headers=headers).json()["state"]=="queued"
  with hd.connect() as db:assert db.execute("PRAGMA integrity_check").fetchone()[0]=="ok"
  print("B14_CPU_HTTP_E2E_PASS API SQLite dual_local_HTTP_mock PNG_SHA256 2_slots restart_no_replay bad_SHA_uncertain stale_failclosed unmapped_prompt_queued")
  print("B14_MAX_SIMULTANEOUS_HTTP_WORKERS="+str(state["peak"]))
  print("B14_REAL_GPU_INFERENCE=NOT_TESTED")
 finally:
  for srv in servers:srv.shutdown();srv.server_close()

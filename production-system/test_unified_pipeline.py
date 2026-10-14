"""B1.8 real localhost HTTP CPU mock E2E, isolated temporary DB/cache."""
import os,tempfile,secrets,json,time,threading,hashlib
from pathlib import Path
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from PIL import Image
from fastapi.testclient import TestClient
with tempfile.TemporaryDirectory(prefix="b16-test-b18-") as td:
 root=Path(td);os.environ["ZIMAGE_B16_TEST_ROOT"]=str(root)
 os.environ["ZIMAGE_B1_DB"]=str(root/"api.sqlite3")
 os.environ["ZIMAGE_B1_API_KEY"]=secrets.token_urlsafe(32)
 import service
 from unified_pipeline import UnifiedPipeline
 identity={"support_manifest_sha256":"d2092798f917a83ed79981ec23cdb5d33ee25b86f667fa46a563476a083dd7d7",
           "diffusers_version":"0.41.0","max_sequence_length":512,"text_encoder_dtype":"bfloat16"}
 artifacts=root/"out"
 for slot in (0,1):(artifacts/f"worker-{slot}").mkdir(parents=True)
 api=TestClient(service.app);h={"Authorization":"Bearer "+os.environ["ZIMAGE_B1_API_KEY"]}
 def submit(prompt,seed):
  resp=api.post("/v1/jobs",headers=h,json={"prompt":prompt,"seed":seed})
  assert resp.status_code==201,resp.text
  return resp.json()["job_id"]
 p1="A paper airplane over moonlit blue dunes";p2="A glass of water beside a sunflower"
 ids=[submit(p1,10),submit(p2,11),submit(p1,12)]
 cancelled=submit("Cancelled prompt never to encode",13)
 assert api.post(f"/v1/jobs/{cancelled}/cancel",headers=h).status_code==200
 pipeline=UnifiedPipeline(api_db=root/"api.sqlite3",registry_db=root/"registry.sqlite3",
  cache_root=root/"cache",identity=identity,session_dir=root/"session",
  artifact_root=artifacts,mode="cpu-mock")
 assert pipeline.pending_prompts()==[p1,p2]
 prepared=pipeline.prepare(max_items=4)
 assert prepared["prompts"]==2 and prepared["phase"]=="READY_FOR_HTTP_WORKERS"
 assert prepared["mode"]=="cpu-mock"
 assert (root/"session"/"b18-inference-manifest.json").is_file()
 try:pipeline.prepare()
 except RuntimeError:pass
 else:raise AssertionError("active session mappings must not be replaced")
 stats={"active":0,"peak":0,"calls":0};m=threading.Lock();servers=[]
 def make_server(slot):
  class Handler(BaseHTTPRequestHandler):
   def log_message(self,*args):pass
   def do_GET(self):
    payload={"ready":True,"worker_id":slot}
    self.send_json(payload)
   def send_json(self,payload):
    data=json.dumps(payload).encode()
    self.send_response(200);self.send_header("Content-Type","application/json")
    self.send_header("Content-Length",str(len(data)));self.end_headers();self.wfile.write(data)
   def do_POST(self):
    req=json.loads(self.rfile.read(int(self.headers["Content-Length"])))
    with m:
     stats["active"]+=1;stats["peak"]=max(stats["peak"],stats["active"]);stats["calls"]+=1
    try:
     time.sleep(.15)
     out=artifacts/f"worker-{slot}"/f"{req['prompt_id']}-seed-{req['seed']}.png"
     Image.new("RGB",(1024,1024),(slot+70,44,100)).save(out)
     self.send_json({"status":"complete","worker_id":slot,"prompt_id":req["prompt_id"],
       "seed":req["seed"],"png_path":str(out),"png_sha256":hashlib.sha256(out.read_bytes()).hexdigest(),
       "seconds":.15})
    finally:
     with m:stats["active"]-=1
  return ThreadingHTTPServer(("127.0.0.1",12340+slot),Handler)
 try:
  for slot in (0,1):
   server=make_server(slot);servers.append(server)
   threading.Thread(target=server.serve_forever,daemon=True).start()
  outcome=pipeline.dispatch(timeout=15)
  assert outcome["states"]=={"completed":3,"cancelled":1},outcome
  assert outcome["verified_artifacts"]==3
  assert stats["peak"]==2,stats
  assert stats["calls"]==3
  assert all(api.get("/v1/jobs/"+jid,headers=h).json()["state"]=="completed" for jid in ids)
  assert api.get("/v1/jobs/"+cancelled,headers=h).json()["state"]=="cancelled"
  assert pipeline.dispatch()["verified_artifacts"]==3
  assert stats["calls"]==3
  # Cache tampering fails closed on subsequent dispatch.
  manifest=json.loads((root/"session"/"b18-inference-manifest.json").read_text())
  cache_path=Path(next(iter(manifest["entries"].values()))["embedding_file"])
  with cache_path.open("ab") as f:f.write(b"tampered")
  try:pipeline.dispatch()
  except RuntimeError:pass
  else:raise AssertionError("tampered cache accepted")
  print("B18_CPU_E2E_PASS API queued prompts encoding_subprocess READY manifest 2_HTTP_workers valid_PNG_SHA256 cancellation no_replay tamper_rejected")
  print("B18_PEAK_HTTP_WORKERS="+str(stats["peak"]))
  print("B18_GPU_INFERENCE=NOT_TESTED")
 finally:
  for srv in servers:srv.shutdown();srv.server_close()

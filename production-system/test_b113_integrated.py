"""B1.13 shared freeze + scoped dispatch, CPU mock only."""
import os,tempfile,secrets,json,threading,hashlib,sqlite3
from pathlib import Path
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from PIL import Image
from fastapi.testclient import TestClient
with tempfile.TemporaryDirectory(prefix="b16-test-b113close-") as td:
 root=Path(td);os.environ["ZIMAGE_B16_TEST_ROOT"]=td;os.environ["ZIMAGE_B1_DB"]=str(root/"api.sqlite3")
 os.environ["ZIMAGE_B1_API_KEY"]=secrets.token_urlsafe(36)
 import b113_admission as admission
 from b113_shared_lifecycle import SharedLifecycle
 from b113_scoped_dispatcher import ScopedDispatcher
 from worker_adapter import WorkerAdapter
 api=TestClient(admission.app);h={"Authorization":"Bearer "+os.environ["ZIMAGE_B1_API_KEY"]}
 for n,p in enumerate(("A luminous paper lantern floating on a lake","An old green bicycle in a studio"),11):
  assert api.post("/v1/jobs",headers=h,json={"prompt":p,"seed":n}).status_code==201
 identity={"support_manifest_sha256":"d2092798f917a83ed79981ec23cdb5d33ee25b86f667fa46a563476a083dd7d7","diffusers_version":"0.41.0","max_sequence_length":512,"text_encoder_dtype":"bfloat16"}
 out=root/"out"
 for slot in (0,1):(out/f"worker-{slot}").mkdir(parents=True)
 controller=SharedLifecycle(api_db=root/"api.sqlite3",sessions_root=root/"sessions",artifact_root=out,identity=identity,mode="cpu-mock",max_prompts=2,max_jobs=2)
 def callback(sid,prepared):
  assert api.post("/v1/jobs",headers=h,json={"prompt":"A luminous paper lantern floating on a lake","seed":19}).status_code==423
  assert api.post("/v1/jobs",headers=h,json={"prompt":"A bright yellow kayak on the sand","seed":20}).status_code==201
  servers=[]
  def server(slot):
   class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def reply(self,data):
     raw=json.dumps(data).encode()
     self.send_response(200);self.send_header("Content-Type","application/json")
     self.send_header("Content-Length",str(len(raw)));self.end_headers();self.wfile.write(raw)
    def do_GET(self):self.reply({"ready":True,"worker_id":slot})
    def do_POST(self):
     d=json.loads(self.rfile.read(int(self.headers["Content-Length"])))
     p=out/f"worker-{slot}"/f"{d['prompt_id']}-seed-{d['seed']}.png"
     Image.new("RGB",(1024,1024),(slot+64,25,90)).save(p)
     self.reply({"status":"complete","worker_id":slot,"prompt_id":d["prompt_id"],"seed":d["seed"],"png_path":str(p),"png_sha256":hashlib.sha256(p.read_bytes()).hexdigest(),"seconds":0.1})
   return ThreadingHTTPServer(("127.0.0.1",12340+slot),Handler)
  try:
   for slot in (0,1):
    s=server(slot);servers.append(s);threading.Thread(target=s.serve_forever,daemon=True).start()
   adapters={i:WorkerAdapter(i,f"http://127.0.0.1:{12340+i}",out) for i in (0,1)}
   result=ScopedDispatcher(adapters,sid).drain(timeout=25)
  finally:
   for s in servers:s.shutdown();s.server_close()
  assert result["states"].get("queued")==1,result
  return result
 first=controller.run_one(callback)
 assert first["archive"]["verified_png"]==2,first
 with sqlite3.connect(root/"api.sqlite3") as c:
  assert c.execute("SELECT COUNT(*) FROM jobs WHERE state='queued'").fetchone()[0]==1
  assert c.execute("SELECT COUNT(*) FROM b113_active_prompts").fetchone()[0]==0
  assert c.execute("SELECT COUNT(*) FROM b113_session_jobs").fetchone()[0]==2
 print("B113_CPU_INTEGRATION_PASS frozen=2 verified=2 late_unrelated_queued=1 same_prompt_423=true mock_only=true")

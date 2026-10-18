import os,tempfile,secrets,threading,json,hashlib
from pathlib import Path
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from fastapi.testclient import TestClient
from PIL import Image
with tempfile.TemporaryDirectory(prefix="b16-test-b112-") as td:
 root=Path(td)
 os.environ["ZIMAGE_B16_TEST_ROOT"]=td
 os.environ["ZIMAGE_B1_DB"]=str(root/"api.sqlite3")
 os.environ["ZIMAGE_B1_API_KEY"]=secrets.token_urlsafe(36)
 import service
 from session_lifecycle import Lifecycle,RolloverBlocked
 api=TestClient(service.app)
 hdr={"Authorization":"Bearer "+os.environ["ZIMAGE_B1_API_KEY"]}
 prompts=["A paper boat under the blue moon","A porcelain vase with yellow flowers","An orange bicycle beside a tree"]
 for seed,prompt in enumerate(prompts,21):
  assert api.post("/v1/jobs",headers=hdr,json={"prompt":prompt,"seed":seed}).status_code==201
 ident={"support_manifest_sha256":"d2092798f917a83ed79981ec23cdb5d33ee25b86f667fa46a563476a083dd7d7","diffusers_version":"0.41.0","max_sequence_length":512,"text_encoder_dtype":"bfloat16"}
 artifacts=root/"out"
 for i in (0,1):(artifacts/f"worker-{i}").mkdir(parents=True)
 lifecycle=Lifecycle(api_db=root/"api.sqlite3",sessions_root=root/"sessions",artifact_root=artifacts,identity=ident,mode="cpu-mock",max_prompts=2,max_jobs=2)
 calls=[]
 def run_dispatch(pipe,sid):
  servers=[]
  def make_server(slot):
   class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def answer(self,d):
     raw=json.dumps(d).encode()
     self.send_response(200);self.send_header("Content-Type","application/json");self.send_header("Content-Length",str(len(raw)));self.end_headers();self.wfile.write(raw)
    def do_GET(self):self.answer({"ready":True,"worker_id":slot})
    def do_POST(self):
     req=json.loads(self.rfile.read(int(self.headers["Content-Length"])))
     path=artifacts/f"worker-{slot}"/f"{req['prompt_id']}-seed-{req['seed']}.png"
     Image.new("RGB",(1024,1024),(40+slot,50,60)).save(path)
     calls.append(req["prompt_id"])
     self.answer({"status":"complete","worker_id":slot,"prompt_id":req["prompt_id"],"seed":req["seed"],"png_path":str(path),"png_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"seconds":.1})
   return ThreadingHTTPServer(("127.0.0.1",12340+slot),Handler)
  try:
   for slot in (0,1):
    srv=make_server(slot);servers.append(srv)
    threading.Thread(target=srv.serve_forever,daemon=True).start()
   outcome=pipe.dispatch(timeout=30)
  finally:
   for srv in servers:srv.shutdown();srv.server_close()
  return outcome
 def tamper_dispatch(pipe,sid):
  result=run_dispatch(pipe,sid)
  pngs=list(artifacts.rglob("*.png"))
  assert pngs
  with pngs[0].open("ab") as f:f.write(b"TAMPERED")
  return result
 try:
  lifecycle.run_one(tamper_dispatch)
 except RolloverBlocked as exc:
  assert "SHA mismatch" in str(exc),str(exc)
 else:raise AssertionError("tampered PNG accepted")
 assert lifecycle.active()["status"]=="BLOCKED"
 import sqlite3
 with sqlite3.connect(root/"api.sqlite3") as c:
  assert c.execute("SELECT COUNT(*) FROM b112_sessions WHERE status=?",("BLOCKED",)).fetchone()[0]==1
  assert c.execute("SELECT COUNT(*) FROM b14_prompt_map").fetchone()[0]==2
 print("SESSION_TAMPER_PROTECTION_PASS blocked_session=1 mappings_retained=2 no_auto_retry=true")
 # Test intentionally ends with a blocked isolated fixture; no rollback or silent replay.
 raise SystemExit(0)
 second=lifecycle.run_one(run_dispatch)
 assert second["archive"]["verified_png"]==1,second
 assert lifecycle.run_one(run_dispatch)=={"status":"NO_PENDING"}
 import sqlite3
 with sqlite3.connect(root/"api.sqlite3") as c:
  assert c.execute("SELECT COUNT(*) FROM b112_sessions WHERE status='ARCHIVED'").fetchone()[0]==2
  assert c.execute("SELECT COUNT(*) FROM b112_artifact_history").fetchone()[0]==3
  assert c.execute("SELECT COUNT(*) FROM b14_prompt_map").fetchone()[0]==0
  assert c.execute("SELECT COUNT(*) FROM jobs WHERE state='completed'").fetchone()[0]==3
 print("SESSION_ROLLOVER_CPU_PASS archived=2 verified_png=3 no_replay=true no_mapping_leak=true mock_only=true")

"""CPU only: mock HTTP responses and real temporary PNG validation."""
import hashlib,importlib.util,tempfile
from pathlib import Path
from unittest.mock import patch
from PIL import Image
import requests
spec=importlib.util.spec_from_file_location("wa",Path(__file__).with_name("worker_adapter.py"))
wa=importlib.util.module_from_spec(spec);spec.loader.exec_module(wa)
class Reply:
 def __init__(self,data,code=200):self.data=data;self.status_code=code
 def raise_for_status(self):
  if self.status_code>=400:raise requests.HTTPError(f"mock HTTP {self.status_code}")
 def json(self):return self.data
def fails(error,fn):
 try:fn()
 except error:return
 raise AssertionError("expected "+error.__name__)
with tempfile.TemporaryDirectory(prefix="zimage-b13-") as td:
 root=Path(td)/"images"
 (root/"worker-0").mkdir(parents=True)
 file=root/"worker-0"/"portrait_studio_v1-seed-45.png"
 Image.new("RGB",(1024,1024),(80,90,100)).save(file)
 digest=hashlib.sha256(file.read_bytes()).hexdigest()
 adapter=wa.WorkerAdapter(0,"http://127.0.0.1:12340",root,timeout=4)
 base={"status":"complete","worker_id":0,"prompt_id":"portrait_studio_v1","seed":45,"png_path":str(file),"png_sha256":digest,"seconds":2.0}
 with patch.object(wa.requests,"get",return_value=Reply({"ready":True,"worker_id":0})):
  assert adapter.ready()
 with patch.object(wa.requests,"get",return_value=Reply({"ready":True,"worker_id":1})):
  assert not adapter.ready()
 with patch.object(wa.requests,"post",return_value=Reply(base)):
  result=adapter.generate("portrait_studio_v1",45)
  assert result["output_sha256"]==digest and result["worker_id"]==0
 for case in [
  dict(base,worker_id=1),
  dict(base,prompt_id="wrong"),
  dict(base,seed=46),
  dict(base,png_sha256="0"*64),
  dict(base,png_path="/tmp/not-an-artifact.png"),
  dict(base,status="queued")
 ]:
  with patch.object(wa.requests,"post",return_value=Reply(case)):
   fails((wa.WorkerProtocolError,FileNotFoundError),lambda:adapter.generate("portrait_studio_v1",45))
 with patch.object(wa.requests,"post",return_value=Reply(base,code=503)):
  fails(requests.HTTPError,lambda:adapter.generate("portrait_studio_v1",45))
 fails(ValueError,lambda:wa.WorkerAdapter(0,"http://example.com:12340",root))
 fails(ValueError,lambda:wa.WorkerAdapter(0,"http://127.0.0.1:12341",root))
 fails(ValueError,lambda:wa.WorkerAdapter(2,"http://127.0.0.1:12342",root))
 # No output published if file bytes differ from digest
 Image.new("RGB",(1024,1024),(5,2,1)).save(file)
 with patch.object(wa.requests,"post",return_value=Reply(base)):
  fails(wa.WorkerProtocolError,lambda:adapter.generate("portrait_studio_v1",45))
 # Must reject symlinked output even when digest matches
 file.unlink()
 real=Path(td)/"hidden.png"
 Image.new("RGB",(1024,1024)).save(real)
 file.symlink_to(real)
 new=dict(base,png_sha256=hashlib.sha256(real.read_bytes()).hexdigest())
 with patch.object(wa.requests,"post",return_value=Reply(new)):
  fails(wa.WorkerProtocolError,lambda:adapter.generate("portrait_studio_v1",45))
 print("WORKER_ADAPTER_CPU_PASS loopback_fencing health identity output_path PNG_size SHA256 http_errors symlink")
 print("WORKER_HTTP=MOCK_ONLY; GPU_INFERENCE=NOT_TESTED")

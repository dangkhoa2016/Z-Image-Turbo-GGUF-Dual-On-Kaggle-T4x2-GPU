"""Loopback HTTP worker adapter with identity and artifact integrity checks.
Accepts only loopback worker endpoints and verifies real PNG bytes on disk.
NOT wired to the production dispatcher; do not use to claim live inference.
"""
import hashlib,ipaddress,os
from pathlib import Path
from urllib.parse import urlsplit
import requests
from PIL import Image

class WorkerProtocolError(RuntimeError):pass

def file_hash(path):
 h=hashlib.sha256()
 with open(path,"rb") as f:
  for part in iter(lambda:f.read(1024*1024),b""):h.update(part)
 return h.hexdigest()

class WorkerAdapter:
 def __init__(self,worker_id,base_url,artifact_root,timeout=950):
  if worker_id not in (0,1):raise ValueError("Only Kaggle worker slots 0 and 1")
  parsed=urlsplit(base_url)
  if parsed.scheme!="http" or parsed.hostname not in ("127.0.0.1","localhost") or parsed.username or parsed.password or parsed.path not in ("","/") or parsed.query or parsed.fragment:raise ValueError("Only loopback HTTP worker permitted")
  if parsed.port!=12340+worker_id:raise ValueError("Worker must use established slot-specific port")
  self.worker_id=worker_id
  self.base_url=f"http://127.0.0.1:{parsed.port}"
  self.root=Path(artifact_root).resolve(strict=True)
  self.timeout=timeout
 def ready(self):
  try:
   r=requests.get(self.base_url+"/ready",timeout=(3,3),allow_redirects=False)
   r.raise_for_status()
   data=r.json()
   return data.get("ready") is True and data.get("worker_id")==self.worker_id
  except (requests.RequestException,ValueError,KeyError):return False
 def generate(self,prompt_id,seed):
  """Send only a cached prompt ID, not arbitrary user text. Encoding remains pending."""
  if not isinstance(prompt_id,str) or not prompt_id or len(prompt_id)>128:raise ValueError("invalid prompt_id")
  if not isinstance(seed,int) or not 0<=seed<=4294967295:raise ValueError("invalid seed")
  resp=requests.post(self.base_url+"/generate",json={"prompt_id":prompt_id,"seed":seed,"height":1024,"width":1024,"steps":9,"guidance_scale":0.0},timeout=(5,self.timeout),allow_redirects=False)
  resp.raise_for_status()
  data=resp.json()
  if data.get("status")!="complete" or data.get("worker_id")!=self.worker_id or data.get("prompt_id")!=prompt_id or data.get("seed")!=seed:
   raise WorkerProtocolError("worker response identity mismatch")
  declared=data.get("png_sha256")
  if not isinstance(declared,str) or len(declared)!=64 or any(ch not in "0123456789abcdef" for ch in declared):
   raise WorkerProtocolError("missing or malformed digest")
  p=Path(data.get("png_path",""))
  if not p.is_absolute():raise WorkerProtocolError("artifact path not absolute")
  # Strictly bind result to expected historical naming and a pre-authorized worker output directory.
  expected=self.root/f"worker-{self.worker_id}"/f"{prompt_id}-seed-{seed}.png"
  if p != expected:raise WorkerProtocolError("unexpected artifact path")
  if p.is_symlink() or expected.parent.is_symlink():raise WorkerProtocolError("symlink artifact forbidden")
  if p.resolve(strict=True)!=expected:raise WorkerProtocolError("artifact path escape")
  with Image.open(p) as img:
   img.verify()
  with Image.open(p) as img:
   if img.format!="PNG" or img.size!=(1024,1024):raise WorkerProtocolError("invalid output PNG")
  actual=file_hash(p)
  if actual!=declared:raise WorkerProtocolError("PNG SHA256 mismatch")
  return {"worker_id":self.worker_id,"prompt_id":prompt_id,"seed":seed,"output_path":str(p),"output_sha256":actual,"seconds":data.get("seconds")}

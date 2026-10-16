"""Build a per-session, integrity-checked inference manifest from READY GPU embeddings."""
import json,os,uuid
from pathlib import Path
from safetensors import safe_open
from embedding_registry import Registry,hash_file
def export_manifest(registry:Registry,prompts,output:Path,*,allow_mock=False):
 entries={}
 for prompt in prompts:
  key=registry.key(prompt);row=registry.status(key)
  if not row or row["status"]!="ready" or not registry.check_ready(key):raise RuntimeError("not READY or corrupt: "+key)
  p=registry.root/row["embedding_file"]
  with safe_open(p,framework="pt",device="cpu") as f:
   meta=f.metadata() or {}
   if meta.get("cache_key")!=key:raise RuntimeError("cache-key metadata mismatch")
   if meta.get("prompt_sha256")!=row["prompt_sha256"]:raise RuntimeError("prompt digest mismatch")
   producer=meta.get("producer")
   if producer!="gpu-qwen3" and not allow_mock:raise RuntimeError("untrusted encoder producer")
   if producer=="cpu-mock-NEVER-PRODUCTION" and not allow_mock:raise RuntimeError("mock embedding forbidden")
   tensor=f.get_tensor("emb_000")
   shape=list(tensor.shape)
  entries[key]={"prompt_id":key,"cache_key":key,"prompt_sha256":row["prompt_sha256"],
    "embedding_file":str(p.resolve()),"embedding_sha256":hash_file(p),
    "tensor_shape":shape,"producer":producer}
 if not entries:raise ValueError("empty manifest")
 obj={"schema":"zimage-b17-dynamic-manifest-v1","source":"READY_REGISTRY","inference_baseline":{"width":1024,"height":1024,"steps":9,"guidance_scale":0.0},
     "test_only":allow_mock,"entries":entries}
 output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
 t=output.with_name(output.name+"."+uuid.uuid4().hex+".tmp")
 t.write_text(json.dumps(obj,sort_keys=True,indent=2)+"\n")
 os.replace(t,output)
 return obj
def read_manifest(path,*,allow_mock=False):
 obj=json.loads(Path(path).read_text())
 if obj.get("schema")!="zimage-b17-dynamic-manifest-v1" or not isinstance(obj.get("entries"),dict):raise RuntimeError("unsupported manifest")
 if obj.get("test_only") and not allow_mock:raise RuntimeError("test-only manifest cannot run real inference")
 for key,entry in obj["entries"].items():
  if key!=entry["cache_key"] or key!=entry["prompt_id"] or len(key)!=64:raise RuntimeError("manifest ID mismatch")
  p=Path(entry["embedding_file"])
  if p.is_symlink() or not p.is_file() or hash_file(p)!=entry["embedding_sha256"]:raise RuntimeError("embedding tampered or missing")
  with safe_open(p,framework="pt",device="cpu") as f:
   if list(f.keys())!=["emb_000"]:raise RuntimeError("tensor key invalid")
   t=f.get_tensor("emb_000");meta=f.metadata() or {}
   if t.dtype.__str__()!="torch.bfloat16" or t.ndim!=2 or t.shape[1]!=2560:raise RuntimeError("tensor invalid")
   if meta.get("cache_key")!=key or meta.get("prompt_sha256")!=entry["prompt_sha256"]:raise RuntimeError("metadata mismatch")
   if meta.get("producer")!="gpu-qwen3" and not allow_mock:raise RuntimeError("unsupported provenance")
 return obj

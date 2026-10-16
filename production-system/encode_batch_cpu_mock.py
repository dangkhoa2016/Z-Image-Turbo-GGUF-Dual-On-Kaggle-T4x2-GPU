#!/usr/bin/env python3
"""B1.6 test-only encoder. Synthetic tensors must NEVER enter a real GPU worker."""
import argparse,hashlib,json,os,uuid
from pathlib import Path
from embedding_registry import Registry
def main():
 p=argparse.ArgumentParser()
 p.add_argument("--db",required=True);p.add_argument("--cache-root",required=True)
 p.add_argument("--identity",required=True);p.add_argument("--max-items",type=int,required=True)
 args=p.parse_args()
 # Never allow mock provenance to be published into the Kaggle production cache.
 trusted=Path(os.environ.get("ZIMAGE_B16_TEST_ROOT","")).resolve()
 db=Path(args.db).resolve();root=Path(args.cache_root).resolve()
 if not str(trusted).startswith("/tmp/b16-test-") or not db.is_relative_to(trusted) or not root.is_relative_to(trusted):
  raise RuntimeError("cpu-mock may write ONLY inside /tmp/b16-test-*")
 if not 1<=args.max_items<=32:raise ValueError("bounded test batch required")
 import torch
 from safetensors.torch import save_file
 registry=Registry(db,root,json.loads(Path(args.identity).read_text()))
 owner="cpu-mock-"+uuid.uuid4().hex
 count=0
 for _ in range(args.max_items):
  j=registry.claim(owner,lease=600)
  if j is None:break
  key=j["cache_key"]
  emb=root/"embeddings"/f"{key}.safetensors"
  emb.parent.mkdir(parents=True,exist_ok=True)
  if emb.exists():raise RuntimeError("mock cache pre-exists")
  tensor=torch.zeros((59,2560),dtype=torch.bfloat16)
  scratch=emb.with_suffix(".partial")
  try:
   save_file({"emb_000":tensor},str(scratch),
     metadata={"cache_key":key,"prompt_sha256":j["prompt_sha256"],"producer":"cpu-mock-NEVER-PRODUCTION"})
   os.link(scratch,emb);scratch.unlink()
   registry.complete(key,owner,f"embeddings/{key}.safetensors")
   count+=1
  finally:
   if scratch.exists():scratch.unlink()
 print(json.dumps({"status":"CPU_MOCK_ONLY","encoded":count,"gpu_inference":"NOT_TESTED"}),flush=True)
if __name__=="__main__":main()

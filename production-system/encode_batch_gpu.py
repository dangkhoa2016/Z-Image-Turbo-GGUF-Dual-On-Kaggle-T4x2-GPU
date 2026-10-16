#!/usr/bin/env python3
"""B1.6 bounded dynamic Qwen3 encoder subprocess — Kaggle T4 GPU0 ONLY.
Never started by the CPU test. No GPU hardware means fail closed.
"""
import argparse,gc,importlib.metadata,json,os,sys,time,uuid,hashlib
from pathlib import Path
from embedding_registry import Registry,hash_file

def parse():
 p=argparse.ArgumentParser()
 p.add_argument("--db",required=True)
 p.add_argument("--cache-root",required=True)
 p.add_argument("--max-items",type=int,default=8)
 p.add_argument("--lease-seconds",type=int,default=1800)
 return p.parse_args()

def main():
 args=parse()
 if not (1<=args.max_items<=32 and 300<=args.lease_seconds<=7200):raise ValueError("bounded batch/lease required")
 if os.environ.get("CUDA_VISIBLE_DEVICES")!="0":raise RuntimeError("GPU0 must be the only visible physical GPU")
 if os.environ.get("HF_HUB_OFFLINE")!="1" or os.environ.get("TRANSFORMERS_OFFLINE")!="1":
  raise RuntimeError("Require fully offline text encoder")
 import torch
 from safetensors.torch import save_file,load_file
 from transformers import AutoTokenizer,Qwen3Model
 from diffusers import ZImagePipeline
 if torch.cuda.device_count()!=1 or "T4" not in torch.cuda.get_device_name(0):
  raise RuntimeError("One logical NVIDIA T4 required for encoder phase")
 root=Path("/kaggle/working/zimage-dual")
 support=json.loads((root/"manifests/support.json").read_text())
 identity={"support_manifest_sha256":support["manifest_sha256"],"diffusers_version":importlib.metadata.version("diffusers"),
           "max_sequence_length":512,"text_encoder_dtype":"bfloat16"}
 registry=Registry(args.db,args.cache_root,identity)
 support_root=Path(support["support_root"])
 if not support_root.is_dir():raise RuntimeError("Support dataset missing")
 # Must run after workers stop; keep this check as a final safeguard.
 import socket
 for port in (12340,12341):
  sock=socket.socket();sock.settimeout(.2)
  try:
   if sock.connect_ex(("127.0.0.1",port))==0:raise RuntimeError("GPU inference port still listening: "+str(port))
  finally:sock.close()
 tokenizer=encoder=harness=None
 processed=0
 owner="gpu-encoder-"+uuid.uuid4().hex
 try:
  # Do not load the 8GB encoder if there is no pending work.
  with registry.conn() as c:pending=c.execute("SELECT COUNT(*) FROM encoding WHERE status='pending'").fetchone()[0]
  if not pending:
   print("GPU_ENCODE_BATCH=NO_PENDING",flush=True);return
  tokenizer=AutoTokenizer.from_pretrained(str(support_root/"tokenizer"),local_files_only=True,use_fast=True)
  encoder=Qwen3Model.from_pretrained(str(support_root/"text_encoder"),torch_dtype=torch.bfloat16,
                                   local_files_only=True,low_cpu_mem_usage=True)
  encoder.eval().to("cuda:0")
  class Harness:
   _encode_prompt=ZImagePipeline._encode_prompt
   def __init__(self,tok,enc):
    self.tokenizer=tok;self.text_encoder=enc;self._execution_device=torch.device("cuda:0")
  harness=Harness(tokenizer,encoder)
  for _ in range(args.max_items):
   job=registry.claim(owner,args.lease_seconds)
   if job is None:break
   key=job["cache_key"]
   if registry.key(job["prompt"])!=key:raise RuntimeError("Prompt/cache identity mismatch")
   final=Path(args.cache_root)/"embeddings"/(key+".safetensors")
   if final.exists():raise RuntimeError("Pre-existing unreviewed cache path: "+str(final))
   final.parent.mkdir(parents=True,exist_ok=True)
   scratch=final.with_name(final.name+"."+uuid.uuid4().hex+".partial")
   try:
    with torch.inference_mode():
     positive,negative=ZImagePipeline.encode_prompt(harness,prompt=job["prompt"],device=torch.device("cuda:0"),
          do_classifier_free_guidance=False,max_sequence_length=512)
    if len(positive)!=1 or len(negative)!=0:raise RuntimeError("unexpected encoder output count")
    emb=positive[0]
    if emb.dtype!=torch.bfloat16 or emb.ndim!=2 or emb.shape[1]!=2560 or not 1<=emb.shape[0]<=512:
     raise RuntimeError("unexpected embedding shape or dtype")
    cpu=emb.detach().to("cpu").contiguous()
    metadata={"cache_key":key,"prompt_sha256":job["prompt_sha256"],"producer":"gpu-qwen3",
              "support_manifest_sha256":support["manifest_sha256"],"diffusers_version":identity["diffusers_version"]}
    save_file({"emb_000":cpu},str(scratch),metadata=metadata)
    reread=load_file(str(scratch),device="cpu")["emb_000"]
    if not torch.equal(reread,cpu):raise RuntimeError("readback embedding differs")
    # Atomic publication without replacing a prior file. Crash before registry.complete
    # leaves an unregistered file needing explicit operator reconciliation.
    os.link(scratch,final);scratch.unlink()
    digest=registry.complete(key,owner,"embeddings/"+final.name)
    print(json.dumps({"cache_key":key,"status":"READY_GPU_ENCODING","embedding_sha256":digest,
                      "tensor_shape":list(cpu.shape)},sort_keys=True),flush=True)
    processed+=1
    del positive,negative,emb,cpu,reread
   finally:
    if scratch.exists():scratch.unlink()
  print(json.dumps({"batch_count":processed,"status":"ENCODE_BATCH_FINISHED",
                    "gpu":0,"real_qwen3":True},sort_keys=True),flush=True)
 finally:
  del harness,encoder,tokenizer
  gc.collect()
  if torch.cuda.is_available():
   torch.cuda.empty_cache();torch.cuda.ipc_collect();torch.cuda.synchronize()

if __name__=="__main__":
 try:main()
 except Exception as exc:
  print("ENCODE_GPU_FAILED "+type(exc).__name__+": "+str(exc),file=sys.stderr,flush=True)
  raise

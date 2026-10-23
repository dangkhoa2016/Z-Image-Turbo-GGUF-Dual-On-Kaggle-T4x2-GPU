#!/usr/bin/env python3
"""Bounded Qwen3 text-encoding subprocess for Kaggle GPU 0.
Never started by the CPU test. No GPU hardware means fail closed.
"""
import argparse,gc,importlib.metadata,json,os,sys,time,uuid,hashlib
from pathlib import Path
from embedding_registry import Registry,hash_file
from qwen3_staging import select_qwen3_source

# Lightweight, read-only diagnostics. No GPU synchronizations or tensor copies.
_ENCODER_STARTED=time.monotonic()
def encoder_stage(name, **details):
 io={}
 try:
  for row in Path("/proc/self/io").read_text().splitlines():
   key,sep,value=row.partition(":")
   if sep and key in ("read_bytes","rchar","syscr"):
    io[key]=int(value.strip())
 except (OSError,ValueError):
  pass
 rss_kib=None
 try:
  for row in Path("/proc/self/status").read_text().splitlines():
   if row.startswith("VmRSS:"):
    rss_kib=int(row.split()[1]);break
 except (OSError,ValueError,IndexError):
  pass
 event={"stage":name,"elapsed_seconds":round(time.monotonic()-_ENCODER_STARTED,2),
        "rss_kib":rss_kib,**io,**details}
 print("ZIMAGE_ENCODER_STAGE "+json.dumps(event,sort_keys=True),flush=True)


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
 encoder_stage("TORCH_IMPORT_BEGIN")
 import torch
 from safetensors.torch import save_file,load_file
 from transformers import AutoTokenizer,Qwen3Model
 from diffusers import ZImagePipeline
 encoder_stage("TORCH_AND_MODELS_IMPORTED",torch_version=str(torch.__version__))
 if torch.cuda.device_count()!=1 or "T4" not in torch.cuda.get_device_name(0):
  raise RuntimeError("One logical NVIDIA T4 required for encoder phase")
 root=Path(__file__).resolve().parents[1]
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
  encoder_stage("TOKENIZER_LOAD_BEGIN")
  tokenizer=AutoTokenizer.from_pretrained(str(support_root/"tokenizer"),local_files_only=True,use_fast=True)
  encoder_stage("TOKENIZER_LOAD_FINISHED")
  qwen3_mode=os.environ.get("ZIMAGE_QWEN3_SOURCE_MODE", "direct")
  qwen3_cache_root=Path(os.environ.get("ZIMAGE_QWEN3_STAGE_ROOT", "/kaggle/working/zimage-qwen3-stage"))
  # Only controlled ephemeral roots are supported. The staging module still
  # checks every path ancestor for symlinks, model hashes, and atomic writes.
  allowed_roots=(Path("/kaggle/working"),Path("/tmp/zimage-t4x2-model-stage"))
  if qwen3_mode in ("auto", "local") and not any(
      qwen3_cache_root.is_relative_to(base) for base in allowed_roots):
   raise RuntimeError("QWEN3_STAGE_ROOT_OUTSIDE_ALLOWED_CACHE_ROOT")
  encoder_stage("QWEN3_SOURCE_SELECTION_BEGIN")
  selected=select_qwen3_source(
      support,
      qwen3_cache_root,
      mode=qwen3_mode,
  )
  encoder_stage("QWEN3_SOURCE_SELECTION_FINISHED",
                requested_mode=selected["requested_mode"],
                effective_mode=selected["effective_mode"],
                integrity=selected["integrity"],
                copied=selected["copied"],
                selection_seconds=selected["selection_seconds"])
  encoder_stage("QWEN3_WEIGHTS_LOAD_BEGIN")
  encoder=Qwen3Model.from_pretrained(selected["text_encoder_dir"],torch_dtype=torch.bfloat16,
                                   local_files_only=True,low_cpu_mem_usage=True)
  encoder_stage("QWEN3_WEIGHTS_LOAD_FINISHED")
  encoder_stage("QWEN3_CUDA_TRANSFER_BEGIN")
  encoder.eval().to("cuda:0")
  encoder_stage("QWEN3_CUDA_TRANSFER_FINISHED")
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
    encoder_stage("PROMPT_ENCODE_BEGIN",item=processed+1)
    with torch.inference_mode():
     positive,negative=ZImagePipeline.encode_prompt(harness,prompt=job["prompt"],device=torch.device("cuda:0"),
          do_classifier_free_guidance=False,max_sequence_length=512)
    encoder_stage("PROMPT_ENCODE_FINISHED",item=processed+1)
    if len(positive)!=1 or len(negative)!=0:raise RuntimeError("unexpected encoder output count")
    emb=positive[0]
    if emb.dtype!=torch.bfloat16 or emb.ndim!=2 or emb.shape[1]!=2560 or not 1<=emb.shape[0]<=512:
     raise RuntimeError("unexpected embedding shape or dtype")
    encoder_stage("EMBEDDING_SAVE_BEGIN",item=processed+1)
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
    encoder_stage("EMBEDDING_SAVE_VERIFIED",item=processed+1)
    print(json.dumps({"cache_key":key,"status":"READY_GPU_ENCODING","embedding_sha256":digest,
                      "tensor_shape":list(cpu.shape)},sort_keys=True),flush=True)
    processed+=1
    del positive,negative,emb,cpu,reread
   finally:
    if scratch.exists():scratch.unlink()
  encoder_stage("ENCODER_BATCH_FINISHED",completed=processed)
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

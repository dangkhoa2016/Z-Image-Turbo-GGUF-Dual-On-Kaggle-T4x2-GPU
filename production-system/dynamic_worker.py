#!/usr/bin/env python3
"""Isolated T4 GPU inference worker with verified prompt embeddings and per-worker CUDA isolation."""
import argparse,hashlib,json,os,time,threading,sys
from pathlib import Path
from fastapi import FastAPI,HTTPException
from pydantic import BaseModel,Field
from dynamic_manifest import read_manifest
parser=argparse.ArgumentParser()
parser.add_argument("--worker-id",type=int,required=True,choices=(0,1))
parser.add_argument("--port",type=int,required=True)
parser.add_argument("--manifest",required=True)
args=parser.parse_args()
STARTED_AT=time.monotonic()
def stage(name,**details):
 print("ZIMAGE_WORKER_STAGE "+json.dumps({
  "worker_id":args.worker_id,"pid":os.getpid(),"stage":name,
  "elapsed_seconds":round(time.monotonic()-STARTED_AT,2),**details
 },sort_keys=True),flush=True)
stage("PROCESS_START",cuda_visible=os.environ.get("CUDA_VISIBLE_DEVICES"))
if args.port!=12340+args.worker_id:raise RuntimeError("port/slot mismatch")
if os.environ.get("CUDA_VISIBLE_DEVICES")!=str(args.worker_id):raise RuntimeError("physical GPU isolation missing")
if os.environ.get("HF_HUB_OFFLINE")!="1" or os.environ.get("TRANSFORMERS_OFFLINE")!="1":raise RuntimeError("offline mode required")
stage("IMPORT_TORCH")
import torch
stage("TORCH_READY",torch_version=str(torch.__version__),cuda_version=str(torch.version.cuda))
from safetensors.torch import load_file
stage("IMPORT_DIFFUSERS")
from diffusers import ZImagePipeline,ZImageTransformer2DModel,GGUFQuantizationConfig,AutoencoderKL,FlowMatchEulerDiscreteScheduler
stage("DIFFUSERS_READY")
if torch.cuda.device_count()!=1 or "T4" not in torch.cuda.get_device_name(0):raise RuntimeError("one logical T4 required")
stage("CUDA_VISIBLE",device=torch.cuda.get_device_name(0))
CACHE=read_manifest(args.manifest)["entries"]
ROOT=Path(__file__).resolve().parents[1]
M=json.loads((ROOT/"manifests/model.json").read_text())
S=json.loads((ROOT/"manifests/support.json").read_text())
support=Path(S["support_root"])
# Optional notebook-local GGUF copy. Legacy Studio paths remain unchanged.
# Validate the exact staged path AND model SHA256 independently inside each
# worker; never trust arbitrary environment-supplied model content.
gguf_path=M["gguf_path"]
staged_override=os.environ.get("ZIMAGE_GGUF_STAGED_PATH","").strip()
if staged_override:
 from stage_gguf_model import verify_staged_override
 gguf_path=str(verify_staged_override(
  M,Path(staged_override),
  Path(os.environ.get("ZIMAGE_GGUF_STAGE_ROOT",
                      "/kaggle/working/zimage-gguf-stage"))))
 stage("GGUF_LOCAL_STAGE_VERIFIED",path=gguf_path,bytes=Path(gguf_path).stat().st_size)
stage("GGUF_LOAD_BEGIN",source="staged-local" if staged_override else "manifest",
      bytes=Path(gguf_path).stat().st_size)
transformer=ZImageTransformer2DModel.from_single_file(gguf_path,
 quantization_config=GGUFQuantizationConfig(compute_dtype=torch.bfloat16),
 config=str(support),subfolder="transformer",dtype=torch.bfloat16)
stage("GGUF_LOAD_FINISHED")
stage("GGUF_TO_CUDA_BEGIN")
transformer=transformer.to("cuda:0")
stage("GGUF_ON_CUDA",allocated_mib=round(torch.cuda.memory_allocated()/1048576))
stage("VAE_LOAD_BEGIN")
vae=AutoencoderKL.from_pretrained(str(support),subfolder="vae",torch_dtype=torch.bfloat16,
 local_files_only=True)
stage("VAE_LOAD_FINISHED")
vae=vae.to("cuda:0")
vae.enable_tiling()
stage("VAE_ON_CUDA",allocated_mib=round(torch.cuda.memory_allocated()/1048576))
scheduler=FlowMatchEulerDiscreteScheduler.from_pretrained(str(support),subfolder="scheduler",local_files_only=True)
stage("PIPELINE_ASSEMBLY_BEGIN")
pipe=ZImagePipeline(transformer=transformer,vae=vae,scheduler=scheduler,text_encoder=None,tokenizer=None)
stage("PIPELINE_READY",allocated_mib=round(torch.cuda.memory_allocated()/1048576))
lock=threading.Lock()
app=FastAPI(title="Z-Image GPU Inference Worker")
stage("HTTP_APPLICATION_READY")
class Job(BaseModel):
 prompt_id:str=Field(min_length=64,max_length=64)
 seed:int=Field(ge=0,le=4294967295)
 width:int=1024
 height:int=1024
 steps:int=9
 guidance_scale:float=0.0
def sha(p):
 h=hashlib.sha256()
 with open(p,"rb") as f:
  for chunk in iter(lambda:f.read(2**20),b""):h.update(chunk)
 return h.hexdigest()
@app.get("/ready")
def ready():return {"ready":True,"worker_id":args.worker_id,"cache_prompt_ids":list(CACHE)}
@app.get("/health")
def health():return {"status":"ok","worker_id":args.worker_id,"mode":"DYNAMIC_INFERENCE"}
@app.post("/generate")
def generate(job:Job):
 if job.prompt_id not in CACHE:raise HTTPException(404,"prompt cache not ready")
 if (job.width,job.height,job.steps,job.guidance_scale)!=(1024,1024,9,0.0):raise HTTPException(422,"unsupported baseline")
 if not lock.acquire(blocking=False):raise HTTPException(409,"busy")
 try:
  entry=CACHE[job.prompt_id];p=Path(entry["embedding_file"])
  if p.is_symlink() or sha(p)!=entry["embedding_sha256"]:raise HTTPException(500,"embedding corrupted")
  embedding=load_file(str(p),device="cpu")["emb_000"]
  gen=torch.Generator(device="cuda:0").manual_seed(job.seed)
  t=time.monotonic()
  with torch.inference_mode():
   result=pipe(prompt=None,prompt_embeds=[embedding.to("cuda:0")],
     height=1024,width=1024,num_inference_steps=9,guidance_scale=0.0,
     generator=gen,output_type="pil")
  output=ROOT/"output"/f"worker-{args.worker_id}"/f"{job.prompt_id}-seed-{job.seed}.png"
  output.parent.mkdir(parents=True,exist_ok=True)
  # Do not overwrite existing completed artifact with another attempt.
  temp=output.with_name(output.name+".partial."+str(os.getpid()))
  result.images[0].save(temp,format="PNG")
  try:os.link(temp,output)
  except FileExistsError:
   temp.unlink();raise HTTPException(409,"existing artifact requires reconciliation")
  finally:
   if temp.exists():temp.unlink()
  return {"status":"complete","worker_id":args.worker_id,"prompt_id":job.prompt_id,"seed":job.seed,
   "png_path":str(output),"png_sha256":sha(output),"seconds":round(time.monotonic()-t,2)}
 finally:lock.release()
if __name__=="__main__":
 import uvicorn
 uvicorn.run(app,host="127.0.0.1",port=args.port,access_log=False)

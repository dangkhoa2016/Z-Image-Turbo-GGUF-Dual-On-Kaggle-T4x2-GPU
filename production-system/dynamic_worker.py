#!/usr/bin/env python3
"""B1.7 isolated GPU worker — untested with real T4x2, not a production signoff."""
import argparse,hashlib,json,os,time,threading
from pathlib import Path
from fastapi import FastAPI,HTTPException
from pydantic import BaseModel,Field
from dynamic_manifest import read_manifest
parser=argparse.ArgumentParser()
parser.add_argument("--worker-id",type=int,required=True,choices=(0,1))
parser.add_argument("--port",type=int,required=True)
parser.add_argument("--manifest",required=True)
args=parser.parse_args()
if args.port!=12340+args.worker_id:raise RuntimeError("port/slot mismatch")
if os.environ.get("CUDA_VISIBLE_DEVICES")!=str(args.worker_id):raise RuntimeError("physical GPU isolation missing")
if os.environ.get("HF_HUB_OFFLINE")!="1" or os.environ.get("TRANSFORMERS_OFFLINE")!="1":raise RuntimeError("offline mode required")
import torch
from safetensors.torch import load_file
from diffusers import ZImagePipeline,ZImageTransformer2DModel,GGUFQuantizationConfig,AutoencoderKL,FlowMatchEulerDiscreteScheduler
if torch.cuda.device_count()!=1 or "T4" not in torch.cuda.get_device_name(0):raise RuntimeError("one logical T4 required")
CACHE=read_manifest(args.manifest)["entries"]
ROOT=Path("/kaggle/working/zimage-dual")
M=json.loads((ROOT/"manifests/model.json").read_text())
S=json.loads((ROOT/"manifests/support.json").read_text())
support=Path(S["support_root"])
transformer=ZImageTransformer2DModel.from_single_file(M["gguf_path"],
 quantization_config=GGUFQuantizationConfig(compute_dtype=torch.bfloat16),
 config=str(support),subfolder="transformer",dtype=torch.bfloat16).to("cuda:0")
vae=AutoencoderKL.from_pretrained(str(support),subfolder="vae",torch_dtype=torch.bfloat16,
 local_files_only=True).to("cuda:0");vae.enable_tiling()
scheduler=FlowMatchEulerDiscreteScheduler.from_pretrained(str(support),subfolder="scheduler",local_files_only=True)
pipe=ZImagePipeline(transformer=transformer,vae=vae,scheduler=scheduler,text_encoder=None,tokenizer=None)
lock=threading.Lock()
app=FastAPI(title="ZImage B1.7 dynamic worker")
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

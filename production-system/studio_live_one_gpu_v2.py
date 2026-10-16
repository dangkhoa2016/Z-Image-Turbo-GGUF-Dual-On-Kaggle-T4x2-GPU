#!/usr/bin/env python3
"""Bounded Studio-origin GPU run: queue -> encoding -> dual T4 -> receipt. Never replay on failure."""
import os,sys,json,time,importlib.metadata as md,urllib.request,sqlite3
from pathlib import Path
ROOT=Path("/kaggle/working/zimage-dual")
SRC=ROOT/"production-system"
sys.path.insert(0,str(SRC))
RUN=SRC/"studio-live-20261015-v2"
DB=RUN/"api.sqlite3"
assert os.getenv("ZIMAGE_B1_DB")==str(DB)
from b113_shared_lifecycle import SharedLifecycle
support=json.loads((ROOT/"manifests/support.json").read_text())
identity={"support_manifest_sha256":support["manifest_sha256"],"diffusers_version":md.version("diffusers"),"max_sequence_length":512,"text_encoder_dtype":"bfloat16"}
def callback(sid,prepared):
 from b114_shared_gpu_supervisor import run
 print("STUDIO_GPU_WORKER_LAUNCH",sid,flush=True)
 result=run(sid,DB,RUN/"sessions",ROOT/"output",300,1800,True)
 print("STUDIO_GPU_DISPATCH",json.dumps(result,sort_keys=True),flush=True)
 return result
life=SharedLifecycle(api_db=DB,sessions_root=RUN/"sessions",artifact_root=ROOT/"output",identity=identity,mode="gpu0",max_prompts=1,max_jobs=1)
print("STUDIO_GPU_REAL_RUN_START",flush=True)
result=life.run_one(callback)
assert result["archive"]["verified_png"]==1
(RUN/"studio-e2e-result.json").write_text(json.dumps(result,indent=2))
print("STUDIO_GPU_E2E_COMPLETED",json.dumps(result["archive"]),flush=True)

#!/usr/bin/env python3
"""Validate imports in the exact vendored runtime before any GPU jobs are submitted."""
import importlib.metadata as md
import json,sys,time
start=time.monotonic()
def mark(stage,**kw):
 print("GPU_RUNTIME_PROBE "+json.dumps({"stage":stage,
       "seconds":round(time.monotonic()-start,2),**kw},sort_keys=True),flush=True)
mark("PYTHON_READY",python=sys.version.split()[0])
import torch
mark("PYTORCH_IMPORTED",torch=str(torch.__version__),cuda=str(torch.version.cuda))
import torchao
mark("TORCHAO_IMPORTED",torchao=md.version("torchao"))
from diffusers import (ZImagePipeline,ZImageTransformer2DModel,GGUFQuantizationConfig,
                       AutoencoderKL,FlowMatchEulerDiscreteScheduler)
mark("DIFFUSERS_IMAGE_IMPORTS_READY",diffusers=md.version("diffusers"),
     gguf=md.version("gguf"),cuda_devices=torch.cuda.device_count())
print("GPU_RUNTIME_IMPORT_SMOKE_PASS",flush=True)

#!/usr/bin/env python3
"""Dispatch verified pre-encoded jobs to isolated Kaggle GPU workers."""
import os,json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
run=root/"production-system/gpu-integration-20261015"
os.environ["ZIMAGE_B1_DB"]=str(run/"api.sqlite3")
from unified_pipeline import UnifiedPipeline
identity=json.loads((run/"session/b18-encoder-identity.json").read_text())
pipe=UnifiedPipeline(api_db=run/"api.sqlite3",registry_db=run/"registry.sqlite3",cache_root=run/"cache",identity=identity,session_dir=run/"session",artifact_root=root/"output",mode="gpu0")
print("GPU_DISPATCH_BEGIN",flush=True)
out=pipe.dispatch(timeout=1800)
print("GPU_DISPATCH_RESULT="+json.dumps(out,sort_keys=True),flush=True)

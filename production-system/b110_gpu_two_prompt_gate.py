#!/usr/bin/env python3
"""B1.10 isolated, real-GPU two-prompt encoding gate. Does NOT start workers."""
import os,secrets,json,importlib.metadata as md
from pathlib import Path
from fastapi.testclient import TestClient
from hashlib import sha256
from uuid import uuid4
ROOT=Path("/kaggle/working/zimage-dual")
RUN=ROOT/"production-system"/"gpu-integration-20261015"
RUN.mkdir(exist_ok=True)
os.environ["ZIMAGE_B1_DB"]=str(RUN/"api.sqlite3")
os.environ["ZIMAGE_B1_API_KEY"]=secrets.token_urlsafe(36)
import service
from unified_pipeline import UnifiedPipeline
support=json.loads((ROOT/"manifests/support.json").read_text())
identity={"support_manifest_sha256":support["manifest_sha256"],"diffusers_version":md.version("diffusers"),"max_sequence_length":512,"text_encoder_dtype":"bfloat16"}
prompts=[
("A sunlit ceramic teapot on a polished oak table, botanical studio photograph, realistic glazing and soft morning shadows",146301),
("An antique brass compass resting on a folded ocean navigation map, detailed macro product photography, natural warm light",146302)]
client=TestClient(service.app)
headers={"Authorization":"Bearer "+os.environ["ZIMAGE_B1_API_KEY"]}
results=[]
for prompt,seed in prompts:
 r=client.post("/v1/jobs",headers=headers,json={"prompt":prompt,"seed":seed})
 r.raise_for_status()
 results.append({"job_id":r.json()["job_id"],"seed":seed,"prompt_sha256":sha256(prompt.encode()).hexdigest()})
(RUN/"job-submissions.json").write_text(json.dumps(results,indent=2)+"\n")
print("GPU_GATE_SUBMITTED="+str(len(results)),flush=True)
pipeline=UnifiedPipeline(api_db=RUN/"api.sqlite3",registry_db=RUN/"registry.sqlite3",cache_root=RUN/"cache",identity=identity,session_dir=RUN/"session",artifact_root=ROOT/"output",mode="gpu0")
print("GPU_GATE_PREPARE_BEGIN",flush=True)
res=pipeline.prepare(max_items=2)
print("GPU_GATE_PREPARE_RESULT="+json.dumps(res,sort_keys=True),flush=True)

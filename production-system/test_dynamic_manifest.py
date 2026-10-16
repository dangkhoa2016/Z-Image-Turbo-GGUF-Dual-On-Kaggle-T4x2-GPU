import tempfile,hashlib
from pathlib import Path
import torch
from safetensors.torch import save_file
from embedding_registry import Registry
from dynamic_manifest import export_manifest,read_manifest
IDENTITY={"support_manifest_sha256":"a"*64,"diffusers_version":"0.41.0","max_sequence_length":512,"text_encoder_dtype":"bfloat16"}
with tempfile.TemporaryDirectory(prefix="b17-test-") as td:
 root=Path(td);r=Registry(root/"db.sqlite3",root/"cache",IDENTITY)
 prompt="An orange cat relaxing on a vintage couch"
 j=r.enqueue(prompt);key=j["cache_key"]
 r.claim("testing-owner-123",lease=100)
 p=r.root/"embeddings"/f"{key}.safetensors";p.parent.mkdir(exist_ok=True)
 save_file({"emb_000":torch.zeros((59,2560),dtype=torch.bfloat16)},str(p),
  metadata={"cache_key":key,"prompt_sha256":j["prompt_sha256"],"producer":"cpu-mock-NEVER-PRODUCTION"})
 r.complete(key,"testing-owner-123",f"embeddings/{key}.safetensors")
 manifest=root/"batch-manifest.json"
 try:export_manifest(r,[prompt],manifest)
 except RuntimeError:pass
 else:raise AssertionError("mock accepted into production manifest")
 obj=export_manifest(r,[prompt],manifest,allow_mock=True)
 assert obj["test_only"] is True
 try:read_manifest(manifest)
 except RuntimeError:pass
 else:raise AssertionError("test_only manifest accepted for inference")
 assert len(read_manifest(manifest,allow_mock=True)["entries"])==1
 with p.open("ab") as f:f.write(b"tampered")
 try:read_manifest(manifest,allow_mock=True)
 except RuntimeError:pass
 else:raise AssertionError("corrupted cache accepted")
 print("B17_CPU_MANIFEST_PASS ready_registry trusted_provenance_mock_isolation checksum_rejection")
 print("B17_REAL_GPU_INFERENCE=NOT_TESTED")

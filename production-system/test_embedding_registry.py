"""B1.5 CPU registry tests; synthetic embeddings only (never actual text encoding)."""
import tempfile,hashlib,json,sqlite3
from pathlib import Path
import torch
from safetensors.torch import save_file
from embedding_registry import Registry
ID={"support_manifest_sha256":"d2092798f917a83ed79981ec23cdb5d33ee25b86f667fa46a563476a083dd7d7",
 "diffusers_version":"0.41.0","max_sequence_length":512,"text_encoder_dtype":"bfloat16"}
with tempfile.TemporaryDirectory(prefix="zimage-b15-") as td:
 root=Path(td);cache=root/"cache";(cache/"embeddings").mkdir(parents=True)
 r=Registry(root/"new-registry.sqlite3",cache,ID)
 a="A bright yellow submarine floating on calm water"
 one=r.enqueue(a)
 k=r.key(a)
 # Bit-for-bit frozen legacy identity algorithm.
 expected=hashlib.sha256(json.dumps({"prompt":a,**ID},sort_keys=True,ensure_ascii=False,separators=(",",":")).encode()).hexdigest()
 assert k==expected==one["cache_key"]
 assert r.enqueue(a)["cache_key"]==k
 assert r.status(k)["status"]=="pending"
 claim=r.claim("encoder-owner-1234",lease=60)
 assert claim["cache_key"]==k
 assert r.claim("another-owner-2345") is None
 path=cache/"embeddings"/(k+".safetensors")
 save_file({"emb_000":torch.zeros((59,2560),dtype=torch.bfloat16)},str(path),metadata={"cache_key":k,"prompt_sha256":one["prompt_sha256"]})
 try:r.complete(k,"wrong-owner-1234","embeddings/"+path.name)
 except RuntimeError:pass
 else:raise AssertionError("wrong owner was allowed")
 digest=r.complete(k,"encoder-owner-1234","embeddings/"+path.name)
 assert digest==hashlib.sha256(path.read_bytes()).hexdigest()
 assert r.status(k)["status"]=="ready" and r.check_ready(k)
 assert r.enqueue(a)["status"]=="ready"
 # Changed file bytes cannot be accepted with previous digest.
 save_file({"emb_000":torch.ones((59,2560),dtype=torch.bfloat16)},str(path),metadata={"cache_key":k})
 assert not r.check_ready(k)
 # Crash / expired lease becomes UNCERTAIN and is not reclaimed automatically.
 b=r.enqueue("A moonlit forest scene with a green bicycle")
 other=r.claim("abandoned-encoder-worker",lease=1)
 assert other["cache_key"]==b["cache_key"]
 assert r.expire(now=10**12)==1
 assert r.status(b["cache_key"])["status"]=="uncertain"
 assert r.claim("next-encoder-321") is None
 # Another unique prompt is queued independently.
 assert r.enqueue("A neon blue car in Tokyo city")["status"]=="pending"
 assert r.claim("new-encoder-444")["status"]=="pending"
 # No codec-specific artifacts exposed from registry test
 with sqlite3.connect(root/"new-registry.sqlite3") as c:assert c.execute("PRAGMA integrity_check").fetchone()[0]=="ok"
 print("B15_CPU_REGISTRY_PASS identity_hash dedupe ownership verified_safetensors SHA256 corruption_detection uncertain_expired")
 print("B15_ACTUAL_TEXT_ENCODING=NOT_TESTED GPU=NOT_USED")

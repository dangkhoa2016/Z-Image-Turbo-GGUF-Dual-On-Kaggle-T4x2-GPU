"""B1.6 CPU process boundary: encode batch, verify, idempotent replay, fail-closed mock."""
import os,tempfile,json,subprocess,sys,sqlite3
from pathlib import Path
from embedding_registry import Registry
ID={"support_manifest_sha256":"d2092798f917a83ed79981ec23cdb5d33ee25b86f667fa46a563476a083dd7d7",
    "diffusers_version":"0.41.0","max_sequence_length":512,"text_encoder_dtype":"bfloat16"}
with tempfile.TemporaryDirectory(prefix="b16-test-") as tmp:
 root=Path(tmp)
 os.environ["ZIMAGE_B16_TEST_ROOT"]=str(root)
 db=root/"registry.sqlite3";cache=root/"cache"
 idf=root/"identity.json";idf.write_text(json.dumps(ID))
 prompts=["An orange bicycle beside a river","A tiny porcelain lighthouse on sand"]
 pf=root/"prompts.json";pf.write_text(json.dumps(prompts))
 cmd=[sys.executable,str(Path(__file__).with_name("phase_controller.py")),"--db",str(db),"--cache-root",str(cache),
      "--identity",str(idf),"--prompt-json",str(pf),"--max-items","4","--mode","cpu-mock"]
 first=subprocess.run(cmd,capture_output=True,text=True,env=os.environ.copy(),timeout=90)
 assert first.returncode==0,first.stderr
 result=json.loads(first.stdout.strip().splitlines()[-1])
 assert result["status"]=="READY_FOR_INFERENCE_START" and result["verified_ready"]==2
 assert result["inference_workers_started"] is False and result["real_gpu_encoding"] is False
 reg=Registry(db,cache,ID)
 assert all(reg.check_ready(reg.key(x)) for x in prompts)
 redo=subprocess.run(cmd,capture_output=True,text=True,env=os.environ.copy(),timeout=90)
 assert redo.returncode==0,redo.stderr
 with sqlite3.connect(db) as c:
  assert c.execute("select count(*) from encoding").fetchone()[0]==2
  assert c.execute("select count(*) from encoding where status='ready'").fetchone()[0]==2
 # Existing cache checksum corruption must block future inference phase.
 bad=cache/"embeddings"/(reg.key(prompts[0])+".safetensors")
 with bad.open("ab") as f:f.write(b"CORRUPTED")
 broken=subprocess.run(cmd,capture_output=True,text=True,env=os.environ.copy(),timeout=90)
 assert broken.returncode!=0
 blocked=json.loads((root/"b16-phase-status.json").read_text())
 assert blocked["status"]=="BLOCKED" and blocked["inference_workers_started"] is False
 # CPU never launched the real Qwen3 encoder or inference workers.
 print("B16_CPU_PROCESS_PASS subprocess bounded_batch dedupe READY_gate restart checksum_corruption_BLOCKED")
 print("B16_GPU_ENCODER=NOT_TESTED; INFERENCE_WORKERS=NOT_STARTED")

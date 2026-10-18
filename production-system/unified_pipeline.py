"""Two-phase pipeline: job API, verified embeddings, inference manifest and dual HTTP workers.

Safety properties:
- New separate SQLite and cache locations, unchanged historical files.
- CPU mock encoding only inside /tmp/b16-test-* and test manifest never usable for real GPU.
- Never map an API prompt to an inference worker without verified READY registry+manifest.
- Do not hot-swap manifest while worker HTTP services are running.
- GPU implementation is not asserted tested; GPU worker processes are launched separately.
"""
import hashlib,json,os,sqlite3,subprocess,sys
from contextlib import closing
from pathlib import Path
from embedding_registry import Registry
from dynamic_manifest import export_manifest,read_manifest
from http_dispatcher import Dispatcher,prepare_http,connect
from worker_adapter import WorkerAdapter

class UnifiedPipeline:
 def __init__(self, *, api_db, registry_db,cache_root,identity,session_dir,artifact_root,mode):
  if mode not in ("cpu-mock","gpu0"):raise ValueError("mode must be explicit")
  self.api_db=Path(api_db).resolve();self.registry_db=Path(registry_db).resolve()
  self.cache_root=Path(cache_root).resolve()
  self.session_dir=Path(session_dir).resolve()
  self.artifact_root=Path(artifact_root).resolve()
  self.mode=mode
  # Existing B1 components use ZIMAGE_B1_DB in their connection factory.
  if self.api_db!=Path(os.environ.get("ZIMAGE_B1_DB","")).resolve():
   raise RuntimeError("API database environment mismatch")
  if mode=="cpu-mock":
   test=Path(os.environ.get("ZIMAGE_B16_TEST_ROOT","")).resolve()
   if not str(test).startswith("/tmp/b16-test-") or any(not p.is_relative_to(test) for p in
       (self.api_db,self.registry_db,self.cache_root,self.session_dir,self.artifact_root)):
    raise RuntimeError("Mock integration must be entirely inside the synthetic test directory")
  self.session_dir.mkdir(parents=True,exist_ok=True)
  self.identity=identity
  self.registry=Registry(self.registry_db,self.cache_root,identity)
  self.manifest_path=self.session_dir/"b18-inference-manifest.json"
  self.identity_path=self.session_dir/"b18-encoder-identity.json"
  prepare_http()
 def pending_prompts(self,max_items=8):
  """Only distinct pending, currently unmapped user prompts; excludes cancelled jobs."""
  if not 1<=max_items<=32:raise ValueError("batch bound exceeded")
  with closing(connect()) as c:
   rows=c.execute("""SELECT j.prompt FROM jobs j LEFT JOIN b14_prompt_map m ON m.prompt=j.prompt
     WHERE j.state='queued' AND m.prompt IS NULL GROUP BY j.prompt ORDER BY MIN(j.created_at),j.prompt LIMIT ?""",
    (max_items,)).fetchall()
  return [r[0] for r in rows]
 def prepare(self,max_items=8):
  prompts=self.pending_prompts(max_items)
  if not prompts:raise RuntimeError("No queued prompts requiring embedding; no manifest changes")
  # Avoid invalidating mapping/workers of a previous active inference session.
  with closing(connect()) as c:
   exists=c.execute("SELECT COUNT(*) FROM b14_prompt_map").fetchone()[0]
  if exists:raise RuntimeError("Mapping already active; new session must explicitly reconcile/drain first")
  # Encoder must run before worker ports are online (phase_controller checks ports).
  self.identity_path.write_text(json.dumps(self.identity,sort_keys=True))
  request_path=self.session_dir/"b18-encoder-prompts.json"
  request_path.write_text(json.dumps(prompts,ensure_ascii=False))
  cmd=[sys.executable,str(Path(__file__).with_name("phase_controller.py")),
       "--db",str(self.registry_db),"--cache-root",str(self.cache_root),
       "--identity",str(self.identity_path),"--prompt-json",str(request_path),
       "--mode",self.mode,"--max-items",str(max_items)]
  result=subprocess.run(cmd,capture_output=True,text=True,timeout=3600,check=False)
  if result.returncode!=0:raise RuntimeError("Encoding phase failed: "+result.stderr[-1200:])
  status=json.loads((self.registry_db.parent/"b16-phase-status.json").read_text())
  if status.get("status")!="READY_FOR_INFERENCE_START" or status.get("mode")!=self.mode:
   raise RuntimeError("Invalid phase gate result")
  obj=export_manifest(self.registry,prompts,self.manifest_path,allow_mock=self.mode=="cpu-mock")
  # Independently re-verify before exposing mapping to the dispatcher.
  checked=read_manifest(self.manifest_path,allow_mock=self.mode=="cpu-mock")
  if sorted(checked["entries"])!=sorted(self.registry.key(p) for p in prompts):
   raise RuntimeError("Manifest entries do not match requested prompts")
  with closing(connect()) as c:
   c.execute("BEGIN IMMEDIATE")
   try:
    # No mapping is published until all embeddings have passed integrity gates.
    for p in prompts:
     key=self.registry.key(p)
     if key not in checked["entries"]:raise RuntimeError("Manifest missing prompt ID")
     c.execute("INSERT INTO b14_prompt_map(prompt,prompt_id) VALUES(?,?)",(p,key))
    c.execute("COMMIT")
   except BaseException:c.execute("ROLLBACK");raise
  return {"phase":"READY_FOR_HTTP_WORKERS","prompts":len(prompts),
          "manifest":str(self.manifest_path),"manifest_sha256":hashlib.sha256(self.manifest_path.read_bytes()).hexdigest(),
          "mode":self.mode,"gpu_inference":"NOT_EXECUTED_BY_PREPARE"}
 def dispatch(self,timeout=15):
  if not self.manifest_path.is_file():raise RuntimeError("No verified manifest")
  obj=read_manifest(self.manifest_path,allow_mock=self.mode=="cpu-mock")
  if obj["test_only"] != (self.mode=="cpu-mock"):raise RuntimeError("Manifest provenance mode mismatch")
  with closing(connect()) as c:
   mapping=c.execute("SELECT prompt,prompt_id FROM b14_prompt_map").fetchall()
  if not mapping:raise RuntimeError("No prepared prompt mapping")
  for p,key in mapping:
   if self.registry.key(p)!=key or key not in obj["entries"] or not self.registry.check_ready(key):
    raise RuntimeError("Mapping/cache integrity mismatch; refusing dispatch")
  # Adapters verify real PNG files even in CPU mock path; no unchecked job completion.
  adapters={i:WorkerAdapter(i,f"http://127.0.0.1:{12340+i}",self.artifact_root) for i in (0,1)}
  return Dispatcher(adapters).drain(timeout=timeout)

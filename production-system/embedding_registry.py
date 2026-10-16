"""B1.5 CPU cache planning/state; encoder and inference are NOT executed here."""
import hashlib,json,os,sqlite3,time,uuid
from pathlib import Path
from contextlib import closing
from threading import RLock
from safetensors import safe_open
REGISTRY_LOCK=RLock()
def digest_bytes(b):return hashlib.sha256(b).hexdigest()
def hash_file(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for part in iter(lambda:f.read(2**20),b""):h.update(part)
 return h.hexdigest()
class Registry:
 def __init__(self,db_path,cache_root,identity):
  self.db_path=Path(db_path);self.root=Path(cache_root)
  self.db_path.parent.mkdir(parents=True,exist_ok=True)
  self.root.mkdir(parents=True,exist_ok=True)
  self.identity={k:identity[k] for k in ("support_manifest_sha256","diffusers_version","max_sequence_length","text_encoder_dtype")}
  if self.identity["max_sequence_length"]!=512 or self.identity["text_encoder_dtype"]!="bfloat16":raise ValueError("unsupported frozen encoder baseline")
  with self.conn() as c:
   c.execute("""CREATE TABLE IF NOT EXISTS encoding (
    cache_key TEXT PRIMARY KEY,prompt TEXT NOT NULL,prompt_sha256 TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('pending','encoding','ready','uncertain')),
    owner TEXT,lease_deadline REAL,embedding_file TEXT,embedding_sha256 TEXT,
    created_at REAL NOT NULL,updated_at REAL NOT NULL,error TEXT)""")
 def conn(self):
  c=sqlite3.connect(self.db_path,timeout=15,isolation_level=None)
  c.row_factory=sqlite3.Row;c.execute("PRAGMA busy_timeout=15000")
  c.execute("PRAGMA journal_mode=WAL")
  return c
 def key(self,prompt):
  if not isinstance(prompt,str) or not 3<=len(prompt)<=2000:raise ValueError("invalid prompt length")
  fields={"prompt":prompt,**self.identity}
  return digest_bytes(json.dumps(fields,sort_keys=True,ensure_ascii=False,separators=(",",":")).encode())
 def enqueue(self,prompt):
  k=self.key(prompt);now=time.time()
  with REGISTRY_LOCK,closing(self.conn()) as c:
   c.execute("INSERT OR IGNORE INTO encoding(cache_key,prompt,prompt_sha256,status,created_at,updated_at) VALUES(?,?,?,?,?,?)",
    (k,prompt,digest_bytes(prompt.encode()),"pending",now,now))
   return dict(c.execute("SELECT * FROM encoding WHERE cache_key=?",(k,)).fetchone())
 def claim(self,owner,lease=600):
  if not isinstance(owner,str) or len(owner)<8 or lease<1:raise ValueError("invalid owner/lease")
  with REGISTRY_LOCK,closing(self.conn()) as c:
   c.execute("BEGIN IMMEDIATE")
   try:
    row=c.execute("SELECT * FROM encoding WHERE status='pending' ORDER BY created_at,cache_key LIMIT 1").fetchone()
    if not row:c.execute("COMMIT");return None
    changed=c.execute("UPDATE encoding SET status='encoding',owner=?,lease_deadline=?,updated_at=? WHERE cache_key=? AND status='pending'",
       (owner,time.time()+lease,time.time(),row["cache_key"])).rowcount
    assert changed==1
    c.execute("COMMIT");return dict(row)
   except BaseException:c.execute("ROLLBACK");raise
 def expire(self,now=None):
  now=time.time() if now is None else now
  with REGISTRY_LOCK,closing(self.conn()) as c:
   return c.execute("UPDATE encoding SET status='uncertain',owner=NULL,lease_deadline=NULL,error='expired encoding lease; reconcile manually',updated_at=? WHERE status='encoding' AND lease_deadline<?",(now,now)).rowcount
 def complete(self,key,owner,relative_file):
  # Encoder process separately writes and verifies a .safetensors file, only this CPU gate can publish READY.
  if not isinstance(relative_file,str) or relative_file!=f"embeddings/{key}.safetensors":raise ValueError("unexpected embedding path")
  path=self.root/relative_file
  if path.is_symlink() or path.parent.is_symlink() or not path.is_file() or path.resolve()!=path:raise ValueError("unsafe embedding location")
  with safe_open(path,framework="pt",device="cpu") as f:
   if list(f.keys())!=["emb_000"]:raise ValueError("unexpected tensor keys")
   t=f.get_tensor("emb_000")
   if t.ndim!=2 or t.dtype.__str__()!="torch.bfloat16" or t.shape[1]!=2560 or t.shape[0]<1 or t.shape[0]>512:raise ValueError("embedding incompatible")
   metadata=f.metadata() or {}
   if metadata.get("cache_key")!=key:raise ValueError("cache key metadata mismatch")
  actual=hash_file(path)
  with REGISTRY_LOCK,closing(self.conn()) as c:
   c.execute("BEGIN IMMEDIATE")
   try:
    n=c.execute("""UPDATE encoding SET status='ready',owner=NULL,lease_deadline=NULL,embedding_file=?,embedding_sha256=?,error=NULL,updated_at=?
      WHERE cache_key=? AND status='encoding' AND owner=? AND lease_deadline>?""",
     (relative_file,actual,time.time(),key,owner,time.time())).rowcount
    if n!=1:raise RuntimeError("lost encoding lease; cannot publish READY")
    c.execute("COMMIT");return actual
   except BaseException:c.execute("ROLLBACK");raise
 def check_ready(self,key):
  with closing(self.conn()) as c:row=c.execute("SELECT * FROM encoding WHERE cache_key=?",(key,)).fetchone()
  if row is None or row["status"]!="ready":return False
  path=self.root/row["embedding_file"]
  if path.is_symlink() or not path.is_file() or path.resolve()!=path or hash_file(path)!=row["embedding_sha256"]:return False
  return True
 def status(self,key):
  with closing(self.conn()) as c:row=c.execute("SELECT * FROM encoding WHERE cache_key=?",(key,)).fetchone()
  return dict(row) if row else None

#!/usr/bin/env python3
"""B1.16 isolated full portable snapshot + verified path relocation, never auto-replay."""
import argparse,hashlib,json,sqlite3,zipfile,tempfile
from pathlib import Path
from safetensors import safe_open
ROOT=Path("/kaggle/working/zimage-dual/production-system")
def h(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ok(v,m):
 if not v:raise RuntimeError(m)
def snapshot_db(source,dest):
 with sqlite3.connect(f"file:{source}?mode=ro",uri=True) as a,sqlite3.connect(dest) as b:a.backup(b)
 with sqlite3.connect(dest) as c:ok(c.execute("PRAGMA integrity_check").fetchone()[0]=="ok","DB corruption")
def pack(source,out):
 source=Path(source).resolve(strict=True);out=Path(out)
 ok(source.is_relative_to(ROOT) and not out.exists(),"unsafe source/out")
 with tempfile.TemporaryDirectory(dir="/kaggle/working",prefix="b116-") as temp:
  files={}
  for p in source.rglob("*"):
   if not p.is_file() or p.is_symlink() or p.name.endswith(("-wal","-shm",".lock",".pid")):continue
   rel=str(p.relative_to(source))
   if p.suffix==".sqlite3":
    target=Path(temp)/rel;target.parent.mkdir(parents=True,exist_ok=True)
    snapshot_db(p,target);files[rel]=target
   elif p.suffix in (".json",".log",".txt",".safetensors",".png"):
    files[rel]=p
  ok("api.sqlite3" in files and any(n.endswith("/registry.sqlite3") for n in files),"missing session registry")
  with sqlite3.connect(files["api.sqlite3"]) as c:
   receipts=c.execute("SELECT path,sha256,worker_id FROM b14_artifacts").fetchall()
   for path,digest,slot in receipts:
    p=Path(path)
    ok(slot in (0,1) and p.parent==Path(f"/kaggle/working/zimage-dual/output/worker-{slot}") and p.is_file() and h(p)==digest,"invalid PNG receipt")
    files[f"restored-artifacts/worker-{slot}/{p.name}"]=p
  manifest={"schema":"zimage-b116-v3","files":{n:{"sha256":h(p),"size":p.stat().st_size} for n,p in sorted(files.items())}}
  with zipfile.ZipFile(out,"x",zipfile.ZIP_DEFLATED) as z:
   z.writestr("MANIFEST.json",json.dumps(manifest,sort_keys=True,indent=2))
   for n,p in files.items():z.write(p,"payload/"+n)
 with zipfile.ZipFile(out) as z:ok(z.testzip() is None,"zip damaged")
 digest=h(out);Path(str(out)+".sha256").write_text(f"{digest}  {out.name}\n")
 return {"status":"B116_V3_PACK_PASS","files":len(files),"bytes":out.stat().st_size,"sha256":digest}
def restore(archive,dest):
 archive=Path(archive);dest=Path(dest)
 ok(dest.resolve().is_relative_to(ROOT) and not dest.exists(),"unsafe/existing restore dir")
 with zipfile.ZipFile(archive) as z:
  ok(z.testzip() is None,"bad zip")
  man=json.loads(z.read("MANIFEST.json"))
  ok(man.get("schema")=="zimage-b116-v3","bad schema")
  files=man["files"];ok(set(z.namelist())=={"MANIFEST.json"}|{"payload/"+x for x in files},"unexpected members")
  dest.mkdir(parents=True)
  try:
   for rel,meta in files.items():
    ok(not Path(rel).is_absolute() and ".." not in Path(rel).parts,"unsafe member")
    dst=dest/rel;dst.parent.mkdir(parents=True,exist_ok=True)
    data=z.read("payload/"+rel)
    ok(hashlib.sha256(data).hexdigest()==meta["sha256"] and len(data)==meta["size"],"tampered member")
    dst.write_bytes(data)
   sessions=list((dest/"sessions").glob("b112-*/session/b18-inference-manifest.json"))
   ok(len(sessions)==1,"expected single session")
   mp=sessions[0];session=mp.parent.parent
   manifest=json.loads(mp.read_text())
   registry=session/"registry.sqlite3"
   ok(registry.is_file(),"missing registry")
   for key,entry in manifest["entries"].items():
    emb=session/"cache/embeddings"/f"{key}.safetensors"
    ok(emb.is_file() and h(emb)==entry["embedding_sha256"],"embedding digest mismatch")
    with safe_open(emb,framework="pt",device="cpu") as f:
     t=f.get_tensor("emb_000");meta=f.metadata() or {}
     ok(meta.get("cache_key")==key and t.ndim==2 and t.shape[1]==2560,"embedding invalid")
    entry["embedding_file"]=str(emb.resolve())
   mp.write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
   with sqlite3.connect(registry) as c:
    ok(c.execute("PRAGMA integrity_check").fetchone()[0]=="ok","registry integrity")
    ok(c.execute("SELECT COUNT(*) FROM encoding WHERE status='ready'").fetchone()[0]==len(manifest["entries"]),"registry mismatch")
   with sqlite3.connect(dest/"api.sqlite3") as c:
    for jobid,old,digest,slot in c.execute("SELECT job_id,path,sha256,worker_id FROM b14_artifacts").fetchall():
     p=dest/"restored-artifacts"/f"worker-{slot}"/Path(old).name
     ok(p.is_file() and h(p)==digest,"PNG digest mismatch")
     c.execute("UPDATE b14_artifacts SET path=? WHERE job_id=?",(str(p.resolve()),jobid))
     c.execute("UPDATE b112_artifact_history SET path=? WHERE job_id=?",(str(p.resolve()),jobid))
    sid=session.name
    c.execute("UPDATE b112_sessions SET manifest=?,manifest_sha256=? WHERE session_id=?",(str(mp.resolve()),h(mp),sid))
    jobs=dict(c.execute("SELECT state,COUNT(*) FROM jobs GROUP BY state"))
    stages=dict(c.execute("SELECT status,COUNT(*) FROM b112_sessions GROUP BY status"))
    c.commit()
   from dynamic_manifest import read_manifest
   read_manifest(mp,allow_mock=False)
   gate={"status":"B116_RESTORE_VERIFIED_QUARANTINED" if jobs.get("running",0) or jobs.get("uncertain",0) or any(stages.get(x,0) for x in ("PREPARING","READY","DISPATCHING","BLOCKED")) else "B116_PORTABLE_RESTORE_PASS",
         "jobs":jobs,"sessions":stages,"registry_ready":len(manifest["entries"]),"automatic_replay":False}
   (dest/"B116-RESTORE-GATE.json").write_text(json.dumps(gate,indent=2))
   return gate
  except BaseException:
   (dest/"DO-NOT-RUN-RESTORE-INCOMPLETE").write_text("FAIL CLOSED\n")
   raise
if __name__=="__main__":
 parser=argparse.ArgumentParser();parser.add_argument("action",choices=("pack","restore"));parser.add_argument("first");parser.add_argument("second");a=parser.parse_args()
 try:print(json.dumps(pack(a.first,a.second) if a.action=="pack" else restore(a.first,a.second),sort_keys=True))
 except Exception as e:print("B116_BLOCKED",type(e).__name__,str(e));raise SystemExit(2)

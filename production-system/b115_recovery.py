#!/usr/bin/env python3
"""B1.15 offline portable checkpoint and fail-closed restore; Kaggle-only paths."""
import argparse,hashlib,json,os,sqlite3,tempfile,zipfile
from pathlib import Path
ROOT=Path("/kaggle/working/zimage-dual/production-system")
def sha(p):
 h=hashlib.sha256()
 with open(p,"rb") as f:
  for chunk in iter(lambda:f.read(1<<20),b""):h.update(chunk)
 return h.hexdigest()
def guard(v,msg):
 if not v:raise RuntimeError(msg)
def dbcopy(src,dst):
 with sqlite3.connect(f"file:{src}?mode=ro",uri=True) as a,sqlite3.connect(dst) as b:a.backup(b)
 with sqlite3.connect(dst) as c:guard(c.execute("PRAGMA integrity_check").fetchone()[0]=="ok","database integrity")
def checkpoint(source,out):
 source=Path(source).resolve(strict=True);out=Path(out).resolve()
 guard(source.is_relative_to(ROOT) and source.is_dir(),"unsafe source")
 guard(out.parent==Path("/kaggle/working") and not out.exists(),"unsafe/existing archive")
 db=source/"api.sqlite3";guard(db.is_file(),"missing sqlite")
 with tempfile.TemporaryDirectory(prefix="b115-snapshot-",dir="/kaggle/working") as t:
  snap=Path(t)/"api.sqlite3";dbcopy(db,snap)
  files={"api.sqlite3":snap}
  # Include only files within the new isolated acceptance run, never secrets or model weights.
  for p in source.rglob("*"):
   if not p.is_file() or p.is_symlink() or p==db:continue
   if p.name.endswith(("-wal","-shm",".lock",".pid")):continue
   if p.suffix in (".safetensors",".json",".log",".png",".txt"):
    files[str(p.relative_to(source))]=p
  with sqlite3.connect(snap) as c:
   if c.execute("SELECT 1 FROM sqlite_master WHERE name='b14_artifacts'").fetchone():
    receipts=c.execute("SELECT path,sha256,worker_id FROM b14_artifacts").fetchall()
    for old,digest,slot in receipts:
     pic=Path(old)
     guard(slot in (0,1) and pic.is_file() and not pic.is_symlink() and sha(pic)==digest,"PNG receipt verification failure")
     guard(pic.parent==Path("/kaggle/working/zimage-dual/output")/f"worker-{slot}","PNG outside output root")
     files[f"restored-artifacts/worker-{slot}/{pic.name}"]=pic
  manifest={"schema":"zimage-b115-checkpoint-v1" ,"source_subdir":source.name,
            "files":{k:{"sha256":sha(v),"size":v.stat().st_size} for k,v in sorted(files.items())}}
  with zipfile.ZipFile(out,"x",zipfile.ZIP_DEFLATED,compresslevel=6) as z:
   z.writestr("CHECKPOINT-MANIFEST.json",json.dumps(manifest,indent=2,sort_keys=True)+"\n")
   for name,p in files.items():z.write(p,"payload/"+name)
 with zipfile.ZipFile(out) as z:guard(z.testzip() is None,"invalid zip")
 digest=sha(out);Path(str(out)+".sha256").write_text(digest+"  "+out.name+"\n")
 return {"status":"B115_CHECKPOINT_PASS","files":len(files),"bytes":out.stat().st_size,"sha256":digest}
def restore(archive,dest):
 archive=Path(archive).resolve(strict=True);dest=Path(dest).resolve()
 guard(dest.is_relative_to(ROOT) and not dest.exists(),"destination must be new within project")
 guard(archive.is_file(),"missing archive")
 with zipfile.ZipFile(archive) as z:
  guard(z.testzip() is None,"zip CRC failure")
  data=json.loads(z.read("CHECKPOINT-MANIFEST.json"))
  guard(data.get("schema")=="zimage-b115-checkpoint-v1","unsupported schema")
  manifest=data["files"]
  names=set(z.namelist())
  guard(names=={"CHECKPOINT-MANIFEST.json"}|{"payload/"+p for p in manifest},"unexpected zip members")
  dest.mkdir(parents=True)
  try:
   for rel,meta in manifest.items():
    guard(rel and not Path(rel).is_absolute() and ".." not in Path(rel).parts,"unsafe member")
    target=dest/rel;target.parent.mkdir(parents=True,exist_ok=True)
    raw=z.read("payload/"+rel)
    guard(hashlib.sha256(raw).hexdigest()==meta["sha256"] and len(raw)==meta["size"],"digest mismatch")
    with target.open("xb") as f:f.write(raw)
   db=dest/"api.sqlite3"
   with sqlite3.connect(db) as c:
    if c.execute("SELECT 1 FROM sqlite_master WHERE name='b14_artifacts'").fetchone():
     for jobid,old,digest,slot in c.execute("SELECT job_id,path,sha256,worker_id FROM b14_artifacts").fetchall():
      target=dest/"restored-artifacts"/f"worker-{slot}"/Path(old).name
      guard(target.is_file() and sha(target)==digest,"restored PNG failed digest")
      c.execute("UPDATE b14_artifacts SET path=? WHERE job_id=?",(str(target),jobid))
      if c.execute("SELECT 1 FROM sqlite_master WHERE name='b112_artifact_history'").fetchone():
       c.execute("UPDATE b112_artifact_history SET path=? WHERE job_id=?",(str(target),jobid))
    c.commit()
   with sqlite3.connect(db) as c:
    guard(c.execute("PRAGMA integrity_check").fetchone()[0]=="ok","restored DB invalid")
    jobs=dict(c.execute("SELECT state,COUNT(*) FROM jobs GROUP BY state"))
    sessions=dict(c.execute("SELECT status,COUNT(*) FROM b112_sessions GROUP BY status")) if c.execute("SELECT 1 FROM sqlite_master WHERE name='b112_sessions'").fetchone() else {}
   # NO implicit reset of running, frozen mappings, sessions, or leases. An operator must reconcile.
   blocked=any(jobs.get(x,0) for x in ("running","uncertain","failed")) or any(sessions.get(x,0) for x in ("PREPARING","READY","DISPATCHING","BLOCKED"))
   gate={"status":"B115_RESTORE_QUARANTINED" if blocked else "B115_RESTORE_DATA_VERIFIED",
         "automatic_inference_resume":False,"artifacts_restored":len(list((dest/"restored-artifacts").rglob("*.png"))),"jobs":jobs,"sessions":sessions,"source_archive":str(archive)}
   (dest/"B115-RESTORE-GATE.json").write_text(json.dumps(gate,indent=2)+"\n")
   return gate
  except BaseException:
   (dest/"B115-INCOMPLETE-DO-NOT-RUN").write_text("Restore failed; quarantine this directory.\n")
   raise
def main():
 p=argparse.ArgumentParser();sub=p.add_subparsers(dest="command",required=True)
 a=sub.add_parser("checkpoint");a.add_argument("--source",required=True);a.add_argument("--out",required=True)
 a=sub.add_parser("restore");a.add_argument("--archive",required=True);a.add_argument("--dest",required=True)
 x=p.parse_args()
 obj=checkpoint(x.source,x.out) if x.command=="checkpoint" else restore(x.archive,x.dest)
 print(json.dumps(obj,sort_keys=True))
if __name__=="__main__":
 try:main()
 except Exception as e:
  print("B115_BLOCKED "+type(e).__name__+": "+str(e),flush=True)
  raise SystemExit(2)

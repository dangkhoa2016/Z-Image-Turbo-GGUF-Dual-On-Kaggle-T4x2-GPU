from pathlib import Path
p=(Path(__file__).resolve().parents[1]/"production-system"/"portable_recovery.py")
s=p.read_text()
s=s.replace('  manifest={"schema":"zimage-b115-checkpoint-v1"', """  with sqlite3.connect(snap) as c:
   if c.execute("SELECT 1 FROM sqlite_master WHERE name='b14_artifacts'").fetchone():
    receipts=c.execute("SELECT path,sha256,worker_id FROM b14_artifacts").fetchall()
    for old,digest,slot in receipts:
     pic=Path(old)
     guard(slot in (0,1) and pic.is_file() and not pic.is_symlink() and sha(pic)==digest,"PNG receipt verification failure")
     guard(pic.parent==(Path(__file__).resolve().parents[1]/"output")/f"worker-{slot}","PNG outside output root")
     files[f"restored-artifacts/worker-{slot}/{pic.name}"]=pic
  manifest={"schema":"zimage-b115-checkpoint-v1" """)
s=s.replace('   db=dest/"api.sqlite3"\n   with sqlite3.connect(db) as c:', """   db=dest/"api.sqlite3"
   with sqlite3.connect(db) as c:
    if c.execute("SELECT 1 FROM sqlite_master WHERE name='b14_artifacts'").fetchone():
     for jobid,old,digest,slot in c.execute("SELECT job_id,path,sha256,worker_id FROM b14_artifacts").fetchall():
      target=dest/"restored-artifacts"/f"worker-{slot}"/Path(old).name
      guard(target.is_file() and sha(target)==digest,"restored PNG failed digest")
      c.execute("UPDATE b14_artifacts SET path=? WHERE job_id=?",(str(target),jobid))
      if c.execute("SELECT 1 FROM sqlite_master WHERE name='b112_artifact_history'").fetchone():
       c.execute("UPDATE b112_artifact_history SET path=? WHERE job_id=?",(str(target),jobid))
    c.commit()
   with sqlite3.connect(db) as c:""")
s=s.replace('"automatic_inference_resume":False,"jobs":jobs', '"automatic_inference_resume":False,"artifacts_restored":len(list((dest/"restored-artifacts").rglob("*.png"))),"jobs":jobs')
p.write_text(s)
print("RECOVERY_PATCH_APPLIED")

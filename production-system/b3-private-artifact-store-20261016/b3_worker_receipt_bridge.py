"""B3 read-only bridge from B1.14/B1.13 ARCHIVED GPU receipts to private Store.

No inference; never changes worker, legacy SQLite, session status, or artifact receipts.
Requires explicit b3_job_owner mapping recorded at authenticated job admission.
"""
import argparse,hashlib,json,os,sqlite3,stat,sys,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from store import Store

def safe_read_worker_file(filename,slot,output_root):
    root=Path(output_root)
    if not root.is_dir() or root.is_symlink():raise RuntimeError("unsafe output root")
    parent=root/("worker-"+str(slot))
    if parent.is_symlink() or not parent.is_dir():raise RuntimeError("unsafe worker directory")
    p=Path(filename)
    if not p.is_absolute() or p.parent!=parent or p.suffix!=".png" or p.is_symlink():
        raise RuntimeError("out-of-root or unsafe receipt path")
    fd=os.open(p,os.O_RDONLY|getattr(os,"O_NOFOLLOW",0))
    with os.fdopen(fd,"rb") as f:
        if not stat.S_ISREG(os.fstat(f.fileno()).st_mode):raise RuntimeError("nonregular PNG")
        data=f.read(16*1024*1024+1)
    if len(data)>16*1024*1024:raise RuntimeError("oversize PNG")
    Store._validate_png(data)
    return data

def publish_archived(db_path,store_root,output_root,session_id):
    """Fail closed before publication unless every frozen job and receipt is consistent."""
    try:
        if str(uuid.UUID(session_id))==session_id:raise RuntimeError("invalid B1.13 session ID")
    except (ValueError,TypeError,AttributeError):pass
    if not session_id.startswith("b112-") or len(session_id)>80:
        raise RuntimeError("invalid session ID")
    db=Path(db_path)
    if not db.is_file():raise RuntimeError("missing DB")
    with sqlite3.connect("file:"+str(db)+"?mode=ro",uri=True) as c:
        c.row_factory=sqlite3.Row
        if c.execute("pragma integrity_check").fetchone()[0]!="ok":raise RuntimeError("DB integrity")
        sess=c.execute("select status from b112_sessions where session_id=?",(session_id,)).fetchone()
        if not sess or sess["status"]!="ARCHIVED":raise RuntimeError("session must be ARCHIVED")
        rows=c.execute("""SELECT j.id AS job, j.state AS state,j.worker_id AS worker,
           j.output_sha256 AS digest,o.owner_id AS owner,
           a.worker_id AS artifact_worker,a.path AS artifact_path,a.sha256 AS artifact_sha,
           h.path AS history_path,h.sha256 AS history_sha,h.worker_id AS history_worker
          FROM b113_session_jobs sj
          JOIN jobs j ON j.id=sj.job_id
          LEFT JOIN b3_job_owner o ON o.job_id=j.id
          LEFT JOIN b14_artifacts a ON a.job_id=j.id
          LEFT JOIN b112_artifact_history h ON h.job_id=j.id AND h.session_id=sj.session_id
          WHERE sj.session_id=? ORDER BY j.id""",(session_id,)).fetchall()
        if not rows:raise RuntimeError("no frozen jobs")
        data=[]
        for r in rows:
            if r["state"]=="cancelled":continue
            if r["state"]!="completed" or r["owner"] is None or r["worker"] not in (0,1):
                raise RuntimeError("nonterminal, unowned or invalid worker")
            if not (r["worker"]==r["artifact_worker"]==r["history_worker"] and
                    r["digest"]==r["artifact_sha"]==r["history_sha"] and
                    r["artifact_path"]==r["history_path"] and
                    isinstance(r["digest"],str) and len(r["digest"])==64):
                raise RuntimeError("receipt mismatch")
            raw=safe_read_worker_file(r["artifact_path"],r["worker"],output_root)
            if hashlib.sha256(raw).hexdigest()!=r["digest"]:raise RuntimeError("PNG SHA mismatch")
            data.append((r["job"],r["owner"],raw,r["digest"]))
    # Preflight complete. Partial publication is safe on retry because Store.put is idempotent.
    store=Store(store_root)
    published=[]
    for job,owner,raw,digest in data:
        receipt=store.put(job,owner,raw)
        if receipt["sha256"]!=digest:raise RuntimeError("store digest mismatch")
        published.append({"job_id":job,"sha256":digest,"idempotent":receipt["idempotent"]})
    return {"status":"B3_ARCHIVED_GPU_RECEIPT_PUBLICATION_PASS","session_id":session_id,
            "published":len(published),"results":published,"gpu_inference":"NOT_RUN",
            "legacy_database_mutation":False}

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--db",required=True);p.add_argument("--store",required=True)
    p.add_argument("--output-root",required=True);p.add_argument("--session-id",required=True)
    a=p.parse_args()
    print(json.dumps(publish_archived(a.db,a.store,a.output_root,a.session_id),sort_keys=True))

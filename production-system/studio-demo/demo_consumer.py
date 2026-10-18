"""B3 demo queue consumer: preserves B1.13/B1.14 lifecycle and publishes archived GPU PNGs.
CPU-only --reconcile-only is the DEFAULT, no GPU models/workers started.
"""
import argparse,fcntl,json,os,sqlite3,sys,time,traceback
from pathlib import Path
HERE=Path(__file__).resolve().parent
SRC=HERE.parent
B3=SRC/"private-artifact-store"
sys.path.insert(0,str(SRC))
sys.path.insert(0,str(B3))
from worker_receipt_bridge import publish_archived

from lifecycle_schema import ensure_session_schema

def publish_previous(db_path,private_root,output_root):
    ensure_session_schema(db_path)
    published=[];skipped=[]
    with sqlite3.connect("file:"+str(db_path)+"?mode=ro",uri=True) as c:
        rows=c.execute("SELECT session_id FROM b112_sessions WHERE status='ARCHIVED' ORDER BY created_at").fetchall()
        for (sid,) in rows:
            owners=c.execute("""SELECT COUNT(*),COUNT(o.owner_id) FROM b113_session_jobs sj
             LEFT JOIN b3_job_owner o ON o.job_id=sj.job_id WHERE sj.session_id=?""",(sid,)).fetchone()
            if owners[1]==0:
                skipped.append(sid)
                continue # Old legacy sessions predate tenant binding; do not invent owners.
            if owners[0]!=owners[1]:
                raise RuntimeError("partly owned archived session requires operator attention: "+sid)
            result=publish_archived(db_path,private_root,output_root,sid)
            published.append(result)
    return {"status":"B3_ARCHIVED_SESSIONS_RECONCILED","published_sessions":published,
            "unowned_legacy_sessions_skipped":skipped,"automatic_replay":False}

def run_gpu_consumer(run_root,private_root,poll,batch_wait,once):
    # GPU-specific imports and dispatch happen ONLY with --enable-gpu explicitly provided.
    import importlib.metadata as md
    from b113_shared_lifecycle import SharedLifecycle
    from b114_shared_gpu_supervisor import run as gpu_dispatch
    from http_dispatcher import connect
    ROOT=Path("/kaggle/working/zimage-dual")
    db=run_root/"api.sqlite3"
    support=json.loads((ROOT/"manifests/support.json").read_text())
    identity={"support_manifest_sha256":support["manifest_sha256"],
              "diffusers_version":md.version("diffusers"),"max_sequence_length":512,
              "text_encoder_dtype":"bfloat16"}
    life=SharedLifecycle(api_db=db,sessions_root=run_root/"sessions",artifact_root=ROOT/"output",
                         identity=identity,mode="gpu0",max_prompts=2,max_jobs=4)
    def dispatch(sid,prepared):
        return gpu_dispatch(sid,db,run_root/"sessions",ROOT/"output",300,1800,True)
    print("B3_DEMO_CONSUMER_READY",flush=True)
    while True:
        publish_previous(db,private_root,ROOT/"output")
        with connect() as c:
            count,oldest=c.execute("SELECT COUNT(*),MIN(created_at) FROM jobs WHERE state='queued'").fetchone()
        if count:
            age=max(0,time.time()-oldest)
            if count>1 or age>=batch_wait or once:
                result=life.run_one(dispatch)
                sid=result["archive"]["session_id"]
                private_result=publish_archived(db,private_root,ROOT/"output",sid)
                print("B3_GPU_AND_PRIVATE_PUBLICATION",json.dumps({"session_id":sid,"private_receipts":private_result["published"]}),flush=True)
        if once:break
        time.sleep(poll)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--run-root",required=True)
    p.add_argument("--private-root",required=True)
    p.add_argument("--reconcile-only",action="store_true")
    p.add_argument("--enable-gpu",action="store_true")
    p.add_argument("--poll",type=float,default=2)
    p.add_argument("--batch-wait",type=float,default=25)
    p.add_argument("--once",action="store_true")
    a=p.parse_args()
    if a.enable_gpu and a.reconcile_only:raise RuntimeError("conflicting modes")
    if a.poll<1 or a.poll>30 or a.batch_wait<0 or a.batch_wait>60:raise RuntimeError("invalid timing")
    run_root=Path(a.run_root).resolve(strict=True)
    if not run_root.is_relative_to(SRC) or not (run_root/"api.sqlite3").is_file():
        raise RuntimeError("invalid project-local database")
    private=Path(a.private_root).resolve()
    if not private.is_relative_to(SRC):raise RuntimeError("private root must remain in project")
    if os.environ.get("ZIMAGE_B1_DB")!=str(run_root/"api.sqlite3"):
        raise RuntimeError("ZIMAGE_B1_DB mismatch")
    lock=run_root/"b3-demo-consumer.lock"
    with lock.open("a+") as fd:
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if not a.enable_gpu:
            print(json.dumps(publish_previous(run_root/"api.sqlite3",private,Path("/kaggle/working/zimage-dual/output"))))
            return
        run_gpu_consumer(run_root,private,a.poll,a.batch_wait,a.once)

if __name__=="__main__":
    main()

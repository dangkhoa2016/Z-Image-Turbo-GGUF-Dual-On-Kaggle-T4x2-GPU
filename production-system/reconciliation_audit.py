#!/usr/bin/env python3
"""Read-only recovery reconciliation audit. Never changes/requeues jobs."""
import argparse,json,sqlite3,hashlib
from pathlib import Path
ROOT=(Path(__file__).resolve().parents[1]/"production-system")
def audit(folder):
 folder=Path(folder).resolve(strict=True)
 if not folder.is_relative_to(ROOT):raise RuntimeError("outside authorized restore root")
 db=folder/"api.sqlite3";gate=folder/"restore-gate.json"
 if not gate.exists():gate=folder/"B116-RESTORE-GATE.json"  # read existing pre-release checkpoints
 if not db.is_file() or not gate.is_file():raise RuntimeError("missing restored SQLite database or recovery manifest")
 state=json.loads(gate.read_text())
 with sqlite3.connect(f"file:{db}?mode=ro",uri=True) as c:
  c.row_factory=sqlite3.Row
  jobs=[dict(x) for x in c.execute("SELECT id,state,attempt,worker_id,output_sha256,last_error FROM jobs ORDER BY id")]
  sessions=[dict(x) for x in c.execute("SELECT session_id,status FROM b112_sessions ORDER BY created_at")]
  records=[]
  for j in jobs:
   receipt=c.execute("SELECT path,sha256 FROM b14_artifacts WHERE job_id=?",(j["id"],)).fetchone()
   artifact_ok=False
   if receipt:
    p=Path(receipt["path"])
    artifact_ok=p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==receipt["sha256"]==j["output_sha256"]
   records.append({"id":j["id"],"state":j["state"],"attempt":j["attempt"],"receipt_integrity":artifact_ok,
                   "decision":"KEEP_COMPLETED" if j["state"]=="completed" and artifact_ok else "MANUAL_RECONCILIATION_REQUIRED"})
 quarantined=state["status"] in ("RESTORE_VERIFIED_QUARANTINED","B116_RESTORE_VERIFIED_QUARANTINED")
 return {"status":"RESTORE_AUDIT_PASS","quarantined":quarantined,"sessions":sessions,
  "jobs":records,"automatic_requeue":False,"operator_action":"Inspect receipts, worker logs, lease history; explicitly approve a new isolated job only after reconciliation"}
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--restore",required=True);a=p.parse_args()
 try:print(json.dumps(audit(a.restore),indent=2))
 except Exception as e:print("RECOVERY_AUDIT_BLOCKED",str(e));raise SystemExit(2)

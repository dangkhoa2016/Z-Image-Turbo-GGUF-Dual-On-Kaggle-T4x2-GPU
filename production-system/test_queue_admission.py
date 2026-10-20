"""CPU tests for atomic queue admission and session snapshots; no GPU execution."""
import os,secrets,tempfile,sqlite3
from pathlib import Path
from fastapi.testclient import TestClient
with tempfile.TemporaryDirectory(prefix="b16-test-b113-") as td:
 os.environ["ZIMAGE_B1_DB"]=str(Path(td)/"jobs.sqlite3")
 os.environ["ZIMAGE_B1_API_KEY"]=secrets.token_urlsafe(36)
 import queue_admission as a
 from scoped_dispatcher import ScopedDispatcher
 client=TestClient(a.app);h={"Authorization":"Bearer "+os.environ["ZIMAGE_B1_API_KEY"]}
 def submit(p,seed,key=None):
  headers=dict(h)
  if key:headers["Idempotency-Key"]=key
  return client.post("/v1/jobs",headers=headers,json={"prompt":p,"seed":seed})
 assert submit("Moonlit mountain forest",11,"idempotent-111").status_code==201
 assert submit("Moonlit mountain forest",11,"idempotent-111").status_code==201
 assert submit("Another mountain forest",12).status_code==201
 with a.connection() as c:
  c.execute("BEGIN IMMEDIATE")
  sid="b112-abc123"
  ids=[r[0] for r in c.execute("SELECT id FROM jobs WHERE prompt=?",("Moonlit mountain forest",))]
  c.execute("INSERT INTO b113_active_prompts VALUES(?,?)",("Moonlit mountain forest",sid))
  c.executemany("INSERT INTO b113_session_jobs VALUES(?,?)",[(sid,x) for x in ids])
  c.execute("COMMIT")
 assert submit("Moonlit mountain forest",13).status_code==423
 assert submit("New unrelated prompt",14).status_code==201
 with a.connection() as c:
  x=c.execute("SELECT COUNT(*) FROM b113_session_jobs WHERE session_id=?",(sid,)).fetchone()[0]
  assert x==1
  assert c.execute("SELECT COUNT(*) FROM jobs WHERE state='queued'").fetchone()[0]==3
 assert submit("Moonlit mountain forest",99,"idempotent-111").status_code==409
 print("QUEUE_ADMISSION_CPU_PASS same_prompt_blocked=423 unrelated_prompt_queued=201 idempotency_preserved=PASS snapshot_job_count=1")

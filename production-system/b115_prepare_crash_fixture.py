from pathlib import Path
import sqlite3,shutil
root=Path("/kaggle/working/zimage-dual/production-system")
src=root/"b115-restore-with-png-v2-20261015"
fixture=root/"b115-synthetic-crash-20261015"
assert not fixture.exists()
shutil.copytree(src,fixture)
db=fixture/"api.sqlite3"
with sqlite3.connect(db) as c:
 c.execute("UPDATE jobs SET state='running',lease_owner='synthetic-crashed-worker',lease_deadline=1 WHERE id=(SELECT id FROM jobs LIMIT 1)")
 c.execute("UPDATE b112_sessions SET status='DISPATCHING' WHERE status='ARCHIVED'")
 c.commit()
print("SYNTHETIC_CRASH_FIXTURE_READY")

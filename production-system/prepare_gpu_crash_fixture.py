from pathlib import Path
import sqlite3,shutil
root=(Path(__file__).resolve().parents[1]/"production-system")
src=root/"b114-real-gpu-acceptance-20261015"
fixture=root/"b115-synthetic-crash-source-20261015"
assert not fixture.exists()
shutil.copytree(src,fixture)
with sqlite3.connect(fixture/"api.sqlite3") as c:
 c.execute("UPDATE jobs SET state='running',lease_owner='synthetic-crashed-worker',lease_deadline=1 WHERE id=(SELECT id FROM jobs LIMIT 1)")
 c.execute("UPDATE b112_sessions SET status='DISPATCHING' WHERE status='ARCHIVED'")
 c.commit()
print("SYNTHETIC_CRASH_SOURCE_VERIFIED_READY")

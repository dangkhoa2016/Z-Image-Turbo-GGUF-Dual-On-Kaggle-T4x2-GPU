"""Verify first-start schema creation and fail-closed lifecycle behavior."""
import sqlite3
import tempfile
from pathlib import Path
from lifecycle_schema import ensure_session_schema

with tempfile.TemporaryDirectory() as tmp:
    db = Path(tmp) / "studio.sqlite3"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE jobs(id TEXT PRIMARY KEY,state TEXT NOT NULL)")
        conn.execute("INSERT INTO jobs VALUES('existing-job','queued')")
    ensure_session_schema(db)
    with sqlite3.connect(db) as conn:
        tables = {x[0] for x in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {'b112_sessions','b112_mapping_history','b112_artifact_history',
                'b113_active_prompts','b113_session_jobs'} <= tables
        conn.execute("INSERT INTO b112_sessions VALUES('active','BLOCKED',0,0,NULL,NULL,'gpu0')")
    ensure_session_schema(db)
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT status FROM b112_sessions WHERE session_id='active'").fetchone()[0] == 'BLOCKED'
        assert conn.execute("SELECT state FROM jobs WHERE id='existing-job'").fetchone()[0] == 'queued'
    missing = Path(tmp) / "missing.sqlite3"
    try: ensure_session_schema(missing)
    except RuntimeError: pass
    else: raise AssertionError("Missing DB was silently created")
    assert not missing.exists()
print("STUDIO_LIFECYCLE_FIRST_START_SCHEMA=PASS")

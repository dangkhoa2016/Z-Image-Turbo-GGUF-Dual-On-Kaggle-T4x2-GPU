"""Idempotent shared SQLite session schema for Studio GPU consumers."""
import sqlite3
from pathlib import Path

TABLES = {
    "b112_sessions": (
        "session_id TEXT PRIMARY KEY,status TEXT NOT NULL,created_at REAL NOT NULL,"
        "updated_at REAL NOT NULL,manifest TEXT,manifest_sha256 TEXT,mode TEXT NOT NULL"),
    "b112_mapping_history": (
        "session_id TEXT NOT NULL,prompt TEXT NOT NULL,prompt_id TEXT NOT NULL,"
        "PRIMARY KEY(session_id,prompt)"),
    "b112_artifact_history": (
        "session_id TEXT NOT NULL,job_id TEXT NOT NULL,worker_id INTEGER NOT NULL,"
        "sha256 TEXT NOT NULL,path TEXT NOT NULL,PRIMARY KEY(job_id)"),
    "b113_active_prompts": "prompt TEXT PRIMARY KEY,session_id TEXT NOT NULL",
    "b113_session_jobs": (
        "session_id TEXT NOT NULL,job_id TEXT NOT NULL UNIQUE,"
        "PRIMARY KEY(session_id,job_id)"),
}

def ensure_session_schema(db_path):
    """Initialize absent session tables without replacing existing data."""
    db = Path(db_path)
    if not db.is_file():
        raise RuntimeError("Existing Studio database required")
    with sqlite3.connect(f"file:{db}?mode=rw", uri=True, timeout=15) as conn:
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("Studio database integrity check failed")
        existing = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        if "jobs" not in existing:
            raise RuntimeError("Studio jobs schema missing")
        for name, definition in TABLES.items():
            conn.execute(f"CREATE TABLE IF NOT EXISTS {name} ({definition})")
        required = {
            "b112_sessions": {"session_id", "status", "created_at", "updated_at", "manifest", "manifest_sha256", "mode"},
            "b112_mapping_history": {"session_id", "prompt", "prompt_id"},
            "b112_artifact_history": {"session_id", "job_id", "worker_id", "sha256", "path"},
            "b113_active_prompts": {"prompt", "session_id"},
            "b113_session_jobs": {"session_id", "job_id"},
        }
        for name, expected in required.items():
            columns = {row[1] for row in conn.execute(f"PRAGMA table_info({name})")}
            if not expected <= columns:
                raise RuntimeError(f"Unexpected Studio lifecycle schema: {name}")

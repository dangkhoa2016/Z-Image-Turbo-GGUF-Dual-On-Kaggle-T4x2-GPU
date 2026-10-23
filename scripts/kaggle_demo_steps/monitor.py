if P23_ENABLE_OPTIONAL_WEB_APPS:
    # Studio live activity monitor: read-only, no GPU jobs are submitted.
    # Runs until the operator interrupts the cell; never submits Studio jobs.
    import os
    import re
    import sqlite3
    import subprocess
    import time
    from datetime import datetime
    from pathlib import Path

    STUDIO_POLL_INTERVAL_SECONDS = 10
    STUDIO_MONITOR_MAX_MINUTES = None  # continuous; stop with Interrupt Cell
    STUDIO_GPU_METRIC_EVERY_POLLS = 3

    assert 2 <= STUDIO_POLL_INTERVAL_SECONDS <= 120
    assert STUDIO_MONITOR_MAX_MINUTES is None or STUDIO_MONITOR_MAX_MINUTES > 0
    assert "RUN" in globals(), "Start Studio and its GPU consumer before monitoring."
    studio_db = Path(RUN) / "api.sqlite3"
    consumer_log = Path(RUN) / "persistent-gpu-consumer.log"
    consumer_pid_file = Path(RUN) / "persistent-gpu-consumer.pid"
    assert studio_db.is_file(), "Studio database not found. Run the Studio setup cells first."

    def _studio_consumer_status():
        try:
            pid = int(consumer_pid_file.read_text().strip())
            proc = Path("/proc") / str(pid)
            stat_fields = (proc / "stat").read_text().rsplit(")", 1)[1].split()
            if not stat_fields or stat_fields[0] in ("Z", "X"):
                return "STOPPED", pid
            args = (proc / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
            if "demo_consumer.py" not in args or "--enable-gpu" not in args:
                return "UNVERIFIED_PID", pid
            environment = (proc / "environ").read_bytes().split(b"\0")
            if ("ZIMAGE_B1_DB=" + str(studio_db)).encode() not in environment:
                return "DB_MISMATCH", pid
            return "RUNNING", pid
        except (OSError, ValueError, IndexError):
            return "STOPPED", None

    def _studio_db_snapshot():
        con = sqlite3.connect("file:" + str(studio_db) + "?mode=ro", uri=True, timeout=5)
        con.row_factory = sqlite3.Row
        try:
            states = {r["state"]: r["n"] for r in
                      con.execute("SELECT state, COUNT(*) AS n FROM jobs GROUP BY state")}
            recent = [dict(r) for r in con.execute(
                "SELECT id, state, worker_id, created_at, updated_at "
                "FROM jobs ORDER BY created_at DESC LIMIT 6")]
            sessions = [dict(r) for r in con.execute(
                "SELECT session_id, status FROM b112_sessions "
                "ORDER BY created_at DESC LIMIT 3")]
            return states, recent, sessions
        finally:
            con.close()

    def _studio_gpu_summary():
        p = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,utilization.gpu,memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=8, check=True,
        )
        parts = []
        for line in p.stdout.splitlines():
            fields = [x.strip() for x in line.split(",")]
            if len(fields) == 4:
                index, util, used, total = fields
                parts.append(f"GPU{index}={util}% VRAM={used}/{total}MiB")
        return " | ".join(parts) if parts else "GPU_METRICS_UNAVAILABLE"

    def _allowed_studio_log(line):
        # Do not expose credentials, bearer tokens or sensitive request headers.
        lowered = line.lower()
        if any(s in lowered for s in ("password", "api_token", "authorization:",
                                      "bearer ", "service_key", "studio_password")):
            return False
        return any(s in line for s in (
            "STUDIO_CONSUMER_READY", "GPU_", "ZIMAGE_WORKER_STAGE",
            "ENCODE_", "ZIMAGE_ENCODER_STAGE", "QWEN3_", "TOKENIZER_",
            "RuntimeError:", "TimeoutError:", "Traceback",
            "ERROR:", "Error:", "GPU_PRIVATE_PUBLICATION"))

    def _read_studio_log_increment(path, positions, max_bytes=32768):
        key = str(path)
        try:
            size = path.stat().st_size
            if key not in positions:
                # Begin monitoring only new log lines, not historical output.
                positions[key] = size
                return []
            if size < positions[key]:
                positions[key] = 0
            with path.open("rb") as f:
                f.seek(positions[key])
                data = f.read(max_bytes)
                positions[key] = f.tell()
            lines = data.decode("utf-8", errors="replace").replace("\r", "\n").splitlines()
            return [line.strip()[:700] for line in lines if _allowed_studio_log(line)][-12:]
        except OSError:
            return []

    def monitor_studio_live():
        start = time.monotonic()
        positions = {}
        previous_states = {}
        seen_stage = {}
        tick = 0
        deadline = None if STUDIO_MONITOR_MAX_MINUTES is None else (
            start + 60 * STUDIO_MONITOR_MAX_MINUTES)
        print("STUDIO_LIVE_MONITOR_STARTED "
              f"poll_interval={STUDIO_POLL_INTERVAL_SECONDS}s "
              "mode=READ_ONLY (no generation jobs submitted)", flush=True)
        print("Leave this cell running while using Studio. "
              "Interrupt this cell to stop logging without shutting down Studio.",
              flush=True)
        try:
            while deadline is None or time.monotonic() < deadline:
                timestamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
                consumer, pid = _studio_consumer_status()
                try:
                    states, recent, sessions = _studio_db_snapshot()
                except (sqlite3.Error, OSError) as error:
                    print(f"STUDIO_MONITOR_DB_READ_ERROR {type(error).__name__}: {error}",
                          flush=True)
                    states, recent, sessions = {}, [], []
                elapsed = round(time.monotonic() - start)
                counts = " ".join(f"{k}={v}" for k, v in sorted(states.items())) or "no_jobs"
                active = " ".join(f"{s['session_id'][-8:]}:{s['status']}"
                                  for s in sessions) or "no_sessions"
                print(f"STUDIO_LIVE_POLL at={timestamp} elapsed={elapsed}s "
                      f"consumer={consumer} pid={pid} jobs=[{counts}] "
                      f"sessions=[{active}]", flush=True)

                # Print changes in job state without inventing a completion percentage.
                for job in recent:
                    jid = job["id"]
                    identity = (job["state"], job["worker_id"])
                    if previous_states.get(jid) != identity:
                        print(f"STUDIO_JOB_UPDATE id={jid[:8]} "
                              f"state={job['state']} gpu={job['worker_id']}", flush=True)
                    previous_states[jid] = identity

                # Poll the persistent consumer and only the current session worker logs.
                log_paths = [consumer_log]
                for item in sessions:
                    session_id = item["session_id"]
                    if re.fullmatch(r"b112-[0-9a-f]{32}", session_id):
                        session_root = Path(RUN) / "sessions" / session_id
                        log_paths.append(session_root / "encoder-phase.log")
                        log_paths.extend(sorted(
                            (session_root / "gpu-supervisor-logs").glob("worker-*.log")))
                for path in log_paths:
                    for line in _read_studio_log_increment(path, positions):
                        print(f"STUDIO_LIVE_LOG source={path.name} {line}", flush=True)

                # Snapshot GPU load every 30s by default, without creating CUDA contexts.
                if tick % STUDIO_GPU_METRIC_EVERY_POLLS == 0:
                    try:
                        print("STUDIO_GPU_METRICS " + _studio_gpu_summary(), flush=True)
                    except (OSError, subprocess.SubprocessError) as error:
                        print(f"STUDIO_GPU_METRICS_UNAVAILABLE {type(error).__name__}",
                              flush=True)
                tick += 1
                if consumer != "RUNNING":
                    print("STUDIO_MONITOR_WARNING: consumer is not confirmed running. "
                          "Keeping read-only monitor active; no automatic restart/replay.",
                          flush=True)
                time.sleep(STUDIO_POLL_INTERVAL_SECONDS)
        except KeyboardInterrupt:
            print("STUDIO_LIVE_MONITOR_INTERRUPTED: monitoring stopped; "
                  "Studio services were not stopped.", flush=True)
        else:
            print("STUDIO_LIVE_MONITOR_DURATION_COMPLETE: "
                  "Studio services were not stopped.", flush=True)

    monitor_studio_live()
else:
    print("P23_OPTIONAL_UI_SKIPPED: Studio read-only monitor (enable P23_ENABLE_OPTIONAL_WEB_APPS to run)")

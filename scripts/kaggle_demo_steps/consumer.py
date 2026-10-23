if P23_ENABLE_OPTIONAL_WEB_APPS:
    import os, sys, sqlite3, time, subprocess
    from pathlib import Path

    assert "RUN" in globals() and "PROJECT" in globals(), "Run Steps 1–4 first"
    DB=RUN/"api.sqlite3"
    LOG=RUN/"persistent-gpu-consumer.log"
    PIDFILE=RUN/"persistent-gpu-consumer.pid"
    assert DB.is_file(), "STUDIO_DB_MISSING: Step 4 must initialize the database"

    def snapshot_queue():
        with sqlite3.connect("file:"+str(DB)+"?mode=ro",uri=True,timeout=5) as con:
            con.row_factory=sqlite3.Row
            states={s:n for s,n in con.execute("SELECT state,count(*) FROM jobs GROUP BY state")}
            sessions=[dict(x) for x in con.execute("SELECT session_id,status FROM b112_sessions WHERE status!='ARCHIVED'")]
            return states,sessions

    def consumer_health():
        if not PIDFILE.is_file():return False,"PID_FILE_MISSING"
        try:pid=int(PIDFILE.read_text().strip())
        except (ValueError,OSError):return False,"INVALID_PID"
        proc=Path("/proc")/str(pid)
        if not proc.is_dir():return False,"PROCESS_NOT_RUNNING"
        try:
            stat=(proc/"stat").read_text().split()
            if stat[2] in ("Z","X"):return False,"DEAD_OR_ZOMBIE_PROCESS"
            argv=(proc/"cmdline").read_bytes().replace(b"\x00",b" ").decode(errors="replace")
            if "demo_consumer.py" not in argv or "--enable-gpu" not in argv:
                return False,"PID_BELONGS_TO_UNRELATED_PROCESS"
            env=(proc/"environ").read_bytes().split(b"\x00")
            expected=("ZIMAGE_B1_DB="+str(DB)).encode()
            if expected not in env:return False,"CONSUMER_USES_DIFFERENT_DATABASE"
        except OSError as exc:
            return False,"CANNOT_INSPECT_CONSUMER:"+type(exc).__name__
        if not LOG.is_file() or "STUDIO_CONSUMER_READY" not in LOG.read_text(errors="replace"):
            return False,"CONSUMER_STARTUP_NOT_CONFIRMED"
        return True,"PID="+str(pid)+" DB_MATCH READY_MARKER"

    def show_consumer_tail(lines=75):
        print("=== GPU CONSUMER LOG ===")
        if LOG.is_file():print("\n".join(LOG.read_text(errors="replace").splitlines()[-lines:]))
        else:print("CONSUMER_LOG_MISSING")

    # The notebook's full-SHA256 GGUF cache must also be used by Studio workers.
    # Never treat a size-only direct fallback as equivalent to verified staging.
    if "gguf_choice" not in globals():
        # Studio-only browser troubleshooting after a separately verified GPU
        # receipt: do not render two expensive notebook PNGs again.
        sys.path.insert(0, str(PROJECT / "scripts"))
        from gguf_source_policy import select_gguf_source
        gguf_choice = select_gguf_source(
            json.loads((PROJECT / "manifests/model.json").read_text()),
            Path(os.environ["ZIMAGE_GGUF_STAGE_ROOT"]), "local")
        print("STUDIO_ONLY_MODEL_STAGE_VERIFIED: no notebook PNGs generated", flush=True)
    assert gguf_choice["effective_mode"] == "local" and gguf_choice["integrity"] == "sha256_verified_local"
    os.environ["ZIMAGE_GGUF_STAGED_PATH"] = gguf_choice["staged_override_path"]
    assert os.environ["ZIMAGE_GGUF_STAGED_PATH"].startswith(
        os.environ["ZIMAGE_GGUF_STAGE_ROOT"] + "/")
    assert os.environ["ZIMAGE_QWEN3_SOURCE_MODE"] == "local"
    print("STUDIO_MODEL_CACHE_POLICY", "source=verified-/tmp",
          "qwen3_root="+os.environ["ZIMAGE_QWEN3_STAGE_ROOT"],
          "gguf_root="+os.environ["ZIMAGE_GGUF_STAGE_ROOT"],flush=True)

    states,sessions=snapshot_queue()
    print("QUEUE_BEFORE_GPU_TEST",states,"UNRESOLVED_SESSIONS",sessions)
    assert not sessions,"PREEXISTING_UNRESOLVED_SESSION: inspect this session; no new GPU jobs allowed"
    assert not any(states.get(s,0) for s in ("queued","running","uncertain","failed")), (
        "PREEXISTING_UNRESOLVED_JOBS: inspect/cancel or archive them before running fresh demo")

    ok,reason=consumer_health()
    if not ok:
        if PIDFILE.exists():
            show_consumer_tail()
            raise RuntimeError("EXISTING_CONSUMER_NOT_READY:"+reason+". Do not launch a duplicate consumer")
        print("STARTING_GPU_CONSUMER (not yet claiming inference PASS)")
        log_start=LOG.stat().st_size if LOG.exists() else 0
        p=subprocess.run([sys.executable,str(PROJECT/"deployment/start_persistent_gpu_consumer.py")],
            capture_output=True,text=True,env=os.environ.copy(),timeout=150)
        if p.returncode:
            print(p.stdout[-1200:],p.stderr[-2000:]);show_consumer_tail()
            raise RuntimeError("GPU_CONSUMER_START_FAILED")
        print(p.stdout.strip())
        until=time.monotonic()+50
        while time.monotonic()<until:
            ok,reason=consumer_health()
            if ok:
                # Old READY markers in append-only logs must NOT validate a new process.
                with LOG.open("rb") as fp:
                    fp.seek(log_start)
                    new_log=fp.read().decode(errors="replace")
                if "STUDIO_CONSUMER_READY" in new_log:break
                ok=False;reason="NEW_PROCESS_READY_MARKER_NOT_YET_OBSERVED"
            if reason in ("PROCESS_NOT_RUNNING","DEAD_OR_ZOMBIE_PROCESS","PID_BELONGS_TO_UNRELATED_PROCESS"):
                break
            time.sleep(1)
        if not ok:
            show_consumer_tail()
            raise RuntimeError("GPU_CONSUMER_STARTUP_GATE_FAILED: "+reason)

    print("IMAGE_GENERATION_COORDINATOR_ONLINE",reason)
    print("MODEL_WORKERS_START_WITH_LIVE_JOBS: Submit a Studio prompt, then observe the final Live Monitor cell")
else:
    print("P23_OPTIONAL_UI_SKIPPED: Studio GPU consumer (enable P23_ENABLE_OPTIONAL_WEB_APPS to run)")

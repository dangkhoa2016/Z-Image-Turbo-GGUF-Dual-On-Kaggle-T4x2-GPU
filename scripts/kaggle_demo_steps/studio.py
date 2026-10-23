# Studio and galleries are enabled via the source-setup flag (Step 01).
if P23_ENABLE_OPTIONAL_WEB_APPS:
    import secrets,json,time,urllib.request,shutil
    from pathlib import Path
    PROD=PROJECT/"production-system"
    RUN=PROD/"b3-studio-demo-live-20261016"
    cfgpath=RUN/"local-secrets.json"
    if REUSE_LIVE_STUDIO:
        assert RUN.is_dir() and cfgpath.is_file(), "Previously verified Studio runtime is missing"
        print("STUDIO_ALREADY_RUNNING: reusing verified API and gateway", flush=True)
    elif not RUN.exists():
        import socket
        occupied=[]
        for port in (18788,18789):
            with socket.socket() as sock:
                sock.settimeout(0.5)
                if sock.connect_ex(("127.0.0.1",port))==0:
                    occupied.append(port)
        if occupied:
            raise RuntimeError(
                "STUDIO_PORT_CONFLICT: "+str(occupied)+
                " already in use by an earlier run. Stop the old Studio processes "
                "or restart the Kaggle runtime before starting this checkout."
            )
        subprocess.run([sys.executable,str(PROD/"studio-demo/start_local_demo.py")],check=True,env=os.environ.copy())
    else:
        assert cfgpath.exists(),"Incomplete runtime: manual inspection required"
        subprocess.run([sys.executable,str(PROJECT/"deployment"/"resume_local_demo.py")],check=True,env=os.environ.copy())
    cfg=json.loads(cfgpath.read_text())
    assert all(cfg.get(key) for key in ("api_token","studio_password","service_key"))
    assert cfgpath.stat().st_mode & 0o077==0,"Unsafe secret permissions"
    for port,path in ((18788,"/health"),(18789,"/auth/session")):
        with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}",timeout=10) as res:
            assert res.status==200
    print("STUDIO_GATEWAY_READY: http://127.0.0.1:18789/studio/")
    print("Service keys are NOT printed")
else:
    print("P23_OPTIONAL_UI_SKIPPED: Studio setup (enable P23_ENABLE_OPTIONAL_WEB_APPS to run)")

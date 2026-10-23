if P23_ENABLE_OPTIONAL_WEB_APPS:
    import os, re, stat, subprocess, tempfile, time, urllib.request, hashlib
    from pathlib import Path

    # Known Linux amd64 binary for the Kaggle runtime, with an exact release digest.
    CLOUDFLARED_VERSION = "2026.10.2"
    CLOUDFLARED_SHA256 = "35fbdd2beb378436c7da377d7358cea8e33f9c94a6705d1d8036bf9b0d6d8005"
    CLOUDFLARED_URL = ("https://github.com/cloudflare/cloudflared/releases/download/"
                      + CLOUDFLARED_VERSION + "/cloudflared-linux-amd64")

    def verify_cloudflared_digest(path):
        h = hashlib.sha256()
        with open(path, "rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest() == CLOUDFLARED_SHA256
    cf = Path("/kaggle/working/cloudflared")

    def cloudflared_version(binary):
        try:
            proc = subprocess.run(
                [str(binary), "--version"], capture_output=True, text=True,
                check=True, timeout=15
            )
            return proc.stdout.strip() or proc.stderr.strip()
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return None

    def ensure_cloudflared():
        if cf.exists() and not cf.is_file():
            raise RuntimeError("Cloudflared path exists but is not a regular file: " + str(cf))
        if cf.is_file():
            # Every execution needs this check, not only the first download.
            cf.chmod(cf.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            version = cloudflared_version(cf) if verify_cloudflared_digest(cf) else None
            if version:
                print("CLOUDFLARED_READY", version, flush=True)
                return cf
            print("CLOUDFLARED_REINSTALL: existing executable failed version check", flush=True)

        fd, temporary = tempfile.mkstemp(prefix=".cloudflared-", dir=str(cf.parent))
        os.close(fd)
        try:
            urllib.request.urlretrieve(CLOUDFLARED_URL, temporary)
            if not verify_cloudflared_digest(temporary):
                raise RuntimeError('CLOUDFLARED_SHA256_MISMATCH')
            os.chmod(temporary, 0o755)
            version = cloudflared_version(Path(temporary))
            if not version:
                raise RuntimeError(
                    "Downloaded cloudflared cannot execute. Check Kaggle runtime "
                    "architecture, file permissions and executable filesystem."
                )
            os.replace(temporary, cf)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        print("CLOUDFLARED_READY", version, flush=True)
        return cf

    cf = ensure_cloudflared()
    def quick_tunnel(name,port):
        logfile=Path(f"/kaggle/working/{name}-cloudflared.log")
        logfile.write_text("")  # Discard stale Quick Tunnel URLs from earlier notebook runs.
        proc=subprocess.Popen([str(cf),"tunnel","--no-autoupdate","--url",f"http://127.0.0.1:{port}"],stdout=logfile.open("ab"),stderr=subprocess.STDOUT,start_new_session=True)
        print("TUNNEL_PID",proc.pid)
        for attempt in range(50):
            text=logfile.read_text(errors="replace")
            urls=re.findall(r"https://[a-z0-9-]+\.trycloudflare\.com",text)
            if urls and proc.poll() is None:return urls[-1]
            if proc.poll() is not None:raise RuntimeError(f"{name} tunnel exited: {text[-1200:]}")
            time.sleep(1)
        raise RuntimeError(f"Tunnel URL not found in {logfile}")
    ready=globals().get("ready",{})
    if ready:
        gallery_urls["quality"]=quick_tunnel("gallery-quality",18881)
        gallery_urls["benchmark"]=quick_tunnel("gallery-benchmark",18882)
        print("QUALITY_GALLERY_HTTPS:",gallery_urls["quality"]+"/")
        print("BENCHMARK_GALLERY_HTTPS:",gallery_urls["benchmark"]+"/")
        for kind,port in (("quality",18881),("benchmark",18882)):
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/",timeout=10) as response:
                served=response.read().decode("utf-8")
            assert gallery_urls["quality"] in served and gallery_urls["benchmark"] in served
            print("GALLERY_CROSS_DOMAIN_NAV_LOCAL_PASS",kind)
        # Public HTTPS is observed from Kaggle but must be browser-verified.
        # A newly assigned Quick Tunnel can be unresolvable by Kaggle DNS while
        # its tunnel process and both local galleries remain healthy. Never
        # equate PENDING with PASS, and never swallow navigation-content errors.
        gallery_public_https_status = {}
        for kind,url in gallery_urls.items():
            last_network_error = None
            for retry in range(4):
                try:
                    with urllib.request.urlopen(url+"/",timeout=12) as res:
                        if res.status != 200:
                            raise urllib.error.URLError("NON_200_PUBLIC_HTTP_STATUS")
                        served=res.read().decode("utf-8")
                except (urllib.error.URLError, TimeoutError, OSError) as err:
                    last_network_error = err
                    if retry < 3:
                        time.sleep(2)
                    continue
                # A reachable but incorrect gallery is a product defect:
                # keep this fatal rather than misclassifying it as a DNS issue.
                assert gallery_urls["quality"] in served and gallery_urls["benchmark"] in served, (
                    "GALLERY_CROSS_DOMAIN_NAV_PUBLIC_CONTENT_INVALID: "+kind)
                last_network_error = None
                break
            if last_network_error is not None:
                gallery_public_https_status[kind] = "PENDING_BROWSER_VERIFICATION"
                print("GALLERY_PUBLIC_HTTPS_PROBE_PENDING",kind,
                      type(last_network_error).__name__,
                      "BROWSER_VERIFICATION_REQUIRED",flush=True)
            else:
                gallery_public_https_status[kind] = "VERIFIED_FROM_KAGGLE"
                print("GALLERY_CROSS_DOMAIN_NAV_HTTPS_PASS",kind,flush=True)
        if any(v != "VERIFIED_FROM_KAGGLE" for v in gallery_public_https_status.values()):
            print("PUBLIC_GALLERIES_E2E_STATUS PENDING_BROWSER_VERIFICATION; "
                  "continue to Studio setup; never claim Full E2E PASS yet",flush=True)
    else:
        print("GALLERY_TUNNELS_SKIPPED: gallery archive unavailable")

    # Present both public gallery destinations directly in the notebook.
    if ready:
        from IPython.display import display, Markdown
        display(Markdown(
            "### Gallery links / Liên kết gallery\n\n"
            "- **Quality · 48 images:** [Open gallery / Mở gallery](" + gallery_urls["quality"] + "/)\n"
            "- **Benchmark · 122 images:** [Open gallery / Mở gallery](" + gallery_urls["benchmark"] + "/)\n\n"
            "Both galleries have independent temporary HTTPS domains."))
else:
    print("P23_OPTIONAL_UI_SKIPPED: gallery HTTPS tunnels (enable P23_ENABLE_OPTIONAL_WEB_APPS to run)")

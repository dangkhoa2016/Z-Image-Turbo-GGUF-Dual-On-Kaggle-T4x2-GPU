from pathlib import Path
import importlib.util, os, socket, subprocess, sys, uuid, urllib.request

REPO_URL = "https://github.com/dangkhoa2016/Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU.git"
SOURCE_REF = os.environ.get("ZIMAGE_SOURCE_REF", "main")

# Final acceptance candidate: two real PNGs, followed by Studio and galleries.
P23_ENABLE_OPTIONAL_WEB_APPS = True
P27_VAE_STALL_PROFILING = False
P25_LOAD_ONLY = False
P24_GGUF_PREFETCH_ENABLED = False
P25_EXPERIMENT_LABEL = "sequential"
assert P25_LOAD_ONLY is False and P24_GGUF_PREFETCH_ENABLED is False
assert P23_ENABLE_OPTIONAL_WEB_APPS is True
assert isinstance(P27_VAE_STALL_PROFILING, bool)
# Preserve the GGUF local full-SHA256 staging path accepted for GPU inference.
os.environ["ZIMAGE_GGUF_SOURCE_MODE"] = "local"
# Model-weight copies are disposable; provenance/images/logs stay in /kaggle/working.
ZIMAGE_MODEL_STAGE_PARENT = Path("/tmp/zimage-t4x2-model-stage")
os.environ["ZIMAGE_QWEN3_SOURCE_MODE"] = "local"
os.environ["ZIMAGE_QWEN3_STAGE_ROOT"] = str(ZIMAGE_MODEL_STAGE_PARENT / "qwen3")
os.environ["ZIMAGE_GGUF_STAGE_ROOT"] = str(ZIMAGE_MODEL_STAGE_PARENT / "gguf")
P29_FRESH_RUN_ID = uuid.uuid4().hex[:12]
print("FINAL_RUNALL_POLICY","images=2","gguf=verified-local",
      "prefetch=off","studio_gallery=enabled","fresh_id="+P29_FRESH_RUN_ID,flush=True)
# Pin to a reviewed commit by setting ZIMAGE_SOURCE_SHA before this cell.
# Without a pin, resolve the published main branch HEAD and record the exact SHA.
SOURCE_SHA = os.environ.get("ZIMAGE_SOURCE_SHA", "").strip()
if SOURCE_SHA:
    import re
    if not re.fullmatch(r"[0-9a-fA-F]{40}", SOURCE_SHA):
        raise ValueError("ZIMAGE_SOURCE_SHA must be a full 40-character commit SHA")
    SOURCE_SHA = SOURCE_SHA.lower()
BASE_PROJECT = Path("/kaggle/working/zimage-source-demo")
PROJECT = BASE_PROJECT
REUSE_LIVE_STUDIO = False
STUDIO_PORTS = {"api": 18788, "gateway": 18789}

def git(project, *args):
    return subprocess.run(
        ["git", "-C", str(project), *args], check=True,
        capture_output=True, text=True, timeout=30
    ).stdout.strip()

def published_source_sha():
    """Resolve the final candidate source branch; do not trust a stale checkout."""
    if SOURCE_SHA:
        return SOURCE_SHA
    result = subprocess.run(
        ["git", "ls-remote", "--heads", REPO_URL, SOURCE_REF],
        capture_output=True, text=True, timeout=60
    )
    if result.returncode:
        raise RuntimeError("REMOTE_SOURCE_LOOKUP_FAILED: " + result.stderr[-500:])
    lines = result.stdout.strip().splitlines()
    import re
    if len(lines) != 1:
        raise RuntimeError("REMOTE_SOURCE_LOOKUP_AMBIGUOUS: " + repr(lines))
    fields = lines[0].split()
    if (len(fields) != 2 or fields[1] != "refs/heads/" + SOURCE_REF
            or not re.fullmatch(r"[0-9a-f]{40}", fields[0])):
        raise RuntimeError("REMOTE_SOURCE_REFERENCE_INVALID")
    return fields[0]

EXPECTED_SOURCE_SHA = published_source_sha()
print("EXPECTED_SOURCE_SHA", EXPECTED_SOURCE_SHA,
      "mode", "PINNED" if SOURCE_SHA else "REMOTE_BRANCH", flush=True)

def verified_checkout(project):
    """Verify public source identity without resetting, fetching or modifying it."""
    project = Path(project).resolve()
    if not (project / ".git").is_dir():
        return False, "Not a Git source checkout", None
    try:
        remote = git(project, "config", "--get", "remote.origin.url")
        normal = lambda x: x.removesuffix(".git").rstrip("/")
        if normal(remote) != normal(REPO_URL):
            return False, "Git remote does not match this project", None
        revision = git(project, "rev-parse", "HEAD")
        target = EXPECTED_SOURCE_SHA
        if revision != target:
            return False, "Source revision differs from published demo revision", None
        for args in (("diff", "--quiet"), ("diff", "--cached", "--quiet")):
            if subprocess.run(["git", "-C", str(project), *args],
                              capture_output=True, timeout=15).returncode != 0:
                return False, "Tracked source has local edits", None
        return True, "SOURCE_SHA=" + revision, {"sha": revision, "remote": remote}
    except (OSError, subprocess.SubprocessError) as exc:
        return False, "Cannot verify Git checkout: " + type(exc).__name__, None

def active_ports():
    found = []
    for port in STUDIO_PORTS.values():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                found.append(port)
    return found

def listener_pids(port):
    """Resolve socket ownership from procfs rather than potentially stale PID files."""
    inodes = set()
    for name in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            lines = Path(name).read_text().splitlines()[1:]
        except OSError:
            continue
        for line in lines:
            fields = line.split()
            if len(fields) > 9 and fields[3] == "0A":
                try:
                    if int(fields[1].rsplit(":", 1)[-1], 16) == port:
                        inodes.add("socket:[" + fields[9] + "]")
                except ValueError:
                    continue
    owners = set()
    if not inodes:
        return owners
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            for fd in (proc / "fd").iterdir():
                try:
                    target = os.readlink(fd)
                except OSError:
                    continue
                if target in inodes:
                    owners.add(int(proc.name))
                    break
        except OSError:
            continue
    return owners

def inspect_service(service, port):
    """Return observed running source path only when process identity is verified."""
    module = "demo_api:app" if service == "api" else "gateway:app"
    suffix = Path("production-system/studio-demo") if service == "api" else Path("product-studio")
    notes = []
    pids = sorted(listener_pids(port))
    if not pids:
        return None, service + ": no accessible listening-process owner on port " + str(port)
    for pid in pids:
        proc = Path("/proc") / str(pid)
        try:
            argv = [x.decode(errors="replace") for x in
                    (proc / "cmdline").read_bytes().split(b"\x00") if x]
            cwd = (proc / "cwd").resolve(strict=True)
            state = (proc / "stat").read_text().rsplit(")", 1)[1].strip().split()[0]
            environment = (proc / "environ").read_bytes().split(b"\x00")
        except OSError as exc:
            notes.append("PID " + str(pid) + ": cannot inspect procfs (" + type(exc).__name__ + ")")
            continue
        if state in ("Z", "X"):
            notes.append("PID " + str(pid) + ": not running")
            continue
        if not (module in argv and "uvicorn" in argv and "--port" in argv and
                argv.index("--port") + 1 < len(argv) and
                argv[argv.index("--port") + 1] == str(port)):
            notes.append("PID " + str(pid) + ": command/module is not the expected Studio service")
            continue
        if cwd.name != suffix.name or not str(cwd).endswith("/" + str(suffix)):
            notes.append("PID " + str(pid) + ": working directory is not Studio source: " + str(cwd))
            continue
        project = cwd.parents[1] if service == "api" else cwd.parent
        run_db = project / "production-system/b3-studio-demo-live-20261016/api.sqlite3"
        key = "ZIMAGE_B1_DB" if service == "api" else "ZIMAGE_STUDIO_DB"
        expected = (key + "=" + str(run_db)).encode()
        if expected not in environment:
            notes.append("PID " + str(pid) + ": " + key + " does not match its source checkout")
            continue
        if not run_db.is_file():
            notes.append("PID " + str(pid) + ": Studio database missing")
            continue
        return project.resolve(), "PID " + str(pid) + " port " + str(port)
    return None, "; ".join(notes)

def locate_live_studio():
    """Find the real source folder of an existing Studio, including clean-* clones."""
    api_project, api_info = inspect_service("api", STUDIO_PORTS["api"])
    gateway_project, gateway_info = inspect_service("gateway", STUDIO_PORTS["gateway"])
    if api_project is None or gateway_project is None:
        return None, "API: " + api_info + " | GATEWAY: " + gateway_info
    if api_project != gateway_project:
        return None, "API and gateway were started from DIFFERENT source checkouts: " + str(api_project) + " / " + str(gateway_project)
    run = api_project / "production-system/b3-studio-demo-live-20261016"
    if not (run / "local-secrets.json").is_file():
        return None, "Existing Studio login configuration not found"
    for name, endpoint in (("api", "/health"), ("gateway", "/auth/session")):
        try:
            with urllib.request.urlopen(
                "http://127.0.0.1:" + str(STUDIO_PORTS[name]) + endpoint,
                timeout=5
            ) as response:
                if response.status != 200:
                    return None, name + " HTTP returned " + str(response.status)
        except Exception as exc:
            return None, name + " HTTP check failed: " + type(exc).__name__
    return api_project, "API=" + api_info + " GATEWAY=" + gateway_info

ports_in_use = active_ports()
if ports_in_use:
    if set(ports_in_use) != set(STUDIO_PORTS.values()):
        raise RuntimeError(
            "PARTIAL_STUDIO_SESSION: only ports " + str(ports_in_use) + " are reachable. "
            "The existing services were not modified. For a clean start, use the "
            "Kaggle UI to restart the session after saving your files."
        )
    live_project, discovery = locate_live_studio()
    if live_project is None:
        raise RuntimeError(
            "STUDIO_REUSE_NOT_VERIFIED: " + discovery + ". "
            "No running process or local files were changed. Save the required "
            "Kaggle outputs before choosing Restart Session for a clean run."
        )
    ok, reason, info = verified_checkout(live_project)
    if not ok:
        raise RuntimeError(
            "STUDIO_SOURCE_NOT_VERIFIED: " + reason + "; running checkout: "
            + str(live_project) + ". Existing services were not changed."
        )
    PROJECT = live_project
    REUSE_LIVE_STUDIO = True
    print("EXISTING_STUDIO_REUSED", discovery, flush=True)
else:
    ok, reason, info = verified_checkout(BASE_PROJECT)
    if ok:
        PROJECT = BASE_PROJECT
        print("EXISTING_SOURCE_REUSED", reason, flush=True)
    else:
        # A stale source checkout may contain Studio state; never reset or delete it.
        candidate = Path("/kaggle/working") / (
            "zimage-source-demo-rev-" + EXPECTED_SOURCE_SHA[:12])
        if BASE_PROJECT.exists():
            print("PREVIOUS_SOURCE_PRESERVED", BASE_PROJECT, flush=True)
            PROJECT = candidate
        reused = False
        if PROJECT.exists():
            ok, reason, info = verified_checkout(PROJECT)
            if ok:
                reused = True
                print("EXISTING_REVISION_SOURCE_REUSED", PROJECT, flush=True)
            else:
                print("OTHER_SOURCE_PRESERVED", PROJECT, reason, flush=True)
                PROJECT = Path("/kaggle/working") / (
                    "zimage-source-demo-clean-" + uuid.uuid4().hex[:8])
        if not reused:
            assert not PROJECT.exists(), "Refusing to overwrite an existing path"
            subprocess.run(["git", "clone", "--branch", SOURCE_REF, REPO_URL, str(PROJECT)],
                           check=True, timeout=180)
            # Pin the revision obtained before clone. Fail if the remote moved
            # or the expected historical object cannot be fetched.
            subprocess.run(["git", "-C", str(PROJECT), "checkout", "--detach",
                            EXPECTED_SOURCE_SHA], check=True, timeout=30)
            ok, reason, info = verified_checkout(PROJECT)
            if not ok:
                raise RuntimeError("FRESH_SOURCE_VERIFICATION_FAILED: " + reason)
            print("SOURCE_CLONED_FRESH", PROJECT, flush=True)

assert (PROJECT / "product-studio/index.html").is_file(), "Application source incomplete"
assert info and info["sha"], "Source revision verification failed"
print("SOURCE_READY", PROJECT, flush=True)
print("SOURCE_SHA", info["sha"], flush=True)
print("STUDIO_SESSION_MODE", "REUSE_VERIFIED" if REUSE_LIVE_STUDIO else "FRESH_OR_RESUME", flush=True)

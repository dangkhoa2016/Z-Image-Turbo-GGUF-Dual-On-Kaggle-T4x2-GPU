"""CPU security regression tests: private artifact Store, receipt bridge, Studio gateway.

No GPU, no real network. Verifies tenant isolation, input validation, path/symlink
safety and gateway authentication/origin/allowlist behaviour. Dummy secrets only.
"""
import hashlib
import importlib.util
import os
import secrets
import sys
import tempfile
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
STORE_DIR = Path(__file__).resolve().parent / "b3-private-artifact-store-20261016"
sys.path.insert(0, str(STORE_DIR))
sys.path.insert(0, str(ROOT))

from store import Store  # noqa: E402
import b3_worker_receipt_bridge as bridge  # noqa: E402


def png_bytes(size=(1024, 1024), color=(120, 30, 200)):
    buf = BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()


# ---- Store: tenant isolation, validation, integrity -------------------------
with tempfile.TemporaryDirectory(prefix="b3-store-") as td:
    store = Store(Path(td) / "private")
    job = "60f6f0e2-0000-4000-8000-000000000001"
    other = "60f6f0e2-0000-4000-8000-000000000002"
    data = png_bytes()
    receipt = store.put(job, "tenant_a", data)
    assert receipt["sha256"] == hashlib.sha256(data).hexdigest()
    assert receipt["idempotent"] is False

    # Owner isolation: another tenant cannot read the artifact.
    try:
        store.get(job, "tenant_b")
        raise SystemExit("FAIL: cross-tenant read was not blocked")
    except LookupError:
        pass

    # Idempotent re-put by the same owner.
    assert store.put(job, "tenant_a", data)["idempotent"] is True

    # Conflicting put (different bytes for same job) is rejected.
    try:
        store.put(job, "tenant_a", png_bytes(color=(0, 0, 0)))
        raise SystemExit("FAIL: conflicting put was not blocked")
    except LookupError:
        pass

    # Input validation.
    for bad_job in ("not-a-uuid", str(Path(td)), "60f6f0e2-0000-4000-8000-00000000000"):
        try:
            store.put(bad_job, "tenant_a", data)
            raise SystemExit("FAIL: invalid job id accepted: %r" % bad_job)
        except ValueError:
            pass
    for bad_owner in ("../escape", "bad owner", "x" * 65, ""):
        try:
            store.put(other, bad_owner, data)
            raise SystemExit("FAIL: invalid owner accepted: %r" % bad_owner)
        except ValueError:
            pass
    try:
        store.put(other, "tenant_a", png_bytes(size=(64, 64)))
        raise SystemExit("FAIL: non-1024 PNG accepted")
    except ValueError:
        pass


# ---- Receipt bridge: path and symlink safety --------------------------------
with tempfile.TemporaryDirectory(prefix="b3-bridge-") as td:
    out = Path(td) / "out"
    (out / "worker-0").mkdir(parents=True)
    good = out / "worker-0" / "result.png"
    good.write_bytes(png_bytes())
    bridge.safe_read_worker_file(str(good), 0, str(out))  # valid

    outside = Path(td) / "outside.png"
    outside.write_bytes(png_bytes())
    for filename, slot in ((str(outside), 0), (str(good), 1)):
        try:
            bridge.safe_read_worker_file(filename, slot, str(out))
            raise SystemExit("FAIL: out-of-root receipt accepted")
        except RuntimeError:
            pass

    link = out / "worker-0" / "link.png"
    try:
        os.symlink(good, link)
        try:
            bridge.safe_read_worker_file(str(link), 0, str(out))
            raise SystemExit("FAIL: symlink receipt accepted")
        except RuntimeError:
            pass
    except OSError:
        pass  # filesystem forbids symlinks; skip


# ---- Gateway: authentication, origin, validation, allowlist -----------------
with tempfile.TemporaryDirectory(prefix="b3-gw-") as td:
    os.environ["VUE_STUDIO_PASSWORD"] = secrets.token_urlsafe(24)
    os.environ["STUDIO_INTERNAL_KEY"] = secrets.token_urlsafe(32)
    db = Path(td) / "studio.sqlite3"
    import sqlite3
    with sqlite3.connect(db) as c:
        c.execute("CREATE TABLE jobs(id TEXT PRIMARY KEY,prompt TEXT,state TEXT)")
    os.environ["ZIMAGE_STUDIO_DB"] = str(db)

    spec = importlib.util.spec_from_file_location(
        "studio_gateway", ROOT / "product-studio-vue-cdn-v3" / "gateway.py")
    gw = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gw)
    client = TestClient(gw.app)

    # Unauthenticated access is rejected.
    assert client.get("/v1/studio/jobs/" + "60f6f0e2-0000-4000-8000-000000000001" + "/prompt").status_code == 401
    assert client.get("/v1/jobs").status_code == 401

    # Login origin / content-type validation.
    assert client.post("/auth/login", json={"password": "x"}).status_code == 403  # no Origin
    assert client.post("/auth/login", data="raw",
                       headers={"Origin": "http://testserver"}).status_code == 415  # not JSON
    assert client.post("/auth/login", content=b"x" * 2048,
                       headers={"Origin": "http://testserver",
                                "Content-Type": "application/json"}).status_code == 413

    # Rate limiting after repeated wrong passwords from one client.
    ip = {"cf-connecting-ip": "203.0.113.9", "Origin": "http://testserver",
          "Content-Type": "application/json"}
    codes = [client.post("/auth/login", json={"password": "wrong"}, headers=ip).status_code
             for _ in range(9)]
    assert codes[0] == 401 and codes[-1] == 429, codes

    # A registered session authorises reads; allowlist rejects unknown paths.
    token = secrets.token_urlsafe(48)
    gw.SESSIONS[hashlib.sha256(token.encode()).hexdigest()] = __import__("time").time() + 3600
    cookie = {"Cookie": "zs_session=" + token}
    assert client.get("/auth/session", headers=cookie).json()["authenticated"] is True
    assert client.get("/v1/secret/../etc", headers=cookie).status_code == 404
    assert client.get("/v1/jobs/not-a-uuid", headers=cookie).status_code == 404

print("SECURITY_BOUNDARIES_PASS store_isolation bridge_path_safety gateway_auth_origin_ratelimit_allowlist")

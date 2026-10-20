"""CPU negative/supply-chain tests for the SHA256-locked vendor bootstrap.

No network. Verifies the bootstrap fails closed on tampered wheels, unsafe
archive paths, corrupt on-disk trees and missing offline wheels.
"""
import importlib.util
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("bootstrap_vendor", ROOT / "scripts" / "bootstrap_vendor.py")
bv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bv)


def expect(exc, fragment, fn):
    try:
        fn()
    except exc as err:
        assert fragment in str(err), "expected %r in %r" % (fragment, err)
        return
    raise SystemExit("FAIL: expected %s(%r)" % (exc.__name__, fragment))


with tempfile.TemporaryDirectory(prefix="vendor-neg-") as td:
    tmp = Path(td)

    # 1. Tampered wheel digest is rejected before any extraction.
    bad = tmp / "diffusers-0.41.0-py3-none-any.whl"
    with zipfile.ZipFile(bad, "w") as z:
        z.writestr("diffusers/__init__.py", "x")
    expect(RuntimeError, "WHEEL_SHA256_MISMATCH",
           lambda: bv.checked_wheel(bad, "diffusers", "0.41.0", "0" * 64))

    # 2. Archive path traversal is rejected by populate().
    evil = tmp / "evil.whl"
    with zipfile.ZipFile(evil, "w") as z:
        z.writestr("pkg-1.0/../evil.py", "boom")
    stage = tmp / "stage"
    stage.mkdir()
    expect(RuntimeError, "UNSAFE_WHEEL_PATH",
           lambda: bv.populate(stage, evil, "pkg", "1.0", "deadbeef", 0))

    # 3. A corrupt pre-existing vendor tree is rejected by verify().
    corrupt = tmp / "corrupt"
    (corrupt / "diffusers").mkdir(parents=True)
    (corrupt / "diffusers" / "__init__.py").write_text("x")
    expect(RuntimeError, "EXISTING_VENDOR_INVALID",
           lambda: bv.verify(corrupt, "diffusers", "0.41.0", "deadbeef", 0))

# 4. Offline bootstrap with no matching wheel fails closed (no network use).
import subprocess  # noqa: E402
import sys  # noqa: E402
empty = tempfile.mkdtemp(prefix="vendor-empty-")
proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "bootstrap_vendor.py"),
                       "--wheel-dir", empty], capture_output=True, text=True)
assert proc.returncode != 0 and "OFFLINE_WHEEL_MISSING" in (proc.stdout + proc.stderr), \
    "offline bootstrap did not fail closed: %r" % proc.stdout

print("VENDOR_BOOTSTRAP_NEGATIVE_PASS tamper unsafe_path corrupt_tree offline_fail_closed")

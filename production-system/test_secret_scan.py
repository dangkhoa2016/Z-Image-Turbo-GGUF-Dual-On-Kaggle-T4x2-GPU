"""CPU test for the secret scanner: detects planted secrets, clean text passes."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("scan_secrets", ROOT / "scripts" / "scan_secrets.py")
scanner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scanner)

planted = [
    "-----BEGIN RSA PRIVATE KEY-----",
    "aws id AKIAIOSFODNN7EXAMPLE end",
    "token ghp_" + "a" * 40,
    "url https://user:secretpw@example.invalid/path",
]
for line in planted:
    assert scanner.scan_text(line), "scanner missed planted secret: %r" % line

clean = "def add(a, b):\n    return a + b  # no secrets here\n"
assert scanner.scan_text(clean) == [], "scanner false positive on clean text"

# The scanner must skip its own fixture file (otherwise it flags fake secrets).
assert "production-system/test_secret_scan.py" in scanner.ALLOWLIST

print("SECRET_SCAN_TEST_PASS detects_planted clean_passes allowlist_ok")

#!/usr/bin/env python3
"""Scan Git-tracked text files for accidental secrets.

High-signal patterns only, to avoid false positives on documentation. Designed
to run in CI and locally; exits non-zero when a finding is present.
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

PATTERNS = [
    ("private_key_block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----")),
    ("aws_access_key_id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("url_with_credentials", re.compile(r"https?://[^\s/:@]+:[^\s/@]+@[^\s/]+")),
]

TEXT_SUFFIXES = {".py", ".md", ".txt", ".json", ".yml", ".yaml", ".ipynb",
                 ".cfg", ".ini", ".toml", ".sh", ".js", ".html", ".cff", ".vi"}

# Test fixtures that must contain fake secrets to prove detection works.
# These are the only files exempt from the scan.
ALLOWLIST = {"production-system/test_secret_scan.py"}


def scan_text(text):
    findings = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for name, pattern in PATTERNS:
            if pattern.search(line):
                findings.append((name, lineno))
    return findings


def tracked_files(repo):
    out = subprocess.check_output(["git", "-C", str(repo), "ls-files"], text=True)
    return [repo / line for line in out.splitlines() if line.strip()]


def scan_repo(repo):
    results = []
    for path in tracked_files(repo):
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        rel = str(path.relative_to(repo))
        if rel in ALLOWLIST:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for name, lineno in scan_text(text):
            results.append((rel, lineno, name))
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args(argv)
    repo = Path(args.repo).resolve()
    findings = scan_repo(repo)
    for path, lineno, name in findings:
        print("SECRET_FINDING %s:%d %s" % (path, lineno, name))
    if findings:
        print("SECRET_SCAN=FAIL findings=%d" % len(findings))
        return 1
    print("SECRET_SCAN=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

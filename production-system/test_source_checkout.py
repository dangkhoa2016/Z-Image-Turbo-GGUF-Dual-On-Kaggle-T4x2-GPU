"""Fail-closed source checkout policy tests (CPU only, local bare remotes).

Covers the four required notebook scenarios:
  1. fresh checkout creates an independent clone (no archive branch needed)
  2. re-running against the correct revision is idempotent
  3. a dirty checkout is preserved and blocks execution (no reset --hard)
  4. a revision mismatch is blocked without changing the checkout
Plus origin mismatch rejection for an unrelated remote.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from source_checkout import ensure_source, SourceCheckoutError  # noqa: E402

_GIT_ENV = os.environ.copy()
_GIT_ENV.update({
    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid",
})


def sh(args, cwd=None):
    return subprocess.run(["git", *args], cwd=cwd, check=True, env=_GIT_ENV,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True).stdout


def make_origin(base, name, contents):
    origin = base / (name + ".git")
    sh(["init", "--bare", "-b", "main", str(origin)])
    seed = base / (name + "-seed")
    sh(["clone", str(origin), str(seed)])
    shas = []
    for i, text in enumerate(contents):
        (seed / "f.txt").write_text(text)
        sh(["add", "."], cwd=seed)
        sh(["commit", "-m", "c%d" % (i + 1)], cwd=seed)
        shas.append(sh(["rev-parse", "HEAD"], cwd=seed).strip())
    sh(["push", "origin", "main"], cwd=seed)
    return origin, shas


with tempfile.TemporaryDirectory(prefix="zimage-srccheck-") as td:
    base = Path(td)
    origin, (c1, c2) = make_origin(base, "origin", ["one\n", "two\n"])
    assert c1 != c2

    # 1. Fresh checkout creates an independent clone at the ref tip.
    work = base / "work"
    info = ensure_source(work, str(origin), source_ref="main", source_sha="", log=lambda *_: None)
    assert info["sha"] == c2, info
    assert info["clean"] is True, info
    assert (work / ".git").is_dir()
    assert not (work / "archive").exists()  # never depends on an archive branch
    probe = subprocess.run(["git", "rev-parse", "--verify",
                            "refs/remotes/origin/archive/pre-rewrite-20261016"],
                           cwd=work, env=_GIT_ENV, stdout=subprocess.PIPE,
                           stderr=subprocess.DEVNULL, text=True)
    assert probe.returncode != 0, "fresh clone unexpectedly depends on archive branch"

    # 2. Re-running against the same revision is idempotent.
    again = ensure_source(work, str(origin), source_ref="main", source_sha="", log=lambda *_: None)
    assert again["sha"] == c2 and again["clean"] is True

    # Pinned-but-equal revision is also a no-op.
    pinned_eq = ensure_source(work, str(origin), source_ref="main", source_sha=c2, log=lambda *_: None)
    assert pinned_eq["sha"] == c2

    # 3. Dirty checkout is preserved and blocked.
    (work / "f.txt").write_text("local edit\n")
    try:
        ensure_source(work, str(origin), source_ref="main", source_sha="", log=lambda *_: None)
        raise SystemExit("FAIL: dirty checkout was not blocked")
    except SourceCheckoutError as exc:
        assert "SOURCE_TREE_DIRTY" in str(exc), exc
    assert (work / "f.txt").read_text() == "local edit\n"  # preserved, not reset
    sh(["checkout", "--", "f.txt"], cwd=work)

    # 4. Revision mismatch (pinned old SHA) is blocked without changing HEAD.
    head_before = sh(["rev-parse", "HEAD"], cwd=work).strip()
    try:
        ensure_source(work, str(origin), source_ref="main", source_sha=c1, log=lambda *_: None)
        raise SystemExit("FAIL: revision mismatch was not blocked")
    except SourceCheckoutError as exc:
        assert "SOURCE_SHA_MISMATCH" in str(exc), exc
    assert sh(["rev-parse", "HEAD"], cwd=work).strip() == head_before

    # 5. Fresh pinned clone lands on the requested immutable SHA (detached).
    work2 = base / "work-pinned"
    info2 = ensure_source(work2, str(origin), source_ref="main", source_sha=c1, log=lambda *_: None)
    assert info2["sha"] == c1, info2

    # 6. An unrelated origin is rejected.
    other, _ = make_origin(base, "other", ["unrelated\n"])
    work3 = base / "work-other"
    sh(["clone", str(other), str(work3)])
    try:
        ensure_source(work3, str(origin), source_ref="main", source_sha="", log=lambda *_: None)
        raise SystemExit("FAIL: origin mismatch was not blocked")
    except SourceCheckoutError as exc:
        assert "origin mismatch" in str(exc), exc

print("SRCCHECK_PASS fresh idempotent pinned dirty_preserved mismatch_blocked origin_mismatch")

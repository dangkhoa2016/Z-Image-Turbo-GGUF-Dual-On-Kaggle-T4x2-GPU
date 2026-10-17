#!/usr/bin/env python3
"""Fail-closed source checkout policy for the Kaggle demo notebook.

The repository is the single source of truth. This module enforces an
*immutable checkout policy*: it never discards local work, never silently
changes the running revision, and never depends on a historical Git archive
branch. Any ambiguity (dirty tree, wrong origin, revision mismatch) is a hard
stop that asks the operator to clone fresh into a separate path.

Only the Python standard library is used so the module can run before any
project dependency is installed.
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

__all__ = [
    "SourceCheckoutError",
    "sanitize_remote",
    "normalize_remote",
    "ensure_source",
]


class SourceCheckoutError(RuntimeError):
    """Raised when the working copy cannot be verified safely (fail closed)."""


def sanitize_remote(url):
    """Remove embedded credentials from a Git URL for safe printing/logging."""
    return re.sub(r"://[^@/]*@", "://", (url or "").strip())


def normalize_remote(url):
    """Normalize a remote URL for equality comparison (drop creds/.git/slash)."""
    text = sanitize_remote(url)
    if text.endswith(".git"):
        text = text[:-4]
    return text.rstrip("/")


def _run(git_args, cwd=None, check=True):
    proc = subprocess.run(
        ["git", *git_args], cwd=cwd,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    if check and proc.returncode != 0:
        raise SourceCheckoutError(
            "git %s failed: %s" % (" ".join(git_args), proc.stdout.strip()))
    return proc


def _rev(project, ref):
    proc = _run(["rev-parse", "--verify", ref + "^{commit}"], cwd=project, check=False)
    return proc.stdout.strip() if proc.returncode == 0 else None


def _head(project):
    return _run(["rev-parse", "HEAD"], cwd=project).stdout.strip()


def _origin_url(project):
    return _run(["config", "--get", "remote.origin.url"], cwd=project).stdout.strip()


def _is_clean(project):
    return _run(["status", "--porcelain"], cwd=project).stdout.strip() == ""


def ensure_source(project, repo_url, source_ref="main", source_sha="", *, log=print):
    """Return the checked-out source identity or raise ``SourceCheckoutError``.

    ``project`` is created only when it does not exist. When it already exists
    the checkout is verified and *never* reset; on any mismatch the call fails
    closed with guidance to clone fresh into a separate path.
    """
    project = Path(project)
    pinned = (source_sha or "").strip()

    if not (project / ".git").is_dir():
        if project.exists():
            raise SourceCheckoutError(
                "Refusing to overwrite existing non-repository path: %s" % project)
        if pinned:
            _run(["clone", repo_url, str(project)])
            proc = _run(["checkout", "--detach", pinned], cwd=project, check=False)
            if proc.returncode != 0:
                raise SourceCheckoutError(
                    "Pinned SOURCE_SHA %s not found after clone" % pinned)
        else:
            _run(["clone", "--branch", source_ref, repo_url, str(project)])
        log("SOURCE_CLONED_FRESH ref=%s" % (pinned or source_ref))
    else:
        actual_remote = _origin_url(project)
        if normalize_remote(actual_remote) != normalize_remote(repo_url):
            raise SourceCheckoutError(
                "origin mismatch: expected %s but found %s; clone fresh into a "
                "new path instead of reusing this checkout."
                % (normalize_remote(repo_url), normalize_remote(actual_remote)))
        if not _is_clean(project):
            raise SourceCheckoutError(
                "SOURCE_TREE_DIRTY: local changes present; refusing to reset. "
                "Commit/stash them, or clone fresh into a new path.")
        if pinned:
            target = _rev(project, pinned)
            if target is None:
                _run(["fetch", "--no-tags", "origin", source_ref], cwd=project,
                     check=False)
                target = _rev(project, pinned)
            if target is None:
                raise SourceCheckoutError(
                    "Pinned SOURCE_SHA %s not found in origin" % pinned)
        else:
            fetch = _run(["fetch", "--no-tags", "--depth", "1", "origin", source_ref],
                         cwd=project, check=False)
            if fetch.returncode != 0:
                raise SourceCheckoutError(
                    "Unable to fetch %s from origin: %s" % (source_ref, fetch.stdout.strip()))
            target = _rev(project, "FETCH_HEAD") or _rev(project, "origin/" + source_ref)
            if target is None:
                raise SourceCheckoutError(
                    "Could not resolve %s after fetch" % source_ref)
        head = _head(project)
        if head != target:
            raise SourceCheckoutError(
                "SOURCE_SHA_MISMATCH: checkout %s != expected %s; refusing to "
                "change revision. Clone fresh into a new path." % (head, target))
        log("SOURCE_CHECKOUT_VERIFIED ref=%s" % (pinned or source_ref))

    return {
        "project": str(project),
        "sha": _head(project),
        "remote": sanitize_remote(_origin_url(project)),
        "clean": _is_clean(project),
    }


def _main(argv=None):
    parser = argparse.ArgumentParser(description="Fail-closed Git source checkout policy.")
    parser.add_argument("--project", required=True)
    parser.add_argument("--repo-url", required=True)
    parser.add_argument("--source-ref", default="main")
    parser.add_argument("--source-sha", default="")
    args = parser.parse_args(argv)
    try:
        info = ensure_source(args.project, args.repo_url,
                             source_ref=args.source_ref, source_sha=args.source_sha)
    except SourceCheckoutError as exc:
        print("SOURCE_CHECKOUT_FAILED: %s" % exc, file=sys.stderr)
        return 1
    print("SOURCE_SHA=%s" % info["sha"])
    print("SOURCE_REMOTE=%s" % info["remote"])
    print("SOURCE_TREE_CLEAN=%s" % info["clean"])
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())

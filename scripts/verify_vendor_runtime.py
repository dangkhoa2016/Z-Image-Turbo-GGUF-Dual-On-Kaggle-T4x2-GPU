#!/usr/bin/env python3
"""Fail closed when imports or dist metadata do not originate in the pinned vendor tree."""
import importlib.metadata as metadata
import importlib.util
import sys
from pathlib import Path

from bootstrap_vendor import LOCK, ROOT, verify


def validate():
    results = []
    for dirname, (package, version, _, tree_hash, file_count) in LOCK.items():
        vendor_dir = (ROOT / dirname).resolve()
        verify(vendor_dir, package, version, tree_hash, file_count)
        spec = importlib.util.find_spec(package)
        if spec is None or spec.origin is None:
            raise RuntimeError(f"VENDOR_IMPORT_MISSING: {package}")
        origin = Path(spec.origin).resolve()
        if not origin.is_relative_to(vendor_dir / package):
            raise RuntimeError(f"VENDOR_IMPORT_SHADOWED: {package}: {origin}")
        distribution = metadata.distribution(package)
        located = Path(distribution.locate_file("")).resolve()
        if located != vendor_dir or distribution.version != version:
            raise RuntimeError(
                f"VENDOR_METADATA_SHADOWED: {package}: {located} ({distribution.version})"
            )
        results.append((package, version, origin))
    if "sitecustomize" not in sys.modules:
        raise RuntimeError("VENDOR_SHIM_NOT_AUTOLOADED")
    shim = Path(sys.modules["sitecustomize"].__file__).resolve()
    if shim != (ROOT / "vendor-shim" / "sitecustomize.py").resolve():
        raise RuntimeError(f"VENDOR_SHIM_SHADOWED: {shim}")
    for package, version, origin in results:
        print(f"RUNTIME_VENDOR_VERIFIED {package}=={version} {origin}")
    print("RUNTIME_VENDOR_ISOLATION_PASS")


if __name__ == "__main__":
    validate()

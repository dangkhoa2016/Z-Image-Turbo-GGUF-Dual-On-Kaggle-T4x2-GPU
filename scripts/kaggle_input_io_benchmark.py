#!/usr/bin/env python3
"""CPU-only bounded Kaggle input read/mmap benchmark. No weights copied or modified.

This measures small windows of the same GGUF and Qwen3 files used by the demo,
without constructing a model or importing torch/diffusers. Caches, network file
systems and other users can affect results. A slow probe supports an I/O
hypothesis; a fast probe does NOT rule out full-model page-in or CUDA stalls.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import mmap
import os
from pathlib import Path
import platform
import resource
import stat
import subprocess
import sys
import tempfile
import time

VERSION = "1.0"
POSITIONS = ("begin", "middle", "end")


def bytes_read():
    try:
        values = {}
        for line in Path("/proc/self/io").read_text().splitlines():
            key, _, val = line.partition(":")
            if key in ("read_bytes", "rchar", "syscr"):
                values[key] = int(val.strip())
        return values
    except (OSError, ValueError):
        return {}


def mem_stats():
    names = ("file", "anon", "pgfault", "pgmajfault", "workingset_refault_file")
    result = {}
    try:
        for line in Path("/sys/fs/cgroup/memory.stat").read_text().splitlines():
            key, value = line.split()
            if key in names:
                result[key] = int(value)
    except (OSError, ValueError):
        pass
    return result


def mount_info(path):
    """Best matching Linux mount, from procfs (mount-specific, not a disk speed claim)."""
    best = None
    try:
        for line in Path("/proc/self/mountinfo").read_text().splitlines():
            first, sep, after = line.partition(" - ")
            if not sep:
                continue
            fields = first.split()
            if len(fields) < 5:
                continue
            root = fields[4].replace("\\040", " ")
            if not (str(path) == root or str(path).startswith(root.rstrip("/") + "/")):
                continue
            if best is None or len(root) > len(best["mount_point"]):
                fs = after.split()
                best = {"mount_point": root, "filesystem": fs[0] if fs else "unknown",
                        "mount_source": fs[1] if len(fs)>1 else "unknown"}
    except OSError:
        pass
    return best


def windows(size, nbytes):
    if not (isinstance(size, int) and size >= 1 and 1 <= nbytes <= 8*1048576):
        raise ValueError("INVALID_BOUNDED_SAMPLE")
    length = min(size, nbytes)
    offsets = [0, max(0, (size-length)//2), max(0, size-length)]
    return list(zip(POSITIONS, offsets, [length]*3))


def sample_one(fd, name, offset, nbytes, method):
    before = bytes_read()
    usage0 = resource.getrusage(resource.RUSAGE_SELF)
    stamp = time.monotonic()
    if method == "pread":
        remaining = nbytes
        parts = []
        next_offset = offset
        while remaining:
            part = os.pread(fd, remaining, next_offset)
            if not part:
                raise RuntimeError("SHORT_READ")
            parts.append(part)
            next_offset += len(part)
            remaining -= len(part)
        blob = b"".join(parts)
    elif method == "mmap":
        page = mmap.ALLOCATIONGRANULARITY
        aligned = offset - offset % page
        shift = offset - aligned
        with mmap.mmap(fd, length=nbytes + shift,
                       offset=aligned, access=mmap.ACCESS_READ) as view:
            blob = view[shift:shift+nbytes]
    else:
        raise ValueError("INVALID_READ_METHOD")
    # Hash is to prove equality between two bounded read mechanisms,
    # not the full model SHA256.
    digest = hashlib.sha256(blob).hexdigest()
    del blob
    elapsed = max(time.monotonic()-stamp, 1e-9)
    usage1 = resource.getrusage(resource.RUSAGE_SELF)
    after = bytes_read()
    result = {
        "position": name, "offset_bytes": offset,
        "sample_bytes": nbytes, "method": method,
        "seconds": round(elapsed, 5),
        "mib_per_second": round((nbytes/1048576)/elapsed, 3),
        "sample_sha256": digest,
        "minor_faults_delta": usage1.ru_minflt-usage0.ru_minflt,
        "major_faults_delta": usage1.ru_majflt-usage0.ru_majflt,
        "cpu_user_seconds_delta": round(usage1.ru_utime-usage0.ru_utime, 4),
        "cpu_system_seconds_delta": round(usage1.ru_stime-usage0.ru_stime, 4),
    }
    for key in ("read_bytes", "rchar", "syscr"):
        if key in before and key in after:
            result[key+"_delta"] = after[key] - before[key]
    return result


def profile_file(path: Path, mib: int, repeats: int):
    if not (1<=mib<=8 and 1<=repeats<=2):
        raise ValueError("BOUNDS: 1..8 MiB and 1..2 passes")
    if path.is_symlink() or not path.is_file():
        raise ValueError("MODEL_FILE_MISSING_OR_SYMLINK")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        meta = os.fstat(fd)
        if not stat.S_ISREG(meta.st_mode) or meta.st_size<=0:
            raise ValueError("MODEL_INPUT_NOT_REGULAR_FILE")
        result = {
            "path": str(path), "size_bytes": meta.st_size,
            "mount": mount_info(path),
            "memory_stat_before": mem_stats(),
            "events": [],
        }
        # First pread pass may be cold, but this is NOT guaranteed. Subsequent
        # reads can warm page cache, so no pass is labeled 'cold'.
        for method in ("pread", "mmap"):
            for number in range(1,repeats+1):
                for label, offset, size in windows(meta.st_size, mib*1048576):
                    sample = sample_one(fd,label,offset,size,method)
                    sample["pass"] = number
                    result["events"].append(sample)
        # Verify method equivalence, fail closed if the source changes during
        # benchmarking. The full source hash is deliberately NOT computed.
        by_pos = {}
        for item in result["events"]:
            key = item["position"]
            if key in by_pos and by_pos[key]!=item["sample_sha256"]:
                raise RuntimeError("SAMPLE_DIGEST_CHANGED_DURING_BENCHMARK")
            by_pos[key]=item["sample_sha256"]
        result["memory_stat_after"] = mem_stats()
        return result
    finally:
        os.close(fd)


def read_setup(project: Path, max_text_shards: int):
    if not (1 <= max_text_shards <= 3):
        raise ValueError("MAX_SHARDS_BOUNDS")
    model = json.loads((project/"manifests/model.json").read_text())
    support = json.loads((project/"manifests/support.json").read_text())
    gguf = Path(model["gguf_path"])
    support_root = Path(support["support_root"])
    folder = support_root/"text_encoder"
    if (not gguf.is_file() or gguf.is_symlink() or not folder.is_dir()
            or folder.is_symlink()):
        raise FileNotFoundError(
            "MODEL_ATTACHMENTS_MISSING: mount BOTH GGUF model and support dataset "
            "in a Kaggle CPU notebook with the same version as GPU run")
    if gguf.stat().st_size != model["gguf_bytes"]:
        raise ValueError("GGUF_MANIFEST_FILE_SIZE_MISMATCH")
    shards = [f for f in folder.iterdir()
              if f.is_file() and f.suffix in (".safetensors",".bin")]
    if not shards:
        raise FileNotFoundError("QWEN3_WEIGHT_SHARDS_MISSING")
    if any(f.is_symlink() for f in shards):
        raise ValueError("SHARD_SYMLINK_REJECTED")
    shards.sort(key=lambda x: (-x.stat().st_size, x.name))
    selected = [gguf]+shards[:max_text_shards]
    return selected, {"model_sha256_expected":model["gguf_sha256"],
                      "support_manifest_sha256":support.get("manifest_sha256"),
                      "gguf_size_expected":model["gguf_bytes"],
                      "text_shards_total":len(shards),
                      "text_shards_selected":len(selected)-1}


def run(project, out, mib, repeats, max_text_shards, timeout):
    files, identity = read_setup(project,max_text_shards)
    if out.is_symlink():
        raise ValueError("OUTPUT_DIR_SYMLINK_REJECTED")
    out.mkdir(mode=0o700,parents=True,exist_ok=True)
    results = []
    for index,path in enumerate(files):
        print("PROBE_START",index+1,"of",len(files),path.name,flush=True)
        cmd = [sys.executable, __file__, "_worker", "--path",str(path),
               "--sample-mib",str(mib),"--repeats",str(repeats)]
        start = time.monotonic()
        try:
            cp = subprocess.run(cmd, capture_output=True,text=True,
                                timeout=timeout,check=False)
            if cp.returncode:
                value={"path":str(path),"status":"ERROR",
                       "message":(cp.stderr or cp.stdout)[-800:]}
            else:
                value=json.loads(cp.stdout)
                value["status"]="PASS"
        except subprocess.TimeoutExpired:
            value={"path":str(path),"status":"TIMEOUT","seconds_limit":timeout}
        value["wall_seconds"]=round(time.monotonic()-start,3)
        results.append(value)
        print("PROBE_RESULT",index+1,value["status"],
              value["wall_seconds"],"seconds",flush=True)
    report = {
        "version":VERSION,"cpu_only":True,"read_only":True,
        "gpu_inference":"NOT_RUN","source_checksum":"BOUNDED_SAMPLES_ONLY",
        "timestamp_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "host":platform.node(),"python":platform.python_version(),
        "cpu_count":os.cpu_count(),"project":str(project),
        "parameters":{"sample_mib":mib,"repeats":repeats,
                      "max_text_shards":max_text_shards,
                      "timeout_seconds_per_file":timeout},
        "identity":identity,"files":results,
        "interpretation":"Throughputs include cache and FUSE effects. Fast samples "
        "do not exclude slow full-model tensor materialization or CUDA copies. "
        "No disk cache was dropped and no model files were modified.",
    }
    now=datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path=out/("kaggle-input-io-"+now+".json")
    with path.open("x",encoding="utf-8") as stream:
        json.dump(report,stream,indent=2,ensure_ascii=False)
        stream.write("\n")
    print("ZIMAGE_IO_BENCHMARK_REPORT",path,flush=True)
    print("ZIMAGE_IO_BENCHMARK_STATUS",
          "PASS" if all(x["status"]=="PASS" for x in results) else "PARTIAL",flush=True)
    return 0 if all(x["status"]=="PASS" for x in results) else 2


def self_test():
    assert windows(1024,128)==[
        ("begin",0,128),("middle",448,128),("end",896,128)]
    with tempfile.TemporaryDirectory(prefix="zimage-io-bench-test-") as name:
        tmp=Path(name)
        source=tmp/"data.safetensors"
        source.write_bytes(bytes(range(256))*32768)  # 8 MiB, synthetic CPU data
        stats=profile_file(source,1,2)
        assert len(stats["events"])==12
        assert {x["method"] for x in stats["events"]}=={"pread","mmap"}
        assert all(x["sample_bytes"]==1048576 for x in stats["events"])
        assert all(x["seconds"]>0 and x["mib_per_second"]>0
                   for x in stats["events"])
        link=tmp/"link.safetensors"
        link.symlink_to(source)
        try:
            profile_file(link,1,1)
        except ValueError:
            pass
        else:
            raise AssertionError("symlink not rejected")
        print("ZIMAGE_IO_BENCHMARK_CPU_SELF_TEST_PASS",
              "bytes_synthetic=8388608 samples=12 cuda_not_imported=YES",flush=True)
    return 0


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project",type=Path,default=Path.cwd())
    parser.add_argument("--out",type=Path,
                        default=Path("/kaggle/working/zimage-input-io-benchmark"))
    parser.add_argument("--sample-mib",type=int,default=2,choices=range(1,9))
    parser.add_argument("--repeats",type=int,default=2,choices=(1,2))
    parser.add_argument("--max-text-shards",type=int,default=2,choices=(1,2,3))
    parser.add_argument("--timeout-per-file",type=int,default=90)
    parser.add_argument("--self-test",action="store_true")
    parser.add_argument("_internal",nargs="?",choices=("_worker",))
    parser.add_argument("--path",type=Path)
    a=parser.parse_args()
    if a.self_test:
        return self_test()
    if a._internal=="_worker":
        if a.path is None:
            raise ValueError("MISSING_FILE")
        print(json.dumps(profile_file(a.path,a.sample_mib,a.repeats),
                         sort_keys=True))
        return 0
    if not 10 <= a.timeout_per_file <= 180:
        parser.error("--timeout-per-file must be between 10 and 180")
    return run(a.project.resolve(),a.out,a.sample_mib,a.repeats,
               a.max_text_shards,a.timeout_per_file)


if __name__=="__main__":
    try:
        raise SystemExit(main())
    except (OSError,ValueError,FileNotFoundError,RuntimeError) as exc:
        print("ZIMAGE_IO_BENCHMARK_FAILED",type(exc).__name__+":"+str(exc),
              file=sys.stderr,flush=True)
        raise SystemExit(2)

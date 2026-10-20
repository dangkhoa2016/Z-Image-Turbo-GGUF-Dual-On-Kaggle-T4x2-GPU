#!/usr/bin/env python3
"""Read-only Qwen3 startup I/O diagnostics, Linux CPU-only compatible.

Observes the actual encode_batch_gpu.py child process, not its phase-controller
parent. Does not load, copy, hash or modify model weights. Only the optional
small shard probe accesses weight bytes; cached reads cannot measure cold I/O.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import time

from gguf_startup_diagnostics import read_process

def describe_text_encoder_storage(folder: Path, sample_mib: int = 8) -> dict:
    """Bounded shard inventory and sample; not an end-to-end I/O benchmark."""
    folder=Path(folder)
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError("QWEN3_SUPPORT_TEXT_ENCODER_DIRECTORY_INVALID")
    if not isinstance(sample_mib,int) or not 0<=sample_mib<=16:
        raise ValueError("QWEN3_PROBE_BOUNDS_INVALID")
    weights=[]
    for item in sorted(folder.iterdir()):
        if item.is_symlink():
            raise ValueError("QWEN3_WEIGHT_SYMLINK_REJECTED")
        if item.is_file() and item.suffix in (".safetensors",".bin"):
            weights.append(item)
    if not weights:
        raise ValueError("QWEN3_SUPPORT_WEIGHTS_NOT_FOUND")
    total=sum(x.stat().st_size for x in weights)
    result={"shards":len(weights),"total_weight_bytes":total,
            "first_shard_bytes":weights[0].stat().st_size,
            "sample_bytes":0,"sample_seconds":0.0,
            "sample_mib_per_second":None,
            "warning":"Bounded sequential read; page cache and mount conditions affect results"}
    if sample_mib:
        wanted=min(sample_mib*1048576,weights[0].stat().st_size)
        seen=0
        started=time.monotonic()
        with weights[0].open("rb") as stream:
            while seen<wanted:
                data=stream.read(min(1048576,wanted-seen))
                if not data:
                    break
                seen+=len(data)
        elapsed=max(time.monotonic()-started,1e-6)
        result.update(sample_bytes=seen,sample_seconds=round(elapsed,3),
                      sample_mib_per_second=round((seen/1048576)/elapsed,2))
    return result

def encoder_child_snapshot(controller_pid: int) -> dict | None:
    """Find the actual direct Python encoder child; never report unrelated PIDs."""
    if not isinstance(controller_pid,int) or controller_pid<=0:
        raise ValueError("invalid controller PID")
    children=Path("/proc")/str(controller_pid)/"task"/str(controller_pid)/"children"
    try:
        pid_strings=children.read_text().strip().split()
    except (OSError,ValueError):
        return None
    for entry in pid_strings:
        try:
            pid=int(entry)
            args=(Path("/proc")/str(pid)/"cmdline").read_bytes().split(b"\0")
            # subprocess.run([python, path/to/encode_batch_gpu.py, ...])
            if not any(arg.decode("utf-8","replace").endswith("/encode_batch_gpu.py")
                       for arg in args if arg):
                continue
            return read_process(pid)
        except (OSError,ValueError,AssertionError):
            continue
    return None

def process_delta(previous: dict | None, current: dict | None, elapsed: float) -> dict:
    """Counter deltas are meaningful only for the same process incarnation."""
    if current is None:
        return {"state":"ENCODER_PROCESS_NOT_FOUND"}
    result={
        "state":current.get("process_state"),
        "pid":current["pid"],
        "rss_mib":round(current.get("rss_bytes",0)/1048576,1),
        "major_faults":current.get("major_faults"),
        "minor_faults":current.get("minor_faults"),
        "read_bytes":current.get("read_bytes"),
        "rchar":current.get("rchar"),
        "cpu_user_ticks":current.get("cpu_user_ticks"),
        "cpu_system_ticks":current.get("cpu_system_ticks"),
    }
    if (previous is not None and
        previous.get("pid")==current["pid"] and
        previous.get("process_start_ticks")==current.get("process_start_ticks")
        and elapsed>0):
        for key in ("read_bytes","rchar","major_faults","minor_faults"):
            if key in current and key in previous:
                result[key+"_delta"]=max(0,current[key]-previous[key])
        if "read_bytes_delta" in result:
            result["read_mib_per_second"]=round(result["read_bytes_delta"]/1048576/elapsed,3)
        ticks=((current["cpu_user_ticks"]+current["cpu_system_ticks"])-
               (previous["cpu_user_ticks"]+previous["cpu_system_ticks"]))
        result["cpu_pct_one_core_100"]=round(max(0,ticks)/current["cpu_ticks_per_second"]/elapsed*100,2)
    return result

if __name__=="__main__":
    raise SystemExit("Import the CPU-only Qwen3 diagnostics into the Kaggle notebook")

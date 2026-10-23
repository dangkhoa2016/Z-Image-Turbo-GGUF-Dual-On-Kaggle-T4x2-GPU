#!/usr/bin/env python3
"""CPU-only, read-only VAE startup stall observer for diagnostic Kaggle runs.

Never touches model tensors, checkpoint bytes, job outputs or CUDA.
It provides bounded /proc + nvidia-smi samples for VAE stage dwell analysis.
"""
from __future__ import annotations
from pathlib import Path
import os
import re
import subprocess
import time

_ALLOWED_STAGES = frozenset({"VAE_LOAD_BEGIN", "VAE_LOAD_FINISHED"})
MAX_SAMPLE_BYTES = 2048


def read_bounded(path: Path, max_bytes: int = MAX_SAMPLE_BYTES) -> str | None:
    path = Path(path)
    if path.is_symlink():
        return None
    try:
        with path.open("rb") as file:
            data = file.read(max_bytes + 1)
        if len(data) > max_bytes:
            return None
        return data.decode("utf-8",errors="replace").strip()
    except (OSError, ValueError):
        return None


def sample_vae_startup(pid: int, gpu: int, stage: str, seconds_in_stage: float,
                       proc_root: Path = Path("/proc"),
                       cgroup_root: Path = Path("/sys/fs/cgroup"),
                       gpu_probe: bool = True) -> dict:
    if (isinstance(pid,bool) or not isinstance(pid,int) or pid<=0
            or gpu not in (0,1) or isinstance(gpu,bool)
            or stage not in _ALLOWED_STAGES
            or not isinstance(seconds_in_stage,(float,int))
            or isinstance(seconds_in_stage,bool)
            or seconds_in_stage < 0):
        raise ValueError("P27_OBSERVER_INVALID_ARGUMENT")
    proc=Path(proc_root)/str(pid)
    wchan=read_bounded(proc/"wchan",64)
    schedstat=read_bounded(proc/"schedstat",256)
    status=read_bounded(proc/"status",MAX_SAMPLE_BYTES)
    state=None
    if status:
        state=next((line.split(":",1)[1].strip() for line in status.splitlines()
                    if line.startswith("State:")),None)
    memory_pressure=read_bounded(Path(cgroup_root)/"memory.pressure",512)
    io_pressure=read_bounded(Path(cgroup_root)/"io.pressure",512)
    result={
        "schema":"ZIMAGE_P27_VAE_READ_ONLY_SAMPLE_V1",
        "pid":pid,"gpu":gpu,"stage":stage,
        "seconds_in_stage":round(float(seconds_in_stage),2),
        "worker_state":state,
        "worker_wchan":wchan,
        "worker_schedstat":schedstat,
        "cgroup_memory_pressure":memory_pressure,
        "cgroup_io_pressure":io_pressure,
        "gpu_probe":"not_requested",
    }
    if gpu_probe:
        try:
            proc=subprocess.run(
                ["nvidia-smi","--query-gpu=index,utilization.gpu,utilization.memory,memory.used",
                 "--format=csv,noheader,nounits","-i",str(gpu)],
                capture_output=True,text=True,timeout=5,check=False)
            line=proc.stdout.strip()
            if proc.returncode==0 and len(line)<150 and re.fullmatch(r"[\d,\sN/A]+",line):
                result["gpu_probe"]=line
            else:
                result["gpu_probe"]="unavailable"
        except (OSError,subprocess.TimeoutExpired):
            result["gpu_probe"]="unavailable"
    return result


def stack_request_allowed(pid: int, stage: str, seconds_in_stage: float,
                          prior_thresholds: set[tuple[str,int]],
                          worker_log: Path, threshold: int) -> bool:
    """Policy only: caller sends SIGUSR1 after checking process is still alive.

    The GGUF wrapper must already have announced faulthandler registration.
    """
    if (stage not in _ALLOWED_STAGES or threshold not in (12,30)
            or seconds_in_stage < threshold
            or (stage,threshold) in prior_thresholds
            or pid<=0 or worker_log.is_symlink()):
        return False
    try:
        if not worker_log.is_file() or worker_log.stat().st_size>6*1024**2:
            return False
        with worker_log.open("rb") as log:
            # The faulthandler marker is printed near startup, before imports.
            marker=log.read(8192)
        return b"ZIMAGE_GGUF_STACK_PROBE_READY" in marker
    except OSError:
        return False

"""P2.7 CPU-only VAE process observer tests. No GPU or model loading."""
from pathlib import Path
import ast,json,sys,tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from vae_startup_probe import sample_vae_startup,read_bounded,stack_request_allowed

def fail(fragment,callback):
    try:callback()
    except (ValueError,RuntimeError) as exc:
        assert fragment in str(exc),(fragment,str(exc))
    else:raise AssertionError("EXPECTED_REJECTION:"+fragment)

with tempfile.TemporaryDirectory(prefix="p27-proc-stub-") as t:
    base=Path(t)
    proc=base/"proc"
    child=proc/"4812";child.mkdir(parents=True)
    (child/"wchan").write_text("futex_wait_queue")
    (child/"status").write_text("Name:\tpython\nState:\tS (sleeping)\nVmRSS:\t900 kB\n")
    (child/"schedstat").write_text("123 456 8")
    group=base/"cgroup";group.mkdir()
    (group/"memory.pressure").write_text("some avg10=0.00 total=123")
    (group/"io.pressure").write_text("some avg10=0.12 total=456")
    sample=sample_vae_startup(
        4812,0,"VAE_LOAD_FINISHED",17.222,
        proc_root=proc,cgroup_root=group,gpu_probe=False)
    assert sample["stage"]=="VAE_LOAD_FINISHED"
    assert sample["seconds_in_stage"]==17.22
    assert sample["worker_wchan"]=="futex_wait_queue"
    assert sample["worker_state"]=="S (sleeping)"
    assert sample["worker_schedstat"]=="123 456 8"
    assert sample["gpu_probe"]=="not_requested"
    assert "total=456" in sample["cgroup_io_pressure"]
    fail("P27_OBSERVER_INVALID_ARGUMENT",lambda:sample_vae_startup(
        -1,0,"VAE_LOAD_BEGIN",1,gpu_probe=False))
    fail("P27_OBSERVER_INVALID_ARGUMENT",lambda:sample_vae_startup(
        1,9,"VAE_LOAD_BEGIN",1,gpu_probe=False))
    fail("P27_OBSERVER_INVALID_ARGUMENT",lambda:sample_vae_startup(
        1,0,"PIPELINE_READY",1,gpu_probe=False))
    (child/"wchan").unlink()
    (child/"wchan").symlink_to(base/"fake")
    (base/"fake").write_text("should never be read")
    assert read_bounded(child/"wchan",64) is None
    (child/"status").write_text("X"*5000)
    sample=sample_vae_startup(4812,0,"VAE_LOAD_BEGIN",0,
                             proc_root=proc,cgroup_root=group,gpu_probe=False)
    assert sample["worker_state"] is None
    log=base/"worker-0.log"
    log.write_text("ZIMAGE_GGUF_STACK_PROBE_READY\nZIMAGE_WORKER_STAGE {}\n")
    assert stack_request_allowed(4812,"VAE_LOAD_FINISHED",12,set(),log,12)
    assert not stack_request_allowed(4812,"VAE_LOAD_FINISHED",12,{("VAE_LOAD_FINISHED",12)},log,12)
    assert not stack_request_allowed(4812,"GGUF_LOAD_BEGIN",100,set(),log,12)
    assert not stack_request_allowed(4812,"VAE_LOAD_FINISHED",10,set(),log,12)
    assert not stack_request_allowed(4812,"VAE_LOAD_FINISHED",31,set(),log,13)
    assert stack_request_allowed(4812,"VAE_LOAD_FINISHED",31,set(),log,30)
    sneaky=base/"symlink.log";sneaky.symlink_to(log)
    assert not stack_request_allowed(4812,"VAE_LOAD_FINISHED",31,set(),sneaky,30)
    log.write_text("not registered")
    assert not stack_request_allowed(4812,"VAE_LOAD_FINISHED",31,set(),log,30)

assert not (ROOT/"benchmarks/notebooks").exists()
print("VAE_STARTUP_OBSERVER_CPU_PASS procfs_mock bounded_stack_policy symlink_guard missing_data no_inference")

"""CPU-only isolation benchmark contract and end-to-end synthetic test."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

PROJECT=Path(__file__).resolve().parents[1]
TOOL=PROJECT/"scripts/kaggle_input_io_benchmark.py"
assert TOOL.is_file() and not TOOL.is_symlink()
test=subprocess.run([sys.executable,str(TOOL),"--self-test"],
    capture_output=True,text=True,timeout=20)
assert test.returncode==0,(test.stdout,test.stderr)
assert "CPU_SELF_TEST_PASS" in test.stdout

with tempfile.TemporaryDirectory(prefix="zimage-io-isolation-") as directory:
    root=Path(directory)
    source=root/"source"
    manifests=source/"manifests"
    weights=source/"support"/"text_encoder"
    manifests.mkdir(parents=True)
    weights.mkdir(parents=True)
    model=source/"model.gguf"
    model.write_bytes(bytes(range(256))*32768)  # 8 MiB synthetic
    (weights/"model-00001.safetensors").write_bytes(bytes(range(255,-1,-1))*32768)
    (manifests/"model.json").write_text(json.dumps({
        "gguf_path":str(model),"gguf_bytes":model.stat().st_size,
        "gguf_sha256":hashlib.sha256(model.read_bytes()).hexdigest()
    }))
    (manifests/"support.json").write_text(json.dumps({
        "support_root":str(weights.parent),"manifest_sha256":"d"*64
    }))
    cmd=[sys.executable,str(TOOL),
         "--project",str(source),"--out",str(root/"reports"),
         "--sample-mib","1","--repeats","2",
         "--max-text-shards","1","--timeout-per-file","10"]
    cp=subprocess.run(cmd,capture_output=True,text=True,timeout=45)
    assert cp.returncode==0,(cp.stdout,cp.stderr)
    assert "ZIMAGE_IO_BENCHMARK_STATUS PASS" in cp.stdout
    reports=list((root/"reports").glob("kaggle-input-io-*.json"))
    assert len(reports)==1
    report=json.loads(reports[0].read_text())
    assert report["cpu_only"] and report["gpu_inference"]=="NOT_RUN"
    assert len(report["files"])==2
    for item in report["files"]:
        assert item["status"]=="PASS"
        assert len(item["events"])==12
        assert {x["method"] for x in item["events"]}=={"pread","mmap"}
        assert {x["position"] for x in item["events"]}=={"begin","middle","end"}
        assert {x["pass"] for x in item["events"]}=={1,2}
        assert all(x["sample_bytes"]==1048576 and x["seconds"]>0
                   for x in item["events"])
    missing=subprocess.run([sys.executable,str(TOOL),
                            "--project",str(PROJECT),"--out",str(root/"missing")],
                           capture_output=True,text=True,timeout=10)
    # On a CPU sandbox without the Kaggle-mounted model, fail with an explicit
    # model-attachment message, never claim a benchmark succeeded.
    if not Path(json.loads((PROJECT/"manifests/model.json").read_text())["gguf_path"]).exists():
        assert missing.returncode==2 and "MODEL_ATTACHMENTS_MISSING" in missing.stderr
print("KAGGLE_INPUT_IO_CPU_TEST_PASS synthetic_gguf_qwen3 2_files 24_windows invalid_inputs")

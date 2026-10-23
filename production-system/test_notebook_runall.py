"""CPU-only P2.3 tests. All PNGs used here are synthetic fixtures, NOT GPU outputs."""
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import zipfile

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "scripts"))
from kaggle_production_demo import engine_notebook
sys.path.insert(0, str(ROOT / "scripts"))
from notebook_runall_acceptance import export_runall_evidence

nb = engine_notebook(ROOT)
assert len(nb["cells"]) == 28
checkout = "".join(nb["cells"][3]["source"])
display = "".join(nb["cells"][13]["source"])
assert 'SOURCE_REF = os.environ.get("ZIMAGE_SOURCE_REF", "main")' in checkout
assert "P23_ENABLE_OPTIONAL_WEB_APPS = True" in checkout
assert "FINAL_RUNALL_POLICY" in checkout
assert 'from notebook_runall_acceptance import export_runall_evidence' in display
assert "report_path=DIRECT_REPORT" in display
assert 'reuse=DIRECT_IMAGES_WERE_REUSED' in display
assert 'output_zip=DIRECT_ROOT / "p23-runall-acceptance.zip"' in display
optional=(16,18,20,22,24,27)
for i in optional:
    cell="".join(nb["cells"][i]["source"])
    assert "if P23_ENABLE_OPTIONAL_WEB_APPS:" in cell and "P23_OPTIONAL_UI_SKIPPED" in cell
    assert "else:" in cell
    output=io.StringIO()
    # The optional cells must run without any Kaggle, GPU, Internet, IPython or Studio globals.
    with contextlib.redirect_stdout(output):
        exec(compile(cell, f"notebook-cell-{i}", "exec"), {"P23_ENABLE_OPTIONAL_WEB_APPS":False})
    assert "P23_OPTIONAL_UI_SKIPPED" in output.getvalue()
assert "STUDIO_MONITOR_MAX_MINUTES = None" in "".join(nb["cells"][27]["source"])
assert "p23-runall-acceptance.zip" in "".join(nb["cells"][25]["source"])

SHA="a"*40
FP="b"*64
SEEDS=(112233, 445566)
PROMPTS=("CPU fixture prompt 0", "CPU fixture prompt 1")


def bad(expected, call):
    try:
        call()
    except (ValueError, RuntimeError) as exc:
        assert expected in str(exc), (expected, type(exc).__name__,str(exc))
        return
    raise AssertionError("Should reject " + expected)


with tempfile.TemporaryDirectory(prefix="zimage-p23-cpu-fixture-") as temp:
    root=Path(temp)
    files=[]
    for i, color in enumerate(((255, 0, 0), (0, 127, 245))):
        filename=root/f"gpu{i}.png"
        Image.new("RGB",(1024,1024),color).save(filename,format="PNG")
        digest=hashlib.sha256(filename.read_bytes()).hexdigest()
        files.append({"gpu":i,"pid":1200+i,"seed":SEEDS[i],
                      "prompt":PROMPTS[i],"file":str(filename),
                      "sha256":digest,"generation_seconds":1.9+i})
    report={
        "status":"DUAL_GPU_NOTEBOOK_RENDER_VERIFIED","source_sha":SHA,
        "inference_fingerprint":FP,"images":files,"encoder_gpu":0,
        "encoding_seconds":12.0,"model_startup_seconds":21.0,
        "parallel_inference_wall_seconds":2.8}
    r=root/"report.json"
    z=root/"p23-runall-acceptance.zip"
    def setreport(x):r.write_text(json.dumps(x)+"\n")
    def run(reuse=False):return export_runall_evidence(
        report_path=r,output_zip=z,source_sha=SHA,inference_fingerprint=FP,
        seeds=SEEDS,prompts=PROMPTS,reuse=reuse)
    setreport(report)
    (root/"worker-0.log").write_text("GPU0_PIPELINE_READY")
    (root/"worker-1.log").write_text("GPU1_PIPELINE_READY")
    (root/"encoder.log").write_text("Authorization: Bearer should-not-leak")
    (root/"other-secret.txt").write_text("private should-not-package")
    result=run()
    assert result["status"]=="P23_TWO_GPU_IMAGES_SHA256_VERIFIED"
    assert result["execution"]=="GENERATED_IN_CURRENT_KERNEL_RUN"
    assert result["gpu_images"]==2 and z.is_file()
    with zipfile.ZipFile(z) as bundle:
        assert bundle.testzip() is None
        receipt=json.loads(bundle.read("acceptance.json"))
        assert receipt["new_gpu_images_generated_during_this_run"] is True
        assert len(receipt["images"])==2
        assert hashlib.sha256(bundle.read("images/gpu0-1024x1024.png")).hexdigest()==files[0]["sha256"]
        assert hashlib.sha256(bundle.read("images/gpu1-1024x1024.png")).hexdigest()==files[1]["sha256"]
        assert "diagnostics/worker-0.log" in bundle.namelist()
        assert "diagnostics/worker-1.log" in bundle.namelist()
        assert "diagnostics/encoder.log" not in bundle.namelist()
        assert "other-secret.txt" not in bundle.namelist()
        assert any(x["reason"]=="POSSIBLE_SECRET" for x in receipt["diagnostics_omitted"])
    previous=z.read_bytes()
    result=run(reuse=True)
    assert result["execution"]=="VERIFIED_REUSE"
    with zipfile.ZipFile(z) as bundle:
        receipt=json.loads(bundle.read("acceptance.json"))
        assert receipt["new_gpu_images_generated_during_this_run"] is False
    assert len(z.read_bytes()) > 0
    bad("P23_SOURCE_SHA_MISMATCH",lambda:export_runall_evidence(
        report_path=r,output_zip=z,source_sha="c"*40,inference_fingerprint=FP,
        seeds=SEEDS,prompts=PROMPTS,reuse=False))
    bad("P23_INFERENCE_FINGERPRINT_MISMATCH",lambda:export_runall_evidence(
        report_path=r,output_zip=z,source_sha=SHA,inference_fingerprint="d"*64,
        seeds=SEEDS,prompts=PROMPTS,reuse=False))
    bad("P23_ZIP_MUST_SHARE_REPORT_ROOT",lambda:export_runall_evidence(
        report_path=r,output_zip=root/"child"/"p23-runall-acceptance.zip",source_sha=SHA,
        inference_fingerprint=FP,seeds=SEEDS,prompts=PROMPTS,reuse=False))
    bad("P23_REUSE_FLAG_INVALID",lambda:export_runall_evidence(
        report_path=r,output_zip=z,source_sha=SHA,inference_fingerprint=FP,
        seeds=SEEDS,prompts=PROMPTS,reuse="no"))
    x=copy.deepcopy(report)
    x["status"]="PENDING"
    setreport(x)
    bad("P23_GPU_RENDER_NOT_VERIFIED",lambda:run())
    x=copy.deepcopy(report);x["images"][1]["gpu"]=0;setreport(x)
    bad("P23_GPU_DISTRIBUTION_INVALID",lambda:run())
    x=copy.deepcopy(report);x["images"][0]["sha256"]="0"*64;setreport(x)
    bad("P23_IMAGE_SHA256_MISMATCH",lambda:run())
    x=copy.deepcopy(report);x["images"][0]["prompt"]="wrong";setreport(x)
    bad("P23_PROMPT_OR_SEED_MISMATCH",lambda:run())
    x=copy.deepcopy(report);x["images"][1]["file"]=files[0]["file"];setreport(x)
    bad("P23_IMAGE_SHA256_MISMATCH",lambda:run())
    x=copy.deepcopy(report);x["images"][1]["sha256"]=files[0]["sha256"];x["images"][1]["file"]=files[0]["file"];setreport(x)
    bad("P23_DUPLICATE_IMAGE_OUTPUT",lambda:run())
    x=copy.deepcopy(report);x["images"][0]["file"]=str(root/"other.png");setreport(x)
    bad("P23_UNSAFE_OR_MISSING_EVIDENCE",lambda:run())
    x=copy.deepcopy(report);x["images"][0]["file"]=str(Path(temp).parent/"outside.png");setreport(x)
    bad("P23_IMAGE_PATH_OUTSIDE_OUTPUT_ROOT",lambda:run())
    # Symlink checkpoint must not be used as evidence input.
    with tempfile.TemporaryDirectory() as outside:
        linked=root/"linked.png"
        linked.symlink_to(files[0]["file"])
        x=copy.deepcopy(report);x["images"][0]["file"]=str(linked);setreport(x)
        bad("P23_IMAGE_PATH_OUTSIDE_OUTPUT_ROOT",lambda:run())
    # Unsupported 512x512 PNG may never appear as successful 1024x1024 proof.
    small=root/"small.png"
    Image.new("RGB",(512,512),(1,2,3)).save(small)
    x=copy.deepcopy(report);x["images"][0]["file"]=str(small)
    x["images"][0]["sha256"]=hashlib.sha256(small.read_bytes()).hexdigest()
    setreport(x)
    bad("P23_PNG_RESOLUTION_MISMATCH",lambda:run())
    # Failures may not clobber a previous validated ZIP.
    assert z.is_file() and zipfile.is_zipfile(z)
print("KAGGLE_RUN_ALL_CPU_SYNTHETIC_PASS optional_defaults six_cells nonblocking monitor_finite zip_SHA256 two_PNG provenance_failclosed reuse_marked")

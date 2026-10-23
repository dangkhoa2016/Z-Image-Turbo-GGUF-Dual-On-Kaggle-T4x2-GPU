# Reconstruct audited upstream vendor packages using exact wheel and file-tree SHA256.
# Source remains GitHub; model and support weights remain separately attached inputs.
import os, subprocess, sys, importlib.util
subprocess.run([sys.executable,str(PROJECT/"scripts"/"bootstrap_vendor.py")],check=True)
VENDOR_PATHS=[f"production-system/{name}" for name in
 ("vendor-shim","vendor-hub128","vendor-diffusers041","vendor-torchao015","vendor-gguf")]
assert all((PROJECT / path).is_dir() for path in VENDOR_PATHS)
# Project-local pinned vendor imports take precedence in subprocesses and future kernels.
VENDORS=[str(PROJECT/path) for path in VENDOR_PATHS]
os.environ["PYTHONPATH"]=os.pathsep.join(VENDORS + ([os.environ["PYTHONPATH"]] if os.environ.get("PYTHONPATH") else []))
subprocess.run([sys.executable,str(PROJECT/"scripts"/"verify_vendor_runtime.py")],check=True,env=os.environ.copy())
required=("fastapi","uvicorn","safetensors","transformers","accelerate","httpx","torch")
missing=[package for package in required if importlib.util.find_spec(package) is None]
assert not missing, f"Required runtime packages not installed: {missing}. Provision compatible pinned dependencies before GPU run."
gpu_probe = subprocess.run([sys.executable,'-c',"import torch; assert torch.cuda.device_count()==2; print([torch.cuda.get_device_name(i) for i in range(2)])"],capture_output=True,text=True,timeout=35)
assert gpu_probe.returncode == 0, gpu_probe.stderr
print('TWO_GPUS',gpu_probe.stdout.strip())
os.environ["HF_HUB_OFFLINE"]="1"
os.environ["TRANSFORMERS_OFFLINE"]="1"
print("PREFLIGHT_READY", gpu_probe.stdout.strip())

subprocess.run([sys.executable,str(PROJECT/'scripts/validate_gpu_runtime_imports.py')],check=True,env=os.environ.copy(),timeout=150)
print('GPU_RUNTIME_IMPORT_SMOKE_PASS',flush=True)

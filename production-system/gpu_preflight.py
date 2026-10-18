#!/usr/bin/env python3
"""Read-only Kaggle T4x2 GPU preflight; does not launch inference."""
import argparse,importlib.metadata as im,json,os,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser()
 p.add_argument("--expect-gpu",action="store_true",help="Fail closed unless 2 T4 visible")
 p.add_argument("--manifest",help="Validate a REAL verified dynamic manifest")
 args=p.parse_args()
 checks={}
 def ck(name,ok,detail=None):
  checks[name]={"pass":bool(ok),"detail":detail}
 model=json.loads((ROOT/"manifests/model.json").read_text())
 support=json.loads((ROOT/"manifests/support.json").read_text())
 ck("root_exists",ROOT.is_dir())
 ck("model_file_present",Path(model["gguf_path"]).is_file())
 ck("support_files_present",Path(support["support_root"]).is_dir())
 ck("expected_q6k",model.get("variation")=="q6-k")
 vendor_dirs=[ROOT/"production-system"/n for n in ("vendor-shim","vendor-hub128","vendor-diffusers041","vendor-torchao015","vendor-gguf")]
 vendor_env=os.environ.copy()
 vendor_env["PYTHONPATH"]=os.pathsep.join([str(x) for x in vendor_dirs]+([vendor_env["PYTHONPATH"]] if vendor_env.get("PYTHONPATH") else []))
 verifier=ROOT/"scripts"/"verify_vendor_runtime.py"
 try:
  v=subprocess.run([sys.executable,str(verifier)],env=vendor_env,capture_output=True,text=True,timeout=90)
  ck("vendored_runtime_identity",v.returncode==0,(v.stdout if v.returncode==0 else v.stderr)[-1000:])
 except Exception as e:ck("vendored_runtime_identity",False,type(e).__name__+": "+str(e))
 try:
  deps=subprocess.run([sys.executable,"-c","import importlib.metadata as m;print(m.version('diffusers'))"],env=vendor_env,capture_output=True,text=True,timeout=20)
  d=deps.stdout.strip() if deps.returncode==0 else None
 except Exception:d=None
 ck("diffusers_0_41_0",d=="0.41.0",d)
 try:
  import torch
  ck("torch_cuda_build",torch.version.cuda is not None,str(torch.__version__))
  devices=torch.cuda.device_count()
  names=[torch.cuda.get_device_name(i) for i in range(devices)] if torch.cuda.is_available() else []
  ck("two_T4_devices",devices==2 and all("T4" in n for n in names),names)
 except Exception as e:ck("two_T4_devices",False,type(e).__name__+": "+str(e))
 smi=shutil.which("nvidia-smi")
 if smi:
  try:
   gp=subprocess.run([smi,"--query-gpu=index,name,memory.total","--format=csv,noheader"],
    capture_output=True,text=True,timeout=15,check=True)
   ck("nvidia_smi_two_T4",len(gp.stdout.strip().splitlines())==2 and all("T4" in x for x in gp.stdout.strip().splitlines()),gp.stdout.strip())
  except Exception as e:ck("nvidia_smi_two_T4",False,str(e))
 else:ck("nvidia_smi_two_T4",False,"not installed")
 if args.manifest:
  try:
   from dynamic_manifest import read_manifest
   obj=read_manifest(args.manifest,allow_mock=False)
   ck("real_dynamic_manifest",obj.get("test_only") is False and bool(obj.get("entries")),str(len(obj["entries"])))
  except Exception as e:ck("real_dynamic_manifest",False,type(e).__name__+": "+str(e))
 all_pass=all(x["pass"] for x in checks.values())
 status="GPU_PREFLIGHT_PASS" if all_pass else "GPU_PREFLIGHT_BLOCKED"
 print(json.dumps({"status":status,"checks":checks,"requested_gpu":args.expect_gpu,"inference_started":False},indent=2,sort_keys=True))
 # expect-gpu fails, but CPU audit mode can produce a report without error while showing blockers
 if args.expect_gpu and not all_pass:return 2
 return 0
if __name__=="__main__":sys.exit(main())

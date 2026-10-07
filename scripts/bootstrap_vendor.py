#!/usr/bin/env python3
"""Offline-capable SHA256-locked wheel reconstruction for the audited Kaggle runtime."""
import argparse, hashlib, os, platform, subprocess, sys, tempfile, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/"production-system"
LOCK={
 "vendor-diffusers041":("diffusers","0.41.0","ea8918b7dfd92ce793b6db689a551b8cd25d52c6c0fcd3ade0706a5fd2a25990","72ac24529e14780a4bae6fe5c77e6a8dca83d99109dd4293e4bf18a1008fd6bb",1049),
 "vendor-hub128":("huggingface_hub","1.28.0","58a8bacb03072edfc38067065e9dc24bbb34805410fcd36a1632de0b329660bb","378ffe0a4512d769bb22cec63829111ead8edb3e3025e479381dd8ee17bd2b18",186),
 "vendor-torchao015":("torchao","0.15.0","1cbe813201314ba6329a650a76944502f3e8ec4b1b44523f3f48676810d8d1f6","2938bd2dc06cafb99069baf85e4157d1b3ec93e3aab1ed2442d6aaf61e9ee3e0",422),
 "vendor-gguf":("gguf","0.17.1","7bc5aa7eeb1931f7d39b48fdc5b38fda6b294b9dca75cf607ac69557840a3943","e8cb59809d0b267e2abc078611333f6d59693190180b96ef76f4872534b9dcea",18)}
def digest(f):return hashlib.sha256(f.read_bytes()).hexdigest()
def tree(root):
 files=sorted(p for p in root.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix not in (".pyc", ".pyo"))
 h=hashlib.sha256()
 for f in files:h.update(str(f.relative_to(root)).encode()+b"\0"+bytes.fromhex(digest(f)))
 return len(files),h.hexdigest()
def checked_wheel(wheel,pkg,ver,expected):
 if digest(wheel)!=expected:raise RuntimeError("WHEEL_SHA256_MISMATCH:"+wheel.name)
 with zipfile.ZipFile(wheel) as z:
  metadata=f"{pkg}-{ver}.dist-info/METADATA"
  if metadata not in z.namelist():raise RuntimeError("DIST_METADATA_MISSING")
  data=z.read(metadata).decode()
  if f"Name: {pkg.replace('_','-')}" not in data and f"Name: {pkg}" not in data:raise RuntimeError("DIST_NAME_MISMATCH")
  if f"Version: {ver}" not in data:raise RuntimeError("DIST_VERSION_MISMATCH")
def populate(stage,wheel,pkg,ver,expected_tree,count):
 dest=stage
 dist=f"{pkg}-{ver}.dist-info"
 with zipfile.ZipFile(wheel) as z:
  for item in z.infolist():
   if item.is_dir():continue
   name=Path(item.filename)
   if name.is_absolute() or ".." in name.parts:raise RuntimeError("UNSAFE_WHEEL_PATH")
   if not (item.filename.startswith(pkg+"/") or item.filename.startswith(dist+"/")):continue
   out=dest/name;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(z.read(item))
  # License and metadata retained within isolated vendor prefix.
 if tree(dest/pkg)!=(count,expected_tree):raise RuntimeError("VENDOR_TREE_MISMATCH")
 from importlib.metadata import Distribution
 distribution=Distribution.at(str(dest/dist))
 if distribution.version!=ver:raise RuntimeError("METADATA_VERSION_MISMATCH")
DIST_HASH={
 "diffusers":"1d4524b41155c48165cbba255a933bf1295bc4a2f759e64322e6697c122a030b",
 "huggingface_hub":"a1b4a60771137661a2df17921843b2fc9c574747a26e1d7e5a74abd19dde3769",
 "torchao":"0de5e448164cdb6f610bee2ded833be9245fe1f9e3a87b3393336713a22713a9",
 "gguf":"b2fd2f2dfb979a5de3f56f16699baadab82529dba3b0928212fdc55fc2337164"}
def verify(dest,pkg,ver,expected_tree,count):
 if tree(dest/pkg)!=(count,expected_tree):raise RuntimeError("EXISTING_VENDOR_INVALID")
 from importlib.metadata import Distribution
 dist=dest/f"{pkg}-{ver}.dist-info"
 if not dist.is_dir() or Distribution.at(str(dist)).version!=ver:raise RuntimeError("METADATA_MISSING_OR_WRONG")
 if tree(dist)[1]!=DIST_HASH[pkg]:raise RuntimeError("METADATA_SHA256_MISMATCH")
 if not any("LICENSE" in p.name for p in dist.rglob("*") if p.is_file()):raise RuntimeError("LICENSE_MISSING")
def main():
 p=argparse.ArgumentParser();p.add_argument("--wheel-dir",type=Path);args=p.parse_args()
 if platform.system()!="Linux" or platform.machine()!="x86_64":raise RuntimeError("Only validated Linux x86_64 supported")
 if not (ROOT/"vendor-shim"/"sitecustomize.py").is_file():raise RuntimeError("SHIM_MISSING")
 for name,(pkg,ver,sha,expected_tree,count) in LOCK.items():
  dest=ROOT/name
  if dest.exists():
   verify(dest,pkg,ver,expected_tree,count);print("VERIFIED",name,ver,flush=True);continue
  with tempfile.TemporaryDirectory(prefix="zimage-wheel-") as t:
   wheel_dir=args.wheel_dir or Path(t)
   if args.wheel_dir:
    matches=[x for x in wheel_dir.glob(f"{pkg}-{ver}-*.whl") if digest(x)==sha]
    if len(matches)!=1:raise RuntimeError("OFFLINE_WHEEL_MISSING:"+name)
    wheel=matches[0]
   else:
    subprocess.run([sys.executable,"-m","pip","download","--no-deps","--only-binary=:all:","--dest",str(wheel_dir),f"{pkg}=={ver}"],check=True)
    matches=list(wheel_dir.glob("*.whl"))
    if len(matches)!=1:raise RuntimeError("WHEEL_NOT_UNIQUE")
    wheel=matches[0]
   checked_wheel(wheel,pkg,ver,sha)
   with tempfile.TemporaryDirectory(dir=ROOT,prefix=".vendor-stage-") as stage:
    candidate=Path(stage)/name;candidate.mkdir()
    populate(candidate,wheel,pkg,ver,expected_tree,count)
    verify(candidate,pkg,ver,expected_tree,count)
    os.rename(candidate,dest)
   verify(dest,pkg,ver,expected_tree,count)
   print("INSTALLED_VERIFIED",name,ver,flush=True)
 print("VENDOR_BOOTSTRAP_PASS")
if __name__=="__main__":main()

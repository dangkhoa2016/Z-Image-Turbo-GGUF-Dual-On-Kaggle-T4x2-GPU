import subprocess,sys,importlib.metadata as md,json
model=Path("/kaggle/input/models/dangkhoa2016/unsloth-z-image-turbo-gguf/gguf/q6-k/1/z-image-turbo-Q6_K.gguf")
support=Path("/kaggle/input/datasets/dangkhoa2016/z-image-turbo-diffusers-support-components/z-image-turbo-diffusers-support")
assert model.is_file(),f"Attach Kaggle model first: {model}"
assert all((support/component).is_dir() for component in ("text_encoder", "tokenizer", "vae")), (
    "Missing Kaggle support dataset or required text_encoder/tokenizer/vae directory: " + str(support)
)
gpus=subprocess.check_output(["nvidia-smi","-L"],text=True)
assert gpus.count("Tesla T4")>=2,"Switch Kaggle accelerator to T4 ×2"
print("GPU_T4X2_READY",gpus)
# P2.3: fail early if both local checkpoint copies will not fit.
# The notebook deliberately opts into verified staging for Qwen3 + GGUF;
# production library defaults are untouched. An explicit GGUF mode override
# ("direct" or "auto") can disable the extra GGUF 5.9 GB copy.
import os, shutil
GGUF_P23_REQUESTED=os.environ.get("ZIMAGE_GGUF_SOURCE_MODE","local")
assert GGUF_P23_REQUESTED in ("local","auto","direct"), "Unsupported GGUF source mode"
QWEN3_ATTACHED_FILES = (
    "model-00001-of-00003.safetensors",
    "model-00002-of-00003.safetensors",
    "model-00003-of-00003.safetensors",
    "config.json", "generation_config.json", "model.safetensors.index.json",
)
assert all((support / "text_encoder" / name).is_file() for name in QWEN3_ATTACHED_FILES), (
    "Missing Qwen3 shard/config; reattach the support dataset"
)
QWEN3_STAGE_BYTES=sum((support / "text_encoder" / name).stat().st_size
                      for name in QWEN3_ATTACHED_FILES)
GGUF_STAGE_BYTES=model.stat().st_size if GGUF_P23_REQUESTED=="local" else 0
P23_DISK_RESERVE_BYTES=3*1024**3  # staging reserve on ephemeral /tmp
P23_WORKING_RESERVE_BYTES=1024**3     # preserve output ZIPs, logs, source checkout
P23_STAGE_FREE_BYTES=shutil.disk_usage("/tmp").free
P23_DISK_FREE_BYTES=shutil.disk_usage("/kaggle/working").free
P23_REQUIRED_BYTES=QWEN3_STAGE_BYTES + GGUF_STAGE_BYTES + P23_DISK_RESERVE_BYTES
print("P23_FRESH_DISK_PREFLIGHT",
      json.dumps({"stage_root":str(ZIMAGE_MODEL_STAGE_PARENT),
                  "tmp_free_gib":round(P23_STAGE_FREE_BYTES/1024**3,2),
                  "tmp_required_gib":round(P23_REQUIRED_BYTES/1024**3,2),
                  "working_free_gib":round(P23_DISK_FREE_BYTES/1024**3,2),
                  "working_reserve_gib":1,
                  "qwen3_bytes":QWEN3_STAGE_BYTES,"gguf_bytes":GGUF_STAGE_BYTES,
                  "gguf_mode":GGUF_P23_REQUESTED},sort_keys=True), flush=True)
assert P23_STAGE_FREE_BYTES >= P23_REQUIRED_BYTES, (
    "P23_INSUFFICIENT_TMP_DISK: verified Qwen3/GGUF model staging needs "
    +str(round(P23_REQUIRED_BYTES/1024**3,2))+" GiB free under /tmp; available "
    +str(round(P23_STAGE_FREE_BYTES/1024**3,2))+
    " GiB. Stop before loading any GPU model; review the disk layout."
)
# If both paths share a filesystem, reserve both staging and output budgets.
if os.stat('/tmp').st_dev == os.stat('/kaggle/working').st_dev:
    assert P23_STAGE_FREE_BYTES >= P23_REQUIRED_BYTES + P23_WORKING_RESERVE_BYTES, (
        "P23_SHARED_TMP_WORKING_DISK_INSUFFICIENT")
assert P23_DISK_FREE_BYTES >= P23_WORKING_RESERVE_BYTES, (
    "P23_INSUFFICIENT_WORKING_DISK_FOR_OUTPUTS: need 1 GiB for source/logs/PNG/ZIP"
)
print("MODEL_INPUT_ATTACHED:", model)
print("MODEL_VARIATION_VERSION:", "GGUF / q6-k / 1")
print("SUPPORT_DATASET_ATTACHED:", support)
print("SUPPORT_COMPONENTS:", "text_encoder, tokenizer, vae")
print("GGUF_BYTES",model.stat().st_size)
for key in ("torch","transformers","diffusers","huggingface-hub","torchao","gguf","safetensors","fastapi","uvicorn"):
    try: print(key,md.version(key))
    except md.PackageNotFoundError:print(key,"MISSING")
print("NOTE: Tensor library versions must match the validated runtime. Install missing packages in the next cell; do not randomly upgrade torch.")

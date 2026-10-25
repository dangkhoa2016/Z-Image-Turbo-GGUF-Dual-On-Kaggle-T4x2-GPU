# Runtime Compatibility & Launch Guide

> 🌐 Language / Ngôn ngữ: **English** | [Tiếng Việt](runtime-compatibility.vi.md)

## Validated reference environment

Z-Image-Turbo GGUF Q6_K has been exercised on **Kaggle Tesla T4 ×2** using a bounded GPU0 prompt-encoding phase and independent GPU0/GPU1 inference workers. The current revision must independently demonstrate authenticated browser submission, new 1024 × 1024 PNG output, SHA256 integrity, and View/Download. See the [validation index](evidence-index.md) for acceptance requirements.

## Launch on Kaggle

1. Select **GPU T4 ×2** and enable Internet access for the initial setup.
2. Attach the Kaggle GGUF model `dangkhoa2016/unsloth-z-image-turbo-gguf`, variant `q6-k`, version 1, and the dataset `dangkhoa2016/z-image-turbo-diffusers-support-components`.
3. Open [the showcase notebook](../notebooks/kaggle-dual-gpu-production-demo.ipynb). Run its cells in order to check the inputs, start API/Studio and the GPU queue consumer, then publish the two HTTPS websites.
4. Use Studio's generated demo login, submit a prompt, and verify the job, artifact and image retrieval. Check both GPUs with separate jobs when demonstrating dual inference.

## Environment compatibility

The repo supplies source and launch orchestration; it deliberately does not distribute model weights, private job artifacts or runtime databases. Rebuilding a runtime requires compatible GPU/PyTorch/Diffusers/Transformers components and the model inputs above. GPU acceptance is established through a Kaggle execution documented for the exact source SHA on the [GitHub Release](https://github.com/dangkhoa2016/Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/releases/tag/v1.0.0). GitHub's repository audit checks structure and syntax, and additionally runs the CPU contract/security suite (`requirements-ci.txt` + `python scripts/run_cpu_tests.py`); it does not execute GPU inference.

## Dependency lock

The machine-readable lock is [`manifests/runtime-compatibility.json`](../manifests/runtime-compatibility.json).

- **Verified now (CPU):** the four SHA256-locked vendor wheels — Diffusers
  0.41.0, Hugging Face Hub 1.28.0, TorchAO 0.15.0, GGUF 0.17.1 — with their
  wheel, extracted-tree and dist-info hashes, plus the CPU/CI reference set in
  [`requirements-ci.txt`](../requirements-ci.txt).
- **GPU validation:** confirm PyTorch, CUDA, Transformers, Accelerate and Python versions on the actual T4 ×2 host before publishing compatibility results.
- `requirements.txt` remains an unpinned minimum set and now includes `numpy`,
  which `safetensors.torch.save_file` needs at runtime (`encode_batch_gpu.py`,
  `encode_batch_cpu_mock.py`). Do not upgrade PyTorch on an accepted GPU runtime
  without compatibility evidence.

## Source checkout policy

The demo notebook obtains its working copy through `scripts/source_checkout.py`,
which is fail-closed: it refuses to overwrite a non-empty directory
(`SOURCE_TREE_DIRTY`), an unexpected remote, or a revision mismatch
(`SOURCE_SHA_MISMATCH`), and it never runs `git reset --hard`. A new Kaggle session should use a verified published commit SHA or release tag.

## Verification

Run the CPU contract suite using `python scripts/run_cpu_tests.py`. GPU and browser acceptance checks must run on the current Kaggle session before claiming runtime verification.

## Further reading

[Deployment profile](deployment-profile.md) · [Architecture](architecture.md) · [Kaggle guide](kaggle.md) · [Technical evidence](evidence-index.md)

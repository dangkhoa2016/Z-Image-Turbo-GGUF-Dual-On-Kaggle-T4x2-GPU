# Audited vendor dependencies for Kaggle

> 🌐 Language / Ngôn ngữ: **English** | [Tiếng Việt](vendor-dependencies.vi.md)

The repository is the source of project code. On Kaggle, the notebook clones this repository and runs `python3 scripts/bootstrap_vendor.py`. The script downloads SHA256-pinned third-party wheels from PyPI (internet required) or consumes previously downloaded wheels with `--wheel-dir PATH`. It verifies the complete wheel SHA256, extracted package tree, and upstream distribution metadata, including licenses.

Audited versions: Diffusers 0.41.0 (Apache-2.0), Hugging Face Hub 1.28.0 (Apache-2.0), TorchAO 0.15.0 (BSD-3-Clause) and GGUF 0.17.1 (MIT). The project-specific `vendor-shim/sitecustomize.py` is maintained independently. The package directories are generated runtime outputs and **must not be committed** as project-owned MIT source.

Native TorchAO wheel is platform-specific; the audited artifact is Linux x86_64 cp310-abi3. It is not a general cross-platform wheel guarantee. Version metadata from `importlib.metadata` must be read from the explicit vendored distribution paths, rather than blindly from system site-packages.

The GGUF model and text-encoder/VAE support components are separate model data attachments, not source. This first public release is a demonstrator, not a production-hosted service. GPU Run All and browser acceptance require revision-specific evidence on the [GitHub Release](https://github.com/dangkhoa2016/Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/releases/tag/v1.0.0); the CPU-verified dependency matrix does not guarantee cross-runtime GPU compatibility. Published GitHub Actions CI exercises static and CPU contract tests, not CUDA inference.

[Tiếng Việt](vendor-dependencies.vi.md) · [English](vendor-dependencies.md)

**Compatibility gate:** PyTorch, Transformers and Accelerate versions from the previously accepted T4×2 runtime have not yet been established. Do not pin them from this CPU-only audit machine. GPU preflight and worker launch now require the vendor identity gate.

# Z-Image-Turbo GGUF Dual on Kaggle T4 ×2

[![Repository audit](https://github.com/dangkhoa2016/Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/actions/workflows/repository-audit.yml/badge.svg)](https://github.com/dangkhoa2016/Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/actions/workflows/repository-audit.yml)
[![License MIT](https://img.shields.io/badge/Project%20License-MIT-2ea44f)](LICENSE)
[![Model Apache](https://img.shields.io/badge/Model%20License-Apache--2.0-1565c0)](LICENSE-NOTES.md)
[![Language](https://img.shields.io/badge/Docs-English%20%7C%20Ti%E1%BA%BFng%20Vi%E1%BB%87t-835df1)](README.vi.md)

![Platform](https://img.shields.io/badge/Platform-Kaggle-20BEFF?logo=kaggle&logoColor=white)
![GPU](https://img.shields.io/badge/Accelerator-NVIDIA%20T4%20%C3%97%202-76B900?logo=nvidia&logoColor=white)
![Model](https://img.shields.io/badge/Model-Z--Image--Turbo-3459c7)
![Quantization](https://img.shields.io/badge/GGUF-Q6__K-7350a2)
![Output](https://img.shields.io/badge/PNG-1024%20%C3%97%201024-4f687b)

![API](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white)
![Studio](https://img.shields.io/badge/Studio-Vue%203-4FC08D?logo=vuedotjs&logoColor=white)
![Queue](https://img.shields.io/badge/Queue-SQLite-0a5885?logo=sqlite&logoColor=white)
![Tunnel](https://img.shields.io/badge/Tunnel-Cloudflare-ef7f1a?logo=cloudflare&logoColor=white)

[![Prior GPU evidence](https://img.shields.io/badge/Dual--GPU%20Evidence-PASS-22863a)](docs/evidence-index.md)
[![Browser E2E](https://img.shields.io/badge/Browser--to--PNG-PASS-22863a)](docs/evidence-index.md)
[![Kaggle Notebook](https://img.shields.io/badge/Kaggle-Launch%20Notebook-20BEFF)](notebooks/kaggle-dual-gpu-production-demo.ipynb)
[![Gallery Showcase](https://img.shields.io/badge/Gallery-Static%20Showcase-506c91)](docs/deployment-profile.md)

> 🌐 Language / Ngôn ngữ: **English** | [Tiếng Việt](README.vi.md)

## Overview
Z-Image-Turbo GGUF Q6_K on **two Tesla T4 GPUs**; bounded GPU0 prompt encoding, independent GPU0/GPU1 inference workers, authenticated Vue Studio v3, private PNG receipts, and two independent Cloudflare HTTPS websites.

## Quick start
1. [Open Kaggle notebook](notebooks/kaggle-dual-gpu-production-demo.ipynb).
2. Enable GPU T4×2 and Internet; attach model `dangkhoa2016/unsloth-z-image-turbo-gguf`, variation `q6-k`, version 1.
3. Attach support dataset `dangkhoa2016/z-image-turbo-diffusers-support-components`.
4. Run notebook cells sequentially. The Studio cell prints its demo-only login; private backend credentials are never displayed.
5. Open the Studio and generate images; View/Download PNG, total job elapsed seconds and SVG loading have been previously accepted.

## Two public websites
- Static gallery: the **original 48-image and 122-image** benchmark galleries need to be attached separately under `/kaggle/working/gallery-48` and `/kaggle/working/gallery-122`. They are **not currently available**. The 32-image Pilot32 quality-review set is **not** a replacement.
- Studio: a password-protected Cloudflare HTTPS gateway; NEVER tunnel the private API directly.

## Verification and launch
The system has been demonstrated with real T4×2 GPU inference and browser-to-PNG delivery on the reference Kaggle environment. See the [technical evidence](docs/evidence-index.md) for the recorded checks. The showcase notebook provides the launch workflow for a new session; model inputs and library compatibility should be verified on that session. See [runtime compatibility](docs/runtime-compatibility.md) and the [deployment profile](docs/deployment-profile.md).

## Documentation
[Architecture](docs/architecture.md) · [Kaggle](docs/kaggle.md) · [API](docs/api.md) · [Benchmarks](docs/benchmark.md) · [Runtime compatibility](docs/runtime-compatibility.md) · [Deployment profile](docs/deployment-profile.md) · [Engineering overview](docs/engineering-overview.md) · [License notes](LICENSE-NOTES.md).

## Licensing
© 2026 Đăng Khoa <i.am@dangkhoa.dev>. MIT for project-authored code and text **only**; [upstream model Apache-2.0](LICENSE-NOTES.md). Model weights, user images, tokens, local SQLite data and gallery assets are not committed. This is a demo, not production GO.

## Additional references
[Evidence index](docs/evidence-index.md) · [Troubleshooting](docs/troubleshooting.md) · [Changelog](CHANGELOG.md) · [Project contract](PROJECT-CONTRACT.md) · [Demo snapshot notes](RELEASE_NOTES_v1.0.0-demo.md).

# Z-Image-Turbo GGUF Dual on Kaggle T4 ×2

[![Repository audit](https://github.com/dangkhoa2016/Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/actions/workflows/repository-audit.yml/badge.svg)](https://github.com/dangkhoa2016/Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/actions/workflows/repository-audit.yml)
![Python](https://img.shields.io/badge/Python-3.13-blue) ![Kaggle](https://img.shields.io/badge/Kaggle-T4%C3%972-20BEFF) [![MIT](https://img.shields.io/badge/Project-MIT-green)](LICENSE) [![Apache](https://img.shields.io/badge/Model-Apache--2.0-orange)](LICENSE-NOTES.md)

> 🌐 Language / Ngôn ngữ: **English** | [Tiếng Việt](README.vi.md)

## Overview
Z-Image-Turbo GGUF Q6_K on **two Tesla T4 GPUs**; bounded GPU0 prompt encoding, independent GPU0/GPU1 inference workers, authenticated Vue Studio v3, private PNG receipts, and two independent Cloudflare HTTPS websites.

## Quick start
1. [Open Kaggle notebook](notebooks/kaggle-dual-gpu-production-demo.ipynb).
2. Enable GPU T4×2 and Internet; attach model `dangkhoa2016/unsloth-z-image-turbo-gguf`, variation `q6-k`, version 1.
3. Attach support dataset `dangkhoa2016/z-image-turbo-diffusers-support-components`.
4. Run notebook cells sequentially. The Studio cell prints its demo-only login; internal service keys remain private.
5. Open the Studio and generate images; View/Download PNG, total job elapsed seconds and SVG loading have been previously accepted.

## Two public websites
- Static gallery: the **original 48-image and 122-image** benchmark galleries need to be attached separately under `/kaggle/working/gallery-48` and `/kaggle/working/gallery-122`. They are **not currently available**. The 32-image Pilot32 quality-review set is **not** a replacement.
- Studio: a password-protected Cloudflare HTTPS gateway; NEVER tunnel the private API directly.

## Reproducibility status
The earlier Kaggle runtime demonstrated dual-GPU inference and real browser-to-PNG generation. **This rewritten repo and notebook have not yet passed a clean Kaggle replay**. Large third-party vendored dependencies are not included in the rewritten source tree; see [reproducibility](docs/reproducibility.md).

## Documentation
[Architecture](docs/architecture.md) · [Kaggle](docs/kaggle.md) · [API](docs/api.md) · [Benchmarks](docs/benchmark.md) · [Reproducibility](docs/reproducibility.md) · [Limitations](docs/limitations.md) · [Development history](docs/development-history.md) · [License notes](LICENSE-NOTES.md).

## Licensing
© 2026 Đăng Khoa <i.am@dangkhoa.dev>. MIT for project-authored code and text **only**; [upstream model Apache-2.0](LICENSE-NOTES.md). Model weights, user images, tokens, local SQLite data and gallery assets are not committed. This is a demo, not production GO.

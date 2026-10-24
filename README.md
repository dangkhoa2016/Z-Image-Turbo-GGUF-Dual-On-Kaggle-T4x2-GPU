# Z-Image-Turbo GGUF Q6_K — Dual-GPU Image Generation on Kaggle

[![Repository audit](https://github.com/dangkhoa2016/Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/actions/workflows/repository-audit.yml/badge.svg)](https://github.com/dangkhoa2016/Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/actions/workflows/repository-audit.yml)
[![Technical preview](https://img.shields.io/badge/Release-v1.0.0-2864b4)](https://github.com/dangkhoa2016/Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/releases/tag/v1.0.0)
[![License: MIT](https://img.shields.io/badge/Project-MIT-2ea44f)](LICENSE)
[![Upstream model: Apache 2.0](https://img.shields.io/badge/Upstream%20model-Apache--2.0-1565c0)](LICENSE-NOTES.md)
[![Kaggle T4 x2](https://img.shields.io/badge/Kaggle-Tesla%20T4%20%C3%97%202-20beff)](docs/runtime-compatibility.md)
[![GGUF Q6_K](https://img.shields.io/badge/GGUF-Q6__K-7350a2)](manifests/model.json)

**Language:** English · [Tiếng Việt](README.vi.md)

**Release:** [v1.0.0](https://github.com/dangkhoa2016/Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/releases/tag/v1.0.0) · **Platform:** Kaggle, NVIDIA Tesla T4 ×2 · **Output:** 1024 × 1024 PNG

> **An evidence-driven AI image-generation demo, not a hosted production service.** This project brings Z-Image-Turbo in GGUF Q6_K format to two Kaggle Tesla T4 GPUs, with bounded GPU0 prompt encoding, independently scheduled GPU0/GPU1 inference workers, an authenticated image-generation Studio, and reviewable benchmark galleries. The repository provides the source, a published Kaggle launch notebook, measured GPU/browser evidence, and a 170-image Release gallery for independent review.

**Explore:** [System architecture](#system-architecture) · [Measured evidence](#measured-evidence-and-verification-status) · [170-image galleries](#170-image-release-galleries) · [Run on Kaggle](#run-the-demo-on-kaggle) · [Source layout](#repository-guide) · [Security and limitations](#security-and-limitations)

## Image showcase · existing approved Release gallery

| Sample 010 | Sample 011 | Sample 013 | Sample 027 |
|:---:|:---:|:---:|:---:|
| ![Published quality-gallery sample 010](assets/showcase/pqt_v1_010.webp) | ![Published quality-gallery sample 011](assets/showcase/pqt_v1_011.webp) | ![Published quality-gallery sample 013](assets/showcase/pqt_v1_013.webp) | ![Published quality-gallery sample 027](assets/showcase/pqt_v1_027.webp) |

*Four compact WebP thumbnails copied without modification from the existing watermarked v1.0.0 gallery Release. These are gallery previews, **not** the notebook's two independently generated GPU proof images. [Inspect the 170-image Release gallery](https://github.com/dangkhoa2016/Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/releases/tag/v1.0.0) for prompts, metadata, and review status.*

## Why this project exists

Running a quantized image-generation model on two memory-constrained Tesla T4 GPUs involves more than making a model load: prompt encoding must fit the available memory; GPU workers must consume real, distinguishable jobs; generated images need reliable ownership and integrity checks; and the browser demonstration must make queue and generation states observable. This repository packages the source, operational entry points, automated CPU checks, and archived acceptance records around those engineering questions.

The intended audience is AI/ML engineers reviewing **how a Kaggle dual-GPU demonstration is assembled and verified**. Parallel workers demonstrate independent GPU execution; this does not imply that a single image runs twice as fast.

## What is included

| Area | Implementation and reviewer value |
|---|---|
| Model and hardware | Z-Image-Turbo GGUF **Q6_K** on **Tesla T4 ×2**; model input remains external to the Git repository. |
| Dual-GPU execution | Bounded prompt encoding on **GPU0**, with independent inference workers targeting **GPU0** and **GPU1**; worker identity and GPU activity are recorded in historical acceptance evidence. |
| Job orchestration | SQLite-backed job lifecycle, worker consumption, session-aware recovery and per-job metadata. Queue time and GPU compute time are not treated as equivalent. |
| Authenticated Studio | Vue-based interface and gateway for prompt submission, job states, image preview/download, and displayed elapsed seconds. |
| Artifact integrity | Privately stored generated PNGs with job ownership checks and SHA256 receipts; authenticated image retrieval. |
| Reproducible launch path | The Kaggle notebook checks out a verified Git commit, checks model inputs and both GPUs, prepares verified dependencies, and starts the demo services. |
| Reviewable visuals | **48-image quality gallery** and **122-image test/benchmark gallery**, distributed together as a SHA256-verified, watermarked Release archive. |
| Engineering records | Bilingual guides, runtime manifest, CPU/security checks, and JSON reports that distinguish verified work from unverified claims. |

## System architecture

```text
Kaggle runtime · NVIDIA Tesla T4 ×2

Browser ── HTTPS Quick Tunnel (Studio) ── Authenticated gateway :18789
                                                 │
                                         Private API :18788
                                                 │
                                    SQLite jobs / session state
                                                 │
                                   Bounded prompt encoding
                                             GPU0
                                                 │
                                       GPU job dispatch
                                        /           \
                              Inference worker 0   Inference worker 1
                                 Tesla T4 / GPU0    Tesla T4 / GPU1
                                        \           /
                                    PNG artifacts + SHA256
                                                 │
                                Authenticated View / Download

Browser ── Separate HTTPS Quick Tunnel ── Two independent gallery servers :18881 / :18882
                                            ├─ 48-image quality gallery
                                            └─ 122-image benchmark gallery
```

**Important execution details:** GPU0 participates in both prompt encoding and image inference; it is not a dedicated text-encoder-only device. Independent GPU workers support concurrent workloads, but prompt encoding, VRAM pressure, queueing, and setup can constrain effective throughput. Observed simultaneous utilization is evidence of activity on both GPUs—not proof of linear scaling. The Studio tunnel exposes the authenticated gateway, **never** the private API directly. [Architecture details](docs/architecture.md) · [API endpoints](docs/api.md).

## Measured evidence and verification status

This table intentionally separates archived runtime observations, human-reviewed visual presentation, CI checks, and work still required. Evidence represents the stated session and scope; it is not automatically transferable to a new Kaggle instance.

| Verification area | Recorded result | Source / boundary |
|---|---|---|
| Dual-GPU inference | **PASS — 2/2** completed jobs on workers GPU0/GPU1, private PNG SHA256 receipts verified; both GPUs observed at 100% utilization in the same sample. | [Dual-GPU acceptance, 16 Oct](evidence/dual-gpu-inference-acceptance-2026-10-16.json); a bounded observation, not a scalability benchmark. |
| Browser-to-image | **PASS** for a 1024 × 1024 PNG with View/Download and no reported JavaScript errors. | [Browser acceptance, 16 Oct](evidence/browser-image-generation-acceptance-2026-10-16.json). |
| Existing Studio runtime | **PASS** for authenticated View/Download and previously reviewed prompt fidelity; **5 completed, 1 cancelled** across the recorded Studio outcomes. | [Kaggle/Studio acceptance, 18 Oct](evidence/kaggle-t4x2-studio-acceptance-2026-10-18.json); not a clean notebook replay. |
| Measured GPU phase | Five historical **nine-step diffusion-phase** measurements: **234, 236, 246, 247, 262 seconds** (reported dataset). | [18 Oct record](evidence/kaggle-t4x2-studio-acceptance-2026-10-18.json). These values **exclude** some queue/setup/encoding/saving work; do not present them as end-to-end image time. |
| UI elapsed-time display | **PASS — 6/6** completed rows showed total elapsed seconds in a prior HTTPS Studio review. | [Elapsed-time acceptance](evidence/studio-elapsed-time-acceptance-2026-10-16.json). |
| Public gallery package | **170 PNG = 48 quality + 122 benchmark**, with **40 WebP thumbnails**; the approved *presentation/watermark* is distributed in Release `v1.0.0`. | [Release download](https://github.com/dangkhoa2016/Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/releases/tag/v1.0.0); display approval does not mean 100% prompt-fidelity PASS. |
| Repository audit | **PASS** on the published README-reorganization commit; checks include Python/notebook syntax, bilingual documentation, security and CPU contracts. | [GitHub Actions](https://github.com/dangkhoa2016/Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/actions/workflows/repository-audit.yml). CI is not a GPU run. |

**Reproduction scope:** The published notebook has not yet been end-to-end tested from a fresh Kaggle T4×2 session; the recorded GPU/Studio acceptance applies to the documented reference runtimes. This is a verification boundary for independent reproduction, not an assertion that the demonstrated system is incomplete.

The historical measurements establish that actual image generation was exercised; they do **not** establish a universal per-image speed, a sustained images/hour benchmark, or all-image semantic acceptance. See [benchmark methodology](docs/benchmark.md) and the [evidence index](docs/evidence-index.md).

## 170-image Release galleries

The galleries preserve more than final images: prompts, seeds, worker/runtime information where available, original/retry relationships, status labels and image hashes make the work inspectable instead of relying on a handful of curated thumbnails.

| Collection | Contents | Intended interpretation |
|---|---|---|
| **48-image quality gallery** | **48 PNGs** in the approved quality-gallery collection, with **40 WebP thumbnails** for browsing. | Human-review workflow and visual variety. Original/retry and pending/rejected quality flags must remain visible; not every prompt is declared successful. |
| **122-image test & benchmark gallery** | **122 PNGs** with per-image metadata and recorded execution context. Worker and run details should be read from each item’s included metadata. | Technical workload/evidence gallery—not 122 independently art-directed, quality-approved concepts. |

Both static sites support **English/Vietnamese**, filtering, image detail modals, keyboard navigation, responsive layouts and links between the two galleries. The public release uses the approved watermarked presentation. The original, unwatermarked PNG archive is kept private and is **not** part of this public repository or release.

**Public artifact:** [`zimage-gallery-170-watermarked-public-v1.0.0.tar.gz`](https://github.com/dangkhoa2016/Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/releases/download/v1.0.0/zimage-gallery-170-watermarked-public-v1.0.0.tar.gz)

**SHA256:** `e0240d7bc60314f9e8394b5afd922a330216ecd6b596122e381f0bab3e755997`

**Includes:** the approved 170 PNGs, thumbnails and bilingual gallery presentation. The gallery files are a **Release asset**, not Git-tracked source files or a source-code Kaggle dataset.

To inspect the public galleries locally on Linux/macOS (outside Kaggle inference), download the archive, verify it, and serve its root:

```bash
curl -fL -o zimage-gallery-170-watermarked-public-v1.0.0.tar.gz \
  https://github.com/dangkhoa2016/Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/releases/download/v1.0.0/zimage-gallery-170-watermarked-public-v1.0.0.tar.gz
printf '%s  %s\n' \
  e0240d7bc60314f9e8394b5afd922a330216ecd6b596122e381f0bab3e755997 \
  zimage-gallery-170-watermarked-public-v1.0.0.tar.gz | sha256sum -c -
tar -xzf zimage-gallery-170-watermarked-public-v1.0.0.tar.gz
find . -name index.html -print
# Serve the extracted directory containing the gallery HTML files.
python3 -m http.server 8080 --bind 127.0.0.1
```

Open the gallery `index.html` paths printed by `find` using `http://127.0.0.1:8080/`; the exact directory layout is defined by the archive. The notebook serves each gallery from its own local server and can create two independent temporary gallery HTTPS links, separate from Studio.

## Run the demo on Kaggle

**Notebook to import:** [`kaggle-dual-gpu-production-demo.ipynb`](notebooks/kaggle-dual-gpu-production-demo.ipynb). Download this file from GitHub and import it into Kaggle to begin the guided two-GPU image demo.

**Start with the [complete English setup guide](docs/public-demo-notebook.md).** It explains exactly how to import the file, choose **Kaggle GPU T4 ×2**, then find and attach both required inputs in **Input → Add Input**: the [GGUF Q6_K Model](https://www.kaggle.com/models/dangkhoa2016/unsloth-z-image-turbo-gguf/gguf/q6-k) (`gguf / q6-k / version 1`) and the [Diffusers Support Dataset](https://www.kaggle.com/datasets/dangkhoa2016/z-image-turbo-diffusers-support-components). **Run All** requires both. No separate Kaggle dataset of project source code is needed.


### Requirements

- A Kaggle notebook with **Tesla T4 ×2** accelerator and **Internet enabled** for initial dependencies and Release downloads.
- Attach GGUF model **`dangkhoa2016/unsloth-z-image-turbo-gguf`**, variation **`q6-k`**, version **1** (`z-image-turbo-Q6_K.gguf`).
- Attach support components **`dangkhoa2016/z-image-turbo-diffusers-support-components`** (required text encoder and VAE). These are **model inputs**, not a separate dataset of application source code.
- The notebook clones **`main`** from GitHub and records its exact Git SHA. Set an explicit 40-character `ZIMAGE_SOURCE_SHA` for immutable reproduction; application source is **not** supplied by a Kaggle dataset.
- The [v1.0.0 release notebook](https://github.com/dangkhoa2016/Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/releases/download/v1.0.0/kaggle-dual-gpu-production-demo.ipynb) remains a separately published snapshot.

### Community-friendly Kaggle notebook

The refreshed notebook uses **12 short code cells** (11 of them a single readable method call) and 16 English/Vietnamese explanatory cells. Model-loading, checksum verification, GPU inference, Studio and gallery implementation now live in [Python demo steps](scripts/kaggle_production_demo.py) rather than thousands of notebook lines. See the [community notebook guide](docs/public-demo-notebook.md).

The canonical notebook is published on **`main`**. Previous GPU and Studio sessions produced checksum-verified notebook PNGs and completed Studio jobs; their scope is recorded in the [evidence index](docs/evidence-index.md). **A clean-environment Run All of the current published `main` remains to be verified.** No inference speedup or model change is claimed.

### Production notebook — verified GPU/Studio draft, fresh `main` replay next

The [28-cell production notebook](notebooks/kaggle-dual-gpu-production-demo.ipynb) is the **canonical GitHub template** for dual-T4 image generation, authenticated Studio and galleries. Earlier reviewed runs verified two 1024×1024 notebook PNGs and completed Studio GPU jobs. **These historical results do not constitute a fresh execution of the current published `main`.**

The default configuration is `P25_LOAD_ONLY=False`, `P24_GGUF_PREFETCH_ENABLED=False`, `P23_ENABLE_OPTIONAL_WEB_APPS=True` and `P27_VAE_STALL_PROFILING=False`. Qwen3 and GGUF checkpoint copies use full-SHA256 verified staging under `/tmp/zimage-t4x2-model-stage/`. Source checkout, output PNGs, logs and acceptance ZIP stay in `/kaggle/working`. The notebook preflights free space on both mounts; `/tmp` is not necessarily a faster or separate disk.

**Gallery HTTPS reliability:** The production notebook records transient Kaggle DNS/network probe failures as `PENDING_BROWSER_VERIFICATION` instead of aborting Studio. This is **not** public HTTPS PASS: verify both gallery URLs, cross-gallery links, and image loading in a real browser before Full E2E acceptance. A reachable gallery with incorrect cross-navigation still fails. For network or Studio access issues, see [troubleshooting](docs/troubleshooting.md).

### Kaggle run options

For a complete **fresh Run All**, attach GGUF Q6_K version 1 and the support dataset, select Tesla T4 ×2 and Internet, and execute all 28 cells. Verify both newly generated PNGs, SHA256 receipts and the ZIP; then test Studio and gallery browsers.

For a **Studio-only validation without regenerating the two already approved notebook PNGs**, use a fresh Kaggle T4 ×2 runtime. Run **code cells 3, 5, 7, 16 and 18**, in that order; then submit new Studio prompts and run **code cell 27** for continuous read-only logs (stop by Interrupt Cell). This selective run is **not** a new notebook GPU Run All result. Studio still needs to encode new prompts and start independent GPU workers; the original notebook workers are no longer in VRAM. Acceptance requires a verified Studio PNG and an `ARCHIVED` session.

Studio gateway: `:18789`, private API: `:18788`, quality gallery: `:18881`, benchmark gallery: `:18882`. Temporary HTTPS links and Studio passwords must not be exposed while active. Capture `persistent-gpu-consumer.log`, `encoder-phase.log` and `worker-*.log` on failure. [Kaggle guide](docs/kaggle.md) · [Troubleshooting](docs/troubleshooting.md).

## Repository guide

```text
Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/
├── README.md / README.vi.md              # Bilingual project entry points
├── notebooks/                             # One public Kaggle demo notebook
├── product-studio/                        # Vue interface and authenticated gateway
├── production-system/                    # Queue, inference, sessions, worker and artifacts
│   ├── studio-demo/                       # Local demo startup/API/consumer
│   └── private-artifact-store/            # Job ownership, receipts, PNG retrieval
├── deployment/                           # Start/resume entry points
├── scripts/                              # Checkout, vendor bootstrap, CPU/security checks
├── manifests/                            # Model/support metadata and compatibility lock
├── evidence/                             # Sanitized historical acceptance JSON
├── docs/                                 # Architecture, deployment and bilingual guides
├── .github/workflows/                    # Repository audit workflow
├── RELEASE_NOTES_v1.0.0.md               # Technical preview notes
└── LICENSE / LICENSE-NOTES.md            # Project and upstream license boundaries
```

**Source is not model distribution:** the repository does not contain GGUF weights, tokenizer/encoder checkpoints, a public cache of generated private PNGs, runtime SQLite databases or secret files. The 170-image *watermarked* collection is distributed separately as a Release download.

### Validate source without a GPU

For a configured Python environment with dependencies installed, the repository exposes:

```bash
python scripts/run_cpu_tests.py
python scripts/scan_secrets.py
```

The GitHub [repository audit](.github/workflows/repository-audit.yml) automates syntax/document checks and CPU/security contracts. The four verified vendor package versions and their wheel/tree digests are recorded in [`manifests/runtime-compatibility.json`](manifests/runtime-compatibility.json): Diffusers **0.41.0**, Hugging Face Hub **1.28.0**, TorchAO **0.15.0**, GGUF **0.17.1**. This is a verified **vendor/CPU reference**, not a full GPU version lock; PyTorch/CUDA/Transformers/Accelerate versions still require measurement on the target T4×2 runtime.

## Security and limitations

- **Demonstration scope:** there is no SLA, durable public endpoint, autoscaling guarantee or production service approval. An offline CI PASS must not be reported as a fresh GPU inference PASS.
- **Access boundary:** expose only the authenticated Studio gateway through Cloudflare; keep the private API, service keys and internal job receipts behind it. The gallery is a separate static, public, *watermarked* artifact.
- **Runtime persistence:** Kaggle processes, local SQLite state, unexported PNGs and Quick Tunnel URLs may disappear at session shutdown. Save required private results outside the ephemeral runtime before stopping it.
- **Interpretation of results:** worker concurrency is distinct from queue batching; nine-step GPU diffusion timing is distinct from full elapsed job time; image-gallery display approval is distinct from prompt-adherence or image-quality acceptance.

## Documentation and further reading

| Topic | English | Tiếng Việt |
|---|---|---|
| Architecture | [Architecture](docs/architecture.md) | [Kiến trúc](docs/architecture.vi.md) |
| Kaggle setup | [Kaggle guide](docs/kaggle.md) | [Hướng dẫn Kaggle](docs/kaggle.vi.md) |
| API and Studio | [API](docs/api.md) | [API](docs/api.vi.md) |
| Runtime requirements | [Compatibility](docs/runtime-compatibility.md) | [Tương thích](docs/runtime-compatibility.vi.md) |
| Benchmark context | [Benchmarks](docs/benchmark.md) | [Benchmark](docs/benchmark.vi.md) |
| Evidence | [Evidence index](docs/evidence-index.md) | [Chỉ mục bằng chứng](docs/evidence-index.vi.md) |
| Deployment | [Deployment profile](docs/deployment-profile.md) | [Cấu hình triển khai](docs/deployment-profile.vi.md) |
| Engineering overview | [Engineering overview](docs/engineering-overview.md) | [Tổng quan kỹ thuật](docs/engineering-overview.vi.md) |
| Release | [Release notes](RELEASE_NOTES_v1.0.0.md) | [Ghi chú phát hành](RELEASE_NOTES_v1.0.0.vi.md) |
| Project changes | [Changelog](CHANGELOG.md) | [Nhật ký thay đổi](CHANGELOG.vi.md) |

Additional policies: [Security](SECURITY.md) · [Contributing](CONTRIBUTING.md) · [Project contract](PROJECT-CONTRACT.md) · [Troubleshooting](docs/troubleshooting.md).

## Licensing and attribution

Project-authored code and documentation: **MIT License**, © 2026 **Đăng Khoa** ([i.am@dangkhoa.dev](mailto:i.am@dangkhoa.dev)). This license does **not** relicense Z-Image-Turbo, GGUF weights or other upstream packages. The Z-Image model family and referenced quantized model publish separate upstream Apache-2.0 notices; retain their terms and verify rights for your intended use. See [license notes](LICENSE-NOTES.md), the [upstream license copy](THIRD_PARTY_LICENSES/Z-IMAGE-APACHE-2.0), and the original [Z-Image project](https://github.com/Tongyi-MAI/Z-Image).

---

**Project position:** a documented dual-T4 image-generation demo, reviewable technical evidence, and a published bilingual gallery are available. The notebook and source enable independent reproduction, with environment-specific results to be verified by each operator.

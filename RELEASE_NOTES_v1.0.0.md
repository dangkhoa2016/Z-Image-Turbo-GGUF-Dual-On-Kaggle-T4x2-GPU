# Z-Image-Turbo GGUF Q6_K — v1.0.0

**First public release · Dual-GPU image generation on Kaggle Tesla T4 ×2**

**Language:** English · [Tiếng Việt](RELEASE_NOTES_v1.0.0.vi.md)

This release presents an end-to-end, open-source demonstration of **Z-Image-Turbo GGUF Q6_K running on two NVIDIA Tesla T4 GPUs**. It brings together GPU-aware model preparation, independent image-generation workers, a guided Kaggle notebook, an authenticated Vue Studio, and two browsable galleries containing **170 watermarked images**.

The objective is not simply to load a quantized model or display a few generated pictures. It is to make a constrained dual-GPU workflow **understandable, executable, observable, and reviewable**: from verified inputs and bounded prompt encoding to independent PNG outputs, job lifecycle records, browser interaction, and downloadable evidence.

**Explore this release:** [Visual showcase](#image-showcase) · [Key capabilities](#what-this-release-delivers) · [Architecture](#how-the-system-works) · [Validation status](#gpu-validation-status-for-this-release) · [Run on Kaggle](#run-the-demo-on-kaggle) · [Downloads](#release-assets-and-integrity)

## Image showcase

| Curated example 010 | Curated example 011 | Curated example 013 | Curated example 027 |
| :---: | :---: | :---: | :---: |
| ![Published image showcase sample 010](assets/showcase/pqt_v1_010.webp) | ![Published image showcase sample 011](assets/showcase/pqt_v1_011.webp) | ![Published image showcase sample 013](assets/showcase/pqt_v1_013.webp) | ![Published image showcase sample 027](assets/showcase/pqt_v1_027.webp) |

*These are lightweight previews from the published, watermarked quality gallery—not the two separate PNGs used as GPU execution evidence. The full [170-image gallery archive](https://github.com/dangkhoa2016/Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/releases/download/v1.0.0/zimage-gallery-170-watermarked-public-v1.0.0.tar.gz) includes the galleries and their browsing metadata.*

## What this release delivers

**A complete demonstration path, not just a model-loading script.** The initial release combines five parts that can be explored together or reviewed independently:

1. **Dual-GPU GGUF inference.** Prompt encoding is bounded on GPU 0; separate inference workers then generate images on **GPU 0 and GPU 1**. GPU 0 participates in both stages—it is not reserved exclusively for the text encoder.
2. **One source-first Kaggle notebook.** The **28-cell** notebook contains **12 short code cells and 16 bilingual instructional cells**. It retrieves the application source from GitHub, validates the two Kaggle inputs, prepares the runtime, and runs image generation without an extra Kaggle dataset for the source code.
3. **An interactive generation Studio.** A Vue interface provides authenticated prompt submission, a SQLite-backed job queue, visible job progress, image viewing and downloading, and distinct timing information for job lifecycle and GPU work.
4. **An inspectable image showcase.** Two bilingual galleries present **48 curated examples** and **122 test/benchmark examples**, with prompts and supporting metadata where available. They are packaged separately from source code as **170 watermarked PNGs and 40 WebP thumbnails**.
5. **Engineering evidence and documentation.** Runtime observations, source provenance, SHA256-based artifact checks, CPU tests, security boundaries, architecture notes, and Kaggle setup instructions are available for technical review.

The project is intended for **AI/ML engineers, developers experimenting with GGUF image generation, and Kaggle users** who want to study how a multi-component inference workflow is assembled and verified.

## How the system works

The architecture separates interactive access, queue management, prompt encoding, image inference, and public gallery presentation. It also keeps the browser-facing Studio gateway distinct from the private generation API.

~~~text
Kaggle notebook → verified GitHub source + Kaggle model/support inputs
       │
       ├─ Hardware, dependency, storage and model-integrity checks
       │
       └─ Qwen3 prompt encoding (bounded stage on GPU 0)
                      │
              GPU job dispatch
                 /         \
     GGUF worker GPU 0    GGUF worker GPU 1
                 \         /
              1024×1024 PNGs
                      │
         artifact integrity / SHA256
                      │
     notebook evidence + Studio image delivery

Browser → authenticated Vue Studio gateway → private API
                                                │
                                       SQLite job/session queue
                                                │
                                          GPU workers

Browser → separate quality / benchmark gallery sites
~~~

This division matters on Tesla T4 hardware: preparing the encoder and GGUF weights, controlling memory pressure, dispatching real jobs to both devices, and checking resulting artifacts are distinct problems. The repository treats them as distinct stages instead of assuming that two detected GPUs automatically mean useful parallel execution.

**Studio design.** The browser connects through the authenticated gateway (port **18789**), while the API (port **18788**) remains private. SQLite records job and session state; completed artifacts are linked to owned jobs, with private receipts and authenticated image retrieval. The public quality and benchmark galleries use separate static servers rather than exposing private Studio outputs.

**Model and source integrity.** The workflow verifies its Git source revision and stages the required GGUF and encoder resources with integrity checks. It also distinguishes an image newly generated in the current execution from a checksum-verified file reused from an earlier run. This distinction is essential when assessing whether both GPUs actually performed inference.

For implementation details, see [Architecture](docs/architecture.md), [API and Studio](docs/api.md), and [Runtime compatibility](docs/runtime-compatibility.md).

## Engineering decisions and trade-offs

This release is the outcome of making several pieces work *together* under Kaggle's dual-T4 constraints. Detecting two CUDA devices or loading GGUF weights is only the starting point; a useful demo must also prepare the right inputs, make both devices perform real work, protect interactive sessions, and leave evidence that others can inspect.

| Engineering challenge | Approach in this release | Why it matters |
| --- | --- | --- |
| **Multi-component model setup** | Keep the Q6_K GGUF model and the separate text encoder/tokenizer/VAE support dataset as explicit Kaggle inputs. Stage and verify the required model files before inference. | Reviewers can distinguish input preparation and integrity checking from image-generation time instead of treating everything as a single opaque startup cost. |
| **Shared GPU 0 responsibilities** | Bound the Qwen3 prompt-encoding stage on GPU 0, then use GPU 0 alongside GPU 1 for independent GGUF image inference. | Neither GPU is merely decorative; the workflow explicitly manages the transition from prompt preparation to two device-assigned generation jobs. |
| **Concurrent jobs, not misleading speed claims** | Launch separate inference workers and record per-device outputs and timings, with an observable queue/session lifecycle for Studio requests. | The result demonstrates independent work on two devices without confusing concurrent output with a guaranteed reduction in single-image latency. |
| **Public UI versus private results** | Route Studio traffic through an authenticated Vue gateway to a private API, with SQLite job ownership and private artifact delivery; serve the public galleries separately. | Visitors can examine released examples without exposing Studio's private image store or turning a temporary Kaggle runtime into an assumed public service. |
| **Reproducibility and provenance** | Use a compact notebook as a launcher for GitHub-hosted application source; keep revision information, new-versus-reused artifact distinctions, checksums, and technical records. | A reviewer can trace what code and resources produced a result, rather than relying on a screenshot or a success message alone. |

These decisions also explain why the project documents **model staging, encoder preparation, GPU worker startup, image rendering, and browser delivery as different phases**. In Kaggle, storage I/O, VAE initialization and accelerator availability can vary from session to session. The release therefore reports observed results while leaving detailed measurements and investigation history in the [benchmarks](docs/benchmark.md) and [evidence index](docs/evidence-index.md).

The outcome is a practical reference for developers building constrained inference demos: a clear path from inputs and GPU orchestration to an authenticated interactive experience, published visual examples, and inspectable artifacts.

## GPU validation and acceptance records

**Verification and reproducibility:** The v1.0.0 release provides a source-traceable Kaggle Tesla T4 ×2 workflow with verifiable outputs. GPU inference, authenticated Studio interactions and independent reproduction are assessed separately, using evidence tied to the exact executed Git SHA. Consult the [GitHub Release v1.0.0](https://github.com/dangkhoa2016/Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/releases/tag/v1.0.0) for reported results and supporting artifacts.

Each accepted GPU execution must record the actual Git SHA, two newly rendered 1024 × 1024 PNGs (one per GPU), independently recomputed SHA256 digests, worker identities and times, and exported receipts. Studio image generation, browser View/Download, and both galleries require separate checks.

The [revision-specific validation protocol](docs/evidence-index.md) defines the evidence to collect. Results from another revision or earlier development session do not establish acceptance of the published notebook.

## Two complementary image galleries

| Collection | What you can explore |
| --- | --- |
| **Quality gallery — 48 images** | Curated visual examples and review information, including original/retry relationships and status metadata where present. |
| **Test and benchmark gallery — 122 images** | A broader set of generated outputs with available prompt, runtime, worker and artifact details for technical inspection. |

Both galleries provide **English/Vietnamese presentation**, image detail views, navigation, and browsing tools. The release archive contains **170 watermarked PNG images total**; the **40 WebP thumbnails** are optimized browsing derivatives, *not 40 additional generated images*. Unwatermarked originals and private Studio artifacts are not redistributed.

The galleries can be inspected **without allocating a Kaggle GPU**: download the archive, extract it, and serve or open the provided static gallery files locally. See the [README gallery guide](README.md#170-image-release-galleries) for instructions and integrity verification.

Visual review of the published collection should not be confused with independent proof that every image perfectly follows its prompt. The gallery records retain the distinction between demonstration output and evaluated image quality.

## Run the demo on Kaggle

### Requirements

Use a Kaggle notebook with **NVIDIA Tesla T4 ×2**, **Internet enabled**, sufficient available runtime resources, and *both* of these inputs:

| Input category | Resource to attach |
| --- | --- |
| **Kaggle Model** | [dangkhoa2016/unsloth-z-image-turbo-gguf](https://www.kaggle.com/models/dangkhoa2016/unsloth-z-image-turbo-gguf/gguf/q6-k) — framework **gguf**, variation **q6-k**, version **1** |
| **Kaggle Dataset** | [z-image-turbo-diffusers-support-components](https://www.kaggle.com/datasets/dangkhoa2016/z-image-turbo-diffusers-support-components) — text encoder, tokenizer and VAE |

The **Model** supplies the Q6_K weights; the separate **Dataset** supplies its required Diffusers support components. Neither is a dataset containing the application's GitHub source.

### Five-step walkthrough

1. **Download and import** the [official 28-cell release notebook](https://github.com/dangkhoa2016/Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/releases/download/v1.0.0/kaggle-dual-gpu-production-demo.ipynb) into Kaggle. It is an output-free template, not a published dump of private execution logs.
2. **Configure the session:** select the **Tesla T4 ×2** accelerator and enable Internet. In **Input → Add Input**, attach the exact Model and Dataset listed above.
3. **Run the notebook in order.** Its preflight checks both devices and inputs, obtains source from GitHub, prepares dependencies, performs prompt encoding, and dispatches one image-generation workload to each GPU. No edits to the notebook's code cells are required for the documented configuration.
4. **Inspect your results:** verify two new **1024 × 1024 PNGs**, check their artifact hashes, and save the generated evidence ZIP. For a fresh execution, distinguish *generated in this run* from previously cached output.
5. **Explore the optional web interfaces:** open the session's Studio and gallery URLs, use your own temporary Studio credentials, submit a prompt, and download completed images. Interrupt the continuous monitor cell when finished and save wanted files before the Kaggle runtime ends.

The [step-by-step Kaggle guide](docs/public-demo-notebook.md) covers model selection, exact input mounts, run stages, expected output markers, and troubleshooting. The operator's executed Kaggle notebook remains intentionally **PRIVATE**, so its Kaggle page is not a public `Copy & Edit` entry point. Import the output-free notebook from this GitHub Release instead; independent third-party GPU reproduction requires separately published receipts.

## Release assets and integrity

Two assets accompany **v1.0.0**. The Git repository intentionally excludes large model weights, generated private images, and runtime databases.

| Download | Contents | Size |
| --- | --- | ---: |
| [**Kaggle production demo** (.ipynb)](https://github.com/dangkhoa2016/Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/releases/download/v1.0.0/kaggle-dual-gpu-production-demo.ipynb) | Clean guided 28-cell notebook | 53,176 bytes |
| [**170-image public gallery** (.tar.gz)](https://github.com/dangkhoa2016/Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/releases/download/v1.0.0/zimage-gallery-170-watermarked-public-v1.0.0.tar.gz) | Watermarked images, WebP thumbnails and bilingual gallery presentation | 228,277,211 bytes |

**SHA256 of the two stable assets** (also available in GitHub Release metadata):

~~~text
d925b1f3b729d5ea4ca6cc655b14eb90eced42dd4a11e9e8ca6cbd98f1f9d094  kaggle-dual-gpu-production-demo.ipynb
acb2997ac8430ba239d8afadcfb8d17c7ff09634e00299f3bf8d2161681b207e  zimage-gallery-170-watermarked-public-v1.0.0.tar.gz
~~~

Download checksums are also recorded in GitHub Release asset metadata. Model files must be attached separately through Kaggle and retain their own upstream licensing conditions.

## Compatibility, scope and security

- **Validated environment:** Kaggle **Tesla T4 ×2**. CPU-only and single-T4 sessions are not supported targets for the documented dual-GPU flow.
- **Performance scope:** Accepted per-GPU render timings, if available, belong in the GitHub Release validation report. Two workers do not guarantee a 2× single-image speedup, fixed cold-start time, or universal throughput.
- **Session lifetime:** Kaggle runtime storage, Studio state, downloaded results, and Cloudflare Quick Tunnel URLs can be temporary. Studio is a **session-based demo**, not a continuously hosted production service.
- **Security boundary:** Only the authenticated gateway should be exposed for Studio; keep the private API, receipts, service tokens and active login credentials private. Do not publicly share an executed notebook containing active passwords or tunnel details.
- **Reproduction boundary:** GPU execution and operator browser acceptance must be substantiated in the GitHub Release for the exact source SHA. Independent-account Copy & Edit and executed-output sanitization must be verified separately; every session must verify its own inputs and execution.

## Navigate the source and contribute

| Area | Where to begin |
| --- | --- |
| Project overview and gallery | [README](README.md) |
| Notebook orchestration | [notebooks/](notebooks/) and [Kaggle demo guide](docs/public-demo-notebook.md) |
| Inference, queue and artifacts | [production-system/](production-system/) |
| Vue Studio and gateway | [product-studio/](product-studio/) |
| Architecture and Studio endpoints | [Architecture](docs/architecture.md) · [API](docs/api.md) |
| Runtime compatibility and dependencies | [Compatibility guide](docs/runtime-compatibility.md) · [Vendor dependency notes](docs/vendor-dependencies.md) |
| Measured evidence and test methodology | [Evidence index](docs/evidence-index.md) · [Benchmarks](docs/benchmark.md) |
| Repository checks | [GitHub Actions audit](https://github.com/dangkhoa2016/Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/actions/workflows/repository-audit.yml) |

Project-authored source and documentation are released under the **MIT License**, copyright © 2026 **Đăng Khoa**. **Model weights and third-party packages are not relicensed by this repository**; see [License Notes](LICENSE-NOTES.md), the [upstream notices](THIRD_PARTY_LICENSES/Z-IMAGE-APACHE-2.0), and the original [Z-Image project](https://github.com/Tongyi-MAI/Z-Image).

Issues, technical reviews, and focused pull requests are welcome. See [Contributing](CONTRIBUTING.md) and [Security](SECURITY.md) before reporting a bug or sharing a reproduction artifact. Please omit credentials, private generated images, and live tunnel links from public reports.

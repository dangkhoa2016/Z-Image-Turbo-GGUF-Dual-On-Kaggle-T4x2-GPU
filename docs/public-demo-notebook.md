# Run Z-Image Turbo Q6_K on Kaggle T4 ×2

> 🌐 Language / Ngôn ngữ: **English** | [Tiếng Việt](public-demo-notebook.vi.md)

## Start here — choose exactly one notebook

**Import only [kaggle-dual-gpu-production-demo.ipynb](../notebooks/kaggle-dual-gpu-production-demo.ipynb).** This is the community-facing notebook for image generation and the Studio/Gallery demo. It includes 16 complete English/Vietnamese instructional cells and 12 short code cells.

Download the linked notebook, attach the Model and Dataset below, and run it in Kaggle.

**What you will get:** two newly generated 1024 × 1024 PNG images (one per Tesla T4), SHA256 verification, an evidence ZIP, a temporary Studio login, and example quality/benchmark galleries. All source code is obtained from GitHub, not from a Kaggle source-code dataset.

## A. Import the notebook into Kaggle

1. Open [the single official notebook](../notebooks/kaggle-dual-gpu-production-demo.ipynb) on GitHub.
2. Download the actual `.ipynb` file using **Download raw file**. Do not download the HTML preview of the GitHub page.
3. Sign in to [Kaggle](https://www.kaggle.com/) and open its **Notebooks** editor. Import/upload the `.ipynb` file. The exact import-menu wording may vary between Kaggle editor layouts.
4. Open **Session options / Notebook settings**. Select **Accelerator → GPU T4 ×2** and enable **Internet**.
5. Prefer a fresh Kaggle session without other GPU-intensive processes. The notebook validates both GPUs.

The script is written for **two** Tesla T4 devices. Selecting CPU or a single T4 does not satisfy its requirements.

## B. Attach the Q6_K model (select **Models**, not Datasets)

This is a separate **Kaggle Model** resource. Attach it to the notebook rather than downloading a different GGUF quantization.

1. In the notebook editor, find the right-side **Input** panel. Select **Add Input** or **Add Models** (Kaggle's wording depends on the editor).
2. Choose/filter **Models**, not Datasets.
3. Search by the full owner/model slug `dangkhoa2016/unsloth-z-image-turbo-gguf`, or open the [exact model detail page](https://www.kaggle.com/models/dangkhoa2016/unsloth-z-image-turbo-gguf/gguf/q6-k) to identify it.
4. Confirm **owner:** `dangkhoa2016`; **model:** `unsloth-z-image-turbo-gguf`.
5. In the model selection interface, select **framework:** `gguf`; **variation:** `q6-k`; **version:** `1`. The variation and version are important: another quantization or version is not interchangeable with this demo.
6. Choose **Add / Attach** to include the model in your current notebook. If a license gate appears, review it before accepting.

**Verification:** The Input panel should show this model, variation and version. At runtime, the expected weight is `z-image-turbo-Q6_K.gguf`. The notebook automatically validates its exact Kaggle-mounted location.

## C. Attach the support components (select **Datasets**, not Models)

This is a separate **Kaggle Dataset** containing the components needed alongside the GGUF model.

1. Return to **Input → Add Input**.
2. Choose/filter **Datasets** rather than Models.
3. Search `dangkhoa2016/z-image-turbo-diffusers-support-components` or open the [support dataset page](https://www.kaggle.com/datasets/dangkhoa2016/z-image-turbo-diffusers-support-components).
4. Confirm **owner:** `dangkhoa2016`; **dataset:** `z-image-turbo-diffusers-support-components`. Choose **Add / Attach**.
5. Verify that **two inputs are attached**: the **GGUF Q6_K Model** and the **Diffusers support Dataset**. Both are required.

**Why a dataset?** It contains **text_encoder**, **tokenizer** and **vae** files. It does *not* contain the main GGUF weights, and is *not* a dataset of this repository's source code.

### Input verification checklist

| Input category | Exact selection | Expected runtime mount |
| --- | --- | --- |
| **Model** | `dangkhoa2016/unsloth-z-image-turbo-gguf` → `gguf / q6-k / 1` | `/kaggle/input/models/dangkhoa2016/unsloth-z-image-turbo-gguf/gguf/q6-k/1/z-image-turbo-Q6_K.gguf` |
| **Dataset** | `dangkhoa2016/z-image-turbo-diffusers-support-components` | `/kaggle/input/datasets/dangkhoa2016/z-image-turbo-diffusers-support-components/z-image-turbo-diffusers-support` |

These are the exact paths currently required by the project, not paths a user needs to type. The notebook checks them automatically and stops with a descriptive message if either is missing. Do not manually move or rename the attached Kaggle inputs.

## D. Run All and understand the output

After both inputs are attached, select **Run All**. No code-cell modifications are required.

| Steps | What happens | How to recognize success |
| --- | --- | --- |
| Source and setup | Check out verified Git source, validate two GPUs and both inputs; prepare dependencies | `SOURCE_READY`, `GPU_T4X2_READY`, `PREFLIGHT_READY` |
| Prompt encoding | Generate embeddings for two prompts | `NOTEBOOK_GPU_EMBEDDINGS_READY` |
| Two-GPU generation | Load GPU0 and GPU1 workers and generate two images | `BOTH_MODEL_INSTANCES_READY`, verified 1024 × 1024 PNGs |
| Verify and archive | Check provenance and SHA256; export evidence ZIP | `NOTEBOOK_OWN_INFERENCE_PROOF: PASS` and `p23-runall-acceptance.zip` |
| Studio and galleries | Start web services, generate temporary HTTPS URLs | Studio sign-in and two gallery links |
| Live monitor | Display Studio job/session states and GPU logs continuously | Use **Interrupt Cell** when finished using Studio |

For a **fresh run**, verify `GENERATED_IN_CURRENT_RUN`. A checksum-verified *reused* PNG is valid as a file, but does not demonstrate new GPU generation during the current run.

## E. Try Studio and the galleries

1. Open the Studio HTTPS URL printed by the notebook; use the temporary `studio` username and the password in **your own** Kaggle output.
2. Enter and submit a **new prompt**. Observe the queue and GPU logs using the final monitor cell.
3. When a new PNG is generated, test **View** and **Download**, and verify the job/session reaches its completed `ARCHIVED` state.
4. Open the **Quality Gallery** and **Benchmark Gallery** URLs in a browser; confirm both display images and link to each other.
5. If the notebook prints `PENDING_BROWSER_VERIFICATION`, external HTTPS was **not confirmed from Kaggle**. Open the addresses yourself; do not treat the pending status as a success.
6. Save the PNG files, SHA256 results, evidence ZIP and executed notebook before ending the Kaggle session. Do not share a notebook containing still-active Studio credentials.

Studio generation is **separate** from notebook-native GPU inference. The two verified notebook PNGs do not prove a Studio browser job succeeded.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| Cannot find the model | Search in **Models**, check owner `dangkhoa2016`, framework `gguf`, variation `q6-k` and version `1` |
| Cannot find support files | Search in **Datasets**; attach `z-image-turbo-diffusers-support-components` in addition to the model |
| Notebook says no T4 ×2 | Select the correct accelerator in Session options; a single T4 is insufficient |
| Source checkout fails | Enable Internet, and confirm Kaggle can reach GitHub |
| Disk-space check fails | The notebook handles staging and checks capacity automatically; save existing files and use a clean session rather than overriding safeguards |
| Studio loads but never creates an image | Keep the final monitor running; preserve consumer/encoder/worker logs and check that a new job reaches `ARCHIVED` |

See [Kaggle's official Notebook instructions](https://www.kaggle.com/docs/notebooks) for the current **Input → Add Input** flow and [Kaggle Models documentation](https://www.kaggle.com/docs/models) for framework, variation and version selection. Kaggle may change button labels without changing the underlying steps.

## Revision-specific validation

The production notebook is published on **`main`** and records the exact Git revision at runtime. For reproduction, pin `ZIMAGE_SOURCE_SHA` to a SHA from the [GitHub Release](https://github.com/dangkhoa2016/Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/releases/tag/v1.0.0) acceptance report; verify the notebook output matches it. The [validation protocol](evidence-index.md) defines evidence requirements. Independent-account copying and replay require their own proof.

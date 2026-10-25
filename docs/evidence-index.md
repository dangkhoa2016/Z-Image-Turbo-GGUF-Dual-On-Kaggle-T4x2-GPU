# Revision-specific GPU and browser validation

> 🌐 Language / Ngôn ngữ: **English** | [Tiếng Việt](evidence-index.vi.md)

## Where to find the current result

The [v1.0.0 GitHub Release](https://github.com/dangkhoa2016/Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/releases/tag/v1.0.0) provides published GPU and browser validation reports and their supporting artifacts. This guide defines the evidence needed to assess a Kaggle Tesla T4 ×2 execution. An acceptance claim requires verifiable source provenance, input versions, outputs and checks; a missing result is **not** a PASS.

The released notebook loads application code from GitHub and records a 40-character checkout SHA. Results apply **only to that exact SHA and the stated Kaggle input versions**. Before reproducing a specific acceptance, set `ZIMAGE_SOURCE_SHA` to the SHA recorded in the Release evidence; otherwise the notebook intentionally resolves the latest `main` SHA. Reviewers can verify a reported result by checking that the executed source SHA matches the published evidence.

| Acceptance gate | Evidence to inspect | Acceptance rule |
|---|---|---|
| Source and inputs | Exact 40-character Git SHA, T4 ×2 hardware, both Kaggle model inputs and versions | SHA and input identity must match the report |
| New GPU images | Two newly generated 1024 × 1024 PNGs, one per worker with GPU ID, prompt and seed | Freshly rendered outputs, not reused cache |
| Image and archive integrity | SHA256 of each PNG, `report.json`, `inference-manifest.json` and ZIP | Recalculate hashes from actual bytes |
| Studio workflow | Authenticated new prompt, completed/archived job, PNG View/Download | Browser action and receipts both verified |
| Public galleries | Gallery asset SHA256, images, two sites and cross-navigation | Integrity and browser behavior verified separately |
| Independent replay | Other Kaggle account importing released notebook with both model inputs | Mark unverified unless actually reproduced |

## Execute and archive fresh evidence

Download the [v1.0.0 release notebook](https://github.com/dangkhoa2016/Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/releases/download/v1.0.0/kaggle-dual-gpu-production-demo.ipynb). Use a clean Kaggle Tesla T4 ×2 runtime with Internet enabled and attach both documented model inputs. Verify the source SHA printed by the notebook; retain each GPU's seed, worker ID, PNG, log and per-worker/wall elapsed time, plus `report.json`, `inference-manifest.json`, and `p23-runall-acceptance.zip`.

Before publishing, independently check the source SHA, PNG bytes, SHA256, and ZIP receipt. Sanitize Studio passwords, API secrets, private media and temporary tunnel addresses. Attach approved evidence to the same GitHub Release, with execution date, SHA, hardware, model input versions and explicit scope/status. Publish the verified outcome alongside its source SHA and evidence in the GitHub Release so other developers can reproduce the checks.

CPU/CI PASS is **not** proof that CUDA image inference, HTTPS links or Studio interactions worked. A `PENDING_BROWSER_VERIFICATION` output remains unverified until inspected in a real browser. The gallery's 170 watermarked PNGs and 40 WebP previews are published visual examples, not evidence of a fresh GPU Run All or universal prompt-fidelity acceptance.

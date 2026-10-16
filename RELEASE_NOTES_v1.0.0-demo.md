# v1.0.0-demo — Technical preview

> 🌐 Language / Ngôn ngữ: **English** | [Tiếng Việt](RELEASE_NOTES_v1.0.0-demo.vi.md)

This technical preview publishes the source of a Z-Image-Turbo GGUF Q6_K demonstration for two Kaggle Tesla T4 GPUs. Included are bounded GPU0 prompt encoding, two inference workers, an authenticated Vue Studio, private PNG artifact receipts, a Kaggle launch notebook and bilingual documentation.

## Verification
- Archived dual-GPU inference, browser image generation, Studio elapsed seconds and public HTTPS checks are included as JSON evidence.
- GitHub repository audit validates source/documentation structure; it does not exercise a fresh live GPU runtime.
- Historical Pilot32 prompt-adherence and visual-quality evaluation: **NOT_PASS**.
- New clean-room Kaggle T4×2 setup and end-to-end replay: **PENDING**.

## Distribution and support
- Third-party model weights are not distributed; attach the referenced model and support dataset on Kaggle.
- Original 48/122 gallery HTML assets are not bundled.
- HTTPS tunnels are temporary, and the demo does not carry a production uptime SLA.

See [engineering overview](docs/engineering-overview.md), [runtime compatibility](docs/runtime-compatibility.md), [evidence index](docs/evidence-index.md) and [license notices](LICENSE-NOTES.md).

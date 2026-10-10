# v1.0.0 — Technical preview

> 🌐 Language / Ngôn ngữ: **English** | [Tiếng Việt](RELEASE_NOTES_v1.0.0.vi.md)

This technical preview publishes the source of a Z-Image-Turbo GGUF Q6_K demonstration for two Kaggle Tesla T4 GPUs. Included are bounded GPU0 prompt encoding, two inference workers, an authenticated Vue Studio, private PNG artifact receipts, a Kaggle launch notebook and bilingual documentation.

## Verification
- Archived dual-GPU, browser image generation, HTTPS and job elapsed checks are documented in JSON evidence. A separate [October 18 verified-runtime summary](evidence/kaggle-t4x2-studio-acceptance-2026-10-18.json) records dual-T4 image receipts and user-accepted Studio View/Download; it is not a fresh notebook reproduction.
- GitHub repository audit validates source/documentation structure; it does not exercise a fresh live GPU runtime.
- Public gallery presentation acceptance does not imply that every prompt meets all visual-quality and semantic-adherence criteria.
- New clean-room Kaggle T4×2 setup and end-to-end replay: **PENDING**.

## Distribution and support
- Third-party model weights are not distributed; attach the referenced model and support dataset on Kaggle.
- The public Release includes the approved watermarked 170-image bundle (48 quality and 122 benchmark PNGs) with bilingual gallery HTML. Original unwatermarked private media is not distributed.
- HTTPS tunnels are temporary, and the demo does not carry a production uptime SLA.

See [engineering overview](docs/engineering-overview.md), [runtime compatibility](docs/runtime-compatibility.md), [evidence index](docs/evidence-index.md) and [license notices](LICENSE-NOTES.md).

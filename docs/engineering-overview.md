# Engineering overview

> 🌐 Language / Ngôn ngữ: **English** | [Tiếng Việt](engineering-overview.vi.md)

Z-Image-Turbo GGUF Dual is an image-generation demonstration built around Kaggle Tesla T4 ×2, bounded prompt encoding and independent inference workers. The system includes session-aware queues, isolated artifact receipts, authenticated Vue Studio and a notebook launch path.

## Engineering evidence and limitations

The current source includes GPU orchestration, authenticated Studio and two static galleries. Run All and browser acceptance are recorded per Git SHA on the [GitHub Release](https://github.com/dangkhoa2016/Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/releases/tag/v1.0.0). Published gallery presentation approval is not proof that every generated image meets every visual-quality and prompt-adherence criterion. Fresh GPU and independent-account reproduction must not be claimed as PASS without independent revision-matched evidence.

## Technical references

See [architecture](architecture.md), [runtime compatibility](runtime-compatibility.md), and [evidence index](evidence-index.md) for implementation details and verified test boundaries.

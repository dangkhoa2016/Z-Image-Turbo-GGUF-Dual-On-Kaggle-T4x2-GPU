# Engineering overview

> 🌐 Language / Ngôn ngữ: **English** | [Tiếng Việt](engineering-overview.vi.md)

Z-Image-Turbo GGUF Dual is an image-generation demonstration built around Kaggle Tesla T4 ×2, bounded prompt encoding and independent inference workers. The system includes session-aware queues, isolated artifact receipts, authenticated Vue Studio and a notebook launch path.

## Engineering evidence and limitations

The included acceptance JSONs document earlier dual-GPU execution, browser-to-PNG delivery, Studio elapsed-time display and HTTPS access. Those tests describe the original Kaggle environment; they are not a fresh installation test. Published gallery presentation approval is not proof that every generated image meets every visual-quality and prompt-adherence criterion. A clean Kaggle T4×2 end-to-end notebook replay remains **PENDING**.

## Technical references

See [architecture](architecture.md), [runtime compatibility](runtime-compatibility.md), and [evidence index](evidence-index.md) for implementation details and verified test boundaries.

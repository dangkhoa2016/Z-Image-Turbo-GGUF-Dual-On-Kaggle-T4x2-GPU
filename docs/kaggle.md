# Kaggle deployment

> 🌐 Language / Ngôn ngữ: **English** | [Tiếng Việt](kaggle.vi.md)

Select Tesla T4 ×2, enable Internet and attach the Q6_K GGUF Kaggle model and Z-Image support dataset identified in the README. Open the notebook and run its cells in order. It clones code, verifies GPU/model, prepares dependencies, starts API, starts consumer, and creates separate gallery/Studio tunnels. Studio login is printed only for demo viewers; backend service keys stay private. Re-running the notebook against an existing live runtime requires preserving job states. Cloudflare URLs are transient. Attach actual 48/122-image HTML and assets before gallery startup; never relabel the Pilot32 set. Installation of the exact vendored package versions is not yet independently reproduced from a clean environment.

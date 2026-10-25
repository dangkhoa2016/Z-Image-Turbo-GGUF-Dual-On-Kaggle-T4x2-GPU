# System architecture

> 🌐 Language / Ngôn ngữ: **English** | [Tiếng Việt](architecture.vi.md)

The browser submits authenticated jobs through the Vue Studio gateway on localhost port 18789, which forwards requests to a private FastAPI API on port 18788. SQLite stores job lifecycle state. GPU0 performs bounded prompt encoding; independent inference workers use GPU0 and GPU1 for concurrent image generation. Archived artifacts are SHA256 verified, stored privately and downloaded through authenticated API requests. Worker concurrency does not imply the encoder phase is parallel. The Studio and gallery Cloudflare tunnels must use distinct web servers. GPU and independent-account reproduction require revision-matched acceptance evidence; consult the [GitHub Release](https://github.com/dangkhoa2016/Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/releases/tag/v1.0.0) for results, not the static source tree.

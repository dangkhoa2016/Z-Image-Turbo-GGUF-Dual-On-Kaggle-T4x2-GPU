# Z-Image-Turbo-GGUF Dual — Kaggle T4 ×2 Demo

A real GPU image generation showcase with Z-Image-Turbo Q6_K GGUF, two Kaggle Tesla T4 GPUs, Vue Studio v3, private PNG receipts, and independent Cloudflare Quick Tunnels.

## Notebook

Open [Kaggle production demo notebook](notebooks/kaggle-dual-gpu-production-demo.ipynb). Configure Kaggle GPU T4×2, Internet ON, model `dangkhoa2016/unsloth-z-image-turbo-gguf` Q6_K v1 and dataset `dangkhoa2016/z-image-turbo-diffusers-support-components`. Execute notebook cells in order.

The notebook clones this repository, prepares model/runtime, starts API, protected Vue Studio and the GPU consumer. It then provides separate HTTPS tunnel cells for the benchmark galleries and the Studio. Studio login `studio` plus a generated demo-only password are printed in the Studio cell; internal Bearer keys are never printed.

## Gallery assets

The original **48-image and 122-image gallery assets are not currently available in the Kaggle runtime and are not included in this repository**. Attach them under `/kaggle/working/gallery-48/` and `/kaggle/working/gallery-122/` with `index.html` and their image files. The existing Pilot32 gallery has 32 images and must not be substituted. The gallery cell checks assets before starting the site.

## Demonstrated capabilities

Prior runtime tests PASSED real GPU0 and GPU1 concurrent inference, authenticated browser click-to-render, View/Download, 1024×1024 private PNG and SHA256 receipts, elapsed seconds per image, and user-approved Vue image-loading spinner. A fresh run of the published notebook is **not yet independently GPU-verified**. Archived milestones are not replayed.

## Security / persistence

No secrets, SQLite, user PNGs, model weights or private runtime artifacts are committed. Gallery and Studio have different public Quick Tunnel URLs. The Studio tunnel targets the password-protected gateway `127.0.0.1:18789`, never the private API `18788`. Shared notebook output makes demo credentials visible to viewers by design. URLs are ephemeral. Git clone does not restore previous sessions or images; use Kaggle Save Version or a private verified checkpoint if you want state persistence. Demo readiness does not equal production-grade GO.

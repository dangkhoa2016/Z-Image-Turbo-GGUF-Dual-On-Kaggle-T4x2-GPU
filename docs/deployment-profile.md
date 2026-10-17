# Showcase Deployment Profile

> 🌐 Language / Ngôn ngữ: **English** | [Tiếng Việt](deployment-profile.vi.md)

## Presentation architecture

The project offers two separate HTTPS experiences for a Kaggle T4 ×2 showcase:

- **Generation Studio:** the approved Vue interface provides an authenticated prompt-to-image workflow, queued/running/completed status, a loading animation, total job elapsed time, and PNG View/Download. The Cloudflare tunnel points to the password-protected gateway on port `18789`, not the internal API on `18788`.
- **Benchmark galleries:** a separate static server presents the original **48-image and 122-image** gallery sites. The original HTML and corresponding image assets are provided separately as optional showcase inputs; they are not distributed in the source repository. The Pilot32 quality-review set is not a replacement for either gallery.

## Operational profile

Two Tesla T4 GPUs support independent inference workers, while bounded GPU0 prompt encoding and VRAM requirements determine throughput. Kaggle sessions are ephemeral; Cloudflare Quick Tunnel addresses change on restart. The notebook prints a **disposable demo password** for viewers; it does not print internal service secrets. Keep private PNGs, SQLite state and model weights outside the public Git repository, and export needed runtime artifacts before shutdown.

## Evidence and intended scope

The [evidence index](evidence-index.md) links to completed dual-GPU, browser and image-integrity checks. Technical completion and human visual-quality review are distinct; the earlier Pilot32 visual-quality gate was **NOT_PASS**. The showcase targets a reproducible technical demo, not a production SLA or permanent public hosting service.

[Runtime compatibility](runtime-compatibility.md) · [Kaggle guide](kaggle.md) · [License notes](../LICENSE-NOTES.md)

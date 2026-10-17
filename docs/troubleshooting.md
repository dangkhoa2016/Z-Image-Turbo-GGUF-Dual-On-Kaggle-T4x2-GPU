# Troubleshooting

> 🌐 Language / Ngôn ngữ: **English** | [Tiếng Việt](troubleshooting.vi.md)

## Notebook refuses to start
Check T4×2 accelerator, exact Kaggle input model+dataset versions, Internet access for initial vendor restoration, and an accessible notebook working directory. A leftover runtime that is incomplete is intentionally not overwritten.

## Missing original galleries
Provide original index.html and 48/122 images in the two expected folders; Pilot32 contains only 32 images and must not be misrepresented.

## GPU worker fails
Compare Python/PyTorch/Transformers/Diffusers/TorchAO versions and archive provenance; only reuse legacy PASS after the same environment is actually tested. Inspect worker logs without exposing tokens.

## 401 or unavailable HTTPS URL
Login using the demo-only credentials printed in the Studio notebook cell. Quick Tunnel URLs change on restart. Expose only gateway 18789; do not expose API 18788.

## Missing PNG or receipt
Check job state and tenant ownership; do not invent receipts or replay uncertain jobs automatically.

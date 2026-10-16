# Evidence index

> 🌐 Language / Ngôn ngữ: **English** | [Tiếng Việt](evidence-index.vi.md)

## Verified evidence (legacy live Kaggle runtime)
- [Dual GPU E2E](../evidence/dual-gpu-inference-acceptance-2026-10-16.json): two completed PNG jobs assigned to GPU0 and GPU1; same-sample GPU utilization and verified private SHA256 receipts.
- [Chromium browser submission to rendered PNG](../evidence/browser-image-generation-acceptance-2026-10-16.json): completed 1024×1024 image, View/Download validated, no JS errors.
- [Studio elapsed seconds](../evidence/studio-elapsed-time-acceptance-2026-10-16.json): total seconds visible for six completed jobs.
- [Public HTTPS browser](../evidence/studio-https-browser-acceptance-2026-10-16.json): sign-in, three existing images and sign-out via temporary tunnel.

## Visual-quality and new-runtime verification boundaries
The historical Pilot32 visual-quality and prompt-adherence gate was **NOT_PASS**; rejected cases remain part of the evidence. Original 48/122 HTML galleries were not in this runtime. The repo rewrite and notebook have NOT yet passed a fresh Kaggle environment replay. These JSONs record past isolated verifications, not current cloud availability. No passwords, API keys or private image bytes are included.

# Evidence index

> 🌐 Language / Ngôn ngữ: **English** | [Tiếng Việt](evidence-index.vi.md)

## Verified evidence (legacy live Kaggle runtime)
- [Dual GPU E2E](../evidence/dual-gpu-inference-acceptance-2026-10-16.json): two completed PNG jobs assigned to GPU0 and GPU1; same-sample GPU utilization and verified private SHA256 receipts.
- [Chromium browser submission to rendered PNG](../evidence/browser-image-generation-acceptance-2026-10-16.json): completed 1024×1024 image, View/Download validated, no JS errors.
- [Studio elapsed seconds](../evidence/studio-elapsed-time-acceptance-2026-10-16.json): total seconds visible for six completed jobs.
- [Public HTTPS browser](../evidence/studio-https-browser-acceptance-2026-10-16.json): sign-in, three existing images and sign-out via temporary tunnel.

- [October 18 Kaggle T4x2 and authenticated Studio verification](../evidence/kaggle-t4x2-studio-acceptance-2026-10-18.json): 2/2 portable GPU receipts, 5 completed and 1 cancelled Studio jobs, user-accepted View/Download and prompt adherence; the logged 9-step GPU diffusion timings must not be labeled full generation time.

## Visual-quality and new-runtime verification boundaries
The published gallery archive is verifiable by its manifest; its existence does not imply universal human visual-quality or prompt-fidelity acceptance. The original 48/122 HTML galleries were not present in the reference runtime described by these archived checks; a later approved bilingual 170-image gallery bundle is now available separately as a GitHub Release asset. The repo rewrite and notebook have NOT yet passed a fresh Kaggle environment replay. These JSONs record past isolated verifications, not current cloud availability. No passwords, API keys or private image bytes are included.

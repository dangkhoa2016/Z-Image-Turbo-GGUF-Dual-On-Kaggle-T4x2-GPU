# API and Studio

> 🌐 Language / Ngôn ngữ: **English** | [Tiếng Việt](api.vi.md)

Vue Studio v3 protects access using a gateway session and internal service authentication. Submit prompt via POST /v1/jobs; inspect owned jobs via GET /v1/jobs, GET /v1/jobs/{job_id}; request completed PNG through GET /v1/studio/jobs/{job_id}/image. The job list exposes created_at and updated_at; the UI's Total Ns is end-to-end elapsed time, not pure GPU inference. View displays an SVG loading state until the PNG/prompt response has finished. The public tunnel must target 18789, never the private API at 18788. Do not publish service tokens or owner receipts.

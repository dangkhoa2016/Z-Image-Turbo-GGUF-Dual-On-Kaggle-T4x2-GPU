# API and Studio

> 🌐 Language / Ngôn ngữ: **English** | [Tiếng Việt](api.vi.md)

Vue Studio restricts access through gateway sessions and private backend credentials. Submit prompt via POST /v1/jobs; inspect owned jobs via GET /v1/jobs, GET /v1/jobs/{job_id}; request completed PNG through GET /v1/studio/jobs/{job_id}/image. The job list exposes created_at and updated_at; the UI labels end-to-end elapsed time explicitly as including queue/setup. Generation time is worker-measured where available; historical runs display log-derived GPU diffusion time (9 steps) distinctly, never as total job runtime. View displays an SVG loading state until the PNG/prompt response has finished. The public tunnel must target 18789, never the private API at 18788. Do not publish service tokens or owner receipts.

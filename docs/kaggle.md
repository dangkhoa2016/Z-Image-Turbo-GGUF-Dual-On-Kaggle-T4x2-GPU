# Kaggle deployment

> 🌐 Language / Ngôn ngữ: **English** | [Tiếng Việt](kaggle.vi.md)

## Maintained public notebook and verification scope

Open [the maintained production notebook](../notebooks/kaggle-dual-gpu-production-demo.ipynb) from `main`. Choose Tesla T4 ×2, enable Internet and attach GGUF Q6_K v1 plus the support dataset. The default Run All generates two real PNGs, verifies SHA256 and enables Studio/Gallery. Disposable Qwen3/GGUF copies reside under `/tmp`; source, logs, PNG and ZIP reside under `/kaggle/working`. Both disk budgets are checked before GPU work.

**Studio-only testing**: on a fresh runtime, run code cells **3, 5, 7, 16, 18**, submit a Studio prompt, then run **cell 27** for continuous read-only monitoring. This does not redo notebook-native inference and does not prove a fresh notebook Run All. Studio is accepted only after a real archived job and verified PNG. Full Run All uses all 28 cells. Protect active Studio credentials.

## Prepare
Use a Kaggle notebook with **Tesla T4 ×2**, Internet and the GGUF model/support dataset linked from the [README](../README.md). The v1.0.0 notebook retrieves application source directly from GitHub **`main`** by default: it first resolves the branch to a full 40-character Git SHA, then checks out and verifies that exact SHA for the current run. This identifies what was actually executed; `main` may move between runs. To reproduce a chosen immutable revision, explicitly set `ZIMAGE_SOURCE_SHA` to its full 40-character SHA before the source cell.

## Storage budget and historical evidence

The maintained notebook checks both `/tmp` and `/kaggle/working` before GPU work. Its hash-verified local staging uses approximately 8.05 GB for Qwen3 and 5.91 GB for GGUF, plus a 3 GiB staging reserve. Set `ZIMAGE_GGUF_SOURCE_MODE=auto` before Step 02 only if you intentionally accept a potentially slower cold read directly from Kaggle input.

GPU load and inference behavior must be verified anew in the current Kaggle runtime; source revisions and third-party copies require their own evidence. The current Run All writes `p23-runall-acceptance.zip` containing verified PNGs, provenance and bounded diagnostic logs. Review outputs for active credentials before sharing.

## Run the notebook-native GPU demonstration
Execute the **28-cell** notebook in order. After source checkout, hardware/model validation and vendor bootstrap, steps **04–06** encode two prompts on GPU0, run independent GPU0/GPU1 GGUF workers, verify their 1024 × 1024 PNG outputs with SHA256 and display the results. A verified prior report in the same workspace can be reused; incomplete results fail closed. Studio-generated PNGs are never substituted for the notebook's GPU proof.

## GGUF source choice and controlled A/B measurement
The library default is `auto`, while this dual-GPU Run All notebook deliberately defaults to `local` for fresh-run reproducibility. Before cell 12, you may set ZIMAGE_GGUF_SOURCE_MODE to auto, direct, or local. **auto** chooses an existing verified local GGUF when present; otherwise it uses the original Kaggle input without copying 5.9 GB. **direct** always reads the original manifest input, avoiding staging; earlier runs timed out during direct model loading. **local** explicitly copies and SHA256-verifies one GGUF before worker startup; corrupted cached objects fail closed and are never silently replaced.

Notebook cell 12 writes a per-attempt gguf-source-selection-*.json including requested/effective mode and source-selection elapsed seconds. model-startup-*.jsonl records the same mode alongside each worker startup stage and resource samples. The final report records source choice and startup durations separately from concurrent image generation. Compare direct and local under equivalent Kaggle hardware/model/runtime while preserving failed logs, worker traces and verified PNGs. Do not rerun completed image jobs merely for benchmarking; use isolated sessions or a controlled load-only test. Source selection does not fix the distinct Qwen3 CPU-to-CUDA transfer latency.


## Live Qwen3 memory and storage evidence
Step 04 checks sizes of the attached Qwen3 weight shards and reads at most 4 MiB from one shard. This bounded sample is cache-sensitive, NOT a cold-storage benchmark. While loading, the notebook samples the real encode_batch_gpu.py child process rather than only its controller every 15 seconds: CPU, RSS, page faults, physical read_bytes and application-level rchar. GPU memory and utilization are measured approximately every 30 seconds. Save encoder-resources-*.jsonl and encoder.log for investigation. Zero read_bytes does not prove the loader is inactive: cached and memory-mapped access need careful interpretation. This observer does not alter Qwen3 numerical operations or weights.

## Qwen3 encoder phase telemetry
Cell 10 shows the most recent encoder stage every 15 seconds; the encoder streams JSON events with timestamps, RSS and process I/O counters to encoder.log as each phase starts or finishes. Phases include imports, tokenizer loading, Qwen3 weights, transfer to CUDA, encoding each prompt and persisting/verifying embeddings. The controller no longer holds encoder stdout until its subprocess exits. These are elapsed wall-clock measurements, not percentages. The numerical inference, prompts and dtype are unchanged. GPU performance is not established by CPU tests.

## GGUF startup diagnostics (CPU-only instrumentation)
Notebook Step 05 reads a bounded 16 MiB GGUF sample (potentially from the OS cache), records per-worker CPU, RSS, I/O and page-fault counters every 30 seconds, and requests Python stack traces in the worker log approximately every 120 seconds during GGUF model loading. This instrumentation does not change model weights, restart inference or extend the 1,200-second per-GPU startup deadline. After a failure, preserve the worker logs and model-startup JSONL telemetry before terminating Kaggle. CPU test success is not GPU inference acceptance.

## Optional browser experiences
Cells **15–25** launch the authenticated Studio gateway and GPU consumer, restore the checksum-verified 170-image Release gallery, and create separate temporary HTTPS tunnels for Studio, the 48-image quality gallery and the 122-image benchmark gallery. Their local ports are `18789`, `18881` and `18882`; the private API remains on localhost port `18788`. The Studio password is a disposable demo credential; never publish an executed notebook with a still-active password and tunnel.

Cells **27–28** provide the optional, read-only Studio live monitor. The current monitor continues until the operator uses **Interrupt Cell**; it submits no generation requests. Export PNGs, reports and logs before the Kaggle session ends.

## Reproduction status
**Fresh-run acceptance:** The [validation protocol](evidence-index.md) defines required PNGs, SHA256, Studio and gallery checks. Consult the [GitHub Release](https://github.com/dangkhoa2016/Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/releases/tag/v1.0.0) for the latest evidence and actual status for the printed source SHA. Independent-account `Copy & Edit` needs its own proof; CPU/CI success is not GPU acceptance.

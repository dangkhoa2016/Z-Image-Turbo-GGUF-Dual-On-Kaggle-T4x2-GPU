# Kaggle deployment

> 🌐 Language / Ngôn ngữ: **English** | [Tiếng Việt](kaggle.vi.md)

## Prepare
Use a Kaggle notebook with **Tesla T4 ×2**, Internet and the GGUF model/support dataset linked from the [README](../README.md). The maintained application source is cloned from GitHub `main`; to select an immutable reviewed revision, configure `ZIMAGE_SOURCE_SHA` with a full 40-character commit SHA before the notebook source cell.

## Run the notebook-native GPU demonstration
Execute the **28-cell** notebook in order. After source checkout, hardware/model validation and vendor bootstrap, steps **04–06** encode two prompts on GPU0, run independent GPU0/GPU1 GGUF workers, verify their 1024 × 1024 PNG outputs with SHA256 and display the results. A verified prior report in the same workspace can be reused; incomplete results fail closed. Studio-generated PNGs are never substituted for the notebook's GPU proof.

## GGUF source choice and controlled A/B measurement
Set environment variable ZIMAGE_GGUF_SOURCE_MODE to auto (default), direct or local before running cell 12. **auto** chooses an existing verified local GGUF when present; otherwise it uses the original Kaggle input without copying 5.9 GB. **direct** always reads the original manifest input, avoiding staging; earlier runs timed out during direct model loading. **local** explicitly copies and SHA256-verifies one GGUF before worker startup; corrupted cached objects fail closed and are never silently replaced.

Notebook cell 12 writes a per-attempt gguf-source-selection-*.json including requested/effective mode and source-selection elapsed seconds. model-startup-*.jsonl records the same mode alongside each worker startup stage and resource samples. The final report records source choice and startup durations separately from concurrent image generation. Compare direct and local under equivalent Kaggle hardware/model/runtime while preserving failed logs, worker traces and verified PNGs. Do not rerun completed image jobs merely for benchmarking; use isolated sessions or a controlled load-only test. Source selection does not fix the distinct Qwen3 CPU-to-CUDA transfer latency.


## Live Qwen3 memory and storage evidence
Step 04 checks sizes of the attached Qwen3 weight shards and reads at most 4 MiB from one shard. This bounded sample is cache-sensitive, NOT a cold-storage benchmark. While loading, the notebook samples the real encode_batch_gpu.py child process rather than only its controller every 15 seconds: CPU, RSS, page faults, physical read_bytes and application-level rchar. GPU memory and utilization are measured approximately every 30 seconds. Save encoder-resources-*.jsonl and encoder.log for investigation. Zero read_bytes does not prove the loader is inactive: cached and memory-mapped access need careful interpretation. This observer does not alter Qwen3 numerical operations or weights.

## Qwen3 encoder phase telemetry
Cell 10 shows the most recent encoder stage every 15 seconds; the encoder streams JSON events with timestamps, RSS and process I/O counters to encoder.log as each phase starts or finishes. Phases include imports, tokenizer loading, Qwen3 weights, transfer to CUDA, encoding each prompt and persisting/verifying embeddings. The controller no longer holds encoder stdout until its subprocess exits. These are elapsed wall-clock measurements, not percentages. The numerical inference, prompts and dtype are unchanged. GPU performance is not established by CPU tests.

## GGUF startup diagnostics (CPU-only instrumentation)
Notebook Step 05 reads a bounded 16 MiB GGUF sample (potentially from the OS cache), records per-worker CPU, RSS, I/O and page-fault counters every 30 seconds, and requests Python stack traces in the worker log approximately every 120 seconds during GGUF model loading. This instrumentation does not change model weights, restart inference or extend the 1,200-second per-GPU startup deadline. After a failure, preserve the worker logs and model-startup JSONL telemetry before terminating Kaggle. CPU test success is not GPU inference acceptance.

## Optional browser experiences
Cells **15–25** launch the authenticated Studio gateway and GPU consumer, restore the checksum-verified 170-image Release gallery, and create separate temporary HTTPS tunnels for Studio, the 48-image quality gallery and the 122-image benchmark gallery. Their local ports are `18789`, `18881` and `18882`; the private API remains on localhost port `18788`. The Studio password is a disposable demo credential; never publish an executed notebook with a still-active password and tunnel.

Cells **27–28** contain an optional, read-only Studio live monitor; interrupt that cell alone when done. Export PNGs, report and logs before Kaggle shuts down.

## Reproduction status
The original dual-GPU and Studio acceptance records cover their documented Kaggle sessions. A complete end-to-end replay of the **current** published notebook from a fresh Kaggle T4×2 environment remains pending; CPU/CI success must not be described as a new GPU PASS.

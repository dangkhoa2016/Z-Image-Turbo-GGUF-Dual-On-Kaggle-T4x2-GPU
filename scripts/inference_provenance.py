"""Source-content identity for reusing prior verified notebook outputs.

The fingerprint covers inference-critical source inputs, not docs, UI or Git metadata.
Files must be byte-identical to reuse results from earlier source revisions.
"""
from __future__ import annotations
from pathlib import Path
import hashlib
import re

ACCEPTED_SOURCE_SHA = "ba52ec0be7c1a0396a21fe9fd07afa1c8f022577"
ACCEPTED_INFERENCE_FINGERPRINT = "2072f70c35a2091c1976ec2cc8f41e41d080a1b0ba0144b79e66f13b75f3d15e"
# Distinct code revision: staging changes the GPU worker but does not rewrite
# the historically accepted inference baseline, release tag, or GPU evidence.
PREDIAGNOSTIC_STAGED_INFERENCE_FINGERPRINT = "6b666652822db2ac3a8b686e9f02dd2fda05427a0dcbbee6f995147af4cd46db"
STAGED_INFERENCE_FINGERPRINT = "82c306b6f8ca2ba45fb2f7c86c3df4fcee1ad88906fbd189535c04956b62c530"
SELECTABLE_GGUF_INFERENCE_FINGERPRINT = "87175fea2b0dda67c393bdccb95d3802e729087f8a7e7e4ca47ac67c473129b7"
# P2.2 fingerprint intentionally differs: Qwen3 checkpoint path selection became
# opt-in (default direct) and qwen3_staging.py was added. Old accepted images and
# encoder embeddings cannot be migrated by silently assuming byte-equivalence.
P22_QWEN3_STAGING_INFERENCE_FINGERPRINT = "77442f8c7a3ec49c7ee74975987401d7fa47b000e71237fb953264bc64da7c61"
P22_QWEN3_STAGING_ENCODER_SUBSET_FINGERPRINT = "fe8babebb765bb5bb0d530bf870dc805ff7df3d65f3c2188dda76317fcad2ed0"
# Candidate-specific source identity after Studio encoder visibility and /tmp staging.
# Historical P2.2/P2.3 fingerprints above remain immutable.
STUDIO_TMP_INFERENCE_FINGERPRINT = "9a88a0b60e6e7cb2c32b2970301b7d441725cfa6c4a422353d89061b164f24cb"
STUDIO_TMP_ENCODER_SUBSET_FINGERPRINT = "bd9aad998ff3c0b6154717ceb8e377f06378cf2b58b43914a929b522b044e4df"

# All encoder-related inference files (excluding worker and staging) must match the accepted
# encoder dependency set before old verified embeddings can be migrated safely.
PREDIAGNOSTIC_ENCODER_SUBSET_FINGERPRINT = "7b5d2e41c0fa8347899f1fe67bd7f887bbd3a33027fe881042cc23d1155315df"
ACCEPTED_ENCODER_SUBSET_FINGERPRINT = "340bd5ce68564968fe36ef7868c4f66eb08f5565ddfec429b7919d8c221821ba"

INFERENCE_SOURCE_FILES = ('manifests/model.json', 'manifests/runtime-compatibility.json', 'manifests/support.json', 'production-system/dynamic_manifest.py', 'production-system/dynamic_worker.py', 'production-system/embedding_registry.py', 'production-system/encode_batch_cpu_mock.py', 'production-system/encode_batch_gpu.py', 'production-system/gpu_acceptance.py', 'production-system/gpu_dispatch.py', 'production-system/gpu_preflight.py', 'production-system/gpu_prompt_gate.py', 'production-system/http_dispatcher.py', 'production-system/lifecycle_schema.py', 'production-system/mock_dispatcher.py', 'production-system/package_portable_runtime.py', 'production-system/phase_controller.py', 'production-system/portable_checkpoint.py', 'production-system/portable_recovery.py', 'production-system/prepare_gpu_crash_fixture.py', 'production-system/prepare_restore_crash_fixture.py', 'production-system/queue_admission.py', 'production-system/reconciliation_audit.py', 'production-system/recovery_patch_helper.py', 'production-system/scoped_dispatcher.py', 'production-system/service.py', 'production-system/session_lifecycle.py', 'production-system/session_supervisor.py', 'production-system/shared_gpu_supervisor.py', 'production-system/shared_session_lifecycle.py', 'production-system/studio_auto_consumer.py', 'production-system/studio_batched_consumer.py', 'production-system/studio_live_one_gpu.py', 'production-system/studio_single_gpu_acceptance.py', 'production-system/studio_single_gpu_replay.py', 'production-system/unified_pipeline.py', 'production-system/vendor-shim/sitecustomize.py', 'production-system/verify_gpu_package.py', 'production-system/verify_portable_runtime.py', 'production-system/worker_adapter.py', 'requirements.txt', 'scripts/bootstrap_vendor.py', 'scripts/validate_gpu_runtime_imports.py', 'scripts/verify_vendor_runtime.py', 'scripts/stage_gguf_model.py', 'scripts/gguf_source_policy.py', 'production-system/qwen3_staging.py')

def inference_fingerprint(project):
    root = Path(project)
    digest = hashlib.sha256()
    for name in INFERENCE_SOURCE_FILES:
        file = root / name
        blob = file.read_bytes()
        digest.update(name.encode("utf-8") + b"\x00")
        digest.update(hashlib.sha256(blob).digest())
    return digest.hexdigest()

def encoder_subset_fingerprint(project):
    """Prove that the GPU0 encoder inputs are unaffected by worker-only staging."""
    root = Path(project)
    digest = hashlib.sha256()
    for name in INFERENCE_SOURCE_FILES:
        if name in ("production-system/dynamic_worker.py", "scripts/stage_gguf_model.py", "scripts/gguf_source_policy.py"):
            continue
        blob = (root / name).read_bytes()
        digest.update(name.encode("utf-8") + bytes([0]))
        digest.update(hashlib.sha256(blob).digest())
    return digest.hexdigest()


def check_source_sha(source_sha):
    if source_sha and not re.fullmatch(r"[0-9a-fA-F]{40}", source_sha):
        raise ValueError("ZIMAGE_SOURCE_SHA must be a full 40-character Git commit SHA")
    return source_sha.lower()

def verify_cached_source(report, checkout_sha, current_fingerprint):
    """Fail closed for changed inference inputs and unrelated source revisions."""
    stored_sha = report.get("source_sha")
    recorded_core = report.get("inference_fingerprint")
    if recorded_core is not None:
        if recorded_core != current_fingerprint:
            raise ValueError("CACHED_INFERENCE_SOURCE_MISMATCH")
        return "SAME_INFERENCE_CONTENT"
    if stored_sha == checkout_sha:
        return "SAME_CHECKOUT"
    if (stored_sha == ACCEPTED_SOURCE_SHA
            and current_fingerprint == ACCEPTED_INFERENCE_FINGERPRINT):
        return "VERIFIED_ACCEPTED_INFERENCE_CONTENT"
    raise ValueError("CACHED_INFERENCE_SOURCE_NOT_VERIFIED")

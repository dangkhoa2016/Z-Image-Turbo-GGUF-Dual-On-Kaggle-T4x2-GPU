import os, sys, time, json, socket, signal, hashlib, sqlite3, subprocess, textwrap
from pathlib import Path
from datetime import datetime, timezone

DIRECT_ROOT = (
    Path('/kaggle/working') /
    ('zimage-p25-loadonly-' + P25_EXPERIMENT_LABEL + '-' + uuid.uuid4().hex[:12])
    if P25_LOAD_ONLY else (Path('/kaggle/working') / ('zimage-final-runall-' + P29_FRESH_RUN_ID))
)
DIRECT_REPORT = DIRECT_ROOT / 'report.json'
if P25_LOAD_ONLY:
    print('P25_FRESH_BENCHMARK_ROOT',str(DIRECT_ROOT),
          'fresh_root_required=true','no_prior_image_reuse=true',flush=True)
DIRECT_PROMPTS = [
    'A cinematic photograph of a vintage red sports car parked beside a Mediterranean coastal road at sunrise, detailed paint reflections, realistic natural light, professional automotive photography',
    'A tranquil Japanese mountain village in autumn with a stone bridge over a clear river, colorful maple trees, distant misty mountains, photorealistic environmental detail',
]
DIRECT_SEEDS = (121041, 121042)
PROD = PROJECT / 'production-system'
assert (PROD / 'phase_controller.py').is_file()
assert (PROD / 'dynamic_worker.py').is_file()
assert (PROJECT / 'scripts/validate_gpu_runtime_imports.py').is_file(), 'Choose a source commit with GPU runtime validation available'
VENDOR_ENV = os.environ.copy()
VENDOR_ENV['PYTHONUNBUFFERED'] = '1'
VENDOR_ENV['HF_HUB_OFFLINE'] = '1'
VENDOR_ENV['TRANSFORMERS_OFFLINE'] = '1'

# Final run: stage and verify Qwen3 now, verified GGUF local in Step 05 after
# SHA256 manifest and disk-space checks. Encoder default outside this
# notebook remains 'direct', and 'auto' never creates a cache.
QWEN3_SOURCE_MODE = 'local'
QWEN3_STAGE_ROOT = Path(os.environ['ZIMAGE_QWEN3_STAGE_ROOT'])
assert QWEN3_SOURCE_MODE in ('direct', 'auto', 'local')
VENDOR_ENV['ZIMAGE_QWEN3_SOURCE_MODE'] = QWEN3_SOURCE_MODE
VENDOR_ENV['ZIMAGE_QWEN3_STAGE_ROOT'] = str(QWEN3_STAGE_ROOT)
print('QWEN3_SOURCE_POLICY', QWEN3_SOURCE_MODE,
      'stage_root='+str(QWEN3_STAGE_ROOT), 'sha256_manifest=required',
      'reserve_gib=2', 'gpu_inference=NOT_STARTED')

# Verify inference-critical source identity as well as image bytes/metadata.
# This allows trusted prior results to survive documentation/UI-only revisions.
sys.path.insert(0, str(PROJECT / "scripts"))
from inference_provenance import inference_fingerprint, verify_cached_source
DIRECT_INFERENCE_FINGERPRINT = inference_fingerprint(PROJECT)

def direct_previous_result():
    if not DIRECT_REPORT.is_file():
        return None
    report = json.loads(DIRECT_REPORT.read_text(encoding='utf-8'))
    from PIL import Image as PILImage
    assert report['status'] == 'DUAL_GPU_NOTEBOOK_RENDER_VERIFIED'
    source_mode = verify_cached_source(report, info['sha'], DIRECT_INFERENCE_FINGERPRINT)
    assert len(report['images']) == 2
    assert set(int(i['gpu']) for i in report['images']) == {0, 1}
    for image in report['images']:
        index = int(image['gpu'])
        assert image['seed'] == DIRECT_SEEDS[index]
        assert image['prompt'] == DIRECT_PROMPTS[index]
        p = Path(image['file'])
        assert p.is_file() and p.resolve().is_relative_to(DIRECT_ROOT.resolve())
        assert hashlib.sha256(p.read_bytes()).hexdigest() == image['sha256']
        with PILImage.open(p) as im:
            assert im.format == 'PNG' and im.size == (1024, 1024)
            im.verify()
    print('NOTEBOOK_CACHED_SOURCE_VERIFIED', source_mode, flush=True)
    return report

# P2.4 prefetch is not an extra model or CUDA process. It only stages GGUF
# bytes with the existing atomic SHA256 policy, while GPU0 encodes prompts.
# Cache presence is observational ONLY; do not treat it as SHA verification.
P25_MODEL_MANIFEST = json.loads((PROJECT/'manifests/model.json').read_text())
P25_SUPPORT_MANIFEST = json.loads((PROJECT/'manifests/support.json').read_text())
P25_CACHE_AT_START = {
    'gguf_path_existed': (
        Path(os.environ['ZIMAGE_GGUF_STAGE_ROOT']) /
        (P25_MODEL_MANIFEST['gguf_sha256']+'.gguf')
    ).is_file(),
    'qwen3_path_existed': (
        Path(os.environ['ZIMAGE_QWEN3_STAGE_ROOT']) /
        P25_SUPPORT_MANIFEST['manifest_sha256'] / 'text_encoder'
    ).is_dir(),
}
print('P25_CACHE_STATE_BEFORE_ENCODER', json.dumps(P25_CACHE_AT_START,sort_keys=True),
      'existence_is_not_integrity_verification',flush=True)

P24_PREFETCH_PROCESS = None
P24_PREFETCH_START = None
P24_PREFETCH_REPORT = None
P24_PREFETCH_LOG = None
P24_PREFETCH_RESULT = {"enabled":False,"reason":"not started"}

DIRECT_CACHED_REPORT = direct_previous_result()
DIRECT_IMAGES_WERE_REUSED = DIRECT_CACHED_REPORT is not None
DIRECT_SHOULD_RENDER = DIRECT_CACHED_REPORT is None

if not DIRECT_SHOULD_RENDER:
    print('EXISTING_NOTEBOOK_GPU_IMAGES_VERIFIED — reusing completed direct render; no GPU jobs submitted.', flush=True)
else:
    DIRECT_REUSE_ENCODER = False

    def validated_encoder_recovery(root):
        """Read-only source/input/embedding verification for an interrupted Step 05."""
        if root.is_symlink() or not root.is_dir():
            return False, 'root must be a real directory'
        required = ('prompts.json', 'encoder-identity.json', 'b16-phase-status.json',
                    'inference-manifest.json', 'encoder-timing.json', 'registry.sqlite3')
        if any((root/name).is_symlink() or not (root/name).is_file()
               for name in required):
            return False, 'GPU0 encoder files are incomplete'
        try:
            if json.loads((root/'prompts.json').read_text()) != DIRECT_PROMPTS:
                return False, 'recorded prompts do not match'
            identity = json.loads((root/'encoder-identity.json').read_text())
            support = json.loads((PROJECT/'manifests/support.json').read_text())
            version = subprocess.check_output(
                [sys.executable,'-c',
                 "import importlib.metadata as m;print(m.version('diffusers'))"],
                env=VENDOR_ENV,text=True,timeout=30).strip()
            if (identity.get('support_manifest_sha256') != support['manifest_sha256']
                    or identity.get('diffusers_version') != version
                    or identity.get('text_encoder_dtype') != 'bfloat16'
                    or identity.get('max_sequence_length') != 512):
                return False, 'encoder runtime or support manifest changed'
            from inference_provenance import (
                ACCEPTED_INFERENCE_FINGERPRINT, ACCEPTED_ENCODER_SUBSET_FINGERPRINT,
                PREDIAGNOSTIC_STAGED_INFERENCE_FINGERPRINT, STAGED_INFERENCE_FINGERPRINT,
                encoder_subset_fingerprint,
            )
            recorded = identity.get('inference_fingerprint')
            if recorded != DIRECT_INFERENCE_FINGERPRINT:
                # The only compatible legacy difference is the GPU worker's
                # local-GGUF loading path, not the source used to encode prompts.
                if (recorded not in (None, ACCEPTED_INFERENCE_FINGERPRINT,
                                     PREDIAGNOSTIC_STAGED_INFERENCE_FINGERPRINT,
                                     STAGED_INFERENCE_FINGERPRINT)
                    or encoder_subset_fingerprint(PROJECT)
                       != ACCEPTED_ENCODER_SUBSET_FINGERPRINT):
                    return False, 'encoder source provenance mismatch'
                print('GPU0_ENCODER_WORKER_ONLY_MIGRATION_VERIFIED', flush=True)
            phase=json.loads((root/'b16-phase-status.json').read_text())
            if phase.get('status')!='READY_FOR_INFERENCE_START' or phase.get('verified_ready')!=2:
                return False, 'GPU0 encoding was not fully verified'
            elapsed=json.loads((root/'encoder-timing.json').read_text()).get('seconds')
            if not isinstance(elapsed,(int,float)) or not 0<elapsed<1800:
                return False, 'encoder timing is invalid'
            # This subprocess checks registry READY rows, real safetensors
            # producer provenance and every embedding SHA256/shape/metadata.
            source = """
import json,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import hashlib,sqlite3
from embedding_registry import hash_file
from dynamic_manifest import read_manifest
root=Path(sys.argv[2])
identity=json.loads((root/'encoder-identity.json').read_text())
prompts=json.loads((root/'prompts.json').read_text())
manifest=read_manifest(root/'inference-manifest.json',allow_mock=False)
fields={k:identity[k] for k in ('support_manifest_sha256','diffusers_version',
                              'max_sequence_length','text_encoder_dtype')}
key_for=lambda prompt:hashlib.sha256(json.dumps({'prompt':prompt,**fields},
                         sort_keys=True,ensure_ascii=False,
                         separators=(',',':')).encode()).hexdigest()
keys={key_for(prompt) for prompt in prompts}
assert len(keys)==2 and set(manifest['entries'])==keys
db=sqlite3.connect('file:'+str(root/'registry.sqlite3')+'?mode=ro',uri=True)
try:
    for key in keys:
        row=db.execute('SELECT status,embedding_file,embedding_sha256 FROM encoding WHERE cache_key=?',
                       (key,)).fetchone()
        assert row and row[0]=='ready'
        assert (root/'cache'/row[1]).resolve()==Path(manifest['entries'][key]['embedding_file']).resolve()
        assert row[2]==manifest['entries'][key]['embedding_sha256']
finally:
    db.close()
print('GPU0_EMBEDDING_RECOVERY_INTEGRITY_PASS')
"""
            check=subprocess.run(
                [sys.executable,'-c',source,str(PROD),str(root)],
                env=VENDOR_ENV,text=True,capture_output=True,timeout=180)
            if check.returncode:
                return False, 'embedded tensor/registry check failed: '+check.stderr[-320:]
            # Do not auto-replay a job which may have already produced an image.
            for i in (0,1):
                roots=[PROJECT/'output'] + [
                    path/'output' for path in Path('/kaggle/working').glob('zimage-source-demo*')
                    if path.is_dir() and not path.is_symlink()]
                for output_root in roots:
                    folder=output_root/f'worker-{i}'
                    if folder.is_dir() and any(folder.glob(f'*-seed-{DIRECT_SEEDS[i]}.png')):
                        raise RuntimeError('PARTIAL_GPU_PNG_REQUIRES_RECONCILIATION: '
                                           +str(folder))
            print(check.stdout.strip(),flush=True)
            return True, 'two verified GPU0 embeddings with no previously completed PNG'
        except RuntimeError:
            raise
        except (OSError,ValueError,KeyError,TypeError,AssertionError,
                subprocess.SubprocessError) as exc:
            return False, type(exc).__name__+': '+str(exc)[-240:]

    if DIRECT_ROOT.exists():
        DIRECT_REUSE_ENCODER, reason = validated_encoder_recovery(DIRECT_ROOT)
        if DIRECT_REUSE_ENCODER:
            print('NOTEBOOK_ENCODER_RECOVERY_VERIFIED',reason,'root',DIRECT_ROOT,flush=True)
        else:
            for i in (0,1):
                roots=[PROJECT/'output'] + [
                    path/'output' for path in Path('/kaggle/working').glob('zimage-source-demo*')
                    if path.is_dir() and not path.is_symlink()]
                for output_root in roots:
                    folder=output_root/f'worker-{i}'
                    if folder.is_dir() and any(folder.glob(f'*-seed-{DIRECT_SEEDS[i]}.png')):
                        raise RuntimeError('PARTIAL_GPU_PNG_REQUIRES_RECONCILIATION: '+str(folder))
            old_root=DIRECT_ROOT
            DIRECT_ROOT=Path('/kaggle/working')/(
                'zimage-notebook-dual-gpu-demo-fresh-'+uuid.uuid4().hex[:12])
            DIRECT_REPORT=DIRECT_ROOT/'report.json'
            print('INCOMPLETE_RUN_PRESERVED',old_root,'reason',reason,flush=True)
            print('NEW_ISOLATED_OUTPUT_ROOT',DIRECT_ROOT,flush=True)
    for port in (12340, 12341):
        with socket.socket() as probe:
            probe.settimeout(0.3)
            if probe.connect_ex(('127.0.0.1', port)) == 0:
                raise RuntimeError('GPU_WORKER_PORT_OCCUPIED: ' + str(port))
    # Studio and notebook have separate job stores. Stale Studio queue records
    # are NOT proof of live GPU activity and must not block notebook inference.
    # Conversely, a live Studio consumer/encoder/worker must block this step,
    # even if its queue is momentarily empty, to avoid overlapping GPU usage.
    def other_live_inference_processes():
        scripts = {'demo_consumer.py', 'dynamic_worker.py',
                   'phase_controller.py', 'encode_batch_gpu.py',
                   'shared_gpu_supervisor.py'}
        active = []
        for entry in Path('/proc').iterdir():
            if not entry.name.isdecimal():
                continue
            try:
                argv = [x.decode('utf-8', errors='replace') for x in
                        (entry / 'cmdline').read_bytes().split(b'\\0') if x]
                script_names = {Path(part).name for part in argv}
                matched = sorted(script_names & scripts)
                if not matched:
                    continue
                raw_stat = (entry / 'stat').read_text()
                state = raw_stat[raw_stat.rfind(')')+2:].split()[0]
                if state in ('Z', 'X'):
                    continue
                if matched == ['demo_consumer.py'] and '--enable-gpu' not in argv:
                    continue
                active.append({'pid': int(entry.name), 'scripts': matched})
            except (OSError, IndexError, ValueError):
                continue  # A process may exit while /proc is being inspected.
        return active

    studio_databases = sorted(Path('/kaggle/working').glob(
        'zimage-source-demo*/production-system/b3-studio-demo-live-20261016/api.sqlite3'))
    for db_path in studio_databases:
        with sqlite3.connect('file:' + str(db_path) + '?mode=ro', uri=True,
                             timeout=5) as db:
            counts = dict(db.execute(
                "SELECT state, COUNT(*) FROM jobs GROUP BY state").fetchall())
            sessions = []
            if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='b112_sessions'").fetchone():
                sessions = db.execute(
                    "SELECT status, COUNT(*) FROM b112_sessions "
                    "WHERE status != 'ARCHIVED' GROUP BY status").fetchall()
        pending = sum(counts.get(state, 0) for state in ('queued', 'running', 'uncertain'))
        if pending or sessions:
            print('STUDIO_HISTORY_LEFT_UNCHANGED',
                  str(db_path), 'job_states=', counts, 'session_states=', sessions,
                  '— notebook will not consume or modify these jobs.', flush=True)

    live_pipelines = other_live_inference_processes()
    if live_pipelines:
        raise RuntimeError('LIVE_GPU_PIPELINE_CONFLICT: ' + json.dumps(live_pipelines) +
                           '. Studio/other inference processes are still active. '
                           'Do not run notebook generation concurrently.')
    gpu_owners = subprocess.run(
        ['nvidia-smi', '--query-compute-apps=pid,gpu_uuid',
         '--format=csv,noheader,nounits'],
        capture_output=True, text=True, timeout=15)
    if gpu_owners.returncode != 0:
        raise RuntimeError('GPU_PROCESS_PROBE_FAILED: ' + gpu_owners.stderr[-600:])
    if gpu_owners.stdout.strip():
        raise RuntimeError('GPU_ALREADY_IN_USE_BY_COMPUTE_PROCESSES: ' +
                           gpu_owners.stdout.strip())
    print('DIRECT_NOTEBOOK_GPU_EXCLUSIVITY_CONFIRMED: no live GPU inference '
          'process or CUDA compute owner was found.', flush=True)
    if not DIRECT_REUSE_ENCODER:
        DIRECT_ROOT.mkdir(parents=True, exist_ok=False)
        (DIRECT_ROOT / 'prompts.json').write_text(
            json.dumps(DIRECT_PROMPTS, indent=2), encoding='utf-8')
    # CPU-only background I/O: overlap GGUF local staging with the independent
    # GPU0 Qwen3 encoding phase. The worker will still reverify GGUF SHA256.
    if P24_GGUF_PREFETCH_ENABLED and os.environ.get("ZIMAGE_GGUF_SOURCE_MODE","local")=="local":
        P24_PREFETCH_START=time.monotonic()
        prefetch_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        P24_PREFETCH_REPORT=DIRECT_ROOT/("gguf-prefetch-"+prefetch_id+".json")
        P24_PREFETCH_LOG=DIRECT_ROOT/("gguf-prefetch-"+prefetch_id+".log")
        prefetch_command=[
            sys.executable,"-u",str(PROJECT/"scripts/gguf_prefetch.py"),
            "--manifest",str(PROJECT/"manifests/model.json"),
            "--destination",os.environ["ZIMAGE_GGUF_STAGE_ROOT"],
            "--report",str(P24_PREFETCH_REPORT),
        ]
        assert (PROJECT/"scripts/gguf_prefetch.py").is_file()
        with P24_PREFETCH_LOG.open("x",encoding="utf8") as prefetch_log:
            P24_PREFETCH_PROCESS=subprocess.Popen(
                prefetch_command,stdout=prefetch_log,stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,start_new_session=True,
                env=VENDOR_ENV.copy())
        P24_PREFETCH_RESULT={"enabled":True,"pid":P24_PREFETCH_PROCESS.pid,
                             "report_path":str(P24_PREFETCH_REPORT),
                             "log_path":str(P24_PREFETCH_LOG)}
        print("P24_GGUF_PREFETCH_STARTED",
              "pid="+str(P24_PREFETCH_PROCESS.pid),
              "sha256=mandatory","cuda=unused",flush=True)
    else:
        P24_PREFETCH_RESULT={"enabled":False,
                             "reason":"disabled_or_nonlocal_mode"}
        print("P24_GGUF_PREFETCH_SKIPPED",P24_PREFETCH_RESULT["reason"],flush=True)

    if DIRECT_REUSE_ENCODER:
        DIRECT_ENCODE_SECONDS=json.loads((DIRECT_ROOT/'encoder-timing.json').read_text())['seconds']
        print('GPU0_ENCODER_RECOVERED',f'{DIRECT_ENCODE_SECONDS}s',
              'no_repeat_encoding=true',flush=True)
    else:
        from qwen3_encoder_diagnostics import (describe_text_encoder_storage,
            encoder_child_snapshot, process_delta)
        version = subprocess.check_output([sys.executable, '-c',
            "import importlib.metadata as m; print(m.version('diffusers'))"],
            env=VENDOR_ENV, text=True, timeout=30).strip()
        support_manifest = json.loads((PROJECT / 'manifests/support.json').read_text())
        identity = dict(support_manifest_sha256=support_manifest['manifest_sha256'],
                        diffusers_version=version, max_sequence_length=512,
                        text_encoder_dtype='bfloat16',
                        inference_fingerprint=DIRECT_INFERENCE_FINGERPRINT)
        (DIRECT_ROOT / 'encoder-identity.json').write_text(json.dumps(identity, indent=2), encoding='utf-8')
        try:
            weight_details = describe_text_encoder_storage(
                Path(support_manifest['support_root']) / 'text_encoder', sample_mib=4)
            print('QWEN3_WEIGHT_STORAGE_SAMPLE', json.dumps(weight_details, sort_keys=True), flush=True)
        except (OSError, ValueError) as exc:
            print('QWEN3_WEIGHT_STORAGE_SAMPLE_UNAVAILABLE', type(exc).__name__, flush=True)
        print('NOTEBOOK_DIRECT_GPU_PHASE', 'ENCODING_TWO_PROMPTS', 'physical_gpu=0', flush=True)
        print('PROMPT_0', DIRECT_PROMPTS[0], '\nPROMPT_1', DIRECT_PROMPTS[1], flush=True)

        encoder_cmd = [sys.executable, '-u', str(PROD / 'phase_controller.py'),
                       '--db', str(DIRECT_ROOT / 'registry.sqlite3'),
                       '--cache-root', str(DIRECT_ROOT / 'cache'),
                       '--identity', str(DIRECT_ROOT / 'encoder-identity.json'),
                       '--prompt-json', str(DIRECT_ROOT / 'prompts.json'),
                       '--mode', 'gpu0', '--max-items', '2']
        encoder_log = DIRECT_ROOT / 'encoder.log'
        started = time.monotonic()
        encoder_resource_log = DIRECT_ROOT / ('encoder-resources-' +
            datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.jsonl')
        encoder_last_proc = None
        encoder_last_probe_at = None
        encoder_last_gpu_probe_at = started - 30
        print('QWEN3_RESOURCE_TELEMETRY', encoder_resource_log, flush=True)
        with encoder_log.open('w') as log:
            encoder = subprocess.Popen(encoder_cmd, cwd=PROD, env=VENDOR_ENV,
                                       stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                while encoder.poll() is None:
                    elapsed = time.monotonic() - started
                    if elapsed > 1500:
                        raise TimeoutError('GPU0 text encoding exceeded 1500 seconds')
                    # The GPU0 child now streams stage markers into encoder.log.
                    # Show the latest stage without reading large logs into memory.
                    last_stage = 'PHASE_CONTROLLER_STARTING'
                    try:
                        with encoder_log.open('rb') as current_log:
                            current_log.seek(0, 2)
                            end=current_log.tell()
                            current_log.seek(max(0,end-32768))
                            lines=current_log.read().decode('utf-8',errors='replace').splitlines()
                        for line in reversed(lines):
                            if line.startswith('ZIMAGE_ENCODER_STAGE '):
                                last_stage=json.loads(line.split(' ',1)[1]).get('stage','UNKNOWN')
                                break
                    except (OSError,ValueError):
                        last_stage='LOG_UNAVAILABLE'
                    # Observe the REAL encode_batch_gpu.py child, not this controller.
                    # Counter deltas show I/O/page faults during an ongoing phase,
                    # including potentially memory-mapped weight loading.
                    try:
                        probe_time = time.monotonic()
                        proc = encoder_child_snapshot(encoder.pid)
                        proc_data = process_delta(
                            encoder_last_proc, proc,
                            (probe_time-encoder_last_probe_at)
                            if encoder_last_probe_at is not None else 0)
                        if proc is not None:
                            encoder_last_proc = proc
                            encoder_last_probe_at = probe_time
                        resource = {'timestamp_utc':datetime.now(timezone.utc).isoformat(),
                                    'elapsed_seconds':round(elapsed,1),
                                    'stage':last_stage,'worker':proc_data}
                        if probe_time - encoder_last_gpu_probe_at >= 30:
                            try:
                                gp = subprocess.run(
                                    ['nvidia-smi', '--query-gpu=index,memory.used,utilization.gpu',
                                     '--format=csv,noheader,nounits'],
                                    capture_output=True, text=True, timeout=8)
                                resource['gpu_memory_and_utilization'] = (
                                    gp.stdout.strip() if gp.returncode==0 else 'unavailable')
                            except (OSError,subprocess.TimeoutExpired):
                                resource['gpu_memory_and_utilization']='unavailable'
                            encoder_last_gpu_probe_at=probe_time
                        with encoder_resource_log.open('a', encoding='utf-8') as details_file:
                            details_file.write(json.dumps(resource, sort_keys=True)+'\n')
                        if int(elapsed//15)%2==0:
                            print('QWEN3_ENCODER_RESOURCE',
                                  'state='+str(proc_data.get('state')),
                                  'rss_mib='+str(proc_data.get('rss_mib')),
                                  'cpu_pct='+str(proc_data.get('cpu_pct_one_core_100')),
                                  'read_mibps='+str(proc_data.get('read_mib_per_second')),
                                  'major_faults_delta='+str(proc_data.get('major_faults_delta')),
                                  flush=True)
                    except (OSError,ValueError,AssertionError) as exc:
                        print('QWEN3_RESOURCE_PROBE_UNAVAILABLE',type(exc).__name__,flush=True)
                    print(f'ENCODER_GPU_0 elapsed={elapsed:.0f}s (not percent)',
                          'stage='+last_stage,flush=True)
                    time.sleep(15)
            except BaseException:
                if encoder.poll() is None:
                    os.killpg(encoder.pid, signal.SIGTERM)
                    try: encoder.wait(timeout=15)
                    except subprocess.TimeoutExpired: os.killpg(encoder.pid, signal.SIGKILL)
                if P24_PREFETCH_PROCESS is not None and P24_PREFETCH_PROCESS.poll() is None:
                    os.killpg(P24_PREFETCH_PROCESS.pid, signal.SIGTERM)
                    try:P24_PREFETCH_PROCESS.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        os.killpg(P24_PREFETCH_PROCESS.pid, signal.SIGKILL)
                raise
        DIRECT_ENCODE_SECONDS = round(time.monotonic()-started, 2)
        if encoder.returncode != 0:
            if P24_PREFETCH_PROCESS is not None and P24_PREFETCH_PROCESS.poll() is None:
                os.killpg(P24_PREFETCH_PROCESS.pid,signal.SIGTERM)
                try:P24_PREFETCH_PROCESS.wait(timeout=10)
                except subprocess.TimeoutExpired:os.killpg(P24_PREFETCH_PROCESS.pid,signal.SIGKILL)
            print('\n'.join(encoder_log.read_text(errors='replace').splitlines()[-45:]))
            raise RuntimeError('GPU0_ENCODER_FAILED: see ' + str(encoder_log))
        phase = json.loads((DIRECT_ROOT / 'b16-phase-status.json').read_text())
        assert phase['status'] == 'READY_FOR_INFERENCE_START' and phase['verified_ready'] == 2, phase
        print('GPU0_ENCODER_PASS', f'{DIRECT_ENCODE_SECONDS}s', phase['status'], flush=True)

        # Export verified embeddings for the independent GPU-0 and GPU-1 workers.
        manifest_builder = """
    import json,sys
    from pathlib import Path
    sys.path.insert(0,sys.argv[1])
    from embedding_registry import Registry
    from dynamic_manifest import export_manifest
    root=Path(sys.argv[2]);identity=json.loads((root/'encoder-identity.json').read_text())
    prompts=json.loads((root/'prompts.json').read_text())
    reg=Registry(root/'registry.sqlite3',root/'cache',identity)
    export_manifest(reg,prompts,root/'inference-manifest.json')
    print('NOTEBOOK_EMBEDDING_MANIFEST_VERIFIED',flush=True)
    """
        subprocess.run([sys.executable, '-c', textwrap.dedent(manifest_builder), str(PROD), str(DIRECT_ROOT)],
                       env=VENDOR_ENV, check=True, timeout=120)
        subprocess.run([sys.executable, str(PROD / 'gpu_preflight.py'), '--expect-gpu',
                        '--manifest', str(DIRECT_ROOT / 'inference-manifest.json')],
                       cwd=PROD, env=VENDOR_ENV, check=True, timeout=150)
        (DIRECT_ROOT / 'encoder-timing.json').write_text(json.dumps({'seconds': DIRECT_ENCODE_SECONDS}))
        print('NOTEBOOK_GPU_EMBEDDINGS_READY', flush=True)

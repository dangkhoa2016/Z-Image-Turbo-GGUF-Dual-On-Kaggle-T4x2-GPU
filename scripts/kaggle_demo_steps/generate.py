from concurrent.futures import ThreadPoolExecutor
from urllib.request import urlopen
from PIL import Image as PILImage
import shutil, urllib.error, textwrap
sys.path.insert(0, str(PROJECT / 'scripts'))
from gguf_startup_diagnostics import read_process
from vae_startup_probe import sample_vae_startup, stack_request_allowed

if not DIRECT_SHOULD_RENDER:
    print('NOTEBOOK_DIRECT_GENERATION_ALREADY_COMPLETED — images will be displayed below.', flush=True)
else:
    MANIFEST_PATH = DIRECT_ROOT / 'inference-manifest.json'
    assert MANIFEST_PATH.is_file(), 'Run Step 04 before Step 05'
    ARTIFACT_ROOT = PROJECT / 'output'
    assert not ARTIFACT_ROOT.is_symlink(), 'Unsafe artifact root'
    ARTIFACT_ROOT.mkdir(exist_ok=True)
    log_suffix=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    worker_logs=[
        DIRECT_ROOT/(f'worker-{i}.log' if not (DIRECT_ROOT/f'worker-{i}.log').exists()
                     else f'worker-{i}-retry-{log_suffix}.log')
        for i in (0,1)
    ]
    worker_processes = []
    worker_handles = []
    started_models = time.monotonic()
    STARTUP_PER_GPU_LIMIT_SECONDS = 1200
    STARTUP_REPORT_INTERVAL_SECONDS = 30
    model_startup_by_gpu = {}
    last_process_sample = {}
    clock_ticks_per_second = os.sysconf('SC_CLK_TCK')
    worker_probe_script = PROJECT / 'scripts/gguf_startup_diagnostics.py'
    assert worker_probe_script.is_file() and not worker_probe_script.is_symlink()
    # Keep diagnostics from every attempt; never overwrite failed-run evidence.
    telemetry_path = DIRECT_ROOT / ('model-startup-' +
        datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.jsonl')

    def worker_stage(logpath):
        if not logpath.exists(): return 'STARTING'
        data = logpath.read_text(errors='replace')
        stages = [line for line in data.splitlines() if line.startswith('ZIMAGE_WORKER_STAGE ')]
        if not stages: return 'IMPORTING'
        try: return json.loads(stages[-1].split(' ', 1)[1]).get('stage','UNKNOWN')
        except ValueError: return 'UNREADABLE_STAGE'

    def worker_ready(i):
        try:
            with urlopen(f'http://127.0.0.1:{12340+i}/ready', timeout=2) as response:
                data = json.load(response)
            return data.get('ready') is True and data.get('worker_id') == i
        except (OSError, ValueError):
            return False

    def process_alive(i):
        return worker_processes[i].poll() is None

    def observed_gpu_memory():
        try:
            p = subprocess.run(['nvidia-smi', '--query-compute-apps=pid,gpu_uuid,used_gpu_memory',
                                '--format=csv,noheader,nounits'],capture_output=True,
                               text=True,timeout=15)
            return p.stdout.strip() if p.returncode == 0 else 'not available'
        except (OSError, subprocess.TimeoutExpired):
            return 'not available'

    def memory_events():
        try:
            return {k:int(v) for k,v in
                    (line.split() for line in
                     Path('/sys/fs/cgroup/memory.events').read_text().splitlines())}
        except (OSError, ValueError):
            return {}

    def sampled_process_resources(i, pid):
        now = time.monotonic()
        try:
            current = read_process(pid)
        except (OSError, ValueError, AssertionError) as exc:
            return {'procfs_probe_error': type(exc).__name__}
        previous = last_process_sample.get(i)
        result = dict(current)
        if previous is not None and previous[1]['process_start_ticks'] == current['process_start_ticks']:
            elapsed = max(now - previous[0], 1e-6)
            ticks = ((current['cpu_user_ticks'] + current['cpu_system_ticks']) -
                     (previous[1]['cpu_user_ticks'] + previous[1]['cpu_system_ticks']))
            result['process_cpu_pct_one_core_100'] = round(
                max(0, ticks) / clock_ticks_per_second / elapsed * 100, 1)
            for key in ('rchar', 'read_bytes', 'minor_faults', 'major_faults'):
                if key in current and key in previous[1]:
                    result[key + '_delta'] = max(0, current[key]-previous[1][key])
        last_process_sample[i] = (now, current)
        return result

    def startup_resources(i,seconds,stage):
        def read_optional(path):
            try: return path.read_text().strip()
            except OSError: return None
        root=Path('/sys/fs/cgroup')
        meminfo=read_optional(Path('/proc/meminfo')) or ''
        available=next((line.split()[1] for line in meminfo.splitlines()
                        if line.startswith('MemAvailable:')),None)
        return {'gpu':i,'stage':stage,'elapsed_seconds':round(seconds,1),
                'gguf_source_mode':gguf_choice['effective_mode'],
                'gguf_source_requested':gguf_choice['requested_mode'],
                'timestamp_utc':datetime.now(timezone.utc).isoformat(),
                'cgroup_current_bytes':read_optional(root/'memory.current'),
                'cgroup_peak_bytes':read_optional(root/'memory.peak'),
                'cgroup_max_bytes':read_optional(root/'memory.max'),
                'cgroup_events':memory_events(),
                'mem_available_kib':available,
                'gpu_compute':observed_gpu_memory(),
                'worker_process':sampled_process_resources(i, worker_processes[i].pid)}

    # P2.4: the background prefetch must finish successfully before ANY worker
    # starts. No unverified cache or failed/background job is ever accepted.
    P24_PREFETCH_AWAIT_SECONDS = 0.0
    if P24_PREFETCH_PROCESS is not None:
        prefetch_wait_started=time.monotonic()
        try:
            prefetch_rc=P24_PREFETCH_PROCESS.wait(timeout=430)
        except subprocess.TimeoutExpired as exc:
            if P24_PREFETCH_PROCESS.poll() is None:
                os.killpg(P24_PREFETCH_PROCESS.pid,signal.SIGTERM)
                try:P24_PREFETCH_PROCESS.wait(timeout=8)
                except subprocess.TimeoutExpired:os.killpg(P24_PREFETCH_PROCESS.pid,signal.SIGKILL)
            raise RuntimeError("P24_PREFETCH_WAIT_TIMED_OUT; inspect log "+str(P24_PREFETCH_LOG)) from exc
        P24_PREFETCH_AWAIT_SECONDS=round(time.monotonic()-prefetch_wait_started,3)
        if prefetch_rc != 0:
            print("P24_GGUF_PREFETCH_LOG_TAIL",
                  "\n".join(P24_PREFETCH_LOG.read_text(errors="replace").splitlines()[-25:]),
                  flush=True)
            raise RuntimeError("P24_GGUF_PREFETCH_FAILED: worker startup BLOCKED")
        if not P24_PREFETCH_REPORT.is_file() or P24_PREFETCH_REPORT.is_symlink():
            raise RuntimeError("P24_GGUF_PREFETCH_RECEIPT_MISSING")
        P24_PREFETCH_RECEIPT=json.loads(P24_PREFETCH_REPORT.read_text())
        assert (P24_PREFETCH_RECEIPT.get("status")=="VERIFIED_LOCAL_GGUF_READY"
                and P24_PREFETCH_RECEIPT.get("worker_must_reverify") is True
                and P24_PREFETCH_RECEIPT.get("staged_path")
                   ==str(Path(os.environ['ZIMAGE_GGUF_STAGE_ROOT']) /
                       (P24_PREFETCH_RECEIPT["source_sha256"]+".gguf")))
        P24_PREFETCH_RESULT.update({
            "status":"PASS","receipt":P24_PREFETCH_RECEIPT,
            "wait_seconds_after_encoder":P24_PREFETCH_AWAIT_SECONDS,
            "elapsed_from_launch_seconds":round(time.monotonic()-P24_PREFETCH_START,3),
        })
        print("P24_GGUF_PREFETCH_COMPLETED",
              "wait_seconds="+str(P24_PREFETCH_AWAIT_SECONDS),
              "stage_seconds="+str(P24_PREFETCH_RECEIPT["total_elapsed_seconds"]),
              "reverify_in_worker=true",flush=True)
    else:
        print("P24_PREFETCH_NOT_USED_SEQUENTIAL_BASELINE",flush=True)

    # The bounded source probe is not a storage benchmark (page cache may dominate).
    model_spec = json.loads((PROJECT / 'manifests/model.json').read_text())
    gguf_source = Path(model_spec['gguf_path'])
    try:
        io_check = subprocess.run(
            [sys.executable, str(worker_probe_script), 'io-probe', str(gguf_source), '--mib', '16'],
            capture_output=True, text=True, timeout=60)
        print('GGUF_IO_SAMPLE', io_check.stdout.strip() if io_check.returncode == 0
              else 'FAILED: '+io_check.stderr[-300:], flush=True)
    except (OSError, subprocess.TimeoutExpired) as exc:
        print('GGUF_IO_SAMPLE_UNAVAILABLE', type(exc).__name__, flush=True)

    # auto(default): verified existing local GGUF, otherwise direct input.
    # direct: no staging; local: explicitly stream and SHA256 verify the GGUF.
    from gguf_source_policy import select_gguf_source
    GGUF_SOURCE_REQUEST = os.environ.get('ZIMAGE_GGUF_SOURCE_MODE', 'local')
    gguf_choice = select_gguf_source(
        model_spec, Path(os.environ['ZIMAGE_GGUF_STAGE_ROOT']), GGUF_SOURCE_REQUEST)
    selection_file = DIRECT_ROOT / ('gguf-source-selection-' + log_suffix + '.json')
    selection_file.write_text(json.dumps(gguf_choice, indent=2, sort_keys=True)+'\n')
    print('NOTEBOOK_GGUF_SOURCE_SELECTED', json.dumps(gguf_choice, sort_keys=True), flush=True)
    if gguf_choice['effective_mode']=='local':
        GGUF_STAGED_PATH = Path(gguf_choice['staged_override_path'])
        print('NOTEBOOK_GGUF_LOCAL_STAGE_VERIFIED', GGUF_STAGED_PATH,
              'size_bytes', GGUF_STAGED_PATH.stat().st_size, flush=True)
        try:
            local_io = subprocess.run(
                [sys.executable, str(worker_probe_script), 'io-probe',
                 str(GGUF_STAGED_PATH), '--mib', '16'],
                capture_output=True, text=True, timeout=60)
            print('GGUF_LOCAL_IO_SAMPLE',
                  local_io.stdout.strip() if local_io.returncode==0
                  else 'UNAVAILABLE: '+local_io.stderr[-300:], flush=True)
        except (OSError, subprocess.TimeoutExpired) as exc:
            print('GGUF_LOCAL_IO_SAMPLE_UNAVAILABLE', type(exc).__name__, flush=True)
    else:
        print('NOTEBOOK_GGUF_DIRECT_INPUT_SELECTED',
              'source='+gguf_choice['model_path'],
              'warning=prior_direct_input_load_timeouts_not_resolved', flush=True)

    # A failed Step 05 can be rerun after its workers fully exit; Step 04
    # embeddings remain on disk, so no text-encoder repeat is required.
    for port in (12340,12341):
        with socket.socket() as sock:
            sock.settimeout(0.5)
            if sock.connect_ex(('127.0.0.1',port))==0:
                raise RuntimeError('NOTEBOOK_WORKER_PORT_STILL_ACTIVE: '+str(port))
    assert not DIRECT_REPORT.exists(), 'A completed report already exists; verify it first'
    initial_oom=memory_events().get('oom_kill',0)
    print('STARTUP_POLICY', 'load_gpu0_then_gpu1', 'inference_concurrent=true',
              'gguf_source='+gguf_choice['effective_mode'],
          'timeout_per_gpu='+str(STARTUP_PER_GPU_LIMIT_SECONDS),
          'telemetry='+str(telemetry_path),flush=True)
    try:
        # Serial model initialization avoids simultaneous CPU/GGUF decoding.
        # Both workers stay resident and serve concurrent inference afterward.
        for i in (0,1):
            env=VENDOR_ENV.copy()
            env['CUDA_VISIBLE_DEVICES']=str(i)
            # Avoid stale inherited override in direct mode.
            env.pop('ZIMAGE_GGUF_STAGED_PATH', None)
            if gguf_choice['effective_mode']=='local':
                env['ZIMAGE_GGUF_STAGED_PATH']=gguf_choice['staged_override_path']
            started_one=time.monotonic()
            handle=worker_logs[i].open('w')
            worker_handles.append(handle)
            process=subprocess.Popen(
                [sys.executable,'-u',str(worker_probe_script), 'run',
                 str(PROD/'dynamic_worker.py'),
                 '--worker-id',str(i),'--port',str(12340+i),'--manifest',str(MANIFEST_PATH)],
                cwd=PROD,env=env,stdin=subprocess.DEVNULL,
                stdout=handle,stderr=subprocess.STDOUT,start_new_session=True)
            worker_processes.append(process)
            print('NOTEBOOK_WORKER_STARTED','gpu='+str(i),'pid='+str(process.pid),flush=True)
            last_report=started_one-STARTUP_REPORT_INTERVAL_SECONDS
            last_stage=None
            last_stack_sample_at=started_one
            p27_stage_entered_at=started_one
            p27_observed_stage=None
            p27_last_observer_at=started_one-10
            p27_stack_thresholds=set()
            p27_last_gpu_probe_at=started_one-15
            while True:
                if not process_alive(i):
                    raise RuntimeError(f'GPU_{i}_MODEL_STARTUP_FAILED exit={process.returncode}'
                                       f' stage={worker_stage(worker_logs[i])}')
                if worker_ready(i):
                    break
                now=time.monotonic()
                stage=worker_stage(worker_logs[i])
                elapsed=now-started_one
                # P2.7 observational VAE diagnosis; never touches CUDA tensors.
                # This profile is NOT a comparable no-overhead speed benchmark.
                if P27_VAE_STALL_PROFILING:
                    if stage!=p27_observed_stage:
                        p27_observed_stage=stage
                        p27_stage_entered_at=now
                        p27_stack_thresholds=set()
                        p27_last_observer_at=now-10
                    if stage in ('VAE_LOAD_BEGIN','VAE_LOAD_FINISHED'):
                        stage_dwell=now-p27_stage_entered_at
                        if now-p27_last_observer_at>=6:
                            p27_gpu_probe=now-p27_last_gpu_probe_at>=12
                            probe=sample_vae_startup(
                                process.pid,i,stage,stage_dwell,
                                gpu_probe=p27_gpu_probe)
                            if p27_gpu_probe:
                                p27_last_gpu_probe_at=now
                            probe['event']='P27_VAE_STARTUP_OBSERVER'
                            probe['worker_elapsed_seconds']=round(elapsed,2)
                            probe['timestamp_utc']=datetime.now(timezone.utc).isoformat()
                            with telemetry_path.open('a',encoding='utf-8') as sample_file:
                                sample_file.write(json.dumps(probe,sort_keys=True)+'\n')
                            print('P27_VAE_STARTUP_SAMPLE','gpu='+str(i),
                                  'stage='+stage,
                                  'dwell_s='+str(round(stage_dwell,1)),
                                  'wchan='+str(probe['worker_wchan']),
                                  'state='+str(probe['worker_state']),flush=True)
                            p27_last_observer_at=now
                        # Existing faulthandler signal registration is required.
                        # At most twice per stage; no stack or SIGUSR1 on a normal path.
                        for threshold in (12,30):
                            if (process.poll() is None
                                    and stack_request_allowed(
                                        process.pid,stage,stage_dwell,
                                        p27_stack_thresholds,worker_logs[i],threshold)):
                                try:
                                    os.kill(process.pid,signal.SIGUSR1)
                                    p27_stack_thresholds.add((stage,threshold))
                                    print('P27_VAE_STACK_DUMP_REQUESTED',
                                          'gpu='+str(i),'stage='+stage,
                                          'threshold_s='+str(threshold),
                                          'log='+str(worker_logs[i]),flush=True)
                                except ProcessLookupError:
                                    print('P27_WORKER_EXITED_BEFORE_TRACE',i,flush=True)
                if stage!=last_stage or now-last_report>=STARTUP_REPORT_INTERVAL_SECONDS:
                    telemetry=startup_resources(i,elapsed,stage)
                    with telemetry_path.open('a',encoding='utf-8') as f:
                        f.write(json.dumps(telemetry,sort_keys=True)+'\n')
                    print('WORKER_STARTUP_PROGRESS','gpu='+str(i),'stage='+stage,
                          f'elapsed={elapsed:.0f}s','cgroup_bytes='+str(telemetry['cgroup_current_bytes']),
                          'available_ram_kib='+str(telemetry['mem_available_kib']),flush=True)
                    last_report=now
                    last_stage=stage
                    details = telemetry.get('worker_process', {})
                    print('WORKER_PROC_RESOURCE', 'gpu='+str(i),
                          'cpu_pct='+str(details.get('process_cpu_pct_one_core_100')),
                          'rss_bytes='+str(details.get('rss_bytes')),
                          'read_bytes_delta='+str(details.get('read_bytes_delta')),
                          'rchar_delta='+str(details.get('rchar_delta')),
                          'major_faults_delta='+str(details.get('major_faults_delta')),
                          flush=True)
                    if telemetry['cgroup_events'].get('oom_kill',0)>initial_oom:
                        raise MemoryError('CGROUP_OOM_KILL_DURING_MODEL_STARTUP: '+str(telemetry_path))
                if (stage=='GGUF_LOAD_BEGIN' and elapsed>=120 and
                    now-last_stack_sample_at>=120 and
                    'ZIMAGE_GGUF_STACK_PROBE_READY' in worker_logs[i].read_text(errors='replace')):
                    # SIGUSR1 only prints Python stack traces; the worker keeps loading.
                    os.kill(process.pid, signal.SIGUSR1)
                    last_stack_sample_at=now
                    print('GGUF_PYTHON_STACK_DUMP_REQUESTED','gpu='+str(i),
                          'log='+str(worker_logs[i]), flush=True)
                if elapsed>=STARTUP_PER_GPU_LIMIT_SECONDS:
                    raise TimeoutError(f'GPU_{i}_MODEL_STARTUP_TIMEOUT_AFTER_{STARTUP_PER_GPU_LIMIT_SECONDS}s'
                                       f' stage={stage}; telemetry={telemetry_path}')
                time.sleep(3)
            assert 'PIPELINE_READY' in worker_logs[i].read_text(errors='replace'), (
                f'GPU_{i}_READY_WITHOUT_PIPELINE_STAGE')
            model_startup_by_gpu[str(i)]=round(time.monotonic()-started_one,2)
            print('NOTEBOOK_WORKER_READY','gpu='+str(i),
                  'startup_seconds='+str(model_startup_by_gpu[str(i)]),flush=True)
        DIRECT_STARTUP_SECONDS=round(time.monotonic()-started_models,2)
        print('BOTH_MODEL_INSTANCES_READY',
              {'GPU0_PID':worker_processes[0].pid,'GPU1_PID':worker_processes[1].pid,
                'gguf_source':gguf_choice['effective_mode'],
               'startup_seconds':DIRECT_STARTUP_SECONDS,
               'per_gpu_startup_seconds':model_startup_by_gpu},flush=True)
        print('NVIDIA_SMI_ACTIVE_WORKERS',observed_gpu_memory(),flush=True)
        for i in (0,1):
            print('=== NOTEBOOK GPU',i,'MODEL INITIALIZATION EVIDENCE ===',flush=True)
            stages=[line for line in worker_logs[i].read_text(errors='replace').splitlines()
                    if line.startswith('ZIMAGE_WORKER_STAGE ')]
            assert any('PIPELINE_READY' in line for line in stages),'Model pipeline is not ready'
            for line in stages:
                print(line,flush=True)

        if P25_LOAD_ONLY:
            # Strict LOAD-ONLY: only GET /ready was called above. No /generate.
            # The existing worker processes are still terminated by finally below.
            timings=json.loads((DIRECT_ROOT/'encoder-timing.json').read_text())
            report={
                'schema':'ZIMAGE_P25_T4X2_LOAD_ONLY_V1',
                'status':'P25_TWO_GPU_MODELS_READY_NO_IMAGE_GENERATION',
                'benchmark_mode':P25_EXPERIMENT_LABEL,
                'p27_vae_stall_profiling':P27_VAE_STALL_PROFILING,
                'checkpoint_cache_present_at_start':P25_CACHE_AT_START,
                'gpu_inventory':gpus,
                'execution_host':socket.gethostname(),
                'fresh_benchmark_root':str(DIRECT_ROOT),
                'source_sha':info['sha'],
                'inference_fingerprint':DIRECT_INFERENCE_FINGERPRINT,
                'gpu_count':2,'encoder_gpu':0,
                'encoding_seconds':timings['seconds'],
                'gguf_source_selection':gguf_choice,
                'p24_gguf_prefetch':P24_PREFETCH_RESULT,
                'model_startup_seconds':DIRECT_STARTUP_SECONDS,
                'model_startup_seconds_per_gpu':model_startup_by_gpu,
                'startup_telemetry_file':str(telemetry_path),
                'worker_pids':{str(i):worker_processes[i].pid for i in (0,1)},
                'worker_readiness':{str(i):worker_ready(i) for i in (0,1)},
                'cgroup_memory_peak_bytes':read_optional(Path('/sys/fs/cgroup/memory.peak')) if 'read_optional' in globals() else (Path('/sys/fs/cgroup/memory.peak').read_text().strip() if Path('/sys/fs/cgroup/memory.peak').is_file() else None),
                'cgroup_memory_events':memory_events(),
                'png_count':0,'images':[],
                'generate_requests_sent':0,
                'gpu_model_load_verified':True,
                'worker_cleanup_required':True,
                'benchmark_caveat':'OS page cache and staging reuse bias comparisons; no GPU throughput/speedup claim without controlled measurements.',
                'created_utc':datetime.now(timezone.utc).isoformat(),
            }
            assert all(report['worker_readiness'].values())
            assert all('PIPELINE_READY' in worker_logs[i].read_text(errors='replace') for i in (0,1))
            assert not list(DIRECT_ROOT.glob('*.png')), 'NO_PNG_ALLOWED_IN_LOAD_ONLY_ROOT'
            pending=DIRECT_REPORT.with_suffix('.json.tmp')
            pending.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf8')
            os.replace(pending,DIRECT_REPORT)
            print('P25_LOAD_ONLY_TWO_GPU_WORKERS_READY_NO_GENERATION',
                  'report='+str(DIRECT_REPORT),
                  'prefetch='+P25_EXPERIMENT_LABEL,
                  'worker_startup_s='+str(DIRECT_STARTUP_SECONDS),
                  flush=True)
        else:
            # Reuse the repository's verification adapter; requests are issued simultaneously.
            def generate_one(i):
                script = r"""
    import json,sys
    from pathlib import Path
    sys.path.insert(0,sys.argv[1])
    from worker_adapter import WorkerAdapter
    root=Path(sys.argv[2]);project=Path(sys.argv[3]);worker=int(sys.argv[4]);seed=int(sys.argv[5])
    manifest=json.loads((root/'inference-manifest.json').read_text())
    prompts=json.loads((root/'prompts.json').read_text())
    identity=json.loads((root/'encoder-identity.json').read_text())
    from embedding_registry import Registry
    reg=Registry(root/'registry.sqlite3',root/'cache',identity)
    key=reg.key(prompts[worker]);assert key in manifest['entries']
    a=WorkerAdapter(worker,f'http://127.0.0.1:{12340+worker}',project/'output',timeout=920)
    print(json.dumps(a.generate(key,seed),sort_keys=True))
    """
                cmd = [sys.executable,'-c',textwrap.dedent(script),str(PROD),str(DIRECT_ROOT),str(PROJECT),str(i),str(DIRECT_SEEDS[i])]
                # Separate client processes keep driver/CUDA allocations out of the notebook kernel.
                cp = subprocess.run(cmd,env=VENDOR_ENV,capture_output=True,text=True,timeout=950)
                if cp.returncode:
                    raise RuntimeError('GPU_'+str(i)+'_INFERENCE_FAILED: '+cp.stderr[-1200:])
                return json.loads(cp.stdout.strip().splitlines()[-1])

            print('NOTEBOOK_INFERENCE_STARTED gpu0_and_gpu1_concurrent=true', flush=True)
            inference_start = time.monotonic()
            executor = ThreadPoolExecutor(max_workers=2)
            futures = [executor.submit(generate_one,i) for i in (0,1)]
            try:
                next_report=0
                while not all(f.done() for f in futures):
                    if any(not process_alive(i) for i in (0,1)):
                        raise RuntimeError('MODEL_WORKER_EXITED_DURING_RENDER')
                    now=time.monotonic()
                    if now-inference_start > 975:
                        raise TimeoutError('DUAL_GPU_INFERENCE_EXCEEDED_975_SECONDS')
                    if now-next_report >= 20:
                        print('NOTEBOOK_RENDER_PROGRESS',f'elapsed={now-inference_start:.0f}s',
                              'completed='+str(sum(f.done() for f in futures))+'/2',flush=True)
                        next_report=now
                    time.sleep(3)
                generated = [f.result() for f in futures]
            finally:
                executor.shutdown(wait=False,cancel_futures=True)
            DIRECT_INFERENCE_WALL_SECONDS = round(time.monotonic()-inference_start,2)
            artifacts = []
            for i, entry in enumerate(generated):
                assert entry['worker_id'] == i and entry['seed'] == DIRECT_SEEDS[i]
                assert 'PIPELINE_READY' in worker_logs[i].read_text(errors='replace')
                origin = Path(entry['output_path'])
                destination = DIRECT_ROOT / f'zimage-notebook-gpu-{i}-1024.png'
                with PILImage.open(origin) as im:
                    assert im.format=='PNG' and im.size==(1024,1024)
                    im.verify()
                shutil.copyfile(origin,destination)
                digest = hashlib.sha256(destination.read_bytes()).hexdigest()
                assert digest == entry['output_sha256']
                artifacts.append({'gpu':i,'pid':worker_processes[i].pid,'seed':DIRECT_SEEDS[i],
                                  'prompt':DIRECT_PROMPTS[i], 'file':str(destination), 'sha256':digest,
                                  'generation_seconds':entry['seconds'], 'resolution':'1024x1024'})
                print(f'GPU_{i}_PNG_VERIFIED',destination,'render_seconds',entry['seconds'],flush=True)
            timings=json.loads((DIRECT_ROOT/'encoder-timing.json').read_text())
            report={'status':'DUAL_GPU_NOTEBOOK_RENDER_VERIFIED','source_sha':info['sha'],
                    'inference_fingerprint':DIRECT_INFERENCE_FINGERPRINT,
                    'encoder_gpu':0,'encoding_seconds':timings['seconds'],
                    'model_startup_seconds':DIRECT_STARTUP_SECONDS,
                    'model_startup_seconds_per_gpu':model_startup_by_gpu,
                    'gguf_source_selection':gguf_choice,
                    'gguf_source_selection_file':str(selection_file),
                     'p24_gguf_prefetch':P24_PREFETCH_RESULT,
                    'startup_telemetry_file':str(telemetry_path),
                    'parallel_inference_wall_seconds':DIRECT_INFERENCE_WALL_SECONDS,
                    'images':artifacts,'generated_at':datetime.now(timezone.utc).isoformat(),
                    'proof':'Each independent worker reached PIPELINE_READY and returned a SHA256-verified 1024x1024 PNG'}
            temp = DIRECT_REPORT.with_suffix('.json.tmp')
            temp.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
            os.replace(temp,DIRECT_REPORT)
            DIRECT_CACHED_REPORT=report
            DIRECT_SHOULD_RENDER=False
            print('NOTEBOOK_DUAL_GPU_DEMONSTRATION_COMPLETE',DIRECT_REPORT,flush=True)
    except BaseException as error:
        print('NOTEBOOK_GENERATION_ERROR',type(error).__name__,str(error),flush=True)
        for i,p in enumerate(worker_logs):
            if p.exists():
                print('\n=== GPU',i,'WORKER LOG (last 35 lines) ===',flush=True)
                print('\n'.join(p.read_text(errors='replace').splitlines()[-35:]),flush=True)
        raise
    finally:
        for proc in worker_processes:
            if proc.poll() is None:
                os.killpg(proc.pid,signal.SIGTERM)
        for proc in worker_processes:
            try: proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid,signal.SIGKILL)
                proc.wait(timeout=10)
        for handle in worker_handles:
            handle.close()

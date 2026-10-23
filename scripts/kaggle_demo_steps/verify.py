# Diagnostic load-only exporter is disabled for this final inference run.
if P25_LOAD_ONLY:
    import json,sys
    sys.path.insert(0,str(PROJECT/'scripts'))
    from loadonly_evidence import export_loadonly_evidence
    P25_BENCHMARK_PROOF=export_loadonly_evidence(
        report_path=DIRECT_REPORT,
        archive_path=DIRECT_ROOT/'p25-loadonly-evidence.zip',
        source_sha=info['sha'],
        inference_fingerprint=DIRECT_INFERENCE_FINGERPRINT,
        mode=P25_EXPERIMENT_LABEL,
    )
    print('P25_LOAD_ONLY_ACCEPTANCE',json.dumps(P25_BENCHMARK_PROOF,sort_keys=True),flush=True)
    print('P25_BENCHMARK_ZIP',P25_BENCHMARK_PROOF['archive_path'],flush=True)
else:
    from IPython.display import display, HTML
    import base64

    result = direct_previous_result()
    if result is None:
        raise RuntimeError('NO_NOTEBOOK_IMAGES: run Steps 04 and 05. Studio images are not substituted.')
    assert result['status'] == 'DUAL_GPU_NOTEBOOK_RENDER_VERIFIED'
    items=sorted(result['images'],key=lambda x:x['gpu'])
    assert [x['gpu'] for x in items]==[0,1], 'Both GPUs must have a verified image'

    columns=[]
    for x in items:
        data=base64.b64encode(Path(x['file']).read_bytes()).decode('ascii')
        import html
        prompt=html.escape(x['prompt'])
        columns.append(f"""<div style="flex:1;min-width:280px;background:#151b29;color:white;border:1px solid #374151;border-radius:14px;padding:15px">
        <h3 style="margin:0 0 10px">GPU {x['gpu']} · Independent GGUF Q6_K</h3>
        <img src="data:image/png;base64,{data}" style="width:100%;max-width:512px;border-radius:8px" />
        <p><b>1024 × 1024 PNG</b> · Seed {x['seed']} · {x['generation_seconds']} seconds</p>
        <p style="font-size:13px;line-height:1.55">{prompt}</p>
        <small>SHA256: {x['sha256'][:24]}…</small></div>""")
    display(HTML('<div style="display:flex;gap:16px;flex-wrap:wrap">' + ''.join(columns) + '</div>'))
    print('NOTEBOOK_OWN_INFERENCE_PROOF: PASS — 2 independent model processes, 2 verified 1024×1024 images')
    print('NOTEBOOK_IMAGE_PROVENANCE:', 'HASH_VERIFIED_REUSE_FROM_PREVIOUS_RUN' if DIRECT_IMAGES_WERE_REUSED else 'GENERATED_IN_CURRENT_RUN')
    print('Source SHA:',result['source_sha'])
    print('Text encoding on GPU 0:',result['encoding_seconds'],'seconds')
    print('Two model instances startup:',result['model_startup_seconds'],'seconds')
    print('Per-GPU model startup:',result.get('model_startup_seconds_per_gpu','not in older reports'))
    print('Parallel generation wall time:',result['parallel_inference_wall_seconds'],'seconds')
    for x in items:
        print(f"GPU {x['gpu']}: PID {x['pid']}, seed {x['seed']}, generation {x['generation_seconds']}s, SHA256 {x['sha256']}")
    print('Output directory:',DIRECT_ROOT)


    # P2.3 Run All receipt: this stage runs only after the two real PNGs were
    # generated and verified (or marked as verified reuse). No model is loaded here.
    import sys as _p23_sys
    if str(PROJECT / "scripts") not in _p23_sys.path:
        _p23_sys.path.insert(0, str(PROJECT / "scripts"))
    from notebook_runall_acceptance import export_runall_evidence
    P23_EVIDENCE = export_runall_evidence(
        report_path=DIRECT_REPORT,
        output_zip=DIRECT_ROOT / "p23-runall-acceptance.zip",
        source_sha=info["sha"],
        inference_fingerprint=DIRECT_INFERENCE_FINGERPRINT,
        seeds=tuple(DIRECT_SEEDS),
        prompts=tuple(DIRECT_PROMPTS),
        reuse=DIRECT_IMAGES_WERE_REUSED,
    )
    print("P23_RUNALL_ACCEPTANCE", json.dumps(P23_EVIDENCE, sort_keys=True), flush=True)
    display(HTML(
        '<p><b>P2.3 Evidence / Bằng chứng P2.3</b> · '
        + html.escape(P23_EVIDENCE["execution"]) + ' · '
        + html.escape(P23_EVIDENCE["bundle_sha256"][:24]) + '…'
        + '<p><code>' + html.escape(P23_EVIDENCE["bundle"]) + '</code></p>'))

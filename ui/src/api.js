// Calls into Python (window.pywebview.api). In a normal browser (UI work with `npm run dev`) a small fake
// answers, so the pages can be seen without the engine.
let ready;
export function api() {
  if (!ready) ready = new Promise(res => {
    if (window.pywebview?.api) return res(window.pywebview.api);
    const t = setTimeout(() => res(fake()), 1500);
    window.addEventListener('pywebviewready', () => { clearTimeout(t); res(window.pywebview.api); }, { once: true });
  });
  return ready;
}

// call('name', ...args): the result, or throws Error(message) when Python returned {error}
export async function call(name, ...args) {
  const a = await api();
  const r = await a[name](...args);
  if (r && typeof r === 'object' && !Array.isArray(r) && 'error' in r && Object.keys(r).length === 1) throw new Error(r.error);
  return r;
}

function fake() {
  const cfg = { outMode: 'next', outDir: '', format: 'FLAC', mp3Bitrate: '320k', device: 'auto', modelDir: '', model: 'model_bs_roformer_ep_317_sdr_12.9755.ckpt', overwrite: false, custom: [], modelDirUsed: 'C:\\Users\\you\\AppData\\Roaming\\Dubplates Client\\models', appDir: '' };
  const m = (group, file, name, stems, extra = {}) => ({ group, file, name, stems, files: [file], installed: false, arch: 'MDXC', sdr: null, desc: '', suggested: group !== 'all', known: true, ...extra });
  const models = [
    m('vocals', 'model_bs_roformer_ep_317_sdr_12.9755.ckpt', 'BS-Roformer 1297', ['Vocals', 'Instrumental'], { installed: true, badge: 'Start here', sdr: 16.45, desc: 'Vocals + instrumental. Clean and fast. The best all-round model.' }),
    m('vocals', 'melband_roformer_big_beta4.ckpt', 'Mel-Roformer Big Beta 4', ['Vocals', 'Other'], { sdr: 12.52, desc: 'Very clean vocals. Slower and needs more GPU memory.' }),
    m('multi', 'BS-Roformer-SW.ckpt', 'BS-Roformer SW (6 stems)', ['Vocals', 'Drums', 'Bass', 'Guitar', 'Piano', 'Other'], { installed: true, badge: 'Mega-stem', desc: 'Vocals, drums, bass, guitar, piano and other. The best multi-stem model.' }),
    m('multi', 'MDX23C-DrumSep-aufr33-jarredou.ckpt', 'Drum Split', ['Kick', 'Snare', 'Toms', 'Hi-Hat', 'Ride', 'Crash'], { installed: true, desc: 'Splits a drum stem into kick, snare, toms, hi-hat, ride and crash.' }),
    m('multi', 'htdemucs_ft.yaml', 'Demucs v4 Fine-tuned (4 stems)', ['Vocals', 'Drums', 'Bass', 'Other'], { arch: 'Demucs', installed: true, sdr: 12.02, desc: 'Vocals, drums, bass and other. Classic, reliable.' }),
    m('clean', 'dereverb_mel_band_roformer_anvuew_sdr_19.1729.ckpt', 'De-Reverb', ['Noreverb', 'Reverb'], { desc: 'Removes room and reverb. Best on a vocal stem.' }),
    m('all', 'UVR-DeNoise.pth', 'VR Arch Single Model v5: UVR-DeNoise by FoxJoy', ['Noise', 'No Noise'], { arch: 'VR' }),
  ];
  const jobs = [
    { id: 1, name: 'Burial - Archangel.flac', path: 'D:\\Music\\Burial - Archangel.flac', modelName: 'BS-Roformer 1297', state: 'done', pct: 100, msg: 'Done', folder: 'D:\\Music\\Burial - Archangel Stems', stems: [{ name: 'Vocals' }, { name: 'Instrumental' }], secs: 14 },
    { id: 2, name: 'Skream - Midnight Request Line.mp3', path: '', modelName: 'BS-Roformer 1297', state: 'running', pct: 46, msg: 'Making stems…', stems: [], secs: 6 },
    { id: 3, name: 'Mala - Changes.wav', path: '', modelName: 'BS-Roformer 1297', state: 'queued', pct: 0, msg: 'Waiting', stems: [], secs: 0 },
  ];
  const ok = async () => true;
  if (location.search.includes('setup')) {          // preview of the first-start page: http://localhost:5174/?setup
    let pct = 0, on = false;
    return {
      hello: async () => ({ version: '0.1.0 (preview)', platform: 'browser', setup: { gpu: 'NVIDIA GeForce RTX 3080', recommended: 'cuda', options: [{ id: 'cuda', label: 'NVIDIA GPU (fast)', size: 'about 3 GB' }, { id: 'cpu', label: 'CPU only (slow)', size: 'about 300 MB' }] } }),
      setup_start: async () => { on = true; return true; },
      setup_state: async () => { if (on) pct = Math.min(100, pct + 2); return { running: on && pct < 100, done: pct >= 100, error: '', step: pct < 80 ? 'Downloading PyTorch' : 'Installing the stem engine', pct, msg: `torch-2.11.0+cu128-cp311-cp311-win_amd64.whl · ${Math.round(pct * 30)} of 3000 MB`, log: ['> pip install torch==2.11.0 torchaudio==2.11.0', 'Collecting torch==2.11.0'] }; },
      restart: ok, open_url: ok,
    };
  }
  return {
    hello: async () => ({ version: '0.1.0 (preview)', device: { kind: 'cuda', name: 'NVIDIA GeForce RTX 3080', memGB: 10 }, config: cfg, platform: 'browser' }),
    state: async () => { const j = jobs[1]; if (j.pct < 100) j.pct = Math.min(99, j.pct + 1.5); return { jobs, installs: {} }; },
    models: async () => models, install: ok, cancel_install: ok, remove: ok, add_custom: async () => ({ error: 'Not in preview' }),
    add_jobs: async p => ({ added: p.length }), cancel_job: ok, clear_jobs: ok,
    set_config: async p => Object.assign(cfg, p), pick_files: async () => [], pick_folder: async () => '', pick_model_file: async () => '',
    open_path: ok, open_url: async u => { window.open(u, '_blank'); return true; },
  };
}

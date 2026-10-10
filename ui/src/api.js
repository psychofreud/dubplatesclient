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
  const cfg = { outMode: 'next', outDir: '', layoutChosen: false, skipDone: true, format: 'FLAC', mp3Bitrate: '320k', device: 'auto', modelDir: '', model: 'model_bs_roformer_ep_317_sdr_12.9755.ckpt', overwrite: false, custom: [], modelDirUsed: 'C:\\Users\\you\\AppData\\Roaming\\Dubplates Client\\models', appDir: '' };
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
    state: async () => { if (location.search.includes('shot')) return { jobs: [], installs: {} }; const qs = { total: 342, done: 120, skipped: 12, error: 1, queued: 208, running: true, paused: false, eta: 7400 }; const j = jobs[1]; if (j.pct < 100) j.pct = Math.min(99, j.pct + 1.5); return { jobs, installs: {}, queue: qs }; },
    models: async () => models, install: ok, cancel_install: ok, remove: ok, add_custom: async () => ({ error: 'Not in preview' }),
    add_jobs: async p => ({ added: p.length }), cancel_job: ok, clear_jobs: ok,
    set_config: async p => Object.assign(cfg, p), pick_files: async () => [], pick_folder: async () => '', pick_model_file: async () => '',
    open_path: ok, open_url: async u => { window.open(u, '_blank'); return true; },
    pending_link: async () => (location.search.includes('link') ? { action: 'separate', root: 'Music', path: 'Dub/King Tubby - Dub Fi Gwan.mp3', name: 'King Tubby - Dub Fi Gwan.mp3', needRoot: location.search.includes('root') } : null),
    set_root: async () => ({ file: 'D:\\Music\\Dub\\King Tubby - Dub Fi Gwan.mp3' }),
    library: async () => [
      { id: 'l1', folder: 'D:\\Music\\Burial - Archangel Stems', name: 'Burial - Archangel', created: '2026-10-09T14:12:00', model: 'BS-Roformer SW (6 stems)', stems: ['Vocals', 'Drums', 'Bass', 'Guitar', 'Piano', 'Other'], parts: 6, missing: false, added: 3 },
      { id: 'l2', folder: 'D:\\Music\\Mala - Changes Stems', name: 'Mala - Changes', created: '2026-10-08T21:40:00', model: 'BS-Roformer 1297', stems: ['Vocals', 'Instrumental'], parts: 0, missing: false, added: 2 },
      { id: 'l3', folder: 'E:\\Old\\Skream Stems', name: 'Skream - Midnight Request Line', created: '2026-10-01', model: 'Demucs v4', stems: ['Vocals', 'Drums', 'Bass', 'Other'], parts: 0, missing: true, added: 1 }],
    library_detail: async () => ({ id: 'l1', folder: 'D:/Music/Burial - Archangel Stems', sourceFile: 'D:/Music/Burial - Archangel.flac', media: null,
      meta: { created: '2026-10-09T14:12:00', model: { name: 'BS-Roformer SW (6 stems)' }, source: { name: 'Burial - Archangel.flac' },
        stems: ['Vocals', 'Drums', 'Bass', 'Guitar', 'Piano', 'Other'].map(n => ({ name: n, file: `Burial - Archangel - ${n}.flac`, ...(n === 'Drums' ? { parts: ['Kick', 'Snare', 'Toms', 'Hi-Hat', 'Ride', 'Crash'].map(p => ({ name: p, file: `Drums parts/x - ${p}.flac` })) } : {}) })) } }),
    peaks: async path => { let s = 0; for (const ch of path) s = (s * 31 + ch.charCodeAt(0)) % 9973; const rnd = () => { s = (s * 16807) % 2147483647; return s / 2147483647; };
      const env = 0.3 + rnd() * 0.6; return { dur: 238, peaks: Array.from({ length: 1600 }, (_, i) => { const a = env * (0.35 + 0.65 * Math.abs(Math.sin(i / (20 + rnd() * 3)))) * (0.6 + rnd() * 0.4) * (i > 1500 ? (1600 - i) / 100 : 1); return [-a, a]; }) }; },
    preview_add: async (paths, mode, outDir) => { const d = mode === 'next' || !outDir ? 'D:\\Music\\Dub' : (mode === 'mirror' ? outDir + '\\Dub' : outDir);
      return { count: 342, folders: 18, structure: 'shared', have: 12, examples: ['King Tubby - Dub Fi Gwan', 'Scientist - Plague of Zombies', 'Mala - Alicia', 'Burial - Archangel'].map(n => ({ src: 'D:\\Music\\Dub\\' + n + '.mp3', out: d + '\\' + n + ' Stems' })) }; },
    pause_queue: ok, cancel_all: ok,
    fx_catalog: async () => ({ order: ['bleed', 'repair', 'hpf', 'gate', 'comp', 'eq', 'lpf', 'limit', 'gain'], chains: ['Natural cleanup', 'Vocal polish', 'Tight drums', 'Solid bass', 'Wide & airy', 'Lo-fi'], suggest: { vocals: 'Vocal polish' },
      vsts: [{ name: 'ValhallaSupermassive', path: 'x' }, { name: 'kHs Compressor', path: 'y' }, { name: 'Ozone 11 Equalizer', path: 'z' }],
      modules: { bleed: { title: 'Bleed reduction', text: '', params: [['amount', 'Amount', 0, 100, '%', 50], ['floor', 'Floor', -60, -6, 'dB', -30]], presets: { Light: {}, Medium: {}, Strong: {} } },
        repair: { title: 'Repair', text: '', params: [['denoise', 'De-noise', 0, 100, '%', 40], ['declick', 'De-click', 0, 100, '%', 40], ['floor', 'Floor', -40, -6, 'dB', -20]], presets: { Light: {}, Medium: {}, Heavy: {} } },
        hpf: { title: 'High-pass', text: '', params: [['freq', 'Cut', 20, 1000, 'Hz', 40]], presets: { Rumble: {}, Vocal: {} } },
        gate: { title: 'Gate', text: '', params: [['threshold', 'Thresh', -80, 0, 'dB', -45], ['range', 'Range', -80, 0, 'dB', -40], ['release', 'Release', 10, 1000, 'ms', 120]], presets: { Gentle: {}, Tight: {} } },
        comp: { title: 'Compression', text: '', params: [['threshold', 'Thresh', -60, 0, 'dB', -18], ['ratio', 'Ratio', 1, 20, ':1', 3], ['attack', 'Attack', 0.1, 100, 'ms', 10], ['makeup', 'Makeup', 0, 24, 'dB', 3]], presets: { Glue: {}, Vocal: {} } },
        eq: { title: 'EQ', text: '', params: [['f1', 'Low Hz', 20, 500, 'Hz', 80], ['g1', 'Low', -18, 18, 'dB', 0], ['f2', 'Mid 1 Hz', 100, 4000, 'Hz', 400], ['g2', 'Mid 1', -18, 18, 'dB', 2], ['f3', 'Mid 2 Hz', 500, 12000, 'Hz', 3200], ['g3', 'Mid 2', -18, 18, 'dB', 4], ['f4', 'High Hz', 2000, 18000, 'Hz', 11000], ['g4', 'High', -18, 18, 'dB', 2.5]], presets: { Flat: {}, Presence: {} } },
        lpf: { title: 'Low-pass', text: '', params: [['freq', 'Cut', 1000, 20000, 'Hz', 16000]], presets: {} }, limit: { title: 'Limiter', text: '', params: [['ceiling', 'Ceiling', -12, 0, 'dB', -1], ['release', 'Release', 10, 1000, 'ms', 100]], presets: {} }, gain: { title: 'Gain', text: '', params: [['db', 'Gain', -24, 24, 'dB', 0]], presets: {} } } }),
    fx_chain: async () => ({ applied: false, original: false, chain: [{ type: 'repair', on: true, p: { denoise: 55, declick: 50, floor: -20 } }, { type: 'bleed', on: true, p: { amount: 55, floor: -30 } }, { type: 'gate', on: true, p: { threshold: -50, range: -20, release: 250 } }, { type: 'comp', on: true, p: { threshold: -24, ratio: 4, attack: 5, makeup: 6 } }, { type: 'eq', on: true, p: { f1: 90, g1: -2, f2: 350, g2: -1.5, f3: 3200, g3: 4, f4: 11000, g4: 2.5 } }, { type: 'vst', on: true, name: 'ValhallaSupermassive', path: 'x', state: {} }] }),
    fx_module: async k => ({ type: k, on: true, p: {} }), fx_preset: async () => [], fx_preview: async () => ({ media: null }), fx_apply: ok, fx_restore: ok,
    vst_params: async () => ({ mix: { value: 0.5, min: 0, max: 1, label: '%' }, delay_ms: { value: 120, min: 0, max: 1000, label: 'ms' }, feedback: { value: 0.4, min: 0, max: 1, label: '' }, density: { value: 0.6, min: 0, max: 1, label: '' } }),
    library_add: async () => ({ cancelled: true }), library_remove: ok, stem_work: async () => ({ job: 9 }),
    site_link: async () => ({ connected: !location.search.includes('nosite') }), send_deck: async () => ({ sent: 1 }),
    plugins: async () => ({ dir: 'C:\\Users\\you\\AppData\\Roaming\\Dubplates Client\\plugins', saved: { vocal_repair: { reference: 'D:\\Vocals\\clean studio vocal.flac', ml: true } }, items: [
      { id: 'vocal_repair', name: 'Vocal repair', version: '1.0', author: 'Anders', for: ['vocals'], packages: location.search.includes('nopkg') ? 'missing' : 'ok', problem: '', ready: !location.search.includes('nopkg'), modelsState: location.search.includes('nopkg') ? 'missing' : 'ok',
        models: [{ file: '.models/dereverb_roformer.onnx', name: 'Mel-Roformer De-Reverb', size: 918257906, have: !location.search.includes('nopkg') }, { file: '.models/dereverb_vr.onnx', name: 'UVR DeEcho-DeReverb', size: 223235642, have: !location.search.includes('nopkg') }], dir: 'C:\\Users\\you\\AppData\\Roaming\\Dubplates Client\\plugins\\vocal_repair',
        description: 'Repairs an AI-made vocal: removes artificial reverb, noise and harsh tone. A clean studio vocal (from any song) is the quality target. Same length and loudness, so it replaces the stem in place.',
        time: 'About 70 s per song on a good GPU (DirectX 12), about 15 times longer on the CPU. Needs about 6.5 GB of GPU memory.',
        inputs: [{ id: 'reference', type: 'audio', label: 'Reference vocal', remember: true, help: 'A clean, dry studio vocal (any song, any words). The plugin learns from it how a good recording sounds.' }],
        options: [{ id: 'ml', type: 'bool', label: 'ML dereverb (recommended)', default: true }, { id: 'mono', type: 'bool', label: 'Mono output', default: false }] }] }),
    plugin_catalog: async () => ({ canInstall: true, items: [{ id: 'crowd_cut', name: 'Crowd cut', version: '1.0', author: 'Anders', for: ['vocals'], description: 'Removes crowd noise and claps from a live recording stem.', size: 48000, models: [{ file: '.models/crowd.onnx', name: 'Crowd model', size: 210000000 }], installed: null, newer: false }] }), plugin_get: ok,
    plugin_install: ok, plugin_add: async () => ({ cancelled: true }), plugin_folder: ok, plugin_run: async () => ({ job: 10 }), pick_audio: async () => '',
    check_update: async () => (location.search.includes('shot') ? { newer: false } : { current: '0.1.1', latest: '0.1.2', newer: true, url: 'https://github.com/psychofreud/dubplatesclient/releases/' }),
  };
}

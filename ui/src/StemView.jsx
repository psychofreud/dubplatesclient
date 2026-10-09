// One stem set: the original and every stem as a waveform; play them together, mute / solo, click to jump.
// Parts (drum split) and results of "more work" show under their stem.
// Audio: one <audio> per lane from the client's local media URL (low memory), kept in step with one clock.
// Waveforms: peaks from Python (api.peaks), cached on disk.
import React from 'react';
import { call } from './api.js';
import ModelPicker from './ModelPicker.jsx';
import { stemHue } from './ui.jsx';
import { IcFolder, IcStems } from './icons.jsx';

const fmt = s => { s = Math.max(0, s || 0); return `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`; };

export default function StemView({ id, models, jobs, say }) {
  const [d, setD] = React.useState(null);
  const [err, setErr] = React.useState('');
  const [peaks, setPeaks] = React.useState({});
  const [mute, setMute] = React.useState({ src: true });
  const [solo, setSolo] = React.useState({});
  const [open, setOpen] = React.useState({});
  const [playing, setPlaying] = React.useState(false);
  const [work, setWork] = React.useState(null);           // {stem, model}
  const [dur, setDur] = React.useState(0);
  const audio = React.useRef({}), clock = React.useRef({ t0: 0, pos: 0, on: false }), heads = React.useRef([]), timeEl = React.useRef(null);

  const load = React.useCallback(() => call('library_detail', id).then(setD).catch(e => setErr(e.message)), [id]);
  React.useEffect(() => { load(); }, [load]);
  // more work on a stem of this set finished: show its result
  const doneKey = jobs.filter(j => j.kind === 'stem' && j.state === 'done' && d && j.path === d.folder).map(j => j.id).join(',');
  React.useEffect(() => { if (doneKey) load(); }, [doneKey]);  // eslint-disable-line react-hooks/exhaustive-deps

  // the lanes: original, stems, and under each stem its parts / results
  const lanes = React.useMemo(() => {
    if (!d) return [];
    const f = rel => d.folder + '/' + rel, out = [];
    if (d.sourceFile) out.push({ key: 'src', name: 'Original', path: d.sourceFile, depth: 0, kids: 0 });
    for (const s of d.meta.stems) {
      const kids = [...(s.parts || []).map(p => ({ key: s.name + '/' + p.name, name: p.name, path: f(p.file), from: 'Drum split' })),
        ...(s.derived || []).flatMap(x => (x.stems || []).map(p => ({ key: s.name + '/' + x.name + '/' + p.name, name: p.name, path: f(p.file), from: x.name })))];
      out.push({ key: s.name, name: s.name, path: f(s.file), depth: 0, kids: kids.length });
      if (open[s.name]) kids.forEach(k => out.push({ ...k, depth: 1, parent: s.name }));
    }
    return out;
  }, [d, open]);

  // waveforms
  React.useEffect(() => {
    lanes.forEach(l => {
      if (peaks[l.path]) return;
      call('peaks', l.path).then(p => { setPeaks(x => ({ ...x, [l.path]: p })); setDur(v => Math.max(v, p.dur)); }).catch(() => {});
    });
  }, [lanes]);  // eslint-disable-line react-hooks/exhaustive-deps

  // audio elements: one per lane that is shown
  React.useEffect(() => {
    if (!d || !d.media) return;
    const a = audio.current;
    lanes.forEach(l => { if (!a[l.key]) { const el = new Audio(d.media + encodeURIComponent(l.path)); el.preload = 'auto'; a[l.key] = el; } });
    Object.keys(a).forEach(k => { if (!lanes.find(l => l.key === k)) { a[k].pause(); delete a[k]; } });
  }, [lanes, d]);
  React.useEffect(() => () => { Object.values(audio.current).forEach(el => { el.pause(); el.src = ''; }); }, []);

  const audible = React.useCallback(k => {
    const anySolo = Object.values(solo).some(Boolean);
    const l = lanes.find(x => x.key === k);
    if (anySolo) return !!solo[k] || (l && l.parent && !!solo[l.parent] && !lanes.some(x => x.parent === l.parent && solo[x.key]));
    return !mute[k];
  }, [solo, mute, lanes]);
  React.useEffect(() => { Object.entries(audio.current).forEach(([k, el]) => { el.muted = !audible(k); }); }, [audible, lanes]);

  const now = () => (clock.current.on ? (performance.now() - clock.current.t0) / 1000 : clock.current.pos);
  const seek = t => {
    t = Math.max(0, Math.min(dur || 0, t)); clock.current.pos = t;
    if (clock.current.on) clock.current.t0 = performance.now() - t * 1000;
    Object.values(audio.current).forEach(el => { try { el.currentTime = t; } catch { /* */ } });
  };
  const play = async () => {
    const t = clock.current.pos >= dur - 0.05 ? 0 : clock.current.pos;
    Object.values(audio.current).forEach(el => { el.currentTime = t; });
    await Promise.all(Object.values(audio.current).map(el => el.play().catch(() => {})));
    clock.current = { t0: performance.now() - t * 1000, pos: t, on: true }; setPlaying(true);
  };
  const pause = () => { clock.current = { ...clock.current, pos: now(), on: false }; Object.values(audio.current).forEach(el => el.pause()); setPlaying(false); };
  // the play head + keep every lane in step with the clock
  React.useEffect(() => {
    let raf, n = 0;
    const tick = () => {
      const t = now();
      if (clock.current.on && dur && t >= dur) { pause(); seek(0); }
      heads.current.forEach(h => { if (h) h.style.left = (dur ? (t / dur) * 100 : 0) + '%'; });
      if (timeEl.current) timeEl.current.textContent = `${fmt(t)} / ${fmt(dur)}`;
      if (clock.current.on && ++n % 15 === 0) Object.values(audio.current).forEach(el => { if (Math.abs(el.currentTime - t) > 0.06 && el.readyState > 2) el.currentTime = t; });
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [dur]);  // eslint-disable-line react-hooks/exhaustive-deps
  React.useEffect(() => {
    const k = e => { if (e.code === 'Space' && !/INPUT|SELECT|TEXTAREA/.test(e.target.tagName)) { e.preventDefault(); clock.current.on ? pause() : play(); } };
    window.addEventListener('keydown', k); return () => window.removeEventListener('keydown', k);
  });

  if (err) return <div className="lib-pick err">{err}</div>;
  if (!d) return <div className="lib-pick"><span className="spin" /> Opening…</div>;
  const m = d.meta, installed = models.filter(x => x.installed);
  const busy = jobs.filter(j => j.kind === 'stem' && j.path === d.folder && ['queued', 'running'].includes(j.state));
  const runWork = async () => {
    try { await call('stem_work', id, work.stem, work.model); say(`${work.stem}: ${installed.find(x => x.file === work.model)?.name} added to the queue`, 'ok'); setWork(null); } catch (e) { say(e.message, 'err'); }
  };
  heads.current = [];

  return (
    <div className="sv">
      <div className="sv-head">
        <div className="sv-title">
          <h2>{(m.source?.name || '').replace(/\.[^.]+$/, '') || d.folder.split(/[\\/]/).pop()}</h2>
          <small>{m.stems.length} stems · {m.model?.name} · {(m.created || '').slice(0, 16).replace('T', ' ')}</small>
        </div>
        <button className="btn sm" onClick={() => call('open_path', d.folder)}><IcFolder size={14} /> Folder</button>
      </div>
      <div className="sv-transport">
        <button className="btn pri play" onClick={() => (playing ? pause() : play())} title="Play / pause (Space)">{playing ? '❚❚' : '▶'}</button>
        <span className="mono sv-time" ref={timeEl}>0:00 / {fmt(dur)}</span>
        <span className="dim sv-hint">Click a waveform to jump · M mute · S solo · Space play</span>
      </div>
      <div className="sv-lanes">
        {lanes.map(l => {
          const p = peaks[l.path], on = audible(l.key), hue = l.key === 'src' ? null : stemHue(l.name), job = busy.find(j => j.stem === l.name);
          return (
            <div key={l.key} className={'sv-lane' + (on ? '' : ' off') + (l.depth ? ' kid' : '') + (l.key === 'src' ? ' src' : '')} style={{ '--h': hue ?? 62 }}>
              <div className="sv-ctl">
                <div className="sv-name" title={l.from ? `${l.from}: ${l.name}` : l.name}>
                  {l.kids > 0 && <button className="sv-tw" onClick={() => setOpen(o => ({ ...o, [l.key]: !o[l.key] }))} title={open[l.key] ? 'Hide the parts' : 'Show the parts'}>{open[l.key] ? '▾' : '▸'}</button>}
                  <b>{l.name}</b>{l.kids > 0 && <em>{l.kids}</em>}
                </div>
                <div className="sv-btns">
                  <button className={'ms' + (mute[l.key] ? ' on' : '')} onClick={() => setMute(x => ({ ...x, [l.key]: !x[l.key] }))} title="Mute">M</button>
                  <button className={'ms s' + (solo[l.key] ? ' on' : '')} onClick={() => setSolo(x => ({ ...x, [l.key]: !x[l.key] }))} title="Solo">S</button>
                  {l.depth === 0 && l.key !== 'src' && <button className="ms more" onClick={() => setWork({ stem: l.name, model: work?.model || installed[0]?.file })} title="More work on this stem: run another model on it">＋</button>}
                </div>
                {job && <div className="sv-job"><div className="bar"><i style={{ width: Math.max(3, job.pct) + '%' }} /></div><small>{job.modelName} {Math.round(job.pct)}%</small></div>}
              </div>
              <div className="sv-wave" onPointerDown={e => { const r = e.currentTarget.getBoundingClientRect(); seek(((e.clientX - r.left) / r.width) * dur); }}>
                {p ? <Wave peaks={p.peaks} scale={dur ? p.dur / dur : 1} /> : <div className="sv-load" />}
                <i className="sv-head" ref={el => heads.current.push(el)} />
              </div>
            </div>
          );
        })}
      </div>
      {work && (
        <div className="modal-bg" onMouseDown={e => { if (e.target === e.currentTarget) setWork(null); }}>
          <div className="card modal">
            <h2><IcStems size={18} /> More work on “{work.stem}”</h2>
            <p className="sub">Run another model on this stem: for example De-Reverb on Vocals, or Drum Split on Drums. The result shows under the stem. (Filters and VST effects come here later.)</p>
            <label className="lbl">Model</label>
            <ModelPicker models={installed} value={work.model} onChange={v => setWork({ ...work, model: v })} />
            <div className="modal-btns"><button className="btn pri" disabled={!work.model} onClick={runWork}>Run</button><button className="btn ghost" onClick={() => setWork(null)}>Cancel</button></div>
          </div>
        </div>
      )}
    </div>
  );
}

// a waveform from [min, max] pairs: drawn to fit the canvas (sharp on high-DPI screens)
function Wave({ peaks, scale }) {
  const ref = React.useRef(null);
  React.useEffect(() => {
    const c = ref.current; if (!c) return;
    const draw = () => {
      const w = c.clientWidth, h = c.clientHeight, dpr = window.devicePixelRatio || 1;
      c.width = w * dpr; c.height = h * dpr;
      const g = c.getContext('2d'); g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, w, h);
      const col = getComputedStyle(c).color, ww = w * Math.min(1, scale), n = peaks.length, mid = h / 2;
      let top = 0; for (const [a, b] of peaks) top = Math.max(top, -a, b);
      const k = top > 0 ? (mid - 2) / Math.max(top, 0.05) : 0;
      g.fillStyle = col;
      for (let x = 0; x < ww; x++) {
        const [a, b] = peaks[Math.min(n - 1, Math.floor((x / ww) * n))];
        const y1 = mid - b * k, y2 = mid - a * k;
        g.fillRect(x, y1, 1, Math.max(1, y2 - y1));
      }
    };
    draw();
    const ro = new ResizeObserver(draw); ro.observe(c);
    return () => ro.disconnect();
  }, [peaks, scale]);
  return <canvas ref={ref} className="sv-canvas" />;
}

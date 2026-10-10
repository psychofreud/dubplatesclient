// One stem set: the original and every stem as a waveform; play them together, mute / solo, click to jump.
// Parts (drum split) and results of "more work" show under their stem.
// Audio: one <audio> per lane from the client's local media URL (low memory). The first playing lane is the clock;
// the others follow it with a very small speed change (no jumps: jumps on many players at once sound like noise).
// Waveforms: peaks from Python (api.peaks), cached on disk.
import React from 'react';
import { call } from './api.js';
import ModelPicker from './ModelPicker.jsx';
import FxPanel from './FxPanel.jsx';
import PluginRun from './PluginRun.jsx';
import { stemHue } from './ui.jsx';
import { IcFolder, IcStems } from './icons.jsx';

const fmt = s => { s = Math.max(0, s || 0); return `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`; };

export default function StemView({ id, models, jobs, say, go }) {
  const [d, setD] = React.useState(null);
  const [err, setErr] = React.useState('');
  const [peaks, setPeaks] = React.useState({});
  const [mute, setMute] = React.useState({ src: true });
  const [solo, setSolo] = React.useState({});
  const [open, setOpen] = React.useState({});
  const [playing, setPlaying] = React.useState(false);
  const [work, setWork] = React.useState(null);           // {stem, model, tab: 'model' | 'plugin'}
  const [plugins, setPlugins] = React.useState(null);
  const [site, setSite] = React.useState({ connected: false });   // a dubplates.net mixer is open (Send to deck)
  const [dur, setDur] = React.useState(0);
  const [fxStem, setFxStem] = React.useState(null);      // the effects panel is open for this stem
  const audio = React.useRef({}), clock = React.useRef({ t0: 0, pos: 0, on: false }), heads = React.useRef([]), timeEl = React.useRef(null);

  const load = React.useCallback(() => call('library_detail', id).then(setD).catch(e => setErr(e.message)), [id]);
  React.useEffect(() => { load(); }, [load]);
  // more work on a stem of this set finished: show its result
  const doneKey = jobs.filter(j => ['stem', 'fx', 'plugin'].includes(j.kind) && j.state === 'done' && d && j.path === d.folder).map(j => j.id).join(',');
  const refresh = React.useCallback(() => {        // a stem file changed (effects applied / restored): new waveform and audio
    setPeaks({}); Object.values(audio.current).forEach(el => { el.pause(); el.src = ''; }); audio.current = {}; load();
  }, [load]);
  React.useEffect(() => { if (doneKey) refresh(); }, [doneKey]);  // eslint-disable-line react-hooks/exhaustive-deps

  React.useEffect(() => {
    let on = true; const ask = () => call('site_link').then(r => on && setSite(r)).catch(() => {});
    ask(); const t = setInterval(ask, 3000); return () => { on = false; clearInterval(t); };
  }, []);
  const sendDeck = async D => {
    try { await call('send_deck', id, D); say(`Sent to deck ${D} on dubplates.net`, 'ok'); } catch (e) { say(e.message, 'err'); }
  };
  const openWork = async (stem, tab) => {
    setWork({ stem, model: work?.model || installed[0]?.file, tab });
    try { setPlugins(await call('plugins')); } catch (e) { say(e.message, 'err'); }
  };

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
    lanes.forEach(l => { if (!a[l.key]) { const el = new Audio(d.media + encodeURIComponent(l.path)); el.preload = 'auto'; el.preservesPitch = false; a[l.key] = el; } });
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

  // the clock: the first lane that plays (its sound card clock); before it plays: the time since Play
  const master = () => Object.values(audio.current).find(el => !el.paused && el.readyState > 2 && !el.seeking);
  const now = () => {
    if (!clock.current.on) return clock.current.pos;
    const m = master();
    return m ? m.currentTime : (performance.now() - clock.current.t0) / 1000;
  };
  const seek = t => {
    t = Math.max(0, Math.min(dur || 0, t)); clock.current.pos = t;
    if (clock.current.on) clock.current.t0 = performance.now() - t * 1000;
    Object.values(audio.current).forEach(el => { try { el.currentTime = t; el.playbackRate = 1; } catch { /* */ } });
  };
  const play = async () => {
    const t = clock.current.pos >= dur - 0.05 ? 0 : clock.current.pos;
    Object.values(audio.current).forEach(el => { el.currentTime = t; el.playbackRate = 1; });
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
      if (clock.current.on && ++n % 6 === 0) {
        const m = master();
        if (m) clock.current.t0 = performance.now() - m.currentTime * 1000;
        Object.values(audio.current).forEach(el => {
          if (el === m || el.readyState < 3 || el.seeking) return;
          if (el.paused) { el.currentTime = t; el.play().catch(() => {}); return; }   // (a lane that stopped: start it again)
          const off = el.currentTime - t;
          if (Math.abs(off) > 0.3) { el.currentTime = t; el.playbackRate = 1; }      // far off: jump (rare)
          else el.playbackRate = Math.abs(off) < 0.012 ? 1 : 1 - Math.max(-0.03, Math.min(0.03, off * 0.6));
        });
      }
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
  const busy = jobs.filter(j => ['stem', 'fx', 'plugin'].includes(j.kind) && j.path === d.folder && ['queued', 'running'].includes(j.state));
  const runWork = async () => {
    try { await call('stem_work', id, work.stem, work.model); say(`${work.stem}: ${installed.find(x => x.file === work.model)?.name} added to the queue`, 'ok'); setWork(null); } catch (e) { say(e.message, 'err'); }
  };
  heads.current = [];
  const fxOn = name => !!(m.stems.find(s => s.name === name) || {}).fx;
  const plugOf = name => (m.stems.find(s => s.name === name) || {}).plugin;

  return (
    <div className="sv">
      <div className="sv-head">
        <div className="sv-title">
          <h2>{(m.source?.name || '').replace(/\.[^.]+$/, '') || d.folder.split(/[\\/]/).pop()}</h2>
          <small>{m.stems.length} stems · {m.model?.name} · {(m.created || '').slice(0, 16).replace('T', ' ')}</small>
        </div>
        <div className="sv-send" title={site.connected ? 'Load these stems into a deck of the dubplates.net mixer that is open in your browser' : 'Open the dubplates.net mixer (signed in) in your browser on this computer, then send the stems to a deck'}>
          <span className={'sv-site' + (site.connected ? ' on' : '')}>{site.connected ? 'dubplates.net' : 'dubplates.net not open'}</span>
          {['A', 'B'].map(D => <button key={D} className={'btn sm deck d' + D} disabled={!site.connected} onClick={() => sendDeck(D)}>Deck {D}</button>)}
        </div>
        <button className="btn sm" onClick={() => call('open_path', d.folder)}><IcFolder size={14} /> Folder</button>
      </div>
      <div className="sv-transport">
        <button className="btn pri play" onClick={() => (playing ? pause() : play())} title="Play / pause (Space)">{playing ? '❚❚' : '▶'}</button>
        <span className="mono sv-time" ref={timeEl}>0:00 / {fmt(dur)}</span>
        <span className="dim sv-hint">Click a waveform to jump · M mute · S solo · Space play</span>
      </div>
      {fxStem && <FxPanel key={fxStem} id={id} stem={fxStem} pos={now} say={say} onPlaying={on => { if (on) pause(); }} onClose={changed => { setFxStem(null); if (changed) refresh(); }} />}
      <div className="sv-lanes">
        {lanes.map(l => {
          const p = peaks[l.path], on = audible(l.key), hue = l.key === 'src' ? null : stemHue(l.name), job = busy.find(j => j.stem === l.name);
          return (
            <div key={l.key} className={'sv-lane' + (on ? '' : ' off') + (l.depth ? ' kid' : '') + (l.key === 'src' ? ' src' : '')} style={{ '--h': hue ?? 62 }}>
              <div className="sv-ctl">
                <div className="sv-name" title={l.from ? `${l.from}: ${l.name}` : l.name}>
                  {l.kids > 0 && <button className="sv-tw" onClick={() => setOpen(o => ({ ...o, [l.key]: !o[l.key] }))} title={open[l.key] ? 'Hide the parts' : 'Show the parts'}>{open[l.key] ? '▾' : '▸'}</button>}
                  <b>{l.name}</b>{l.kids > 0 && <em>{l.kids}</em>}
                  {l.depth === 0 && plugOf(l.name) && (p => <span className="sv-plug" title={`${p.name}${p.warnings?.length ? ': ' + p.warnings.join(' · ') : ''}`}>{p.name}{p.warnings?.length ? ' ⚠' : ''}</span>)(plugOf(l.name))}
                </div>
                <div className="sv-btns">
                  <button className={'ms' + (mute[l.key] ? ' on' : '')} onClick={() => setMute(x => ({ ...x, [l.key]: !x[l.key] }))} title="Mute">M</button>
                  <button className={'ms s' + (solo[l.key] ? ' on' : '')} onClick={() => setSolo(x => ({ ...x, [l.key]: !x[l.key] }))} title="Solo">S</button>
                  {l.depth === 0 && l.key !== 'src' && <button className={'ms fxb' + (fxStem === l.name ? ' on' : '') + (fxOn(l.name) ? ' has' : '')} onClick={() => setFxStem(fxStem === l.name ? null : l.name)} title="Effects on this stem (filters, dynamics, EQ, VST plugins)">FX</button>}
                  {l.depth === 0 && l.key !== 'src' && <button className="ms more" onClick={() => openWork(l.name, 'model')} title="More work on this stem: another model, or a plugin">＋</button>}
                </div>
                {job && <div className="sv-job"><div className="bar"><i style={{ width: Math.max(3, job.pct) + '%' }} /></div><small>{job.modelName} {job.state === 'queued' ? 'waiting' : Math.round(job.pct) + '%'}</small></div>}
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
            <div className="seg">
              <button className={work.tab === 'model' ? 'on' : ''} onClick={() => setWork({ ...work, tab: 'model' })}>Another model</button>
              <button className={work.tab === 'plugin' ? 'on' : ''} onClick={() => setWork({ ...work, tab: 'plugin' })}>Plugin{plugins?.items?.length ? ` (${plugins.items.length})` : ''}</button>
            </div>
            {work.tab === 'model' ? <>
              <p className="sub">Run another model on this stem: for example De-Reverb on Vocals, or Drum Split on Drums. The result shows under the stem.</p>
              <label className="lbl">Model</label>
              <ModelPicker models={installed} value={work.model} onChange={v => setWork({ ...work, model: v })} />
              <div className="modal-btns"><button className="btn pri" disabled={!work.model} onClick={runWork}>Run</button><button className="btn ghost" onClick={() => setWork(null)}>Cancel</button></div>
            </> : plugins ? <PluginRun id={id} stem={work.stem} list={plugins} say={say} go={(p, s) => { setWork(null); go && go(p, s); }} onDone={() => setWork(null)} />
              : <div className="lib-pick"><span className="spin" /> Reading the plugins…</div>}
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

// Effects on one stem: a chain of modules (Bleed reduction, Repair, Gate, Compression, EQ…) and VST3 plugins.
// Preview: 20 s from the play head, with and without the chain (A/B). Apply: the whole stem is rendered and the file
// replaced (the original stays in .originals/, "Restore original" puts it back). Runs in the queue (progress there).
import React from 'react';
import { call } from './api.js';
import { IcX, IcPlus, IcSearch } from './icons.jsx';

const fmtV = (v, unit) => (unit === 'Hz' ? (v >= 1000 ? (v / 1000).toFixed(v >= 10000 ? 0 : 1) + ' kHz' : Math.round(v) + ' Hz') : (Math.abs(v) < 10 && v % 1 ? v.toFixed(1) : Math.round(v)) + (unit ? ' ' + unit : ''));
const logP = (min, max) => min > 0 && max / min >= 50;       // frequency / time knobs: log scale

export default function FxPanel({ id, stem, pos, onClose, say, onPlaying }) {
  const [cat, setCat] = React.useState(null);
  const [chain, setChain] = React.useState(null);
  const [info, setInfo] = React.useState({});
  const [adding, setAdding] = React.useState(false);
  const [q, setQ] = React.useState('');
  const [pv, setPv] = React.useState(null);              // {wet, dry, start, media}
  const [busy, setBusy] = React.useState('');
  const [ab, setAb] = React.useState('');                // 'wet' | 'dry' | ''
  const audio = React.useRef(null);

  React.useEffect(() => {
    call('fx_catalog').then(setCat).catch(e => say(e.message, 'err'));
    call('fx_chain', id, stem).then(r => { setChain(r.chain); setInfo(r); }).catch(e => say(e.message, 'err'));
    return () => { if (audio.current) audio.current.pause(); };
  }, [id, stem, say]);

  const stop = () => { if (audio.current) audio.current.pause(); setAb(''); onPlaying(false); };
  const set = c => { setChain(c); setPv(null); stop(); };
  const upd = (i, patch) => set(chain.map((m, j) => (j === i ? { ...m, ...patch } : m)));
  const move = (i, d) => { const c = [...chain]; const [m] = c.splice(i, 1); c.splice(Math.max(0, Math.min(c.length, i + d)), 0, m); set(c); };
  const add = async (kind, vst) => {
    setAdding(false);
    if (vst) set([...chain, { type: 'vst', on: true, path: vst.path, name: vst.name, state: {} }]);
    else set([...chain, await call('fx_module', kind)]);
  };
  const preset = async name => set(await call('fx_preset', name));

  const play = async which => {
    if (ab === which) { stop(); return; }
    let p = pv;
    if (!p) {
      setBusy('Rendering the preview…');
      try { p = await call('fx_preview', id, stem, chain, Math.max(0, pos() - 2), 20); setPv(p); } catch (e) { say('Preview: ' + e.message, 'err'); setBusy(''); return; }
      setBusy('');
    }
    if (!p.media) { say('Preview needs the app (not the browser preview)', 'err'); return; }
    const t = audio.current && !audio.current.paused ? audio.current.currentTime : 0;
    if (audio.current) audio.current.pause();
    const a = new Audio(p.media + encodeURIComponent(which === 'wet' ? p.wet : p.dry));
    a.currentTime = t; a.onended = () => { setAb(''); onPlaying(false); };
    audio.current = a; onPlaying(true);
    a.play().catch(() => {}); setAb(which);
  };
  const apply = async () => {
    stop();
    try { await call('fx_apply', id, stem, chain); say(`${stem}: the effects are rendered in the queue (Make stems page shows the progress)`, 'ok'); onClose(); } catch (e) { say(e.message, 'err'); }
  };
  const restore = async () => {
    if (!window.confirm(`Put the original “${stem}” back (the effects are removed)?`)) return;
    try { await call('fx_restore', id, stem); say(`${stem}: original back`, 'ok'); onClose(true); } catch (e) { say(e.message, 'err'); }
  };

  if (!cat || !chain) return <div className="fx card"><span className="spin" /> Loading effects…</div>;
  const vsts = cat.vsts.filter(v => v.name.toLowerCase().includes(q.toLowerCase()));

  return (
    <div className="fx card">
      <div className="fx-head">
        <h2>Effects · {stem}</h2>
        {info.applied && <span className="badge">Applied</span>}
        <span style={{ flex: 1 }} />
        <select value="" onChange={e => e.target.value && preset(e.target.value)} title="A whole chain for this kind of stem">
          <option value="">Chain preset…</option>
          {cat.chains.map(c => <option key={c} value={c}>{c}{c === cat.suggest[stem.toLowerCase()] ? ' (suggested)' : ''}</option>)}
        </select>
        <button className="icon-btn" title="Close" onClick={() => { stop(); onClose(); }}><IcX size={14} /></button>
      </div>
      <div className="fx-chain">
        {chain.map((m, i) => {
          const def = cat.modules[m.type];
          return (
            <div key={i} className={'fx-mod' + (m.on ? '' : ' off')}>
              <div className="fx-mh">
                <label className="tog sm"><input type="checkbox" checked={m.on} onChange={e => upd(i, { on: e.target.checked })} /><span /></label>
                <b title={def ? def.text : m.path}>{def ? def.title : m.name}</b>
                <span style={{ flex: 1 }} />
                <button className="ms" title="Earlier in the chain" disabled={!i} onClick={() => move(i, -1)}>‹</button>
                <button className="ms" title="Later in the chain" disabled={i === chain.length - 1} onClick={() => move(i, 1)}>›</button>
                <button className="ms" title="Remove" onClick={() => set(chain.filter((_, j) => j !== i))}>✕</button>
              </div>
              {def ? <>
                {Object.keys(def.presets).length > 0 && <div className="fx-pre">{Object.entries(def.presets).map(([n, v]) => <button key={n} onClick={() => upd(i, { p: { ...m.p, ...v } })}>{n}</button>)}</div>}
                {def.params.map(([k, label, min, max, unit]) => <Knob key={k} label={label} unit={unit} min={min} max={max} value={m.p[k]} onChange={v => upd(i, { p: { ...m.p, [k]: v } })} />)}
              </> : <Vst m={m} onState={st => upd(i, { state: st })} say={say} />}
            </div>
          );
        })}
        <div className="fx-add">
          {!adding ? <button className="btn" onClick={() => setAdding(true)}><IcPlus size={16} /> Add</button> : (
            <div className="fx-menu">
              <label className="lbl">Built in</label>
              <div className="fx-list">{cat.order.map(k => <button key={k} onClick={() => add(k)} title={cat.modules[k].text}>{cat.modules[k].title}</button>)}</div>
              <label className="lbl">VST3 plugins ({cat.vsts.length})</label>
              {cat.vsts.length > 8 && <div className="search sm"><IcSearch size={14} /><input placeholder="Search plugins…" value={q} onChange={e => setQ(e.target.value)} /></div>}
              <div className="fx-list vst">{vsts.map(v => <button key={v.path} onClick={() => add(null, v)} title={v.path}>{v.name}</button>)}{!cat.vsts.length && <small className="dim">No VST3 plugins found in the standard folder.</small>}</div>
              <button className="btn ghost sm" onClick={() => setAdding(false)}>Close</button>
            </div>
          )}
        </div>
      </div>
      <div className="fx-foot">
        <button className={'btn sm' + (ab === 'wet' ? ' pri' : '')} disabled={!!busy} onClick={() => play('wet')} title="20 s from the play head, with the effects">{ab === 'wet' ? '❚❚' : '▶'} With effects</button>
        <button className={'btn sm' + (ab === 'dry' ? ' pri' : '')} disabled={!!busy} onClick={() => play('dry')} title="The same 20 s without them (A/B)">{ab === 'dry' ? '❚❚' : '▶'} Without</button>
        {busy && <span className="dim"><span className="spin" /> {busy}</span>}
        <span style={{ flex: 1 }} />
        {info.original && <button className="btn ghost sm" onClick={restore}>Restore original</button>}
        <button className="btn pri sm" onClick={apply} title="Render the whole stem with this chain and replace the file (the original is kept)">Apply to the stem</button>
      </div>
    </div>
  );
}

function Knob({ label, unit, min, max, value, onChange }) {
  if (!(max > min)) { min = 0; max = 1; }
  const lg = logP(min, max), r = max - min, step = r > 50 ? 1 : r > 5 ? 0.1 : 0.001;
  const toS = v => (lg ? Math.log(v / min) / Math.log(max / min) : (v - min) / (max - min)) * 1000;
  const fromS = s => { const f = s / 1000; const v = lg ? min * (max / min) ** f : min + f * r; return Math.round(v / step) * step; };
  return (
    <label className="fx-k">
      <span>{label}</span>
      <input type="range" min={0} max={1000} value={toS(value ?? min)} onChange={e => onChange(fromS(+e.target.value))} onDoubleClick={() => {}} />
      <em className="mono">{fmtV(value ?? min, unit)}</em>
    </label>
  );
}

// a VST3 plugin: its own window (best), or its parameters as sliders
function Vst({ m, onState, say }) {
  const [ps, setPs] = React.useState(null);
  const [all, setAll] = React.useState(false);
  const [open, setOpen] = React.useState(false);
  React.useEffect(() => { call('vst_params', m.path).then(setPs).catch(e => say(`${m.name}: ${e.message}`, 'err')); }, [m.path, say]);
  const edit = async () => {
    setOpen(true);
    try { onState(await call('vst_editor', m.path, m.state)); } catch (e) { say(`${m.name}: ${e.message}`, 'err'); }
    setOpen(false);
  };
  if (!ps) return <small className="dim"><span className="spin" /> Loading the plugin…</small>;
  const keys = Object.keys(ps), shown = all ? keys : keys.slice(0, 6);
  return (
    <>
      <button className="btn sm" disabled={open} onClick={edit}>{open ? 'Plugin window is open…' : 'Open the plugin window'}</button>
      {shown.map(k => {
        const p = ps[k], v = m.state[k] ?? p.value;
        return <Knob key={k} label={k.replace(/_/g, ' ')} unit={p.label} min={p.min} max={p.max} value={v} onChange={x => onState({ ...m.state, [k]: x })} />;
      })}
      {keys.length > 6 && <button className="btn ghost sm" onClick={() => setAll(!all)}>{all ? 'Fewer' : `All ${keys.length} parameters`}</button>}
    </>
  );
}

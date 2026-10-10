// Run a plugin on one stem (plugins.py): its files to choose (remembered), its options, then a job in the queue.
// The result replaces the stem (the model's stem stays; "Restore original" in Effects puts it back).
import React from 'react';
import { call } from './api.js';
import { IcFile, IcWarn } from './icons.jsx';

const forStem = (p, stem) => (p.for || []).some(s => s.toLowerCase() === stem.toLowerCase());

export default function PluginRun({ id, stem, list, say, onDone, go }) {
  const items = [...list.items].sort((a, b) => forStem(b, stem) - forStem(a, stem));
  const [pid, setPid] = React.useState(items[0]?.id || '');
  const p = items.find(x => x.id === pid);
  const saved = (list.saved || {})[pid] || {};
  const [vals, setVals] = React.useState({});
  React.useEffect(() => {                     // the plugin's defaults, then what the user chose the last time
    if (!p) return;
    const v = {};
    (p.options || []).forEach(o => { v[o.id] = o.id in saved ? saved[o.id] : o.default; });
    (p.inputs || []).forEach(i => { v[i.id] = i.remember && saved[i.id] ? saved[i.id] : ''; });
    setVals(v);
  }, [pid]);  // eslint-disable-line react-hooks/exhaustive-deps

  if (!items.length) return (
    <div className="plg-none">
      <p>No plugins yet. A plugin is a folder with a <code>plugin.json</code> in the plugins folder.</p>
      <div className="modal-btns"><button className="btn sm" onClick={() => call('plugin_folder')}>Open the plugins folder</button><button className="btn ghost sm" onClick={() => go('models', 'plugins')}>Plugins page</button></div>
    </div>
  );
  const pick = async k => { const f = await call('pick_audio'); if (f) setVals(v => ({ ...v, [k]: f })); };
  const missing = p && (p.inputs || []).find(i => !i.optional && !vals[i.id]);
  const run = async () => {
    const inputs = {}, options = {};
    (p.inputs || []).forEach(i => { inputs[i.id] = vals[i.id] || ''; });
    (p.options || []).forEach(o => { options[o.id] = vals[o.id]; });
    try { await call('plugin_run', id, stem, pid, inputs, options); say(`${stem}: ${p.name} added to the queue (Make stems page shows the progress)`, 'ok'); onDone(); } catch (e) { say(e.message, 'err'); }
  };
  return (
    <>
      <label className="lbl">Plugin</label>
      <select className="plg-sel" value={pid} onChange={e => setPid(e.target.value)}>
        {items.map(x => <option key={x.id} value={x.id}>{x.name}{x.version ? ` ${x.version}` : ''}{forStem(x, stem) ? ` · for ${stem}` : ''}</option>)}
      </select>
      {p && <>
        <p className="sub">{p.description}{p.time ? <><br /><span className="dim">{p.time}</span></> : null}</p>
        {p.problem && <p className="err"><IcWarn size={14} /> {p.problem}</p>}
        {!p.problem && p.ready === false && <p className="err"><IcWarn size={14} /> Install this plugin first (packages{p.models?.length ? ' and models' : ''}). <button className="btn sm" onClick={() => go('models', 'plugins')}>Install</button></p>}
        {(p.inputs || []).map(i => (
          <div key={i.id} className="plg-in">
            <label className="lbl">{i.label || i.id}</label>
            <div className="in-row">
              <input readOnly value={vals[i.id] || ''} placeholder="Choose a file…" title={vals[i.id] || ''} onClick={() => pick(i.id)} />
              <button className="btn sm" onClick={() => pick(i.id)}><IcFile size={14} /> Browse</button>
            </div>
            {i.help && <small className="dim">{i.help}{i.remember ? ' (Remembered for the next time.)' : ''}</small>}
          </div>
        ))}
        {(p.options || []).map(o => o.type === 'bool' ? (
          <label key={o.id} className="check" title={o.help || ''}><input type="checkbox" checked={!!vals[o.id]} onChange={e => setVals(v => ({ ...v, [o.id]: e.target.checked }))} /> {o.label || o.id}</label>
        ) : (
          <label key={o.id} className="plg-in"><span className="lbl">{o.label || o.id}</span><input type={o.type === 'number' ? 'number' : 'text'} value={vals[o.id] ?? ''} onChange={e => setVals(v => ({ ...v, [o.id]: e.target.value }))} /></label>
        ))}
        <p className="hint">The result replaces “{stem}”. The stem from the model is kept: <b>FX › Restore original</b> puts it back.</p>
      </>}
      <div className="modal-btns"><button className="btn pri" disabled={!p || !!p.problem || p.ready === false || !!missing} onClick={run}>Run</button><button className="btn ghost" onClick={onDone}>Cancel</button></div>
    </>
  );
}

// "Make stems" from dubplates.net: a dubplates:// link, or a request over the local bridge (bridge.py).
// The client asks before it starts (a bridge request: until the user ticks "start without asking").
// The first time for a music folder, the user shows where that folder is on this computer (kept in the settings).
import React from 'react';
import { call } from './api.js';
import ModelPicker from './ModelPicker.jsx';
import { IcFolder, IcStems, IcX } from './icons.jsx';

export default function LinkAsk({ cfg, models, setConfig, say, go }) {
  const [ask, setAsk] = React.useState(null);       // {kind: 'link'|'site', id?, root, path, name, file?, needRoot?, tried?}
  const [busy, setBusy] = React.useState(false);
  const [err, setErr] = React.useState('');
  const [trust, setTrust] = React.useState(true);
  const askRef = React.useRef(null); askRef.current = ask;

  const pullLink = React.useCallback(async () => {
    try {
      const l = await call('pending_link');
      if (!l) return;
      if (l.action === 'error') { say(l.error, 'err'); return; }
      if (l.action === 'separate') { setErr(''); setAsk({ kind: 'link', ...l }); go('separate'); }
    } catch { /* */ }
  }, [say, go]);
  const pullSite = React.useCallback(async () => {
    if (askRef.current) return;
    try {
      const list = await call('site_pending');
      const r = list && list[0];
      if (r) { setErr(''); setAsk({ kind: 'site', id: r.id, root: r.root, path: r.path, name: r.name, file: r.file, needRoot: r.state === 'needRoot' }); go('separate'); }
    } catch { /* */ }
  }, [go]);
  React.useEffect(() => {
    window.__dpLink = pullLink; window.__dpSite = pullSite; pullLink(); pullSite();
    const t = setInterval(pullSite, 2000);                // (in case the window missed the call)
    return () => { window.__dpLink = null; window.__dpSite = null; clearInterval(t); };
  }, [pullLink, pullSite]);

  if (!ask) return null;
  const installed = models.filter(m => m.installed);
  const sel = installed.find(m => m.file === cfg.model) || installed[0];
  const drumModels = installed.filter(m => m.stems.some(s => s.toLowerCase() === 'kick'));
  const drum = sel?.stems.some(s => s.toLowerCase() === 'drums') ? drumModels.find(m => m.file === cfg.drumSplit) : null;

  const close = () => { if (ask.kind === 'site') call('site_cancel', ask.id); setAsk(null); };
  const locate = async () => {
    setErr('');
    try {
      const r = ask.kind === 'site' ? await call('site_root', ask.id) : await call('set_root', ask.root, ask.path);
      if (r.file) setAsk({ ...ask, file: r.file, needRoot: false });
    } catch (e) { setErr(e.message); }
  };
  const start = async () => {
    setBusy(true);
    try {
      if (sel.file !== cfg.model) await setConfig({ model: sel.file });
      if (ask.kind === 'site') { await call('site_accept', ask.id, trust); say(`“${ask.name}”: making stems`, 'ok'); setAsk(null); }
      else { const r = await call('add_jobs', [ask.file], sel.file, drum ? drum.file : ''); if (r.added) { say(`“${ask.name}” added`, 'ok'); setAsk(null); } }
    } catch (e) { setErr(e.message); }
    setBusy(false);
  };

  return (
    <div className="modal-bg" onMouseDown={e => { if (e.target === e.currentTarget) close(); }}>
      <div className="card modal">
        <button className="icon-btn modal-x" title="Cancel" onClick={close}><IcX size={14} /></button>
        <h2><IcStems size={18} /> Make stems</h2>
        <p className="modal-track">{ask.name}</p>
        <p className="sub">dubplates.net asks to make stems of this track, from your music folder “{ask.root}”.</p>
        {ask.needRoot ? (
          <>
            <div className="note">
              {ask.tried ? <>The track is not in <code>{ask.tried}</code> any more.</> : <>The client does not know your music folder “{ask.root}” yet.</>}
              {' '}Show where it is on this computer (once).
            </div>
            <button className="btn pri" onClick={locate}><IcFolder size={16} /> Where is “{ask.root}”?</button>
          </>
        ) : !sel ? (
          <button className="btn pri" onClick={() => { close(); go('models'); }}>Install a model first</button>
        ) : (
          <>
            <label className="lbl">Model</label>
            <ModelPicker models={installed} value={sel.file} onChange={v => setConfig({ model: v })} />
            {drum && <small className="dim">Then the drums are split with {drum.name}.</small>}
            {ask.kind === 'site' && <label className="check"><input type="checkbox" checked={trust} onChange={e => setTrust(e.target.checked)} /> Next time, start without asking (with the model chosen here)</label>}
            <div className="modal-btns">
              <button className="btn pri" disabled={busy} onClick={start}><IcStems size={16} /> Make stems</button>
              <button className="btn ghost" onClick={close}>Cancel</button>
            </div>
          </>
        )}
        {err && <p className="err">{err}</p>}
      </div>
    </div>
  );
}

// Before tracks go into the queue: how many, how the folders look, and WHERE the stems will go (examples from the
// user's own files). The first time the user must choose a layout; later the window shows for folders and many files.
import React from 'react';
import { createPortal } from 'react-dom';
import { call } from './api.js';
import { IcFolder, IcStems, IcX } from './icons.jsx';

export const LAYOUTS = [
  { id: 'next', title: 'Next to each track', text: 'A “Track Stems” folder beside every track. Good when each track has its own folder, and fine for one big folder.', tree: ['Music/', '  Artist - Track.mp3', '  Artist - Track Stems/'] },
  { id: 'mirror', title: 'One stems folder, same sub folders', text: 'All stems in one folder you choose, in the same sub folders as your music. Your music folders stay clean.', tree: ['Stems/', '  Dub/', '    Artist - Track Stems/'] },
  { id: 'flat', title: 'One stems folder, all together', text: 'All stem folders side by side in one folder you choose. Easy to browse; the sub folders are not kept.', tree: ['Stems/', '  Artist - Track Stems/', '  Other - Song Stems/'] },
];
const STRUCT = {
  'per-track': ['Your tracks: one folder per track.', 'next'],
  shared: ['Your tracks: many tracks in one folder.', 'mirror'],
  mixed: ['Your tracks: some folders with one track, some with many.', 'next'],
};

export default function AddWindow({ paths, cfg, setConfig, onAdd, onClose }) {
  const [mode, setMode] = React.useState(cfg.outMode);
  const [outDir, setOutDir] = React.useState(cfg.outDir || '');
  const [skip, setSkip] = React.useState(cfg.skipDone !== false);
  const [pv, setPv] = React.useState(null);
  const [busy, setBusy] = React.useState(false);
  const needDir = mode !== 'next' && !outDir;

  React.useEffect(() => {
    let dead = false;
    call('preview_add', paths, mode, outDir).then(r => { if (!dead) setPv(r); }).catch(() => {});
    return () => { dead = true; };
  }, [paths, mode, outDir]);

  const pick = async () => { const f = await call('pick_folder'); if (f) setOutDir(f); };
  const add = async () => {
    setBusy(true);
    await setConfig({ outMode: mode, outDir, skipDone: skip, layoutChosen: true });
    await onAdd(paths, skip);
    setBusy(false);
  };
  const st = pv && STRUCT[pv.structure];
  const short = p => { const parts = p.split(/[\\/]/); return parts.length > 4 ? '…\\' + parts.slice(-3).join('\\') : p; };

  return createPortal(
    <div className="modal-bg" onMouseDown={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="card modal addw">
        <button className="icon-btn modal-x" title="Cancel" onClick={onClose}><IcX size={14} /></button>
        <h2><IcStems size={18} /> {pv ? `Add ${pv.count} track${pv.count === 1 ? '' : 's'}` : 'Looking at the files…'}</h2>
        {pv && <p className="sub">{pv.folders > 1 ? `In ${pv.folders} folders. ` : ''}{st ? st[0] : ''} Choose where the stems go:</p>}
        <div className="layouts">
          {LAYOUTS.map(l => (
            <button key={l.id} className={'layout' + (mode === l.id ? ' on' : '')} onClick={() => setMode(l.id)}>
              <b>{l.title}{st && st[1] === l.id && <span className="badge">Fits your folders</span>}</b>
              <small>{l.text}</small>
              <pre>{l.tree.join('\n')}</pre>
            </button>
          ))}
        </div>
        {mode !== 'next' && (
          <div className="in-row"><input readOnly value={outDir} placeholder="Choose the stems folder…" /><button className="btn sm" onClick={pick}><IcFolder size={14} /> Choose</button></div>
        )}
        {pv && pv.examples.length > 0 && !needDir && (
          <div className="examples">
            <label className="lbl">What will happen</label>
            {pv.examples.map(x => <div key={x.src} className="ex"><span title={x.src}>{short(x.src)}</span><i>→</i><code title={x.out}>{short(x.out)}</code></div>)}
          </div>
        )}
        {pv && pv.have > 0 && <label className="check"><input type="checkbox" checked={skip} onChange={e => setSkip(e.target.checked)} /> Skip the {pv.have} track{pv.have === 1 ? '' : 's'} that have stems already</label>}
        {pv && pv.count > 20 && <p className="hint">Big queue: it runs one track at a time, keeps the computer awake, and goes on after a restart. Leave it running overnight.</p>}
        <div className="modal-btns">
          <button className="btn pri" disabled={busy || !pv || !pv.count || needDir} onClick={add}>{pv && pv.count ? `Add ${pv.count - (skip && pv.have ? pv.have : 0)} to the queue` : 'Add'}</button>
          <button className="btn ghost" onClick={onClose}>Cancel</button>
        </div>
      </div>
    </div>
  , document.body);
}

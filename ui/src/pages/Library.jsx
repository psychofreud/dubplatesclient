// The user's stem sets: a list (newest first), and one set opened: waveforms, play, mute / solo, more work on a stem.
import React from 'react';
import { call } from '../api.js';
import { IcFolder, IcSearch, IcPlus, IcTrash, IcStems, IcWarn } from '../icons.jsx';
import StemView from '../StemView.jsx';

export default function Library({ models, jobs, say, sel, setSel, go }) {
  const [list, setList] = React.useState(null);
  const [q, setQ] = React.useState('');
  const load = React.useCallback(() => call('library').then(setList).catch(e => say(e.message, 'err')), [say]);
  React.useEffect(() => { load(); }, [load]);
  // a job finished: the list (and an open set) may have new stems
  const doneKey = jobs.filter(j => j.state === 'done').map(j => j.id).join(',');
  React.useEffect(() => { if (doneKey) load(); }, [doneKey, load]);
  // opened from the queue ("View"): by folder
  React.useEffect(() => {
    if (sel && sel.folder && list) { const it = list.find(x => x.folder.toLowerCase() === sel.folder.toLowerCase()); if (it) setSel({ id: it.id }); }
  }, [sel, list, setSel]);

  const add = async () => { try { const r = await call('library_add'); if (r.id) { await load(); setSel({ id: r.id }); } } catch (e) { say(e.message, 'err'); } };
  const forget = async it => { if (!window.confirm(`Remove “${it.name}” from the list? (The files stay on the disk.)`)) return; await call('library_remove', it.id); if (sel && sel.id === it.id) setSel(null); load(); };
  const shown = (list || []).filter(x => (x.name + ' ' + x.stems.join(' ') + ' ' + x.model).toLowerCase().includes(q.toLowerCase()));

  return (
    <div className="page wide lib">
      <header className="ph">
        <div><h1>Library</h1><p>Your stem sets. Open one to listen, compare and do more work on a stem.</p></div>
        <button className="btn" onClick={add}><IcPlus size={16} /> Add a Stems folder</button>
      </header>
      <div className="lib-grid">
        <aside className="lib-list">
          <div className="search"><IcSearch size={16} /><input placeholder="Search…" value={q} onChange={e => setQ(e.target.value)} /></div>
          {list && !list.length && <div className="lib-empty"><IcStems size={26} /><b>No stem sets yet</b><span>Make stems of a track: it shows here.</span><button className="btn pri sm" onClick={() => go('separate')}>Make stems</button></div>}
          {shown.map(it => (
            <button key={it.id} className={'lib-it' + (sel && sel.id === it.id ? ' on' : '') + (it.missing ? ' missing' : '')} onClick={() => !it.missing && setSel({ id: it.id })}>
              <b>{it.name}</b>
              <small>{it.missing ? <><IcWarn size={12} /> Folder not found</> : <>{it.stems.length} stems{it.parts ? ` + ${it.parts} parts` : ''} · {it.model}</>}</small>
              <small className="dim">{(it.created || '').slice(0, 10)}</small>
              <span className="lib-x" title="Remove from the list" onClick={e => { e.stopPropagation(); forget(it); }}><IcTrash size={13} /></span>
            </button>
          ))}
        </aside>
        <section className="lib-main">
          {sel && sel.id ? <StemView key={sel.id} id={sel.id} models={models} jobs={jobs} say={say} go={go} />
            : <div className="lib-pick"><IcFolder size={28} /><span>Pick a stem set on the left.</span></div>}
        </section>
      </div>
    </div>
  );
}

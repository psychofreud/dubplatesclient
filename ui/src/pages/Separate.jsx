import React from 'react';
import { call } from '../api.js';
import { IcUpload, IcFolder, IcFile, IcX, IcCheck, IcWarn } from '../icons.jsx';
import { StemChips, fmtTime } from '../ui.jsx';
import ModelPicker from '../ModelPicker.jsx';

export default function Separate({ cfg, models, jobs, say, go, setConfig }) {
  const installed = models.filter(m => m.installed);
  const sel = installed.find(m => m.file === cfg.model) || installed[0];
  // drum models: their stems are drum parts (kick, snare…). Used as a second step on the Drums stem.
  const drumModels = installed.filter(m => m.stems.some(s => s.toLowerCase() === 'kick'));
  const hasDrums = sel?.stems.some(s => s.toLowerCase() === 'drums');
  const drum = hasDrums ? drumModels.find(m => m.file === cfg.drumSplit) : null;
  const [drag, setDrag] = React.useState(false);
  const dragN = React.useRef(0);

  const add = React.useCallback(async paths => {
    if (!paths?.length) return;
    if (!sel) { say('Install a model first', 'err'); go('models'); return; }
    try {
      const r = await call('add_jobs', paths, sel.file, drum ? drum.file : '');
      say(r.added ? `${r.added} track${r.added > 1 ? 's' : ''} added` : 'No audio files found there', r.added ? 'ok' : 'err');
    } catch (e) { say(e.message, 'err'); }
  }, [sel, drum, say, go]);

  // files dropped on the window: Python sends their full paths here
  React.useEffect(() => { window.__dpDrop = paths => { dragN.current = 0; setDrag(false); add(paths); }; return () => { window.__dpDrop = null; }; }, [add]);
  React.useEffect(() => {
    const enter = e => { if ([...(e.dataTransfer?.types || [])].includes('Files')) { dragN.current++; setDrag(true); } };
    const leave = () => { dragN.current = Math.max(0, dragN.current - 1); if (!dragN.current) setDrag(false); };
    const over = e => e.preventDefault();
    const drop = e => { e.preventDefault(); dragN.current = 0; setDrag(false); };
    window.addEventListener('dragenter', enter); window.addEventListener('dragleave', leave);
    window.addEventListener('dragover', over); window.addEventListener('drop', drop);
    return () => { window.removeEventListener('dragenter', enter); window.removeEventListener('dragleave', leave); window.removeEventListener('dragover', over); window.removeEventListener('drop', drop); };
  }, []);

  const pickFiles = async () => add(await call('pick_files'));
  const pickFolder = async () => { const f = await call('pick_folder'); if (f) add([f]); };
  const done = jobs.filter(j => !['queued', 'running'].includes(j.state)).length;

  return (
    <div className="page">
      <header className="ph"><div><h1>Make stems</h1><p>Drop tracks, pick a model, get stems. Everything runs on this computer.</p></div></header>

      <section className="card model-pick">
        <div className="mp-l">
          <label className="lbl">Model</label>
          {installed.length ? (
            <ModelPicker models={installed} value={sel?.file} onChange={v => setConfig({ model: v })} />
          ) : <button className="btn pri" onClick={() => go('models')}>Install a model</button>}
        </div>
        {sel && <div className="mp-r"><StemChips stems={sel.stems} /><small>{sel.desc}</small></div>}
        {hasDrums && (
          <div className="chain">
            <label className="tog"><input type="checkbox" checked={!!drum} disabled={!drumModels.length} onChange={e => setConfig({ drumSplit: e.target.checked ? drumModels[0].file : '' })} /><span />Then split the drums</label>
            {drumModels.length ? (
              drum ? <ModelPicker models={drumModels} value={drum.file} onChange={v => setConfig({ drumSplit: v })} />
                : <small>Kick, snare, toms, hi-hat, ride and crash, each on its own.</small>
            ) : <small>Install “Drum Split” on the Models page to split the drum stem into kick, snare, hats… <a onClick={() => go('models')}>Models</a></small>}
          </div>
        )}
      </section>

      <section className={'drop' + (drag ? ' over' : '')} onClick={pickFiles}>
        <div className="drop-ic"><IcUpload size={30} /></div>
        <b>{drag ? 'Drop to add' : 'Drop tracks or folders here'}</b>
        <span>WAV, FLAC, MP3, M4A, OGG, AIFF</span>
        <div className="drop-btns" onClick={e => e.stopPropagation()}>
          <button className="btn" onClick={pickFiles}><IcFile size={16} /> Add files</button>
          <button className="btn" onClick={pickFolder}><IcFolder size={16} /> Add folder</button>
        </div>
        <small className="drop-out">
          Stems go to {cfg.outMode === 'folder' && cfg.outDir ? <code>{cfg.outDir}</code> : 'a “Track Stems” folder next to each track'} · {cfg.format}
          {' '}<a onClick={e => { e.stopPropagation(); go('settings'); }}>Change</a>
        </small>
      </section>

      {jobs.length > 0 && (
        <section className="queue">
          <div className="q-head"><h2>Queue</h2>{done > 0 && <button className="btn ghost sm" onClick={() => call('clear_jobs')}>Clear finished</button>}</div>
          {[...jobs].reverse().map(j => <Job key={j.id} j={j} say={say} />)}
        </section>
      )}
    </div>
  );
}

function Job({ j, say }) {
  const open = p => call('open_path', p).catch(e => say(e.message, 'err'));
  const icon = j.state === 'done' ? <IcCheck size={16} /> : j.state === 'error' ? <IcWarn size={16} /> : j.state === 'cancelled' ? <IcX size={16} /> : <IcFile size={16} />;
  return (
    <div className={'job ' + j.state}>
      <div className="job-ic">{icon}</div>
      <div className="job-main">
        <div className="job-top">
          <b title={j.path}>{j.name}</b>
          <span className="job-meta">{j.modelName}{j.secs ? ` · ${fmtTime(j.secs)}` : ''}</span>
        </div>
        {j.state === 'running' && <div className="bar"><i style={{ width: Math.max(2, j.pct) + '%' }} /></div>}
        <div className="job-msg">
          {j.state === 'running' ? <>{j.msg} <span className="mono">{Math.round(j.pct)}%</span></>
            : j.state === 'error' ? <span className="err">{j.err}</span>
              : j.state === 'done' ? <span className="stem-list">{j.stems.map(s => <em key={s.name}>{s.name}{s.parts?.length ? ` + ${s.parts.length} parts` : ''}</em>)}</span>
                : j.msg}
        </div>
      </div>
      <div className="job-act">
        {j.state === 'done' && <button className="btn sm" onClick={() => open(j.folder)}><IcFolder size={14} /> Open</button>}
        {(j.state === 'running' || j.state === 'queued') && <button className="btn ghost sm" onClick={() => call('cancel_job', j.id)}>Cancel</button>}
      </div>
    </div>
  );
}

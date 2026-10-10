import React from 'react';
import { call } from '../api.js';
import { IcDown, IcTrash, IcRefresh, IcPlus, IcSearch, IcCheck, IcX, IcFolder, IcWarn } from '../icons.jsx';
import { StemChips, Seg } from '../ui.jsx';

const SECTIONS = [
  ['vocals', 'Vocals & instrumental', 'Two stems: the voice and the music.'],
  ['multi', 'Multi-stem', 'Drums, bass, vocals and more, each on its own.'],
  ['clean', 'Clean-up', 'Run these on a stem to remove reverb, noise, crowd or bleed.'],
];

export default function Models({ sub, cfg, models, installs, reload, say, setConfig, go }) {
  const [tab, setTab] = React.useState(sub || 'suggested');
  const [q, setQ] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const refresh = async () => { setBusy(true); await reload(true); setBusy(false); say('Model list updated', 'ok'); };
  const n = models.filter(m => m.installed).length;

  return (
    <div className="page">
      <header className="ph">
        <div><h1>Models</h1><p>{n} installed · models are saved in <code>{cfg.modelDirUsed}</code></p></div>
        <button className="btn" onClick={refresh} disabled={busy}><IcRefresh size={16} className={busy ? 'rot' : ''} /> Check for new models</button>
      </header>
      <Seg value={tab} onChange={setTab} options={[['suggested', 'Suggested'], ['all', 'All models'], ['custom', 'Custom'], ['plugins', 'Plugins']]} />

      {tab === 'suggested' && SECTIONS.map(([g, title, sub]) => (
        <section key={g} className="msec">
          <h2>{title}</h2><p className="sub">{sub}</p>
          <div className="grid">{models.filter(m => m.group === g).map(m => <Card key={m.file} m={m} inst={installs[m.file]} say={say} cfg={cfg} setConfig={setConfig} go={go} />)}</div>
        </section>
      ))}

      {tab === 'all' && (
        <section className="msec">
          <div className="search"><IcSearch size={16} /><input placeholder="Search models (name, stem, author)…" value={q} onChange={e => setQ(e.target.value)} /></div>
          <div className="rows">
            {models.filter(m => (m.name + ' ' + m.stems.join(' ') + ' ' + m.file).toLowerCase().includes(q.toLowerCase())).slice(0, 200)
              .map(m => <Row key={m.file} m={m} inst={installs[m.file]} say={say} />)}
          </div>
        </section>
      )}

      {tab === 'custom' && <Custom models={models.filter(m => m.custom)} say={say} reload={reload} installs={installs} />}
      {tab === 'plugins' && <Plugins say={say} />}
    </div>
  );
}

function useActions(m, say) {
  const install = () => call('install', m.file).catch(e => say(e.message, 'err'));
  const cancel = () => call('cancel_install', m.file);
  const remove = async () => {
    if (!window.confirm(`Remove “${m.name}” from this computer?`)) return;
    try { await call('remove', m.file); say('Removed', 'ok'); } catch (e) { say(e.message, 'err'); }
  };
  return { install, cancel, remove };
}

function InstallBtn({ m, inst, a }) {
  const going = inst && !inst.done;
  if (going) return (
    <div className="dl">
      <div className="bar"><i style={{ width: Math.max(3, inst.pct) + '%' }} /></div>
      <span className="dl-msg">{inst.msg}</span>
      <button className="icon-btn" title="Stop" onClick={a.cancel}><IcX size={14} /></button>
    </div>
  );
  if (m.installed) return <button className="btn ghost sm" onClick={a.remove}><IcTrash size={14} /> Remove</button>;
  return <button className="btn pri sm" onClick={a.install}><IcDown size={14} /> Install</button>;
}

function Card({ m, inst, say, cfg, setConfig, go }) {
  const a = useActions(m, say);
  const use = () => { setConfig({ model: m.file }); go('separate'); };
  return (
    <div className={'mcard' + (m.installed ? ' have' : '')}>
      <div className="mc-top">
        <b>{m.name}</b>
        {m.badge && <span className="badge">{m.badge}</span>}
        {m.stems.length > 0 && <span className="mpk-n" style={{ marginLeft: m.installed ? 0 : 'auto' }}>{m.stems.length} stems</span>}
        {m.installed && <span className="ok-dot" title="Installed"><IcCheck size={13} /></span>}
      </div>
      <p>{m.desc}</p>
      <StemChips stems={m.stems} />
      {inst?.err && <p className="err">{inst.err}</p>}
      {!m.known && <p className="err">Not in the engine’s list yet. Click “Check for new models”.</p>}
      <div className="mc-foot">
        <span className="mono dim">{m.arch}{m.sdr ? ` · SDR ${m.sdr}` : ''}</span>
        <div className="mc-btns">
          {m.installed && cfg.model !== m.file && <button className="btn sm" onClick={use}>Use</button>}
          <InstallBtn m={m} inst={inst} a={a} />
        </div>
      </div>
    </div>
  );
}

function Row({ m, inst, say }) {
  const a = useActions(m, say);
  return (
    <div className={'mrow' + (m.installed ? ' have' : '')}>
      <div className="mr-name"><b>{m.name}</b>{m.stems.length > 0 && <span className="mpk-n">{m.stems.length} stems</span>}{m.vip && <span className="badge vip" title="A UVR VIP model: please support its author">VIP</span>}<StemChips stems={m.stems} /></div>
      <span className="mono dim">{m.arch}{m.sdr ? ` · ${m.sdr}` : ''}</span>
      {inst?.err && <span className="err" title={inst.err}>Failed</span>}
      <InstallBtn m={m} inst={inst} a={a} />
    </div>
  );
}

function Custom({ models, say, installs }) {
  const [f, setF] = React.useState({ name: '', model: '', config: '', sha256: '' });
  const [busy, setBusy] = React.useState(false);
  const set = k => e => setF({ ...f, [k]: e.target.value });
  const pick = async (k, kind) => { const p = await call('pick_model_file', kind); if (p) setF(x => ({ ...x, [k]: p })); };
  const add = async () => {
    setBusy(true);
    try { await call('add_custom', f.name, f.model, f.config, f.sha256); say('Model added', 'ok'); setF({ name: '', model: '', config: '', sha256: '' }); } catch (e) { say(e.message, 'err'); }
    setBusy(false);
  };
  return (
    <section className="msec">
      <div className="card form">
        <h2><IcPlus size={18} /> Add a model</h2>
        <p className="sub">For new Roformer or MDX23C models: you need the model file (.ckpt) and its config (.yaml). Use https links or files on this computer.</p>
        <label>Name<input value={f.name} onChange={set('name')} placeholder="e.g. Mel-Roformer Vocals FV8" /></label>
        <label>Model file<div className="in-row"><input value={f.model} onChange={set('model')} placeholder="https://huggingface.co/…/model.ckpt" /><button className="btn sm" onClick={() => pick('model', 'model')}>Browse</button></div></label>
        <label>Config (.yaml)<div className="in-row"><input value={f.config} onChange={set('config')} placeholder="https://huggingface.co/…/config.yaml" /><button className="btn sm" onClick={() => pick('config', 'config')}>Browse</button></div></label>
        <label>SHA-256 <span className="dim">(optional: checks the download)</span><input value={f.sha256} onChange={set('sha256')} className="mono" /></label>
        <div className="note">Only add models from people you trust. The client loads the weights in safe mode, but a model can still give bad results.</div>
        <button className="btn pri" disabled={busy || !f.name || !f.model || !f.config} onClick={add}>{busy ? 'Downloading…' : 'Add model'}</button>
      </div>
      {models.length > 0 && <div className="rows">{models.map(m => <Row key={m.file} m={m} inst={installs[m.file]} say={say} />)}</div>}
    </section>
  );
}

const mb = b => (b >= 1e9 ? (b / 1e9).toFixed(1) + ' GB' : Math.round(b / 1e6) + ' MB');
// Plugins: folders in <app dir>/plugins with a plugin.json. They work on one stem (Library › a set › ＋ › Plugin).
function Plugins({ say }) {
  const [p, setP] = React.useState(null);
  const [cat, setCat] = React.useState(null);              // the plugins on dubplates.net
  const load = React.useCallback(() => call('plugins').then(setP).catch(e => say(e.message, 'err')), [say]);
  const loadCat = React.useCallback(() => call('plugin_catalog').then(setCat).catch(e => setCat({ error: e.message, items: [] })), []);
  React.useEffect(() => { load(); loadCat(); }, [load, loadCat]);
  const going = p && (p.items.some(x => x.install && !x.install.done) || Object.values(p.getting || {}).some(g => !g.done));
  const wasGoing = React.useRef(false);
  React.useEffect(() => { if (wasGoing.current && !going) loadCat(); wasGoing.current = going; }, [going, loadCat]);
  const get = async id => { try { await call('plugin_get', id); load(); } catch (e) { say(e.message, 'err'); } };
  React.useEffect(() => { if (!going) return undefined; const t = setInterval(load, 700); return () => clearInterval(t); }, [going, load]);
  const add = async () => { try { const r = await call('plugin_add'); if (!r.cancelled) { say(`${r.name} added`, 'ok'); load(); } } catch (e) { say(e.message, 'err'); } };
  const install = async id => { try { await call('plugin_install', id); load(); } catch (e) { say(e.message, 'err'); } };
  if (!p) return <section className="msec"><span className="spin" /></section>;
  return (
    <section className="msec">
      <h2>Plugins</h2>
      <p className="sub">Tools that work on one stem, for example a vocal repair. Use them in the Library: open a set, click <b>＋</b> on a stem, then <b>Plugin</b>.
        A plugin is a folder (with a <code>plugin.json</code>) in <code>{p.dir}</code>. Only add plugins from people you trust: a plugin is a program.</p>
      <div className="modal-btns" style={{ marginBottom: 14 }}>
        <button className="btn sm" onClick={add}><IcPlus size={14} /> Add a plugin folder…</button>
        <button className="btn sm" onClick={() => call('plugin_folder')}><IcFolder size={14} /> Open the plugins folder</button>
        <button className="btn ghost sm" onClick={load}><IcRefresh size={14} /> Look again</button>
      </div>
      {cat && (cat.error ? <div className="note">Plugins on dubplates.net: could not get the list ({cat.error}).</div> : cat.items.filter(x => !x.installed || x.newer).length > 0 && <>
        <h2 style={{ marginTop: 6 }}>From dubplates.net</h2>
        <div className="grid" style={{ marginBottom: 18 }}>{cat.items.filter(x => !x.installed || x.newer).map(x => {
          const g = (p.getting || {})[x.id] || p.items.find(y => y.id === x.id)?.install, run = g && !g.done;
          const dl = (x.models || []).reduce((a, y) => a + (y.size || 0), 0);
          return (
            <div key={x.id} className="mcard pcard">
              <div className="mc-top"><b>{x.name}</b><span className="mpk-n">{x.version}</span>{x.newer && <span className="badge">Update</span>}</div>
              <p>{x.description}</p>
              {x.for?.length > 0 && <span className="pmeta">For: {x.for.slice(0, 3).join(', ')}{x.author ? ` · by ${x.author}` : ''}</span>}
              {x.time && <span className="pmeta">{x.time}</span>}
              {x.models?.length > 0 && <span className="pmeta">Models: {x.models.map(y => `${y.name || y.file.split('/').pop()} (${mb(y.size || 0)})`).join(' · ')}</span>}
              {x.local && <p className="err"><IcWarn size={14} /> You have your own copy of this plugin ({x.installed}). Installing replaces it.</p>}
              {g?.err && <p className="err">{g.err}</p>}
              <div className="mc-foot">
                <span className="mono dim">{x.installed ? `You have ${x.installed}` : `${mb(x.size || 0)}${dl ? ` + models ${mb(dl)}` : ''}`}</span>
                <div className="mc-btns">
                  {run ? <div className="dl"><div className="bar"><i style={{ width: Math.max(3, g.pct) + '%' }} /></div><span className="dl-msg">{g.msg}</span></div>
                    : <button className="btn pri sm" disabled={!cat.canInstall} title={cat.canInstall ? '' : 'Update the client first'} onClick={() => get(x.id)}><IcDown size={14} /> {x.newer ? 'Update' : 'Install'}</button>}
                </div>
              </div>
            </div>
          );
        })}</div>
        <h2>On this computer</h2>
      </>)}
      {!p.items.length && <div className="note">No plugins on this computer yet. Install one from dubplates.net, or copy a plugin folder into the plugins folder and click “Look again”.</div>}
      <div className="grid">{p.items.map(x => {
        const inst = x.install, run = inst && !inst.done;
        return (
          <div key={x.id} className={'mcard pcard' + (x.ready ? ' have' : '')}>
            <div className="mc-top"><b>{x.name}</b>{x.version && <span className="mpk-n">{x.version}</span>}{x.ready && <span className="ok-dot" title="Ready"><IcCheck size={13} /></span>}</div>
            <p>{x.description}</p>
            {x.for?.length > 0 && <span className="pmeta">For: {x.for.slice(0, 3).join(', ')}{x.author ? ` · by ${x.author}` : ''}</span>}
            {x.time && <span className="pmeta">{x.time}</span>}
            {x.models?.length > 0 && <span className="pmeta">Models: {x.models.map(y => `${y.name || y.file.split('/').pop()}${y.size ? ` (${mb(y.size)})` : ''}${y.have ? ' ✓' : ''}`).join(' · ')}</span>}
            {x.fromSite && <span className="pmeta">From dubplates.net (signed)</span>}
            {x.problem && <p className="err"><IcWarn size={14} /> {x.problem}</p>}
            {inst?.err && <p className="err">{inst.err}</p>}
            <span className="pdir mono">{x.dir}</span>
            <div className="mc-foot">
              <span className="mono dim">{x.problem ? 'Not ready' : x.ready ? 'Ready' : x.packages !== 'ok' && x.modelsState !== 'ok' ? 'Needs packages + models' : x.packages !== 'ok' ? 'Needs packages' : 'Needs models'}</span>
              <div className="mc-btns">
                {run ? <div className="dl"><div className="bar"><i style={{ width: Math.max(3, inst.pct) + '%' }} /></div><span className="dl-msg">{inst.msg}</span></div>
                  : !x.problem && !x.ready && <button className="btn pri sm" onClick={() => install(x.id)}><IcDown size={14} /> Install{(s => s ? ` (${mb(s)})` : '')(x.models.filter(y => !y.have).reduce((a, y) => a + (y.size || 0), 0))}</button>}
                <button className="btn ghost sm" onClick={() => call('open_path', x.dir)}><IcFolder size={14} /></button>
              </div>
            </div>
          </div>
        );
      })}</div>
    </section>
  );
}

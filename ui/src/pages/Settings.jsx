import React from 'react';
import { call } from '../api.js';
import { Seg } from '../ui.jsx';
import { IcFolder } from '../icons.jsx';
import { LAYOUTS } from '../AddWindow.jsx';

export default function Settings({ cfg, hello, setConfig, say, onUpdate }) {
  const [checking, setChecking] = React.useState(false);
  const checkUpdate = async () => {
    setChecking(true);
    try {
      const u = await call('check_update');
      if (u.newer) { onUpdate(u); say(`Version ${u.latest} is out`, 'ok'); } else say(`You have the newest version (${u.current})`, 'ok');
    } catch (e) { say('Could not check: ' + e.message, 'err'); }
    setChecking(false);
  };
  const browse = async (key, extra = {}) => { const f = await call('pick_folder'); if (f) setConfig({ [key]: f, ...extra }); };
  const dev = hello?.device;
  return (
    <div className="page">
      <header className="ph"><div><h1>Settings</h1><p>Saved on this computer only.</p></div></header>

      <section className="card set">
        <h2>Output</h2>
        <Field label="Where stems go" hint={(LAYOUTS.find(l => l.id === cfg.outMode) || LAYOUTS[0]).text}>
          <Seg value={cfg.outMode} onChange={v => (v !== 'next' && !cfg.outDir ? browse('outDir', { outMode: v, layoutChosen: true }) : setConfig({ outMode: v, layoutChosen: true }))}
            options={LAYOUTS.map(l => [l.id, l.id === 'next' ? 'Next to each track' : l.id === 'mirror' ? 'Stems folder, same sub folders' : 'Stems folder, all together'])} />
        </Field>
        {cfg.outMode !== 'next' && (
          <Field label="Stems folder"><div className="in-row"><input readOnly value={cfg.outDir} /><button className="btn sm" onClick={() => browse('outDir')}><IcFolder size={14} /> Browse</button></div></Field>
        )}
        <Field label="Skip tracks with stems" hint="When you add a folder again, tracks that have stems already are not done again.">
          <Seg value={cfg.skipDone ? 'y' : 'n'} onChange={v => setConfig({ skipDone: v === 'y' })} options={[['y', 'Skip them'], ['n', 'Make them again']]} />
        </Field>
        <Field label="Folder name" hint="Each track gets its own folder."><code>My Track Stems / My Track - Vocals.{cfg.format.toLowerCase()}</code></Field>
        <Field label="When the folder is already there">
          <Seg value={cfg.overwrite ? 'y' : 'n'} onChange={v => setConfig({ overwrite: v === 'y' })} options={[['n', 'Make a new one (2)'], ['y', 'Replace the files']]} />
        </Field>
        <Field label="File format" hint={cfg.format === 'FLAC' ? 'Lossless and small. Best for DJ use.' : cfg.format === 'WAV' ? 'Lossless, big files.' : 'Small files, some quality loss.'}>
          <Seg value={cfg.format} onChange={v => setConfig({ format: v })} options={[['FLAC', 'FLAC'], ['WAV', 'WAV'], ['MP3', 'MP3']]} />
        </Field>
        {cfg.format === 'MP3' && <Field label="MP3 quality"><Seg value={cfg.mp3Bitrate} onChange={v => setConfig({ mp3Bitrate: v })} options={[['192k', '192k'], ['256k', '256k'], ['320k', '320k']]} /></Field>}
      </section>

      <section className="card set">
        <h2>Engine</h2>
        <Field label="Run on" hint={dev ? `Found: ${dev.name}` : ''}>
          <Seg value={cfg.device} onChange={v => setConfig({ device: v })} options={[['auto', 'Auto'], ['cpu', 'CPU only']]} />
        </Field>
        <Field label="Model folder" hint="Models are big (100 MB – 1 GB each). Move them to a disk with space.">
          <div className="in-row"><input readOnly value={cfg.modelDirUsed} /><button className="btn sm" onClick={() => browse('modelDir')}><IcFolder size={14} /> Change</button>
            {cfg.modelDir && <button className="btn ghost sm" onClick={() => setConfig({ modelDir: '' })}>Default</button>}</div>
        </Field>
      </section>

      <section className="card set">
        <h2>dubplates.net</h2>
        <Field label="Make stems from the site" hint="The Live mix on dubplates.net sends tracks here and loads the stems back into the deck.">
          <Seg value={cfg.trustSite ? 'y' : 'n'} onChange={v => setConfig({ trustSite: v === 'y' })} options={[['n', 'Ask me first'], ['y', 'Start without asking']]} />
        </Field>
        <Field label="Music folders" hint="Where the site's music folders are on this computer.">
          {Object.keys(cfg.roots || {}).length ? <div className="roots">{Object.entries(cfg.roots).map(([k, v]) => (
            <div key={k} className="in-row"><code title={v}>{k} → {v}</code><button className="btn ghost sm" onClick={() => { const r = { ...cfg.roots }; delete r[k]; setConfig({ roots: r }); }}>Forget</button></div>
          ))}</div> : <small className="dim">None yet: the first “Make stems” from the site asks.</small>}
        </Field>
      </section>

      <section className="card set about">
        <h2>About</h2>
        <p>Dubplates.net Client {hello?.version}. Free and open source (GPL-3.0). Engine: audio-separator and PyTorch.
          Models belong to their authors and have their own licences.</p>
        <div className="in-row">
          <button className="btn sm" onClick={checkUpdate} disabled={checking}>{checking ? 'Checking…' : 'Check for updates'}</button>
          <button className="btn sm" onClick={() => call('open_url', 'https://github.com/psychofreud/dubplatesclient')}>Source code</button>
          <button className="btn sm" onClick={() => call('open_path', cfg.appDir)}>Open settings folder</button>
        </div>
      </section>
    </div>
  );
}

function Field({ label, hint, children }) {
  return (
    <div className="field">
      <div className="f-l"><b>{label}</b>{hint && <small>{hint}</small>}</div>
      <div className="f-r">{children}</div>
    </div>
  );
}

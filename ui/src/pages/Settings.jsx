import React from 'react';
import { call } from '../api.js';
import { Seg } from '../ui.jsx';
import { IcFolder } from '../icons.jsx';

export default function Settings({ cfg, hello, setConfig }) {
  const browse = async key => { const f = await call('pick_folder'); if (f) setConfig({ [key]: f, ...(key === 'outDir' ? { outMode: 'folder' } : {}) }); };
  const dev = hello?.device;
  return (
    <div className="page">
      <header className="ph"><div><h1>Settings</h1><p>Saved on this computer only.</p></div></header>

      <section className="card set">
        <h2>Output</h2>
        <Field label="Where stems go">
          <Seg value={cfg.outMode} onChange={v => (v === 'folder' && !cfg.outDir ? browse('outDir') : setConfig({ outMode: v }))}
            options={[['next', 'Next to the track'], ['folder', 'One folder']]} />
        </Field>
        {cfg.outMode === 'folder' && (
          <Field label="Folder"><div className="in-row"><input readOnly value={cfg.outDir} /><button className="btn sm" onClick={() => browse('outDir')}><IcFolder size={14} /> Browse</button></div></Field>
        )}
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
        <Field label="Account" hint="Soon: link this computer to your dubplates.net account and load stems straight into the mixer.">
          <button className="btn" disabled>Link this computer (coming soon)</button>
        </Field>
      </section>

      <section className="card set about">
        <h2>About</h2>
        <p>Dubplates.net Client {hello?.version}. Free and open source (GPL-3.0). Engine: audio-separator and PyTorch.
          Models belong to their authors and have their own licences.</p>
        <div className="in-row">
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

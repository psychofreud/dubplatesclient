import React from 'react';
import { call } from './api.js';
import { IcStems, IcModels, IcSettings, IcChip, IcLink } from './icons.jsx';
import Separate from './pages/Separate.jsx';
import Models from './pages/Models.jsx';
import Settings from './pages/Settings.jsx';
import Setup from './pages/Setup.jsx';
import LinkAsk from './LinkAsk.jsx';

const PAGES = [
  { id: 'separate', label: 'Make stems', Icon: IcStems },
  { id: 'models', label: 'Models', Icon: IcModels },
  { id: 'settings', label: 'Settings', Icon: IcSettings },
];

// First: hello. No engine yet (first start) = the setup page, else the app.
export default function App() {
  const [hello, setHello] = React.useState(null);
  const [err, setErr] = React.useState('');
  React.useEffect(() => { call('hello').then(setHello).catch(e => setErr(e.message)); }, []);
  if (!hello) return <div className="app solo"><div className="bg" /><div className="center">{err ? <span className="err">{err}</span> : <><span className="spin" /> Starting…</>}</div></div>;
  return hello.setup ? <Setup hello={hello} /> : <Main hello={hello} />;
}

function Main({ hello }) {
  const [page, setPage] = React.useState('separate');
  const [cfg, setCfg] = React.useState(hello.config);
  const [models, setModels] = React.useState([]);
  const [st, setSt] = React.useState({ jobs: [], installs: {} });
  const [toast, setToast] = React.useState(null);

  const say = React.useCallback((text, kind = 'info') => { setToast({ text, kind, t: Date.now() }); }, []);
  React.useEffect(() => { if (!toast) return; const t = setTimeout(() => setToast(null), toast.kind === 'err' ? 6000 : 3500); return () => clearTimeout(t); }, [toast]);

  const loadModels = React.useCallback(async (refresh = false) => {
    try { setModels(await call('models', refresh)); } catch (e) { say(e.message, 'err'); }
  }, [say]);

  React.useEffect(() => { loadModels(); }, [loadModels]);
  // a newer release on GitHub? (once per start; no network = no message)
  const [upd, setUpd] = React.useState(null);
  React.useEffect(() => { call('check_update').then(u => u.newer && setUpd(u)).catch(() => {}); }, []);

  // live state: jobs + installs (fast while something runs)
  const busy = st.jobs.some(j => j.state === 'running' || j.state === 'queued') || Object.values(st.installs).some(i => !i.done);
  const prevInst = React.useRef('');
  React.useEffect(() => {
    let dead = false;
    const tick = async () => {
      try {
        const s = await call('state');
        if (dead) return;
        setSt(s);
        const key = Object.entries(s.installs).map(([k, v]) => k + v.done + v.err).join('|');
        if (key !== prevInst.current) { const was = prevInst.current; prevInst.current = key; if (was) loadModels(); }
      } catch { /* */ }
    };
    tick();
    const t = setInterval(tick, busy ? 400 : 1500);
    return () => { dead = true; clearInterval(t); };
  }, [busy, loadModels]);

  const setConfig = async patch => { try { setCfg(await call('set_config', patch)); } catch (e) { say(e.message, 'err'); } };
  const running = st.jobs.filter(j => j.state === 'running' || j.state === 'queued').length;
  const dev = hello?.device;

  return (
    <div className="app">
      <div className="bg" />
      <aside className="side">
        <div className="brand"><img src="assets/logo-dark.png" alt="dubplates.net" /><span>Client</span></div>
        <nav>
          {PAGES.map(({ id, label, Icon }) => (
            <button key={id} className={'nav' + (page === id ? ' on' : '')} onClick={() => setPage(id)}>
              <Icon /><span>{label}</span>
              {id === 'separate' && running > 0 && <em className="pill">{running}</em>}
            </button>
          ))}
        </nav>
        <div className="side-foot">
          {upd && (
            <div className="upd">
              <b>Version {upd.latest} is out</b>
              <small>You have {upd.current}. Install it over this one: your models and settings stay.</small>
              <button className="btn pri sm" onClick={() => call('open_url', upd.url)}>Download</button>
            </div>
          )}
          {dev && (
            <div className={'device ' + dev.kind} title="The engine runs on this">
              <IcChip size={16} />
              <div><b>{dev.kind === 'cuda' ? 'NVIDIA GPU' : dev.kind === 'mps' ? 'Apple GPU' : 'CPU'}</b><small>{dev.name}{dev.memGB ? ` · ${dev.memGB} GB` : ''}</small></div>
            </div>
          )}
          <button className="site-link" onClick={() => call('open_url', 'https://dubplates.net')}><IcLink size={14} /> dubplates.net</button>
          <small className="ver">v{hello?.version || '…'} · GPL-3.0</small>
        </div>
      </aside>
      <main className="main">
        {!cfg ? <div className="center"><span className="spin" /> Starting the engine…</div> : (
          page === 'separate' ? <Separate cfg={cfg} models={models} jobs={st.jobs} say={say} go={setPage} setConfig={setConfig} />
            : page === 'models' ? <Models cfg={cfg} models={models} installs={st.installs} reload={loadModels} say={say} setConfig={setConfig} go={setPage} />
              : <Settings cfg={cfg} hello={hello} setConfig={setConfig} say={say} onUpdate={setUpd} />
        )}
      </main>
      {cfg && <LinkAsk cfg={cfg} models={models} setConfig={setConfig} say={say} go={setPage} />}
      {toast && <div className={'toast ' + toast.kind} key={toast.t} onClick={() => setToast(null)}>{toast.text}</div>}
    </div>
  );
}

// First start: download and install the stem engine (PyTorch + audio-separator), then start the app again.
import React from 'react';
import { call } from '../api.js';
import { IcChip, IcCheck, IcWarn, IcDown } from '../icons.jsx';

export default function Setup({ hello }) {
  const info = hello.setup;
  const [pick, setPick] = React.useState(info.recommended);
  const [st, setSt] = React.useState(null);
  const [showLog, setShowLog] = React.useState(false);
  const logRef = React.useRef(null);
  const running = st?.running;

  React.useEffect(() => {
    if (!st || (!st.running && !st.done)) return;
    const t = setInterval(async () => { try { setSt(await call('setup_state')); } catch { /* */ } }, 500);
    return () => clearInterval(t);
  }, [st?.running, st?.done]);
  React.useEffect(() => { if (st?.done) { const t = setTimeout(() => call('restart'), 1200); return () => clearTimeout(t); } }, [st?.done]);
  React.useEffect(() => { if (logRef.current) logRef.current.scrollTop = 1e9; }, [st?.log?.length, showLog]);

  const start = async () => {
    try { await call('setup_start', pick); setSt(await call('setup_state')); } catch (e) { setSt({ error: e.message, log: [] }); }
  };

  return (
    <div className="app solo">
      <div className="bg" />
      <div className="setup">
        <img className="setup-logo" src="assets/logo-stack-dark.png" alt="dubplates.net" />
        <div className="card setup-card">
          {!st || (!st.running && !st.done && !st.error) ? (
            <>
              <h1>Welcome</h1>
              <p className="lead">The client needs its stem engine (PyTorch). It is a one-time download.</p>
              <div className="opts">
                {info.options.map(o => (
                  <button key={o.id} className={'opt' + (pick === o.id ? ' on' : '')} onClick={() => setPick(o.id)}>
                    <IcChip size={20} />
                    <div><b>{o.label}{o.id === info.recommended && <span className="badge">Best for this PC</span>}</b><small>Download: {o.size}</small></div>
                  </button>
                ))}
              </div>
              {info.gpu ? <p className="hint">Found: {info.gpu}</p> : <p className="hint">No NVIDIA GPU found: stems are made on the CPU (works, but slower).</p>}
              <button className="btn pri big" onClick={start}><IcDown size={16} /> Install the engine</button>
            </>
          ) : st.error ? (
            <>
              <h1><IcWarn size={22} /> Setup stopped</h1>
              <p className="err">{st.error}</p>
              <p className="lead">Check the internet connection and the free disk space, then try again.</p>
              <button className="btn pri big" onClick={start}>Try again</button>
            </>
          ) : st.done ? (
            <>
              <h1><IcCheck size={22} /> Ready</h1>
              <p className="lead">Starting the client…</p>
            </>
          ) : (
            <>
              <h1>Installing the engine</h1>
              <p className="lead">{st.step}</p>
              <div className="bar big"><i style={{ width: Math.max(2, st.pct) + '%' }} /></div>
              <div className="setup-msg"><span>{st.msg}</span><span className="mono">{Math.round(st.pct)}%</span></div>
              <p className="hint">This takes a few minutes. You can keep working in other programs.</p>
            </>
          )}
          {(running || st?.error) && st?.log?.length > 0 && (
            <div className="setup-log">
              <a onClick={() => setShowLog(!showLog)}>{showLog ? 'Hide details' : 'Show details'}</a>
              {showLog && <pre ref={logRef}>{st.log.join('\n')}</pre>}
            </div>
          )}
        </div>
        <small className="ver">Dubplates.net Client {hello.version} · free and open source (GPL-3.0)</small>
      </div>
    </div>
  );
}

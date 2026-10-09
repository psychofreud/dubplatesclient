// A model dropdown that tells the user what each model does: stem count, the stems, a short text.
import React from 'react';
import { StemChips } from './ui.jsx';

export const GROUPS = { vocals: 'Vocals & instrumental', multi: 'Multi-stem', clean: 'Clean-up', custom: 'Custom', all: 'Other models' };

const count = m => (m.stems?.length ? `${m.stems.length} stems` : 'stems: see name');

export default function ModelPicker({ models, value, onChange, placeholder = 'Pick a model' }) {
  const [open, setOpen] = React.useState(false);
  const box = React.useRef(null);
  const sel = models.find(m => m.file === value);

  React.useEffect(() => {
    if (!open) return;
    const off = e => { if (box.current && !box.current.contains(e.target)) setOpen(false); };
    const key = e => { if (e.key === 'Escape') setOpen(false); };
    window.addEventListener('mousedown', off); window.addEventListener('keydown', key);
    return () => { window.removeEventListener('mousedown', off); window.removeEventListener('keydown', key); };
  }, [open]);

  return (
    <div className={'mpk' + (open ? ' open' : '')} ref={box}>
      <button className="mpk-btn" onClick={() => setOpen(!open)} aria-haspopup="listbox" aria-expanded={open}>
        {sel ? <><b>{sel.name}</b><span className="mpk-n">{count(sel)}</span></> : <span className="dim">{placeholder}</span>}
        <i className="mpk-car" />
      </button>
      {open && (
        <div className="mpk-pop" role="listbox">
          {Object.entries(GROUPS).map(([g, label]) => {
            const list = models.filter(m => m.group === g);
            if (!list.length) return null;
            return (
              <div key={g} className="mpk-grp">
                <div className="mpk-gl">{label}</div>
                {list.map(m => (
                  <button key={m.file} role="option" aria-selected={m.file === value} className={'mpk-it' + (m.file === value ? ' on' : '')}
                    onClick={() => { onChange(m.file); setOpen(false); }}>
                    <div className="mpk-top"><b>{m.name}</b>{m.badge && <span className="badge">{m.badge}</span>}<span className="mpk-n">{count(m)}</span></div>
                    {m.desc && <p>{m.desc}</p>}
                    <StemChips stems={m.stems} />
                  </button>
                ))}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

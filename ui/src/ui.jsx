// Small shared parts
import React from 'react';

const STEM_HUE = { vocals: 20, instrumental: 200, drums: 50, bass: 280, guitar: 140, piano: 320, other: 0, kick: 40, snare: 90, toms: 120, 'hi-hat': 170, ride: 230, crash: 300, 'no reverb': 20, reverb: 250 };
// a stem's colour (hue); unknown names get one from their letters
export const stemHue = name => { const k = String(name || '').toLowerCase(); if (k in STEM_HUE) return STEM_HUE[k]; let h = 0; for (const ch of k) h = (h * 31 + ch.charCodeAt(0)) % 360; return h; };

export function StemChips({ stems }) {
  if (!stems?.length) return null;
  return (
    <span className="stems">
      {stems.map(s => {
        const h = STEM_HUE[s.toLowerCase()];
        return <em key={s} style={h !== undefined ? { '--h': h } : undefined} className={h === undefined ? 'n' : ''}>{s}</em>;
      })}
    </span>
  );
}

export const fmtTime = s => (s >= 60 ? `${Math.floor(s / 60)}m ${String(s % 60).padStart(2, '0')}s` : `${s}s`);

export function Seg({ value, options, onChange }) {
  return (
    <div className="seg">
      {options.map(([v, l]) => <button key={v} className={value === v ? 'on' : ''} onClick={() => onChange(v)}>{l}</button>)}
    </div>
  );
}

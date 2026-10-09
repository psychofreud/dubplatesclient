// Line icons (24x24, stroke = currentColor)
import React from 'react';

const I = ({ d, size = 18, fill, className }) => (
  <svg className={className} width={size} height={size} viewBox="0 0 24 24" fill={fill ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{d}</svg>
);

export const IcStems = p => <I {...p} d={<><path d="M4 7h3M4 12h7M4 17h5" /><path d="M14 4v16M18 8v8M22 10v4" /></>} />;
export const IcModels = p => <I {...p} d={<><rect x="3" y="4" width="18" height="6" rx="2" /><rect x="3" y="14" width="18" height="6" rx="2" /><path d="M7 7h.01M7 17h.01" /></>} />;
export const IcSettings = p => <I {...p} d={<><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" /></>} />;
export const IcUpload = p => <I {...p} d={<><path d="M12 16V4M7 9l5-5 5 5" /><path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" /></>} />;
export const IcFolder = p => <I {...p} d={<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />} />;
export const IcFile = p => <I {...p} d={<><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" /><path d="M14 3v5h5" /><path d="M10 17v-4l4-1v4" /><circle cx="9" cy="17" r="1" /><circle cx="13" cy="16" r="1" /></>} />;
export const IcX = p => <I {...p} d={<path d="M6 6l12 12M18 6L6 18" />} />;
export const IcCheck = p => <I {...p} d={<path d="M5 12l5 5 9-10" />} />;
export const IcDown = p => <I {...p} d={<><path d="M12 4v12M7 11l5 5 5-5" /><path d="M5 20h14" /></>} />;
export const IcTrash = p => <I {...p} d={<><path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13" /></>} />;
export const IcRefresh = p => <I {...p} d={<><path d="M20 11a8 8 0 1 0-2.3 5.7" /><path d="M20 4v7h-7" /></>} />;
export const IcPlus = p => <I {...p} d={<path d="M12 5v14M5 12h14" />} />;
export const IcSearch = p => <I {...p} d={<><circle cx="11" cy="11" r="7" /><path d="M20 20l-4-4" /></>} />;
export const IcChip = p => <I {...p} d={<><rect x="6" y="6" width="12" height="12" rx="2" /><path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4" /></>} />;
export const IcWarn = p => <I {...p} d={<><path d="M12 3l10 18H2z" /><path d="M12 10v5M12 18h.01" /></>} />;
export const IcLink = p => <I {...p} d={<><path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1" /><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1" /></>} />;

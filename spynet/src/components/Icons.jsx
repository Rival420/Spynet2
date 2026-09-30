import React from 'react';

const P = { fill: 'none', stroke: 'currentColor', strokeWidth: 1.6, strokeLinecap: 'round', strokeLinejoin: 'round' };

export function TypeIcon({ type, size = 18 }) {
  const common = { width: size, height: size, viewBox: '0 0 24 24', ...P, 'aria-hidden': true };
  switch (type) {
    case 'router': return <svg {...common}><rect x="3" y="13" width="18" height="7" rx="2" /><path d="M7 16.5h.01M11 16.5h.01" /><path d="M12 13V8M8.5 6.5a5 5 0 0 1 7 0M6 4a8.5 8.5 0 0 1 12 0" /></svg>;
    case 'phone': return <svg {...common}><rect x="7" y="2.5" width="10" height="19" rx="2" /><path d="M11 18h2" /></svg>;
    case 'tablet': return <svg {...common}><rect x="4" y="3" width="16" height="18" rx="2" /><path d="M11 17.5h2" /></svg>;
    case 'laptop': return <svg {...common}><rect x="4" y="5" width="16" height="11" rx="1.5" /><path d="M2 19h20" /></svg>;
    case 'computer': return <svg {...common}><rect x="3" y="4" width="18" height="12" rx="1.5" /><path d="M9 20h6M12 16v4" /></svg>;
    case 'tv': return <svg {...common}><rect x="2.5" y="5" width="19" height="12" rx="1.5" /><path d="M8 20h8" /></svg>;
    case 'speaker': return <svg {...common}><rect x="6" y="3" width="12" height="18" rx="2" /><circle cx="12" cy="14.5" r="3" /><circle cx="12" cy="7.5" r="1" /></svg>;
    case 'camera': return <svg {...common}><path d="M4 8h3l2-2.5h6L17 8h3v11H4z" /><circle cx="12" cy="13" r="3.2" /></svg>;
    case 'iot': return <svg {...common}><path d="M12 3v3M12 18v3M3 12h3M18 12h3" /><circle cx="12" cy="12" r="4" /></svg>;
    case 'printer': return <svg {...common}><path d="M7 8V3h10v5" /><rect x="3" y="8" width="18" height="9" rx="1.5" /><path d="M7 14h10v7H7z" /></svg>;
    case 'console': return <svg {...common}><path d="M6 8h12a4 4 0 0 1 4 4l-1 6a2 2 0 0 1-3.5 1L15 16H9l-2.5 3A2 2 0 0 1 3 18l-1-6a4 4 0 0 1 4-4z" /><path d="M8 11v3M6.5 12.5h3M16 12h.01M18 13.5h.01" /></svg>;
    case 'server': return <svg {...common}><rect x="3" y="3" width="18" height="7" rx="1.5" /><rect x="3" y="14" width="18" height="7" rx="1.5" /><path d="M7 6.5h.01M7 17.5h.01" /></svg>;
    case 'nas': return <svg {...common}><rect x="4" y="3" width="16" height="18" rx="2" /><path d="M8 8h8M8 12h8M8 16h8" /></svg>;
    default: return <svg {...common}><circle cx="12" cy="12" r="8" /><path d="M12 8v4l2.5 1.5" /></svg>;
  }
}

export const EVENT_GLYPH = {
  new_device: '✦',
  online: '●',
  offline: '○',
  ip_change: '⇄',
  ports_changed: '◫',
  scanner: '▸',
  test: '▸',
};

export function CloseIcon(props) {
  return <svg width="18" height="18" viewBox="0 0 24 24" {...P} {...props} aria-hidden><path d="M6 6l12 12M18 6L6 18" /></svg>;
}

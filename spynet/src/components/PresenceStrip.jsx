import React, { useMemo } from 'react';

/* A horizontal strip of the last `hours`: filled where the device was online. */
export default function PresenceStrip({ spans = [], hours = 24, now, height = 8, ticks = false, title }) {
  const end = now;
  const start = end - hours * 3600 * 1000;
  const segments = useMemo(() => spans
    .map(([s, e]) => [Math.max(start, Date.parse(s)), Math.min(end, e ? Date.parse(e) : end)])
    .filter(([s, e]) => e > s)
    .map(([s, e]) => ({ x: ((s - start) / (end - start)) * 100, w: ((e - s) / (end - start)) * 100 })), [spans, start, end]);
  const uptime = segments.reduce((acc, seg) => acc + seg.w, 0);
  const tickCount = hours <= 24 ? hours / 6 : hours / 24;
  return (
    <div className="presence" title={title || `${Math.round(uptime)}% online in the last ${hours <= 24 ? `${hours} h` : `${hours / 24} days`}`}>
      <svg viewBox="0 0 100 10" preserveAspectRatio="none" width="100%" height={height} aria-hidden>
        <rect x="0" y="1" width="100" height="8" className="presence-track" />
        {segments.map((seg, i) => (
          <rect key={i} x={seg.x} y="1" width={Math.max(seg.w, 0.4)} height="8" className="presence-on" />
        ))}
      </svg>
      {ticks && (
        <div className="presence-ticks" aria-hidden>
          {Array.from({ length: tickCount + 1 }, (_, i) => {
            const t = start + (i / tickCount) * (end - start);
            const d = new Date(t);
            return <span key={i}>{hours <= 24 ? d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' }) : d.toLocaleDateString(undefined, { weekday: 'short' })}</span>;
          })}
        </div>
      )}
    </div>
  );
}

export function uptimePercent(spans = [], hours = 24, now = Date.now()) {
  const end = now, start = end - hours * 3600 * 1000;
  let total = 0;
  for (const [s, e] of spans) {
    const a = Math.max(start, Date.parse(s)), b = Math.min(end, e ? Date.parse(e) : end);
    if (b > a) total += b - a;
  }
  return Math.round((total / (end - start)) * 100);
}

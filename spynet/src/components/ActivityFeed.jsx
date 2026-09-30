import React, { useMemo } from 'react';
import { dayLabel, deviceLabel, formatTime } from '../format.js';
import { EVENT_GLYPH } from './Icons.jsx';

export default function ActivityFeed({ events, devices, onSelect, onClear }) {
  const groups = useMemo(() => {
    const out = [];
    let current = null;
    for (const ev of events) {
      const day = dayLabel(ev.ts);
      if (!current || current.day !== day) {
        current = { day, items: [] };
        out.push(current);
      }
      current.items.push(ev);
    }
    return out;
  }, [events]);

  return (
    <div className="activity">
      <div className="activity-head">
        <h2>Activity</h2>
        {events.length > 0 && <button className="btn quiet small" onClick={onClear}>Clear</button>}
      </div>
      {events.length === 0 ? (
        <p className="faint pad">Joins, departures, address changes and new open ports show up here.</p>
      ) : (
        <div className="activity-scroll">
          {groups.map((g) => (
            <section key={g.day}>
              <h3>{g.day}</h3>
              <ul>
                {g.items.map((ev) => {
                  const d = ev.mac ? devices[ev.mac] : null;
                  return (
                    <li key={ev.id} className={`ev ${ev.kind}`}>
                      <span className="glyph" aria-hidden>{EVENT_GLYPH[ev.kind] || '·'}</span>
                      <div className="ev-body">
                        {d ? (
                          <button className="link" onClick={() => onSelect(ev.mac)}>{messageFor(ev, d)}</button>
                        ) : (
                          <span>{ev.message}</span>
                        )}
                        <time dateTime={ev.ts}>{formatTime(ev.ts)}</time>
                      </div>
                    </li>
                  );
                })}
              </ul>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}

/* Rewrite the stored message with the device's current name, so renaming a
   device updates its history too. */
export function messageFor(ev, d) {
  const name = deviceLabel(d);
  switch (ev.kind) {
    case 'new_device': return `New device ${ev.ip}${d.vendor ? ` (${d.vendor})` : ''}`;
    case 'online': return `${name} is online`;
    case 'offline': return `${name} went offline`;
    case 'ip_change': return `${name} moved from ${ev.details.from} to ${ev.details.to}`;
    case 'ports_changed': {
      const parts = [];
      if (ev.details.opened && ev.details.opened.length) parts.push(`opened ${ev.details.opened.join(', ')}`);
      if (ev.details.closed && ev.details.closed.length) parts.push(`closed ${ev.details.closed.join(', ')}`);
      return `${name} ${parts.join('; ')}`;
    }
    default: return ev.message;
  }
}

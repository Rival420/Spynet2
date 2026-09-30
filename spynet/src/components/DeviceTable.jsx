import React, { useMemo, useState } from 'react';
import { compareIp, deviceLabel, deviceSubtitle, guessType, timeAgo } from '../format.js';
import { TypeIcon } from './Icons.jsx';

const FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'online', label: 'Online' },
  { id: 'offline', label: 'Offline' },
  { id: 'new', label: 'Unrecognized' },
];

const SORTS = {
  ip: { label: 'IP address', fn: (a, b) => compareIp(a.ip, b.ip) },
  name: { label: 'Name', fn: (a, b) => deviceLabel(a).localeCompare(deviceLabel(b)) },
  seen: { label: 'Last seen', fn: (a, b) => Date.parse(b.last_seen || 0) - Date.parse(a.last_seen || 0) },
  first: { label: 'Newest first', fn: (a, b) => Date.parse(b.first_seen || 0) - Date.parse(a.first_seen || 0) },
  ports: { label: 'Most open ports', fn: (a, b) => b.ports.length - a.ports.length },
};

export default function DeviceTable({ devices, selectedMac, onSelect, now, scanner, actions, onOpenSettings }) {
  const [filter, setFilter] = useState('all');
  const [sort, setSort] = useState('ip');
  const [query, setQuery] = useState('');

  const counts = useMemo(() => ({
    all: devices.length,
    online: devices.filter((d) => d.online).length,
    offline: devices.filter((d) => !d.online).length,
    new: devices.filter((d) => !d.known).length,
  }), [devices]);

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return devices
      .filter((d) => {
        if (filter === 'online' && !d.online) return false;
        if (filter === 'offline' && d.online) return false;
        if (filter === 'new' && d.known) return false;
        if (!q) return true;
        return [d.name, d.hostname, d.vendor, d.ip, d.mac, d.notes, ...d.ports.map(String)]
          .some((v) => v && v.toLowerCase().includes(q));
      })
      .sort((a, b) => {
        // Unrecognized devices float to the top: they are what you came to see.
        if (a.known !== b.known) return a.known ? 1 : -1;
        if (sort === 'ip' && a.online !== b.online) return a.online ? -1 : 1;
        return SORTS[sort].fn(a, b);
      });
  }, [devices, filter, sort, query]);

  return (
    <div className="device-table">
      <div className="table-tools">
        <div className="segmented" role="tablist" aria-label="Filter devices">
          {FILTERS.map((f) => (
            <button key={f.id} role="tab" aria-selected={filter === f.id}
              className={`${filter === f.id ? 'active' : ''} ${f.id === 'new' && counts.new ? 'attention' : ''}`}
              onClick={() => setFilter(f.id)}>
              {f.label} <span className="count">{counts[f.id]}</span>
            </button>
          ))}
        </div>
        <div className="tools-right">
          <input className="search" type="search" placeholder="Search name, IP, MAC, vendor, port" value={query}
            onChange={(e) => setQuery(e.target.value)} aria-label="Search devices" />
          <select value={sort} onChange={(e) => setSort(e.target.value)} aria-label="Sort devices">
            {Object.entries(SORTS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
          </select>
          {counts.new > 0 && (
            <button className="btn small" onClick={actions.acknowledgeAll} title="Mark every device currently listed as recognized">
              Recognize all
            </button>
          )}
        </div>
      </div>

      {devices.length === 0 ? (
        <EmptyState scanner={scanner} onOpenSettings={onOpenSettings} actions={actions} />
      ) : rows.length === 0 ? (
        <div className="empty"><p>No devices match.</p></div>
      ) : (
        <table>
          <thead>
            <tr>
              <th className="col-status"><span className="sr-only">Status</span></th>
              <th>Device</th>
              <th>Address</th>
              <th className="col-ports">Open ports</th>
              <th className="col-seen">Last seen</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((d) => (
              <DeviceRow key={d.mac} d={d} now={now} selected={d.mac === selectedMac} onSelect={onSelect} />
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function DeviceRow({ d, now, selected, onSelect }) {
  const subtitle = deviceSubtitle(d);
  const type = guessType(d);
  return (
    <tr className={`${selected ? 'selected' : ''} ${d.online ? 'online' : 'offline'} ${d.known ? '' : 'unknown'}`}
      onClick={() => onSelect(d.mac)} tabIndex={0}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(d.mac); } }}>
      <td className="col-status">
        <span key={d.last_seen} className={`dot ${d.online ? 'on' : 'off'}`} aria-label={d.online ? 'Online' : 'Offline'} />
      </td>
      <td className="col-device">
        <div className="device-cell">
          <span className={`type-icon ${type ? '' : 'faint'}`}><TypeIcon type={type} /></span>
          <div className="device-names">
            <div className="device-title">
              <span className="label">{deviceLabel(d)}</span>
              {!d.known && <span className="tag new">New</span>}
              {d.is_self && <span className="tag">This machine</span>}
            </div>
            {subtitle && <div className="device-sub">{subtitle}</div>}
          </div>
        </div>
      </td>
      <td className="col-addr">
        <div className="mono ip">{d.ip || '—'}</div>
        <div className="mono mac">{d.mac}</div>
      </td>
      <td className="col-ports">
        <PortChips d={d} />
      </td>
      <td className="col-seen">
        <span title={d.last_seen}>{d.online ? 'now' : timeAgo(d.last_seen, now)}</span>
      </td>
    </tr>
  );
}

export function PortChips({ d, max = 5 }) {
  if (d.scanning) return <span className="scanning">scanning…</span>;
  if (d.scan_queued) return <span className="scanning faint">scan queued</span>;
  if (!d.ports.length) return <span className="faint">{d.ports_scanned_at ? 'none' : 'not scanned'}</span>;
  const shown = d.services.slice(0, max);
  const rest = d.ports.length - shown.length;
  return (
    <div className="chips">
      {shown.map((s) => (
        <span key={s.port} className="chip mono" title={s.name || undefined}>{s.port}</span>
      ))}
      {rest > 0 && <span className="chip more">+{rest}</span>}
    </div>
  );
}

function EmptyState({ scanner, onOpenSettings, actions }) {
  const state = scanner ? scanner.state : 'stopped';
  if (scanner && scanner.last_error) {
    return (
      <div className="empty">
        <h2>Spynet cannot open a raw socket</h2>
        <p>{scanner.last_error}</p>
        <p>On the Pi the systemd unit grants this automatically. When running by hand, use <code>sudo</code>.</p>
      </div>
    );
  }
  if (state === 'stopped') {
    return (
      <div className="empty">
        <h2>Nothing here yet</h2>
        <p>Choose the network to watch and start scanning. Devices appear after the first sweep, usually within a few seconds.</p>
        <div className="row gap">
          <button className="btn primary" onClick={onOpenSettings}>Choose network</button>
          {scanner && scanner.network && <button className="btn" onClick={() => actions.start()}>Start watching {scanner.network}</button>}
        </div>
      </div>
    );
  }
  return (
    <div className="empty">
      <h2>Waiting for the first sweep</h2>
      <p>Listening for replies on {scanner.network}…</p>
    </div>
  );
}

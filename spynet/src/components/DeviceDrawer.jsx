import React, { useEffect, useState } from 'react';
import { deviceLabel, formatDateTime, guessType, timeAgo, TYPE_LABELS } from '../format.js';
import { CloseIcon, TypeIcon, EVENT_GLYPH } from './Icons.jsx';
import { formatTime, dayLabel } from '../format.js';
import { messageFor } from './ActivityFeed.jsx';

export default function DeviceDrawer({ device: d, deviceTypes, now, actions, onClose }) {
  const [name, setName] = useState(d.name);
  const [notes, setNotes] = useState(d.notes);
  const [type, setType] = useState(d.device_type);
  const [scanMode, setScanMode] = useState('quick');
  const [range, setRange] = useState({ start: 1, end: 1024 });
  const [banners, setBanners] = useState({});
  const [history, setHistory] = useState([]);
  const [confirmForget, setConfirmForget] = useState(false);

  const dirty = name !== d.name || notes !== d.notes || type !== d.device_type;

  useEffect(() => {
    let alive = true;
    actions.fetchDevice(d.mac).then((full) => { if (alive && full) setHistory(full.events || []); }).catch(() => {});
    return () => { alive = false; };
  }, [d.mac, d.last_seen, d.ports_scanned_at, actions]);

  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const save = () => actions.updateDevice(d.mac, { name, notes, device_type: type, known: true });
  const toggleKnown = () => actions.updateDevice(d.mac, { known: !d.known });
  const readBanner = async (port) => {
    setBanners((b) => ({ ...b, [port]: { loading: true } }));
    const r = await actions.banner(d.mac, port);
    setBanners((b) => ({ ...b, [port]: r ? { text: r.banner } : { text: 'Request failed.' } }));
  };
  const startScan = () => actions.portScan(d.mac, scanMode === 'range' ? { mode: 'range', ...range } : { mode: scanMode });

  const effectiveType = guessType(d);

  return (
    <aside className="drawer" aria-label={`Details for ${deviceLabel(d)}`}>
      <header className="drawer-head">
        <div className="drawer-title">
          <span className={`dot big ${d.online ? 'on' : 'off'}`} />
          <span className="type-icon"><TypeIcon type={effectiveType} size={22} /></span>
          <div>
            <h2>{deviceLabel(d)}</h2>
            <p className="faint">
              {d.online ? 'Online now' : `Last seen ${timeAgo(d.last_seen, now)}`}
              {' · first seen '}{formatDateTime(d.first_seen)}
            </p>
          </div>
        </div>
        <button className="btn icon quiet" onClick={onClose} aria-label="Close"><CloseIcon /></button>
      </header>

      <div className="drawer-body">
        {!d.known && (
          <div className="callout attention">
            <div>
              <strong>Not recognized yet.</strong> Give it a name if it is yours, or keep an eye on it.
            </div>
            <button className="btn small" onClick={toggleKnown}>Mark as recognized</button>
          </div>
        )}

        <dl className="facts">
          <div><dt>IP address</dt><dd className="mono">{d.ip || '—'}{d.previous_ip && <span className="faint"> (was {d.previous_ip})</span>}</dd></div>
          <div><dt>MAC address</dt><dd className="mono">{d.mac}</dd></div>
          <div><dt>Vendor</dt><dd>{d.vendor || <span className="faint">unknown</span>}</dd></div>
          <div><dt>Hostname</dt><dd>{d.hostname || <span className="faint">none announced</span>}</dd></div>
        </dl>
        <div className="row gap">
          <button className="btn small" onClick={() => actions.refreshDevice(d.mac)}>Look up name and vendor again</button>
          {d.known && <button className="btn small quiet" onClick={toggleKnown}>Mark as unrecognized</button>}
        </div>

        <section>
          <h3>Identity</h3>
          <label className="field">
            <span>Name</span>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder={d.hostname || d.vendor || 'e.g. Living room TV'} />
          </label>
          <label className="field">
            <span>Type</span>
            <select value={type} onChange={(e) => setType(e.target.value)}>
              {deviceTypes.map((t) => <option key={t} value={t}>{TYPE_LABELS[t] || t}{!t && effectiveType ? ` (guess: ${TYPE_LABELS[effectiveType]})` : ''}</option>)}
            </select>
          </label>
          <label className="field">
            <span>Notes</span>
            <textarea rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Where it lives, who owns it, anything worth remembering" />
          </label>
          <button className="btn primary" onClick={save} disabled={!dirty && d.known}>
            {d.known ? 'Save changes' : 'Save and mark as recognized'}
          </button>
        </section>

        <section>
          <h3>Open ports</h3>
          {d.scanning ? <p className="scanning">Scanning…</p>
            : d.scan_queued ? <p className="faint">Scan queued.</p>
            : d.services.length === 0 ? (
              <p className="faint">{d.ports_scanned_at ? `No open TCP ports found (checked ${timeAgo(d.ports_scanned_at, now)}).` : 'Not scanned yet.'}</p>
            ) : (
              <ul className="services">
                {d.services.map((s) => (
                  <li key={s.port}>
                    <div className="service-row">
                      <span className="mono port">{s.port}</span>
                      <span className="service-name">{s.name || <span className="faint">unknown service</span>}</span>
                      {isWeb(s.port) && <a className="btn small quiet" href={`${isTls(s.port) ? 'https' : 'http'}://${d.ip}:${s.port}`} target="_blank" rel="noreferrer">Open</a>}
                      <button className="btn small quiet" onClick={() => readBanner(s.port)} disabled={banners[s.port]?.loading}>
                        {banners[s.port]?.loading ? 'Reading…' : 'Read banner'}
                      </button>
                    </div>
                    {banners[s.port]?.text && <pre className="banner">{banners[s.port].text}</pre>}
                  </li>
                ))}
              </ul>
            )}
          {d.ports_scanned_at && d.services.length > 0 && <p className="faint small">Checked {timeAgo(d.ports_scanned_at, now)}.</p>}
          <div className="row gap wrap">
            <select value={scanMode} onChange={(e) => setScanMode(e.target.value)} aria-label="Scan type">
              <option value="quick">Common ports (fast)</option>
              <option value="range">Port range</option>
              <option value="full">All 65,535 ports (slow)</option>
            </select>
            {scanMode === 'range' && (
              <>
                <input type="number" min={1} max={65535} value={range.start} onChange={(e) => setRange({ ...range, start: +e.target.value })} aria-label="First port" />
                <input type="number" min={1} max={65535} value={range.end} onChange={(e) => setRange({ ...range, end: +e.target.value })} aria-label="Last port" />
              </>
            )}
            <button className="btn" onClick={startScan} disabled={!d.ip || d.scanning || d.scan_queued}>Scan ports</button>
          </div>
        </section>

        <section>
          <h3>History</h3>
          {history.length === 0 ? <p className="faint">No events recorded.</p> : (
            <ul className="timeline">
              {history.slice(0, 40).map((ev) => (
                <li key={ev.id}>
                  <span className={`glyph ${ev.kind}`} aria-hidden>{EVENT_GLYPH[ev.kind] || '·'}</span>
                  <span className="msg">{messageFor(ev, d)}</span>
                  <time dateTime={ev.ts} title={formatDateTime(ev.ts)}>{dayLabel(ev.ts)} {formatTime(ev.ts)}</time>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="danger">
          {confirmForget ? (
            <div className="row gap">
              <span>Forget this device and its history? It comes back as new if it reappears.</span>
              <button className="btn danger small" onClick={() => actions.forgetDevice(d.mac).then(onClose)}>Forget</button>
              <button className="btn small quiet" onClick={() => setConfirmForget(false)}>Keep</button>
            </div>
          ) : (
            <button className="btn quiet small" onClick={() => setConfirmForget(true)}>Forget this device</button>
          )}
        </section>
      </div>
    </aside>
  );
}

const WEB_PORTS = new Set([80, 81, 443, 3000, 5000, 5001, 7443, 8000, 8008, 8080, 8081, 8088, 8123, 8443, 8888, 9000, 9090, 9443, 10000, 32400]);
const TLS_PORTS = new Set([443, 5001, 7443, 8443, 9443]);
const isWeb = (p) => WEB_PORTS.has(p);
const isTls = (p) => TLS_PORTS.has(p);

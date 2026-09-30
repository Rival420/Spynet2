import React, { useEffect, useState } from 'react';
import { CloseIcon } from './Icons.jsx';

export default function SettingsDialog({ settings, scanner, firstRun, actions, onClose }) {
  const [form, setForm] = useState({ ...settings });
  const [detecting, setDetecting] = useState(false);
  const [interfaces, setInterfaces] = useState(scanner && scanner.interfaces ? scanner.interfaces : []);
  const [saving, setSaving] = useState(false);
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  useEffect(() => {
    if (firstRun && !form.network) detect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const detect = async () => {
    setDetecting(true);
    const r = await actions.detectNetwork();
    if (r) {
      if (r.interfaces) setInterfaces(r.interfaces);
      if (r.network && !form.network) set('network', r.network);
    }
    setDetecting(false);
  };

  const submit = async (startAfter) => {
    setSaving(true);
    const saved = await actions.saveSettings(form);
    setSaving(false);
    if (!saved) return;
    if (startAfter) await actions.start(saved.network);
    onClose();
  };

  const running = scanner && scanner.state !== 'stopped';

  return (
    <div className="modal-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby="settings-title">
        <header className="modal-head">
          <h2 id="settings-title">{firstRun ? 'Welcome. Which network should Spynet watch?' : 'Settings'}</h2>
          <button className="btn icon quiet" onClick={onClose} aria-label="Close"><CloseIcon /></button>
        </header>

        <form className="modal-body" onSubmit={(e) => { e.preventDefault(); submit(firstRun); }}>
          <section>
            <h3>Network</h3>
            <label className="field">
              <span>Networks to watch (CIDR, separate several with commas)</span>
              <div className="row gap">
                <input className="mono" value={form.network} onChange={(e) => set('network', e.target.value)} placeholder="192.168.1.0/24, 192.168.20.0/24" required />
                <button type="button" className="btn" onClick={detect} disabled={detecting}>{detecting ? 'Detecting…' : 'Detect'}</button>
              </div>
              <small className="faint">ARP does not cross routers: this machine needs an interface on every network it watches, for example a VLAN sub-interface such as <code>eth0.20</code>.</small>
            </label>
            {interfaces.length > 0 && (
              <ul className="iface-list">
                {interfaces.map((i) => {
                  const listed = form.network.split(/[\s,;]+/).includes(i.network);
                  return (
                    <li key={`${i.iface}-${i.ip}`}>
                      <span className="mono">{i.network}</span>
                      <span className="faint"> via {i.iface} ({i.ip})</span>
                      {listed ? <span className="faint small"> watched</span>
                        : <button type="button" className="btn small quiet" onClick={() => set('network', form.network ? `${form.network}, ${i.network}` : i.network)}>Add</button>}
                    </li>
                  );
                })}
              </ul>
            )}
            <div className="grid2">
              <label className="field">
                <span>Sweep every (seconds)</span>
                <input type="number" min={5} max={3600} value={form.sweep_interval} onChange={(e) => set('sweep_interval', +e.target.value)} />
                <small className="faint">How often every address is asked to answer. 30 s is a good default.</small>
              </label>
              <label className="field">
                <span>Offline after (seconds)</span>
                <input type="number" min={10} max={86400} value={form.offline_after} onChange={(e) => set('offline_after', +e.target.value)} />
                <small className="faint">Phones nap between sweeps. Allow a few missed sweeps before calling a device offline.</small>
              </label>
              <label className="field">
                <span>Reply timeout (seconds)</span>
                <input type="number" min={1} max={30} value={form.arp_timeout} onChange={(e) => set('arp_timeout', +e.target.value)} />
              </label>
            </div>
          </section>

          <section>
            <h3>Port scans</h3>
            <div className="grid2">
              <label className="field">
                <span>Automatic scan</span>
                <select value={form.portscan_mode} onChange={(e) => set('portscan_mode', e.target.value)}>
                  <option value="quick">Common ports (recommended)</option>
                  <option value="range">Port range</option>
                  <option value="full">All ports (slow, noisy)</option>
                  <option value="off">Off, only on request</option>
                </select>
              </label>
              <label className="field">
                <span>Rescan each device every (seconds)</span>
                <input type="number" min={60} max={604800} value={form.portscan_interval} onChange={(e) => set('portscan_interval', +e.target.value)} />
              </label>
              {form.portscan_mode === 'range' && (
                <>
                  <label className="field"><span>First port</span><input type="number" min={1} max={65535} value={form.port_range_start} onChange={(e) => set('port_range_start', +e.target.value)} /></label>
                  <label className="field"><span>Last port</span><input type="number" min={1} max={65535} value={form.port_range_end} onChange={(e) => set('port_range_end', +e.target.value)} /></label>
                </>
              )}
              <label className="field">
                <span>Connect timeout (seconds)</span>
                <input type="number" step="0.1" min={0.2} max={10} value={form.port_timeout} onChange={(e) => set('port_timeout', +e.target.value)} />
              </label>
            </div>
          </section>

          <section>
            <h3>Notifications</h3>
            <label className="field">
              <span>Webhook URL</span>
              <div className="row gap">
                <input className="mono" type="url" value={form.webhook_url} onChange={(e) => set('webhook_url', e.target.value)} placeholder="https://homeassistant.local:8123/api/webhook/spynet" />
                <button type="button" className="btn" onClick={actions.testWebhook} disabled={!settings.webhook_url}>Send test</button>
              </div>
              <small className="faint">Spynet posts JSON with the event and the device. Works with Home Assistant webhooks, ntfy, n8n and similar. Save before sending a test.</small>
            </label>
            <div className="checks">
              <label><input type="checkbox" checked={form.notify_new_device} onChange={(e) => set('notify_new_device', e.target.checked)} /> New device appears</label>
              <label><input type="checkbox" checked={form.notify_ports_changed} onChange={(e) => set('notify_ports_changed', e.target.checked)} /> Open ports change</label>
              <label><input type="checkbox" checked={form.notify_online} onChange={(e) => set('notify_online', e.target.checked)} /> Device comes online</label>
              <label><input type="checkbox" checked={form.notify_offline} onChange={(e) => set('notify_offline', e.target.checked)} /> Device goes offline</label>
            </div>
          </section>

          <section>
            <h3>Startup</h3>
            <label className="check-line">
              <input type="checkbox" checked={form.auto_start} onChange={(e) => set('auto_start', e.target.checked)} />
              <span>Resume watching when the service starts <small className="faint">(set automatically when you press Start)</small></span>
            </label>
          </section>

          <footer className="modal-foot">
            {!firstRun && <a className="btn quiet" href={`${import.meta.env.VITE_API_ENDPOINT || ''}/api/devices/export.csv`}>Export devices as CSV</a>}
            <span className="spacer" />
            <button type="button" className="btn quiet" onClick={onClose}>Cancel</button>
            {firstRun ? (
              <button type="submit" className="btn primary" disabled={saving || !form.network}>Save and start watching</button>
            ) : (
              <button type="submit" className="btn primary" disabled={saving}>{running ? 'Save and apply' : 'Save'}</button>
            )}
          </footer>
        </form>
      </div>
    </div>
  );
}

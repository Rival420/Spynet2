import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from './api.js';
import { useSpynet, useNow } from './useSpynet.js';
import TopBar from './components/TopBar.jsx';
import DeviceTable from './components/DeviceTable.jsx';
import DeviceDrawer from './components/DeviceDrawer.jsx';
import ActivityFeed from './components/ActivityFeed.jsx';
import SettingsDialog from './components/SettingsDialog.jsx';
import Toasts, { useToasts } from './components/Toasts.jsx';

export default function App() {
  const { devices, events, presence, scanner, settings, deviceTypes, connected, loadError, reload } = useSpynet();
  const now = useNow(1000);
  const { toasts, toast, dismiss } = useToasts();
  const [selectedMac, setSelectedMac] = useState(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [mobilePane, setMobilePane] = useState('devices');

  const deviceList = useMemo(() => Object.values(devices), [devices]);
  const selected = selectedMac ? devices[selectedMac] : null;
  const firstRun = settings && !settings.network && scanner && scanner.state === 'stopped';

  useEffect(() => {
    if (firstRun) setSettingsOpen(true);
  }, [firstRun]);

  useEffect(() => {
    if (selectedMac && !devices[selectedMac]) setSelectedMac(null);
  }, [devices, selectedMac]);

  const run = useCallback(async (fn, okMessage) => {
    try {
      const r = await fn();
      if (okMessage) toast(typeof okMessage === 'function' ? okMessage(r) : okMessage);
      return r;
    } catch (e) {
      toast(e.message, 'error');
      return null;
    }
  }, [toast]);

  const actions = useMemo(() => ({
    start: (network) => run(() => api.post('/api/scanner/start', network ? { network } : {}), 'Scanner started'),
    pause: () => run(() => api.post('/api/scanner/pause'), 'Scanner paused'),
    resume: () => run(() => api.post('/api/scanner/resume'), 'Scanner resumed'),
    stop: () => run(() => api.post('/api/scanner/stop'), 'Scanner stopped'),
    sweep: () => run(() => api.post('/api/scanner/sweep'), 'Sweeping now'),
    saveSettings: (body) => run(() => api.put('/api/settings', body), 'Settings saved'),
    detectNetwork: () => run(() => api.get('/api/network/detect')),
    testWebhook: () => run(() => api.post('/api/settings/test_webhook'), 'Test notification sent'),
    updateDevice: (mac, body) => run(() => api.patch(`/api/devices/${mac}`, body), 'Device saved'),
    forgetDevice: (mac) => run(() => api.del(`/api/devices/${mac}`), 'Device forgotten'),
    acknowledgeAll: () => run(() => api.post('/api/devices/acknowledge_all'),
      (r) => `${r.acknowledged} device${r.acknowledged === 1 ? '' : 's'} marked as recognized`),
    portScan: (mac, body) => run(() => api.post(`/api/devices/${mac}/portscan`, body),
      (r) => (r.queued ? 'Port scan queued' : 'A scan is already running for this device')),
    banner: (mac, port) => run(() => api.post(`/api/devices/${mac}/banner`, { port })),
    acceptBaseline: (mac) => run(() => api.post(`/api/devices/${mac}/baseline`, { mode: 'current' }), 'Current ports accepted as the baseline'),
    clearBaseline: (mac) => run(() => api.post(`/api/devices/${mac}/baseline`, { mode: 'clear' }), 'Baseline cleared'),
    fetchPresence: (mac, hours) => api.get(`/api/presence?hours=${hours}&mac=${mac}`),
    refreshDevice: (mac) => run(() => api.post(`/api/devices/${mac}/refresh`), 'Looking up name and vendor'),
    clearEvents: () => run(() => api.del('/api/events'), 'Activity cleared'),
    fetchDevice: (mac) => api.get(`/api/devices/${mac}`),
  }), [run]);

  const selectDevice = useCallback((mac) => {
    setSelectedMac(mac);
    if (mac && window.innerWidth < 900) setMobilePane('devices');
  }, []);

  if (loadError && !scanner) {
    return (
      <div className="boot-error">
        <h1>Spynet</h1>
        <p>The dashboard cannot reach the API.</p>
        <code>{loadError}</code>
        <p>Start the server and this page will retry automatically.</p>
        <RetryOnTimer onRetry={reload} />
      </div>
    );
  }

  return (
    <div className={`app ${selected ? 'has-drawer' : ''}`}>
      <TopBar
        scanner={scanner}
        settings={settings}
        connected={connected}
        now={now}
        actions={actions}
        onOpenSettings={() => setSettingsOpen(true)}
      />

      <div className="pane-switch" role="tablist">
        <button role="tab" aria-selected={mobilePane === 'devices'} className={mobilePane === 'devices' ? 'active' : ''} onClick={() => setMobilePane('devices')}>Devices</button>
        <button role="tab" aria-selected={mobilePane === 'activity'} className={mobilePane === 'activity' ? 'active' : ''} onClick={() => setMobilePane('activity')}>Activity</button>
      </div>

      <main className="layout">
        <section className={`devices-pane ${mobilePane === 'devices' ? 'show' : ''}`}>
          <DeviceTable
            devices={deviceList}
            selectedMac={selectedMac}
            onSelect={selectDevice}
            now={now}
            presence={presence}
            scanner={scanner}
            actions={actions}
            onOpenSettings={() => setSettingsOpen(true)}
          />
        </section>
        <aside className={`activity-pane ${mobilePane === 'activity' ? 'show' : ''}`}>
          <ActivityFeed events={events} devices={devices} onSelect={selectDevice} onClear={actions.clearEvents} />
        </aside>
      </main>

      {selected && (
        <DeviceDrawer
          key={selected.mac}
          device={selected}
          deviceTypes={deviceTypes}
          presence={presence[selected.mac] || []}
          networks={scanner ? scanner.networks : []}
          now={now}
          actions={actions}
          onClose={() => setSelectedMac(null)}
        />
      )}

      {settingsOpen && settings && (
        <SettingsDialog
          settings={settings}
          scanner={scanner}
          firstRun={firstRun}
          actions={actions}
          onClose={() => setSettingsOpen(false)}
        />
      )}

      <Toasts toasts={toasts} dismiss={dismiss} />
    </div>
  );
}

function RetryOnTimer({ onRetry }) {
  useEffect(() => {
    const t = setInterval(onRetry, 3000);
    return () => clearInterval(t);
  }, [onRetry]);
  return null;
}

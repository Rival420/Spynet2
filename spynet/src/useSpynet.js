import { useCallback, useEffect, useRef, useState } from 'react';
import { io } from 'socket.io-client';
import { api, BASE } from './api.js';

const MAX_EVENTS = 500;

export function useSpynet() {
  const [devices, setDevices] = useState({});
  const [events, setEvents] = useState([]);
  const [presence, setPresence] = useState({});
  const [scanner, setScanner] = useState(null);
  const [settings, setSettings] = useState(null);
  const [deviceTypes, setDeviceTypes] = useState(['']);
  const [connected, setConnected] = useState(false);
  const [loadError, setLoadError] = useState('');
  const socketRef = useRef(null);

  const load = useCallback(async () => {
    try {
      const s = await api.get('/api/state');
      setDevices(Object.fromEntries(s.devices.map((d) => [d.mac, d])));
      setEvents(s.events);
      setPresence(s.presence || {});
      setScanner(s.scanner);
      setSettings(s.settings);
      setDeviceTypes(s.device_types);
      setLoadError('');
    } catch (e) {
      setLoadError(e.message);
    }
  }, []);

  const loadPresence = useCallback(async () => {
    try { setPresence(await api.get('/api/presence?hours=24')); } catch { /* keep the old strip */ }
  }, []);

  useEffect(() => {
    const t = setInterval(loadPresence, 60000);
    return () => clearInterval(t);
  }, [loadPresence]);

  useEffect(() => {
    load();
    const socket = io(BASE || undefined, { transports: ['websocket', 'polling'] });
    socketRef.current = socket;
    socket.on('connect', () => { setConnected(true); load(); });
    socket.on('disconnect', () => setConnected(false));
    socket.on('devices', (list) => setDevices(Object.fromEntries(list.map((d) => [d.mac, d]))));
    socket.on('device', (d) => {
      setDevices((prev) => {
        const next = { ...prev };
        if (d.deleted) delete next[d.mac]; else next[d.mac] = d;
        return next;
      });
    });
    socket.on('event', (ev) => {
      setEvents((prev) => [ev, ...prev].slice(0, MAX_EVENTS));
      if (ev.kind === 'online' || ev.kind === 'offline' || ev.kind === 'new_device') loadPresence();
    });
    socket.on('events_cleared', () => setEvents([]));
    socket.on('scanner', setScanner);
    socket.on('settings', setSettings);
    return () => socket.disconnect();
  }, [load, loadPresence]);

  return { devices, events, presence, scanner, settings, deviceTypes, connected, loadError, reload: load };
}

export function useNow(intervalMs = 1000) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(t);
  }, [intervalMs]);
  return now;
}

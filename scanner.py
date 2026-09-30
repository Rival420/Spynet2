"""The scanning engine: periodic ARP sweeps for presence, a queue-driven port
scanner, background vendor/hostname enrichment and an event log."""
import ipaddress
import json
import logging
import queue
import threading
import time
from datetime import timedelta

import settings as settings_store
import vendor
from db import session_scope
from discovery import RawSocketPermissionError, arp_sweep, detect_network, resolve_hostname
from models import Device, Event, iso, utcnow
from notify import send_webhook
from port_scanner import ports_for_mode, scan_ports, service_name

log = logging.getLogger("spynet.scanner")

HOSTNAME_RECHECK = timedelta(hours=24)


def display_name(d):
    return d.name or d.hostname or d.vendor or d.mac


class NetworkScanner:
    def __init__(self, emit):
        self.emit = emit                      # emit(event_name, payload)
        self.settings = settings_store.load()
        self.state = "stopped"                # stopped | running | paused
        self.lock = threading.RLock()
        self.iface = ""
        self.local_ip = ""
        self.local_mac = ""
        self.last_sweep_at = None
        self.next_sweep_at = None
        self.last_sweep_duration = 0.0
        self.last_sweep_found = 0
        self.sweep_count = 0
        self.last_error = ""
        self.sweeping = False

        self._stop = threading.Event()
        self._wake = threading.Event()
        self._sweep_guard = threading.Lock()
        self._loop_thread = None

        self._port_q = queue.Queue()
        self._port_queued = set()
        self.scanning = set()                 # MACs with a port scan in flight
        self._enrich_q = queue.Queue()
        self._enrich_queued = set()

        threading.Thread(target=self._port_worker, daemon=True, name="portscan").start()
        threading.Thread(target=self._enrich_worker, daemon=True, name="enrich").start()

    # ------------------------------------------------------------------ control

    def apply_settings(self, new_settings):
        with self.lock:
            self.settings = new_settings
        self._wake.set()

    def start(self, network=None):
        network = (network or self.settings["network"] or "").strip()
        if not network:
            network, self.iface, self.local_ip = detect_network()
            if not network:
                raise ValueError("Could not detect the local network. Enter it as CIDR, e.g. 192.168.1.0/24.")
        try:
            net = ipaddress.ip_network(network, strict=False)
        except ValueError as exc:
            raise ValueError(f"'{network}' is not a valid network. Use CIDR, e.g. 192.168.1.0/24.") from exc
        if net.num_addresses > 65536:
            raise ValueError("Networks larger than /16 are not supported.")
        network = str(net)
        self.settings = settings_store.save({"network": network, "auto_start": True})
        self._detect_self()
        with self.lock:
            self.last_error = ""
            self.state = "running"
            if self._loop_thread is None or not self._loop_thread.is_alive():
                self._stop.clear()
                self._loop_thread = threading.Thread(target=self._loop, daemon=True, name="sweep")
                self._loop_thread.start()
        self._wake.set()
        self._log_scanner_event(f"Started watching {network}")
        self.emit("scanner", self.status())

    def pause(self):
        with self.lock:
            if self.state == "running":
                self.state = "paused"
                self.next_sweep_at = None
        self._log_scanner_event("Paused")
        self.emit("scanner", self.status())

    def resume(self):
        with self.lock:
            if self.state == "paused":
                self.state = "running"
        self._wake.set()
        self._log_scanner_event("Resumed")
        self.emit("scanner", self.status())

    def stop(self):
        with self.lock:
            self.state = "stopped"
            self.next_sweep_at = None
        self._stop.set()
        self._wake.set()
        self.settings = settings_store.save({"auto_start": False})
        self._log_scanner_event("Stopped")
        self.emit("scanner", self.status())

    def sweep_now(self):
        """Run one sweep immediately, whatever the state."""
        if self.state == "running":
            self._wake.set()
            return
        threading.Thread(target=self._safe_sweep, daemon=True, name="sweep-once").start()

    def shutdown(self):
        self._stop.set()
        self._wake.set()

    # -------------------------------------------------------------------- loop

    def _detect_self(self):
        try:
            from scapy.all import conf, get_if_addr, get_if_hwaddr
            self.iface = conf.route.route("0.0.0.0")[0]
            self.local_ip = get_if_addr(self.iface)
            self.local_mac = get_if_hwaddr(self.iface).lower()
        except Exception as exc:  # pragma: no cover
            log.debug("could not detect local interface: %s", exc)

    def _loop(self):
        while not self._stop.is_set():
            if self.state == "running":
                self._safe_sweep()
                if self._stop.is_set():
                    break
            interval = self.settings["sweep_interval"]
            with self.lock:
                self.next_sweep_at = time.time() + interval if self.state == "running" else None
            self.emit("scanner", self.status())
            self._wake.wait(interval)
            self._wake.clear()

    def _safe_sweep(self):
        if not self._sweep_guard.acquire(blocking=False):
            return
        try:
            self.sweep()
        except RawSocketPermissionError as exc:
            log.error("%s", exc)
            with self.lock:
                self.last_error = str(exc)
                self.state = "stopped"
                self.next_sweep_at = None
            self._stop.set()
            self.emit("scanner", self.status())
        except Exception as exc:
            log.exception("sweep failed")
            with self.lock:
                self.last_error = f"Sweep failed: {exc}"
            self.emit("scanner", self.status())
        finally:
            self._sweep_guard.release()

    # ------------------------------------------------------------------- sweep

    def sweep(self):
        cfg = self.settings
        network = cfg["network"]
        if not network:
            raise ValueError("No network configured")
        started = time.time()
        with self.lock:
            self.sweeping = True
        self.emit("scanner", self.status())

        found = arp_sweep(network, timeout=cfg["arp_timeout"])
        if self.local_ip and self.local_mac:
            try:
                if ipaddress.ip_address(self.local_ip) in ipaddress.ip_network(network, strict=False):
                    found.append({"ip": self.local_ip, "mac": self.local_mac})
            except ValueError:
                pass

        now = utcnow()
        offline_after = timedelta(seconds=cfg["offline_after"])
        new_events = []
        snapshot = []
        to_enrich, to_scan = [], []   # queued after commit so workers can see the rows
        with session_scope() as s:
            devices = {d.mac: d for d in s.query(Device).all()}
            seen = set()
            for host in found:
                mac, ip = host["mac"], host["ip"]
                if mac in seen:
                    continue
                seen.add(mac)
                d = devices.get(mac)
                if d is None:
                    d = Device(mac=mac, ip=ip, vendor=vendor.cached_vendor(mac), online=True,
                               first_seen=now, last_seen=now)
                    s.add(d)
                    devices[mac] = d
                    label = d.vendor or "unknown vendor"
                    new_events.append(self._event(s, "new_device", d,
                                                  f"New device {ip} ({label})", {"vendor": d.vendor}))
                    to_enrich.append(mac)
                    to_scan.append(mac)
                    continue
                if ip and d.ip != ip:
                    if d.ip:
                        new_events.append(self._event(s, "ip_change", d,
                                                      f"{display_name(d)} moved from {d.ip} to {ip}",
                                                      {"from": d.ip, "to": ip}))
                        d.previous_ip = d.ip
                    d.ip = ip
                if not d.online:
                    d.online = True
                    new_events.append(self._event(s, "online", d, f"{display_name(d)} is online"))
                d.last_seen = now
                if not d.vendor or not d.hostname and (
                        d.hostname_checked_at is None or now - d.hostname_checked_at > HOSTNAME_RECHECK):
                    to_enrich.append(mac)
                if cfg["portscan_mode"] != "off" and (
                        d.ports_scanned_at is None
                        or (now - d.ports_scanned_at).total_seconds() > cfg["portscan_interval"]):
                    to_scan.append(mac)

            for mac, d in devices.items():
                if mac in seen or not d.online:
                    continue
                if d.last_seen is None or now - d.last_seen > offline_after:
                    d.online = False
                    new_events.append(self._event(s, "offline", d, f"{display_name(d)} went offline"))
            s.flush()
            snapshot = [self._device_dict(d) for d in devices.values()]
            event_dicts = [e.to_dict() for e in new_events]

        for mac in to_enrich:
            self._queue_enrich(mac)
        for mac in to_scan:
            self._queue_port_scan(mac)

        with self.lock:
            self.sweeping = False
            self.sweep_count += 1
            self.last_sweep_at = time.time()
            self.last_sweep_duration = round(time.time() - started, 2)
            self.last_sweep_found = len(seen)
            self.last_error = ""
        log.info("Sweep %d: %d hosts answered in %.1fs", self.sweep_count, len(seen), self.last_sweep_duration)
        self.emit("devices", snapshot)
        for ev in event_dicts:
            self.emit("event", ev)
            self._maybe_notify(ev)
        self.emit("scanner", self.status())

    # ------------------------------------------------------------------ events

    def _event(self, s, kind, device, message, details=None):
        ev = Event(kind=kind, mac=device.mac if device else "", ip=device.ip if device else "",
                   message=message, details_json=json.dumps(details or {}))
        s.add(ev)
        return ev

    def _log_scanner_event(self, message):
        with session_scope() as s:
            ev = self._event(s, "scanner", None, message)
            s.flush()
            payload = ev.to_dict()
        self.emit("event", payload)

    def _maybe_notify(self, ev):
        cfg = self.settings
        wanted = {
            "new_device": cfg["notify_new_device"],
            "online": cfg["notify_online"],
            "offline": cfg["notify_offline"],
            "ports_changed": cfg["notify_ports_changed"],
        }
        if not cfg["webhook_url"] or not wanted.get(ev["kind"]):
            return
        device = None
        if ev["mac"]:
            with session_scope() as s:
                d = s.query(Device).filter_by(mac=ev["mac"]).first()
                device = d.to_dict() if d else None
        send_webhook(cfg["webhook_url"], {"source": "spynet", "event": ev, "device": device})

    # -------------------------------------------------------------- port scans

    def _queue_port_scan(self, mac, mode=None, start=None, end=None):
        key = mac
        with self.lock:
            if key in self._port_queued or key in self.scanning:
                return False
            self._port_queued.add(key)
        self._port_q.put((mac, mode, start, end))
        return True

    def request_port_scan(self, mac, mode="quick", start=1, end=1024):
        if mode not in ("quick", "range", "full"):
            raise ValueError("mode must be quick, range or full")
        queued = self._queue_port_scan(mac, mode, start, end)
        if queued:
            self.emit("device", self._device_dict_by_mac(mac))
        return queued

    def _port_worker(self):
        while True:
            mac, mode, start, end = self._port_q.get()
            with self.lock:
                self._port_queued.discard(mac)
            try:
                self._run_port_scan(mac, mode, start, end)
            except Exception:
                log.exception("port scan failed for %s", mac)
            finally:
                with self.lock:
                    self.scanning.discard(mac)
                self.emit("device", self._device_dict_by_mac(mac))

    def _run_port_scan(self, mac, mode, start, end):
        cfg = self.settings
        if mode is None:
            mode = cfg["portscan_mode"]
            start, end = cfg["port_range_start"], cfg["port_range_end"]
            if mode == "off":
                return
        ports = ports_for_mode(mode, start or 1, end or 1024)
        with session_scope() as s:
            d = s.query(Device).filter_by(mac=mac).first()
            if d is None or not d.ip:
                return
            ip, previous, first_scan = d.ip, set(d.ports), d.ports_scanned_at is None
        with self.lock:
            self.scanning.add(mac)
        self.emit("device", self._device_dict_by_mac(mac))

        open_ports = set(scan_ports(ip, ports, timeout=cfg["port_timeout"],
                                    should_abort=self._stop.is_set if self.state == "stopped" else None))
        scanned = set(ports)
        # Ports outside the scanned set keep their previous state.
        merged = (previous - scanned) | open_ports
        opened = sorted(merged - previous)
        closed = sorted(previous - merged)

        ev_dict = None
        with session_scope() as s:
            d = s.query(Device).filter_by(mac=mac).first()
            if d is None:
                return
            d.ports = merged
            d.ports_scanned_at = utcnow()
            if not first_scan and (opened or closed):
                parts = []
                if opened:
                    parts.append("opened " + ", ".join(map(str, opened)))
                if closed:
                    parts.append("closed " + ", ".join(map(str, closed)))
                ev = self._event(s, "ports_changed", d, f"{display_name(d)} {'; '.join(parts)}",
                                 {"opened": opened, "closed": closed})
                s.flush()
                ev_dict = ev.to_dict()
        if ev_dict:
            self.emit("event", ev_dict)
            self._maybe_notify(ev_dict)

    # -------------------------------------------------------------- enrichment

    def _queue_enrich(self, mac):
        with self.lock:
            if mac in self._enrich_queued:
                return
            self._enrich_queued.add(mac)
        self._enrich_q.put(mac)

    def refresh_device(self, mac):
        """Force a fresh vendor + hostname lookup."""
        with session_scope() as s:
            d = s.query(Device).filter_by(mac=mac).first()
            if d is None:
                return False
            d.hostname_checked_at = None
        self._queue_enrich(mac)
        return True

    def _enrich_worker(self):
        while True:
            mac = self._enrich_q.get()
            with self.lock:
                self._enrich_queued.discard(mac)
            try:
                self._enrich(mac)
            except Exception:
                log.exception("enrichment failed for %s", mac)

    def _enrich(self, mac):
        with session_scope() as s:
            d = s.query(Device).filter_by(mac=mac).first()
            if d is None:
                return
            ip, has_vendor, hostname, checked = d.ip, bool(d.vendor), d.hostname, d.hostname_checked_at
        new_vendor = None if has_vendor else vendor.lookup_vendor(mac)
        new_hostname = None
        if ip and (not hostname or checked is None):
            new_hostname = resolve_hostname(ip)
        with session_scope() as s:
            d = s.query(Device).filter_by(mac=mac).first()
            if d is None:
                return
            if new_vendor:
                d.vendor = new_vendor
            if new_hostname is not None:
                d.hostname_checked_at = utcnow()
                if new_hostname:
                    d.hostname = new_hostname
            payload = self._device_dict(d)
        self.emit("device", payload)

    # ------------------------------------------------------------------- views

    def _device_dict(self, d):
        data = d.to_dict()
        data["scanning"] = d.mac in self.scanning
        data["scan_queued"] = d.mac in self._port_queued
        data["is_self"] = bool(self.local_mac) and d.mac == self.local_mac
        data["services"] = [{"port": p, "name": service_name(p)} for p in data["ports"]]
        return data

    def _device_dict_by_mac(self, mac):
        with session_scope() as s:
            d = s.query(Device).filter_by(mac=mac).first()
            return self._device_dict(d) if d else {"mac": mac, "deleted": True}

    def all_devices(self):
        with session_scope() as s:
            return [self._device_dict(d) for d in s.query(Device).all()]

    def status(self):
        with self.lock:
            return {
                "state": self.state,
                "network": self.settings["network"],
                "iface": self.iface,
                "local_ip": self.local_ip,
                "sweeping": self.sweeping,
                "sweep_interval": self.settings["sweep_interval"],
                "last_sweep_at": iso(utcnow() - timedelta(seconds=time.time() - self.last_sweep_at))
                if self.last_sweep_at else None,
                "next_sweep_in": max(0, round(self.next_sweep_at - time.time())) if self.next_sweep_at else None,
                "last_sweep_duration": self.last_sweep_duration,
                "last_sweep_found": self.last_sweep_found,
                "sweep_count": self.sweep_count,
                "port_queue": len(self._port_queued) + len(self.scanning),
                "last_error": self.last_error,
            }

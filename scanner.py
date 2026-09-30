"""The scanning engine: periodic ARP sweeps for presence, a queue-driven port
scanner, background vendor/hostname enrichment, presence spans and an event
log."""
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
from discovery import RawSocketPermissionError, arp_sweep, interface_for, local_interfaces, resolve_hostname
from models import Device, Event, Presence, iso, utcnow
from notify import send_webhook
from port_scanner import ports_for_mode, scan_ports, service_name

log = logging.getLogger("spynet.scanner")

HOSTNAME_RECHECK = timedelta(hours=24)
NO_INTERFACE = ("This machine has no interface on this network, so ARP cannot reach it. "
                "Add a VLAN interface (e.g. eth0.20) or remove the network.")


def display_name(d):
    return d.name or d.hostname or d.vendor or d.mac


class NetworkScanner:
    def __init__(self, emit):
        self.emit = emit                      # emit(event_name, payload)
        self.settings = settings_store.load()
        self.state = "stopped"                # stopped | running | paused
        self.lock = threading.RLock()
        self.interfaces = []                  # local interfaces (from discovery)
        self.iface = ""
        self.local_ip = ""
        self.local_macs = set()
        self.network_warnings = {}            # network -> human readable problem
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

        self._close_dangling_spans()
        self._detect_self()
        threading.Thread(target=self._port_worker, daemon=True, name="portscan").start()
        threading.Thread(target=self._enrich_worker, daemon=True, name="enrich").start()

    # ------------------------------------------------------------------ control

    @property
    def networks(self):
        return settings_store.parse_networks(self.settings.get("network", ""))

    def apply_settings(self, new_settings):
        with self.lock:
            self.settings = new_settings
        self._detect_self()
        self._wake.set()

    def start(self, network=None):
        network = (network or self.settings["network"] or "").strip()
        if not network:
            self._detect_self()
            network = next((i["network"] for i in self.interfaces if i["iface"] == self.iface), "")
            if not network:
                raise ValueError("Could not detect the local network. Enter it as CIDR, e.g. 192.168.1.0/24.")
        networks = settings_store.parse_networks(network)   # raises ValueError with a clear message
        if not networks:
            raise ValueError("Enter at least one network in CIDR form, e.g. 192.168.1.0/24.")
        self.settings = settings_store.save({"network": ", ".join(networks), "auto_start": True})
        self._detect_self()
        with self.lock:
            self.last_error = ""
            self.state = "running"
            if self._loop_thread is None or not self._loop_thread.is_alive():
                self._stop.clear()
                self._loop_thread = threading.Thread(target=self._loop, daemon=True, name="sweep")
                self._loop_thread.start()
        self._wake.set()
        self._log_scanner_event(f"Started watching {', '.join(networks)}")
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
        interfaces = local_interfaces()
        iface, ip = "", ""
        try:
            from scapy.all import conf, get_if_addr
            iface = str(conf.route.route("0.0.0.0")[0])
            ip = get_if_addr(iface)
        except Exception as exc:  # pragma: no cover
            log.debug("could not detect default interface: %s", exc)
        warnings = {}
        for net in self.networks:
            if interface_for(net, interfaces) is None:
                warnings[net] = NO_INTERFACE
        with self.lock:
            self.interfaces = interfaces
            self.iface, self.local_ip = iface, ip
            self.local_macs = {i["mac"] for i in interfaces if i["mac"]}
            self.network_warnings = warnings

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
        networks = self.networks
        if not networks:
            raise ValueError("No network configured")
        started = time.time()
        with self.lock:
            self.sweeping = True
        self.emit("scanner", self.status())

        found = []
        for net in networks:
            local = interface_for(net, self.interfaces)
            found.extend(arp_sweep(net, timeout=cfg["arp_timeout"], iface=local["iface"] if local else None))
            if local and local["mac"]:
                # The scanning machine never answers its own ARP request.
                found.append({"ip": local["ip"], "mac": local["mac"]})

        now = utcnow()
        offline_after = timedelta(seconds=cfg["offline_after"])
        new_events = []
        snapshot = []
        to_enrich, to_scan = [], []   # queued after commit so workers can see the rows
        with session_scope() as s:
            devices = {d.mac: d for d in s.query(Device).all()}
            replies = {}
            for host in found:
                replies.setdefault(host["mac"], set()).add(host["ip"])
            seen = set(replies)
            for mac, ips in replies.items():
                # A MAC answering for several IPs (router secondary address,
                # proxy ARP) keeps the lowest one as its address and the rest
                # as aliases, so it never flips between them.
                ordered = sorted(ips, key=lambda x: ipaddress.ip_address(x))
                ip, aliases = ordered[0], ordered[1:]
                d = devices.get(mac)
                if d is None:
                    d = Device(mac=mac, ip=ip, vendor=vendor.cached_vendor(mac), online=True,
                               first_seen=now, last_seen=now)
                    d.other_ips = aliases[:32]
                    s.add(d)
                    devices[mac] = d
                    s.add(Presence(mac=mac, started_at=now))
                    label = d.vendor or "unknown vendor"
                    new_events.append(self._event(s, "new_device", d,
                                                  f"New device {ip} ({label})", {"vendor": d.vendor}))
                    to_enrich.append(mac)
                    to_scan.append(mac)
                    continue
                if d.other_ips != aliases[:32]:
                    d.other_ips = aliases[:32]
                if ip and d.ip != ip:
                    if d.ip:
                        new_events.append(self._event(s, "ip_change", d,
                                                      f"{display_name(d)} moved from {d.ip} to {ip}",
                                                      {"from": d.ip, "to": ip}))
                        d.previous_ip = d.ip
                    d.ip = ip
                if not d.online:
                    d.online = True
                    s.add(Presence(mac=mac, started_at=now))
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
                    self._close_span(s, mac, d.last_seen or now)
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

    # ---------------------------------------------------------------- presence

    def _close_span(self, s, mac, at):
        span = (s.query(Presence).filter_by(mac=mac, ended_at=None)
                .order_by(Presence.id.desc()).first())
        if span is not None:
            span.ended_at = max(at, span.started_at)

    def _close_dangling_spans(self):
        """After a restart nothing was watching; end open spans at last_seen."""
        with session_scope() as s:
            open_spans = s.query(Presence).filter_by(ended_at=None).all()
            if not open_spans:
                return
            last = {d.mac: d.last_seen for d in s.query(Device).all()}
            for span in open_spans:
                span.ended_at = max(last.get(span.mac) or span.started_at, span.started_at)
            s.query(Device).update({"online": False})
        log.info("Closed %d presence spans left open by the previous run", len(open_spans))

    def presence_spans(self, hours=24, mac=None):
        """{mac: [[start_iso, end_iso|None], ...]} for spans overlapping the window."""
        since = utcnow() - timedelta(hours=hours)
        out = {}
        with session_scope() as s:
            q = s.query(Presence).filter((Presence.ended_at == None) | (Presence.ended_at >= since))  # noqa: E711
            if mac:
                q = q.filter_by(mac=mac)
            for span in q.order_by(Presence.started_at):
                out.setdefault(span.mac, []).append(span.to_pair())
        return out

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
        if ev["kind"] == "ports_changed" and ev["details"].get("baseline") and not ev["details"].get("deviation"):
            return   # change stays within the accepted baseline
        device = None
        if ev["mac"]:
            with session_scope() as s:
                d = s.query(Device).filter_by(mac=ev["mac"]).first()
                device = d.to_dict() if d else None
        send_webhook(cfg["webhook_url"], {"source": "spynet", "event": ev, "device": device})

    # -------------------------------------------------------------- port scans

    def _queue_port_scan(self, mac, mode=None, start=None, end=None):
        with self.lock:
            if mac in self._port_queued or mac in self.scanning:
                return False
            self._port_queued.add(mac)
        self._port_q.put((mac, mode, start, end))
        return True

    def request_port_scan(self, mac, mode="quick", start=1, end=1024):
        if mode not in ("quick", "range", "full"):
            raise ValueError("mode must be quick, range or full")
        queued = self._queue_port_scan(mac, mode, start, end)
        if queued:
            self.emit("device", self._device_dict_by_mac(mac))
        return queued

    def set_baseline(self, mac, ports):
        """ports=None clears the baseline; a list accepts exactly those ports."""
        with session_scope() as s:
            d = s.query(Device).filter_by(mac=mac).first()
            if d is None:
                return None
            d.baseline_ports = ports
            s.flush()
            payload = self._device_dict(d)
        self.emit("device", payload)
        return payload

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
                baseline = d.baseline_ports
                details = {"opened": opened, "closed": closed, "baseline": baseline is not None}
                parts = []
                if opened:
                    parts.append("opened " + ", ".join(map(str, opened)))
                if closed:
                    parts.append("closed " + ", ".join(map(str, closed)))
                message = f"{display_name(d)} {'; '.join(parts)}"
                if baseline is not None:
                    base = set(baseline)
                    unexpected = sorted(merged - base)
                    missing = sorted(base - merged)
                    details.update({"unexpected": unexpected, "missing": missing,
                                    "deviation": bool(set(opened) - base or set(closed) & base)})
                    if not details["deviation"]:
                        message += " (within baseline)"
                ev = self._event(s, "ports_changed", d, message, details)
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

    def _network_of(self, ip):
        if not ip:
            return ""
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return ""
        for net in self.networks:
            if addr in ipaddress.ip_network(net, strict=False):
                return net
        return ""

    def _device_dict(self, d):
        data = d.to_dict()
        data["scanning"] = d.mac in self.scanning
        data["scan_queued"] = d.mac in self._port_queued
        data["is_self"] = d.mac in self.local_macs
        data["network"] = self._network_of(d.ip)
        data["services"] = [{"port": p, "name": service_name(p)} for p in data["ports"]]
        baseline = d.baseline_ports
        if baseline is None:
            data["port_deviation"] = None
        else:
            current, base = set(d.ports), set(baseline)
            data["port_deviation"] = {"unexpected": sorted(current - base), "missing": sorted(base - current)}
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
                "networks": self.networks,
                "network_warnings": dict(self.network_warnings),
                "interfaces": list(self.interfaces),
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

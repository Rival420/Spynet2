"""Spynet API + dashboard server. One process: Flask REST, Socket.IO push and
the static frontend build."""
import csv
import io
import logging
import os
import signal
import sys

from flask import Flask, jsonify, request, send_from_directory, Response
from flask_cors import CORS
from flask_socketio import SocketIO

import config
import settings as settings_store
from db import init_db, session_scope
from discovery import detect_network, local_interfaces
from models import Device, Event
from port_scanner import grab_banner, service_name
from scanner import NetworkScanner
from vendor import normalize_mac

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logging.getLogger("werkzeug").setLevel(logging.WARNING)
log = logging.getLogger("spynet")

app = Flask(__name__, static_folder=None)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading", logger=False, engineio_logger=False)

init_db()
scanner = NetworkScanner(emit=lambda name, payload: socketio.emit(name, payload))

DEVICE_TYPES = ["", "router", "computer", "laptop", "phone", "tablet", "tv", "speaker",
                "camera", "iot", "printer", "console", "server", "nas", "other"]


def error(message, status=400):
    return jsonify({"error": message}), status


def find_device(session, mac):
    return session.query(Device).filter_by(mac=normalize_mac(mac)).first()


# ------------------------------------------------------------------ frontend

@app.route("/")
@app.route("/<path:path>")
def frontend(path="index.html"):
    if path.startswith("api/") or path.startswith("socket.io"):
        return error("Not found", 404)
    full = os.path.join(config.FRONTEND_DIR, path)
    if os.path.isfile(full):
        return send_from_directory(config.FRONTEND_DIR, path)
    index = os.path.join(config.FRONTEND_DIR, "index.html")
    if os.path.isfile(index):
        return send_from_directory(config.FRONTEND_DIR, "index.html")
    return Response(
        "<h1>Spynet API is running</h1><p>The dashboard has not been built yet. "
        "Run <code>cd spynet && npm install && npm run build</code>, then reload.</p>",
        mimetype="text/html", status=503)


# ---------------------------------------------------------------------- state

@app.get("/api/health")
def health():
    return jsonify({"ok": True, "scanner": scanner.status()["state"]})


@app.get("/api/state")
def state():
    with session_scope() as s:
        events = [e.to_dict() for e in s.query(Event).order_by(Event.id.desc()).limit(200)]
    return jsonify({
        "devices": scanner.all_devices(),
        "events": events,
        "presence": scanner.presence_spans(24),
        "scanner": scanner.status(),
        "settings": settings_store.load(),
        "device_types": DEVICE_TYPES,
    })


# -------------------------------------------------------------------- devices

@app.get("/api/devices")
def list_devices():
    return jsonify(scanner.all_devices())


@app.get("/api/devices/export.csv")
def export_devices():
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["name", "hostname", "ip", "mac", "vendor", "type", "known", "online",
                     "first_seen", "last_seen", "open_ports", "notes"])
    for d in sorted(scanner.all_devices(), key=lambda x: [int(p) for p in x["ip"].split(".")] if x["ip"] else [999]):
        writer.writerow([d["name"], d["hostname"], d["ip"], d["mac"], d["vendor"], d["device_type"],
                         d["known"], d["online"], d["first_seen"], d["last_seen"],
                         " ".join(map(str, d["ports"])), d["notes"]])
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=spynet-devices.csv"})


@app.get("/api/devices/<mac>")
def get_device(mac):
    with session_scope() as s:
        d = find_device(s, mac)
        if d is None:
            return error("Device not found", 404)
        data = scanner._device_dict(d)
        data["events"] = [e.to_dict() for e in
                          s.query(Event).filter_by(mac=d.mac).order_by(Event.id.desc()).limit(100)]
    return jsonify(data)


@app.patch("/api/devices/<mac>")
def update_device(mac):
    body = request.get_json(silent=True) or {}
    with session_scope() as s:
        d = find_device(s, mac)
        if d is None:
            return error("Device not found", 404)
        if "name" in body:
            d.name = str(body["name"] or "").strip()[:120]
        if "notes" in body:
            d.notes = str(body["notes"] or "").strip()[:2000]
        if "known" in body:
            d.known = bool(body["known"])
        if "device_type" in body:
            dt = str(body["device_type"] or "")
            if dt not in DEVICE_TYPES:
                return error("Unknown device type")
            d.device_type = dt
        s.flush()
        data = scanner._device_dict(d)
    socketio.emit("device", data)
    return jsonify(data)


@app.delete("/api/devices/<mac>")
def delete_device(mac):
    with session_scope() as s:
        d = find_device(s, mac)
        if d is None:
            return error("Device not found", 404)
        s.query(Event).filter_by(mac=d.mac).delete()
        s.delete(d)
        mac = d.mac
    socketio.emit("device", {"mac": mac, "deleted": True})
    return jsonify({"deleted": mac})


@app.post("/api/devices/acknowledge_all")
def acknowledge_all():
    with session_scope() as s:
        count = s.query(Device).filter_by(known=False).update({"known": True})
    socketio.emit("devices", scanner.all_devices())
    return jsonify({"acknowledged": count})


@app.post("/api/devices/<mac>/portscan")
def device_portscan(mac):
    body = request.get_json(silent=True) or {}
    mode = body.get("mode", "quick")
    try:
        start = int(body.get("start", 1))
        end = int(body.get("end", 1024))
    except (TypeError, ValueError):
        return error("start and end must be numbers")
    with session_scope() as s:
        d = find_device(s, mac)
        if d is None:
            return error("Device not found", 404)
        if not d.ip:
            return error("This device has no IP address yet")
        mac = d.mac
    try:
        queued = scanner.request_port_scan(mac, mode, start, end)
    except ValueError as exc:
        return error(str(exc))
    return jsonify({"queued": queued, "mac": mac, "mode": mode})


@app.post("/api/devices/<mac>/banner")
def device_banner(mac):
    body = request.get_json(silent=True) or {}
    try:
        port = int(body.get("port"))
    except (TypeError, ValueError):
        return error("port is required")
    if not 1 <= port <= 65535:
        return error("port must be between 1 and 65535")
    with session_scope() as s:
        d = find_device(s, mac)
        if d is None:
            return error("Device not found", 404)
        ip = d.ip
    banner = grab_banner(ip, port, timeout=float(body.get("timeout", 3)))
    return jsonify({"mac": mac, "ip": ip, "port": port, "service": service_name(port), "banner": banner})


@app.post("/api/devices/<mac>/baseline")
def device_baseline(mac):
    """{"mode": "current"} accepts the open ports as expected; {"mode": "clear"} removes the baseline;
    {"ports": [..]} sets an explicit list."""
    body = request.get_json(silent=True) or {}
    mode = body.get("mode", "current")
    with session_scope() as s:
        d = find_device(s, mac)
        if d is None:
            return error("Device not found", 404)
        mac = d.mac
        current = d.ports
    if "ports" in body:
        try:
            ports = sorted({int(p) for p in body["ports"]})
        except (TypeError, ValueError):
            return error("ports must be a list of numbers")
    elif mode == "clear":
        ports = None
    elif mode == "current":
        ports = current
    else:
        return error("mode must be current or clear")
    return jsonify(scanner.set_baseline(mac, ports))


@app.get("/api/presence")
def presence():
    hours = max(1, min(int(request.args.get("hours", 24)), 24 * 90))
    mac = request.args.get("mac")
    return jsonify(scanner.presence_spans(hours, normalize_mac(mac) if mac else None))


@app.post("/api/devices/<mac>/refresh")
def device_refresh(mac):
    if not scanner.refresh_device(normalize_mac(mac)):
        return error("Device not found", 404)
    return jsonify({"queued": True})


# --------------------------------------------------------------------- events

@app.get("/api/events")
def list_events():
    limit = min(int(request.args.get("limit", 200)), 2000)
    mac = request.args.get("mac")
    kind = request.args.get("kind")
    with session_scope() as s:
        q = s.query(Event)
        if mac:
            q = q.filter_by(mac=normalize_mac(mac))
        if kind:
            q = q.filter_by(kind=kind)
        rows = q.order_by(Event.id.desc()).limit(limit).all()
        return jsonify([e.to_dict() for e in rows])


@app.delete("/api/events")
def clear_events():
    with session_scope() as s:
        count = s.query(Event).delete()
    socketio.emit("events_cleared", {})
    return jsonify({"deleted": count})


# -------------------------------------------------------------------- scanner

@app.get("/api/scanner")
def scanner_status():
    return jsonify(scanner.status())


@app.post("/api/scanner/start")
def scanner_start():
    body = request.get_json(silent=True) or {}
    try:
        if body:
            settings_store.save({k: v for k, v in body.items() if k != "network"})
            scanner.apply_settings(settings_store.load())
        scanner.start(body.get("network"))
    except ValueError as exc:
        return error(str(exc))
    return jsonify(scanner.status())


@app.post("/api/scanner/pause")
def scanner_pause():
    scanner.pause()
    return jsonify(scanner.status())


@app.post("/api/scanner/resume")
def scanner_resume():
    scanner.resume()
    return jsonify(scanner.status())


@app.post("/api/scanner/stop")
def scanner_stop():
    scanner.stop()
    return jsonify(scanner.status())


@app.post("/api/scanner/sweep")
def scanner_sweep():
    if not scanner.settings["network"]:
        return error("Set a network first")
    scanner.sweep_now()
    return jsonify({"queued": True})


@app.get("/api/network/detect")
def network_detect():
    network, iface, ip = detect_network()
    interfaces = local_interfaces()
    if not network and not interfaces:
        return error("Could not detect the local network", 404)
    return jsonify({"network": network, "iface": iface, "ip": ip, "interfaces": interfaces})


# ------------------------------------------------------------------- settings

@app.get("/api/settings")
def get_settings():
    return jsonify(settings_store.load())


@app.put("/api/settings")
@app.patch("/api/settings")
def put_settings():
    body = request.get_json(silent=True) or {}
    try:
        new = settings_store.save(body)
    except ValueError as exc:
        return error(str(exc))
    scanner.apply_settings(new)
    socketio.emit("settings", new)
    socketio.emit("scanner", scanner.status())
    return jsonify(new)


@app.post("/api/settings/test_webhook")
def test_webhook():
    from notify import send_webhook
    url = settings_store.load()["webhook_url"]
    if not url:
        return error("No webhook URL configured")
    send_webhook(url, {"source": "spynet", "event": {"kind": "test", "message": "Spynet webhook test"}, "device": None})
    return jsonify({"sent": True})


# ------------------------------------------------------------------- sockets

@socketio.on("connect")
def on_connect():
    socketio.emit("scanner", scanner.status(), to=request.sid)


def _shutdown(*_args):
    log.info("Shutting down")
    scanner.shutdown()
    sys.exit(0)


def main():
    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)
    cfg = settings_store.load()
    if cfg["auto_start"] and cfg["network"]:
        try:
            scanner.start(cfg["network"])
        except ValueError as exc:
            log.error("auto-start failed: %s", exc)
    log.info("Spynet listening on http://%s:%d", config.HOST, config.PORT)
    socketio.run(app, host=config.HOST, port=config.PORT, allow_unsafe_werkzeug=True)


if __name__ == "__main__":
    main()

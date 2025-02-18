# server.py
import threading
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO
from scanner import NetworkScanner
from port_scanner import scan_ports_for_host, grab_banner
from arp_scanner import lookup_vendor
import time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Host
from datetime import datetime
from db import db_session

app = Flask(__name__, static_folder='./build', template_folder='./build')
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize scanner without any parameters (inactive)
scanner = NetworkScanner()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/scan')
def api_scan():
    data = scanner.get_data()
    return jsonify(data)

@app.route('/api/scanner/start', methods=['POST'])
def start_scanner():
    data = request.get_json()
    network = data.get('network')
    port_start = int(data.get('port_start', 1))
    port_end = int(data.get('port_end', 1024))
    timeout = int(data.get('timeout', 2))
    interval = int(data.get('interval', 60))
    if not network:
        return jsonify({"error": "Network parameter is required"}), 400
    scanner.start(network, (port_start, port_end), timeout, interval)
    return jsonify({"status": "scanner started", "network": network})

@app.route('/api/scanner/pause', methods=['POST'])
def pause_scanner():
    scanner.pause()
    return jsonify({"status": "scanner paused"})

@app.route('/api/scanner/resume', methods=['POST'])
def resume_scanner():
    scanner.resume()
    return jsonify({"status": "scanner resumed"})

@app.route('/api/scanner/stop', methods=['POST'])
def stop_scanner():
    scanner.stop()
    return jsonify({"status": "scanner stopped"})

# Existing endpoints for on-demand port scan and banner grab remain unchanged.
@app.route('/api/command/portscan', methods=['POST'])
def api_port_scan():
    data = request.get_json()
    host = data.get('host')
    scan_type = data.get('scan_type', 'popular')
    timeout_val = data.get('timeout', 1)

    if scan_type == 'range':
        start_port = data.get('start_port')
        end_port = data.get('end_port')
        if start_port is None or end_port is None:
            return jsonify({"error": "start_port and end_port required for range scan"}), 400
        ports = list(range(int(start_port), int(end_port) + 1))
    elif scan_type == 'all':
        ports = list(range(1, 65536))
    else:
        # Default/popular ports
        ports = [21, 22, 23, 25, 53, 80, 110, 135, 139, 143, 443, 445, 993, 995, 3389, 8000, 8080, 8443, 9000, 9001, 9443]

    def run_scan():
        # Mark scanning in progress so that UI shows "Scanning in progress"
        with scanner.lock:
            if host in scanner.hosts:
                scanner.hosts[host]['port_scan_in_progress'] = True
            else:
                # In case the host isn't already in our in-memory store
                scanner.hosts[host] = {
                    'mac': '',
                    'vendor': '',
                    'ports': [],
                    'status': 'unknown',
                    'last_seen': time.time(),
                    'port_scan_in_progress': True
                }
        # Emit an update so the frontend sees the change
        socketio.emit('scan_update', scanner.get_data())

        # Run the port scan
        open_ports = scan_ports_for_host(host, ports, timeout=timeout_val)

        # Update in-memory data with results and mark scan as complete
        with scanner.lock:
            if host in scanner.hosts:
                scanner.hosts[host]['ports'] = open_ports
                scanner.hosts[host]['port_scan_in_progress'] = False
        # Optionally, update the database here if desired

        # Emit final results so the UI can update immediately
        socketio.emit('port_scan_result', {'host': host, 'open_ports': open_ports})

    threading.Thread(target=run_scan, daemon=True).start()
    return jsonify({"status": "Port scan started", "host": host})

@app.route('/api/command/bannergrab', methods=['POST'])
def api_banner_grab():
    data = request.get_json()
    host = data.get('host')
    port = data.get('port')
    timeout_val = data.get('timeout', 5)
    if not host or not port:
        return jsonify({"error": "host and port are required"}), 400
    banner = grab_banner(host, int(port), timeout=timeout_val)
    return jsonify({"host": host, "port": port, "banner": banner})

@app.route('/api/host/update', methods=['POST'])
def update_host():
    data = request.get_json()
    ip = data.get('ip')
    hostname = data.get('hostname')
    is_dhcp = data.get('is_dhcp')
    if not ip:
        return jsonify({"error": "IP is required"}), 400

    # Query the host from the database.
    from models import Host
    db_host = db_session.query(Host).filter_by(ip=ip).first()
    if not db_host:
        return jsonify({"error": "Host not found"}), 404

    if hostname is not None:
        db_host.hostname = hostname
    if is_dhcp is not None:
        db_host.is_dhcp = bool(is_dhcp)

    db_session.commit()

    # Also update the in-memory data, if available.
    if ip in scanner.hosts:
        if hostname is not None:
            scanner.hosts[ip]['hostname'] = hostname
        if is_dhcp is not None:
            scanner.hosts[ip]['is_dhcp'] = bool(is_dhcp)

    return jsonify({"status": "Host updated", "ip": ip, "hostname": db_host.hostname, "is_dhcp": db_host.is_dhcp})

@app.route('/api/command/maclookup', methods=['POST'])
@cross_origin()
def api_maclookup():
    data = request.get_json()
    host_ip = data.get('host')
    if not host_ip:
        return jsonify({"error": "host is required"}), 400

    # Try to get the host data from memory; if not, fall back to the database.
    host_data = scanner.hosts.get(host_ip)
    if host_data:
        mac = host_data.get('mac')
    else:
        db_host = db_session.query(Host).filter_by(ip=host_ip).first()
        if db_host:
            mac = db_host.mac
        else:
            return jsonify({"error": "Host not found"}), 404

    # Import and call the lookup_vendor function from arp_scanner.
    from arp_scanner import lookup_vendor
    vendor = lookup_vendor(mac)

    # Save vendor to in-memory data if available.
    if host_data:
        host_data['vendor'] = vendor

    # Update the database record with the found vendor.
    db_host = db_session.query(Host).filter_by(ip=host_ip).first()
    if db_host:
        db_host.vendor = vendor
        db_session.commit()

    return jsonify({"host": host_ip, "vendor": vendor})



def background_thread():
    while True:
        socketio.sleep(1)
        data = scanner.get_data()
        socketio.emit('scan_update', data)

if __name__ == '__main__':
    socketio.start_background_task(target=background_thread)
    socketio.run(app, host='0.0.0.0', port=5000)

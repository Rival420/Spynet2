# server.py
import threading
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO
from scanner import NetworkScanner
from port_scanner import scan_ports_for_host, grab_banner
import time

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
        ports = [21, 22, 23, 25, 53, 80, 110, 135, 139, 143, 443, 445, 993, 995, 3389, 8000, 8080, 8443, 9000, 9001, 9443]

    result = {}
    def run_scan():
        open_ports = scan_ports_for_host(host, ports, timeout=timeout_val)
        result['open_ports'] = open_ports
        socketio.emit('port_scan_result', {'host': host, 'open_ports': open_ports})
    threading.Thread(target=run_scan, daemon=True).start()
    return jsonify({"status": "Port scan started", "host": host})

@app.route('/api/command/bannergrab', methods=['POST'])
def api_banner_grab():
    data = request.get_json()
    host = data.get('host')
    port = data.get('port')
    timeout_val = data.get('timeout', 2)
    if not host or not port:
        return jsonify({"error": "host and port are required"}), 400
    banner = grab_banner(host, int(port), timeout=timeout_val)
    return jsonify({"host": host, "port": port, "banner": banner})

def background_thread():
    while True:
        socketio.sleep(1)
        data = scanner.get_data()
        socketio.emit('scan_update', data)

if __name__ == '__main__':
    socketio.start_background_task(target=background_thread)
    socketio.run(app, host='0.0.0.0', port=5000)

# server.py
import threading
import argparse
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO
from flask_cors import CORS
from scanner import NetworkScanner
from port_scanner import scan_ports_for_host, grab_banner
import time

# Configure Flask to serve the React build (assume it's in the 'build' folder)
app = Flask(__name__, static_folder='./build', template_folder='./build')
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Global scanner instance (will be initialized in main)
scanner = None

@app.route('/')
def index():
    # Serves the React app index.html
    return render_template('index.html')

@app.route('/api/scan')
def api_scan():
    """Optional REST API endpoint to fetch current scan data."""
    data = scanner.get_data()
    return jsonify(data)

def background_thread():
    """Background task to push scan updates to connected clients via SocketIO."""
    while True:
        socketio.sleep(1)  # Push updates every 5 seconds
        data = scanner.get_data()
        socketio.emit('scan_update', data)

@app.route('/api/command/portscan', methods=['POST'])
def api_port_scan():
    """
    Expects JSON payload with:
      - host: target IP (string)
      - scan_type: "popular", "range", or "all" (default is popular)
      - start_port and end_port (if scan_type is range)
      - timeout: optional (default: 1)
    """
    data = request.get_json()
    host = data.get('host')
    scan_type = data.get('scan_type', 'popular')
    timeout_val = data.get('timeout', 1)

    # Determine which ports to scan based on scan_type
    if scan_type == 'range':
        start_port = data.get('start_port')
        end_port = data.get('end_port')
        if start_port is None or end_port is None:
            return jsonify({"error": "start_port and end_port required for range scan"}), 400
        ports = list(range(int(start_port), int(end_port) + 1))
    elif scan_type == 'all':
        ports = list(range(1, 65536))  # Warning: This is heavy!
    else:  # default/popular
        ports = [21, 22, 23, 25, 53, 80, 110, 139, 143, 443, 445, 993, 995, 3389]

    result = {}
    def run_scan():
        open_ports = scan_ports_for_host(host, ports, timeout=timeout_val)
        result['open_ports'] = open_ports
        # Emit the scan result to all connected clients
        socketio.emit('port_scan_result', {'host': host, 'open_ports': open_ports})

    threading.Thread(target=run_scan, daemon=True).start()
    return jsonify({"status": "Port scan started", "host": host})

@app.route('/api/command/bannergrab', methods=['POST'])
def api_banner_grab():
    """
    Expects JSON payload with:
      - host: target IP (string)
      - port: target port (int)
      - timeout: optional (default: 2)
    """
    data = request.get_json()
    host = data.get('host')
    port = data.get('port')
    timeout_val = data.get('timeout', 2)
    if not host or not port:
        return jsonify({"error": "host and port are required"}), 400
    banner = grab_banner(host, int(port), timeout=timeout_val)
    return jsonify({"host": host, "port": port, "banner": banner})

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Modular Network Scanner')
    parser.add_argument('--network', type=str, required=True,
                        help='Network in CIDR notation, e.g. 192.168.1.0/24')
    parser.add_argument('--port-start', type=int, default=1, help='Start port (default: 1)')
    parser.add_argument('--port-end', type=int, default=1024, help='End port (default: 1024)')
    parser.add_argument('--timeout', type=int, default=2, help='Timeout for scanning in seconds')
    parser.add_argument('--interval', type=int, default=60, help='Interval between scans in seconds')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Host for the web server')
    parser.add_argument('--port', type=int, default=5000, help='Port for the web server')
    args = parser.parse_args()

    # Initialize and start the network scanner in its own thread
    scanner = NetworkScanner(args.network, (args.port_start, args.port_end),
                             args.timeout, args.interval)
    scanner_thread = threading.Thread(target=scanner.scan_loop, daemon=True)
    scanner_thread.start()

    # Start the background thread that pushes scan updates to clients
    socketio.start_background_task(target=background_thread)
    # Run the Flask/SocketIO server
    socketio.run(app, host=args.host, port=args.port)

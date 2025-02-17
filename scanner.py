# scanner.py
import time
import threading
from arp_scanner import arp_scan
from port_scanner import scan_ports_for_host
from models import Host
from sqlalchemy.orm.exc import NoResultFound
from datetime import datetime
from db import db_session  # Import the db_session from server.py
from helper import filter_numeric_ports

class NetworkScanner:
    def __init__(self):
        self.network = None
        self.port_range = (1, 1024)
        self.timeout = 2
        self.scan_interval = 60
        self.hosts = {}
        self.lock = threading.Lock()
        self.scanning_active = False
        self.scanning_paused = False
        self.load_from_db() #load persistent data into memory

    def start(self, network, port_range, timeout, scan_interval):
        print(f"[+] Start continious scanning for network: {network}")
        print(f"[+] the scan will repeat itself every {scan_interval} seconds.")
        self.network = network
        self.port_range = port_range
        self.timeout = timeout
        self.scan_interval = scan_interval
        self.scanning_active = True
        self.scanning_paused = False
        threading.Thread(target=self.scan_loop, daemon=True).start()

    def scan_loop(self):
        while self.scanning_active:
            if not self.scanning_paused:
                self.scan_once()
            time.sleep(self.scan_interval)
            print(f"[+] Sleep timer ended. Starting loop again.")

    def scan_once(self):
        live_hosts = arp_scan(self.network, timeout=self.timeout)
        print("ARP scan found", len(live_hosts), "hosts:", live_hosts)
        live_ips = [host['ip'] for host in live_hosts]

        with self.lock:
            for host in live_hosts:
                ip = host['ip']
                # Update database: try to find an existing record.
                db_host = db_session.query(Host).filter_by(ip=ip).first()
                if db_host:
                    db_host.mac = host['mac']
                    db_host.vendor = host['vendor']
                    db_host.last_seen = datetime.utcnow()
                else:
                    db_host = Host(ip=ip,
                                   mac=host['mac'],
                                   vendor=host['vendor'],
                                   last_seen=datetime.utcnow())
                    db_session.add(db_host)
                db_session.commit()

                # Update in-memory dictionary (which is used for live socket updates)
                if ip not in self.hosts:
                    self.hosts[ip] = {
                        'mac': host['mac'],
                        'vendor': host['vendor'],
                        'ports': [],
                        'status': 'online',
                        'last_seen': time.time(),
                        'port_scan_in_progress': False
                    }
                else:
                    self.hosts[ip]['mac'] = host['mac']
                    self.hosts[ip]['vendor'] = host['vendor']
                    self.hosts[ip]['status'] = 'online'
                    self.hosts[ip]['last_seen'] = time.time()

            # Mark hosts not seen in this ARP scan as offline
            for ip in list(self.hosts.keys()):
                if ip not in live_ips and time.time() - self.hosts[ip]['last_seen'] > self.scan_interval * 1.5:
                    self.hosts[ip]['status'] = 'offline'

        # Optionally, perform port scanning on each live host.
        for ip in live_ips:
            ports = list(range(self.port_range[0], self.port_range[1] + 1))
            with self.lock:
                if ip in self.hosts:
                    self.hosts[ip]['port_scan_in_progress'] = True
            open_ports = scan_ports_for_host(ip, ports, timeout=self.timeout)
            with self.lock:
                if ip in self.hosts:
                    # Convert existing ports (if any) and new scan results into sets of numeric values.
                    existing_ports = filter_numeric_ports(self.hosts[ip].get('ports', []))
                    new_ports = filter_numeric_ports(open_ports)
                    if new_ports:
                        # Merge the new ports with the existing ports.
                        merged_ports = sorted(existing_ports.union(new_ports))
                        self.hosts[ip]['ports'] = merged_ports
                        # Update the corresponding database record.
                        db_host = db_session.query(Host).filter_by(ip=ip).first()
                        if db_host:
                            # Save as a comma-separated string.
                            db_host.port_scan_result = ','.join(map(str, merged_ports))
                            db_session.commit()
                    # If new_ports is empty but there are already ports stored, do nothing.
                    self.hosts[ip]['port_scan_in_progress'] = False


    def pause(self):
        print("[+] Pausing the scan")
        self.scanning_paused = True

    def resume(self):
        print("[+] Resuming the scan")
        self.scanning_paused = False

    def stop(self):
        print("[+] Stopping the scan")
        self.scanning_active = False

    def get_data(self):
        with self.lock:
            return self.hosts.copy()
    
    def load_from_db(self):
        from db import db_session  # ensure we have access to the session
        from models import Host
        db_hosts = db_session.query(Host).all()
        for db_host in db_hosts:
            # Assume that port_scan_result is stored as a comma-separated string.
            ports = db_host.port_scan_result.split(',') if db_host.port_scan_result else []
            # Convert last_seen datetime to a timestamp (float) for our in-memory dict.
            self.hosts[db_host.ip] = {
                'mac': db_host.mac,
                'vendor': db_host.vendor,
                'ports': ports,
                'status': 'offline',  # Mark offline until confirmed by a new ARP scan.
                'last_seen': db_host.last_seen.timestamp(),
                'port_scan_in_progress': False
        }


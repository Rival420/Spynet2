# scanner.py
import time
import threading
from arp_scanner import arp_scan
from port_scanner import scan_ports_for_host

class NetworkScanner:
    def __init__(self, network, port_range, timeout, scan_interval):
        """
        network: Network in CIDR notation (e.g. '192.168.1.0/24')
        port_range: Tuple (start_port, end_port)
        timeout: Timeout in seconds for each scan request.
        scan_interval: Time in seconds between full scans.
        """
        self.network = network
        self.port_range = port_range
        self.timeout = timeout
        self.scan_interval = scan_interval
        # Dictionary to hold scan data. Keys are host IPs.
        self.hosts = {}
        self.lock = threading.Lock()
        self.scanning = True

    def scan_loop(self):
        """Continuously perform a scan at the specified interval."""
        while self.scanning:
            self.scan_once()
            time.sleep(self.scan_interval)

    def scan_once(self):
        """Perform one full scan: ARP then port scan for live hosts."""
        live_hosts = arp_scan(self.network, timeout=self.timeout)
        print("ARP scan found", len(live_hosts), "hosts:", live_hosts)  # Debug line
        live_ips = [host['ip'] for host in live_hosts]

        # Update host info based on ARP scan
        with self.lock:
            for host in live_hosts:
                ip = host['ip']
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
            # Mark hosts not seen in this scan as offline (if sufficient time has passed)
            for ip in list(self.hosts.keys()):
                if ip not in live_ips and time.time() - self.hosts[ip]['last_seen'] > self.scan_interval * 1.5:
                    self.hosts[ip]['status'] = 'offline'

        # PORT SCAN PHASE
        # For each live host, perform a port scan
        for host in live_ips:
            ports = list(range(self.port_range[0], self.port_range[1] + 1))
            # mark host as currently being scanned
            with self.lock:
                if host in self.hosts:
                    self.hosts[host]['port_scan_in_progress'] = True
                    print("Starting scan on host: ", host)
            #Perform the port scan (This may take some time)
            open_ports = scan_ports_for_host(host, ports, timeout=self.timeout)

            #Update the host port scan results and mark scanning as done
            with self.lock:
                if host in self.hosts:
                    self.hosts[host]['ports'] = open_ports
                    self.hosts[host]['port_scan_in_progress'] = False

    def get_data(self):
        """Returns a snapshot copy of the current scan data."""
        with self.lock:
            return self.hosts.copy()

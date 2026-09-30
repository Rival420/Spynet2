"""TCP port scanning with a bounded thread pool, plus banner grabbing.

A TCP connect scan is used rather than raw SYN packets: it is far faster on a
Raspberry Pi, does not confuse scapy's packet matching when run concurrently,
and gives identical results for the "which services does this device expose"
question a home monitor asks."""
import logging
import socket
import ssl
from concurrent.futures import ThreadPoolExecutor

import config

log = logging.getLogger("spynet.ports")

QUICK_PORTS = [
    21, 22, 23, 25, 53, 80, 81, 88, 110, 111, 135, 139, 143, 443, 445, 465, 515,
    548, 554, 587, 631, 636, 853, 873, 993, 995, 1080, 1433, 1883, 2049, 2323,
    3000, 3306, 3389, 5000, 5001, 5060, 5432, 5900, 6379, 7000, 7443, 8000, 8008,
    8080, 8081, 8088, 8123, 8443, 8883, 8888, 9000, 9090, 9100, 9443, 10000,
    32400, 49152, 51413, 62078,
]

SERVICE_NAMES = {
    81: "http-alt", 88: "kerberos", 515: "printer", 548: "afp", 554: "rtsp",
    631: "ipp", 853: "dns-over-tls", 873: "rsync", 1080: "socks", 1883: "mqtt",
    2323: "telnet-alt", 3000: "http-dev", 5000: "upnp/http", 5001: "synology",
    5060: "sip", 5900: "vnc", 6379: "redis", 7000: "airplay", 7443: "https-alt",
    8000: "http-alt", 8008: "cast", 8080: "http-proxy", 8081: "http-alt",
    8088: "http-alt", 8123: "home-assistant", 8443: "https-alt", 8883: "mqtts",
    8888: "http-alt", 9000: "http-alt", 9090: "cockpit", 9100: "jetdirect",
    9443: "https-alt", 10000: "webmin", 32400: "plex", 49152: "upnp",
    51413: "bittorrent", 62078: "iphone-sync",
}

SSL_PORTS = {443, 465, 636, 853, 990, 993, 995, 7443, 8443, 9443, 8883}


def service_name(port):
    if port in SERVICE_NAMES:
        return SERVICE_NAMES[port]
    try:
        return socket.getservbyport(port, "tcp")
    except OSError:
        return ""


def ports_for_mode(mode, start=1, end=1024):
    if mode == "quick":
        return list(QUICK_PORTS)
    if mode == "full":
        return list(range(1, 65536))
    if mode == "range":
        start, end = max(1, int(start)), min(65535, int(end))
        if end < start:
            start, end = end, start
        return list(range(start, end + 1))
    return []


def _connect(host, port, timeout):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        return sock.connect_ex((host, port)) == 0
    except OSError:
        return False
    finally:
        sock.close()


def scan_ports(host, ports, timeout=1.0, workers=None, should_abort=None):
    """Return the sorted list of open TCP ports on `host`."""
    workers = workers or config.PORT_SCAN_WORKERS
    open_ports = []
    log.info("Port scan %s: %d ports", host, len(ports))
    with ThreadPoolExecutor(max_workers=min(workers, max(1, len(ports)))) as pool:
        futures = {pool.submit(_connect, host, p, timeout): p for p in ports}
        for fut in futures:
            if should_abort and should_abort():
                pool.shutdown(wait=False, cancel_futures=True)
                break
            if fut.result():
                open_ports.append(futures[fut])
    return sorted(open_ports)


PROBES = {
    "http": "HEAD / HTTP/1.0\r\nHost: {host}\r\nUser-Agent: spynet\r\n\r\n",
    21: "\r\n", 25: "EHLO spynet.local\r\n", 465: "EHLO spynet.local\r\n",
    587: "EHLO spynet.local\r\n", 110: "\r\n", 995: "\r\n", 143: "\r\n", 993: "\r\n",
}
HTTP_PORTS = {80, 81, 443, 3000, 5000, 5001, 7443, 8000, 8008, 8080, 8081, 8088,
              8123, 8443, 8888, 9000, 9090, 9443, 10000, 32400}


def grab_banner(host, port, timeout=3):
    """Connect and read whatever the service says first. Returns a string."""
    sock = None
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        if port in SSL_PORTS:
            ctx = ssl._create_unverified_context()
            sock = ctx.wrap_socket(sock, server_hostname=host)
        sock.settimeout(timeout)
        banner = b""
        try:
            banner = sock.recv(2048)
        except (socket.timeout, OSError):
            pass
        if not banner:
            probe = PROBES.get(port) or (PROBES["http"] if port in HTTP_PORTS else "\r\n")
            try:
                sock.sendall(probe.format(host=host).encode())
                banner = sock.recv(4096)
            except (socket.timeout, OSError):
                pass
        text = banner.decode("utf-8", errors="replace").strip()
        return text[:4000] if text else "The service accepted the connection but sent nothing."
    except ssl.SSLError as exc:
        return f"TLS handshake failed: {exc}"
    except (socket.timeout, TimeoutError):
        return "Timed out waiting for a reply."
    except OSError as exc:
        return f"Connection failed: {exc.strerror or exc}"
    finally:
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass

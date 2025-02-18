# port_scanner.py
from scapy.all import IP, TCP, sr1
import threading
import socket
import ssl

def syn_scan(target, port, timeout=1):
    """
    Performs a SYN scan on the target:port.
    Sends a SYN packet and checks for a SYN-ACK reply.
    Returns True if the port appears open.
    """
    packet = IP(dst=target)/TCP(dport=port, flags="S")
    response = sr1(packet, timeout=timeout, verbose=0)
    if response is None:
        return False
    if response.haslayer(TCP):
        tcp_layer = response.getlayer(TCP)
        # 0x12 == SYN-ACK; 0x14 == RST-ACK (closed)
        if tcp_layer.flags == 0x12:
            # Send RST to gracefully close the half-open connection.
            rst_pkt = IP(dst=target)/TCP(dport=port, flags="R")
            sr1(rst_pkt, timeout=timeout, verbose=0)
            return True
    return False

def scan_ports_for_host(host, ports, timeout=1):
    """
    Scans a list of ports on the given host using threads.
    Returns a list of open ports.
    """
    open_ports = []
    threads = []
    lock = threading.Lock()

    print(f"[+] Starting port scan on host: {host}")
    def scan_port(port):
        if syn_scan(host, port, timeout):
            with lock:
                open_ports.append(port)

    for port in ports:
        t = threading.Thread(target=scan_port, args=(port,))
        t.start()
        threads.append(t)
    for t in threads:
        t.join()
    return open_ports

def grab_banner(host, port, timeout=2):
    """
    Attempts to connect to host:port and read a banner.
    If no banner is initially received, it sends a protocol-specific probe.
    For SSL ports, certificate verification is disabled to allow self-signed certificates.
    """
    print(f"[+] Grabbing port {port} for host {host}")

    # Define known SSL ports
    ssl_ports = {443, 465, 993, 995, 990, 636, 8443}

    try:
        # Use an unverified SSL context for ports requiring SSL (e.g., 443)
        if port in ssl_ports:
            context = ssl._create_unverified_context()
            sock = socket.create_connection((host, port), timeout=timeout)
            s = context.wrap_socket(sock, server_hostname=host)
        else:
            s = socket.create_connection((host, port), timeout=timeout)
        
        s.settimeout(timeout)
        try:
            banner = s.recv(1024)
        except socket.timeout:
            banner = b""
        
        # If no banner is returned, send a protocol-specific probe
        if not banner:
            probes = {
                80: f"GET / HTTP/1.1\r\nHost: {host}\r\n\r\n",
                443: f"GET / HTTP/1.1\r\nHost: {host}\r\n\r\n",
                8443: f"GET / HTTP/1.1\r\nHost: {host}\r\n\r\n",
                21: "\r\n",               # FTP
                25: "EHLO example.com\r\n",# SMTP
                465: "EHLO example.com\r\n",# SMTP over SSL
                110: "\r\n",              # POP3
                995: "\r\n",              # POP3S
                143: "\r\n",              # IMAP
                993: "\r\n",              # IMAPS
                636: "\r\n",              # LDAPS
                990: "\r\n",              # Implicit FTPS
            }
            if port in probes:
                try:
                    s.sendall(probes[port].encode('utf-8'))
                    banner = s.recv(1024)
                except Exception as e:
                    print(f"[-] Error sending probe: {e}")
        s.close()
        result = banner.decode('utf-8', errors='ignore').strip() if banner else "No banner received."
        return result
    except Exception as e:
        return str(e)
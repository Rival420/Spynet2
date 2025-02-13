# port_scanner.py
from scapy.all import IP, TCP, sr1
import threading
import socket

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
    """
    try:
        s = socket.socket()
        s.settimeout(timeout)
        s.connect((host, port))
        banner = s.recv(1024)
        s.close()
        return banner.decode('utf-8', errors='ignore')
    except Exception as e:
        return str(e)

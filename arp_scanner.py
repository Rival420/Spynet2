# arp_scanner.py
from scapy.all import ARP, Ether, srp
import requests

# Simple in-memory cache for MAC vendor lookups
vendor_cache = {}

def lookup_vendor(mac):
    if mac in vendor_cache:
        return vendor_cache[mac]
    try:
        # Using the macvendors.com API for vendor lookup
        response = requests.get(f"https://api.macvendors.com/{mac}", timeout=5)
        vendor = response.text.strip() if response.status_code == 200 else "Unknown"
    except Exception:
        vendor = "Unknown"
    vendor_cache[mac] = vendor
    return vendor

def arp_scan(network, timeout=2):
    """
    Scans the given network (CIDR notation, e.g. '192.168.1.0/24') using ARP.
    Returns a list of dictionaries with 'ip' and 'mac' for live hosts.
    """
    # Create an Ethernet frame (broadcast) and ARP request
    ans, _ = srp(Ether(dst="ff:ff:ff:ff:ff:ff")/ARP(pdst=network),
                 timeout=timeout, verbose=0)
    live_hosts = []
    for snd, rcv in ans:
        host = {'ip': rcv.psrc, 'mac': rcv.hwsrc}
        host['vendor'] = lookup_vendor(rcv.hwsrc)
        live_hosts.append(host)
    return live_hosts

"""Host discovery: ARP sweeps, network auto-detection and hostname resolution."""
import ipaddress
import logging
import socket
import struct
import random

log = logging.getLogger("spynet.discovery")


class RawSocketPermissionError(RuntimeError):
    pass


def detect_network():
    """Best guess of the local IPv4 network in CIDR form: the interface that
    carries the default route, with its configured netmask."""
    try:
        from scapy.all import conf, get_if_addr
        iface = conf.route.route("0.0.0.0")[0]
        ip = get_if_addr(iface)
    except Exception as exc:  # pragma: no cover - depends on host
        log.debug("default route detection failed: %s", exc)
        return "", "", ""
    if not ip or ip == "0.0.0.0":
        return "", "", ""
    netmask = ""
    try:
        import psutil
        for addr in psutil.net_if_addrs().get(str(iface), []):
            if addr.family == socket.AF_INET and addr.address == ip:
                netmask = addr.netmask or ""
                break
    except Exception as exc:  # pragma: no cover
        log.debug("netmask lookup failed: %s", exc)
    try:
        network = ipaddress.ip_network(f"{ip}/{netmask or '24'}", strict=False)
        if network.prefixlen < 16:      # a /8 sweep would never finish on a Pi
            network = ipaddress.ip_network(f"{ip}/24", strict=False)
        return str(network), str(iface), ip
    except ValueError:
        return "", "", ""


def local_interfaces():
    """Every IPv4-configured interface: [{iface, ip, network, mac}]."""
    out = []
    try:
        import psutil
        for iface, addrs in psutil.net_if_addrs().items():
            mac = next((a.address.lower() for a in addrs if a.family == psutil.AF_LINK and a.address), "")
            for a in addrs:
                if a.family != socket.AF_INET or a.address.startswith("127."):
                    continue
                try:
                    net = ipaddress.ip_network(f"{a.address}/{a.netmask or '24'}", strict=False)
                except ValueError:
                    continue
                out.append({"iface": iface, "ip": a.address, "network": str(net),
                            "mac": mac if len(mac) == 17 else ""})
    except Exception as exc:  # pragma: no cover
        log.debug("interface enumeration failed: %s", exc)
    return out


def interface_for(network, interfaces=None):
    """The local interface attached to `network`, or None if the host is not on it."""
    try:
        target = ipaddress.ip_network(network, strict=False)
    except ValueError:
        return None
    for entry in interfaces if interfaces is not None else local_interfaces():
        local = ipaddress.ip_network(entry["network"], strict=False)
        if target.subnet_of(local) or local.subnet_of(target) or ipaddress.ip_address(entry["ip"]) in target:
            return entry
    return None


def arp_sweep(network, timeout=2, iface=None):
    """Return a list of {'ip', 'mac'} for every ARP reply on `network`.

    The same MAC may appear with several IPs: routers commonly answer for a
    secondary address or proxy-ARP for unused ones. The caller decides which
    address is the primary one."""
    from scapy.all import ARP, Ether, srp
    try:
        kwargs = {"timeout": timeout, "retry": 1, "verbose": 0}
        if iface:
            kwargs["iface"] = iface
        answered, _ = srp(Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=network), **kwargs)
    except PermissionError as exc:
        raise RawSocketPermissionError(
            "Raw socket access denied. Run as root or grant CAP_NET_RAW/CAP_NET_ADMIN."
        ) from exc
    except OSError as exc:
        if "Operation not permitted" in str(exc) or getattr(exc, "errno", None) in (1, 13):
            raise RawSocketPermissionError(
                "Raw socket access denied. Run as root or grant CAP_NET_RAW/CAP_NET_ADMIN."
            ) from exc
        raise
    seen = set()
    replies = []
    for _sent, received in answered:
        mac = received.hwsrc.lower()
        if not mac or mac == "00:00:00:00:00:00" or (mac, received.psrc) in seen:
            continue
        seen.add((mac, received.psrc))
        replies.append({"ip": received.psrc, "mac": mac})
    return replies


# --- hostname resolution ---------------------------------------------------

def _reverse_dns(ip, timeout=1.5):
    old = socket.getdefaulttimeout()
    socket.setdefaulttimeout(timeout)
    try:
        name = socket.gethostbyaddr(ip)[0]
        return name.rstrip(".")
    except (socket.herror, socket.gaierror, socket.timeout, OSError):
        return ""
    finally:
        socket.setdefaulttimeout(old)


def _mdns_reverse(ip, timeout=1.0):
    """Ask the host directly (unicast mDNS) for its PTR record. Works for most
    Apple, Linux and IoT devices running an mDNS responder."""
    try:
        import dns.message
        import dns.rdatatype
        import dns.reversename
        qname = dns.reversename.from_address(ip)
        query = dns.message.make_query(qname, dns.rdatatype.PTR)
        query.id = 0
        wire = bytearray(query.to_wire())
        # Set the QU (unicast response) bit on the question class.
        # Header is 12 bytes; question name follows, then type (2) + class (2).
        idx = 12
        while wire[idx] != 0:
            idx += wire[idx] + 1
        idx += 1 + 2
        wire[idx] |= 0x80
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        try:
            sock.sendto(bytes(wire), (ip, 5353))
            data, _ = sock.recvfrom(2048)
        finally:
            sock.close()
        resp = dns.message.from_wire(data, ignore_trailing=True)
        for rrset in resp.answer:
            if rrset.rdtype == dns.rdatatype.PTR:
                return str(rrset[0].target).rstrip(".").removesuffix(".local")
    except Exception:
        pass
    return ""


def _netbios_name(ip, timeout=1.0):
    """NBSTAT query (UDP 137) for Windows / Samba hosts."""
    tid = random.randint(1, 0xFFFF)
    header = struct.pack(">HHHHHH", tid, 0x0000, 1, 0, 0, 0)
    # Encoded wildcard name "*" padded to 16 bytes.
    name = b"\x20" + b"CK" + b"AA" * 15 + b"\x00"
    packet = header + name + struct.pack(">HH", 0x0021, 0x0001)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        sock.sendto(packet, (ip, 137))
        data, _ = sock.recvfrom(1024)
    except (socket.timeout, OSError):
        return ""
    finally:
        sock.close()
    try:
        count = data[56]
        offset = 57
        for _ in range(count):
            entry = data[offset:offset + 18]
            offset += 18
            nb_name, suffix, flags = entry[:15], entry[15], struct.unpack(">H", entry[16:18])[0]
            is_group = flags & 0x8000
            if suffix == 0x00 and not is_group:
                return nb_name.decode("ascii", errors="ignore").strip()
    except (IndexError, struct.error):
        pass
    return ""


def resolve_hostname(ip):
    """Try reverse DNS, mDNS and NetBIOS in turn. Returns '' if nothing answers."""
    for fn in (_reverse_dns, _mdns_reverse, _netbios_name):
        try:
            name = fn(ip)
        except Exception as exc:  # defensive: never let enrichment kill a worker
            log.debug("%s failed for %s: %s", fn.__name__, ip, exc)
            name = ""
        if name and name != ip:
            return name[:255]
    return ""

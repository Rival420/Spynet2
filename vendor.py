"""MAC vendor (OUI) lookup with a persistent cache and polite rate limiting."""
import logging
import threading
import time

import requests

from db import session_scope
from models import VendorCache

log = logging.getLogger("spynet.vendor")

API = "https://api.macvendors.com/{}"
_lock = threading.Lock()
_last_call = 0.0
_MIN_GAP = 1.1          # macvendors.com free tier allows ~1 request/second
_memory = {}            # prefix -> vendor, avoids DB hits inside a sweep
RETRY_UNKNOWN_AFTER = 7 * 86400


def normalize_mac(mac):
    return mac.strip().lower().replace("-", ":")


def is_randomized(mac):
    """Locally administered MACs (privacy addresses on phones) carry no vendor."""
    try:
        first = int(mac.split(":")[0], 16)
    except (ValueError, IndexError):
        return False
    return bool(first & 0x02) and not bool(first & 0x01)


def prefix_of(mac):
    return normalize_mac(mac)[:8]


def cached_vendor(mac):
    """Vendor from memory/DB cache only; never hits the network."""
    mac = normalize_mac(mac)
    if is_randomized(mac):
        return "Private address"
    prefix = prefix_of(mac)
    if prefix in _memory:
        return _memory[prefix]
    with session_scope() as s:
        row = s.get(VendorCache, prefix)
        if row and row.vendor:
            _memory[prefix] = row.vendor
            return row.vendor
    return ""


def lookup_vendor(mac, force=False):
    """Vendor name, fetching from macvendors.com when not cached. Blocking."""
    global _last_call
    mac = normalize_mac(mac)
    if is_randomized(mac):
        return "Private address"
    prefix = prefix_of(mac)
    if not force:
        cached = cached_vendor(mac)
        if cached:
            return cached
        with session_scope() as s:
            row = s.get(VendorCache, prefix)
            if row and not row.vendor and time.time() - (row.fetched_at or 0) < RETRY_UNKNOWN_AFTER:
                return ""

    with _lock:
        wait = _MIN_GAP - (time.time() - _last_call)
        if wait > 0:
            time.sleep(wait)
        vendor = ""
        try:
            resp = requests.get(API.format(mac), timeout=6)
            if resp.status_code == 200:
                vendor = resp.text.strip()[:120]
            elif resp.status_code == 429:
                log.warning("macvendors.com rate limited us; will retry later")
                _last_call = time.time()
                return ""
        except requests.RequestException as exc:
            log.debug("vendor lookup failed for %s: %s", mac, exc)
            _last_call = time.time()
            return ""
        _last_call = time.time()

    with session_scope() as s:
        row = s.get(VendorCache, prefix)
        if row is None:
            s.add(VendorCache(prefix=prefix, vendor=vendor, fetched_at=time.time()))
        else:
            row.vendor, row.fetched_at = vendor, time.time()
    if vendor:
        _memory[prefix] = vendor
    return vendor

"""Persisted scanner settings (key/value in SQLite) with typed defaults."""
import json

import config
from db import session_scope
from models import Setting

DEFAULTS = {
    "network": config.DEFAULT_NETWORK,   # CIDR, empty = auto-detect
    "sweep_interval": 30,                # seconds between ARP sweeps
    "offline_after": 120,                # seconds unseen before a device counts as offline
    "arp_timeout": 2,                    # seconds to wait for ARP replies
    "portscan_mode": "quick",            # quick | range | full | off
    "port_range_start": 1,
    "port_range_end": 1024,
    "portscan_interval": 3600,           # seconds between automatic port scans per device
    "port_timeout": 1.0,
    "auto_start": False,                 # resume scanning when the service boots
    "webhook_url": "",
    "notify_new_device": True,
    "notify_online": False,
    "notify_offline": False,
    "notify_ports_changed": True,
}

BOUNDS = {
    "sweep_interval": (5, 3600),
    "offline_after": (10, 86400),
    "arp_timeout": (1, 30),
    "port_range_start": (1, 65535),
    "port_range_end": (1, 65535),
    "portscan_interval": (60, 7 * 86400),
    "port_timeout": (0.2, 10),
}


def _coerce(key, value):
    default = DEFAULTS[key]
    if isinstance(default, bool):
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "on")
        return bool(value)
    if isinstance(default, int):
        value = int(float(value))
    elif isinstance(default, float):
        value = float(value)
    else:
        value = str(value).strip()
    if key in BOUNDS:
        lo, hi = BOUNDS[key]
        value = max(lo, min(hi, value))
    return value


def load():
    result = dict(DEFAULTS)
    with session_scope() as s:
        for row in s.query(Setting).all():
            if row.key in DEFAULTS:
                try:
                    result[row.key] = _coerce(row.key, json.loads(row.value))
                except (ValueError, TypeError):
                    pass
    if result["portscan_mode"] not in ("quick", "range", "full", "off"):
        result["portscan_mode"] = "quick"
    if result["port_range_end"] < result["port_range_start"]:
        result["port_range_start"], result["port_range_end"] = result["port_range_end"], result["port_range_start"]
    return result


def save(updates):
    """Validate and persist a partial update. Returns the full settings."""
    clean = {}
    for key, value in updates.items():
        if key not in DEFAULTS:
            continue
        try:
            clean[key] = _coerce(key, value)
        except (ValueError, TypeError):
            raise ValueError(f"Invalid value for {key}")
    if "portscan_mode" in clean and clean["portscan_mode"] not in ("quick", "range", "full", "off"):
        raise ValueError("portscan_mode must be quick, range, full or off")
    with session_scope() as s:
        for key, value in clean.items():
            row = s.get(Setting, key)
            if row is None:
                s.add(Setting(key=key, value=json.dumps(value)))
            else:
                row.value = json.dumps(value)
    return load()

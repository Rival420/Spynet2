"""SQLAlchemy models. Devices are keyed by MAC address, because on a home
network the IP of a device changes with every DHCP lease while the MAC stays."""
import json
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def iso(dt):
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True)
    mac = Column(String(17), unique=True, nullable=False, index=True)
    ip = Column(String(45), default="")
    previous_ip = Column(String(45), default="")
    other_ips_json = Column(Text, default="[]")     # further IPs this MAC answers for
    vendor = Column(String(120), default="")
    hostname = Column(String(255), default="")      # discovered (rDNS / mDNS / NetBIOS)
    name = Column(String(120), default="")          # chosen by the user
    notes = Column(Text, default="")
    device_type = Column(String(32), default="")    # user-picked category
    known = Column(Boolean, default=False)          # acknowledged by the user
    online = Column(Boolean, default=False)
    first_seen = Column(DateTime, default=utcnow)
    last_seen = Column(DateTime, default=utcnow)
    ports_json = Column(Text, default="[]")
    baseline_ports_json = Column(Text, nullable=True)  # accepted set of open ports, None = no baseline
    ports_scanned_at = Column(DateTime, nullable=True)
    hostname_checked_at = Column(DateTime, nullable=True)

    @property
    def ports(self):
        try:
            return sorted({int(p) for p in json.loads(self.ports_json or "[]")})
        except (ValueError, TypeError):
            return []

    @ports.setter
    def ports(self, value):
        self.ports_json = json.dumps(sorted({int(p) for p in value}))

    @property
    def baseline_ports(self):
        if self.baseline_ports_json is None:
            return None
        try:
            return sorted({int(p) for p in json.loads(self.baseline_ports_json)})
        except (ValueError, TypeError):
            return None

    @baseline_ports.setter
    def baseline_ports(self, value):
        self.baseline_ports_json = None if value is None else json.dumps(sorted({int(p) for p in value}))

    @property
    def other_ips(self):
        try:
            return list(json.loads(self.other_ips_json or "[]"))
        except (ValueError, TypeError):
            return []

    @other_ips.setter
    def other_ips(self, value):
        self.other_ips_json = json.dumps(list(value))

    def to_dict(self):
        return {
            "mac": self.mac,
            "ip": self.ip or "",
            "previous_ip": self.previous_ip or "",
            "other_ips": self.other_ips,
            "vendor": self.vendor or "",
            "hostname": self.hostname or "",
            "name": self.name or "",
            "notes": self.notes or "",
            "device_type": self.device_type or "",
            "known": bool(self.known),
            "online": bool(self.online),
            "first_seen": iso(self.first_seen),
            "last_seen": iso(self.last_seen),
            "ports": self.ports,
            "baseline_ports": self.baseline_ports,
            "ports_scanned_at": iso(self.ports_scanned_at),
        }


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True)
    ts = Column(DateTime, default=utcnow, index=True)
    kind = Column(String(32), index=True)   # new_device, online, offline, ip_change, ports_changed, scanner
    mac = Column(String(17), index=True, default="")
    ip = Column(String(45), default="")
    message = Column(Text, default="")
    details_json = Column(Text, default="{}")

    def to_dict(self):
        try:
            details = json.loads(self.details_json or "{}")
        except ValueError:
            details = {}
        return {
            "id": self.id,
            "ts": iso(self.ts),
            "kind": self.kind,
            "mac": self.mac or "",
            "ip": self.ip or "",
            "message": self.message or "",
            "details": details,
        }


class Presence(Base):
    """One row per stretch of time a device was online."""
    __tablename__ = "presence"

    id = Column(Integer, primary_key=True)
    mac = Column(String(17), index=True, nullable=False)
    started_at = Column(DateTime, index=True, nullable=False)
    ended_at = Column(DateTime, nullable=True)   # None while the device is still online

    def to_pair(self):
        return [iso(self.started_at), iso(self.ended_at)]


class Setting(Base):
    __tablename__ = "settings"

    key = Column(String(64), primary_key=True)
    value = Column(Text, default="")


class VendorCache(Base):
    """OUI prefix (first 3 bytes of the MAC) -> vendor name."""
    __tablename__ = "vendor_cache"

    prefix = Column(String(8), primary_key=True)
    vendor = Column(String(120), default="")
    fetched_at = Column(Float, default=0.0)

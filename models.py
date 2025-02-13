# models.py
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Host(Base):
    __tablename__ = 'hosts'
    id = Column(Integer, primary_key=True)
    ip = Column(String, unique=True, nullable=False)
    mac = Column(String, nullable=False)
    vendor = Column(String, default="Unknown")
    hostname = Column(String, default="")        # For custom naming later
    dns_name = Column(String, default="") # to add a dns name as well
    is_dhcp = Column(Boolean, default=False)       # DHCP flag
    last_seen = Column(DateTime, default=datetime.utcnow)
    port_scan_result = Column(String, default="")  # e.g. comma-separated open ports

    def __repr__(self):
        return f"<Host(ip={self.ip}, mac={self.mac}, vendor={self.vendor}, last_seen={self.last_seen})>"

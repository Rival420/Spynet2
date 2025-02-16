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
    hostname = Column(String, default="")        # Custom hostname
    is_dhcp = Column(Boolean, default=False)       # DHCP flag
    last_seen = Column(DateTime, default=datetime.utcnow)
    port_scan_result = Column(String, default="")  # e.g., comma-separated list of ports

    def __repr__(self):
        return f"<Host(ip={self.ip}, mac={self.mac}, vendor={self.vendor}, hostname={self.hostname}, is_dhcp={self.is_dhcp})>"

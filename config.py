"""Runtime configuration read from environment variables."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Where the SQLite database lives. Defaults next to the code; on the Pi the
# systemd unit points this at /var/lib/spynet/spynet.db.
DB_PATH = os.environ.get("SPYNET_DB", str(BASE_DIR / "spynet.db"))

# Web server bind address / port.
HOST = os.environ.get("SPYNET_HOST", "0.0.0.0")
PORT = int(os.environ.get("SPYNET_PORT", "5000"))

# Built frontend (Vite output). Served by Flask so a single process runs it all.
FRONTEND_DIR = os.environ.get("SPYNET_FRONTEND_DIR", str(BASE_DIR / "spynet" / "dist"))

# Optional: preconfigure the network to watch (CIDR). Empty = auto-detect.
DEFAULT_NETWORK = os.environ.get("SPYNET_NETWORK", "")

# Concurrency limits, tuned for a Raspberry Pi.
PORT_SCAN_WORKERS = int(os.environ.get("SPYNET_PORT_WORKERS", "128"))

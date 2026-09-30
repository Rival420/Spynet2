"""Database setup. One scoped session per thread; use `session_scope()`."""
import json
import logging
from contextlib import contextmanager
from datetime import datetime

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import scoped_session, sessionmaker

import config
from models import Base, Device

log = logging.getLogger("spynet.db")

engine = create_engine(
    f"sqlite:///{config.DB_PATH}",
    echo=False,
    connect_args={"check_same_thread": False, "timeout": 30},
)


@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_conn, _record):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA synchronous=NORMAL")
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


SessionFactory = sessionmaker(bind=engine, expire_on_commit=False)
Session = scoped_session(SessionFactory)


@contextmanager
def session_scope():
    session = Session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        Session.remove()


def init_db():
    Base.metadata.create_all(engine)
    _add_missing_columns()
    _migrate_legacy_hosts()


def _add_missing_columns():
    """SQLite create_all never alters existing tables; add new columns here."""
    insp = inspect(engine)
    for table in Base.metadata.sorted_tables:
        if table.name not in insp.get_table_names():
            continue
        existing = {c["name"] for c in insp.get_columns(table.name)}
        for col in table.columns:
            if col.name in existing:
                continue
            ddl = f"ALTER TABLE {table.name} ADD COLUMN {col.name} {col.type.compile(engine.dialect)}"
            if col.default is not None and not callable(col.default.arg):
                ddl += f" DEFAULT {repr(col.default.arg)}"
            with engine.begin() as conn:
                conn.execute(text(ddl))
            log.info("Added column %s.%s", table.name, col.name)


def _migrate_legacy_hosts():
    """Import rows from the pre-2026 `hosts` table (keyed by IP) if present."""
    insp = inspect(engine)
    if "hosts" not in insp.get_table_names():
        return
    with session_scope() as s:
        if s.query(Device).count() > 0:
            return
        rows = s.execute(text(
            "SELECT ip, mac, vendor, hostname, last_seen, port_scan_result FROM hosts"
        )).fetchall()
        imported = 0
        for ip, mac, vendor, hostname, last_seen, ports in rows:
            if not mac or s.query(Device).filter_by(mac=mac.lower()).first():
                continue
            try:
                seen = datetime.fromisoformat(str(last_seen)) if last_seen else None
            except ValueError:
                seen = None
            port_list = [int(p) for p in (ports or "").split(",") if p.strip().isdigit()]
            s.add(Device(
                mac=mac.lower(), ip=ip or "", vendor=vendor or "",
                name=hostname or "", known=bool(hostname),
                first_seen=seen, last_seen=seen, online=False,
                ports_json=json.dumps(port_list),
            ))
            imported += 1
        if imported:
            log.info("Imported %d devices from legacy hosts table", imported)

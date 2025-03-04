# db.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base

# Read the DB path from an environment variable with a default value.
db_path = os.getenv("DB_PATH", "/app/data/spynet.db")

# For an absolute path, SQLite requires four slashes.
if os.path.isabs(db_path):
    engine = create_engine(f"sqlite:////{db_path.lstrip('/')}", echo=False)
else:
    engine = create_engine(f"sqlite:///{db_path}", echo=False)

# Create all tables if they don't exist.
Base.metadata.create_all(engine)

# Create a session factory and a session instance.
Session = sessionmaker(bind=engine)
db_session = Session()

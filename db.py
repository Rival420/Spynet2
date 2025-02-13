# db.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base

# Create an engine; this will create (or use) the spynet.db SQLite file.
engine = create_engine('sqlite:///spynet.db', echo=False)

# Create all tables (if they don't exist)
Base.metadata.create_all(engine)

# Create a session factory and a session instance.
Session = sessionmaker(bind=engine)
db_session = Session()

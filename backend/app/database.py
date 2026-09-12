"""
Occuris Database Setup — SQLAlchemy + SQLite
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "..", "occuris.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables and seed demo data."""
    from app.models import (
        Gateway, Vessel, AISPosition, GatewayCrossing,  # noqa
        Journey, BehaviourEvent, SpillIncident,          # noqa
    )
    Base.metadata.create_all(bind=engine)
    print("[OK] Database tables created.")

    # Seed the four demo gateways if not already present
    from app.services.gateway_seed import seed_gateways
    db = SessionLocal()
    try:
        seed_gateways(db)
    finally:
        db.close()

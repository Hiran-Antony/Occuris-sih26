"""
Unit tests for the Gateway module.

Tests:
  1. normal_crossing          — vessel segment crosses gate_a → crossing recorded
  2. no_crossing              — segment stays inside region → no crossing
  3. duplicate_prevention     — second crossing within 30 min → skipped
  4. missing_previous_position — first position for vessel → no crossing attempted

Run with:
    cd backend
    pytest tests/test_gateway.py -v
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.database import Base
from app.models import Gateway, GatewayCrossing, Vessel, AISPosition
from app.services.gateway_seed import seed_gateways
from app.services.gateway_crossing_service import detect_and_record_crossings


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="function")
def db() -> Session:
    """
    Provide a fresh in-memory SQLite session for each test.
    Seeds the four demo gateways automatically.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        echo=False,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    # Seed demo gateways
    seed_gateways(session)

    yield session

    session.close()
    engine.dispose()


def _add_demo_vessel(db: Session, mmsi: str = "DEMO-111111111") -> Vessel:
    """Insert a DEMO vessel for testing."""
    vessel = Vessel(mmsi=mmsi, vessel_type="DEMO", name=f"DEMO-{mmsi}", flag="DEMO")
    db.add(vessel)
    db.flush()
    return vessel


def _add_position(
    db: Session,
    mmsi: str,
    lat: float,
    lon: float,
    ts: datetime,
) -> AISPosition:
    pos = AISPosition(
        mmsi=mmsi, timestamp=ts,
        latitude=lat, longitude=lon,
        speed=8.0, course=90.0,
    )
    db.add(pos)
    db.flush()
    return pos


# ── Test 1: Normal crossing ───────────────────────────────────────────────────

def test_normal_crossing(db: Session):
    """
    Vessel moves from lon=79.5 to lon=80.5, crossing gate_a at lon=80.
    Exactly one GatewayCrossing record should be created.
    """
    mmsi = "DEMO-111111111"
    _add_demo_vessel(db, mmsi)

    base_ts = datetime(2026, 9, 1, 10, 0, 0)

    crossed = detect_and_record_crossings(
        mmsi=mmsi,
        prev_lat=13.0, prev_lon=79.5,   # just west of gate_a
        curr_lat=13.0, curr_lon=80.5,   # just east of gate_a
        curr_ts=base_ts + timedelta(minutes=10),
        db=db,
    )
    db.commit()

    assert "gate_a" in crossed, "Expected gate_a to be detected"

    crossing_rows = db.query(GatewayCrossing).filter(GatewayCrossing.mmsi == mmsi).all()
    assert len(crossing_rows) == 1
    assert crossing_rows[0].gateway_id == "gate_a"
    assert crossing_rows[0].direction == "entering"


# ── Test 2: No crossing ───────────────────────────────────────────────────────

def test_no_crossing(db: Session):
    """
    Vessel moves entirely inside the BOB region (lon 85→87).
    No gateway crossing should be recorded.
    """
    mmsi = "DEMO-222222222"
    _add_demo_vessel(db, mmsi)

    crossed = detect_and_record_crossings(
        mmsi=mmsi,
        prev_lat=13.0, prev_lon=85.0,
        curr_lat=13.0, curr_lon=87.0,
        curr_ts=datetime(2026, 9, 1, 11, 0, 0),
        db=db,
    )
    db.commit()

    assert crossed == [], f"Expected no crossings but got: {crossed}"
    count = db.query(GatewayCrossing).filter(GatewayCrossing.mmsi == mmsi).count()
    assert count == 0


# ── Test 3: Duplicate crossing prevention ────────────────────────────────────

def test_duplicate_crossing_prevention(db: Session):
    """
    Two segments cross gate_a within 30 minutes of each other.
    Only the first crossing should be recorded.
    """
    mmsi = "DEMO-333333333"
    _add_demo_vessel(db, mmsi)

    base_ts = datetime(2026, 9, 1, 12, 0, 0)

    # First crossing
    detect_and_record_crossings(
        mmsi=mmsi,
        prev_lat=13.0, prev_lon=79.5,
        curr_lat=13.0, curr_lon=80.5,
        curr_ts=base_ts,
        db=db,
    )
    db.commit()

    # Second crossing — 15 minutes later (within dedup window)
    detect_and_record_crossings(
        mmsi=mmsi,
        prev_lat=13.0, prev_lon=79.5,
        curr_lat=13.0, curr_lon=80.5,
        curr_ts=base_ts + timedelta(minutes=15),
        db=db,
    )
    db.commit()

    count = db.query(GatewayCrossing).filter(
        GatewayCrossing.mmsi == mmsi,
        GatewayCrossing.gateway_id == "gate_a",
    ).count()
    assert count == 1, f"Expected 1 crossing (dedup), got {count}"


# ── Test 4: Duplicate allowed after window ────────────────────────────────────

def test_duplicate_allowed_after_window(db: Session):
    """
    Two crossings of gate_a more than 30 minutes apart should both be recorded.
    """
    mmsi = "DEMO-444444444"
    _add_demo_vessel(db, mmsi)

    base_ts = datetime(2026, 9, 1, 14, 0, 0)

    detect_and_record_crossings(
        mmsi=mmsi,
        prev_lat=13.0, prev_lon=79.5,
        curr_lat=13.0, curr_lon=80.5,
        curr_ts=base_ts,
        db=db,
    )
    db.commit()

    # 31 minutes later — outside dedup window
    detect_and_record_crossings(
        mmsi=mmsi,
        prev_lat=13.0, prev_lon=79.5,
        curr_lat=13.0, curr_lon=80.5,
        curr_ts=base_ts + timedelta(minutes=31),
        db=db,
    )
    db.commit()

    count = db.query(GatewayCrossing).filter(
        GatewayCrossing.mmsi == mmsi,
        GatewayCrossing.gateway_id == "gate_a",
    ).count()
    assert count == 2, f"Expected 2 crossings (outside window), got {count}"


# ── Test 5: Missing previous position ────────────────────────────────────────

def test_missing_previous_position(db: Session):
    """
    When there is no previous AIS position for a vessel, the caller receives
    an empty list — this mirrors the POST /api/ais/positions guard in ais.py.
    """
    mmsi = "DEMO-555555555"
    _add_demo_vessel(db, mmsi)

    # No previous position → caller passes prev_lat/lon equal to curr → no segment
    # Simulated by calling detect with identical prev and curr (zero-length segment)
    crossed = detect_and_record_crossings(
        mmsi=mmsi,
        prev_lat=13.0, prev_lon=80.5,
        curr_lat=13.0, curr_lon=80.5,   # same point, zero-length — won't intersect
        curr_ts=datetime(2026, 9, 1, 9, 0, 0),
        db=db,
    )
    db.commit()

    assert crossed == []
    count = db.query(GatewayCrossing).filter(GatewayCrossing.mmsi == mmsi).count()
    assert count == 0


# ── Test 6: Gateways are seeded ───────────────────────────────────────────────

def test_gateways_seeded(db: Session):
    """All four demo gateways must be present after seed."""
    gateways = db.query(Gateway).all()
    ids = {gw.id for gw in gateways}
    assert ids == {"gate_a", "gate_b", "gate_c", "gate_d"}


# ── Test 7: Geometry is valid GeoJSON ────────────────────────────────────────

def test_gateway_geojson_feature(db: Session):
    """Each gateway must return a valid GeoJSON Feature with a LineString."""
    gateways = db.query(Gateway).all()
    for gw in gateways:
        feature = gw.to_geojson_feature()
        assert feature["type"] == "Feature"
        assert feature["geometry"]["type"] == "LineString"
        assert len(feature["geometry"]["coordinates"]) >= 2

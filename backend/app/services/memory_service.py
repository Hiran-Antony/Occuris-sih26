"""
Maritime Memory service.
Stores and queries the complete vessel movement history.
This service is the core of the Occuris concept —
the system continuously remembers before any incident occurs.
"""
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models import Vessel, AISPosition, GatewayCrossing, Journey, BehaviourEvent
from app.algorithms.geometry import point_in_region
from app.services.gateway_service import process_position_pair


# Per-vessel state for streaming ingestion
_vessel_state: Dict[str, Dict] = {}


def reset_vessel_state():
    _vessel_state.clear()


def ingest_position(record: Dict, db: Session):
    """
    Process a single AIS position record:
    1. Ensure vessel exists in DB
    2. Check region containment
    3. Detect gateway crossings
    4. Store position
    """
    mmsi = str(record["mmsi"])
    ts = record["timestamp"] if isinstance(record["timestamp"], datetime) else \
        datetime.fromisoformat(str(record["timestamp"]))

    # Ensure vessel record exists
    vessel = db.query(Vessel).filter(Vessel.mmsi == mmsi).first()
    if vessel is None:
        vessel = Vessel(
            mmsi=mmsi,
            vessel_type=record.get("vessel_type", "unknown"),
            name=record.get("name", None),
            flag=record.get("flag", None),
        )
        db.add(vessel)
        db.flush()

    lat = float(record["latitude"])
    lon = float(record["longitude"])
    curr_inside = point_in_region(lat, lon)

    # Gateway detection (only possible if we have a previous position)
    state = _vessel_state.get(mmsi)
    if state is not None:
        _, crossed_gw = process_position_pair(
            mmsi=mmsi,
            vessel_type=vessel.vessel_type,
            prev_lat=state["lat"], prev_lon=state["lon"],
            prev_ts=state["ts"], prev_inside=state["inside"],
            curr_lat=lat, curr_lon=lon, curr_ts=ts,
            db=db,
        )

    # Update state
    _vessel_state[mmsi] = {"lat": lat, "lon": lon, "ts": ts, "inside": curr_inside}

    # Store the position
    pos = AISPosition(
        mmsi=mmsi,
        timestamp=ts,
        latitude=lat,
        longitude=lon,
        speed=float(record.get("speed", 0.0)),
        course=float(record.get("course", 0.0)),
        heading=record.get("heading"),
        nav_status=record.get("nav_status", "underway"),
        inside_region=curr_inside,
        flagged=bool(record.get("flagged", False)),
        flag_reason=record.get("flag_reason"),
    )
    db.add(pos)


# ── Query helpers ──────────────────────────────────────────────────────────

def get_vessel_track(mmsi: str, db: Session) -> List[Dict]:
    """Return all AIS positions for a vessel, sorted by time."""
    positions = (
        db.query(AISPosition)
        .filter(AISPosition.mmsi == mmsi)
        .order_by(AISPosition.timestamp)
        .all()
    )
    return [p.to_dict() for p in positions]


def get_vessel_timeline(mmsi: str, db: Session) -> List[Dict]:
    """
    Return a unified journey timeline for a vessel:
    gateway crossings + behaviour events, sorted by time.
    """
    events = []

    crossings = (
        db.query(GatewayCrossing)
        .filter(GatewayCrossing.mmsi == mmsi)
        .order_by(GatewayCrossing.timestamp)
        .all()
    )
    for c in crossings:
        events.append({
            "time": c.timestamp.isoformat(),
            "type": "gateway_crossing",
            "label": f"{c.direction.capitalize()} {c.gateway_name}",
            "gateway_id": c.gateway_id,
            "direction": c.direction,
            "latitude": c.latitude,
            "longitude": c.longitude,
        })

    beh_events = (
        db.query(BehaviourEvent)
        .filter(BehaviourEvent.mmsi == mmsi)
        .order_by(BehaviourEvent.start_time)
        .all()
    )
    for e in beh_events:
        events.append({
            "time": e.start_time.isoformat(),
            "end_time": e.end_time.isoformat() if e.end_time else None,
            "type": "behaviour_event",
            "event_type": e.event_type,
            "label": e.description or e.event_type.replace("_", " ").title(),
            "severity": e.severity,
            "is_explained": e.is_explained,
            "explanation": e.explanation,
            "latitude": e.latitude,
            "longitude": e.longitude,
        })

    events.sort(key=lambda x: x["time"])
    return events


def get_all_vessels_summary(db: Session) -> List[Dict]:
    """Return summary of all vessels with their latest journey info."""
    vessels = db.query(Vessel).all()
    result = []
    for v in vessels:
        journey = (
            db.query(Journey)
            .filter(Journey.mmsi == v.mmsi)
            .order_by(desc(Journey.entry_time))
            .first()
        )
        events = db.query(BehaviourEvent).filter(BehaviourEvent.mmsi == v.mmsi).all()
        unexplained = [e for e in events if not e.is_explained]

        result.append({
            **v.to_dict(),
            "journey": journey.to_dict() if journey else None,
            "behaviour_event_count": len(events),
            "unexplained_event_count": len(unexplained),
        })
    return result


def get_recent_crossings(db: Session, limit: int = 30) -> List[Dict]:
    """Return the most recent gateway crossings across all vessels."""
    crossings = (
        db.query(GatewayCrossing)
        .order_by(desc(GatewayCrossing.timestamp))
        .limit(limit)
        .all()
    )
    return [c.to_dict() for c in crossings]


def get_dashboard_stats(db: Session) -> Dict:
    """Return counts for the monitoring dashboard."""
    total_vessels = db.query(Vessel).count()
    vessels_in_region = db.query(AISPosition.mmsi).filter(
        AISPosition.inside_region == True
    ).distinct().count()
    total_crossings = db.query(GatewayCrossing).count()
    total_anomalies = db.query(BehaviourEvent).count()
    unexplained = db.query(BehaviourEvent).filter(BehaviourEvent.is_explained == False).count()
    completed_journeys = db.query(Journey).filter(Journey.status == "completed").count()

    return {
        "total_vessels": total_vessels,
        "vessels_ever_in_region": vessels_in_region,
        "total_gateway_crossings": total_crossings,
        "total_behaviour_events": total_anomalies,
        "unexplained_events": unexplained,
        "completed_journeys": completed_journeys,
    }

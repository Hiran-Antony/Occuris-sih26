"""
Behaviour analysis service.
Runs all anomaly detectors on stored vessel positions and
applies contextual explanations (weather / traffic).
"""
import json
import os
from datetime import datetime
from typing import List, Dict
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models import Vessel, AISPosition, BehaviourEvent, Journey
from app.algorithms.anomaly_detection import run_all_detectors
from app.algorithms.geometry import haversine_nm


def _load_wind_data() -> Dict:
    path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "environmental", "wind.json")
    with open(path) as f:
        return json.load(f)


def _wind_speed_at(lat: float, lon: float, ts: datetime, wind_data: Dict) -> float:
    """
    Return approximate wind speed (knots) at location and time.
    Finds the nearest wind event that covers the location and time.
    """
    for event in wind_data.get("wind_events", []):
        t_start = datetime.fromisoformat(event["start"])
        t_end   = datetime.fromisoformat(event["end"])
        if not (t_start <= ts <= t_end):
            continue
        if not (event["lat_min"] <= lat <= event["lat_max"]):
            continue
        if not (event["lon_min"] <= lon <= event["lon_max"]):
            continue
        return event["speed_knots"]
    return 0.0


def _count_slow_vessels_nearby(lat: float, lon: float, ts: datetime,
                                radius_nm: float, db: Session) -> int:
    """Count vessels with low speed near a location at a given time window."""
    from datetime import timedelta
    t_min = ts - timedelta(minutes=30)
    t_max = ts + timedelta(minutes=30)
    positions = (
        db.query(AISPosition)
        .filter(
            AISPosition.timestamp.between(t_min, t_max),
            AISPosition.speed < 4.0,
        )
        .all()
    )
    count = 0
    for p in positions:
        if haversine_nm(lat, lon, p.latitude, p.longitude) <= radius_nm:
            count += 1
    return count


def analyse_vessel(mmsi: str, db: Session, wind_data: Dict = None) -> int:
    """
    Run behaviour analysis for one vessel and store events in the DB.
    Returns the number of events detected.
    """
    if wind_data is None:
        wind_data = _load_wind_data()

    vessel = db.query(Vessel).filter(Vessel.mmsi == mmsi).first()
    if vessel is None:
        return 0

    # Fetch all positions for this vessel (sorted by time)
    positions_orm = (
        db.query(AISPosition)
        .filter(AISPosition.mmsi == mmsi)
        .order_by(AISPosition.timestamp)
        .all()
    )
    if len(positions_orm) < 2:
        return 0

    positions = [p.to_dict() for p in positions_orm]
    # Convert timestamps back to datetime for algorithm functions
    for p in positions:
        if isinstance(p["timestamp"], str):
            p["timestamp"] = datetime.fromisoformat(p["timestamp"])

    # Fetch journey for route deviation check
    journey = (
        db.query(Journey)
        .filter(Journey.mmsi == mmsi)
        .order_by(Journey.entry_time)
        .first()
    )
    entry_gw = journey.entry_gateway if journey else None
    exit_gw = journey.exit_gateway if journey else None

    # Clear existing behaviour events for this vessel
    db.query(BehaviourEvent).filter(BehaviourEvent.mmsi == mmsi).delete()

    raw_events = run_all_detectors(positions, vessel.vessel_type, entry_gw, exit_gw)

    for evt in raw_events:
        evt_lat = evt.get("latitude")
        evt_lon = evt.get("longitude")
        evt_ts  = evt["start_time"]

        # Context: weather explanation
        is_explained = False
        explanation = None

        wind_spd = _wind_speed_at(evt_lat or 0, evt_lon or 0, evt_ts, wind_data) \
            if evt_lat else 0.0

        if evt["event_type"] in ("speed_reduction", "operational_stop"):
            if wind_spd >= 22:
                is_explained = True
                explanation = f"Consistent with adverse weather — wind {wind_spd:.0f} kn at location"
            else:
                nearby_slow = _count_slow_vessels_nearby(
                    evt_lat or 0, evt_lon or 0, evt_ts, 50, db
                )
                if nearby_slow >= 3:
                    is_explained = True
                    explanation = f"Consistent with traffic — {nearby_slow} slow vessels nearby"

        elif evt["event_type"] == "route_deviation":
            if wind_spd >= 25:
                is_explained = True
                explanation = f"Possible weather-forced deviation — wind {wind_spd:.0f} kn"

        db.add(BehaviourEvent(
            mmsi=mmsi,
            start_time=evt["start_time"],
            end_time=evt.get("end_time"),
            event_type=evt["event_type"],
            severity=evt["severity"],
            latitude=evt_lat,
            longitude=evt_lon,
            description=evt["description"],
            explanation=explanation,
            is_explained=is_explained,
        ))

    db.flush()
    return len(raw_events)


def analyse_all_vessels(db: Session):
    """Run behaviour analysis for every vessel in the database."""
    wind_data = _load_wind_data()
    vessels = db.query(Vessel).all()
    total = 0
    for v in vessels:
        n = analyse_vessel(v.mmsi, db, wind_data)
        total += n
        print(f"  {v.mmsi}: {n} events")
    db.commit()
    print(f"[OK] Behaviour analysis complete: {total} events across {len(vessels)} vessels")

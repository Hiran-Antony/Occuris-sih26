"""
Gateway detection and crossing recording service.
"""
from datetime import datetime
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from app.models import GatewayCrossing, Journey
from app.algorithms.geometry import point_in_region, detect_gateway_crossing
from app.algorithms.route_analysis import expected_journey_hours, gateway_distance_nm

GATEWAY_NAMES = {
    "A": "Gateway Alpha — Western Boundary",
    "B": "Gateway Bravo — Northern Boundary",
    "C": "Gateway Charlie — Southern Boundary",
    "D": "Gateway Delta — Eastern Boundary",
}


def process_position_pair(
    mmsi: str,
    vessel_type: str,
    prev_lat: float, prev_lon: float, prev_ts: datetime, prev_inside: bool,
    curr_lat: float, curr_lon: float, curr_ts: datetime,
    db: Session,
) -> Tuple[bool, Optional[str]]:
    """
    Given two consecutive positions, detect gateway crossings and
    update the journey record in the database.

    Returns (curr_inside_region, gateway_crossed_id).
    """
    curr_inside = point_in_region(curr_lat, curr_lon)

    result = detect_gateway_crossing(
        prev_lat, prev_lon, prev_inside,
        curr_lat, curr_lon, curr_inside,
    )

    if result is not None:
        gw_id, direction = result
        crossing = GatewayCrossing(
            mmsi=mmsi,
            gateway_id=gw_id,
            gateway_name=GATEWAY_NAMES.get(gw_id, gw_id),
            timestamp=curr_ts,
            direction=direction,
            latitude=curr_lat,
            longitude=curr_lon,
        )
        db.add(crossing)

        if direction == "entering":
            _open_journey(mmsi, vessel_type, gw_id, curr_ts, db)
        elif direction == "exiting":
            _close_journey(mmsi, gw_id, curr_ts, db)

        db.flush()
        return curr_inside, gw_id

    return curr_inside, None


def _open_journey(mmsi: str, vessel_type: str, entry_gw: str,
                  entry_time: datetime, db: Session):
    """Open a new journey record when a vessel enters the region."""
    # Close any open journey first (shouldn't happen in clean data)
    _close_open_journeys(mmsi, db)

    journey = Journey(
        mmsi=mmsi,
        entry_gateway=entry_gw,
        entry_time=entry_time,
        status="in_progress",
    )
    db.add(journey)


def _close_journey(mmsi: str, exit_gw: str, exit_time: datetime, db: Session):
    """Close the open journey when a vessel exits the region."""
    from sqlalchemy import desc
    journey = (
        db.query(Journey)
        .filter(Journey.mmsi == mmsi, Journey.status == "in_progress")
        .order_by(desc(Journey.entry_time))
        .first()
    )
    if journey is None:
        return

    journey.exit_gateway = exit_gw
    journey.exit_time = exit_time
    journey.status = "completed"

    if journey.entry_time:
        actual_h = (exit_time - journey.entry_time).total_seconds() / 3600
        journey.actual_duration_hours = round(actual_h, 2)

        vessel = db.query(__import__("app.models", fromlist=["Vessel"]).Vessel).get(mmsi)
        vtype = vessel.vessel_type if vessel else "default"
        exp_h = expected_journey_hours(journey.entry_gateway, exit_gw, vtype)
        journey.expected_duration_hours = exp_h
        journey.delay_hours = round(actual_h - exp_h, 2)
        journey.route_distance_nm = round(gateway_distance_nm(journey.entry_gateway, exit_gw), 1)


def _close_open_journeys(mmsi: str, db: Session):
    """Mark any lingering open journeys as incomplete."""
    open_journeys = (
        db.query(Journey)
        .filter(Journey.mmsi == mmsi, Journey.status == "in_progress")
        .all()
    )
    for j in open_journeys:
        j.status = "incomplete"

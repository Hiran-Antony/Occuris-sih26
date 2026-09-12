"""
Gateway crossing detection service.

Uses Shapely to check if the AIS segment (prev → curr) intersects any
registered gateway LineString.  Duplicate crossings for the same vessel +
gateway within 30 minutes are silently skipped.

No PostGIS required — pure Python / Shapely / SQLite.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from shapely.geometry import LineString, Point
from sqlalchemy.orm import Session

from app.models import Gateway, GatewayCrossing, Vessel

# Window for duplicate-crossing prevention
DEDUP_WINDOW_MINUTES: int = 30


# ── Internal helpers ──────────────────────────────────────────────────────────

def _gateway_shapely_lines(db: Session) -> List[dict]:
    """Load every Gateway row and build its Shapely LineString."""
    rows = db.query(Gateway).all()
    result = []
    for gw in rows:
        coords = json.loads(gw.geometry)["coordinates"]  # [[lon,lat], ...]
        result.append(
            {
                "id":   gw.id,
                "name": gw.name,
                "line": LineString(coords),
            }
        )
    return result


def _intersection_point(
    segment: LineString, gateway_line: LineString
) -> Optional[Tuple[float, float]]:
    """Return (lat, lon) of the intersection or None."""
    geom = segment.intersection(gateway_line)
    if geom.is_empty:
        return None
    if geom.geom_type == "Point":
        return geom.y, geom.x
    if geom.geom_type == "MultiPoint":
        p = list(geom.geoms)[0]
        return p.y, p.x
    # For GeometryCollection or other types, take centroid
    c = geom.centroid
    return c.y, c.x


def _crossing_direction(
    prev_lat: float, prev_lon: float,
    curr_lat: float, curr_lon: float,
    gateway_id: str,
) -> str:
    """
    Determine whether the vessel is entering or exiting the BOB region.

    gate_a  western boundary  lon=80   entering: lon increases (west→east)
    gate_b  northern boundary lat=22   entering: lat decreases (north→south)
    gate_c  southern boundary lat=5    entering: lat increases (south→north)
    gate_d  eastern boundary  lon=100  entering: lon decreases (east→west)
    """
    if gateway_id == "gate_a":
        return "entering" if curr_lon > prev_lon else "exiting"
    if gateway_id == "gate_b":
        return "entering" if curr_lat < prev_lat else "exiting"
    if gateway_id == "gate_c":
        return "entering" if curr_lat > prev_lat else "exiting"
    if gateway_id == "gate_d":
        return "entering" if curr_lon < prev_lon else "exiting"
    return "unknown"


def _is_duplicate(
    mmsi: str, gateway_id: str, crossing_ts: datetime, db: Session
) -> bool:
    """Return True if a crossing already exists within the dedup window."""
    window_start = crossing_ts - timedelta(minutes=DEDUP_WINDOW_MINUTES)
    existing = (
        db.query(GatewayCrossing)
        .filter(
            GatewayCrossing.mmsi       == mmsi,
            GatewayCrossing.gateway_id == gateway_id,
            GatewayCrossing.timestamp  >= window_start,
            GatewayCrossing.timestamp  <= crossing_ts,
        )
        .first()
    )
    return existing is not None


# ── Public API ────────────────────────────────────────────────────────────────

def detect_and_record_crossings(
    mmsi: str,
    prev_lat: float,
    prev_lon: float,
    curr_lat: float,
    curr_lon: float,
    curr_ts: datetime,
    db: Session,
) -> List[str]:
    """
    Detect gateway crossings for the segment (prev → curr) and persist them.

    Returns a list of gateway IDs that were crossed (empty if none).
    Duplicate crossings within DEDUP_WINDOW_MINUTES are automatically skipped.
    """
    # Shapely LineString in (lon, lat) order — GeoJSON convention
    segment = LineString([(prev_lon, prev_lat), (curr_lon, curr_lat)])
    gateway_lines = _gateway_shapely_lines(db)
    crossed: List[str] = []

    for gw in gateway_lines:
        if not segment.intersects(gw["line"]):
            continue

        if _is_duplicate(mmsi, gw["id"], curr_ts, db):
            continue  # skip duplicate within 30-min window

        pt = _intersection_point(segment, gw["line"])
        ix_lat = pt[0] if pt else curr_lat
        ix_lon = pt[1] if pt else curr_lon

        direction = _crossing_direction(prev_lat, prev_lon, curr_lat, curr_lon, gw["id"])

        crossing = GatewayCrossing(
            mmsi=mmsi,
            gateway_id=gw["id"],
            gateway_name=gw["name"],
            timestamp=curr_ts,
            direction=direction,
            latitude=ix_lat,
            longitude=ix_lon,
        )
        db.add(crossing)
        crossed.append(gw["id"])

    if crossed:
        db.flush()

    return crossed

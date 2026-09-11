"""
Vessel endpoints — tracks, timelines, events.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import Vessel, AISPosition, BehaviourEvent
from app.services.memory_service import (
    get_vessel_track,
    get_vessel_timeline,
    get_all_vessels_summary,
    get_recent_crossings,
)

router = APIRouter(prefix="/api/vessels", tags=["vessels"])


@router.get("")
def list_vessels(db: Session = Depends(get_db)):
    """List all vessels with journey summary."""
    return get_all_vessels_summary(db)


@router.get("/crossings/recent")
def recent_crossings(limit: int = 30, db: Session = Depends(get_db)):
    """Recent gateway crossing events (for the live feed panel)."""
    return get_recent_crossings(db, limit=limit)


@router.get("/{mmsi}")
def get_vessel(mmsi: str, db: Session = Depends(get_db)):
    """Get a single vessel record."""
    vessel = db.query(Vessel).filter(Vessel.mmsi == mmsi).first()
    if not vessel:
        raise HTTPException(status_code=404, detail="Vessel not found")
    return vessel.to_dict()


@router.get("/{mmsi}/track")
def get_track(mmsi: str, db: Session = Depends(get_db)):
    """
    Return the full AIS track for a vessel as a GeoJSON LineString + raw positions.
    """
    positions = get_vessel_track(mmsi, db)
    if not positions:
        raise HTTPException(status_code=404, detail="No track data for this vessel")

    geojson_coords = [[p["longitude"], p["latitude"]] for p in positions]

    return {
        "mmsi": mmsi,
        "positions": positions,
        "geojson": {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": geojson_coords,
            },
            "properties": {"mmsi": mmsi},
        },
    }


@router.get("/{mmsi}/timeline")
def get_timeline(mmsi: str, db: Session = Depends(get_db)):
    """Return the unified journey timeline (gateway crossings + behaviour events)."""
    return get_vessel_timeline(mmsi, db)


@router.get("/{mmsi}/events")
def get_events(mmsi: str, db: Session = Depends(get_db)):
    """Return behaviour events for a vessel."""
    events = (
        db.query(BehaviourEvent)
        .filter(BehaviourEvent.mmsi == mmsi)
        .order_by(BehaviourEvent.start_time)
        .all()
    )
    return [e.to_dict() for e in events]

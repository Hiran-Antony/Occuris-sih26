"""
Gateway API — /api/gateways

GET  /api/gateways            → GeoJSON FeatureCollection of all gateways
GET  /api/gateways/crossings  → paginated crossing log (filterable by mmsi / gateway_id)
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Gateway, GatewayCrossing

router = APIRouter(prefix="/api/gateways", tags=["gateways"])


@router.get("", summary="List all gateways as GeoJSON FeatureCollection")
def list_gateways(db: Session = Depends(get_db)):
    """
    Returns every registered gateway as a GeoJSON FeatureCollection.
    Each feature's geometry is the LineString of that boundary.
    """
    gateways = db.query(Gateway).all()
    return {
        "type": "FeatureCollection",
        "features": [gw.to_geojson_feature() for gw in gateways],
    }


@router.get("/crossings", summary="List gateway crossing events")
def list_crossings(
    mmsi:       Optional[str] = Query(None, description="Filter by vessel MMSI"),
    gateway_id: Optional[str] = Query(None, description="Filter by gateway ID (e.g. gate_a)"),
    limit:      int           = Query(100, ge=1, le=1000, description="Max results"),
    db: Session = Depends(get_db),
):
    """
    Returns gateway crossing events, newest first.
    Optionally filter by vessel MMSI or gateway ID.
    """
    q = db.query(GatewayCrossing).order_by(GatewayCrossing.timestamp.desc())

    if mmsi:
        q = q.filter(GatewayCrossing.mmsi == mmsi)
    if gateway_id:
        q = q.filter(GatewayCrossing.gateway_id == gateway_id)

    crossings = q.limit(limit).all()
    return {
        "total":     len(crossings),
        "crossings": [c.to_dict() for c in crossings],
    }

"""
AIS real-time ingestion API — /api/ais

POST /api/ais/positions
    Accept a single AIS position update, persist it, then detect & record
    any gateway crossings against the vessel's previous known position.

    Auto-creates a DEMO vessel record when the MMSI is not yet in the DB.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AISPosition, Vessel
from app.services.gateway_crossing_service import detect_and_record_crossings

router = APIRouter(prefix="/api/ais", tags=["ais"])


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class AISPositionIn(BaseModel):
    """Inbound AIS position message."""
    mmsi:      str           = Field(..., description="Maritime Mobile Service Identity")
    timestamp: datetime      = Field(..., description="UTC observation time (ISO-8601)")
    latitude:  float         = Field(..., ge=-90,  le=90,  description="WGS-84 latitude")
    longitude: float         = Field(..., ge=-180, le=180, description="WGS-84 longitude")
    sog:       float         = Field(0.0,  description="Speed over ground (knots)")
    cog:       float         = Field(0.0,  description="Course over ground (°)")
    heading:   Optional[float] = Field(None, description="True heading (°), null if unavailable")

    class Config:
        json_schema_extra = {
            "example": {
                "mmsi":      "DEMO-123456789",
                "timestamp": "2026-09-11T10:00:00Z",
                "latitude":  12.5,
                "longitude": 79.5,   # just west of gate_a at lon=80
                "sog":       10.2,
                "cog":       90.0,
                "heading":   90,
            }
        }


class AISPositionResponse(BaseModel):
    status:             str
    mmsi:               str
    position_id:        int
    crossings_detected: List[str]
    message:            str


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post(
    "/positions",
    response_model=AISPositionResponse,
    summary="Ingest an AIS position and detect gateway crossings",
)
def ingest_position(
    payload: AISPositionIn,
    db: Session = Depends(get_db),
) -> AISPositionResponse:
    """
    Ingest one AIS position update.

    1. Auto-creates a *DEMO* vessel row if the MMSI is unknown.
    2. Persists the position.
    3. Compares against the vessel's previous position using Shapely
       LineString intersection to detect gateway crossings.
    4. Records each unique crossing (30-minute dedup window).

    Returns a summary including which gateways (if any) were crossed.
    """
    mmsi = payload.mmsi.strip()

    # ── 1. Ensure vessel exists ───────────────────────────────────────────────
    vessel = db.query(Vessel).filter(Vessel.mmsi == mmsi).first()
    if vessel is None:
        vessel = Vessel(
            mmsi=mmsi,
            vessel_type="DEMO",
            name=f"DEMO-{mmsi}",
            flag="DEMO",
        )
        db.add(vessel)
        db.flush()

    # ── 2. Fetch previous position ────────────────────────────────────────────
    prev = (
        db.query(AISPosition)
        .filter(AISPosition.mmsi == mmsi)
        .order_by(AISPosition.timestamp.desc())
        .first()
    )

    # Reject out-of-order messages
    if prev is not None and payload.timestamp <= prev.timestamp:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Timestamp {payload.timestamp.isoformat()} is not newer than "
                f"the last known position at {prev.timestamp.isoformat()}."
            ),
        )

    # ── 3. Persist current position ───────────────────────────────────────────
    pos = AISPosition(
        mmsi=mmsi,
        timestamp=payload.timestamp,
        latitude=payload.latitude,
        longitude=payload.longitude,
        speed=payload.sog,
        course=payload.cog,
        heading=payload.heading,
    )
    db.add(pos)
    db.flush()

    # ── 4. Detect gateway crossings ───────────────────────────────────────────
    crossed: List[str] = []
    if prev is not None:
        crossed = detect_and_record_crossings(
            mmsi=mmsi,
            prev_lat=prev.latitude,
            prev_lon=prev.longitude,
            curr_lat=payload.latitude,
            curr_lon=payload.longitude,
            curr_ts=payload.timestamp,
            db=db,
        )

    db.commit()

    return AISPositionResponse(
        status="ok",
        mmsi=mmsi,
        position_id=pos.id,
        crossings_detected=crossed,
        message=(
            f"Crossing detected at: {', '.join(crossed)}"
            if crossed
            else (
                "First position recorded — no previous point to compare."
                if prev is None
                else "No gateway crossing detected."
            )
        ),
    )

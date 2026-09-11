"""
Journeys and dashboard stats endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Journey, GatewayCrossing
from app.services.memory_service import get_dashboard_stats

router = APIRouter(tags=["journeys"])

# ── Journey routes ─────────────────────────────────────────────────────────

journey_router = APIRouter(prefix="/api/journeys")


@journey_router.get("")
def list_journeys(db: Session = Depends(get_db)):
    journeys = db.query(Journey).order_by(Journey.entry_time).all()
    return [j.to_dict() for j in journeys]


@journey_router.get("/{journey_id}")
def get_journey(journey_id: int, db: Session = Depends(get_db)):
    j = db.query(Journey).filter(Journey.id == journey_id).first()
    if not j:
        raise HTTPException(status_code=404, detail="Journey not found")
    return j.to_dict()


# ── Dashboard stats ────────────────────────────────────────────────────────

dashboard_router = APIRouter(prefix="/api/dashboard")


@dashboard_router.get("/stats")
def stats(db: Session = Depends(get_db)):
    """Counts for the monitoring dashboard cards."""
    return get_dashboard_stats(db)


@dashboard_router.get("/gateway-crossings")
def gateway_crossings(limit: int = 50, db: Session = Depends(get_db)):
    """All gateway crossings, newest first."""
    crossings = (
        db.query(GatewayCrossing)
        .order_by(GatewayCrossing.timestamp.desc())
        .limit(limit)
        .all()
    )
    return [c.to_dict() for c in crossings]

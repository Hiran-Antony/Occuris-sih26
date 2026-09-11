from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import SpillIncident
from app.services.forensics_service import scan_sar_images, process_sar_image

router = APIRouter(prefix="/api/forensics", tags=["forensics"])

@router.get("/sar-images")
def list_sar_images():
    """List available SAR images in the data/sar directory."""
    return {"images": scan_sar_images()}

@router.post("/process-image")
def trigger_process_image(filename: str, db: Session = Depends(get_db)):
    """Process a specific SAR image through the forensic pipeline."""
    try:
        incident = process_sar_image(filename, db)
        return {"status": "success", "incident": incident.to_dict()}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/incidents")
def list_incidents(db: Session = Depends(get_db)):
    """List all processed spill incidents."""
    incidents = db.query(SpillIncident).order_by(SpillIncident.detected_at.desc()).all()
    return [inc.to_dict() for inc in incidents]

@router.get("/incidents/{incident_id}")
def get_incident(incident_id: int, db: Session = Depends(get_db)):
    """Get details of a specific incident."""
    incident = db.query(SpillIncident).filter(SpillIncident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident.to_dict()

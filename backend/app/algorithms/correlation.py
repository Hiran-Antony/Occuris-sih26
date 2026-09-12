from datetime import timedelta
import math
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models import SpillIncident, AISPosition, BehaviourEvent, Vessel

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate the great circle distance between two points on the earth (specified in decimal degrees)."""
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    r = 6371 # Radius of earth in kilometers
    return c * r

def run_memory_rewind(incident: SpillIncident, db: Session):
    """
    Steps 11-15: Trigger Memory Rewind, Filter Candidates, Replay Journeys, Correlate, Rank.
    """
    if not incident.origin_lat or not incident.release_start or not incident.release_end:
        return []

    # Pad the time window by 1 hour on each side for safety
    start_time = incident.release_start - timedelta(hours=1)
    end_time = incident.release_end + timedelta(hours=1)
    
    # 1. Fetch all unique MMSIs that transmitted during this time
    positions = db.query(AISPosition).filter(
        and_(
            AISPosition.timestamp >= start_time,
            AISPosition.timestamp <= end_time
        )
    ).all()
    
    candidate_mmsis = set([p.mmsi for p in positions])
    
    results = []
    
    for mmsi in candidate_mmsis:
        # Get vessel details
        vessel = db.query(Vessel).filter(Vessel.mmsi == mmsi).first()
        vessel_name = vessel.name if vessel else "Unknown Vessel"
        
        # Get positions for this specific vessel in the window
        vessel_positions = [p for p in positions if p.mmsi == mmsi]
        
        # Calculate minimum distance to origin
        min_dist = float('inf')
        for p in vessel_positions:
            dist = calculate_distance(incident.origin_lat, incident.origin_lon, p.latitude, p.longitude)
            if dist < min_dist:
                min_dist = dist
                
        # If vessel never came within 50km of the origin zone, discard as Low Priority/Irrelevant
        if min_dist > 50:
            continue
            
        # Check for behaviour events during this window
        events = db.query(BehaviourEvent).filter(
            and_(
                BehaviourEvent.mmsi == mmsi,
                BehaviourEvent.start_time >= start_time,
                BehaviourEvent.start_time <= end_time
            )
        ).all()
        
        # Generate reasons and calculate priority score (0-100)
        score = 0
        reasons = []
        
        # Proximity score (0-40 points)
        # 0km = 40 points, 20km = 0 points
        if min_dist <= 20:
            proximity_points = 40 * (1 - (min_dist / 20))
            score += proximity_points
            reasons.append(f"Passed within {min_dist:.1f}km of estimated spill origin.")
        
        # Behaviour score (0-60 points)
        if events:
            for event in events:
                if event.event_type == "Unexplained Stopping":
                    score += 60
                    reasons.append(f"Flagged for Unexplained Stopping during release window.")
                else:
                    score += 20
                    reasons.append(f"Flagged for {event.event_type}.")
        else:
            reasons.append("Maintained consistent speed and trajectory (No anomalies).")
            
        # Determine priority category
        if score >= 75:
            priority = "High Priority"
        elif score >= 40:
            priority = "Medium Priority"
        else:
            priority = "Low Priority"
            
        results.append({
            "mmsi": mmsi,
            "vessel_name": vessel_name,
            "min_distance_km": round(min_dist, 2),
            "match_score": round(score, 1),
            "priority": priority,
            "reasons": reasons,
            "event_count": len(events)
        })
        
    # Sort by match score descending
    results.sort(key=lambda x: x["match_score"], reverse=True)
    return results

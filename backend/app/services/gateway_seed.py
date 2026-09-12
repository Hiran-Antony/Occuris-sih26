"""
Gateway seed data — populates the four demo gateways (gate_a … gate_d)
into the gateways table if they are not already present.

All coordinates follow GeoJSON convention: [longitude, latitude].
The region covered is the Bay of Bengal prototype area (80–100°E, 5–22°N).
"""
import json
from sqlalchemy.orm import Session

from app.models import Gateway

# ── Demo gateway definitions ──────────────────────────────────────────────────
DEMO_GATEWAYS = [
    {
        "id": "gate_a",
        "name": "Gateway Alpha — Western Boundary",
        "color": "#00ff88",
        "description": "Western entry / exit — 84°E meridian (Strictly Oceanic)",
        "geometry": {
            "type": "LineString",
            "coordinates": [[84.0, 6.0], [84.0, 19.5]],
        },
    },
    {
        "id": "gate_b",
        "name": "Gateway Bravo — Northern Boundary",
        "color": "#00d4ff",
        "description": "Northern entry / exit — 19.5°N parallel (Strictly Oceanic)",
        "geometry": {
            "type": "LineString",
            "coordinates": [[84.0, 19.5], [93.5, 19.5]],
        },
    },
    {
        "id": "gate_c",
        "name": "Gateway Charlie — Southern Boundary",
        "color": "#ffb800",
        "description": "Southern entry / exit — 6°N parallel (Deep Ocean Corridor)",
        "geometry": {
            "type": "LineString",
            "coordinates": [[84.0, 6.0], [93.5, 6.0]],
        },
    },
    {
        "id": "gate_d",
        "name": "Gateway Delta — Eastern Boundary",
        "color": "#ff6b35",
        "description": "Eastern entry / exit — 93.5°E meridian (Andaman Passage)",
        "geometry": {
            "type": "LineString",
            "coordinates": [[93.5, 6.0], [93.5, 19.5]],
        },
    },
]


def seed_gateways(db: Session) -> None:
    """Insert demo gateways if the table is empty."""
    existing = db.query(Gateway).count()
    if existing > 0:
        return

    for gw in DEMO_GATEWAYS:
        record = Gateway(
            id=gw["id"],
            name=gw["name"],
            color=gw["color"],
            description=gw["description"],
            geometry=json.dumps(gw["geometry"]),
        )
        db.add(record)

    db.commit()
    print(f"[OK] Seeded {len(DEMO_GATEWAYS)} demo gateways.")

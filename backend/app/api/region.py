"""
Region and gateway endpoints.
"""
import json
import os
from fastapi import APIRouter

router = APIRouter(prefix="/api/region", tags=["region"])

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "region")


@router.get("")
def get_region():
    """Return the Bay of Bengal monitoring polygon as GeoJSON."""
    with open(os.path.join(DATA_DIR, "bob_polygon.geojson")) as f:
        return json.load(f)


@router.get("/gateways")
def get_gateways():
    """Return all 4 virtual gateways as a GeoJSON FeatureCollection."""
    with open(os.path.join(DATA_DIR, "gateways.geojson")) as f:
        return json.load(f)

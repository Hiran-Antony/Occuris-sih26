"""
Geometry algorithms using Shapely.
All spatial operations for Occuris Part 1.
NOTE: Shapely uses (longitude, latitude) order internally.
"""
import math
import json
import os
from shapely.geometry import Point, LineString, shape
from shapely.ops import unary_union
from typing import Optional, Tuple

# ── Bay of Bengal bounds (rectangular prototype region) ────────────────────
BOB_WEST = 80.0
BOB_EAST = 100.0
BOB_SOUTH = 5.0
BOB_NORTH = 22.0

# Gateway boundary hint for direction detection
GATEWAY_BOUNDS = {
    "A": {"axis": "lon", "value": BOB_WEST},
    "B": {"axis": "lat", "value": BOB_NORTH},
    "C": {"axis": "lat", "value": BOB_SOUTH},
    "D": {"axis": "lon", "value": BOB_EAST},
}

_region_shape = None
_gateway_shapes = None


def _data_path(rel: str) -> str:
    base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "..", "..", "data", rel)


def get_region_shape():
    global _region_shape
    if _region_shape is None:
        with open(_data_path("region/bob_polygon.geojson")) as f:
            gj = json.load(f)
        _region_shape = shape(gj["features"][0]["geometry"])
    return _region_shape


def get_gateway_shapes():
    global _gateway_shapes
    if _gateway_shapes is None:
        with open(_data_path("region/gateways.geojson")) as f:
            gj = json.load(f)
        _gateway_shapes = []
        for feat in gj["features"]:
            _gateway_shapes.append({
                "id": feat["properties"]["id"],
                "name": feat["properties"]["name"],
                "color": feat["properties"]["color"],
                "geometry": shape(feat["geometry"]),
            })
    return _gateway_shapes


# ── Core spatial functions ─────────────────────────────────────────────────

def point_in_region(lat: float, lon: float) -> bool:
    """Check if (lat, lon) is inside the BOB monitoring region."""
    return get_region_shape().contains(Point(lon, lat))


def haversine_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in nautical miles."""
    R = 3440.065
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(max(0, a)))


def implied_speed_knots(
    lat1: float, lon1: float, t1,
    lat2: float, lon2: float, t2
) -> float:
    """Speed implied by two positions and their timestamps (in knots)."""
    dist_nm = haversine_nm(lat1, lon1, lat2, lon2)
    delta_hours = (t2 - t1).total_seconds() / 3600
    if delta_hours <= 0:
        return 0.0
    return dist_nm / delta_hours


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial bearing from point 1 to point 2 in degrees (0–360)."""
    lat1, lat2 = math.radians(lat1), math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def detect_gateway_crossing(
    prev_lat: float, prev_lon: float, prev_inside: bool,
    curr_lat: float, curr_lon: float, curr_inside: bool,
) -> Optional[Tuple[str, str]]:
    """
    Detect which gateway was crossed and in which direction.
    Returns (gateway_id, direction) or None.
    direction: "entering" | "exiting"
    """
    if prev_inside == curr_inside:
        return None

    direction = "entering" if (not prev_inside and curr_inside) else "exiting"

    # The outside point tells us which boundary was crossed
    outer_lat = prev_lat if direction == "entering" else curr_lat
    outer_lon = prev_lon if direction == "entering" else curr_lon

    # Distance to each boundary
    d_west  = abs(outer_lon - BOB_WEST)
    d_east  = abs(outer_lon - BOB_EAST)
    d_south = abs(outer_lat - BOB_SOUTH)
    d_north = abs(outer_lat - BOB_NORTH)

    min_d = min(d_west, d_east, d_south, d_north)

    if min_d == d_west:
        return "A", direction
    elif min_d == d_north:
        return "B", direction
    elif min_d == d_south:
        return "C", direction
    else:
        return "D", direction


def track_to_linestring(positions: list) -> Optional[LineString]:
    """Convert a list of (lat, lon) tuples to a Shapely LineString."""
    if len(positions) < 2:
        return None
    return LineString([(lon, lat) for lat, lon in positions])


def min_distance_to_point_nm(track_positions: list, target_lat: float, target_lon: float) -> float:
    """
    Minimum distance (nm) between a vessel track and a target point.
    track_positions: list of (lat, lon) tuples
    """
    target = Point(target_lon, target_lat)
    min_dist = float("inf")
    for lat, lon in track_positions:
        d = haversine_nm(lat, lon, target_lat, target_lon)
        if d < min_dist:
            min_dist = d
    return min_dist

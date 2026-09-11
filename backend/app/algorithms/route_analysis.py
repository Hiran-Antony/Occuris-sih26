"""
Expected vs Actual journey analysis.
Uses vessel-type speed profiles and gateway distances.
"""
from app.algorithms.geometry import haversine_nm

# Average cruising speeds by vessel type (knots)
VESSEL_SPEED_PROFILE = {
    "tanker": 10.0,
    "cargo": 12.0,
    "fishing": 6.0,
    "passenger": 16.0,
    "default": 10.0,
}

# Gateway centre-point coordinates (lat, lon) for distance estimation
GATEWAY_CENTERS = {
    "A": (15.0, 80.0),
    "B": (22.0, 90.0),
    "C": (5.0, 90.0),
    "D": (12.0, 100.0),
}


def gateway_distance_nm(entry_gw: str, exit_gw: str) -> float:
    """Straight-line distance between gateway centres in nautical miles."""
    if entry_gw not in GATEWAY_CENTERS or exit_gw not in GATEWAY_CENTERS:
        return 500.0   # fallback
    lat1, lon1 = GATEWAY_CENTERS[entry_gw]
    lat2, lon2 = GATEWAY_CENTERS[exit_gw]
    return haversine_nm(lat1, lon1, lat2, lon2)


def expected_journey_hours(entry_gw: str, exit_gw: str, vessel_type: str) -> float:
    """
    Expected transit time for a vessel type travelling between two gateways.
    Adds a 15% buffer for normal navigation (mild currents, minor course corrections).
    """
    speed = VESSEL_SPEED_PROFILE.get(vessel_type, VESSEL_SPEED_PROFILE["default"])
    dist_nm = gateway_distance_nm(entry_gw, exit_gw)
    raw_hours = dist_nm / speed
    return round(raw_hours * 1.15, 2)   # 15% navigation buffer


def delay_classification(delay_hours: float) -> str:
    """
    Classify a journey delay.
    Returns one of: 'on_time' | 'minor_delay' | 'significant_delay' | 'major_delay'
    """
    if delay_hours <= 1.0:
        return "on_time"
    elif delay_hours <= 3.0:
        return "minor_delay"
    elif delay_hours <= 6.0:
        return "significant_delay"
    else:
        return "major_delay"

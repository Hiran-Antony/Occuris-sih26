"""
Anomaly detection algorithms for vessel behaviour analysis.
All results are clearly labelled as indicators — never as confirmed events.
"""
from datetime import timedelta
from typing import List, Dict, Any
from app.algorithms.geometry import implied_speed_knots, haversine_nm
from app.algorithms.route_analysis import VESSEL_SPEED_PROFILE

# ── Thresholds ─────────────────────────────────────────────────────────────
AIS_GAP_THRESHOLD_MIN = 45          # minutes — gap longer than this is flagged
IMPOSSIBLE_SPEED_THRESHOLD = 45.0   # knots — implied speed above this is flagged
LOW_SPEED_THRESHOLD = 1.5           # knots — below this → possible stationary
SLOW_SPEED_FRACTION = 0.45          # < 45% of vessel average → slowdown
LOW_SPEED_MIN_DURATION_MIN = 20     # minimum duration for low-speed event
SLOWDOWN_MIN_DURATION_MIN = 30      # minimum duration for slowdown event
ROUTE_DEVIATION_THRESHOLD_NM = 20   # nm — deviation from direct path

GATEWAY_CENTERS = {
    "A": (15.0, 80.0),
    "B": (22.0, 90.0),
    "C": (5.0, 90.0),
    "D": (12.0, 100.0),
}


def detect_ais_gaps(positions: List[Dict]) -> List[Dict]:
    """
    Find AIS transmission gaps.
    positions: sorted list of {timestamp (datetime), latitude, longitude, speed}
    Returns list of gap event dicts.
    """
    events = []
    for i in range(1, len(positions)):
        prev = positions[i - 1]
        curr = positions[i]
        gap_min = (curr["timestamp"] - prev["timestamp"]).total_seconds() / 60
        if gap_min >= AIS_GAP_THRESHOLD_MIN:
            events.append({
                "event_type": "ais_gap",
                "start_time": prev["timestamp"],
                "end_time": curr["timestamp"],
                "latitude": (prev["latitude"] + curr["latitude"]) / 2,
                "longitude": (prev["longitude"] + curr["longitude"]) / 2,
                "description": f"Possible AIS gap — {gap_min:.0f} min with no transmission",
                "severity": "high" if gap_min > 120 else "medium",
            })
    return events


def detect_impossible_jumps(positions: List[Dict]) -> List[Dict]:
    """
    Flag position records where implied speed is physically impossible.
    """
    events = []
    for i in range(1, len(positions)):
        prev = positions[i - 1]
        curr = positions[i]
        spd = implied_speed_knots(
            prev["latitude"], prev["longitude"], prev["timestamp"],
            curr["latitude"], curr["longitude"], curr["timestamp"],
        )
        if spd > IMPOSSIBLE_SPEED_THRESHOLD:
            events.append({
                "event_type": "impossible_jump",
                "start_time": prev["timestamp"],
                "end_time": curr["timestamp"],
                "latitude": curr["latitude"],
                "longitude": curr["longitude"],
                "description": f"Possible AIS anomaly — implied speed {spd:.0f} kn exceeds physical limit",
                "severity": "high",
            })
    return events


def detect_low_speed_periods(positions: List[Dict], vessel_type: str) -> List[Dict]:
    """
    Detect prolonged stationary / slow-speed periods.
    """
    events = []
    base_speed = VESSEL_SPEED_PROFILE.get(vessel_type, VESSEL_SPEED_PROFILE["default"])
    slow_threshold = base_speed * SLOW_SPEED_FRACTION

    in_low = False
    low_start = None
    low_pts = []

    for pos in positions:
        spd = pos.get("speed", 0.0)
        if spd < slow_threshold:
            if not in_low:
                in_low = True
                low_start = pos["timestamp"]
                low_pts = [pos]
            else:
                low_pts.append(pos)
        else:
            if in_low:
                duration_min = (low_pts[-1]["timestamp"] - low_start).total_seconds() / 60
                if pos["speed"] < LOW_SPEED_THRESHOLD:
                    threshold_min = LOW_SPEED_MIN_DURATION_MIN
                    evt_type = "operational_stop"
                    desc = f"Prolonged low-speed/stationary period — {duration_min:.0f} min"
                else:
                    threshold_min = SLOWDOWN_MIN_DURATION_MIN
                    evt_type = "speed_reduction"
                    desc = f"Speed reduction below vessel average — {duration_min:.0f} min"

                if duration_min >= threshold_min:
                    mid_idx = len(low_pts) // 2
                    events.append({
                        "event_type": evt_type,
                        "start_time": low_start,
                        "end_time": low_pts[-1]["timestamp"],
                        "latitude": low_pts[mid_idx]["latitude"],
                        "longitude": low_pts[mid_idx]["longitude"],
                        "description": desc,
                        "severity": "medium" if duration_min < 90 else "high",
                    })
                in_low = False
                low_start = None
                low_pts = []

    return events


def detect_route_deviation(positions: List[Dict], entry_gw: str, exit_gw: str) -> List[Dict]:
    """
    Detect significant deviation from the direct expected route.
    """
    if entry_gw not in GATEWAY_CENTERS or exit_gw not in GATEWAY_CENTERS:
        return []

    events = []
    lat1, lon1 = GATEWAY_CENTERS[entry_gw]
    lat2, lon2 = GATEWAY_CENTERS[exit_gw]
    total_dist = haversine_nm(lat1, lon1, lat2, lon2)
    if total_dist == 0:
        return []

    max_dev = 0.0
    max_dev_pos = None

    for pos in positions:
        # Perpendicular distance from point to great-circle path (approx)
        # Simplified: compare actual track progress vs straight-line
        d_from_start = haversine_nm(lat1, lon1, pos["latitude"], pos["longitude"])
        d_from_end = haversine_nm(pos["latitude"], pos["longitude"], lat2, lon2)
        progress = d_from_start / total_dist if total_dist > 0 else 0

        # Expected position at this progress fraction
        exp_lat = lat1 + (lat2 - lat1) * progress
        exp_lon = lon1 + (lon2 - lon1) * progress
        deviation = haversine_nm(pos["latitude"], pos["longitude"], exp_lat, exp_lon)

        if deviation > max_dev:
            max_dev = deviation
            max_dev_pos = pos

    if max_dev >= ROUTE_DEVIATION_THRESHOLD_NM and max_dev_pos is not None:
        events.append({
            "event_type": "route_deviation",
            "start_time": max_dev_pos["timestamp"],
            "end_time": max_dev_pos["timestamp"],
            "latitude": max_dev_pos["latitude"],
            "longitude": max_dev_pos["longitude"],
            "description": f"Route deviation detected — max {max_dev:.1f} nm from expected path",
            "severity": "medium" if max_dev < 40 else "high",
        })

    return events


def run_all_detectors(positions: List[Dict], vessel_type: str,
                      entry_gw: str = None, exit_gw: str = None) -> List[Dict]:
    """Run all behaviour detectors and return combined events."""
    events = []
    events.extend(detect_ais_gaps(positions))
    events.extend(detect_impossible_jumps(positions))
    events.extend(detect_low_speed_periods(positions, vessel_type))
    if entry_gw and exit_gw:
        events.extend(detect_route_deviation(positions, entry_gw, exit_gw))
    events.sort(key=lambda e: e["start_time"])
    return events
